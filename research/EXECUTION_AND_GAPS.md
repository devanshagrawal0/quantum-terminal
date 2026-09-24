# EXECUTION & THE REMAINING GAPS

**Why this doc exists.** After reading all four prior research docs (`CROSS_VENUE_FEATURES`, `NEWS_IMPACT`, `HOW_PROS_TRADE`, `SOURCES`) plus `MARKET_MECHANICS`, five things are named as critical in those docs and **never actually specified anywhere**:

1. **Execution** — every doc says "slippage eats the edge" and calls the depth gate "the single highest-ROI engineering task", then stops. Nothing covers *how to get filled well*.
2. **Regime detection** — "everything is regime-conditional" appears in every doc. The *method* appears in none.
3. **Options / vol surface** — flagged as a gap; zero coverage.
4. **Position sizing at the portfolio level** — partial (`CROSS_VENUE §5`), missing Kelly/drawdown control.
5. **Event-study mechanics** — `NEWS_IMPACT` lists 15 hypotheses to test but never says how to run the test.

Evidence tags: `[M]` measured/cited with source · `[P]` practitioner practice · `[I]` my inference.

---

# 1. EXECUTION — and a Hyperliquid-specific finding that changes the default

## 1.1 The headline: on Hyperliquid, being VISIBLE is cheaper than hiding

There is a 2026 paper studying **our exact venue** — Barone & Lillo, *Trading in the Sunshine or in the Shade: Market Impact and Adverse Selection on Hyperliquid*. They reconstructed **4.3 million hidden metaorders** vs **465,000 visible native TWAP executions** from address-level data (which is possible precisely because HL exposes wallets — the same transparency I verified earlier via `recentTrades.users`).

**Measured results `[M]`:**

| Quantity | Finding |
|---|---|
| Temporary impact at completion | Native visible TWAPs ≈ **8.9 bps LOWER** than comparable hidden metaorders (at median vol) |
| Permanent impact | Visible leaves ≈ **5.4 bps less** permanent displacement |
| Regression coefficient | θ̂ = −0.0177 (SE 0.0010) — robust to entry conditions and pre-trends |
| **Impact scaling exponent** | **β̂ = 0.303 ± 0.002** for native TWAPs — **not** the classic 0.5 square-root |
| Impact elasticity split | ≈ **0.31 to duration**, ≈ **0.12 to participation rate** |
| Adverse-selection penalty | Hidden orders trading alongside **same-side visible TWAP flow** pay **+8.4 to +9.2 bps** per unit dominance (≈0.84–0.92 bps per +10pp of visible same-side flow) |
| Book response to a visible TWAP | Depth **+$4,200** within 5 spreads; imbalance tilts +0.022 toward the absorbing side; $10k sweep cost falls 0.025 bps; **inside spread widens 0.28 bps** |
| Entry-timing asymmetry | Visible orders benefit from trend-following entry (**+18.2 bps** pre-order); hidden orders take a contrarian-entry penalty (**−7.0 bps**) |

**Metaorder size distribution `[M]`:** median notional **$8,500** (hidden) / **$9,100** (visible); 95th percentile $256k (hidden) / $496k (visible). Median child-order count 16 (hidden) vs 30 (visible). Median participation rate 3.4% (hidden) vs 0.45% (visible).

**The mechanism:** announcing intent *selects for uninformed flow*. Market makers infer you're not toxic, so they quote against you instead of fading you — and the adverse-selection cost gets pushed onto the traders who *didn't* announce.

### What this actually means for us `[I]`

**Default execution on Hyperliquid should be the native TWAP order, not a hand-rolled hidden splitter.** That is the opposite of the standard "hide your intent" instinct, and it is measured on our own venue.

**But the far more important number is the size distribution.** Median metaorder = **$8,500**. The whole account is **~$90**. We are **~100× below the median metaorder** and ~3,000× below the 95th percentile.

> **Therefore: market impact is essentially irrelevant to us. Our entire execution cost is SPREAD + FEES + FUNDING.**

This kills a lot of theory as *not applicable at our size*: Almgren-Chriss trajectories, participation-rate optimisation, iceberg splitting, impact-minimising schedules. All of it solves a problem we do not have. **Optimising execution schedules would be pure wasted effort at $90.** The things that *do* matter at our size: whether we cross the spread, what the spread is, and what funding we pay while holding.

This is the single most useful reframe in this document, and it only appeared by looking up the size distribution rather than assuming the textbook problem applies.

## 1.2 The maker-vs-taker trap

The intuition is "post limit orders, earn the spread instead of paying it." The research says it is not that simple `[M]`:

- There is a **negative correlation between maker fill likelihood and post-fill returns**. Your passive order fills *precisely when it is about to be wrong* — that's adverse selection, and it's the whole reason spreads exist.
- **Queue position drives post-fill drift**; orders at the back of the queue suffer adverse immediate price movement.
- Fill probability depends jointly on queue position, displayed depth, volatility, imbalance, and order size.
- Blunt conclusion from the literature: *"for predictive signals, the information advantage is most effectively monetized through immediate liquidity taking rather than passive provision."* `[M]`
- Viable maker strategies therefore tend to require **counter-trading the prevailing book imbalance** — i.e. deliberately being contrarian to flow.

**What this means for us `[I]`:** "just post and save the spread" is a real strategy but it is a *market-making* strategy with its own edge requirement, not a free cost saving bolted onto a directional signal. If we have a genuine short-horizon edge, crossing may be correct. If we post, we must expect to be filled on the bad side and price that in. **Never model a passive fill as "mid price with no cost."**

## 1.3 Cost measurement — TCA

Without measuring, none of the above is actionable `[M]`/`[P]`:

- **Arrival price** is the primary benchmark — the price at the moment the order was sent. Slippage vs arrival captures *total* cost including our own impact. This is the one to start with.
- **VWAP benchmark** answers a different question: did we participate well *during* the order. Secondary for us.
- **Implementation shortfall** = decision price → final execution price, the full economic cost.
- Typical crypto arrival slippage expectation cited: **−10 to −15 bps** `[M]` (institutional size; ours should be far better given §1.1).
- Crypto-specific additions traditional TCA misses: gas as a variable cost, and MEV / transaction-ordering risk on public chains.

**Required for us `[I]`:** log for every fill — decision time & price, order-sent time & price (arrival), each fill price/size/time, fees, and the funding accrued over the hold. Without arrival price stored at decision time, TCA is impossible retroactively. `NEWS_IMPACT` H12 called the depth-gate the highest-ROI task; this logging is its prerequisite.

## 1.4 The classic algorithms — recorded, but flagged as not-for-us

For completeness, since they're the canon `[M]`:

- **TWAP** — even slices over time. Simple, predictable, signals nothing about urgency.
- **VWAP** — slice proportional to expected volume profile. Under an Almgren-Chriss model with an explicit volume process, **VWAP is provably optimal for a risk-neutral trader**.
- **POV** — fixed % of realised volume; adapts to actual liquidity.
- **Implementation Shortfall / Almgren-Chriss** — minimise E[cost] + λ·Var[cost], trading off market impact against price risk over the horizon. Produces a smooth front-loaded schedule; the "efficient frontier" is impact vs timing risk.
- **Order splitting + liquidity replenishment are jointly what produces the square-root law** `[M]` — impact is a sum of small kicks each partially absorbed by refilling market makers.
- Randomise both child sizes and inter-child timing to reduce signalling `[P]`.

**Verdict for us `[I]`: not applicable at $90 notional.** Revisit only if account size approaches the ~$8.5k median metaorder scale, where impact starts to exist.

---

# 2. REGIME DETECTION — the method nobody specified

Every doc asserts regime-dependence (`MARKET_MECHANICS` §3/§11, `newsystem.md` §11.5, `CROSS_VENUE` §2.5 on flipping causality, `NEWS_IMPACT` §3 on correlation regimes). Here is the actual toolkit `[M]`:

| Method | What it does | Trade-offs |
|---|---|---|
| **Gaussian HMM** | Models unobservable states with probabilistic transitions; each state has its own return/vol distribution. The standard tool. | Must pre-specify state count; can fit spurious states; label-switching between refits |
| **Gaussian Mixture Models** | Clusters observations into regimes without a transition model | No temporal persistence — regimes flicker |
| **k-means / agglomerative clustering** | Unsupervised regime labelling on feature vectors | Same flicker problem; no probabilistic output |
| **PELT (Pruned Exact Linear Time)** | Change-point detection — finds *when* the regime broke | Detects breaks retrospectively; lag before a break is confirmed |
| **Binary segmentation / dynamic programming** | Alternative change-point search | Cheaper than PELT, less exact |
| **ARMA-GARCH + ML hybrids / heteroskedastic networks** | Model the volatility process directly, with regime switching on top | More machinery, more overfitting surface |

**Standard practical recipe `[M]`:** fit a Gaussian HMM on a feature set (returns + realised vol, often + volume), extract the hidden states, then *characterise* each state post-hoc by its mean return and mean volatility, and only then name them ("strong bull", "high-vol bear", etc.). **The naming is a post-hoc interpretation, not an input.**

**Cautions `[I]`:**
- Regimes must be **inferred causally** — using only data up to time *t*. An HMM fitted on the full sample and then used to label history is a textbook look-ahead leak (`newsystem.md` §12.4 in a different costume).
- The **number of states is a hyperparameter** and a multiple-testing surface. 2–4 states is the honest range; more is fitting noise.
- Regime labels are only useful if they **change what we do** — sizing, which signals are active, whether to trade at all. A regime label that doesn't gate anything is decoration.
- For us, the cheapest honest version is a small number of observable, pre-registered conditions (realised vol tercile, funding sign/extremity, OI level, BTC trend) rather than a latent-state model. **Start there; graduate to an HMM only if the simple version demonstrably fails.**

---

# 3. OPTIONS / VOL SURFACE — completely absent from every prior doc

We collect only the DVOL index. Deribit's free public API exposes far more, and `CROSS_VENUE` §2.4 explicitly flagged this as under-used ("prioritise IV−RV over venue disagreement").

**The metrics that matter `[M]`:**

- **25-delta risk reversal (RR)** = IV(25Δ call) − IV(25Δ put). Measures willingness to pay for upside vs downside protection.
- **Skew** = (IV 25Δ put − IV 25Δ call) / ATM IV. Positive skew = higher demand for puts = defensive positioning; negative = call demand.
- **Term structure** — e.g. the 30D/7D implied-vol ratio. Recovering sustainably above 1.00 is read as normalisation; inversion (front > back) signals acute near-term stress.
- **Variance risk premium** = IV − subsequently realised vol. Persistently negative on average (see `MARKET_MECHANICS` §4) — the structural payment for bearing crash risk.
- **Dealer gamma / vanna / charm** (`MARKET_MECHANICS` §7) — positive gamma suppresses vol and pins price near heavy strikes; negative gamma amplifies. Vanna drives "vol-reset" rallies when IV falls.

Practitioner claim worth testing, not assuming `[P]`: *"the options market tends to flash those signals before spot does."*

**Concrete numbers seen `[M]`:** BTC 7-day 25Δ put-call skew moved from −11% to 0% over July 2026 with BTC above $66k — i.e. the metric has a usable, interpretable range.

**What we should do `[I]`:** wire Deribit's free `get_instruments` / `get_book_summary_by_currency` / `ticker`, and store per-day: ATM IV by tenor, 25Δ RR, skew, term-structure ratio, and total open interest by strike. Then the first honest test is `CROSS_VENUE`'s: does **IV − RV** add predictive power over lagged realised vol? Only BTC/ETH plus a handful of alts have real options liquidity, so this is a **market-level regime input**, not a cross-sectional signal — which means low statistical power and it should be used as a conditioner, not a trigger.

---

# 4. POSITION SIZING — Kelly and its correction

`CROSS_VENUE` §5.3 covers residual-vol sizing well but never addresses how much total risk to take.

**Kelly `[M]`:** f* = (bp − q)/b maximises long-run geometric growth.

**The correction that matters `[M]`:**
- **Full Kelly produces roughly a 1-in-3 chance of a 50% drawdown**, even with genuinely positive expectancy (Gehm 1983).
- **Half-Kelly cuts volatility ~in half while giving up only ~25% of growth.** That is a very favourable trade.
- Ed Thorp — who literally invented the practical application — **used fractional Kelly, never full**, even with robust statistics behind the edge.
- Fixed-fractional sizing empirically produces lower max drawdown and lower return volatility (Balsara 1992).
- Practical guidance found: **treat quarter-Kelly as the working maximum**, scaling up only with a larger, statistically stable sample.

**The decisive point `[I]`:** Kelly assumes you *know* your edge. We don't — we estimate it, with error, on short samples (`CROSS_VENUE` §4.3: IC of 0.03 is not distinguishable from zero on one year). Kelly sizing on an **overestimated** edge overbets superlinearly. Given our edge estimates have standard errors comparable to the estimates themselves, **quarter-Kelly is an upper bound, not a target.**

---

# 5. EVENT STUDY MECHANICS — how to actually run the tests

`NEWS_IMPACT` lists H1–H15 but never specifies the procedure. The standard methodology `[M]`:

1. **Define the event** and its precise timestamp (for us: *our receipt* timestamp — `NEWS_IMPACT` trap #7).
2. **Define the selection criteria** for which assets enter the study.
3. **Estimate the normal-return model** over a pre-event **estimation window**, typically the market model: regress asset return on market return (for us: on BTC).
4. **Abnormal return** AR = actual − expected on each day of the **event window**.
5. **CAR** = sum of ARs across the event window.
6. **Test**: t-test using the standard deviation of residuals from the estimation period.

**Window guidance from meta-research over 400 event studies `[M]`:**
- Estimation windows range 30–750 days; results are **insensitive to length as long as it exceeds ~100 days**. Rule of thumb: estimation window − K > 100.
- Event windows are typically 1–11 days, symmetric around the event; **5 days is the most common choice (76.3% of studies)**.

**Corrections we must not skip `[M]`/`[I]`:**
- **Clustered/overlapping events** — when many assets share one event, they are not independent. The **Kolari-Pynnonen adjustment** rescales by cross-correlation so clustered observations count as the smaller effective N they really are. Without it, significance is wildly overstated. (Same trap as `newsystem.md` §11.1.)
- Report **median and 25/75 percentiles, not just the mean** — `NEWS_IMPACT` makes this point with the Coinbase-effect range of −32% to +645%. Means lie on fat-tailed event distributions.
- Use **AR, not raw return** (subtract BTC beta), or you're measuring the market.

---

# 6. WHAT IS *STILL* MISSING AFTER THIS DOC

Being explicit, so this isn't mistaken for complete coverage:

1. **The full feature catalogue.** Dev asked about "500+" features. `CROSS_VENUE` has ~15 ranked plus families; `MARKET_MECHANICS` has the microstructure primitives; this doc adds options-derived. A genuinely exhaustive enumeration (trend/momentum/volatility/volume/microstructure/options/on-chain/cross-asset) does **not** exist yet. Note: standard libraries (TA-Lib, TTR — 50+ indicators) cover the technical family, but **`CROSS_VENUE` §6.6's warning applies hard** — 1,200 candidate features on ~365 effective dates gives ~60 false positives at α=0.05. **Enumerating 500 features without a false-discovery budget would actively make the system worse.** Breadth is not the constraint; *selection discipline* is.
2. **On-chain depth.** The HL whale-tracking channel I verified (`recentTrades.users` → `clearinghouseState` per wallet) is unexplored. Given the Barone-Lillo paper reconstructed 4.3M metaorders from exactly this data, **it is demonstrably rich enough for serious analysis.**
3. **Backtest engine specifics** — purged/embargoed CV implementation, triple-barrier labelling, deflated Sharpe computation. Methods named in `newsystem.md` §2; not implemented or specified.
4. **Portfolio-level margin & liquidation modelling** — `CROSS_VENUE` §5.7 flags that the binding constraint is portfolio margin under correlated moves, and it is unmodelled.
5. **The two agent research tracks** (world-context 29 items; driver taxonomy) — still running, results unknown.

---

# 7. THE HONEST TOP-LINE FROM ALL OF TODAY'S READING

1. **At $90, execution theory is irrelevant; spread and funding are everything.** The median HL metaorder is $8,500. Optimising trajectories would be effort spent on a problem we don't have.
2. **On Hyperliquid specifically, visible native TWAP beats hidden execution by ~8.9 bps** — measured, on our venue, contradicting the standard hide-your-intent instinct.
3. **Passive fills are not free.** Fill likelihood correlates *negatively* with post-fill returns.
4. **Funding is a bigger cost line than fees at our horizon** — `CROSS_VENUE` §1.6: 21 bps over a 7-day hold vs 9 bps round-trip fees. It must be in the cost model before it's in the alpha model.
5. **The binding constraint on this whole project is statistical, not informational.** `CROSS_VENUE` §4.3 (IC 0.03 indistinguishable from zero on 1 year), Harvey-Liu-Zhu (**t > 3.0**, not 2.0), McLean-Pontiff (**−58% post-publication**), and the ~10 days of stored history we actually have all say the same thing. **More features and more sources will not fix it. Only more time, and ruthless selection, will.**

---

## Sources

- **Hyperliquid execution (the key paper):** Barone & Lillo, *Trading in the Sunshine or in the Shade: Market Impact and Adverse Selection on Hyperliquid* — [arXiv abs](https://arxiv.org/abs/2606.15715) · [HTML](https://arxiv.org/html/2606.15715v1)
- Maker/taker & adverse selection: [The Market Maker's Dilemma: Fill Probability vs Post-Fill Returns](https://arxiv.org/pdf/2502.18625) · [Limit Order Strategic Placement with Adverse Selection Risk](https://arxiv.org/pdf/1610.00261) · [Optimal Execution with Passive Market Impact](https://arxiv.org/html/2607.28323) · [Explainable Patterns in Cryptocurrency Microstructure](https://arxiv.org/html/2602.00776v1)
- Execution algorithms: [Almgren-Chriss framework](https://medium.com/@ibrahimlanre1890/trading-execution-algorithms-the-almgren-chriss-framework-56717dd650ce) · [VWAP Execution as an Optimal Strategy](https://arxiv.org/pdf/1408.6118) · [Optimal VWAP under transient price impact](https://arxiv.org/pdf/1901.02327) · [Order splitting & liquidity replenishment → square-root law](https://arxiv.org/pdf/2607.04280) · [Key problems in algorithmic trading](https://arxiv.org/pdf/2006.05515)
- TCA: [Slippage, Benchmarks and Beyond — TCA in crypto](https://medium.com/@anboto_labs/slippage-benchmarks-and-beyond-transaction-cost-analysis-tca-in-crypto-trading-2f0b0186980e) · [Talos — TCA benchmarks and slippage](https://www.talos.com/insights/execution-insights-through-transaction-cost-analysis-tca-benchmarks-and-slippage) · [CoinRoutes — TCA for digital assets](https://coinroutes.com/academy/transaction-cost-analysis-tca-digital-assets/)
- Regime detection: [Market Regime Detection using HMMs (QuantStart)](https://www.quantstart.com/articles/market-regime-detection-using-hidden-markov-models-in-qstrader/) · [Market Regime Identification Using HMM (SSRN)](https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID3406068_code3576909.pdf?abstractid=3406068) · [Regime-Switching Factor Investing with HMMs](https://www.mdpi.com/1911-8074/13/12/311) · [Statistical & ML regime detection (LSEG)](https://developers.lseg.com/en/article-catalog/article/market-regime-detection)
- Options/vol: [Anchorage — skew, wings and term structure](https://www.anchorage.com/research/the-anchorage-digital-prime-signal-what-skew-wings-and-the-term-structure-are-telling-us-about-bitcoin-and-its-adjacent-markets) · [Deribit Insights analytics reports](https://insights.deribit.com/industry/crypto-derivatives-analytics-report-week-30-2026/) · [Laevitas skew/butterfly](https://app.laevitas.ch/assets/options/skew-bf/btc/deribit)
- Sizing: [Kelly vs fixed fractional](https://medium.com/@tmapendembe_28659/kelly-criterion-vs-fixed-fractional-which-risk-model-maximizes-long-term-growth-972ecb606e6c) · [Kelly position sizing — overbetting/underbetting](https://astuteinvestorscalculus.com/kelly-criterion-position-sizing/) · [Sizing the Risk: Kelly, VIX and hybrid approaches](https://arxiv.org/html/2508.16598v1)
- Event studies: [Event Study Methodology step-by-step](https://www.eventstudytools.com/introduction-event-study-methodology) · [Event study application blueprint](https://www.eventstudytools.com/event-study-application-blueprint) · [A Note on Testing AR and CAR (UZH WP425)](https://www.econ.uzh.ch/apps/workingpapers/wp/econwp425.pdf) · [Empirical methods: event studies (Ødegaard)](https://ba-odegaard.no/teach/notes/event_studies/event_studies_lecture.pdf) · [Event study significance tests / Kolari-Pynnonen](https://www.eventstudytools.com/significance-tests)
