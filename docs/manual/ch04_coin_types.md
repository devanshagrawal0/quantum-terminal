# Chapter 4 — Coin types and sectors: the trader's taxonomy

## 1. What it is

A trader sorts coins by **what makes them move and how much**, not by legal category. "Utility / governance / security token" is a lawyer's list and predicts nothing about tomorrow's price. The trader's list is: which flow drives it, how much of its move is BTC (beta, R²), how big a normal day is, what its funding usually looks like, and what specific trap it carries.

## 2. Why it matters to a trader

[measured in our store: across 171 Hyperliquid coins, the median beta to BTC is 1.10 and the median R² is 0.30, so for the typical alt 70% of daily variance is its own story; only 4% of coins have R² > 0.6 (ETH 0.78, XRP 0.73, BNB 0.69, SOL 0.67, DOGE 0.66); docs/MEASURED_LINKS_2026-09-16.md §1.] That means a "BTC view" is a complete thesis for ETH and almost useless for a small-cap. Category tells you which case you are in, what stop size is sane, and which calendar events to check before opening.

On BTC shock days the categories collapse into one trade: average pairwise correlation is 0.38 on calm days and 0.76 on top-10% BTC-move days; on down-shocks low-beta alts fell −10.4% vs high-beta −10.7% [store §2–3]. Sector nuance applies on normal days only.

## 3. The reading rules

### 3a. Master table

| Category | Examples | Main driver | Typical beta to BTC | Typical daily move | Main trap |
|---|---|---|---|---|---|
| BTC | BTC | Macro liquidity, ETF flows, leverage cycles | 1.0 by definition | 90-day realised vol ~41% in 2025 ≈ 2.1%/day [source: https://dropstab.com/research/crypto/solana-ethereum-correlation-and-volatility]; ~40% in 2024 [source: https://research.kaiko.com/insights/bitcoin-volatility-dwindles-as-crypto-assets-mature] | Treating it as an alt: it is the market factor, not a bet on a project |
| ETH | ETH | BTC beta + ETF flows + L2/DeFi activity narrative | ~1 to crypto market; R² to BTC 0.78 [store §1]; ETH fell −9.1% vs BTC −7.4% on down-shocks [store §3] | ~60% ann. ≈ 3.1%/day [dropstab] | Assuming it holds up better than BTC in a crash; it falls more |
| Large-cap L1 | SOL, BNB, AVAX, ADA, SUI | BTC beta + ecosystem activity + memecoin/DEX volume on that chain | SOL R² 0.67, BNB 0.69 [store §1]; SOL "high-beta" | SOL ~80% ann. ≈ 4.2%/day [dropstab] | Mistaking chain-activity narrative for price support in a BTC drawdown |
| L2 | ARB, OP, STRK, ZK | ETH beta + unlock schedule + low float | (no source found; use store β per coin) | (no source found; use store residual vol) | **Unlocks**: large scheduled supply, drift begins ~30 days before [source: https://keyrock.com/from-locked-to-liquidity-what-16000-token-unlocks-teach-us/] |
| DeFi | UNI, AAVE, LDO, CRV | Protocol revenue, fee-switch/buyback votes, TVL, ETH beta | (no source found; store per coin) | (store per coin) | Governance headline pumps that fade when no cash flow follows |
| Exchange tokens | HYPE, BNB | Exchange volume → fees → **buybacks/burns**; venue-specific risk | BNB R² 0.69 [store §1]; HYPE (store per coin) | (store per coin) | Buyback support is real but not a floor: Hyperliquid's assistance fund routes ~97–99% of fees into HYPE purchases, >$1.3B deployed by May 2026 [source: https://aminagroup.com/research/hyperliquid-hype-etf-buyback-staking-yield-institutional-access-2026/]; a volume drop cuts the bid immediately |
| Memes | DOGE, PEPE, WIF, SHIB, BONK | Attention and leverage only; no cash flow | DOGE R² 0.66 [store §1]; sector traded as "highest-beta risk expression" [source: https://www.coindesk.com/markets/2026/01/03/dogecoin-spikes-11-pepe-jumps-25-as-2026-brings-starts-with-a-bang-for-memecoins]; the "2–3× BTC vol" rule of thumb: no formal source found, omitted — use store residual vol | Single-day moves of +11% (DOGE) and +25% (PEPE) on 2026-01-03 [coindesk]; 2025 full year DOGE ≈ −65%, PEPE ≈ −80% while BTC ≈ +32% [source: https://cryptoticker.io/en/are-shiba-inu-pepe-dogecoin-dead-2025-memecoin-vs-bitcoin-analysis/] | **Reflexivity**: price discovery sits in derivatives, so cascades are amplified [source: https://www.kaiko.com/resources/meme-coins-a-market-phenomenon-or-an-investable-asset-class]; extreme funding both ways |
| AI / agent tokens | (e.g. KAITO in our store) | Narrative rotation, listings, AI-news beta | KAITO β 0.62, R² 0.03, idio vol 7.3%/day [store §1] | 7%+/day for KAITO [store §1] | Pure idiosyncratic: BTC hedge does nothing; a 5% stop is under one daily move |
| RWA | ONDO, and treasury/credit tokens | TradFi-adoption headlines, partnerships, rates narrative | (no source found; store per coin) | (store per coin) | Headline-driven pumps with thin books |
| Stablecoins | USDT, USDC, USDe | Pegged to $1 by design; supply is a *flow* indicator, not a trade | ~0 | ~0 | **Never traded directionally**; trade the peg only in a depeg crisis and never here |
| New listings / low-float high-FDV | Any coin < 90 days on Hyperliquid or with float ≪ FDV | Listing flow, airdrop sellers, VC unlocks | Unstable; store β meaningless with < 90 days | Highest in the store: ACE 17.6%/day, SKR 13.7%/day, HMSTR 10.8%/day idiosyncratic [store §1] | **Listing pump-and-fade** and unlocks; team unlocks averaged ≈ −25% [Keyrock] |

### 3b. Behaviour by BTC regime

| Regime | BTC | ETH | High-beta alts (top quartile) | Low-beta alts | Memes / new listings |
|---|---|---|---|---|---|
| BTC up-shock day (n=20) | +8.0% | +9.4% | +10.2% | +7.1% | High-beta leads [store §3] |
| BTC down-shock day (n=11) | −7.4% | −9.1% | −10.7% | −10.4% | Everything falls ≈ equally [store §3] |
| Next day after down-shock | +1.5% | — | +2.0% | — | Partial bounce, direction only [store §3] |
| Calm day | Own story dominates for 48% of coins (R² < 0.3) [store §1] | | | | |

### 3c. Funding behaviour by category

| Category | Typical funding pattern | Reading |
|---|---|---|
| BTC, ETH | Near the 0.01%/8h interest baseline most of the time [source: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding]; spikes with leverage cycles | Extreme prints are rarer and more meaningful |
| Large-cap L1, DeFi | Follows BTC funding, wider range | Read with OI change |
| Memes | Extreme both ways; crowded-long prints during rallies, deeply negative in dumps | Highest carry, highest squeeze risk both ways |
| New listings | Often strongly negative early (airdrop recipients and VCs hedge by shorting the perp) | Negative funding = crowded short = squeeze risk **up**; being paid to be long is the measured edge [store §4b: long the most-negative quintile +101 bps/7d] |
| Stablecoins | n/a | Not traded |

## 4. Worked example (units)

Two candidates, $100 notional each, target hold 5 days.

**A. KAITO (AI token)**: funding −0.01%/hour, 7-day return −22%, β 0.62, R² 0.03, idio vol 7.3%/day [store §1].
- Funding: negative → shorts pay longs → a long **receives** $100 × 0.0001 × 24 = $0.24/day = $1.20 over 5 days.
- BTC does not explain it (R² 0.03), so a BTC hedge is pointless; it is a standalone bet.
- Stop: ≥ 1.5 × 7.3% ≈ **11%** ($11 at risk). A 5% stop is 0.7 of one daily move and will be hit by noise.
- Trap: is there an unlock inside the next 30 days? Check the calendar before sizing [Keyrock].

**B. SOL (large-cap L1)**: funding +0.005%/hour, β ≈ 1.0, R² 0.67 [store §1], vol ≈ 4.2%/day [dropstab].
- Funding: positive → a long **pays** $100 × 0.00005 × 24 = $0.12/day = $0.60 over 5 days.
- Two-thirds of SOL's move is BTC; the thesis must be a BTC thesis or a hedged residual.
- Stop: ≥ 1.5 × 4.2% ≈ **6.3%**.
- Round-trip cost either coin: 2 × (4.5 bps + half spread) ≈ 12–15 bps ≈ $0.12–0.15.

## 5. Common misreads

| Misread | Correct |
|---|---|
| Listing categories as utility / governance / security / payment | Those are legal labels. Trader categories: BTC, ETH, L1, L2, DeFi, exchange, meme, AI, RWA, stable, new-listing — each with a driver, beta, daily move, funding habit and trap. |
| "Low-beta alt = safer in a crash" | On down-shock days low-beta alts fell −10.4% vs high-beta −10.7% [store §3]. Use stressed beta ≈ 1.4 for everything. |
| Trading a stablecoin long/short | Stablecoins are $1 by design; their *supply* is a flow indicator, the coin itself is never a directional trade. |
| "Memecoins are 2–3× BTC vol" stated as fact | Plausible but no formal source found; use the coin's measured residual vol from the store. |
| Shorting a new listing because funding is negative | Negative funding = crowded **short**; the measured edge is being **paid to hold the long** [store §4b], subject to the unlock calendar. |
| Exchange-token buyback = price floor | The buyback is a fee-driven bid, not a floor; it shrinks the moment volume drops [aminagroup]. |
| Using a 5% stop on a small-cap | ACE moves 17.6%/day idiosyncratically [store §1]; the stop must be ≥ 1.5–2× the daily move or the trade is a coin flip on noise. |
| "This L2 has strong tech" as a price thesis | L2/DeFi prices are driven by unlock supply and ETH beta far more than by tech; check float and calendar first. |
| Sizing in coins ("short 150 BTC") | Size in dollars of notional: "$100 of BTC". |

## 6. Sources

- Our measured facts (beta, R², idio vol, shock days, funding quintiles): docs/MEASURED_LINKS_2026-09-16.md
- BTC/ETH/SOL 2025 realised vol and correlation: https://dropstab.com/research/crypto/solana-ethereum-correlation-and-volatility
- BTC volatility 2024 (~40%): https://research.kaiko.com/insights/bitcoin-volatility-dwindles-as-crypto-assets-mature
- Memecoin market structure (derivatives-led, cascades): https://www.kaiko.com/resources/meme-coins-a-market-phenomenon-or-an-investable-asset-class
- Memecoin single-day moves 2026-01-03: https://www.coindesk.com/markets/2026/01/03/dogecoin-spikes-11-pepe-jumps-25-as-2026-brings-starts-with-a-bang-for-memecoins
- Memecoin 2025 underperformance vs BTC: https://cryptoticker.io/en/are-shiba-inu-pepe-dogecoin-dead-2025-memecoin-vs-bitcoin-analysis/
- Token unlocks (Keyrock, 16,000+ events): https://keyrock.com/from-locked-to-liquidity-what-16000-token-unlocks-teach-us/
- HYPE assistance-fund buyback: https://aminagroup.com/research/hyperliquid-hype-etf-buyback-staking-yield-institutional-access-2026/
- Hyperliquid fee routing to assistance fund: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees
- Hyperliquid funding baseline: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding
