# Measured on our own data — 2026-09-16
Script: `scratchpad/measure_xsec.py` → `scratchpad/measure_xsec.json`. Daily closes for 172 Hyperliquid coins; funding daily 2025-08-13 → 2026-09-15. Bars with |move| > 300% dropped. These are the first numbers the links engine and the cross-sectional layer will carry; they are measurements, not a trading claim.

## 1. Beta, idiosyncratic share (90-day window ending today, 171 coins)
- Median beta to BTC **1.10** (10th–90th percentile 0.68 – 1.50).
- Median R² to BTC **0.30**: for the typical alt, BTC explains 30% of daily moves; 70% is its own story.
- **48% of coins have R² < 0.3** (their own story dominates); **only 4% have R² > 0.6** (ETH 0.78, XRP 0.73, BNB 0.69, SOL 0.67, DOGE 0.66).
- Median idiosyncratic vol share (residual vol ÷ total vol) **0.84**.
- Most idiosyncratic today: ACE (β 0.14, R² 0.00, **idio vol 17.6%/day**), SKR (13.7%/day), HMSTR (10.8%/day), KAITO (β 0.62, R² 0.03, 7.3%/day), DYDX, TNSR, BABY, MANTA, STABLE, WLFI. → The ACE and KAITO trades in the small test were pure idiosyncratic bets; nothing about BTC could have helped or hurt them. A 5% stop on ACE was 0.3 of one daily residual move.

## 2. Correlation: calm vs stress (last 365 days, coins with ≥90% coverage)
- Average pairwise correlation, all days **0.50**; calm days **0.38**; **top-10% BTC-move days (37 days) 0.76**.
- First principal component explains **54%** of variance across the year.
→ On a normal day the market is half one trade, half many trades. On a shock day it is one trade. A correlation heatmap drawn on all days lies about crash days; the spec needs both (all-days and stressed).

## 3. BTC shock days (|BTC day| > 2.5σ of its 60-day vol; 31 days in the last 2 years)
| | BTC | ETH | high-beta alts (top quartile) | low-beta alts (bottom quartile) | next day BTC | next day high-beta alts |
|---|---|---|---|---|---|---|
| Down shocks (n=11) | −7.4% | −9.1% | −10.7% | **−10.4%** | +1.5% | +2.0% |
| Up shocks (n=20) | +8.0% | +9.4% | +10.2% | +7.1% | −1.1% | −0.3% |
→ Down shocks: ETH > BTC in magnitude, and **low-beta alts fall as much as high-beta alts** — normal-day beta does not protect in a crash (stressed beta ≈ 1.4 for everything). Up shocks: high-beta alts lead, low-beta lag. Day after: partial bounce after down shocks, partial fade after up shocks (small samples, n=11 and 20 — direction only, not a tradeable size claim).
→ This is exactly the "Fed hike → BTC down → alts more" chain, measured: on the day, the order is alts ≥ ETH > BTC, and it does not matter which alt.

## 4. Funding → forward excess return (Dev's first link; 377–383 daily cross-sections, ~27k coin-days)
Sorted each day into quintiles by that day's funding; forward excess = coin return minus the universe average.
| horizon | Q1 (most negative funding) | Q3 | Q5 (most positive) | rank-IC | t-stat of IC |
|---|---|---|---|---|---|
| 1 day | +6.0 bps | −8.0 | +7.6 | −0.002 | −0.3 |
| 3 days | +11.0 | +4.9 | +12.5 | −0.011 | −1.5 |
| 7 days | **+53.5** | +36.0 | **+29.1** | **−0.027** | **−3.8** |
→ The sign is what theory says: crowded longs (high funding) do worse over the following week, crowded shorts do better. It is statistically real at 7 days (t = −3.8 on the rank-IC over 377 days) and **small**: the Q1–Q5 spread is ~24 bps over 7 days (~3.5 bps/day), less than one round trip of costs (≈ 12–15 bps). Excess return here excludes the funding itself; a short on Q5 also *collects* the funding, which roughly doubles the edge for that leg — to be measured next with funding carry included.
→ What the strategist should be shown: "funding → 7-day excess: rank-IC −0.027 (t −3.8, n 377 days); top-vs-bottom quintile 24 bps/7d before funding carry; 1-day and 3-day: no measurable link." A chain built on funding alone at a 1–3 day horizon is `[unmeasured]` and gets its confidence capped.

## 5. What these numbers change in the build
1. `feat_cross` gets filled from data we have (beta, R², residual returns, idio vol, stressed beta on shock days) — the cross-sectional layer is a day's work of computation, not a data problem.
2. Stops and sizes must use **residual** daily vol, and in stress mode assume beta ≈ 1.4 for every alt.
3. Two correlation matrices (all-days, stressed) and the PC1 share become part of the regime read and the heatmap page.
4. Link #1 (funding → 7d) goes into the links table with its sign, size, n, t; next measurements: funding with carry, positioning (long share) → return, OI-change × price → return, unlock size → return (once the calendar has history), Fed-surprise → BTC (once FOMC dates exist).

## 4b. The same link with the funding itself counted (measured after §4)
Holding period 7 days; "carry" = funding a LONG pays over those 7 days (negative = the long is paid).
| quintile by today's funding | excess return | funding paid by a long | long net | short net |
|---|---|---|---|---|
| Q1 most negative | +53.5 bps | −47.8 (long is PAID) | **+101** | −101 |
| Q2 | +35.6 | +1.2 | +34 | −34 |
| Q3 | +36.1 | +8.4 | +28 | −28 |
| Q4 | +44.6 | +15.9 | +29 | −29 |
| Q5 most positive | +28.4 | +22.2 | +6 | −6 |
→ Read carefully: **the edge is one-sided.** Being LONG the crowded-short quintile (Q1) made +101 bps per 7 days, and most of that is the funding collected (48 bps) plus a price bounce (54 bps). SHORTING the crowded-long quintile (Q5) made **−6 bps**: the funding collected (+22) did not cover the price still drifting up (+28). The long-Q1 + short-Q5 pair is +95 bps, t = 4.05 (n ≈ 5,400 coin-days per leg), but the short leg contributes nothing — a hedge against BTC, not a source of return. Costs for the two round trips ≈ 25–30 bps. This is the hedged-carry sleeve the older cryptobot memory called the only survivor, now measured on Hyperliquid with 13 months of history; the honest version is: get paid to hold what the crowd is short, hedge the market, do not expect crowded longs to fall on schedule. Rule for the risk hat: a long on a Q5 coin pays ~22 bps/week and needs a thesis worth more than that; a short on a Q1 coin pays ~48 bps/week against it and needs a much stronger one.
