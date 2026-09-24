# NEWSYSTEM.md — Research Intelligence & Reasoning Engine

**Status:** design / discussion. Nothing here is built or validated yet.
**Author of record:** Dev + Claude (working doc, updated as we go)
**Rule for this doc:** every claim is tagged — `[PROVEN]` (evidence exists), `[HYPOTHESIS]` (plausible, unproven), `[TO-VALIDATE]` (must pass the kill-gate before it earns a dollar). Default is HYPOTHESIS.

---

## 0. What we are actually building

Not "a bot that reads news and says bullish/bearish." That is the thing everyone builds and nobody gets rich from.

We are building a **Research Intelligence Engine**: a system that continuously ingests the world (data + news + on-chain + repos + social), reasons through **cause-and-effect chains** to figure out *what each event actually does to which instruments and when*, checks whether the market has **already priced it**, confirms with live order flow, compares against its **own history of similar events**, turns the surviving theses into **convex/hedged trade structures**, and **grades its own reasoning** so it gets sharper over time.

The 24/7 brain is **not** the LLM. The 24/7 brain is the market-data + quant + ML layer. The LLM is the senior researcher we *wake up* only when something is worth deep thought.

Core principle: **asset-agnostic core, crypto-first data.** The reasoning engine works on events → entities → instruments in *any* market (Dev's best real trade was WTI **oil**, not a coin). We wire crypto data first because it's already connected, but we never hard-code a crypto-only ontology.

---

## 1. The honest edge thesis (why this can work when public repos don't)

**Why the public repos aren't printing money:** they are *infrastructure, not edge*. TradingAgents, FinRL, ai-hedge-fund etc. publish backtests with look-ahead bias, no fees, no slippage, on the most crowded markets (BTC/ETH/SPY). Add real costs and trade live and the "edge" evaporates. Dev already proved this on his own bot: pattern-mining, order-book, and basis strategies all **died under walk-forward**; only hedged **carry** survived. That lesson *is* the edge — 95% of apparent alpha is overfit noise, and the discipline to kill it is rarer than the ideas.

**Where real edge actually lives (and which are reachable for a small operator):**
- **Capacity-constrained corners** `[HYPOTHESIS]` — markets too small for funds to deploy size (new listings, small perps, HIP-3 builder markets, prediction markets). Small size is an *advantage* here.
- **Speed-of-understanding, not speed-of-wire** `[HYPOTHESIS]` — we lose the latency race forever; we can win the "read and correctly size a surprise faster/deeper than a human desk" race with LLMs.
- **Execution quality** `[PROVEN industry-wide]` — making the spread vs paying it; a mediocre signal executed well beats a great signal executed badly.
- **Survival/discipline** `[PROVEN]` — most blow-ups are risk sizing, not bad signals. Not dying compounds.
- **Cross-market structure** `[PROVEN]` — funding/basis/liquidation-cascade/divergence are mechanical, decay slower.

**The product is not a bot — it's a selection machine:** generate *many* small candidate edges, run them through a **brutal kill-gate** (walk-forward, cost-aware, overfitting-controlled), and deploy the rare survivors into corners where the edge persists, sized to survive being early.

---

## 2. What top firms actually do — and what an AI system can replicate

Researched Sep 2026. The point: copy the *transferable principles*, not the parts that need $100M and a fiber line.

| Firm | What they actually do | Replicable by us? |
|---|---|---|
| **Renaissance (Medallion)** | Portfolio-level **statistical arbitrage** taken to the limit, executed superbly. 150k–300k trades/day, holding seconds→days, capturing tiny fleeting mispricings. 66% gross/yr 1988–2018. | **Principle yes, scale no.** We can't do 300k trades/day or their execution. We *can* copy: many tiny uncorrelated edges > one big bet; ruthless statistical validation; portfolio-level netting. |
| **Two Sigma** | Science-first: ML + distributed compute over huge data to find exploitable patterns/correlations. | **Yes, in miniature.** Our ML layer (LightGBM/XGBoost on features + outcomes) is the same idea at hobby scale. |
| **Citadel Securities** | Market-making + HFT + stat-arb; profits from providing liquidity and pricing relationships. | **No on HFT/MM** (needs seats, latency, capital). Principle of *relationship pricing* is usable. |
| **Jane Street** | **Prices relationships between correlated instruments better than anyone** — profits from the *math of microstructure*, NOT direction prediction. "Precision, not prediction." | **Principle is gold.** Relative-value / pairs / cross-instrument mispricing is the most transferable idea. We can't match their speed, but slow relative-value in small markets is open. |
| **Jump** | Deep microstructure expertise in fixed income; durable advantage from owning a niche. | **Niche-ownership principle yes.** Pick a corner and know it better than anyone. |
| **Multi-manager funds (alt-data)** | Combine *many* differentiated datasets into z-scored/percentile signals; fight **alpha decay** by finding *non-crowded* data. Ensemble of many small signals. | **Directly yes.** This is our whole "many small edges + alt-data" plan. Lesson: crowded data = fast decay; hunt differentiated sources. |

**The universal method every serious quant fund uses (and we must copy):** hypothesis → transform raw data into quantified signals (z-score, percentile, composite) → test on history with **anti-overfitting controls** → combine survivors into an ensemble → size by conviction → net at portfolio level → monitor decay and retire dead signals.

**The anti-overfitting toolkit (López de Prado — this is the kill-gate):** `[PROVEN methodology]`
- **Purged + embargoed cross-validation (CPCV)** — remove train samples whose labels overlap test labels; prevents look-ahead leakage.
- **Deflated Sharpe Ratio + Probability of Backtest Overfitting (PBO)** — discount for number of trials, short series, non-normal returns. A backtested Sharpe means little until deflated.
- **Triple-barrier labeling** — label a trade by which of {take-profit, stop-loss, time-expiry} it hits first (realistic outcomes).
- **Meta-labeling** — a *second* model decides *whether to act* on a primary signal. Empirically lifts a mean-revert strategy's accuracy 17%→63% out-of-sample. This is how we bolt "should we actually take this?" onto any signal or LLM thesis.

**AI-replication summary:** we can't replicate their *speed, capital, or seats*. We CAN replicate their *scientific process, their many-small-signals ensemble, their relationship-pricing mindset, their niche ownership, and — most importantly — their statistical honesty.* The last one is where the retail crowd fails and where AI (running the López-de-Prado gate automatically on every idea) gives us leverage.

---

## 3. Architecture — the merged design

### 3.1 Tiered compute (data drives cognition, not the clock)

```
TIER 0 — deterministic, 24/7, $0 API
  collectors → feature engine → quant/ML models → anomaly detector
  (order book, trades, CVD, OI, funding, liquidations, vol, correlation,
   beta, portfolio risk, forecasts, event studies)

        │  anomaly / trigger fires
        ▼
TIER 1 — small LOCAL model (Ollama), $0 API
  alert router · event extractor · dedup/cluster · trade-memory retrieval ·
  journal · data-quality · narrator · "is this important?"

        │  only if genuinely important
        ▼
TIER 2 — cloud LLM (or big local on a GPU box), pennies per call
  deep researcher · bull/bear/skeptic · macro · causal reasoner ·
  research manager · payoff-structure finder · trade-autopsy judge
```

**Wake-on-anomaly, never wake-on-timer.** Example trigger (deterministic): `BTC OI +8% in 30m AND price −1.2% AND funding +2σ AND spot CVD negative → wake derivatives research`. Realistically 5–20 deep LLM investigations/day, not millions of calls.

> Critique to respect: those compound thresholds must be **calibrated from data**, or they fire constantly or never. Thresholds are quant parameters, not hardcoded keyword routing — legitimate, but must be tuned/validated, not guessed.

### 3.2 Most "agents" are quant engines, not LLMs

The Microstructure / Derivatives / Volatility / Relative-Value / Portfolio agents are **deterministic code with structured output**. The LLM only *interprets* their output. Cheaper, faster, and far more trustworthy. (This is FinRobot's separation of numeric computation from narration, and it's correct.)

```
MicrostructureAgent →  {bias: LONG, confidence: 0.73,
  reasons: [OFI +1.8σ, microprice +8bps, sell-sweep absorbed, spot CVD turning+]}
```

### 3.3 The Research pipeline (event → thesis)

```
RAW INFO (news API + RSS + official + on-chain + GitHub + social + prediction mkts)
   ↓  deterministic collectors (respect robots/ToS, no paywall bypass)
NORMALIZE + DEDUP  (Reuters story copied 40× = ONE event, not 41 signals)
   ↓
EVENT EXTRACTION (cheap/local LLM → strict struct: type, actors, facts,
   certainty, novelty, surprise, source_quality, affected_entities)  — NO opinion yet
   ↓
CAUSAL / KNOWLEDGE GRAPH  (transmission channels: Iran→oil→inflation→yields→risk→BTC→alts)
   every edge: {direction, strength, confidence, expected_delay, half_life, historical_support}
   ↓
IMPACT GRAPH per event  (which instruments, which path, what magnitude, what decay)
   ↓
PRICED-IN AGENT  (is it better/worse than EXPECTED? surprise vs positioning → sell-the-news detection)
   ↓
LIVE MARKET CONFIRMATION  (T+5s…T+1h reaction: return, residual vs BTC, CVD, OI, funding, book)
   ↓
EXPECTED-vs-ACTUAL DIVERGENCE  (bullish news that can't move price = bearish info, and vice-versa)
   ↓
HISTORICAL ANALOGUES  (retrieve N most-similar past events + their realized outcomes)
   ↓
EVENT STUDY BASE RATES  (deterministic stats: "token unlock >3% supply under +funding, bearish BTC → −4.2% median")
   ↓
BULL vs BEAR vs SKEPTIC  (LLM debate, but grounded in the numbers above)
   ↓
RESEARCH MANAGER → structured Trade / No-Trade thesis
   ↓
★ PAYOFF-STRUCTURE FINDER  (OUR ADD: turn thesis+uncertainty into a convex/hedged structure —
   "+3% either way," long-oil/short-airlines, carry-while-waiting)
   ↓
★ NICHE ROUTER  (OUR ADD: express the view in the least-crowded instrument where edge persists)
   ↓
HARD-RISK RUNTIME  (model proposes, code disposes: position/leverage caps, auto SL/TP,
   drawdown auto-close, cooldowns, safe-mode — your preflight.py philosophy)
```

### 3.4 What OUR ideas add on top of the pasted architecture

1. **Causal-graph edge weights must be *earned from the event studies*, not LLM-guessed.** A confident graph on made-up numbers is the #1 failure mode. **Method now specified in §11.** `[TO-VALIDATE]`
2. **Payoff engineering.** The pasted doc stops at a directional thesis. We add the stage that finds the **convex/hedged structure** — being right on thesis but wrong on timing shouldn't kill us. `[HYPOTHESIS]`
3. **Anticipatory, not just reactive.** The doc wakes *after* the headline. We pre-build **peacetime playbooks** ("if X escalates → these instruments/structures") so we're positioned *before* the break (Dev's "sentiment still greed, position before macro pressure finally breaks"). `[HYPOTHESIS]`
4. **The trade trigger is the *repricing gap*** — the distance between reasoned probability and current price — not just a "priced-in %". `[HYPOTHESIS]`
5. **Asset-agnostic core** so the same engine later ingests equities/commodities/rates with no rebuild.
6. **The kill-gate is a first-class citizen** (§2 López de Prado toolkit), run automatically on every candidate edge.

### 3.5 Information-Flow Graph (the standout novel edge)

Record *who reported an event first* and *which venue's price reacted first*:
```
Official acct 00:00:00 · Reuters +01:48 · CoinDesk +03:21 · CT +04:10 · Reddit +12:55
Binance spot reacted +00:21 · OKX +00:24 · Hyperliquid +00:29
```
Over months, learn "for listings, Binance announcements lead; for geopolitics, Reuters leads crypto media ~3 min; for project dev, GitHub releases precede social." That *is* an informational edge. `[HYPOTHESIS — high value]`

---

## 4. The learning loop (how it gets better — the part repos skip)

Every thesis is stored as a **prediction with its reasoning**: chain, branch odds, expected moves, horizon. Outcomes grade **not just PnL but whether the causal reasoning was right.**

- Per-agent, per-horizon, per-regime **accuracy, Brier score, calibration, precision@high-confidence.**
- The CIO **learns whom to trust** ("Geopolitical agent 12h BTC acc = 53%; Tokenomics 24h alt acc = 67%").
- Graph edges get **re-weighted** by realized support; bad reasoning patterns pruned; good playbooks reinforced.
- **Nightly** the mini-PC retrains local ML: direction models, P(+1% before −1%), regime (HMM/cluster), vol (GARCH/HAR/ML), relative-value, and a **meta-model** ("which strategy deserves trust now"). Zero API cost.
- Eventually (5k–50k graded examples) **LoRA fine-tune the local model** — but on *reading market state / finding contradictions / selecting tools / recognizing regimes*, NOT on "BUY BTC." Numeric ML stays responsible for forecasting; the LLM stays responsible for understanding.
- **News-impact ML:** LLM extracts the structured event; a **LightGBM/XGBoost** predicts the outcome from (event features + market state + historical similarity). LLM = understanding, ML = base-rate forecasting. Strongest when combined.

---

## 5. Cost & hardware reality (honest)

- **Dev's current laptop:** Ryzen 5 5600H, 15.4 GB RAM, **no discrete GPU** (integrated Radeon, 0.5 GB VRAM), Ollama not installed. It can run a ~7–9B model *slowly* for triage/extraction, but **cannot** run the full stack (collectors + QuestDB + Postgres + Redis + Ollama + big reasoning) 24/7. **A dedicated always-on box is a prerequisite, not a footnote.**
- **Cost is an architecture problem, not a model problem.** ~90% deterministic (no tokens). 1000:1 filtering means the expensive brain fires dozens of times/day.
- **Model tiers (principle, stay vendor-agnostic):** local small model for volume → cheap API model (DeepSeek-class, <$1/M, cached ~$0.004/M) for routine reasoning → frontier only for the rare deep leap. A **$5–20/month** AI budget is realistic if routing is disciplined. Prompt caching (0.1×) + pre-computed playbooks amortize hard.
- **"No compromise" path:** prove it on cheap APIs first (zero hardware); once it earns, buy a **used RTX 3090 24 GB box (~$700–900)** to run a 32B DeepSeek-R1 distill (≈ o1-mini reasoning) locally, unlimited, free per call. Buying hardware for something unproven would be the mistake.

---

## 6. What to steal from each repo (accurate reads)

- **TradingAgents** — take the **orchestration / multi-agent graph + tool-calling** (LangGraph). Do **not** copy its news intelligence (it's just tools→LLM→report; we go far deeper).
- **Microsoft Qlib** — full ML quant pipeline (data→factor→model→backtest→serve).
- **Microsoft RD-Agent** — the **auto propose→implement→backtest→keep-if-better loop**. This is our idea-factory.
- **FinNLP** — **ingestion patterns** (full article bodies, social, multi-source normalization).
- **FinGPT** — **training-data-creation concept** (historical info + subsequent outcome = lesson; LoRA adaptation). Build a *crypto-specific modern* dataset.
- **FinBERT** — cheap local first-pass sentiment **only**; it's 2019-era, never use its sentiment as a signal.
- **FinMem** — **layered memory** (short/medium/long + important events).
- **FinRobot** — **numeric-computation vs LLM-narration separation** + orchestrator/bull/bear/judge. Best architectural match.
- **OpenBB** — **provider abstraction** (one interface over many data sources).
- **NautilusTrader** — serious **backtest==live** engine if we want one backbone (Rust core, event-driven).
- **NOFX** — **"model proposes, code disposes"** hard-risk runtime.
- **awesome-quant / awesome-systematic-trading / machine-learning-for-trading (Jansen)** — mine for factors and implementations.
- **Time-series foundation models** (TimesFM 3.0, Chronos-2, **Kronos** — trained on OHLCV from 45 exchanges) — zero-shot forecasts as extra features.

---

## 7. Data sources to wire (crypto-first, asset-agnostic later)

- **Market:** Binance/OKX/Bybit/Hyperliquid/Lighter WebSockets (order book, trades, funding, OI, liquidations).
- **News:** cryptocurrency.cv (free, no key) + RSS + official project/exchange/regulator feeds + economic releases + ETF/unlock calendars + prediction markets (Kalshi/Polymarket — Arbiter already wired).
- **On-chain / DEX:** Birdeye-class (free tier) for Solana/DEX; on-chain flow.
- **Alt-data (later, mostly equities but pattern transfers):** 13F/Form-4 (AlphaSMO), congressional trades, options flow.
- **Macro:** VIX, DVOL, SPX, treasury yields, TGA, stablecoin supply (several already in the current dashboard).

---

## 8. Honest risks / where this fails

- **Causal maps are unstable** — links that hold in one regime flip in the next. The graph must be probabilistic, regime-conditioned, and *constantly graded against reality* or it becomes confident garbage. **See §11 for the training method and §11.5 for regime conditioning.**
- **LLM look-ahead contamination** — backtesting old news with a model that already knows the outcome produces beautiful, fake results. **Hard gate in §12.4.**
- **LLM scenario trees are plausible-but-wrong by default** — worthless without the outcome-grading loop.
- **Right-thesis-wrong-timing** — why convex/limited-downside structures and survival sizing are non-negotiable.
- **Overfitting** — 30 agents × many signals = huge trial count; without the deflated-Sharpe/PBO/CPCV gate we'll fool ourselves. The gate is the most important component, not the agents.
- **Complexity trap** — the pasted design is ~30 agents / 14 subsystems = a year before anything is validated. **Prove the smallest loop first, kill what doesn't beat base rates, then expand.**
- **Priced-in agent** needs a real measure of *market expectation* (positioning / prediction-market odds / consensus) — genuinely hard, don't hand-wave it.
- **No guarantee** — even done well, edges are small and decay. Realistic goal: a handful of small, real, capacity-limited edges stacked, not a money printer.

---

## 9. Sequenced build plan (prove-then-expand)

**Phase 0 — dedicated box + data spine.** Always-on mini-PC/box; collectors → time-series DB; the deterministic Tier-0 features running 24/7. No LLM yet.

**Phase 1 — the smallest core loop that can show predictive value** (the thing to validate first):
`event → structured extraction → causal impact (edges earned from data) → historical analogues + event-study base rates → directional thesis with confidence/horizon → store prediction → grade outcome (Brier/calibration).`
Run it **read-only** over live + historical events. **Does its high-confidence call beat the base rate, after costs, out-of-sample (CPCV + deflated Sharpe)?** If no → fix or kill before building anything else.

**Phase 2 — add the kill-gate + meta-labeling** as an automatic filter on every candidate signal/thesis.

**Phase 3 — payoff-structure finder + niche router + hard-risk runtime.** Turn surviving theses into convex structures in non-crowded instruments; paper-trade through the risk clamp.

**Phase 4 — learning loop at scale + nightly ML retrain + info-flow graph.**

**Phase 5 — anticipatory playbooks + LoRA fine-tune of the local model + RD-Agent idea-factory.**

**Phase 6 — expand asset classes** (equities/commodities/rates) on the same engine.

Gate between every phase: **it must earn its place with real, out-of-sample, cost-aware evidence.**

---

## 10. Open decisions (need Dev)

1. **Hardware:** laptop/API-only to start, or commit to a dedicated box now? (Phase 0 depends on this.)
2. **First slice to spec deeply:** the full merged architecture on paper, or just the **Phase-1 core loop**? (I lean core loop.)
3. **Scope confirm:** asset-agnostic core, crypto-first data — agreed?
4. **Deep-read depth:** want me to fully read the *code* of the top 3–4 repos (TradingAgents, RD-Agent/Qlib, FinRobot, NautilusTrader)? That's where I'd ask before spawning any research agents.

---

## 11. How the causal graph is actually TRAINED (not guessed)

This section resolves the #1 open risk from §3.4/§8. The rule: **the LLM never supplies a number. Data sets every weight. Statistics decides which edges are allowed to exist.**

### 11.1 The hard wall: rows ≠ events

Millions of price rows do **not** mean millions of events. "US strikes Iran" has happened maybe ~5 times in crypto's lifetime. Statistically, effective sample size tracks the number of **independent clusters**, not the number of observations (this is why event studies use clustered/Kolari-Pynnonen style corrections). Training `Iran → BTC` directly = fitting ~5 points = confident fiction. `[PROVEN statistical fact]`

### 11.2 The unlock: learn each LINK, never the whole chain

Decompose the chain; each individual link has abundant data:

| Link | Approx. independent N |
|---|---|
| geopolitical supply shock → oil | hundreds of events |
| oil shock → inflation expectations | thousands of daily obs |
| inflation expectations → real yields | thousands |
| yields / liquidity → risk assets → high-beta alts | thousands |

A chain's total effect = the links **composed**, with uncertainty propagating and widening down the chain (correct behaviour: the further from the shock, the less we should claim). `[HYPOTHESIS — core method]`

### 11.3 The estimator: Jordà local projections

For each (shock → target → horizon), run a local projection — one simple regression per horizon h (1h, 6h, 24h, 3d…). It is the standard go-to method for impulse responses in macro, estimable by OLS with corrected standard errors.

It outputs exactly the edge attributes §3.3 requires:
- **direction + strength** = the coefficient
- **confidence** = the confidence interval
- **expected_delay** = which horizon the effect peaks at
- **half_life** = how the coefficient decays across horizons
- **historical_support** = N and significance

So graph edges are **measured**, not invented.

### 11.4 Getting N up

- **Pool by event TYPE, not instance** — not "Iran", but "geopolitical supply shock" across every occurrence.
- **Use pre-crypto history for macro links** — oil→inflation→yields has ~50 years. Only the final hop (risk → crypto) is limited to crypto's lifetime.
- **Cross-section multiplies** (1 event × 300 coins × several horizons) — but these are **not independent**; must discount via clustered errors / effective-N.

### 11.5 Regime conditioning is mandatory

The literature on causal discovery in financial time series is explicit: relationships are **non-stationary and regime-dependent**; the same shock transmits differently across regimes, and hidden confounders + endogeneity make naive estimates wrong. So:
- estimate each edge **per regime**,
- re-estimate on a **rolling window**, decaying old data,
- an edge is never one number — it is a number **conditional on the current state of the world**. `[PROVEN concern]`

### 11.6 On the "simulator that runs 100 possibilities" idea

Genuinely useful — but with a hard limit that must be respected:

**A simulator cannot create information that is not already in the data.** A world-model trained on our history can only reproduce our history's statistics; learning from it feels like discovery but is re-reading what we already had, with unearned confidence. Research on RL market simulators is blunt that agents assume fixed dynamics while real markets evolve — precisely when losses happen.

- **Use simulation for:** stress/robustness ("does the thesis survive a 3× bigger move, 6h later, worse fills?"), **sizing and execution policy** (the one place RL genuinely earns its keep, because the market is fixed and only our own behaviour varies), and counterfactuals on our own decisions.
- **Never use simulation for:** discovering a causal edge. Simulate to *test and to learn how to act* — never to *discover truth*. `[PROVEN limitation]`

### 11.7 Two traps that must be built in from day one

1. **Multiple testing / false discovery.** Test 10,000 candidate edges and ~500 look "significant" by pure luck. Without false-discovery-rate control the graph is mostly noise — and it will look magnificent. **FDR control is mandatory.**
2. **LLM-proposed structure is itself a risk** — it will happily invent plausible-but-nonexistent paths. **An edge is admitted only if it passes BOTH a statistical test AND has an economic rationale.** Either alone is insufficient.

---

## 12. LLM-XGB — the reasoning/calibration hybrid

**The problem with plain gradient boosting:** it sees `event_type=7` and has no idea Iran can close a shipping strait. It cannot read, has no world knowledge, and cannot infer implications.
**The problem with a plain LLM:** confident, uncalibrated, no base rates, and it cannot learn from outcomes without retraining.

**LLM-XGB = LLM supplies understanding; gradient boosting supplies calibration and discipline.** This is an **architecture, not a new algorithm** — we are explicitly NOT trying to fuse transformer internals with GBDT internals (research-grade, ~a year, likely worse than the pipeline below).

### 12.1 Three fusion modes (we use b + c; a is a supplement)

**(a) Embeddings as features** — embed the text, reduce (PCA/UMAP), feed to the tree ensemble. Established and it works, but the vector is **opaque** — we could never audit *why* it fired. Supplement only.

**(b) LLM as a *reasoning-feature generator* — the core.** The LLM emits **judgments only a reasoner could produce**, never a sentiment score:

```
escalation_probability          how likely this escalates further
supply_at_risk                  actual magnitude (e.g. barrels), not a mood
reversibility                   structural vs undoable
forced_transactors              WHO is now forced to buy/sell (margin, hedgers)
channels_activated              which transmission paths light up, in what order
novelty                         genuinely new vs restatement of the known
expectation_gap                 distance from what the market was positioned for
expected_duration               first guess at the half-life
```

Crucially these are **opinions to be calibrated, not truth.** If the LLM runs 20% hot on escalation probability, the tree model learns that bias and corrects it. The LLM is allowed to be wrong in a **measurable, correctable** way.

**(c) Gradient boosting as the "should we ACT?" meta-model.** This is López de Prado meta-labeling (§2) applied to an LLM: the LLM produces the thesis and direction; a second model decides **whether to take it and how big**, learning *when the LLM is wrong* — by market state, event type, and horizon. Classic stacking/residual correction. The system improves **without retraining the LLM at all**.

### 12.2 Flow

```
news text
   ↓  LLM (cheap/local for bulk, bigger for hard cases)
JUDGMENT FEATURES  (the table above — numbers, auditable, named)
   +  market state (vol, funding, OI, CVD, regime, positioning)
   +  historical-analogue similarity + event-study base rates (§11)
   ↓  gradient boosting
CALIBRATED probability / expected move / horizon
   ↓  meta-model
ACT / DON'T ACT  + size
```

### 12.3 Why this is the payoff

Because every LLM judgment is a **named feature**, we eventually learn **per-feature trust**: "its escalation estimates are reliable, its half-life estimates are worthless, its forced-seller detection is its best signal." Not just *which agent* to trust — **which kind of thinking** to trust. That is a far sharper learning loop than anything in the public repos. `[HYPOTHESIS — the main bet]`

### 12.4 HARD GATE — LLM look-ahead contamination

**This can silently invalidate every backtest we ever run.** If we backtest 2023 news with a model trained through 2026, the model may already *know how it turned out*. The backtest returns gorgeous numbers that are entirely fake. Almost nobody handles this.

**Rules (non-negotiable):**
1. **Strict point-in-time prompting** — the model sees nothing dated after the event, including our own derived data.
2. **Validate on events AFTER the model's training cutoff** — the only truly clean test.
3. Treat any backtest without both of the above as **void**, no matter how good it looks.
4. Prefer a **frozen, version-pinned** model for historical feature generation, recorded with the features.

### 12.5 Other real risks

- **Feature drift** — changing the model or the prompt silently changes what a feature *means*, breaking the model trained on the old ones. Requires **versioned features** + retrain discipline.
- **Cost of history** — generating judgment features across years of articles is the expensive part. Job for the **cheap local model, in bulk, once**, with results cached forever.
- **Dimensionality/overfit** if embeddings (mode a) are added — reduce before feeding, and it still counts as trials against the §11.7 FDR budget.

---

## 13. Resolving the squeeze (§11.1 small-N vs §12.4 clean-data)

**The apparent problem:** §12.4 says only post-cutoff events are truly clean, but §11.1 says events are already scarce. Those two look like they strangle each other.

**Correction — the squeeze was overstated.** The two needs draw on **different data**, so they mostly don't compete:

- **§11's causal edges are estimated from NUMERIC time series** (oil, yields, funding, returns). **No LLM touches that step.** Therefore **zero contamination risk**, and the full multi-decade history is usable. Small-N applies to event *pooling*; look-ahead does not apply at all.
- **The LLM judgment features (§12) are the ONLY contaminated surface** — and they need far fewer clean samples, because they're validated as an *increment* on top of an already-estimated numeric baseline, not from scratch.

### 13.1 What the research says (Sep 2026)

- Contamination is **real and measurable**: a model trained after an event may already "know" the outcome; apparent skill is memory, not reasoning. `[PROVEN]`
- **Bias scales with model size and data granularity** — *smaller models and finer granularity show negligible bias.* This is a direct architectural win: **the cheap local model we wanted for bulk historical labelling (cost) is also the contamination-safest choice.** `[PROVEN]`
- **Retrieval beats recall** — feeding the model the document is inherently safer than asking it to recall market history. §12(b) already extracts features *from the article text*, which limits the surface by design.
- **Entity masking alone is NOT sufficient** — models reconstruct masked entities from minimal context. Anonymization is a weak defence on its own. `[PROVEN caveat]`
- Detection tooling exists and is cheap: **date-only recall probes**, **counterfactual/perturbation rewriting**, and measuring the **memorization advantage** (performance gap on likely-seen vs novel inputs). Inference-time memory-suppression methods (FinCAD-style) also exist.

### 13.2 The four-tier data budget

| Tier | Data | Contamination | Use |
|---|---|---|---|
| **A** | Numeric market/macro history (full, decades) | **None** — no LLM involved | Estimate all §11 graph edges, event-study base rates, market-state features |
| **B** | LLM features on pre-cutoff history (large) | Measured, per-event | Train/tune the LLM-XGB. Every event gets a **date-recall probe**; events the model demonstrably remembers are **dropped or down-weighted**. Use the **small local model** (negligible bias) for bulk labelling |
| **C** | Post-cutoff events (scarce) | **Clean** | **Final go/no-go only. Spent ONCE.** Never used for tuning, never re-used after a failed result |
| **D** | Forward / live read-only log (accrues) | **Permanently clean** | The real long-run validation set |

### 13.3 Two moves that actually break the squeeze

**1. Start the read-only prediction log NOW.** Time is the *only* source of uncontaminated data, and it accrues at a fixed rate whatever we do. Every day we don't log predictions is a clean day lost forever. This is the strongest argument for building the logging spine **first**, before any strategy work.

**2. Validate the machinery on HIGH-FREQUENCY event types first.** Funding spikes, token unlocks, listings, scheduled macro prints — these produce clean post-cutoff N *quickly*. Prove the pipeline works there, then extend to rare events with honestly wider error bars. Don't try to validate on geopolitical shocks; they're the scarcest thing we have.

**3. Standard walk-forward with an embargo** on everything numeric (e.g. rolling train / validate windows with a ~30-day embargo between them), per §2's kill-gate.

### 13.4 The part this does NOT solve (honest)

**Rare, high-impact events — the exact Iran-style case Dev cares most about — can never be statistically validated at the thesis level.** There will never be enough of them. Anyone claiming otherwise is fitting noise.

What we *can* do for rare events:
- validate the **numeric chain links** (Tier A) that the thesis is composed of — those have real N;
- validate the **reasoning process** on frequent events, and assume it transfers;
- and, most importantly, **make being wrong survivable** — which is exactly why §3.4's convex/hedged payoff structures are not a nice-to-have. For unvalidatable rare events, **payoff shape replaces statistical confidence.** That's the honest answer: we don't get certainty, we get asymmetry.

---

## 14. THE CALENDAR SYSTEM (Dev's design — our own calendar, position-aware)

**Status:** designed, not built. This is the highest-value near-term component and the only one that pays off *before* we have history.

### 14.1 Why a calendar is architecturally different from a feed

Research finding (`research/WORLD_CONTEXT.md` §C). These are **not** the same object with different dates:

| | Event stream (news feed) | Calendar (schedule) |
|---|---|---|
| Time direction | past only | **future** |
| Arrival | unpredictable | known |
| Primary key | `(source, published_at)` | `(entity, scheduled_ts)` |
| Mutation | append-only, immutable | **rows mutate** — date moves, precision sharpens, `confirmed` flips, then the outcome is filled in |
| Query | "what just happened?" | **"what is about to happen, to what I hold?"** |
| Latency need | milliseconds — you are racing | **none** — prepare for weeks |
| Edge lives in | speed | **positioning + conditional priors** |
| Failure mode | you missed it | **you were surprised by something you could have known** |

**The decisive property: a feed has no repeat key.** Every article is unique, so you can never ask "what happened the last 40 times?" A calendar's events are *typed and recurring* (`FOMC`, `CPI`, `NVDA earnings`, `SOL unlock`), so it can maintain `P(move | event_type, entity, regime)` and the empirical move distribution. **That is the machinery behind §3.3's HISTORICAL ANALOGUES stage and the concrete mechanism for §3.4.3's "anticipatory, not reactive" hypothesis.**

### 14.2 We build and curate our OWN calendar — the ingestion rule

**Dev's rule: when any scheduling body announces a date, it goes in our calendar.** Fed announces a meeting → add it. India (RBI) schedules a policy meeting → add it. A company sets an earnings date → add it. A token publishes an unlock schedule → add it. An exchange announces a listing date → add it.

We do **not** depend on a single vendor calendar. We accumulate our own, from primary sources, and **we own the history of the schedule itself** (see revisions, §14.4).

**Sources to seed from (all free):**

| Category | Source |
|---|---|
| Central banks (global) | Each CB's own site; seed the list from `bis.org/cbanks.htm`. **Primary pages are authoritative — aggregators are convenience only** |
| FOMC specifically | `federalreserve.gov/monetarypolicy/fomccalendars.htm` |
| US macro prints (CPI/NFP/claims) | BLS API v2 (free key), FRED release calendar |
| Earnings dates | SEC `data.sec.gov/submissions/CIK##########.json` (incl. `acceptanceDateTime` — the pre-open vs after-hours discriminator) |
| Token unlocks | DefiLlama + on-chain vesting contracts + CoinGecko ids (we already have `unlocks.db`, 142 tokens) |
| Exchange listings/delistings | Binance/Upbit/Bithumb announcement feeds + our HL `meta` diff (already stored in `events.db::hl_universe_changes`) |
| Options expiry / opex | Deribit instrument expiries; monthly/quarterly cycle |
| Funding settlements | HL/venue funding intervals (mechanical, RRULE) |
| Regulation effective dates | Federal Register API, EUR-Lex, MOFCOM |

### 14.3 THE POSITION-AWARE LOOP (Dev's core idea — the part that makes it operational)

A calendar that just *exists* is a reference table. The value is in **checking every position and every candidate trade against it.**

**Three checks, run continuously:**

**(a) PRE-TRADE — before we take a bet**
```
For a candidate position in asset A with expected hold H:
  1. events = calendar.between(now, now + H) affecting A
        (direct: A's own unlock/listing/earnings
         indirect: via §4.2 exposure graph — FOMC → all crypto; MOFCOM → chips → …)
  2. For each event: pull historical base rate
        P(move | event_type, entity_or_peer_group, current_regime), with N and dispersion
  3. Compute funding cost of holding THROUGH the event
  4. Decide: size down / hedge / shorten the hold to land before it / skip / deliberately hold FOR it
```

**(b) IN-POSITION — the "cash out before" rule**
For every open position, every day: *what is coming, when, and does it change the plan?* Output is an explicit, dated action — **"trim SOL before <event> on <date>"** — not a vague warning. This is the thing that stops us getting blindsided by something that was publicly scheduled months ago.

**(c) OPPORTUNITY — "use it"**
The calendar is also a **trade generator**, not only a risk filter. Scheduled, mechanical, one-directional events are precisely the edges the research says survive (§14.6). A large unlock in 6 days *is* the setup.

**Every calendar-driven decision is logged as a prediction** (§4 learning loop) so the base rates improve with each occurrence.

### 14.4 Derived windows — free extra value from the same data

Computed *from* the calendar at no extra collection cost:

- **Fed blackout window.** Exact published rule: begins **00:00 ET on the second Saturday before the meeting**, ends **23:59 ET the day after**. Two consequences: (1) inside it, Fed-speaker headline risk is **zero by rule**, so any "Fed sources" story is the WSJ leak channel or noise; (2) officials deliberately schedule their most informative speeches in the days *immediately before* blackout — making those 2–3 sessions a systematically high-information window.
- **Collision detection.** Flag *ex ante* when two events land in the same 48h (e.g. FOMC + a major unlock + monthly opex). Effects compound.
- **Event-vol vs diffusive-vol decomposition.** Map each future event onto the options/funding term structure it sits inside → know whether an event is priced cheap or rich.
- **Thin-liquidity windows.** Holidays, weekends, session handoffs — where the same order has 4–5× the impact (`research/MARKET_MECHANICS.md` §10).
- **Schedule-change signal.** A company or protocol *moving* a date is itself information (§D22 pre-announcement hints).

### 14.5 Minimum schema

```
scheduled_event(
  id, entity_id, event_type, scheduled_ts_utc,
  local_ts, tz_id,              -- DST shifts the UTC time of a recurring local event
  ts_precision,                  -- 'Q3-2026' and '2026-09-18T14:00:00Z' cannot share a type
  confirmed BOOL, source_url,
  valid_from, observed_at        -- BITEMPORAL, mandatory (§14.7)
)
scheduled_event_revision(event_id, changed_at, field, old, new)   -- schedule history IS data
recurrence_rule(event_type, rrule)                                -- funding, opex, CPI, COT
market_regime_window(kind, start, end)                            -- blackouts, thin liquidity
event_instance(scheduled_event_id, actual_ts, surprise_vs_expected)
event_outcome(event_instance_id, entity_id, horizon, abnormal_return, session_bucket)
```

`event_instance` + `event_outcome` are the storage form for §3.3's analogue stage — **analogue retrieval becomes a JOIN with an N attached**, not a fuzzy similarity search.

### 14.6 Why this is the highest-value near-term build

1. **It pays off before we have history.** Every other component is blocked on the 9.9-day data problem (§6/blockers). The calendar is useful on day one.
2. **It needs no latency race.** Purely scheduled — the exact opposite of the news game we cannot win.
3. **It targets what actually survives.** Independent research (`research/DRIVER_TAXONOMY.md` §13) ranked **token unlocks Tier-1 #2 and explicitly "best fit for a Hyperliquid-based system"**; unlock weakening starts **~30 days early**, so anticipation beats speed. Lockup/unlock effects are *mechanical supply*, stable over 10-year samples.
4. **It is cheap and free.** A few hundred lines of scrapers over free primary sources.
5. **It protects live capital immediately** — Dev has open positions now.

### 14.7 The two hard rules

1. **BITEMPORAL, always.** Every row stores `valid_from` (when it was/will be true) and `observed_at` (when *we* could have known). Backtests filter on `observed_at`. Using a scheduled date without recording when it became knowable is — per `research/WORLD_CONTEXT.md` §H — *"the single easiest way to manufacture fake alpha."*
2. **Small N is the binding constraint here too.** FOMC is 8/year; a given token unlocks a handful of times. **Every base rate must carry N and dispersion**, report median + 25/75 percentiles (not means — event distributions are fat-tailed), and widen N via `peer_group` where honest. A base rate with N=3 must render as N=3.

---

## 15. WHAT WE DO NEXT — the build order

Derived from `research/MASTER_SYNTHESIS.md`. Ordered by (value delivered) ÷ (work + risk). **Each step is a gate: it must show a real result before the next starts.**

### Step 0 — Backfill history (start immediately, runs in background)
`data.binance.vision` bulk archive → turn **9.9 days into years**. This is blocker #1 and it gates §11 entirely. It is mostly *downloading*, so it can run while we build other things.
**Prerequisite: verify the archive's actual depth and coin coverage first** — this is `planned`, not `verified`.

### Step 1 — The calendar (§14)
Highest value per unit of work, pays off before history exists, protects live positions. Build in this order:
1. Policy calendar (FOMC/ECB/BoJ/RBI + CPI/NFP) — free, static, tiny
2. Derived windows (blackout, collisions) — free, from step 1
3. Token unlock calendar **with sizes** (see Step 2)
4. Exchange listing/delisting feed
5. The position-aware loop (§14.3) — this is the part that makes it operational

### Step 2 — Fill the empty tables
- `hl.db::book_snapshots` has the right columns (microprice, imbalance, spread, depth) and **0 rows**. So do `candles`, `funding`, `trades`, `ctx_snapshots`. **Our cost model currently has no data behind it, and at our size cost IS the whole execution problem** (`research/EXECUTION_AND_GAPS.md` §1.1).
- `unlocks.db` stores dates but **not sizes** — our #2 edge needs unlock/float and unlock/ADV (thresholds: >1% supply, >2.4× ADV).
- **Arrival-price logging**: store decision-time price on every order, or TCA is impossible retroactively.

### Step 3 — Store macro history
FRED (free key): `DGS10`, `DGS2`, `T10Y2Y`, `DCOILWTICO`, `CPIAUCSL`, `PAYEMS`, `WALCL`, `VIXCLS`, HY/IG OAS. Decades of free history — the backbone series for §11's causal chains, which currently have **nothing stored**.

### Step 4 — Test the crypto shortlist, one at a time, against the §2 kill-gate
In order of evidence strength:
1. **Carry / hedged funding** — already proven in our own walk-forward
2. **Token unlocks** — needs Step 2
3. **Spot-perp basis** — `CROSS_VENUE_FEATURES.md`'s #1 ranked feature, "best untested candidate"
4. **Liquidation-cascade fragility** — OI + funding + positioning, all already collected
5. **Post-listing decay**
6. **`top_minus_retail`** — 31 days already stored

### Step 5 — Only then: the typed entity graph and the wider world layer
(`research/WORLD_CONTEXT.md` §G Tier 1: `jurisdiction`, `entity`, `company_jurisdiction`, `asset`/`venue_listing`.)

### What we deliberately do NOT do
- **Do not enumerate 500+ features.** 1,200 candidates × 365 dates ⇒ ~60 false positives by chance. Breadth actively hurts here; selection discipline is the constraint.
- **Do not optimise execution schedules.** Median HL metaorder is $8,500; our account is ~$90. Impact is irrelevant at our size.
- **Do not build anything on the dead list** (§2 of MASTER_SYNTHESIS).
- **Do not chase news latency.** Public news is priced in seconds; retail is ~47s late.

---

## 16. THE FEATURE LAYER — the actual calculations (WAS MISSING FROM THIS PLAN)

**Honest admission:** until now this document specified a "feature engine" box in §3.1 and quant agents in §3.2 **without ever saying what they compute.** Grep found 2 mentions of any named calculation in 584 lines, both inside an example string. The entire numeric foundation was unspecified. This section fixes that.

**Source of truth for formulas:** `research/CROSS_VENUE_FEATURES.md` (has exact formulas + failure modes), `research/MARKET_MECHANICS.md` (why each exists), `research/EXECUTION_AND_GAPS.md` (options/regime).

**Two rules that govern this whole layer:**
1. **Everything is computed on the CONSOLIDATED price `CP`, not a single venue** (`CROSS_VENUE` §1.7), and every dispersion feature is relative to `CP`, never to Binance.
2. **Every feature is computed per `session_bucket`** (Asia/Europe/US/weekend). Merging sessions destroys real effects — both agents flagged this independently.

### 16.1 Returns & momentum
`r_h` log returns at h ∈ {5m,1h,4h,1d,3d,7d,30d} · `mom_skip1` (7d→1d, skipping the last day — standard, and it matters) · `rev_1d` short reversal · `resid_ret` (return minus BTC-beta and sector) · `mom_resid_7d_skip1` · cumulative abnormal return (CAR) at event horizons · overnight vs intraday split.

### 16.2 Volatility (7 estimators — they disagree, and the disagreement is information)
`RV` close-to-close · **Parkinson** (high-low, ~5× more efficient) · **Garman-Klass** (adds O/C, ~7–8× efficient) · **Rogers-Satchell** (drift-robust — use when a coin trends hard) · **Yang-Zhang** (handles gaps) · **Bipower variation** (jump-robust) · `JumpFrac = max(0, RV²−BPV)/RV²` · EWMA vol · GARCH/HAR forecast · vol-of-vol · realized skew & kurtosis · downside vol · upside/downside vol ratio · **spread-noise-corrected RV** (`RV_clean ≈ √(max(0, RV² − 2·(spread/2)²/Δt))` — mandatory before comparing venues).

### 16.3 Liquidity & cost (this is our whole execution problem at $90)
Quoted spread (bps) · effective spread · **Roll** estimator from serial covariance · **Corwin-Schultz** high-low estimator · **Amihud** ILLIQ — *log, winsorised 1/99, median-not-mean* (it was previously diagnosed as an outlier artifact in this system; if it dies under those three fixes it was never real) · `impact_proxy` (|r| per √V — **call it that, NOT Kyle's lambda**, we have no signed flow) · top-of-book depth · depth within 5 spreads · 2%-depth · slippage curve per coin · `spread_HL_relative` · `spread_widening_breadth` (fraction of venues with spread_z>1) · turnover · **realised fill vs arrival price (TCA)**.

### 16.4 Microstructure
**Microprice** (size-weighted mid — better than mid, and `book_snapshots` was built for it and is empty) · book imbalance · **OFI** (order-flow imbalance) · queue-position proxy · trade-sign imbalance · sweep detection · absorption detection · book-refill rate · tick-size-adjusted imbalance.
> Use as **confirmation and gating**, never as a standalone signal: OFI's cost/edge ratio was measured at **164×** at 10s frequency.

### 16.5 Volume & flow
ADV (7d/30d) · `vol_surprise = log(V_1d / median_30d)` · **credible-volume aggregate** (Binance+Bybit+OKX+Coinbase+Kraken only — never sum 26 venues, wash trading) · `fringe_volume_share` · venue share · **HHI** concentration · `n_eff = 1/HHI` · `hl_share` · CVD (cumulative volume delta) · **taker imbalance** (the only genuinely signed flow we have).

### 16.6 Derivatives & positioning
Funding rate · `funding_z` (vs own 60d) · **`funding_carry_expected`** (signed, over the expected hold — **21 bps on a 7-day hold vs 9 bps fees, so it's the BIGGER cost line**) · **`sp_basis`** (consolidated perp vs consolidated spot — `CROSS_VENUE`'s #1 ranked feature, "best untested candidate") · `perp_basis` venue-to-venue · `hl_basis_resid` · `funding_gap` · OI · `oi_chg` · **`oi_price_regime = sign(Δprice)·sign(ΔOI)`** (new longs / new shorts / short covering / long liquidation) · liquidation volume & clusters · **`top_minus_retail`** = z(top-trader ratio) − z(account ratio) — *the informed-vs-uninformed proxy, and we already have 31 days of it* · long/short ratios · **cascade-fragility score** (OI × funding extremity × positioning skew).

### 16.7 Cross-venue
`CP` consolidated price · `disp_iqr` (robust dispersion — **use IQR, not range; max/min are the stalest venues**) · `disp_z` · `prem(i,v)` signed premium · **`prem_ma` / `prem_resid`** (structural vs transient — the single most valuable decomposition in the cross-venue family) · `lead_share` per venue · **kimchi premium + `kimchi_breadth`** (breadth gives ~50× the statistical power of the single BTC series) · India/INR premium (**subtract the 1% TDS structural wedge first**) · staleness/`fresh()` mask + per-venue rejection rate (itself a feature).

### 16.8 Cross-sectional & relative value
`beta_btc` (shrunk toward 1.0) · `beta_eth` · residual returns · rolling correlation matrix · **correlation-break detector with `trigger_event_id`** (BTC–NDX swung −0.68→+0.72 in ~2 weeks — never hardcode a correlation) · **hierarchical clustering on 90d residual-return correlations, re-estimated monthly** (NOT hand-labelled sectors — hand labels go stale and leak priors) · sector residual · breadth · BTC dominance · RRG (relative rotation).

### 16.9 Options / vol surface (we have NONE of this — only the DVOL index)
ATM IV by tenor · **25Δ risk reversal** · **skew** = (IV 25Δput − IV 25Δcall)/ATM · **term structure ratio** (30D/7D) · **VRP** = IV − subsequent RV · put/call ratio · OI by strike · max pain · dealer **GEX** · vanna/charm proxies.
> First honest test (`CROSS_VENUE` §2.4's recommendation): does **IV−RV** add predictive power over lagged realised vol? Prioritise this over venue-disagreement.

### 16.10 On-chain
Exchange net-flow · stablecoin supply & by-chain · **HL whale registry** (from `recentTrades.users` → `clearinghouseState` per wallet — verified working, and the Barone-Lillo paper reconstructed 4.3M metaorders from exactly this) · whale position changes/flips · active addresses · TVL.

### 16.11 Regime & state
Vol regime (tercile / HMM state) · trend state · funding regime · liquidity regime · **`session_bucket`** · breadth regime · dominance regime · stress score · **`market_regime_window`** (blackout / thin-liquidity / rebalance, derived from the calendar §14).

### 16.12 Calendar-derived (new — from §14)
`days_to_next_event` per asset · `event_type_next` · `in_fed_blackout` · `collision_flag` · `expected_funding_through_event` · `historical_move_for_this_event_type` (with **N and dispersion**).

### 16.13 Event features
`novelty` · `surprise` vs expectation · **`priced_in` score** = |CAR over T−7..T−1| / realised vol (`NEWS_IMPACT` §6.2: *"this one feature will kill more bad trades than any sentiment model"*) · coverage volume / unique-source count (**attention — which works — as distinct from sentiment, which doesn't**) · source tier · `scheduled` flag (**the master discriminator: scheduled ⇒ fade, surprise ⇒ follow**) · magnitude normalised by the token (stolen/mcap, unlock/supply, unlock/ADV).

### 16.14 Risk
Residual vol (**size on this, never total vol**) · portfolio beta · VaR/ES · drawdown · **stressed correlation matrix (computed on the worst 10% of days only)** · cluster concentration · **portfolio margin utilisation under a 3σ correlated move** (the real binding constraint on perps).

### 16.15 THE HARD RULE ON ALL OF THE ABOVE

This is **~130 named calculations**. That is **not** a licence to test 130 signals.

`CROSS_VENUE` §6.6 computed it: ~1,200 candidate feature-variants on ~365 effective dates produces **~60 "significant" results by pure chance**. Harvey-Liu-Zhu: the bar is **t > 3.0**, not 2.0. So:

1. **Compute widely, test narrowly.** Features are cheap to compute and expensive to *test*. Compute all of them as state; only test the pre-registered shortlist (§15 Step 4).
2. **Collapse per-venue features into triples** — `consolidated`, `dispersion`, `HL_relative` — never 26 separate venue features. This alone cuts the test count ~8×.
3. **Benjamini-Hochberg FDR within each family**, not per-feature p-values.
4. **Sign stability across non-overlapping sub-periods beats any p-value.**
5. **Report every feature's `IC(h)` decay curve for h=1..14 with standard errors, individually, BEFORE combining anything.**
6. **Hold out the last 6 months and never look at it** until the composite is frozen. One look burns it.

---

## 17. THE SOURCE INVENTORY

### 17.1 What we already have (verified 2026-09-02)
26 CEX venues (4.29M price rows) · Hyperliquid incl. **wallet-level `recentTrades.users`** · Lighter · **Binance top-trader positioning** (172 coins/1h/31d) · 19 social channels (15,856 posts) · CoinGecko · unlocks (142 tokens, **dates only, no sizes**) · Fear&Greed · arXiv · Kalshi/Polymarket (unverified) · ~12 crypto news RSS.

### 17.2 New free sources found (~60 total; ALL currently `unverified`)

**No key, no registration (25):** SEC EDGAR submissions · SEC XBRL frames · SEC full-text search · **Federal Register API** (+ `/public-inspection-documents` = documents *before* publication) · **GLEIF** (jurisdiction + parent hierarchy) · World Bank · **ECB Data Portal** (139k series) · **BIS Data Portal / CBPOL** (policy rates, all countries) · `bis.org/cbanks.htm` (every central bank) · Banco Central do Brasil · **GDELT 2.0** (65+ languages, 15-min) · **IMF PortWatch** (28 chokepoints, exact ArcGIS endpoint captured) · USGS earthquakes · Overpass/OSM · Wikidata SPARQL · **FuturesBench COT** (107 markets, 1986→, no limits) · CoinGecko* · DefiLlama* · **crt.sh** (certificate transparency) · **Greenhouse job boards** · RestCountries · **FCC equipment authorisation** · sanctions.network · Fed/ECB speech RSS. *(\*already used)*

**Free with a key (15):** **FRED** (800k series + **release calendar**) · EIA · Congress.gov · GovInfo · Regulations.gov · **Trade.gov CSL** (11 US restricted lists, hourly) · **Cloudflare Radar** (national internet outages) · ACLED · Finnhub · FMP · aisstream · openFDA · USPTO · UN Comtrade · CourtListener.

**Named in body, not tabled (~20):** DBnomics · EUR-Lex · legislation.gov.uk · **MOFCOM** (export controls appear here first) · e-Gov Japan · egazette India · RBI DBIE · law.go.kr · OECD tax tracker · **FDA PDUFA** · NASA FIRMS · NOAA · USGS minerals · Norwegian AIS · centralbank.watch · BoJ/BoE/PBoC portals · Stooq · **`data.binance.vision`** (bulk history).

### 17.3 Genuinely unavailable free (stop looking)
Borrow fee/utilisation (**the single highest-value missing dataset**) · analyst consensus (blocks clean PEAD) · tick/TAQ with sub-penny flags · point-in-time index constituents · historical options chains with OI · **local-language retail sentiment** (Naver/Weibo — GDELT is the substitute) · vessel-level cargo · CDS levels.

### 17.4 The rule
**Every source is `unverified` until we call it and see real data, with a date.** We proved today that documented endpoints die (HL `leaderboard` → HTTP 422). Status goes into `data_layer/registry/sources.yaml`; nothing is "wired" on the strength of documentation.

---

## 18. REVISED BUILD ORDER — DATA FIRST (Dev's call)

**Everything else is deferred. We get the data first.**

**Phase D1 — Verify the sources.** Call all ~60 new endpoints, record real responses, write earned `verified`/`dead` status into `sources.yaml`. Cheap, fast, and it stops us building on documentation that lies.

**Phase D2 — History backfill.** `data.binance.vision` bulk archive → turn 9.9 days into years. Blocker #1. Verify coverage/depth first.

**Phase D3 — Fill the empty tables.** `book_snapshots`, `candles`, `funding`, `trades`, `ctx_snapshots` all have 0 rows. Add **arrival-price logging** on every order. Add **unlock sizes** (unlock/float, unlock/ADV).

**Phase D4 — Wire the new collectors,** highest value first: FRED macro history · Deribit options chain · GDELT · Federal Register · policy calendars (§14) · HL whale registry · LunarCrush/Farcaster · prediction markets.

**Phase D5 — Build the feature engine (§16).** All ~130 calculations, computed continuously as *state*. Compute widely.

**Phase D6 — Only then** test the pre-registered shortlist through the §2 kill-gate. Test narrowly.

---

## Sources
- Firms: [Renaissance/AQR/PDT overview](https://medium.com/@navnoorbawa/how-renaissance-technologies-aqr-and-pdt-built-100-billion-factor-models-statistical-arbitrage-ac0c9cd8a518), [Jim Simons strategy](https://www.quantvps.com/blog/jim-simons-trading-strategy), [Jane Street deep dive](https://underthemarketlens.substack.com/p/jane-street-trading-firm-39-6-billion-revenue-explained), [Jump/Jane Street in crypto](https://www.dlnews.com/articles/markets/how-speed-traders-jump-jane-street-make-money-in-crypto/), [top quant firms 2026](https://www.quantvps.com/blog/top-quant-trading-firms)
- Alt-data/ensemble: [alt-data hedge fund guide](https://vertdata.com/blog/alternative-data-hedge-funds-guide), [combining datasets](https://www.exabel.com/blog/combine-alternative-datasets/)
- Overfitting/validation: [10 reasons ML funds fail — López de Prado (PDF)](https://www.garp.org/hubfs/Whitepapers/a1Z1W0000054x6lUAA.pdf), [purged cross-validation](https://en.wikipedia.org/wiki/Purged_cross-validation), [meta-labeling + triple barrier](https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/)
- Crypto edges: [funding-rate arb 2026](https://arbitrageghost.medium.com/funding-rate-arbitrage-in-2026-the-complete-guide-with-real-calculations-40e6cf341e52), [crypto arbitrage playbook (CCXT)](https://docs.ccxt.com/blog/crypto-arbitrage-strategies)
- Graph training (§11): [Jordà local projections — practical issues (PDF)](https://economia.uc3m.es/jgonzalo/teaching/PhdTimeSeries/Local%20Projections%20OJorda.pdf), [Local Projections — Jordà & Taylor, NBER (PDF)](https://www.nber.org/system/files/working_papers/w32822/w32822.pdf), [Causal discovery in financial markets / nonstationary](https://arxiv.org/abs/2312.17375), [causal regime detection (SCM)](https://arxiv.org/pdf/2511.04361), [clustered standard errors](https://en.wikipedia.org/wiki/Clustered_standard_errors), [event-study significance tests](https://www.eventstudytools.com/significance-tests), [LOB world-model simulator](https://arxiv.org/pdf/2210.09897), [RL in agent-based market simulation](https://arxiv.org/html/2403.19781v1)
- LLM-XGB (§12): [enriching tabular data with LLM embeddings — ablation](https://arxiv.org/html/2411.01645v1), [LLM embeddings improve tabular adaptation](https://arxiv.org/pdf/2410.07395), [hybrid semantic boosted trees](https://machinelearningmastery.com/combining-xgboost-and-embeddings-hybrid-semantic-boosted-trees/), [LLM-based feature extractors — systematic analysis](https://arxiv.org/html/2509.14979), [LLM reasoning in feature generation](https://arxiv.org/html/2503.11989), [meta-model predicting when the LLM is wrong](https://arxiv.org/pdf/2601.07006), [stacking / meta-learning](https://www.geeksforgeeks.org/machine-learning/stacking-in-machine-learning/)
- Contamination / squeeze (§13): [Mitigating look-ahead bias in financial backtesting with LLMs](https://arxiv.org/abs/2605.24564), [Detecting lookahead bias in LLM forecasts](https://arxiv.org/pdf/2512.23847), [AI's predictable memory in financial analysis](https://www.sciencedirect.com/science/article/pii/S0165176525004392), [MemGuard-Alpha](https://arxiv.org/pdf/2603.26797), [survey of contamination detection methods](https://arxiv.org/pdf/2404.00699), [rephrased-samples contamination](https://arxiv.org/pdf/2311.04850), [walk-forward optimization](https://en.wikipedia.org/wiki/Walk_forward_optimization), [walk-forward validation framework for microstructure signals](https://arxiv.org/pdf/2512.12924)
- Frameworks: [TradingAgents](https://github.com/TauricResearch/TradingAgents), [Qlib](https://github.com/microsoft/qlib), [RD-Agent](https://github.com/microsoft/RD-Agent), [FinRobot](https://github.com/ai4finance-foundation/finrobot), [FinGPT](https://github.com/ai4finance-foundation/fingpt), [FinRL](https://github.com/AI4Finance-Foundation/FinRL), [NautilusTrader](https://nautilustrader.io/), [NOFX](https://github.com/NoFxAiOS/nofx), [awesome-systematic-trading](https://github.com/wangzhe3224/awesome-systematic-trading), [machine-learning-for-trading](https://github.com/stefan-jansen/machine-learning-for-trading), [TimesFM](https://github.com/google-research/timesfm), [Kronos paper](https://arxiv.org/pdf/2508.02739)
