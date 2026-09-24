"""The heartbeat: marks every open paper position and closes any that hit their
stop, target or time limit. Without this running, positions never actually exit.

    python scripts/settle_loop.py                # every 60s
    python scripts/settle_loop.py --interval 30
    python scripts/settle_loop.py --once

Marks against the consolidated cross-venue price the recorder computes, so an
exit is a real market level, not whenever someone happens to look.
"""
from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hl.paper import Paper  # noqa: E402

RUNNING = True


def stop(*_a):
    global RUNNING
    RUNNING = False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=60.0)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    signal.signal(signal.SIGINT, stop)

    bk = Paper()
    bk.conn.execute("CREATE TABLE IF NOT EXISTS settle_heartbeat (ts_ms INTEGER PRIMARY KEY)")
    bk.conn.execute("CREATE TABLE IF NOT EXISTS equity_curve (ts_ms INTEGER PRIMARY KEY, "
                    "total_pnl REAL, realized REAL, unrealized REAL, n_open INTEGER)")
    bk.conn.commit()
    print(f"settle loop up, every {args.interval:.0f}s. Ctrl+C to stop.")
    n = 0
    while RUNNING:
        t0 = time.time()
        closed = bk.mark_and_settle()
        a = bk.account()
        with bk.conn:
            now_ms = int(time.time()*1000)
            bk.conn.execute("INSERT OR REPLACE INTO settle_heartbeat VALUES (?)", (now_ms,))
            # equity snapshot each beat -> a real portfolio curve over time
            bk.conn.execute("INSERT OR REPLACE INTO equity_curve VALUES (?,?,?,?,?)",
                            (now_ms, a["total_pnl"], a["realized_pnl"],
                             a["unrealized_pnl"], a["n_open"]))
        n += 1
        for c in closed:
            print(f"  [{time.strftime('%H:%M:%S')}] CLOSED {c['coin']} {c['side']} "
                  f"on {c['reason']} -> pnl ${c['pnl_usd']:+.3f}")
        if n % 10 == 0 or closed:
            print(f"  [{time.strftime('%H:%M:%S')}] open {a['n_open']}  closed {a['n_closed']}"
                  f"  realized ${a['realized_pnl']:+.3f}  unreal ${a['unrealized_pnl']:+.3f}"
                  f"  total ${a['total_pnl']:+.3f}")
        if args.once:
            break
        end = t0 + args.interval
        while RUNNING and time.time() < end:
            time.sleep(0.5)
    bk.close()
    print("settle loop stopped")


if __name__ == "__main__":
    main()
