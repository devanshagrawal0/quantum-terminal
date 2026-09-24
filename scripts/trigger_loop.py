"""The condition watcher: evaluates every ARMED trigger against the live price
each cycle and, when one fires, opens the planned paper trade + writes an alert.

This is what makes a "short ZEC when the rally cracks" thesis actually execute
when neither Dev nor the reasoning layer is watching.

    python scripts/trigger_loop.py                # every 30s
    python scripts/trigger_loop.py --interval 15
    python scripts/trigger_loop.py --once

Runs under the watchdog so it is always up.
"""
from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hl.paper import Paper, live_all_mids  # noqa: E402
import hl.triggers as tg  # noqa: E402

RUNNING = True


def stop(*_a):
    global RUNNING
    RUNNING = False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=30.0)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    signal.signal(signal.SIGINT, stop)

    conn = tg.store()
    conn.execute("CREATE TABLE IF NOT EXISTS trigger_heartbeat (ts_ms INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE IF NOT EXISTS risk_state (id INTEGER PRIMARY KEY CHECK (id=1), "
                 "ts_ms INTEGER, bp_score REAL, bp_level TEXT, crash_score REAL, crash_level TEXT, detail TEXT)")
    conn.commit()
    conn.close()
    print(f"trigger loop up, every {args.interval:.0f}s. Ctrl+C to stop.")
    n = 0
    last_bp_level = last_crash_level = "calm"
    while RUNNING:
        t0 = time.time()
        prices = live_all_mids()
        if prices:
            bk = Paper()
            try:
                fired = tg.evaluate(prices, bk)
            finally:
                bk.close()
            for f in fired:
                if f.get("ok"):
                    print(f"  [{time.strftime('%H:%M:%S')}] FIRED #{f['trigger_id']}: "
                          f"opened {f['side'].upper()} {f['coin']} @ {f['entry_px']:.6g}")
                else:
                    print(f"  [{time.strftime('%H:%M:%S')}] trigger #{f['trigger_id']} "
                          f"condition met but REJECTED: {f.get('error')}")
        conn = tg.store()
        with conn:
            conn.execute("INSERT OR REPLACE INTO trigger_heartbeat VALUES (?)",
                         (int(time.time() * 1000),))
        conn.close()
        n += 1
        # Risk monitors every ~5 min (10 cycles @30s): compute + store + alert on escalation.
        if n == 1 or n % 10 == 0:
            try:
                import json as _json
                from hl import risk
                s = risk.summary()
                bp, cr = s["breaking_point"], s["crash"]
                conn = tg.store()
                with conn:
                    conn.execute("INSERT OR REPLACE INTO risk_state VALUES (1,?,?,?,?,?,?)",
                                 (int(time.time() * 1000), bp["score"], bp["level"],
                                  cr["score"], cr["level"], _json.dumps(s)))
                    order = {"calm": 0, "watch": 1, "caution": 1, "elevated": 2, "risk-off": 2}
                    if order.get(bp["level"], 0) > order.get(last_bp_level, 0) and bp["level"] == "elevated":
                        tg.alert(conn, "BTC", "ERROR",
                                 f"BREAKING-POINT ELEVATED {bp['score']}/100: {bp['components']} — top risk building, cut size")
                    if order.get(cr["level"], 0) > order.get(last_crash_level, 0) and cr["level"] in ("caution", "risk-off"):
                        lvl = cr["level"].upper()
                        tg.alert(conn, "MARKET", "ERROR" if cr["level"] == "risk-off" else "INFO",
                                 f"{lvl} {cr['score']}/100: breadth {cr['components'].get('breadth_1d')}%, "
                                 f"majors {cr['components'].get('majors_1d')}% — alts are NOT a haven, de-risk")
                conn.close()
                last_bp_level, last_crash_level = bp["level"], cr["level"]
                print(f"  [{time.strftime('%H:%M:%S')}] risk: breaking-point {bp['score']} [{bp['level']}] · crash {cr['score']} [{cr['level']}]")
            except Exception as e:
                print(f"  [{time.strftime('%H:%M:%S')}] risk monitor error: {e}")
        if n % 20 == 0:
            armed = len(tg.list_triggers("armed"))
            print(f"  [{time.strftime('%H:%M:%S')}] watching {armed} armed trigger(s)")
        if args.once:
            break
        end = t0 + args.interval
        while RUNNING and time.time() < end:
            time.sleep(0.5)
    print("trigger loop stopped")


if __name__ == "__main__":
    main()
