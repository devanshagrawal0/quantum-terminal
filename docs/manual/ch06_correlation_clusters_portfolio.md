# Chapter 6 — Correlation, clusters and the book: how many bets do you really have?

A book of ten trades can be ten bets or one bet. This chapter is how to tell, what the
correlation matrix and the clusters are for, and the book rules the desk enforces because
of it. Numbers marked **[measured in our store]** are ours (`docs/MEASURED_LINKS_2026-09-16.md`,
`sim/xsec.py`). Formulas are standard portfolio arithmetic; the engine computes them — you
read the result.

## 1. What it is

- **Pairwise correlation** — how much two coins move together, −1 to +1, over a window
  (we use 30 and 90 days, Ledoit–Wolf shrunk so a 172×172 matrix from ~90 days is not
  garbage [source: Ledoit & Wolf 2004, "Honey, I Shrunk the Sample Covariance Matrix",
  J. Portfolio Management 30(4); cited in `D:\crypto trading\quant project\06-risk-portfolio-backtesting\01-portfolio-theory-optimization.md`]).
- **Raw vs residual correlation** — raw correlation is mostly BTC (everyone shares it).
  Residual correlation is what is left after removing each coin's beta × BTC: it shows which
  coins share a *story* (sector, ecosystem, listing wave). The clusters are built on residual
  correlation, so "same cluster" means "same story", not "both follow BTC".
- **Cluster** — a group of coins whose residuals move together (Ward linkage, 8 groups,
  refreshed monthly **[our build]**). A cluster is one bet.
- **Heatmap** — the whole matrix drawn as colours. It shows *structure* (blocks of coins
  that move together, coins that move with nothing) that a list of betas cannot show: beta
  is each coin against one benchmark; the heatmap is every coin against every other.
- **Correlation break** — a coin's 30-day correlation to BTC (or to its cluster) dropping
  well below its 90-day level: it is "trading idiosyncratically" — its own news is in charge.
- **Net vs gross exposure** — net = longs − shorts (beta-weighted dollars); gross = longs +
  shorts. Net/gross = how one-directional the book is.

## 2. Why it matters (the economics)

Information ratio ≈ skill × √(number of independent bets) [source:
`02-strategies/08-portfolio-construction-for-strategies.md` in the quant library]. Ten
correlated longs give you the skill of one bet with the variance of ten. Correlation is also
the thing that changes fastest when you need it least: **[measured in our store]** average
pairwise correlation is **0.38** on calm days and **0.76** on the top-10% BTC-move days;
the first principal component explains **54%** of variance over the year. A book that looks
diversified on the average day is one bet on the day it matters.

Effective number of bets for n equal positions with average correlation ρ:
**n_eff ≈ n / (1 + (n − 1)ρ)**.
| n longs | ρ = 0.38 (calm) | ρ = 0.76 (shock) |
|---|---|---|
| 2 | 1.4 | 1.1 |
| 5 | 2.0 | 1.2 |
| 10 | 2.2 | 1.3 |
Ten alt longs are ~2 bets on a calm day and ~1.3 on a shock day. Adding the 6th–10th long
adds almost no breadth, only exposure.

Clusters are unstable in crypto: **[measured in our build]** month-to-month Jaccard
stability of our 8 clusters is **0.17–0.31** (a third or less of pairs stay together). Read
"same cluster" as "same story *this month*", and re-check on the cluster refresh.

## 3. Reading rules

### 3a. Two positions
| residual correlation | bets | what to do |
|---|---|---|
| > 0.7 | ~1 | it is one trade: size the pair as one (each ≈ half), or pick the better one |
| 0.3–0.7 | 1–2 | allowed; count as 1.5 for the book |
| < 0.3 | ~2 | genuinely separate bets |
| < 0 | > 2 | a natural hedge; both can be full size |

### 3b. The book
| check (the desk computes it) | rule **[our desk]** | why |
|---|---|---|
| positions per cluster | ≤ 2 | a cluster is one story |
| net beta dollars | ≤ 50% of risk capital | the book must survive a BTC shock |
| net / gross | with 4+ positions, ≤ 60% | the book may lean; it may not be one bet |
| 3σ BTC stress loss (stressed beta 1.4 for every alt) | ≤ 10% of risk capital | crash correlation ~0.76: assume everything falls together |
| the same side, the same coin, after a loss within 7 days | needs p ≥ 0.65 | the outside view first |

### 3c. What reopens room in a full book
- a **short** (any beta) or a **hedge leg** lowers net without lowering gross;
- a **low-beta / low-R² long** (own-story coin) adds little net beta;
- closing one of the two in a full cluster.
The desk states the room in words ("room: 0 more beta-1 longs; shorts or beta ≤ 0.2 longs
fit"); copy it, do not compute it.

### 3d. Reading the heatmap
| what you see | reading |
|---|---|
| a dark block of coins | a sector/cluster: one bet; trade the best one, hedge with the worst one |
| a row that is pale everywhere | an own-story coin (low correlation to all): a true diversifier, and BTC hedges do nothing for it |
| the whole map darkens vs last month | correlation regime rising (stress building); cut breadth, it is fake |
| the stressed map vs the all-days map | the stressed one is the truth for stops and the stress test |

### 3e. Idiosyncratic this week?
Measure it as **R² change**, not raw correlation alone: 7-day R² to BTC well below the
90-day R² (and residual vol up) = the coin's own news is in charge. Consequences:
- a thesis about the coin's story can be given **more time** (BTC noise is not what will
  stop it out) — but only if the stop is set on the *own* move, which is larger now;
- a BTC hedge is pointless while it lasts;
- when the 7-day R² climbs back toward the 90-day level the story is over: re-check the trade.

## 4. Worked example

Book: long ETH ($100, β 1.2), long SOL ($100, β 1.2), long AVAX ($100, β 1.3), all in the
"majors" cluster (2 allowed) — the desk already rejected AVAX for the cluster cap. Suppose
ETH + SOL are on and the strategist proposes long DOGE (β 1.3) and long KAITO (β 0.62, R² 0.03).
- net beta $ = 120 + 120 = 240; gross = 240; net/gross = 100%.
- + DOGE long: net 370 / gross 370 = 100% with 3 positions → allowed (rule starts at 4),
  but n_eff at ρ 0.38 ≈ 1.8 — you now have under two bets for three positions.
- + KAITO long (4th): net 432 / gross 432 = 100% ≥ 60% → **rejected** by the net/gross rule
  even though KAITO barely follows BTC — because the *book* is one-way. Fix: add a short
  (e.g. short the Q5 crowded-long coin as a hedge, or a BTC hedge leg $120), then KAITO fits.
- Stress: 3σ BTC ≈ 3 × ~3% = ~9%; at stressed β 1.4, four $100 longs lose ≈ 4 × 12.6 =
  **$50** on a shock day = 2.5% of the $2,000 risk capital → under the 10% cap; the net/gross
  rule, not the stress cap, is what binds here.

## 5. Common misreads

1. **"0.85 residual correlation = two distinct bets."** It is ~1.1 bets; size the pair as one.
2. **Diversifying across alts.** On a shock day they are one trade (ρ ≈ 0.76 **[measured]**);
   only shorts, hedges and own-story coins diversify.
3. **Measuring "idiosyncratic" with raw correlation only.** Use the 7-day vs 90-day R² and
   residual vol; a low correlation over 5 noisy days means little.
4. **Trusting last month's clusters.** Stability 0.17–0.31 **[measured]**; re-read the
   cluster at every refresh, and treat two coins that just listed together as one story
   regardless of the matrix.
5. **Treating the all-days heatmap as the risk picture.** Stops and the stress test use the
   stressed matrix; the all-days map is for finding stories, not for sizing.
6. **Adding a 6th–10th long for "diversification".** n_eff barely moves past 2; you add
   exposure, not breadth.
7. **Hedging an own-story coin with BTC.** R² 0.03 → the hedge removes ~3% of variance and
   costs fees + funding.

## 6. Sources
- Our store and build: `docs/MEASURED_LINKS_2026-09-16.md` §1–2; `sim/xsec.py` (Ledoit–Wolf, Ward/8 clusters, Jaccard stability); `sim/risk.py` (book rules).
- Ledoit & Wolf (2004), "Honey, I Shrunk the Sample Covariance Matrix", J. Portfolio Management 30(4) 110–119 — via `D:\crypto trading\quant project\06-risk-portfolio-backtesting\01-portfolio-theory-optimization.md`.
- Information ratio ≈ IC × √breadth (Grinold's fundamental law) — via `D:\crypto trading\quant project\02-strategies\08-portfolio-construction-for-strategies.md`.
- Alt–BTC correlation rising in drawdowns (0.19 → 0.57) — https://gulfnews.com/your-money/cryptocurrency/beating-bitcoin-requires-alt-coin-traders-to-mind-correlations-1.2174493
- Beta hedges reduce variance for only ~17% of the crypto universe — https://jfin-swufe.springeropen.com/articles/10.1186/s40854-025-00777-w
