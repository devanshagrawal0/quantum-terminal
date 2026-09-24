"""Continuous collector - the history Hyperliquid does not keep for you.

    python scripts/record.py                       # top 25 by volume, every 60s
    python scripts/record.py --coins BTC,ETH,SOL --interval 30
    python scripts/record.py --once                # single pass, then exit

Each pass writes: open interest / funding / mark for every watched coin, an
order book snapshot with depth and slippage, and (hourly) a candle + funding
backfill. Everything is upsert-safe, so stopping and restarting never
duplicates a row.
"""
from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hl import MarketData, Store  # noqa: E402
from hl.info import now_ms  # noqa: E402

RUNNING = True


def stop(*_a) -> None:
    global RUNNING
    RUNNING = False
    print("\nstopping after this pass...")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coins", default="", help="comma separated, default = top by volume")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--interval", type=float, default=60.0, help="seconds between passes")
    ap.add_argument("--db", default="data/hl.db")
    ap.add_argument("--backfill-every", type=float, default=3600.0)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    signal.signal(signal.SIGINT, stop)

    md = MarketData()
    store = Store(args.db)
    md.universe.refresh()

    if args.coins:
        watch = [c.strip().upper() for c in args.coins.split(",") if c.strip()]
    else:
        watch = md.scan().head(args.top)["coin"].tolist()
    print(f"watching {len(watch)} coins: {', '.join(watch)}")
    print(f"writing to {Path(args.db).resolve()}  (Ctrl+C to stop)")

    last_backfill = 0.0
    passes = 0
    while RUNNING:
        t0 = time.time()
        ts = now_ms()

        # One cheap request covers open interest / funding / mark for everything.
        table = md.scan(coins=watch)
        for row in table.to_dict("records"):
            store.save_ctx(ts, row["coin"], row)

        # Books are per coin, so only the watchlist gets one.
        for coin in watch:
            if not RUNNING:
                break
            try:
                book = md.book(coin)
                store.save_book(ts, coin, book.summary())
                store.save_trades(md.info.recent_trades(coin))
            except Exception as exc:
                print(f"  {coin}: {type(exc).__name__} {exc}")

        if time.time() - last_backfill > args.backfill_every:
            for coin in watch:
                try:
                    store.save_candles(coin, "1d", md.info.candles_lookback(coin, "1d", 500))
                    store.save_candles(coin, "1h", md.info.candles_lookback(coin, "1h", 500))
                    store.save_funding(md.info.funding_history(
                        coin, now_ms() - 30 * 86_400_000))
                except Exception as exc:
                    print(f"  backfill {coin}: {type(exc).__name__} {exc}")
            last_backfill = time.time()
            print(f"  backfilled candles + funding for {len(watch)} coins")

        passes += 1
        took = time.time() - t0
        print(f"[pass {passes}] {time.strftime('%H:%M:%S')} took {took:.1f}s "
              f"weight={md.info.limiter.spent()}/{md.info.limiter.budget} "
              f"rows={store.counts()}")

        if args.once:
            break
        sleep = max(args.interval - took, 1.0)
        end = time.time() + sleep
        while RUNNING and time.time() < end:
            time.sleep(0.5)

    store.close()
    print("stopped cleanly")


if __name__ == "__main__":
    main()
