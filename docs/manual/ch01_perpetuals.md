# Chapter 1 — What you are trading: perpetual swaps

## 1. What it is

A perpetual swap ("perp") is a futures contract with no expiry. You never own the coin. You hold a USD-denominated position whose value tracks an index of the spot price. Because there is no expiry to pull the perp back to spot, exchanges use a periodic cash payment between longs and shorts — **funding** — to keep the perp price near spot.

Every position on this desk is expressed in **dollars of notional**, never in coins. "Short $100 of BTC" is a valid order. "Short 150 BTC" is an ~$11M order at $76k and is never what we mean.

Two prices matter and they do different jobs:

| Price | How Hyperliquid builds it | What it is used for |
|---|---|---|
| **Oracle (index) price** | Weighted median of CEX spot prices, updated ~every 3 s; does not use Hyperliquid's own book at all [source: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/robust-price-indices] | Computing **funding** |
| **Mark price** | Median of three inputs: (a) oracle + 150 s EMA of (HL mid − oracle), (b) median of HL best bid / best ask / last trade, (c) weighted median of Binance, OKX, Bybit, Gate, MEXC perp mids (weights 3,2,2,1,1) [same source] | **Margining, liquidations, TP/SL triggers, unrealised PnL** |

Rule: **liquidation is triggered by the mark price, not the last trade and not the index.** A wick on Hyperliquid's own book alone cannot liquidate you because the mark is a median across venues [source: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/liquidations].

## 2. Why it matters to a trader

The perp is where leverage lives. Funding is the hourly price of that leverage, and open interest is its quantity. Together they are the only public, real-time view of *how crowded* a trade is. Spot volume tells you what changed hands; funding tells you who is paying to stay in. That is why crowd positioning is visible in the perp and nowhere else.

The cost of being wrong is also structural, not just price: a leveraged position that crosses maintenance margin is force-closed at the worst moment, and many forced closes at once become a cascade (Section 3, liquidations).

## 3. The reading rules

### 3a. Funding: formula and settlement

| Item | Hyperliquid | Binance (reference CEX) |
|---|---|---|
| Formula | F = average premium P + clamp(interest − P, −0.0005, +0.0005) [source: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding] | Same structure; clamp ±0.05% [source: https://www.binance.com/en/support/faq/360033525031] |
| Premium | impact_price_difference / oracle_price, where impact diff = max(impact_bid − oracle, 0) − max(oracle − impact_ask, 0) [HL funding doc] | Impact bid/ask vs index |
| Interest component | 0.01% per 8 h = 0.00125% per hour ≈ 11.6% APR, paid by longs to shorts when premium is zero [HL funding doc] | 0.01% per 8 h interval [Binance FAQ] |
| **Settlement** | **Every hour**, i.e. 24 payments/day; the displayed rate is an hourly rate [HL funding doc] | Historically every 8 h at 00:00 / 08:00 / 16:00 UTC; since 2026-01-02 Binance switches contracts between 1 h and 4 h settlement depending on how extreme the rate is [source: https://www.binance.com/en/support/faq/360033525031] |
| Cap | 4% per hour [HL funding doc] | Per-contract caps |
| Who pays | Perp above oracle → F > 0 → **long pays short**. Perp below → F < 0 → **short pays long** [HL funding doc] | Same |

### 3b. The sign convention, stated three ways (memorise all three, they are the same fact)

| Funding sign | Who pays whom | Where the perp trades | What the crowd is | Squeeze risk |
|---|---|---|---|---|
| **Positive** | Longs pay shorts | Perp **above** spot/oracle | **Crowded long** | Down (long liquidations) |
| **Negative** | Shorts pay longs | Perp **below** spot/oracle | **Crowded short** | **Up** (short squeeze) |

If you hold a long and funding is positive, **you pay**. If you hold a short and funding is negative, **you pay**. You are paid when you are on the unpopular side.

### 3c. Annualising and comparing rates

Crypto trades every day of the year, so the day count is **365**, not 252. Our store holds one daily bar for every calendar day [measured in our store: docs/MEASURED_LINKS_2026-09-16.md].

| Quoted as | Periods per year | Annualised |
|---|---|---|
| r per 8 h (CEX) | 3 × 365 = 1,095 | r × 1,095 |
| r per hour (Hyperliquid) | 24 × 365 = 8,760 | r × 8,760 |
| Daily volatility σ_d | 365 daily returns | σ_d × √365 (≈ 19.1 × σ_d), **not** √252 |

To compare a Hyperliquid hourly rate with a CEX 8-hour rate, multiply the hourly rate by 8.

### 3d. Open interest, basis, margin, liquidation

| Concept | Rule |
|---|---|
| Open interest (OI) | Total notional of open contracts. Every contract has exactly one long and one short, so **OI is always 50/50 long vs short by construction**. OI never tells you direction; it tells you how much leverage exists. Direction comes from funding, the premium, or account-level long/short ratios. |
| OI change × price | OI up + price up = new longs entering. OI up + price down = new shorts entering. OI down + price down = longs closing/liquidated. OI down + price up = shorts closing/squeezed. |
| Basis vs funding | Basis = perp (or dated future) price − spot, a level in $ or %. Funding = the periodic payment that the basis generates. Funding is the *rate*, basis is the *gap*. |
| Initial margin | Notional / leverage. |
| Maintenance margin (HL) | Half of the initial margin at the asset's maximum leverage, tiered by position size [source: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/liquidations]. Example: 50× max leverage → 2% initial → 1% maintenance. |
| Liquidation (HL) | When account equity < maintenance margin, the position is sent to the book as a market order; positions > 100k USDC are cut 20% at a time. If equity falls below 2/3 of maintenance margin without a fill, a **backstop liquidation** moves the position to the liquidator vault (HLP) [same source]. |
| Insurance fund / ADL (CEX) | Binance: an insurance fund absorbs bankrupt positions; if it cannot, **auto-deleveraging** force-closes the most profitable, most leveraged *winning* positions on the other side [source: https://www.binance.com/en/support/faq/what-is-auto-deleveraging-adl-and-how-does-it-work-360033525471]. Hyperliquid's official liquidation page describes the liquidator-vault backstop but no ADL queue (no official source found for HL ADL; omitted). |
| Cascade | Liquidation is a forced market sell (long) or buy (short). It moves the mark, which triggers the next tranche. On 2025-10-10, with OI near $217B, about $19.16B of positions were liquidated and 1.6M accounts wiped in hours; BTC went from ~$122.6k to ~$105k [source: https://www.coingecko.com/learn/october-10-crypto-crash-explained]. |
| Fees (HL base tier) | Taker 0.045%, maker 0.015%; fees go to HLP, the assistance fund and deployers [source: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees]. Desk assumption: 4.5 bps taker + half the spread, each side. |

## 4. Worked example (units on every line)

Position: **short $100 of XYZ-PERP** on Hyperliquid. Funding shown: **+0.02% per hour**. Hold: 3 days.

1. Sign check: positive → longs pay shorts → I am short → **I receive**.
2. Per hour: $100 × 0.0002 = **$0.02**.
3. Per day: $0.02 × 24 = **$0.48/day** (0.48% of notional/day).
4. Annualised: 0.02% × 8,760 = **175% APR** (this is an extreme, crowded-long print; the interest-only baseline is 11.6% APR [HL funding doc]).
5. Over 3 days: **+$1.44** received.
6. Costs: taker 4.5 bps × 2 sides = 9 bps = $0.09, plus half-spread each side (say 3 bps each) = $0.06. Total ≈ **$0.15**.
7. Net carry before price move: +$1.44 − $0.15 = **+$1.29**. Any price rise > 1.29% over the 3 days wipes it out. Compare to the coin's daily residual vol before deciding [measured in our store: median idiosyncratic vol share 0.84].

Contrast the exam error: quoting a CEX 0.05%/8h rate as "21.9% a year" is wrong; 0.05% × 3 × 365 = **54.75%** a year.

## 5. Common misreads

| Misread | Correct |
|---|---|
| "Negative funding = crowded long" | **Negative = crowded short**; shorts pay longs; perp below spot; squeeze risk is up. |
| "Negative funding means I pay to hold a long" | A long is **paid** when funding is negative. |
| Annualising with 252 days or √252 | Crypto has 365 trading days: ×1,095 for 8 h rates, ×8,760 for hourly, √365 for vol. |
| Treating Hyperliquid's hourly rate as an 8 h rate | Hyperliquid pays **hourly** [HL funding doc]. Multiply by 8 to compare with a CEX 8 h print. |
| "Short 150 BTC" | Size is in **dollars of notional**: "short $150 of BTC". |
| "OI is 70% long" | OI is always 50/50 by construction. Skew lives in funding/premium and in account-count long/short ratios, not in OI. |
| "Liquidation happens at the last trade price" | It happens at the **mark price** (multi-venue median). Funding uses the **oracle** price. |
| Applying stock-market ideas (borrow fee, short interest, hard-to-borrow) | Perps have no borrow. The cost of a short is **negative funding**; the cost of a long is **positive funding**. "Short interest" has no meaning when every contract is one long and one short. |
| "Funding is the basis" | Basis is the price gap; funding is the payment the gap produces. |
| Rising OI = bullish | Rising OI = more leverage on both sides. Read it with the price change (table 3d). |

## 6. Sources

- Hyperliquid funding: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding
- Hyperliquid liquidations and maintenance margin: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/liquidations
- Hyperliquid oracle and mark price: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/robust-price-indices
- Hyperliquid fees: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees
- Binance funding rates (formula, interest, intervals, 2026 frequency rule): https://www.binance.com/en/support/faq/360033525031
- Binance auto-deleveraging: https://www.binance.com/en/support/faq/what-is-auto-deleveraging-adl-and-how-does-it-work-360033525471
- 2025-10-10 liquidation cascade: https://www.coingecko.com/learn/october-10-crypto-crash-explained
- Our measured facts: docs/MEASURED_LINKS_2026-09-16.md
