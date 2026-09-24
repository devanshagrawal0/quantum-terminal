"""Refresh the token-unlock cache periodically (the DefiLlama scan is ~4.5 min, too
slow for the price loops, so it runs on its own slow cadence under the watchdog).

    python scripts/unlocks_refresh.py --every 21600   # every 6h
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hl import unlocks  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _heartbeat(n):
    conn = unlocks._store()
    conn.execute("CREATE TABLE IF NOT EXISTS unlock_runs (ts_ms INTEGER PRIMARY KEY, cached INTEGER)")
    with conn:
        conn.execute("INSERT OR REPLACE INTO unlock_runs VALUES (?,?)", (int(time.time() * 1000), n))
    conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=float, default=21600)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    while True:
        t0 = time.time()
        try:
            n = unlocks.refresh_cache()
            _heartbeat(n)
            print(f"[{time.strftime('%H:%M:%S')}] unlocks refreshed: {n} tokens in {time.time()-t0:.0f}s")
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] unlock refresh error: {e}")
            _heartbeat(0)
        if args.once:
            break
        time.sleep(args.every)


if __name__ == "__main__":
    main()
