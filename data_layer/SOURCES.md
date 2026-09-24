# SOURCES — every API, documented in its category

**Legend — status is earned, never assumed:**
`✅ VERIFIED` = called it, saw real data (date given) · `⬜ UNVERIFIED` = in code/docs, never confirmed · `❌ DEAD` = confirmed broken · `🔲 PLANNED` = free, not yet wired

**Cost rule for this system: FREE ONLY.** Anything paid is listed under §9 and stays off until explicitly approved.

Credentials held (`.env`): `HL_ACCOUNT_ADDRESS`, `LIGHTER_L1_ADDRESS`, `LIGHTER_READONLY_TOKEN`. **Everything else is keyless.**

---

## 1. `crypto_cex/` — centralised exchange market data

### 1.1 Binance — Futures Data ✅ VERIFIED (stored: 172 coins, hourly, 31 days)
| | |
|---|---|
| Base | `https://fapi.binance.com/futures/data/` |
| Auth | none · Free · Public |
| Endpoints | `topLongShortPositionRatio`, `globalLongShortAccountRatio`, `takerlongshortRatio`, `openInterestHist` |
| Gives | **Top-trader positioning** (`top_long_frac`, `top_ls_ratio`), retail L/S, taker buy/sell flow, OI history |
| Periods | `5m 15m 30m 1h 2h 4h 6h 12h 1d` — currently only `1h` collected |
| Notes | This IS the "Binance top traders" signal. Currently the single best positioning source we have. |
| Used by | `scripts/backfill_positioning.py` → `venues.db::positioning` |

### 1.2 Binance — Spot / Futures market ✅ VERIFIED (in `venues.db`)
| | |
|---|---|
| Base | `https://api.binance.com`, `https://fapi.binance.com` |
| Gives | Tickers, klines, depth, funding, mark price |

### 1.3 Binance — **Public historical archive** 🔲 PLANNED — *highest-priority backfill*
| | |
|---|---|
| Base | `https://data.binance.vision/` |
| Auth | none · Free · bulk ZIP/CSV download |
| Gives | **Years** of klines, aggTrades, funding — the fix for our 10-day history problem (`newsystem.md` §13 Tier A) |
| Why critical | §11 cannot estimate a single causal edge without deep numeric history. This is the cheapest path to it. |
| Status note | **Not yet verified** — must confirm depth/coverage for our coins before planning the backfill. |

### 1.4 Multi-venue quote collection ✅ VERIFIED (26 venues, 178 coins, 3,409 pairs)
Collected by `scripts/record_venues.py` → `venues.db::prices` (4.29M rows / 9.9 days).

| Venue | Host | Status |
|---|---|---|
| Bybit | `api.bybit.com` | ✅ in store |
| OKX | `www.okx.com`, `aws.okx.com` | ✅ |
| Kraken | `api.kraken.com`, `futures.kraken.com` | ✅ |
| KuCoin | `api.kucoin.com`, `api-futures.kucoin.com` | ✅ |
| Bitget | `api.bitget.com` | ✅ |
| Gate.io | `api.gateio.ws` | ✅ |
| MEXC | `contract.mexc.com` | ✅ |
| Huobi/HTX | `api.hbdm.com` | ✅ |
| Coinbase | `api.exchange.coinbase.com` | ✅ |
| Bitfinex | `api-pub.bitfinex.com` | ✅ |
| Phemex | `api.phemex.com` | ✅ |
| Crypto.com | `api.crypto.com` | ✅ |
| BingX | `open-api.bingx.com` | ✅ |
| WOO | `api.woo.org` | ✅ |
| BitMart | `api-cloud.bitmart.com` | ✅ |
| Backpack | `api.backpack.exchange` | ✅ |
| Paradex | `api.prod.paradex.trade` | ✅ |
| Aevo | `api.aevo.xyz` | ✅ |
| dYdX | `indexer.dydx.trade` | ✅ |
| Upbit | `api.upbit.com`, `api-manager.upbit.com` | ✅ (Korea premium) |
| Bithumb | `api.bithumb.com` | ✅ (Korea premium) |
| WazirX | `api.wazirx.com` | ✅ (India) |
| CoinDCX | `api.coindcx.com` | ✅ (India) |
| BitBNS | `api.bitbns.com` | ✅ (India) |

> **Regional venues (Upbit/Bithumb/WazirX/CoinDCX) are a real asset** — cross-region premium/discount is a genuine, under-crowded signal.

---

## 2. `crypto_onchain/` — transparent venues & chain data

### 2.1 Hyperliquid — Info API ✅ VERIFIED 2026-09-02
| | |
|---|---|
| Base | `https://api.hyperliquid.xyz/info` (POST, JSON body) |
| Auth | none for reads · Free |

| Request | Gives | Status |
|---|---|---|
| `recentTrades {coin}` | **Trades INCLUDING both wallet addresses (`users`)** | ✅ **the whale-tracking unlock** |
| `clearinghouseState {user}` | Any address's full perp book: size, entry, leverage, liq price, margin | ✅ |
| `clearinghouseState {user, dex}` | Same for **HIP-3 builder sub-dexes** | ✅ (found Dev's `xyz:CL` here) |
| `spotClearinghouseState {user}` | Spot balances | ✅ |
| `perpDexs` | All builder sub-dexes (`xyz`, `flx`, `vntl`, `hyna`, `km`, `abcd`, `cash`, `para`, `mkts`, `io`) | ✅ |
| `meta {dex}` | Universe per dex | ✅ |
| `allMids` | All mid prices | ✅ |
| `l2Book {coin}` | Order book — **`coin` must be top-level, NOT nested in `req`** (422 otherwise) | ✅ |
| `candleSnapshot` | OHLCV | ✅ |
| `portfolio {user}` | Account value + PnL history | ✅ |
| `userNonFundingLedgerUpdates` | Deposits/withdrawals/transfers | ✅ |
| `leaderboard` | — | ❌ **DEAD — HTTP 422 (2026-09-02)** |

> **Why this category matters most:** HL is fully transparent. `recentTrades` gives you *who*, and `clearinghouseState` turns any wallet into a full position readout. No CEX offers this. Positions beat opinions.

### 2.2 Lighter ✅ VERIFIED 2026-09-02
| | |
|---|---|
| Base | `https://mainnet.zklighter.elliot.ai/api/v1` |
| Auth | `LIGHTER_READONLY_TOKEN` for `/trades` · read-only, cannot trade or withdraw |
| Endpoints | `/accountsByL1Address`, `/account?by=index`, `/orderBookDetails`, `/orderBooks`, `/trades`, `/pnl` |
| Gotchas | Spot tokens sit under `assets` with `margin_mode:"disabled"` and are **excluded from `total_asset_value`**. Spot markets are `SYM/USDC` in `/orderBooks`. |

### 2.3 DefiLlama ⬜ UNVERIFIED (in code)
`https://api.llama.fi`, `https://stablecoins.llama.fi`, `https://defillama-datasets.llama.fi` — TVL, protocol flows, **stablecoin supply** (liquidity proxy). Free, no key.

---

## 3. `derivatives/` — options & volatility

### 3.1 Deribit ⬜ UNVERIFIED (DVOL used in dashboard)
| | |
|---|---|
| Base | `https://www.deribit.com/api/v2/public/` |
| Auth | none · Free |
| In use | DVOL index (BTC vol) + 180d series |
| 🔲 PLANNED | **Full options chain** — `get_instruments`, `get_book_summary_by_currency`, `ticker` → **skew, put/call ratio, term structure, max pain**. Real positioning/fear data, currently unused. |

### 3.2 Funding & OI (cross-venue) ✅ VERIFIED
Collected via §1 venues → `venues.db::hl_state` (funding_hourly, oi_base) and `positioning`.

---

## 4. `news/` — editorial & official announcements

### 4.1 Crypto media (RSS/HTML) ⬜ UNVERIFIED individually · 441 events stored / 9.3 days
`coindesk.com` · `cointelegraph.com` · `cryptoslate.com` · `decrypt.co` · `bitcoinist.com` · `bitcoinmagazine.com` · `newsbtc.com` · `protos.com` · `coinjournal.net` · `cryptobriefing.com` · `news.bitcoin.com` · `cryptopanic.com`
→ `scripts/record_events.py` → `events.db::events`

### 4.2 Official / primary sources ⬜ UNVERIFIED — **higher tier than media**
| Source | Host | Gives |
|---|---|---|
| Binance announcements | `binance.com` + TG `binance_announcements` | **Listings** — the fastest-moving scheduled catalyst |
| SEC | `www.sec.gov` | Filings |
| Federal Reserve | `www.federalreserve.gov` | Policy |
| HL universe changes | HL `meta` diff | New/delisted perps — ✅ stored (`events.db::hl_universe_changes`) |

> **Source tiering matters (§3.3):** official > wire > media > social. One Reuters story copied 40× is **one** event. Dedup before it ever reaches a signal.

### 4.3 🔲 PLANNED — free news aggregation
`cryptocurrency.cv` — free crypto news API, **no key required**, RSS/JSON + historical archive.

---

## 5. `social/` — crowd text

**✅ VERIFIED 2026-09-02 — 19 channels live, 15,856 posts, most refreshed <10 min.**
Collector: `scripts/record_social.py` → `social.db::posts`

| Source | Channels | Posts | Status |
|---|---|---|---|
| StockTwits | BTC.X, ETH.X, SOL.X, XRP.X, DOGE.X | 12,576 | ✅ live |
| Reddit | Bitcoin, CryptoCurrency, CryptoMarkets, solana, ethereum | 1,308 | ✅ live |
| Reddit | SatoshiStreetBets | 26 | ⚠️ **STALE 8 days**, 156 timeout failures |
| 4chan | /biz/ | 1,328 | ✅ live |
| Telegram | whale_alert_io, wublockchainenglish, cointelegraph, WatcherGuru, binance_announcements, bwenews, unfolded | 810 | ✅ live |

**Known issue:** frequent `URLError: urlopen timed out` across Reddit/StockTwits (needs retry/backoff + UA rotation in the collector layer — exactly what `collectors/` is for).

### 5.1 🔲 PLANNED — free, endpoints already probed
| Source | Endpoint | Notes |
|---|---|---|
| **LunarCrush** | `lunarcrush.com/api4/public/topic/{topic}/v1` | Free public tier. Social volume/dominance. In `probe_sentiment.py`, **not collecting** — quick win. |
| **Farcaster** | `client.warpcast.com/v2/recent-casts` | Free. Crypto-native crowd. Probed, **not collecting** — quick win. |
| BitcoinTalk | `bitcointalk.org` | Free forum. |

### 5.2 ❌ NOT FREE — see §9
**X / Twitter** — no free tier since Feb 2026.

### 5.3 ⚠️ POLICY-GATED
**Discord** — only via **our own bot invited to servers that permit bots**. Self-bots / user-account scraping violate ToS — **will not do**.

---

## 6. `macro/` — rates, FX, commodities, liquidity

| Source | Host | Gives | Status |
|---|---|---|---|
| Yahoo Finance | `query1.finance.yahoo.com` | ^VIX, ^GSPC + any ticker OHLC | ⬜ in use (spot reads only, **not stored**) |
| US Treasury Fiscal Data | `api.fiscaldata.treasury.gov` | **TGA balance** (liquidity) | ⬜ in use |
| Federal Reserve | `federalreserve.gov` | Policy/releases | ⬜ |
| BEA | `apps.bea.gov` | GDP/economic accounts | ⬜ |
| **FRED** | `fred.stlouisfed.org` | 🔲 **PLANNED — free key.** Yields, inflation expectations (T5YIE/T10YIE), oil (DCOILWTICO), DXY, real rates | **The §11 causal-chain backbone.** Decades of free history. |

> **Gap:** macro is *read live but never stored*. §11's chain (oil → inflation exp → yields → risk) needs **stored deep history**. FRED + Yahoo bulk download fixes this cheaply.

---

## 7. `prediction_markets/` — implied probabilities

| Source | Host | Status |
|---|---|---|
| Kalshi | `api.elections.kalshi.com` | ⬜ UNVERIFIED (wired via Arbiter) |
| Polymarket | `gamma-api.polymarket.com`, `clob.polymarket.com` | ⬜ UNVERIFIED |

> **Strategically important:** these are the only direct read on **what the market expected** — the missing input for the priced-in / surprise agent (`newsystem.md` §3.3, §12 `expectation_gap`). Free. Under-used.

---

## 8. `reference/` — slow-moving facts

| Source | Host | Gives | Status |
|---|---|---|---|
| CoinGecko | `api.coingecko.com` | Market cap, FDV, supply, categories | ✅ in use |
| Token unlocks | via CoinGecko ids | Unlock calendar — 142 tokens stored | ✅ `unlocks.db` |
| alternative.me | `api.alternative.me` | Fear & Greed index | ✅ in use |
| arXiv | `export.arxiv.org` | q-fin papers | ✅ in use |
| SEC | `www.sec.gov` | Filings | ⬜ |

---

## 9. PAID — parked, not wired (needs explicit approval)

| Source | Cost (Sep 2026) | Verdict |
|---|---|---|
| X/Twitter official | pay-per-use, ~$5/1k reads; full archive **$42k/mo** enterprise | ❌ no |
| X via resellers | Sorsa ~$0.02/1k · TwitterAPI.io $0.15/1k · Xpoz free 500 credits then ~$20/mo | ⏸ cheapest viable route if we ever want X |
| Birdeye | free tier 30k CU/mo, then $39/mo | ⏸ Solana/DEX depth |
| CoinMarketCap | free tier + paid WS | ⏸ redundant with CoinGecko |

---

## 10. Build order (free only, highest value first)

1. **HL whale tracking** (`crypto_onchain`) — `recentTrades.users` → whale registry → `clearinghouseState` per wallet. Free, unique, positions-not-opinions.
2. **Binance historical archive** (`crypto_cex`) — `data.binance.vision` bulk backfill. Unblocks §11 entirely.
3. **FRED + Yahoo macro storage** (`macro`) — deep history for the causal chain.
4. **Deribit options chain** (`derivatives`) — skew/put-call/term structure.
5. **LunarCrush + Farcaster** (`social`) — endpoints already probed, ~1h work.
6. **Prediction markets** (`prediction_markets`) — the "what was expected" input.
7. **Collector reliability fix** (`collectors`) — retry/backoff for the Reddit/StockTwits timeouts.

---

## Verification log

| Date | What | Result |
|---|---|---|
| 2026-09-02 | HL `recentTrades` | ✅ returns `users` wallet addresses |
| 2026-09-02 | HL `leaderboard` | ❌ HTTP 422 — dead |
| 2026-09-02 | HL `perpDexs` + `clearinghouseState{dex}` | ✅ 10 builder dexes, positions readable |
| 2026-09-02 | Lighter account/orderbook/trades | ✅ |
| 2026-09-02 | `social.db` freshness | ✅ 19 channels, 18 fresh, 1 stale |
| 2026-09-02 | `venues.db` coverage | ✅ 26 venues / 178 coins / 4.29M rows / **9.9 days only** |
| 2026-09-02 | Binance `topLongShortPositionRatio` | ✅ 172 coins / 1h / 31 days stored |
