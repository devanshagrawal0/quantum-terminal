# hyperliquid-bot — data layer

Everything the bot needs to *see* Hyperliquid. Live prices, order book, tape,
funding, open interest, account state, and the derived variables for 1–7 day
holds. Read-only: nothing here can sign, place or cancel an order.

Built against the live mainnet API (`https://api.hyperliquid.xyz/info` and
`wss://api.hyperliquid.xyz/ws`), verified by running it, not by trusting docs.

## Quick start

```bash
pip install -r requirements.txt
python scripts/selftest.py          # checks that can fail
python scripts/probe.py BTC         # live proof, every subsystem
python scripts/stream.py HYPE       # live book + tape
python scripts/record.py            # start collecting history
```

## What is where

| file | what it does |
|---|---|
| `hl/constants.py` | endpoints, rate-limit weights, intervals, tick rules |
| `hl/info.py` | one method per documented `/info` request type |
| `hl/ws.py` | websocket: subscriptions, keepalive, auto-reconnect, info-over-ws |
| `hl/meta.py` | universe cache, asset ids, **exchange price/size rounding** |
| `hl/book.py` | L2 book model, depth, imbalance, book-walking slippage |
| `hl/features.py` | every derived number (candles, funding, tape, ctx) |
| `hl/marketdata.py` | `snapshot(coin)` and `scan()` — the front door |
| `hl/account.py` | read-only account: equity, positions, fills, funding paid |
| `hl/store.py` | SQLite recorder for the history the exchange does not keep |
| `hl/ratelimit.py` | sliding-window weight budget (cap is 1200/min per IP) |

## The two calls you will actually use

```python
from hl import MarketData
md = MarketData()

snap = md.snapshot("BTC")   # ~110 variables for one coin, ~1.3s, 5 requests
table = md.scan()           # one row per perp (232 of them), 3 requests
```

`snapshot()` keeps the raw payloads under `snap["_raw"]` (`book`, `trades`,
`candles`, `funding_history`, `ctx`) so nothing is a black box.

## The variables

**Price / basis** — `mark_px`, `oracle_px`, `mid_px`, `prev_day_px`,
`day_change_pct`, `mark_oracle_bps`, `spot_mid`, `perp_spot_basis_bps`.

**Funding** (Hyperliquid charges **hourly**, and the API quotes the **hourly**
rate) — `funding_hourly`, `funding_apr`, `premium`, realised
`funding_mean_24h / 72h / 168h`, `funding_pos_frac_168h`, and
`carry_long_1d/2d/3d/7d` + `carry_short_*`, which is the actual cost of holding
for the horizons this bot trades. Cross-venue: `funding_binance`,
`funding_bybit`, `funding_hl_minus_cex_apr`.

**Open interest / volume** — `open_interest_base`, `open_interest_usd`,
`day_notional_volume`, `turnover_vol_over_oi`.

**Order book** — `book_best_bid/ask`, `book_mid`, `book_microprice`,
`book_spread_bps`, `book_depth_bid_usd_10bps` / ask, `book_imbalance_10bps`,
`book_imbalance_top5`, `book_buy_slippage_bps`, `book_sell_slippage_bps`,
plus `book.sweep(usd, is_buy)` for a full cost curve at any size.

**Tape** — `taker_buy_usd`, `taker_sell_usd`, `taker_imbalance`, `trade_vwap`,
`avg_trade_usd`, `max_trade_usd`, `trades_per_second`.

**Daily candles (the 1–7 day horizon)** — `ret_1d/2d/3d/7d/14d/30d`,
`vol_7d_ann`, `vol_30d_ann`, `vol_ratio_7_30`, `parkinson_*`, `atr_14_pct`,
`rsi_14`, `z_30d`, `dist_high_30d`, `dist_low_30d`, `dist_sma_7`,
`dist_sma_30`, `dist_ema_50`, `max_dd_30d`, `up_day_ratio_14d`,
`volume_z_30d`.

**Limits** — `sz_decimals`, `max_leverage`, `asset_id`, `at_oi_cap`.

## Things that bite, and how they are handled here

* **Funding is hourly, not 8-hourly.** A 7-day hold pays 168 funding charges.
  `carry_cost()` sums the whole hold instead of quoting a per-hour rate.
* **The spot ctx array is not aligned with the spot universe** (717 contexts
  vs 326 pairs; pair `@142` sits at list position 140). Contexts are matched on
  their `coin` field — indexing by position silently returns another token's
  price.
* **Bridged spot tickers carry a `U` prefix** (`BTC` perp ↔ `UBTC/USDC` spot,
  addressed as `@142`). Resolved from the live token list, not a fixed list.
* **`recentTrades` comes back newest-first**, so the tape window is measured
  min→max, not first→last.
* **`predictedFundings` can return a null venue body** when a CEX does not list
  the coin — skipped, never read as a zero rate. Missing
  `fundingIntervalHours` on a CEX venue falls back to 8h before normalising.
* **Prices must be ≤5 significant figures and ≤`6 - szDecimals` decimals**
  (spot: `8 - szDecimals`), integers always allowed. `Universe.round_px()` is
  the single place that rule lives; `scripts/selftest.py` checks it against the
  docs' worked examples.
* **Rate limits.** 1200 weight/min per IP (`l2Book` and `allMids` cost 2, most
  others 20, paged responses cost more). `WeightLimiter` blocks before you trip
  it and runs at 90% of the cap.
* **Only 5000 candles are retained** and there is no history at all for open
  interest or the book — hence `scripts/record.py`.

## Account (read-only)

```bash
$env:HL_ACCOUNT_ADDRESS = "0xyourpublicaddress"   # PowerShell
python scripts/account_check.py
```

Public address only. No private key, no API wallet, no signing code exists in
this package.

## Not built yet (on purpose)

Order placement, signing, and any strategy logic. Placing orders needs the
`/exchange` endpoint with EIP-712 signatures and an API wallet — a separate,
deliberate step.
