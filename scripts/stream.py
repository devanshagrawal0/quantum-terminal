"""Live websocket tape and book for one coin.

    python scripts/stream.py BTC
    python scripts/stream.py HYPE --seconds 120

Prints a line whenever the top of book moves and whenever a trade prints, with
the running taker imbalance - the fastest read on who is leaning on the market.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hl import Book, HLWebsocket  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("coin", nargs="?", default="BTC")
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--sweep-usd", type=float, default=25_000.0)
    args = ap.parse_args()
    coin = args.coin.upper()

    state = {"buy": 0.0, "sell": 0.0, "prints": 0, "books": 0}

    def on_book(payload) -> None:
        b = Book.from_payload(payload)
        state["books"] += 1
        if state["books"] % 5:            # every 5th update keeps it readable
            return
        buy = b.sweep(args.sweep_usd, True)["slippage_bps"]
        sell = b.sweep(args.sweep_usd, False)["slippage_bps"]
        imb = b.imbalance(10.0)
        print(f"[book] {b.best_bid} / {b.best_ask}  spread {b.spread_bps:.2f}bps  "
              f"micro {b.microprice:.4f}  imb10 {imb:+.3f}  "
              f"slip ${args.sweep_usd:,.0f} buy {buy:.2f} / sell {sell:.2f} bps")

    def on_trades(trades) -> None:
        for t in trades:
            usd = float(t["px"]) * float(t["sz"])
            if t["side"] == "B":
                state["buy"] += usd
            else:
                state["sell"] += usd
            state["prints"] += 1
            tot = state["buy"] + state["sell"]
            imb = (state["buy"] - state["sell"]) / tot if tot else 0.0
            if usd >= 5_000:              # only shout about size
                side = "BUY " if t["side"] == "B" else "SELL"
                print(f"[tape] {side} ${usd:>12,.0f} @ {t['px']:>12}  "
                      f"running taker imbalance {imb:+.3f}")

    ws = HLWebsocket(on_error=lambda e: print("ws error:", e)).start()
    ws.on_l2_book(coin, on_book)
    ws.on_trades(coin, on_trades)
    print(f"streaming {coin} for {args.seconds:.0f}s ...\n")

    end = time.time() + args.seconds
    try:
        while time.time() < end:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    ws.stop()

    tot = state["buy"] + state["sell"]
    print(f"\n{state['prints']} prints, ${tot:,.0f} traded, "
          f"taker buy ${state['buy']:,.0f} / sell ${state['sell']:,.0f}, "
          f"imbalance {((state['buy'] - state['sell']) / tot if tot else 0):+.3f}")
    print(f"{ws.messages_received} ws messages, {ws.reconnects} reconnects")


if __name__ == "__main__":
    main()
