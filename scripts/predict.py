"""Make, resolve and score predictions.

    python scripts/predict.py --add BTC long 24 --conf 0.6 --thesis "..."
    python scripts/predict.py --random 20 --horizon 24      # the control arm
    python scripts/predict.py --resolve                     # score anything due
    python scripts/predict.py --board                       # how are we doing
    python scripts/predict.py --verify                      # has anything been edited

Entry and exit prices come from the consolidated cross-venue price where one
exists, falling back to Hyperliquid's own mid - never from a single venue that
might have been asleep.

The random arm is not decoration. Without it, a rising market makes every long
look like judgement, and there is no way to tell reasoning from luck.
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hl.exchanges import BY_NAME  # noqa: E402
from hl.predictions import Prediction, PredictionLog  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "predictions.db"
VENUES_DB = ROOT / "data" / "venues.db"


def live_prices() -> Tuple[Dict[str, float], Dict[str, dict]]:
    """Consolidated price per coin right now, plus the raw hyperliquid state."""
    conn = sqlite3.connect(f"file:{VENUES_DB}?mode=ro", uri=True)
    last = conn.execute("SELECT MAX(ts_ms) FROM cv_features").fetchone()[0]
    cp = {}
    if last:
        for coin, price, vol in conn.execute(
                "SELECT coin, cp, credible_vol_usd FROM cv_features WHERE ts_ms=?",
                (last,)):
            if price and price > 0:
                cp[coin] = {"cp": price, "vol": vol or 0.0}
    conn.close()

    hl = BY_NAME["hyperliquid"].quotes_by_coin()
    prices = {c: cp[c]["cp"] if c in cp else hl[c]["mid"] for c in hl}
    return prices, hl


def market_return(entry_map: Dict[str, float], now: Dict[str, float]) -> Optional[float]:
    """Equal-weight move of everything we can price at both ends, in percent."""
    common = [c for c in entry_map if c in now and entry_map[c] > 0]
    if len(common) < 20:
        return None
    rets = [(now[c] / entry_map[c] - 1.0) * 100.0 for c in common]
    return float(sum(rets) / len(rets))


def add_random(log: PredictionLog, n: int, horizon_h: int) -> int:
    """The control arm: coin and side chosen by coin flip, same universe."""
    prices, hl = live_prices()
    liquid = [c for c in prices
              if (hl.get(c, {}).get("vol") or 0) > 5e6 and prices[c] > 0]
    if len(liquid) < n:
        n = len(liquid)
    picks = random.sample(liquid, n)
    preds = [Prediction(coin=c, direction=random.choice(["long", "short"]),
                        horizon_h=horizon_h, entry_px=prices[c], source="random",
                        confidence=0.5,
                        thesis="control arm: coin and side chosen at random",
                        state={"universe": len(liquid)})
             for c in picks]
    return log.add_many(preds)


def resolve_due(log: PredictionLog) -> int:
    due = log.due()
    if not due:
        print("nothing due")
        return 0
    prices, _hl = live_prices()
    done = 0
    for row in due:
        coin = row["coin"]
        exit_px = prices.get(coin)
        state = json.loads(row["state_json"] or "{}")
        entry_map = state.get("entry_map") or {}
        mkt = market_return(entry_map, prices) if entry_map else None
        res = log.resolve(row["id"], exit_px or 0.0, mkt,
                          funding_pct=0.0,
                          notes="" if exit_px else "coin not priceable at resolve")
        done += 1
        print(f"  {coin:<10}{row['direction']:<6}{row['horizon_h']:>4}h  "
              f"{res['outcome']:<9}"
              + (f"net {res.get('net_ret_pct'):+.2f}%" if res.get("net_ret_pct") is not None else "")
              + (f"  excess {res['excess_pct']:+.2f}%" if res.get("excess_pct") is not None else ""))
    return done


def board(log: PredictionLog) -> None:
    rows = log.scoreboard()
    if not rows:
        print("no predictions yet")
        return
    print(f"\n{'source':<12}{'made':>6}{'scored':>8}{'avg net %':>11}"
          f"{'avg excess %':>14}{'hit':>7}{'avg conf':>10}")
    print("-" * 70)
    for r in rows:
        hit = f"{r['hit']*100:.0f}%" if r["hit"] is not None else "-"
        net = f"{r['avg_net']:+.2f}" if r["avg_net"] is not None else "-"
        exc = f"{r['avg_excess']:+.2f}" if r["avg_excess"] is not None else "-"
        conf = f"{r['avg_conf']:.2f}" if r["avg_conf"] is not None else "-"
        print(f"{r['source']:<12}{r['n']:>6}{r['resolved']:>8}{net:>11}{exc:>14}"
              f"{hit:>7}{conf:>10}")
    cal = log.calibration()
    if cal:
        print("\ncalibration (claude only):")
        for c in cal:
            print(f"  stated {c['bucket']:<10}n={c['n']:<4}"
                  f"actually won {c['actual_win_rate']*100:.0f}%")
    print("\nThe comparison that matters is claude vs random on avg excess %.")
    print("Anything else is a story about the market, not about the calls.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--add", nargs=3, metavar=("COIN", "DIR", "HOURS"))
    ap.add_argument("--conf", type=float)
    ap.add_argument("--size", type=float)
    ap.add_argument("--invalidation", type=float)
    ap.add_argument("--thesis", default="")
    ap.add_argument("--random", type=int)
    ap.add_argument("--horizon", type=int, default=24)
    ap.add_argument("--resolve", action="store_true")
    ap.add_argument("--board", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    log = PredictionLog(DB)

    if args.add:
        coin, direction, hours = args.add[0].upper(), args.add[1].lower(), int(args.add[2])
        prices, hl = live_prices()
        if coin not in prices:
            print(f"{coin} is not priceable right now")
            return
        # The whole universe's prices are stored with the call, so the market
        # benchmark at resolution uses the same basket that existed at entry.
        pid = log.add(Prediction(
            coin=coin, direction=direction, horizon_h=hours,
            entry_px=prices[coin], confidence=args.conf, size_pct=args.size,
            invalidation_px=args.invalidation, thesis=args.thesis,
            state={"entry_map": prices, "n_universe": len(prices)}))
        print(f"logged {pid}  {coin} {direction} {hours}h @ {prices[coin]:,.6g}")

    if args.random:
        n = add_random(log, args.random, args.horizon)
        print(f"logged {n} random control calls at {args.horizon}h")

    if args.resolve:
        print(f"resolving due predictions at {time.strftime('%H:%M:%S')}")
        print(f"  resolved {resolve_due(log)}")

    if args.verify:
        v = log.verify()
        print(f"integrity: {v['checked']} calls checked, "
              f"{len(v['tampered'])} tampered {v['tampered'] or ''}")

    if args.list:
        conn = log.conn
        for r in conn.execute(
                "SELECT created_ms, source, coin, direction, horizon_h, entry_px, "
                "confidence, outcome, excess_pct FROM predictions "
                "ORDER BY created_ms DESC LIMIT 25"):
            t = time.strftime("%H:%M:%S", time.localtime(r[0] / 1000))
            print(f"  {t}  {r[1]:<8}{r[2]:<10}{r[3]:<6}{r[4]:>4}h  "
                  f"entry {r[5]:<12,.6g}conf {r[6] if r[6] is not None else '-':<6}"
                  f"{r[7] or 'pending':<10}"
                  f"{'' if r[8] is None else f'excess {r[8]:+.2f}%'}")

    if args.board:
        board(log)

    log.close()


if __name__ == "__main__":
    main()
