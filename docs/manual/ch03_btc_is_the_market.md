# Chapter 3 — BTC is the market: beta, R², dominance, crashes, hedging

Read this before any chain that mentions an altcoin. Every alt you trade is partly a BTC
trade. This chapter tells you how much, when that share changes, and what to do about it.
Numbers marked **[measured in our store]** come from our own 172-coin Hyperliquid data
(`docs/MEASURED_LINKS_2026-09-16.md`, 90-day window to 2026-09-16 unless stated). Numbers
with a URL come from the cited source. Nothing else is a number.

## 1. What it is

- **Beta to BTC** — how many percent a coin moves, on average, per 1% BTC move, on normal
  days. Beta 1.6: BTC +5% → +8% expected from BTC alone. Beta 0.2: almost none of the coin's
  move is BTC.
- **R² to BTC** — the share of a coin's daily variance explained by BTC. R² 0.7: 70% of its
  moves are BTC; 30% is its own story. R² 0.05: it is its own story; beta is nearly
  meaningless for it.
- **Residual (idiosyncratic) return** — the coin's move minus beta × BTC's move. This is the
  part your thesis is about. A long on a beta-1.5 alt "because BTC will bounce" is a BTC
  trade with extra vol; a long on it "because of its unlock/listing/story" is a residual
  trade, and BTC is noise you may want to hedge out.
- **Crash-day (stressed) beta** — beta measured only on days BTC moved more than 2.5σ. It is
  higher than normal beta for nearly every alt, and it is the beta that matters for your
  stop and for the book's stress test.
- **BTC dominance** — BTC market cap ÷ total crypto market cap [source:
  https://nexo.com/blog/bitcoin-dominance-altcoin-season-signals]. Falling dominance while
  BTC rises = money rotating into alts ("altseason"); rising dominance in a sell-off = alts
  falling harder than BTC.

## 2. Why it matters (the economics)

BTC is the collateral, the liquidity anchor and the sentiment gauge of the whole market.
Leverage across venues is largely BTC- and USD-collateralised; when BTC drops, collateral
values fall, margin calls hit every alt position, and forced selling spreads to coins whose
"story" changed nothing. That is why alts share one factor on the way down more than on the
way up: the down-move is a *funding and margin* event, the up-move is partly *narrative*
(rotation into whichever sector is hot).

**[measured in our store]** for the typical alt:
- median beta **1.10** (10th–90th pct 0.68–1.50); median R² **0.30**.
- **48% of coins have R² < 0.3** (their own story dominates); **only 4% have R² > 0.6**
  (ETH 0.78, XRP 0.73, BNB 0.69, SOL 0.67, DOGE 0.66).
- median idiosyncratic vol share **0.84**: for most coins, most of the *volatility* is their
  own even when the *direction* rhymes with BTC.

So: for the majors, BTC explains most of the move; for the long tail, BTC explains a third
or less and the rest is the coin. Both facts are true at once, and you must know which kind
of coin you are holding.

Academic check: crypto betas are far less stable and predictable than stock betas; plain OLS
betas explain much less of next-period beta than in US equities, shrinkage helps, and
beta-hedged portfolios reduced variance for only about **17% of the universe** [source:
https://jfin-swufe.springeropen.com/articles/10.1186/s40854-025-00777-w]. Our desk therefore
shrinks betas (Vasicek) and treats a beta as a working estimate, not a constant.

## 3. Reading rules

### 3a. Which kind of coin is this?
| R² to BTC | reading | what your thesis must be about | stop/size basis |
|---|---|---|---|
| > 0.6 (majors) | "mostly a BTC trade" | BTC direction, or a spread vs BTC | total daily move; BTC view drives it |
| 0.3–0.6 | "half BTC, half its own" | both: state the BTC assumption AND the coin story | residual move, but check BTC first |
| < 0.3 (half the universe) | "its own story" | the coin's story; BTC is noise | residual (own) daily move; hedging BTC adds little |

### 3b. Correlations are not constant — they rise in crashes
**[measured in our store]** average pairwise correlation across the universe: all days
**0.50**; calm days **0.38**; top-10%-BTC-move days **0.76**. One measured public episode:
alt–BTC correlation jumped from **0.19 to 0.57** when BTC fell for more than two weeks from
a record [source: https://gulfnews.com/your-money/cryptocurrency/beating-bitcoin-requires-alt-coin-traders-to-mind-correlations-1.2174493].

| regime | what the book of "diversified" alt longs really is |
|---|---|
| calm | many bets (correlation ~0.4) |
| BTC shock day | one bet (correlation ~0.76); first principal component explains **54%** of variance over the year **[measured]** |

### 3c. BTC shock days — what actually happens **[measured: 31 days, 2 years]**
| | BTC | ETH | high-beta alts | low-beta alts | next day BTC | next day high-beta |
|---|---|---|---|---|---|---|
| down shocks (n=11) | −7.4% | −9.1% | −10.7% | **−10.4%** | +1.5% | +2.0% |
| up shocks (n=20) | +8.0% | +9.4% | +10.2% | +7.1% | −1.1% | −0.3% |

Readings:
- On a down shock, **low-beta alts fall as much as high-beta alts**. Normal-day beta does not
  protect you. Assume stressed beta ≈ **1.4** for every alt in the stress test.
- On an up shock, high-beta leads, low-beta lags: beta works on the way up.
- Day after: partial bounce after down shocks, partial fade after up shocks (small n —
  direction only, not a size to trade).
- Chain "Fed surprise → BTC down → alts down more" is real on the day; the order is
  alts ≥ ETH > BTC, and it does not matter much which alt.

### 3d. Dominance and rotation
| dominance | BTC price | reading |
|---|---|---|
| falling | rising | rotation into alts; high-beta and hot-sector alts outperform |
| rising | rising | BTC-led move; alts lag; alt longs underperform BTC |
| rising | falling | risk-off; alts fall more than BTC; cut alt beta |
| falling | falling | rare; usually a specific alt bid (ETF/news) while BTC leaks |

Altseason is often *defined* by an index threshold (e.g. 75% of top alts beating BTC over 90
days) [source: https://tangem.com/en/blog/post/what-is-altseason/]; treat such indices as
descriptions of the past 90 days, not forecasts.

### 3e. When to hedge with BTC, and how much
- Hedge when the thesis is **residual** (story, unlock, listing, funding) and the coin's R² is
  meaningful (≥ 0.3): you want the story, not the BTC lottery.
- Do not bother hedging an R² < 0.15 coin: the hedge removes little variance and costs
  fees + BTC funding (the academic finding above: hedges help only a minority of coins).
- Do not hedge if the thesis *is* BTC direction — you would cancel your own trade.
- Size: hedge notional = beta × position notional, in **dollars of BTC**, opposite side.
  In stress, the hedge under-protects (stressed beta > normal beta); accept that or
  over-hedge toward the crash beta if the trade spans an event.

## 4. Worked example (units matter)

Long KAITO, $100 notional. **[measured]** KAITO: beta 0.62, R² 0.03, own daily move 7.3%.
- Expected move from BTC on a BTC −5% day: 0.62 × −5% = **−3.1%**. But R² 0.03 says BTC
  explains 3% of its variance: the coin will do its own thing; the −3.1% is a weak prior.
- Own daily move 7.3% → stop band 1.5–3 own moves = **11%–22%**. A 5% stop is 0.7 of a
  move: noise, not thesis failure.
- Hedge? Beta × notional = 0.62 × $100 = **$62 of BTC short** (not "62 BTC"). With R² 0.03
  it removes almost nothing — skip it; the book's beta band handles the little there is.

Long SOL, $100 notional. **[measured]** SOL R² 0.67 (beta ≈ 1.2 typical).
- This *is* a BTC trade plus a spread. State the BTC assumption in the chain. On a BTC −5%
  day expect ≈ −6% from BTC alone; on a shock day assume 1.4 × BTC.
- If the thesis is "SOL outperforms on its ETF/news story", hedge $120 of BTC short and you
  hold the spread; if the thesis is "BTC bounces", do not hedge.

## 5. Common misreads

1. **"Short 150 BTC"** — hedge sizes are in **dollars of BTC notional** (beta × position $),
   never in coins. 1.5 × $100 = **$150 of BTC**.
2. **Using normal beta on a crash day.** Down shocks hit low-beta alts as hard as high-beta
   ones **[measured]**. Stress at beta 1.4 for everything.
3. **"Diversified" = five alt longs.** In a shock that is one bet (corr 0.76 **[measured]**);
   diversification across alts only exists on calm days.
4. **Confusing beta with R².** Beta 1.6 with R² 0.1 means: when it does follow BTC it moves
   1.6×, but it rarely follows. Size and stop from the own move, not from beta.
5. **Hedging everything.** Hedges cost fees and funding and help only a minority of coins
   [source above]; hedge residual theses on R² ≥ 0.3 coins, leave the rest to the book rules.
6. **Reading dominance as a forecast.** It describes what has happened; use it to name the
   regime (BTC-led vs rotation), not to predict the next week.
7. **Ignoring ETH.** In down shocks ETH fell more than BTC (−9.1% vs −7.4% **[measured]**);
   ETH is not a "safer BTC".

## 6. Sources
- Our store: `docs/MEASURED_LINKS_2026-09-16.md` §1–3 (172 Hyperliquid coins, daily closes, 2024-09 → 2026-09).
- Sila, Mark, Kristoufek, Weber, "Crypto market betas: the limits of predictability and hedging", Financial Innovation 2025 — https://jfin-swufe.springeropen.com/articles/10.1186/s40854-025-00777-w
- Alt–BTC correlation 0.19 → 0.57 in a >2-week BTC drawdown — https://gulfnews.com/your-money/cryptocurrency/beating-bitcoin-requires-alt-coin-traders-to-mind-correlations-1.2174493
- BTC dominance definition — https://nexo.com/blog/bitcoin-dominance-altcoin-season-signals
- Altseason index definition — https://tangem.com/en/blog/post/what-is-altseason/
- Memecoin vol 2–3× BTC/ETH, drawdowns > 90% — https://medium.com/@gwrx2005/price-correlation-between-major-cryptocurrencies-and-memecoins-2019-2024-6ce899224366
