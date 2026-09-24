"""Crowd positioning and open-interest history from Binance's public ARCHIVE.

    python scripts/backfill_positioning.py               # fill every missing day, every HL coin
    python scripts/backfill_positioning.py --days 90     # first fill goes 90 days back (default 30)
    python scripts/backfill_positioning.py --keep-5m     # also store the raw 5-minute rows
    python scripts/backfill_positioning.py --top 40      # just the liquid names
    python scripts/backfill_positioning.py --every 3600  # keep running, top up hourly
    python scripts/backfill_positioning.py --stats

WHY THE ARCHIVE. The first version of this script read four live endpoints on
fapi.binance.com. That host answers HTTP 451 (blocked for legal reasons) from
India AND the US - confirmed 2026-09-13 from the new PC. The archive host
data.binance.vision is not blocked, and its daily "metrics" file carries the
same four measurements at 5-minute steps:

    sum_open_interest / sum_open_interest_value   -> oi_coins, oi_usd
    count_long_short_ratio                        -> ls_ratio, long_frac  (share of ALL accounts long)
    sum_toptrader_long_short_ratio                -> top_ls_ratio, top_long_frac (share of top traders' POSITIONS long)
    sum_taker_long_short_vol_ratio                -> taker_ratio (5-minute rows only, see below)

Checked against the rows the API wrote on 2026-09-05: open interest agrees to
0.05%, both long shares agree to 4 decimals. long_frac is derived as r/(1+r)
from the ratio, which is exactly how Binance's longAccount relates to
longShortRatio (0.5193 <-> 1.0803 in the existing rows).

Honest limits:
  * A day's file appears the NEXT day. The newest row is always ~1 day old.
    Good for research and backtests; useless as a "right now" read.
  * The hourly taker ratio CANNOT be rebuilt from the archive. The API gave
    buys/sells over the whole hour; the archive gives it per 5-minute slice
    with no volumes to add back up (1.39 vs 4.17 at the same timestamp). So
    hourly rows carry taker_ratio = NULL and taker_buy_vol = NULL. With
    --keep-5m the 5-minute rows keep their own 5-minute taker ratio.
  * this is BINANCE's crowd, not Hyperliquid's. Related, not identical.
  * open interest is in CONTRACT units, as before (1000PEPEUSDT counts in
    thousands of PEPE). The multiplier lives in venue_symbol if you need it.

Resumable: positioning_days records every (coin, day) already loaded. A 404
on a day older than yesterday means the coin had no perp then and is marked
loaded with 0 rows; a 404 on yesterday means "not published yet" and is
retried on the next run. Existing rows are never overwritten (INSERT OR
IGNORE), so the API-era rows keep their hourly taker ratio.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

UA = {"User-Agent": "quant-research-bot" + ((" contact:" + __import__("os").environ["CONTACT_EMAIL"]) if __import__("os").environ.get("CONTACT_EMAIL") else "")}
BASE = "https://data.binance.vision/data/futures/um/daily/metrics"
ROOT = Path(__file__).resolve().parents[1]
STORE_DB = ROOT / "data" / "store.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS positioning (
  ts_ms  INTEGER NOT NULL,
  coin   TEXT    NOT NULL,
  period TEXT    NOT NULL,
  oi_coins REAL, oi_usd REAL,
  long_frac REAL, ls_ratio REAL,
  top_long_frac REAL, top_ls_ratio REAL,
  taker_buy_vol REAL, taker_ratio REAL,
  PRIMARY KEY (coin, period, ts_ms)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_pos_ts ON positioning(ts_ms);

CREATE TABLE IF NOT EXISTS backfill_log (
  ts_ms INTEGER PRIMARY KEY, period TEXT, coins INTEGER, rows INTEGER,
  failures TEXT, took_s REAL
);

CREATE TABLE IF NOT EXISTS positioning_days (
  coin TEXT NOT NULL, day TEXT NOT NULL, rows INTEGER NOT NULL,
  loaded_ms INTEGER NOT NULL,
  PRIMARY KEY (coin, day)
) WITHOUT ROWID;
"""


def http(url: str, timeout: int = 60, retries: int = 4) -> bytes:
    """Fetch with exponential backoff. A 404 is a real 'no such file' and is
    raised straight away; anything else is treated as transient."""
    delay = 1.0
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404 or attempt == retries - 1:
                raise
        except Exception:
            if attempt == retries - 1:
                raise
        time.sleep(delay)
        delay *= 2
    raise RuntimeError("unreachable")


def binance_symbol_map() -> Dict[str, str]:
    """our coin -> Binance USDT-perp symbol, from the venue_symbol table in
    store.db. Same source binance_history.py uses; the API that used to
    provide this list is the blocked one."""
    if not STORE_DB.exists():
        raise SystemExit(f"{STORE_DB} not found - the symbol map lives there")
    conn = sqlite3.connect(f"file:{STORE_DB}?mode=ro", uri=True, timeout=10)
    try:
        rows = conn.execute(
            "SELECT a.symbol, vs.symbol FROM venue_symbol vs "
            "JOIN venue v ON v.id=vs.venue_id JOIN asset a ON a.id=vs.asset_id "
            "WHERE v.name='binance' AND vs.symbol LIKE '%USDT'").fetchall()
    finally:
        conn.close()
    if not rows:
        raise SystemExit("venue_symbol has no binance rows - nothing to fetch")
    return {coin: sym for coin, sym in rows}


def parse_metrics(blob: bytes) -> List[dict]:
    z = zipfile.ZipFile(io.BytesIO(blob))
    text = z.read(z.namelist()[0]).decode("utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def to_ts_ms(s: str) -> int:
    return int(datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
               .replace(tzinfo=timezone.utc).timestamp() * 1000)


def fnum(row: dict, key: str):
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError):
        return None


def frac(ratio):
    """long/short ratio r -> share long. Binance: longAccount = r / (1 + r)."""
    return None if ratio is None else ratio / (1.0 + ratio)


def rows_for_day(coin: str, recs: List[dict], keep_5m: bool) -> List[Tuple]:
    out = []
    for r in sorted(recs, key=lambda x: x["create_time"]):
        ts = to_ts_ms(r["create_time"])
        ls = fnum(r, "count_long_short_ratio")
        top = fnum(r, "sum_toptrader_long_short_ratio")
        base = (fnum(r, "sum_open_interest"), fnum(r, "sum_open_interest_value"),
                frac(ls), ls, frac(top), top)
        if ts % 3_600_000 == 0:
            # hourly row: taker columns NULL on purpose (not the same measurement)
            out.append((ts, coin, "1h") + base + (None, None))
        if keep_5m:
            out.append((ts, coin, "5m") + base + (None, fnum(r, "sum_taker_long_short_vol_ratio")))
    return out


def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    # record_venues.py writes this file every 5 min; wait out its transaction
    # rather than dying on "database is locked".
    conn = sqlite3.connect(path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def days_to_load(conn: sqlite3.Connection, coin: str, lookback: int) -> List[date]:
    """Every day from the earliest loaded one (or `lookback` days ago,
    whichever is earlier) up to yesterday UTC that is not in positioning_days.
    Scanning the whole window each run is what makes a day that failed on a
    transient error get retried instead of silently skipped."""
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    have = {d for (d,) in conn.execute("SELECT day FROM positioning_days WHERE coin=?", (coin,))}
    start = yesterday - timedelta(days=lookback - 1)
    if have:
        start = min(start, date.fromisoformat(min(have)))
    d, out = start, []
    while d <= yesterday:
        if d.isoformat() not in have:
            out.append(d)
        d += timedelta(days=1)
    return out


def stats(conn: sqlite3.Connection) -> None:
    n = conn.execute("SELECT COUNT(*) FROM positioning").fetchone()[0]
    if not n:
        print("nothing backfilled yet")
        return
    coins = conn.execute("SELECT COUNT(DISTINCT coin) FROM positioning").fetchone()[0]
    lo, hi = conn.execute("SELECT MIN(ts_ms), MAX(ts_ms) FROM positioning").fetchone()
    print(f"\n{n:,} rows, {coins} coins, "
          f"{(hi-lo)/86400000:.1f} days "
          f"({time.strftime('%Y-%m-%d %H:%M', time.gmtime(lo/1000))} -> "
          f"{time.strftime('%Y-%m-%d %H:%M', time.gmtime(hi/1000))} UTC)")
    print("  rows per period:", dict(conn.execute(
        "SELECT period, COUNT(*) FROM positioning GROUP BY period").fetchall()))
    print("\n  coverage per series (non-null values, 1h rows):")
    for c in ["oi_usd", "long_frac", "top_long_frac", "taker_ratio"]:
        v = conn.execute(f"SELECT COUNT({c}) FROM positioning WHERE period='1h'").fetchone()[0]
        print(f"    {c:<18}{v:>10,}")
    print("\n  most recent BTC 1h row:")
    r = conn.execute("SELECT * FROM positioning WHERE coin='BTC' AND period='1h' "
                     "ORDER BY ts_ms DESC LIMIT 1").fetchone()
    names = [d[0] for d in conn.execute("SELECT * FROM positioning LIMIT 1").description]
    if r:
        for k, v in zip(names, r):
            print(f"    {k:<18}{v}")
    dl = conn.execute("SELECT COUNT(*), MIN(day), MAX(day) FROM positioning_days").fetchone()
    print(f"\n  archive days loaded: {dl[0]:,} (coin,day) pairs, {dl[1]} -> {dl[2]}")


def run_once(conn: sqlite3.Connection, symbols: Dict[str, str], args) -> None:
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    t0 = time.time()
    total, files, failures = 0, 0, {}
    todo = {coin: days_to_load(conn, coin, args.days) for coin in symbols}
    n_days = sum(len(v) for v in todo.values())
    print(f"{len(symbols)} coins, {n_days} day-files to fetch")
    for i, (coin, days) in enumerate(todo.items(), 1):
        sym = symbols[coin]
        for d in days:
            url = f"{BASE}/{sym}/{sym}-metrics-{d.isoformat()}.zip"
            try:
                blob = http(url)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    if d < yesterday:
                        # older than yesterday and absent: the coin had no perp
                        # that day. Remember so we never ask again.
                        with conn:
                            conn.execute("INSERT OR REPLACE INTO positioning_days VALUES (?,?,?,?)",
                                         (coin, d.isoformat(), 0, int(time.time() * 1000)))
                    # yesterday's file not published yet: retry next run
                    continue
                failures[f"{coin} {d}"] = f"HTTP {e.code}"
                continue
            except Exception as exc:
                failures[f"{coin} {d}"] = f"{type(exc).__name__}: {str(exc)[:60]}"
                continue
            try:
                rows = rows_for_day(coin, parse_metrics(blob), args.keep_5m)
            except Exception as exc:
                failures[f"{coin} {d}"] = f"parse {type(exc).__name__}: {str(exc)[:60]}"
                continue
            with conn:
                cur = conn.executemany(
                    "INSERT OR IGNORE INTO positioning VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
                conn.execute("INSERT OR REPLACE INTO positioning_days VALUES (?,?,?,?)",
                             (coin, d.isoformat(), len(rows), int(time.time() * 1000)))
            total += cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else len(rows)
            files += 1
            time.sleep(args.sleep)
        if i % 20 == 0 or i == len(todo):
            print(f"  [{i:>3}/{len(todo)}] {coin:<10} {files} files, {total:,} new rows, "
                  f"{time.time()-t0:.0f}s elapsed")

    took = time.time() - t0
    with conn:
        conn.execute("INSERT OR REPLACE INTO backfill_log VALUES (?,?,?,?,?,?)",
                     (int(time.time() * 1000), "1h+5m" if args.keep_5m else "1h",
                      len(symbols), total, json.dumps(failures)[:2000], took))
    print(f"\n{files} files, {total:,} new rows in {took:.0f}s"
          + (f", {len(failures)} failed: {list(failures)[:6]}" if failures else ""))
    stats(conn)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30,
                    help="for a coin with nothing loaded yet, how many days back to start")
    ap.add_argument("--keep-5m", action="store_true",
                    help="also store the raw 5-minute rows (12x the rows; includes the "
                         "5-minute taker ratio)")
    ap.add_argument("--top", type=int, default=0, help="only the N highest-volume HL coins")
    ap.add_argument("--coins", default="", help="comma separated coins, e.g. BTC,ETH")
    ap.add_argument("--db", default="data/venues.db")
    ap.add_argument("--sleep", type=float, default=0.12, help="pause between files")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--every", type=float, default=0.0,
                    help="seconds between runs; 0 = run once and exit")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.is_absolute():
        db = ROOT / db
    conn = open_db(db)
    if args.stats:
        stats(conn)
        return

    symbols = binance_symbol_map()
    if args.coins:
        want = {c.strip().upper() for c in args.coins.split(",") if c.strip()}
        symbols = {c: s for c, s in symbols.items() if c in want}
    if args.top:
        from hl.exchanges import BY_NAME  # Hyperliquid is not blocked; only needed for volumes
        hl = BY_NAME["hyperliquid"].quotes_by_coin()
        ranked = sorted(symbols, key=lambda c: -((hl.get(c) or {}).get("vol") or 0))
        symbols = {c: symbols[c] for c in ranked[: args.top]}
    print(f"symbol map from store.db: {len(symbols)} coins with a Binance USDT perp")

    while True:
        run_once(conn, symbols, args)
        if not args.every:
            break
        nxt = time.time() + args.every
        print(f"  next check in {args.every/60:.0f} min")
        while time.time() < nxt:
            time.sleep(5)


if __name__ == "__main__":
    main()
