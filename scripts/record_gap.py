"""Record the Hyperliquid-vs-rest-of-market price gap, forever.

    python scripts/record_gap.py                 # every 60s, all matched pairs
    python scripts/record_gap.py --interval 30
    python scripts/record_gap.py --once

Why this exists: a snapshot shows a gap. Only a time series can answer the real
question — does the gap CLOSE, and which side moves. Nobody sells that history
for Hyperliquid, so the clock starts when this starts.

What one pass costs: 2 Hyperliquid requests for every coin (allMids-equivalent
via metaAndAssetCtxs), 3 venue requests, plus up to --books order books for real
Hyperliquid bid/ask. Well inside the 1200 weight/minute IP budget.

Honesty rules baked in:
  * raw prices are stored alongside the computed gap, so a gap can be recomputed
    if the definition changes later,
  * a venue that fails is absent, not zero — a missing quote and a quote of zero
    are different facts,
  * every pass writes a gap_runs row with the seconds since the previous pass,
    so a hole in the data is visible instead of silently becoming a signal.
"""
from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hl import Book, MarketData, Store  # noqa: E402
from hl.info import now_ms  # noqa: E402
from hl.venues import ALL_VENUES, Binance, Bybit, OKX, all_quotes  # noqa: E402

SUSPECT_BPS = 1000.0        # 10%: past this it is a mismatched ticker, not a gap
RUNNING = True


def stop(*_a) -> None:
    global RUNNING
    RUNNING = False
    print("\nfinishing this pass, then stopping...")


def one_pass(md: MarketData, store: Store, book_budget: int, cursor: int):
    t0 = time.time()
    ts = now_ms()

    meta, ctxs = md.meta_and_ctxs(force=True)
    hl = {}
    for asset, c in zip(meta["universe"], ctxs):
        # A delisted market keeps returning its final price forever. Compared
        # against a live venue that shows as a several-thousand-bps "gap" and it
        # is pure fiction - PIXEL read as 35,674 bps before this line existed.
        if asset.get("isDelisted"):
            continue
        mid = c.get("midPx") or c.get("markPx")
        if not mid:
            continue
        hl[asset["name"]] = {
            "mid": float(mid),
            "mark": float(c["markPx"]) if c.get("markPx") else None,
            "oracle": float(c["oraclePx"]) if c.get("oraclePx") else None,
            "funding": float(c["funding"]) if c.get("funding") is not None else None,
        }

    venues = all_quotes()
    errors = getattr(all_quotes, "errors", {})

    # Which Hyperliquid coins are quoted anywhere else, and by how much do they differ.
    pairs = []
    for coin, h in hl.items():
        base, mult = _hl_base(coin)
        for vname, quotes in venues.items():
            q = quotes.get(base)
            if not q:
                continue
            v_mid = q["mid"] * mult          # back into Hyperliquid's contract units
            if v_mid <= 0:
                continue
            pairs.append({
                "coin": coin, "venue": vname, "hl": h, "q": q,
                "v_bid": q["bid"] * mult, "v_ask": q["ask"] * mult, "v_mid": v_mid,
                "gap_bps": (h["mid"] / v_mid - 1) * 1e4,
            })

    # Real Hyperliquid bid/ask for a bounded subset: the widest gaps first (they
    # are the ones a trade would ever be considered on), then round-robin so
    # every coin gets a true spread eventually.
    wide = sorted({p["coin"] for p in pairs},
                  key=lambda c: -max(abs(p["gap_bps"]) for p in pairs if p["coin"] == c))
    picked = wide[:book_budget // 2]
    rest = [c for c in wide if c not in picked]
    take = book_budget - len(picked)
    if rest and take > 0:
        cursor %= len(rest)
        picked += (rest + rest)[cursor:cursor + take]
        cursor += take
    books = {}
    for coin in picked:
        if not RUNNING:
            break
        try:
            b = Book.from_payload(md.info.l2_book(coin))
            if b.best_bid and b.best_ask:
                books[coin] = b
        except Exception:
            pass

    rows = []
    for p in pairs:
        b = books.get(p["coin"])
        hl_bid = b.best_bid if b else None
        hl_ask = b.best_ask if b else None
        hl_spread = b.spread_bps if b else None
        v_spread = ((p["v_ask"] - p["v_bid"]) / p["v_mid"] * 1e4) if p["v_mid"] else None
        # Two liquid perps on the same asset cannot sit 10% apart for more than
        # seconds. Anything past that is a ticker collision - Bybit lists a PURR
        # that is not Hyperliquid's PURR - so it is stored and flagged, never
        # deleted (deleting hides the problem) and never counted as a gap.
        suspect = 1 if abs(p["gap_bps"]) > SUSPECT_BPS else 0
        rows.append((ts, p["coin"], p["venue"], hl_bid, hl_ask, p["hl"]["mid"],
                     p["hl"]["mark"], p["hl"]["oracle"], p["v_bid"], p["v_ask"],
                     p["v_mid"], p["gap_bps"], p["hl"]["funding"], hl_spread,
                     v_spread, suspect))

    n = store.save_gaps(rows)
    n_suspect = sum(r[-1] for r in rows)
    took = int((time.time() - t0) * 1000)
    return n, len(books), venues, errors, ts, took, cursor, n_suspect


def _hl_base(coin: str):
    from hl.venues import normalise
    return normalise(coin)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=60.0)
    ap.add_argument("--db", default="data/hl.db")
    ap.add_argument("--books", type=int, default=50,
                    help="order books fetched per pass for real HL bid/ask")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    signal.signal(signal.SIGINT, stop)
    md = MarketData()
    store = Store(args.db)
    print(f"recording HL vs {', '.join(v.name for v in [Binance(), Bybit(), OKX()])}")
    print(f"db {Path(args.db).resolve()}   every {args.interval:.0f}s   Ctrl+C to stop\n")

    last_ts = None
    cursor = 0
    passes = 0
    while RUNNING:
        try:
            n, nb, venues, errors, ts, took, cursor, nsus = one_pass(md, store, args.books, cursor)
        except Exception as exc:
            print(f"  pass failed: {type(exc).__name__}: {exc}")
            time.sleep(5)
            continue
        since = (ts - last_ts) / 1000.0 if last_ts else 0.0
        last_ts = ts
        store.save_gap_run(ts, n, ",".join(sorted(venues)), json.dumps(errors), took, since)
        passes += 1
        warn = f"  ERRORS {errors}" if errors else ""
        print(f"[{passes:>4}] {time.strftime('%H:%M:%S')}  {n} pairs across "
              f"{len(venues)} venues, {nb} real HL books, {nsus} flagged, "
              f"{took}ms, +{since:.0f}s since last{warn}")
        if args.once:
            break
        end = time.time() + max(args.interval - took / 1000.0, 1.0)
        while RUNNING and time.time() < end:
            time.sleep(0.5)

    store.close()
    print("stopped cleanly")


if __name__ == "__main__":
    main()
