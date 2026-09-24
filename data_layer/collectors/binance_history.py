"""Backfill years of OHLCV history from Binance's free public archive.

WHY: the store holds 9.95 days of price data. Nothing can be tested on that.
This archive has monthly files back to 2020-01 (80 months) for USDT perps.

VERIFIED BEFORE WRITING THIS (2026-09-03):
  - archive listing: 80 monthly files, BTCUSDT-1m-2020-01 .. 2026-08
  - data types available: klines, aggTrades, bookTicker, fundingRate,
    indexPriceKlines, markPriceKlines, premiumIndexKlines, trades
  - CSV has a HEADER row and 12 columns incl. taker_buy_volume (signed flow)
  - 172 of our 178 tracked coins are on Binance futures, 5 of them only as
    1000X contracts (1000PEPE, 1000SHIB, 1000BONK, 1000FLOKI, 1000LUNC)

THE MULTIPLIER IS NOT OPTIONAL: a 1000PEPE price is 1000x the PEPE price.
Storing it raw would corrupt every return, vol and correlation for that coin.
Prices are divided / volumes multiplied on load, and the mapping is recorded
in venue_symbol so it is auditable.

Resumable: skips (asset, interval, month) already present in the store.

Run:  python data_layer/collectors/binance_history.py --interval 1h --months 12
      python data_layer/collectors/binance_history.py --interval 1h --all --symbols BTC,ETH,SOL
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "store"))
import store  # noqa: E402

UA = {"User-Agent": store.user_agent()}
BASE = "https://data.binance.vision/data/futures/um/monthly/klines"
FAPI = "https://fapi.binance.com/fapi/v1/exchangeInfo"
MULT_PREFIXES = [("", 1), ("1000", 1000), ("1000000", 1_000_000)]


def http(url, timeout=30, retries=4):
    """Fetch with exponential backoff.

    The first full run fired ~13,760 requests with no pacing and Binance
    throttled it: 9,436 errors, and only 56 of 172 coins actually loaded.
    A 404 is a real 'this month does not exist' and must NOT be retried;
    everything else is treated as transient and backed off.

    timeout was 120 s. On 2026-09-13 a run sat for 20+ minutes in
    _read_status on a dead connection while a fresh client answered 36
    requests in 25 s - a monthly 1h file is ~35 KB, so 30 s is generous and a
    dead socket now costs 30 s per attempt instead of 2 minutes.
    """
    delay = 1.0
    for attempt in range(retries):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=timeout).read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            if attempt == retries - 1:
                raise
            time.sleep(delay)
            delay *= 2
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")


LISTING = ("https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
           "?prefix=data/futures/um/monthly/klines/&delimiter=/")


def archive_symbols():
    """Every USDT-margined perp that has monthly kline files in the public archive.
    The bucket listing is paged (1,000 keys per page), so follow the marker."""
    import re
    out, marker = set(), ""
    while True:
        xml = http(LISTING + (f"&marker={marker}" if marker else "")).decode("utf-8", "replace")
        page = re.findall(r"<Prefix>data/futures/um/monthly/klines/([^/<]+)/</Prefix>", xml)
        out.update(s for s in page if s.endswith("USDT"))
        if "<IsTruncated>true</IsTruncated>" not in xml or not page:
            return out
        nxt = re.findall(r"<NextMarker>([^<]+)</NextMarker>", xml)
        marker = nxt[0] if nxt else f"data/futures/um/monthly/klines/{page[-1]}/"


def binance_symbol_map(assets, conn=None):
    """our asset symbol -> (binance symbol, multiplier). Multiplier matters.

    GEO-BLOCK: Binance's API hosts (fapi/api.binance.com) return HTTP 451
    "Unavailable For Legal Reasons" from some regions (confirmed 2026-09-09). The ARCHIVE host data.binance.vision is NOT blocked.
    So we prefer the mapping already stored in venue_symbol and look up only
    the assets it does not know - through the API, or the archive's own
    listing when the API is blocked.
    """
    out = {}
    if conn is not None:
        for asset, sym, mult in conn.execute(
            "SELECT a.symbol, vs.symbol, vs.multiplier FROM venue_symbol vs "
            "JOIN venue v ON v.id=vs.venue_id JOIN asset a ON a.id=vs.asset_id "
            "WHERE v.name='binance' AND vs.symbol LIKE '%USDT'"
        ):
            if asset in assets:
                out[asset] = (sym, mult or 1)
        if out:
            print(f"  symbol map from DB: {len(out)} of {len(assets)} assets")
        if len(out) == len(set(assets)):
            return out
    todo = [a for a in assets if a not in out]

    try:
        ex = json.loads(http(FAPI, 30))
        trading = {s["symbol"] for s in ex["symbols"] if s.get("status") == "TRADING"}
    except Exception as e:
        # The API is geo-blocked (451) in some regions; the archive's own bucket
        # listing is not, and it names every USDT perp that has history files.
        print(f"  Binance API unreachable ({str(e)[:40]}) - reading the symbol list from the archive")
        try:
            trading = archive_symbols()
        except Exception as e2:
            raise SystemExit(f"Neither the Binance API nor the archive listing answered ({str(e2)[:60]}).")
        print(f"  archive lists {len(trading)} USDT perps")
    for a in todo:
        for pfx, mult in MULT_PREFIXES:
            cand = f"{pfx}{a}USDT"
            if cand in trading:
                out[a] = (cand, mult)
                break
    return out


def months_back(n):
    now = datetime.now(timezone.utc).replace(day=1)
    out = []
    for i in range(1, n + 1):
        d = (now - timedelta(days=1)).replace(day=1) if i == 1 else out[-1][2] - timedelta(days=1)
        d = d.replace(day=1)
        out.append((d.year, d.month, d))
    return [(y, m) for y, m, _ in out]


def all_months(start=(2020, 1)):
    now = datetime.now(timezone.utc)
    y, m = start
    out = []
    while (y, m) < (now.year, now.month):
        out.append((y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def load_month(conn, asset, asset_id, bsym, mult, venue_id, interval, y, m, stats):
    url = f"{BASE}/{bsym}/{interval}/{bsym}-{interval}-{y}-{m:02d}.zip"
    try:
        blob = http(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            stats["missing"] += 1
            return 0
        stats["error"] += 1
        return 0
    except Exception:
        stats["error"] += 1
        return 0

    try:
        z = zipfile.ZipFile(io.BytesIO(blob))
        raw = z.read(z.namelist()[0]).decode("utf-8", "replace")
    except Exception:
        stats["error"] += 1
        return 0

    rows = []
    for line in raw.splitlines():
        p = line.split(",")
        if len(p) < 9 or not p[0].isdigit():
            continue  # header or junk
        try:
            ts = int(p[0])
            # divide price by the contract multiplier, multiply size back up
            o, h, l, c = (float(p[1]) / mult, float(p[2]) / mult,
                          float(p[3]) / mult, float(p[4]) / mult)
            v = float(p[5]) * mult
            n = int(float(p[8]))
        except (ValueError, IndexError):
            continue
        rows.append((ts, venue_id, asset_id, interval, o, h, l, c, v, n))

    if not rows:
        return 0
    w = store.insert_many(conn, "ohlcv",
        ["ts_ms", "venue_id", "asset_id", "interval", "o", "h", "l", "c", "v", "n"], rows)
    conn.commit()
    stats["rows"] += w
    return w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", default="1h")
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--all", action="store_true", help="every month back to 2020-01")
    ap.add_argument("--symbols", help="comma list; default = every tracked asset")
    a = ap.parse_args()

    conn = store.init()
    vid = store.venue_id(conn, "binance", kind="cex")

    if a.symbols:
        want = [s.strip().upper() for s in a.symbols.split(",")]
    else:
        want = [r[0] for r in conn.execute(
            "SELECT DISTINCT a.symbol FROM asset a JOIN perp_state p ON p.asset_id=a.id")]
    print(f"resolving {len(want)} assets against Binance futures...")
    smap = binance_symbol_map(want, conn)
    print(f"  {len(smap)} resolved, {len(want)-len(smap)} not on Binance")
    mults = {k: v for k, v in smap.items() if v[1] != 1}
    if mults:
        print(f"  multiplier contracts: {mults}")

    # record the symbol mapping so it is auditable, not hidden in code
    for asset, (bsym, mult) in smap.items():
        aid = store.asset_id(conn, asset)
        conn.execute(
            "INSERT INTO venue_symbol(venue_id,asset_id,symbol,quote,multiplier) "
            "VALUES(?,?,?,?,?) ON CONFLICT(venue_id,symbol) DO UPDATE SET "
            "asset_id=excluded.asset_id, multiplier=excluded.multiplier",
            (vid, aid, bsym, "USDT", mult))
    conn.commit()

    months = all_months() if a.all else months_back(a.months)
    print(f"interval={a.interval}  months={len(months)}  "
          f"({months[-1][0]}-{months[-1][1]:02d} .. {months[0][0]}-{months[0][1]:02d})")
    print(f"tasks = {len(smap)*len(months):,}\n" + "=" * 74)

    stats = {"rows": 0, "missing": 0, "error": 0, "skipped": 0}
    t0 = time.time()
    done = 0
    for asset, (bsym, mult) in sorted(smap.items()):
        aid = store.asset_id(conn, asset)
        got = 0
        # Newest month first. A coin's archive runs from its listing month to
        # now, so once we have seen data and then hit two 404s in a row, every
        # older month is a 404 too - stop instead of asking for all of them.
        # (Measured 2026-09-13: oldest-first spent ~60 requests per 2025
        # listing, ~7,000 wasted requests across the 114 missing coins.)
        # Two in a row, not one, so a single missing archive month cannot
        # silently truncate a coin's history.
        seen_data, misses = False, 0
        for (y, m) in reversed(months):
            # resume: skip a month already loaded
            lo = int(datetime(y, m, 1, tzinfo=timezone.utc).timestamp() * 1000)
            hi = int((datetime(y + (m == 12), (m % 12) + 1, 1, tzinfo=timezone.utc)
                      ).timestamp() * 1000)
            have = conn.execute(
                "SELECT 1 FROM ohlcv WHERE asset_id=? AND interval=? AND ts_ms>=? AND ts_ms<? LIMIT 1",
                (aid, a.interval, lo, hi)).fetchone()
            if have:
                stats["skipped"] += 1
                seen_data, misses = True, 0
                continue
            before = stats["missing"]
            n = load_month(conn, asset, aid, bsym, mult, vid, a.interval, y, m, stats)
            got += n
            if stats["missing"] > before:
                misses += 1
                if seen_data and misses >= 2:
                    break
            elif n:
                seen_data, misses = True, 0
            time.sleep(0.12)   # pace: ~8 req/s, well under any throttle
        done += 1
        if got or done % 20 == 0:
            el = time.time() - t0
            print(f"  [{done:>3}/{len(smap)}] {asset:<10} {bsym:<16} +{got:>8,} rows   "
                  f"total {stats['rows']:>10,}   {el:.0f}s")
    store.log_run(conn, "binance_history", True, stats["rows"], int((time.time() - t0) * 1000))
    conn.commit()
    print("=" * 74)
    print(f"rows added: {stats['rows']:,}   months skipped(already had): {stats['skipped']:,}   "
          f"404s: {stats['missing']}   errors: {stats['error']}   {time.time()-t0:.0f}s")
    conn.close()


if __name__ == "__main__":
    main()
