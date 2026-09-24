# Chapter 2 — The economic foundation: why prices move and what every feature measures

## 1. What it is

A price moves when someone must trade and the other side demands a concession to take it. Every feature we compute is a proxy for one of four things: **who must trade** (flows, forced flows), **how much it costs to trade** (liquidity), **what they are paid to wait** (risk premia, carry), or **what they know** (information). This chapter maps each feature family to the quantity it measures so the model never reads a number without knowing what it stands for.

## 2. Why it matters to a trader

In crypto, the largest and most repeatable moves are not from news arriving but from **positions being forced**: liquidations, token unlocks, index rebalances, ETF creations/redemptions. These are predictable in timing or in trigger, which is why the crypto-specific edge lives in reflexivity and positioning, not in guessing the next headline.

### Supply and demand for leverage
The perp is a market for leverage. When longs want leverage more than shorts do, the perp trades above spot and funding is positive: longs pay a fee that is the **price of leverage**. Funding is therefore a risk premium being paid in real time, and a high one means the crowd is already positioned. [measured in our store: sorting 172 coins daily by funding, the most-positive quintile earned the *lowest* 7-day forward excess return (+28 bps) and the most-negative quintile the highest (+54 bps); rank-IC −0.027, t = −3.8 over 377 days, docs/MEASURED_LINKS_2026-09-16.md §4.]

### Flows
- **Spot vs perp**: spot buying changes ownership; perp buying changes leverage. A rally on rising OI and rising funding is leverage-led and fragile; one on flat funding is spot-led and sturdier.
- **ETF flows**: daily creations/redemptions are published; they are a visible spot flow.
- **Stablecoin supply**: new stablecoins are dry powder; total supply rose from ~$194B to ~$211B in 2025 per Glassnode figures [source: https://cryptorank.io/news/feed/38f56-stablecoin-market-expands-in-2025]. The link to price is a widely used *folklore* indicator, not an established academic result.

### Liquidity and impact
A trade moves price by roughly (size ÷ depth). Thin books move more for the same dollar flow and also liquidate more violently. Kaiko notes memecoin price discovery is concentrated in derivatives and prone to cascading liquidations [source: https://www.kaiko.com/resources/meme-coins-a-market-phenomenon-or-an-investable-asset-class]. Spread and depth are the direct measures of this cost.

### Risk premia and carry
**Cash-and-carry**: buy spot, short the perp, collect positive funding; the position is price-neutral and earns the funding stream. When funding is negative the mirror trade is long perp / short spot. Funding is thus the market-clearing rent for leverage. On Hyperliquid the interest component alone is 0.01% per 8 h ≈ 11.6% APR paid to shorts when premium is zero [source: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding]. [measured in our store: being long the most-crowded-short quintile earned +101 bps per 7 days, ~48 bps of it funding collected; shorting the crowded-long quintile earned −6 bps — the crowd being long does not make the coin fall on schedule, §4b.]

### Information and news
Scheduled macro (CPI, FOMC) and exchange listings are priced within minutes on the majors. The efficient-market view says only surprises move price; the behavioural view (attention, momentum) says flows chase moves. In crypto both are supported: Liu & Tsyvinski find strong time-series momentum and that investor-attention proxies forecast returns, while "production" factors (mining cost) do not [source: https://academic.oup.com/rfs/article-abstract/34/6/2689/5912024]. Liu, Tsyvinski & Wu show a three-factor model — crypto **market, size, momentum** — prices the cross-section of coin returns, subsuming ten characteristic strategies [source: https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.13119].

### Reflexivity and forced flows
- **Liquidations**: forced market orders that move the mark and trigger the next tranche. On 2025-10-10 about $19.16B of positions were liquidated from OI near $217B [source: https://www.coingecko.com/learn/october-10-crypto-crash-explained].
- **Unlocks**: Keyrock's study of 16,000+ unlock events found ~90% were followed by short-term declines, that the price drift begins ~30 days before the date, that team unlocks averaged the worst outcome (about −25%) while ecosystem unlocks were slightly positive (+1.18%), and that unlocks over 5% of circulating supply saw median 30-day-window drops of 8–15% [source: https://keyrock.com/from-locked-to-liquidity-what-16000-token-unlocks-teach-us/].
- **Rebalancing**: index and ETF rebalances are known in advance and create flow at a known time (no quantified crypto source found; omitted).

## 3. The reading rules: feature family → what it measures → what it is for

| Feature family | Economic quantity | Use | Status |
|---|---|---|---|
| Returns / momentum (1–4 week) | Persistence of flow and attention | Trend entry; cross-sectional ranking | Well-established: momentum factor in JF 2022 and RFS 2021 (sources above) |
| Short-horizon reversal (1–3 day) | Liquidity provision / overreaction | Fade after shocks | Weak in our data: day after a BTC down-shock, high-beta alts +2.0% avg, n=11 — direction only [measured in our store §3] |
| Realised volatility | Uncertainty; the size of one "normal" move | Stops, sizing (stop ≥ 1.5–2× daily range), regime | Established measurement, not a return predictor on its own |
| Funding / basis | Price of leverage; crowd skew | Carry; contrarian at 7-day horizon; **no measurable link at 1–3 days** | Measured: IC −0.027, t −3.8 at 7d; 1d/3d nothing [store §4] |
| Open interest | Quantity of leverage (always 50/50 long/short) | Read with price change; cascade-risk gauge | Established mechanism |
| CVD / volume delta | Net aggressor flow: taker buys − taker sells | Confirms or diverges from price; rising price on falling CVD = passive absorption | Folklore-level; useful as a divergence check |
| Liquidations | Forced flow already executed | Cascade detection; exhaustion after a cluster | Established mechanism, timing folklore |
| Long/short account ratio | Crowd of *accounts*, not notional | Contrarian sentiment | Folklore; not the same as OI skew |
| Spread / depth | Cost of impact; how much a $ moves price | Sizing, venue choice, thin-book warning | Established |
| Cross-venue dispersion | Arbitrage stress; one venue's crowd | Detects local squeezes | Folklore |
| Beta / correlation to BTC | Share of a coin's move that is the market | Hedging; residual sizing | Measured: median beta 1.10, median R² 0.30, 48% of coins R² < 0.3; on shock days average pairwise correlation rises from 0.38 to 0.76 and stressed beta ≈ 1.4 for everything [store §1–3] |
| Sentiment indices | Attention | Weak momentum proxy | Attention forecasts returns in RFS 2021; commercial indices unvalidated |
| Calendar / events | Known forced flow (unlocks, FOMC, listings) | Avoid or fade | Unlocks: Keyrock (above); FOMC → BTC → alts chain [store §3] |
| On-chain flows | Exchange inflows (sell pressure), stablecoin mint | Slow-moving context | Folklore, direction-only |

## 4. Worked example (units)

Coin ABC, price $2.00. Features today: funding **+0.03%/hour** (most-positive quintile), 7-day momentum **+18%**, OI **+40% in 3 days**, daily realised vol **6%/day**, beta to BTC 1.2, R² 0.25.

1. Funding annualised: 0.03% × 8,760 = **263% APR**. A $100 long pays $100 × 0.0003 × 24 = **$0.72/day**.
2. What it measures: leverage demand is extreme, crowd is long, OI up with price up → new longs, not shorts covering.
3. Momentum says continue; funding says the crowd is already in. Our store says the crowded-long quintile still drifted +28 bps over 7 days but a short earned −6 bps net after collecting funding [store §4b]. So: **no short on funding alone**; a long must beat 0.72%/day of carry.
4. Sizing: R² 0.25 → 75% of ABC's variance is its own; residual vol ≈ 6% × √0.75 ≈ **5.2%/day**. A 5% stop is one residual day — too tight. The desk sets stops on the *own* move: 1.5–3 × 5.2% = **7.8%–15.6%**, so $100 notional risks ~$8–16.
5. Annualised vol for comparison: 6% × √365 = **115%** (not 6% × √252 = 95%).

## 5. Common misreads

| Misread | Correct |
|---|---|
| CVD falling while price rises = "buyers in control" | CVD falling = net **taker selling**; price rising anyway means passive bids are absorbing — a divergence, bullish only until the bids pull. CVD is *aggressor* flow: taker buys minus taker sells. |
| High funding = short it now | At 1–3 days there is no measurable link [store §4]; at 7 days the effect is real but small and the short leg contributes ~0 net [store §4b]. |
| Momentum and funding always agree | They often conflict: momentum measures persistence, funding measures crowding. Both can be true. |
| Beta protects in a crash | Stressed beta ≈ 1.4 for all alts; low-beta alts fell −10.4% vs high-beta −10.7% on BTC down-shock days [store §3]. |
| Stock-market vocabulary (short interest, borrow fee, days-to-cover) | No borrow in perps; the cost of a short is negative funding; "short interest" ≠ OI (OI is 50/50). |
| Annualise vol with √252 | √365. |
| Unlock day is the event | The drift starts ~30 days before; much of the move is done by the date [Keyrock]. |
| More OI = more bulls | OI is leverage on both sides; direction only from price change + funding. |
| Citing papers from memory | Only two crypto factor papers are cited here; anything else must be marked folklore. |

## 6. Sources

- Liu, Tsyvinski & Wu (2022), "Common Risk Factors in Cryptocurrency", Journal of Finance 77(2): 1133–1177: https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.13119
- Liu & Tsyvinski (2021), "Risks and Returns of Cryptocurrency", Review of Financial Studies 34(6): 2689–2727: https://academic.oup.com/rfs/article-abstract/34/6/2689/5912024
- Keyrock, token unlocks study: https://keyrock.com/from-locked-to-liquidity-what-16000-token-unlocks-teach-us/
- Kaiko on memecoin liquidity and derivatives-led price discovery: https://www.kaiko.com/resources/meme-coins-a-market-phenomenon-or-an-investable-asset-class
- Hyperliquid funding mechanics: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding
- 2025-10-10 cascade: https://www.coingecko.com/learn/october-10-crypto-crash-explained
- Stablecoin supply 2025 (Glassnode figures as reported): https://cryptorank.io/news/feed/38f56-stablecoin-market-expands-in-2025
- Our measured facts: docs/MEASURED_LINKS_2026-09-16.md
