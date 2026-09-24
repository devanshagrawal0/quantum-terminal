"""Live end-to-end proof that every part of the data layer actually works.

    python scripts/probe.py BTC

Hits the real mainnet API, prints what came back, then opens a websocket and
counts real messages. No mocks anywhere.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hl import HLWebsocket, MarketData, Store, round_px_raw  # noqa: E402


def line(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def show(row: dict, keys: list) -> None:
    for k in keys:
        if k in row:
            v = row[k]
            if isinstance(v, float):
                print(f"  {k:<28} {v:,.8g}")
            else:
                print(f"  {k:<28} {v}")


def main() -> None:
    coin = (sys.argv[1] if len(sys.argv) > 1 else "BTC").upper()
    md = MarketData()

    line("1. UNIVERSE")
    md.universe.refresh()
    coins = md.universe.coins()
    print(f"  perps listed         {len(coins)}")
    print(f"  spot pairs           {len(md.universe.spot_universe)}")
    print(f"  {coin}: szDecimals={md.universe.sz_decimals(coin)} "
          f"maxLev={md.universe.max_leverage(coin)} "
          f"assetId={md.universe.asset_id(coin)} "
          f"spot={md.universe.spot_pair_label(coin)} ({md.universe.spot_pair(coin)})")
    px = md.ctx(coin)
    mark = float(px["markPx"])
    print(f"  rounding check       raw {mark * 1.0031:.6f} -> "
          f"exchange-legal {md.universe.round_px(coin, mark * 1.0031)}")

    line(f"2. SNAPSHOT - {coin}")
    t0 = time.time()
    snap = md.snapshot(coin)
    took = time.time() - t0
    print(f"  built in {took:.2f}s, {len([k for k in snap if not k.startswith('_')])} variables\n")

    print(" -- price / basis")
    show(snap, ["mark_px", "oracle_px", "mid_px", "prev_day_px", "day_change_pct",
                "mark_oracle_bps", "spot_mid", "spot_pair_label", "perp_spot_basis_bps"])
    print(" -- funding (rates are per HOUR)")
    show(snap, ["funding_hourly", "funding_apr", "premium", "funding_mean_24h",
                "funding_apr_24h", "funding_apr_168h", "funding_pos_frac_168h",
                "carry_long_3d", "carry_short_3d", "carry_long_7d"])
    print(" -- open interest / volume")
    show(snap, ["open_interest_base", "open_interest_usd", "day_notional_volume",
                "turnover_vol_over_oi"])
    print(" -- order book")
    show(snap, ["book_best_bid", "book_best_ask", "book_mid", "book_microprice",
                "book_spread_bps", "book_depth_bid_usd_10bps",
                "book_depth_ask_usd_10bps", "book_imbalance_10bps",
                "book_imbalance_top5", "book_buy_slippage_bps",
                "book_sell_slippage_bps", "book_age_ms"])
    print(" -- tape")
    show(snap, ["trades_n", "trade_vwap", "taker_buy_usd", "taker_sell_usd",
                "taker_imbalance", "avg_trade_usd", "trades_per_second"])
    print(" -- daily candles (1-7 day horizon)")
    show(snap, ["bars", "ret_1d", "ret_3d", "ret_7d", "ret_30d", "vol_7d_ann",
                "vol_30d_ann", "vol_ratio_7_30", "parkinson_30d_ann",
                "atr_14_pct", "rsi_14", "z_30d", "dist_high_30d",
                "dist_low_30d", "dist_sma_7", "dist_ema_50", "max_dd_30d",
                "up_day_ratio_14d", "volume_z_30d"])

    line("3. EXECUTION COST CURVE (walking the live book)")
    book = snap["_raw"]["book"]
    print(f"  {'size USD':>12} {'buy slip bps':>14} {'sell slip bps':>14} {'filled':>8}")
    for usd in (1_000, 10_000, 50_000, 250_000, 1_000_000):
        b = book.sweep(usd, True)
        s = book.sweep(usd, False)
        bs = f"{b['slippage_bps']:.2f}" if b["slippage_bps"] is not None else "n/a"
        ss = f"{s['slippage_bps']:.2f}" if s["slippage_bps"] is not None else "n/a"
        print(f"  {usd:>12,} {bs:>14} {ss:>14} {b['filled_pct']*100:>7.1f}%")

    line("4. UNIVERSE SCAN (3 requests, every perp)")
    df = md.scan(min_day_volume_usd=5_000_000)
    print(f"  {len(df)} perps with >$5m daily volume\n")
    cols = ["coin", "mark_px", "day_change_pct", "open_interest_usd",
            "day_notional_volume", "funding_apr", "funding_hl_minus_cex_apr"]
    print(df[cols].head(12).to_string(index=False,
          float_format=lambda v: f"{v:,.4f}"))
    print("\n  biggest HL-vs-CEX funding gaps (annualised):")
    g = df.dropna(subset=["funding_hl_minus_cex_apr"]).reindex(
        df["funding_hl_minus_cex_apr"].abs().sort_values(ascending=False).index)
    print(g[["coin", "funding_apr", "funding_hl_minus_cex_apr",
             "day_notional_volume"]].head(8).to_string(
                 index=False, float_format=lambda v: f"{v:,.4f}"))

    line("5. WEBSOCKET (live, 15 seconds)")
    counts = {"book": 0, "trades": 0, "bbo": 0, "mids": 0, "candle": 0}
    last = {}

    ws = HLWebsocket(on_error=lambda e: print("  ws error:", e)).start()
    ws.on_l2_book(coin, lambda d: (counts.__setitem__("book", counts["book"] + 1),
                                   last.__setitem__("book", d)))
    ws.on_trades(coin, lambda d: counts.__setitem__("trades", counts["trades"] + len(d)))
    ws.on_bbo(coin, lambda d: (counts.__setitem__("bbo", counts["bbo"] + 1),
                               last.__setitem__("bbo", d)))
    ws.on_all_mids(lambda d: counts.__setitem__("mids", counts["mids"] + 1))
    ws.on_candle(coin, "1m", lambda d: counts.__setitem__("candle", counts["candle"] + 1))
    time.sleep(15)

    print(f"  connected            {ws.connected}")
    print(f"  messages received    {ws.messages_received}")
    print(f"  l2Book updates       {counts['book']}")
    print(f"  trades streamed      {counts['trades']}")
    print(f"  bbo updates          {counts['bbo']}")
    print(f"  allMids updates      {counts['mids']}")
    print(f"  candle updates       {counts['candle']}")
    if "bbo" in last:
        b = last["bbo"]["bbo"]
        print(f"  latest bbo           bid {b[0]['px'] if b[0] else '-'} / "
              f"ask {b[1]['px'] if b[1] else '-'}")

    print("\n  info request over the same socket:")
    ws_book = ws.post_info({"type": "l2Book", "coin": coin})
    print(f"    l2Book via ws -> {len(ws_book['levels'][0])} bids / "
          f"{len(ws_book['levels'][1])} asks, top bid {ws_book['levels'][0][0]['px']}")
    ws.stop()

    line("6. STORE")
    store = Store("data/hl.db")
    n_c = store.save_candles(coin, "1d", md.info.candles_lookback(coin, "1d", 200))
    n_f = store.save_funding(md.info.funding_history(
        coin, int(time.time() * 1000) - 14 * 86_400_000))
    n_t = store.save_trades(snap["_raw"]["trades"])
    store.save_ctx(snap["ts_ms"], coin, snap)
    store.save_book(snap["ts_ms"], coin, book.summary())
    store.save_features(snap["ts_ms"], coin, snap)
    print(f"  wrote candles={n_c} funding={n_f} trades={n_t}")
    print(f"  row counts: {store.counts()}")
    store.close()

    line("7. RATE LIMIT BUDGET")
    print(f"  weight used in the last 60s: {md.info.limiter.spent()} "
          f"of {md.info.limiter.budget} (exchange cap 1200/min)")
    print("\nDONE - every number above came from the live mainnet API.\n")


if __name__ == "__main__":
    main()
