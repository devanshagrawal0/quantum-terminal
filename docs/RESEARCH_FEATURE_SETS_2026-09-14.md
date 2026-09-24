# What the research says about using our data as a SET — 2026-09-14

Dev's question: "we have so much data, why can't we use it — read the papers, see
what people do." This is the first pass. Every claim below has a source and a number;
where a paper could not be read in full, it says so. Plain English on purpose.

## The short version

1. **The single-variable approach we ran yesterday is exactly the approach the papers
   say is wrong for crypto.** Two peer-reviewed studies (2024, 2025) built one signal
   out of 28–34 indicators and found the money is in the combination, not in any one
   indicator. Their words: "the benefits from model complexity are limited" — a simple
   *combination* of simple things beats both a single indicator and a fancy model.
2. **We already compute almost every input they use.** Of CTREND's 28 indicators, 26
   are columns in our `feat_*` tables today. Of the 34 "characteristics" in the ML
   paper, we have ~20 outright and can build ~8 more from data we hold.
3. **The strongest, most tradeable result is a WEEKLY signal, not daily.** Weekly
   returns are less noisy, turnover is ~70% a week instead of ~150% a day, and that is
   why it survives fees where our daily reversal died.
4. **It works in the big, liquid coins** — which is our universe (Hyperliquid perps),
   not the 3,000-coin junk tail. CTREND in the 10% largest coins: +2.51%/week, still
   significant at 1%.
5. **What we have that the papers do not:** hourly bars (they use daily), Binance crowd
   positioning, funding, cross-venue spreads/basis, unlock sizes, news. Nobody in
   these papers had that. That is where an edge nobody else has would come from —
   but only on top of a working base signal, not instead of one.

## Paper 1 — "A Trend Factor for the Cross Section of Cryptocurrency Returns"
Fieberg, Liedtke, Poddig, Walker, Zaremba. *Journal of Financial and Quantitative
Analysis* 60(7), Nov 2025. Read in full (38 pages).

**What they built.** One number per coin per week — CTREND — that says "how strong is
the trend, looking at everything at once." Inputs, 28 of them, all from price and volume:
- momentum oscillators: RSI(14), stochastic K and D, stochastic-RSI, CCI
- 7 moving averages of price (3, 5, 10, 20, 50, 100, 200 days), each DIVIDED BY the
  current price so a $60,000 coin and a $0.60 coin are comparable; MACD as a % of the
  fast EMA (= PPO); MACD minus its signal line
- 7 moving averages of dollar volume (same lengths) divided by current volume; a
  volume MACD (= PVO) and its signal-line gap; Chaikin money flow
- Bollinger lower/middle/upper (divided by price) and Bollinger width

**How they combine them (this is the method to copy):**
1. Each week, turn every indicator into a cross-sectional RANK across coins, mapped
   to [−0.5, +0.5]. Ranks, not raw values — kills outliers and price-scale effects.
2. For each indicator on its own, run a weekly regression "next week's return on this
   indicator's rank" over a rolling 52-week window → 28 separate weekly forecasts per
   coin.
3. Feed those 28 forecasts into an elastic net (L1+L2, mix 0.5, strength picked by
   AICc) with the rule that a weight must be POSITIVE (a forecast has to agree with
   the return it forecasts). Indicators that get weight 0 are dropped for that week.
4. CTREND = the plain average of the forecasts that survived. Re-fit every week.
That is "the best set together, chosen by the data, refit as the market changes."

**Results (Apr 2015 – May 2022, 3,244 coins, weekly, value-weighted quintiles):**
- Long top-fifth / short bottom-fifth: **+3.87% per week, t = 5.19, Sharpe 1.94**
  (their Table 3). Returns rise monotonically from bottom to top quintile.
- Big coins only: 50% largest +3.84%/wk; **10% largest +2.51%/wk**, alphas > 2%,
  significant at 1%. Most liquid 50%: +4.36%/wk (their Table 8).
- Costs: turnover 68% per week. Net of 30/40 bps per trade: **+2.90%/wk (t 3.89)**;
  net of 50/60 bps: +2.35% (t 3.16). Break-even cost **1.41% per trade** (their Table 9).
  Hyperliquid taker is 0.045% + a ~1 bp spread on majors, i.e. 20–30× below break-even.
- Robustness: 55,296 alternative design choices; Sharpe positive and significant in 79%
  of them. Beats size and momentum factors, which rarely reach Sharpe 2.

**Honest caveats they state:** sample ends May 2022 (no 2022 crash aftermath, no
2024-25). Weekly value-weighted. Combining ranks in a 52-week window needs ≥ ~60
weeks of history before the first forecast.

## Paper 2 — "Machine Learning and the Cross-Section of Cryptocurrency Returns"
Cakici, Shahzad, Będowska-Sójka, Zaremba. *International Review of Financial
Analysis* 94 (2024). Read in full (55-page working paper, Dec 2022).

**What they built.** 34 coin "characteristics" (on-chain: new/active addresses;
liquidity: volume, size, bid-ask, Amihud illiquidity, turnover, volume shocks;
risk: realised vol, beta, idiosyncratic vol, VaR; past returns: momentum at 7/13/22/31
days, 1-day reversal, long-term reversal, 90-day-high distance, CAPM alpha; return
shape: skew, kurtosis, max/min daily return; other: nominal price, seasonality,
salience) → 10 ML models (OLS, PLS, LASSO, elastic net, random forest, boosted trees,
neural nets 1–5 layers, SVM, a combination) → weekly return forecast → quintiles.

**Results (774 days ≈ 25 months, weekly):**
- Best (the combination): **+4.72% per week, Sharpe 5.37**, gross, equal-weighted.
- Top predictors, most models agree: **idiosyncratic volatility, CAPM alpha, max daily
  return, nominal price, VaR**; linear models also like distance-to-90-day-high;
  neural nets add illiquidity, volume, turnover. On-chain data barely matters.
- Turnover 79–111% a week. Break-even cost 133–281 bps. Net of a per-coin spread
  estimate + 10 bps fee they **lose ~60% of gross** but stay positive and significant.
- **The catch they are honest about:** "abnormal returns originate predominantly from
  short positions, concentrate in hard-to-arbitrage assets" — i.e. shorting tiny
  illiquid coins. That part does NOT transfer to Hyperliquid's ~180 liquid perps.
  "Return predictability … gradually declines over time."

## Paper 3 — funding / carry (perp-specific), partial read
- "Cryptocurrency as an Investable Asset Class: Coming of Age" (arXiv 2510.14435,
  Oct 2025): the spot-vs-perp carry trade had **Sharpe 6.45 over 2020–25, 4.06 in
  2024, and NEGATIVE in 2025**; funding averaged ~8%/yr. This matches Dev's own
  cryptobot finding ("only CARRY survives") and also says why it stopped.
- "Predictability of Funding Rates" (Inan, SSRN 5576424, 2025): funding is
  forecastable with simple autoregressive models, but "the stability of funding rates
  is evolving over time" — predictability comes and goes.
- Not found yet: a peer-reviewed cross-sectional test of long/short account ratios or
  OI changes as predictors. Our `positioning` table (172 coins, 41 days, growing daily)
  is enough to test that ourselves once the base signal exists.

## Mapping: what the papers use vs what `store.db` already has

| Paper input | We have it? | Where |
|---|---|---|
| RSI, stoch K/D, stoch-RSI, CCI | yes | `feat_osc`: rsi_14, stoch_k, stoch_d, stoch_rsi, cci_20 |
| SMA 5/10/20/50/100/200 ÷ price | yes (raw SMAs; divide by close at use) | `feat_trend`: sma_* ; SMA 3 missing |
| MACD as % of fast EMA, MACD − signal | yes (raw; scale at use) | `feat_trend`: macd, macd_signal, ema_12 |
| volume SMAs 3…200 ÷ current volume | partly | `feat_vol_flow`: vol_sma_20 only; others are one rolling mean each from `ohlcv.v` |
| PVO, Chaikin money flow | CMF yes, PVO no | `feat_vol_flow`: cmf; PVO = two EMAs of volume |
| Bollinger low/mid/high ÷ price, width | yes | `feat_bands`: bb_lower/mid/upper (scale at use), bb_width |
| realised vol, VaR, max/min daily ret, skew, kurt | yes | `feat_volat`, `feat_risk`: rv_*, var_95, realized_skew/kurt; max/min = 1 rolling op |
| idiosyncratic vol, CAPM alpha/beta | buildable | needs a market series: equal-weight or BTC from `ohlcv` |
| 90-day-high distance | yes | `feat_trend`: donchian_hi (÷ price) |
| momentum 7/13/22/31, intermediate | yes | `feat_ret`: r_7d, r_14d, r_30d, mom_7d_skip1, mom_30d_skip1 |
| Amihud illiquidity, turnover, size | partly | illiq = |ret|/dollar-vol from `ohlcv`; size needs market cap — NOT in store |
| nominal price | yes | `ohlcv.c` |
| on-chain addresses | no | (paper says they barely matter) |
| **funding, OI, crowd positioning, cross-venue spread/basis, unlocks, news** | **yes, and the papers don't have them** | `perp_state`, `positioning`, `cv_features`, `unlocks.db`, `document` |

Hourly bars: the papers are daily/weekly. Ours can build every indicator at the
daily close AND at intraday points — more observations per coin, an option they never
had.

## What "test it properly" means (the papers' own standard)
- **Rolling window, refit every week, forecast only the next week** (CTREND uses 52
  weeks). Nothing from the future ever enters a fit. This is walk-forward; it is the
  same principle as the "NO LOOK-AHEAD" rule in `compute.py`.
- **Ranks in [−0.5, 0.5] per week**, never raw values.
- **Value-weight or liquidity-screen** so tiny coins don't drive the result — for us:
  measured spread / credible volume from `cv_features`.
- **Costs from measured spreads per coin** — we already have that machinery
  (`validate_reversal.py`: fee + half-spread on every unit traded, both ways).
- **Report the number of designs tried** and how many would pass by luck.
- **Year-by-year**, because the carry paper shows crypto edges can go from Sharpe 6 to
  negative in one year.

## Proposed first build (for Dev to approve, not started)

**CTREND on the Hyperliquid universe.** Reason: it is the one result that (a) is
peer-reviewed in a top journal, (b) survives costs by a 20× margin at our fee level,
(c) is proven in the largest/most liquid coins, (d) uses inputs we already compute,
(e) is a SET chosen by the data every week — exactly what Dev asked for.

Steps: weekly closes for 172 coins from `ohlcv` (6.7 years = ~350 weeks; CTREND needs
52 to start, leaving ~300 weeks of out-of-sample forecasts) → the 28 indicators from
`feat_*` (add SMA-3, volume SMAs, PVO — three small rolling ops) → weekly ranks →
per-indicator rolling regressions → positive-weight elastic net → averaged forecast →
quintile long/short, liquidity-screened, costed with measured spreads → year-by-year
table. Then, and only then, add what the papers lack (positioning, funding, spread,
unlocks) as extra inputs to the same machine and see if the elastic net keeps them.

Expected honest outcome: their +3.87%/week will NOT reproduce on 172 liquid perps
2020–2026 — their 10%-largest result (+2.51%) and their post-2022 blind spot both say
to expect less. Anything net-positive on taker fees in most years would already be
more than any single feature has ever shown here.

## Sources
- Fieberg et al., "A Trend Factor for the Cross Section of Cryptocurrency Returns",
  JFQA 2025 — https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/trend-factor-for-the-cross-section-of-cryptocurrency-returns/4C1509ACBA33D5DCAF0AC24379148178
  (open PDF: https://unipub.lib.uni-corvinus.hu/11621/1/a-trend-factor-for-the-cross-section-of-cryptocurrency-returns.pdf)
- Cakici et al., "Machine Learning and the Cross-Section of Cryptocurrency Returns",
  IRFA 2024 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4295427
  (open PDF: https://affi2023.eventsadmin.com/Papers/ViewContribution?cid=8390&h=A0CBBA4C296557EB2205D3ECCD9DBD7F)
- "Predicting cryptocurrency returns with machine learning: high-dimensional factor
  modeling", Pacific-Basin Finance Journal 2025/26 (abstract only) —
  https://www.sciencedirect.com/science/article/abs/pii/S0927538X25003701
- "Cryptocurrency as an Investable Asset Class: Coming of Age", arXiv 2510.14435 —
  https://arxiv.org/pdf/2510.14435
- Inan, "Predictability of Funding Rates", SSRN 5576424 —
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5576424
Extracted paper text is in `scratchpad/ctrend.txt` and `scratchpad/cakici_ml_crypto.txt`.
