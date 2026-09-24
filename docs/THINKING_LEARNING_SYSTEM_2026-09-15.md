# A trader that learns — what it actually takes, on this data, on this PC
2026-09-15. Written after Dev's correction: "bots don't trade one strategy, they learn
while trading, test their own theories; the economics has to be deep enough to connect
the strings and propose strategies." This is the thinking, then the research, then
what exists, then the design, then the first slice that can run this week.

---

## 1. What "learns while trading" has to mean, concretely

A system learns only if something inside it CHANGES because of an outcome. Four things
have to change, and each needs its own ledger:

| what updates | from what evidence | the file that should own it |
|---|---|---|
| **how much to trust each strategy sleeve** (trend, carry, event theses, relative value) — per regime | each sleeve's realised net return vs what it promised | `hl/tracker.py` (exists, judges one score today) |
| **how much to trust the reasoner's own probabilities** ("70% oil up" — was it 70%?) | every written-first call, graded; Brier score by chain type, horizon, regime | `hl/predictions.py` (exists: hash-locked, random control arm — 13 made, **0 graded**) |
| **the weight on each cause-and-effect link** (oil → inflation expectations → yields → risk assets → alts) | measured response of the target to the shock, per horizon, per regime — NOT the LLM's opinion | `hl/graph.py` (exists as a display map; edges "measured or researched", no learned weights yet) |
| **the playbooks** ("if X escalates, this is the structure") | which playbooks paid, which didn't, in what state of the world | `hl/journal.py` reviews (exists, 75 reviews) |

Everything else — the debate agents, the memory, the reflection prompts — is decoration
unless those four ledgers fill and feed back. That is the whole design principle.

**The economics is the hypothesis generator, not the decider.** Deep economic
understanding is what proposes a chain worth betting on and says what would falsify
it. It does NOT set the numbers. The data sets the numbers, link by link, and the
written-first ledger says whether the understanding was any good. Dev's WTIOIL trade
is the template: a chain (US–Iran escalation → oil supply risk premium → WTI up), a
horizon, an instrument that expresses it, and an outcome that graded the reasoning.

---

## 2. What the research actually says (read this week; sources at the end)

**Learning trading agents (FinMem, FinAgent, TradingAgents, 2023–25).** Layered memory,
reflection on outcomes, bull/bear debate, multi-role agents. Attractive architectures.
Then the March-2026 survey "Agentic Trading: When LLM Agents Meet Financial Markets"
audited 77 such studies: **only 19 had a closed loop at all; 2 of 19 disclosed a
time-consistent train/test split; 1 of 19 stated a transaction-cost model; 0 of 19 were
reproducible.** Its verdict: "no agent framework is validated as systematically
superior." Its prescriptions are exactly a ledger discipline: an *outcome embargo*
("an episode recorded at time t cannot expose its outcome to retrieval until now ≥ t+k"),
provenance on every retrieved fact, time-decayed retrieval so old regimes fade, and an
explicit warning about the "oracle fallacy" — retrieving a past episode whose stored
note mentions what happened next.
→ **The differentiator is not a smarter agent. It is the honest loop nobody in the
literature has run.** That loop is what `predictions.py` and `tracker.py` were built
for. They are empty.

**Can an LLM forecast at all?** On 464 real binary events the best LLM scored Brier
0.135 vs the Metaculus crowd 0.149 and superforecasters 0.122; ForecastBench has
superforecasters at 0.076 vs GPT-4o 0.130; by late 2025 the gap had closed to ~0.02.
Calibration analysis: LLMs are **overconfident on high-probability events**. So a
reasoner's raw "80%" must be corrected against its own graded history before it sizes
anything. That correction IS the learning; it is what `newsystem.md` §12 calls LLM-XGB
(LLM understands, a small model calibrates). The correction can only be fitted once
there are graded calls. Again: the empty ledger is the bottleneck.

**Do structured events predict returns?** Han, Li, Qiao & Zheng (Dec 2025): extract
every news item into (subject, action, object) with an LLM, feed an attention model,
predict the cross-section. Out of sample: Sharpe 0.78 daily, 0.63 weekly — modest, real,
and *interpretable*. Confirms the two-stage split: LLM turns text into structure, a
statistical model learns what the structure is worth. No paper asks an LLM to "feel"
bullish or bearish and does well.

**Automated theory → test loops (RD-Agent, AlphaAgent, QuantaAlpha, XAlpha,
2025–26).** An LLM proposes a factor, writes it as code, backtests, reads the result,
proposes again. Results: IC ≈ 0.047 on Chinese equities for the best; RD-Agent reports
~2× a classic factor library. Two lessons transfer: (1) the loop needs an explicit
**alpha-decay / crowding penalty** or it re-discovers the same thing (AlphaAgent's
"regularized exploration"); (2) hundreds of tries per week means **false-discovery
control is mandatory** — the plan's §11.7 already says this.

**Weekly combined-indicator signals (CTREND, JFQA 2025; Cakici et al., IRFA 2024)** — see
`docs/RESEARCH_FEATURE_SETS_2026-09-14.md`. +3.87%/wk gross, +2.51%/wk in the largest
10% of coins, net-positive at 30–60 bps/trade, break-even 1.41%/trade. This is the
systematic *floor*: a sleeve that pays while the reasoning ledger fills.

---

## 3. What we have, measured today

| piece | state |
|---|---|
| prices | 172 coins, hourly, 2020-01 → 2026-08, 4.78M bars; **features for all 172 as of today** |
| crowd positioning | 172 coins, hourly, 2026-08-02 → yesterday, archive-fed daily |
| funding / OI / basis / cross-venue spread | `perp_state`, `cv_features` (177 coins with measured HL spread) |
| unlocks | 140 tokens, with sizes since 09-13 |
| macro | Fed funds + US 10y (daily, decades), EUR/USD, euro 10y, ECB rate, BRL, Fear&Greed, CPI for 164 countries, 6 policy rates. **Missing: oil, dollar index, inflation breakevens, VIX, S&P, gold** — every one of them is one FRED series (needs the free key; §7 "needs a free key" list) |
| prediction markets | Kalshi 8,000 markets, Polymarket 500, to 09-09 (now verified from the US) |
| news | `document` has 914 rows but they are mostly **not news**: govinfo *collection names*, exchange listings, GDELT stubs. The RSS/news collectors are not writing articles into the store. `event` and `event_outcome` tables: **0 rows**. The event-extraction stage does not exist yet |
| the reasoner's ledger | 13 reasoned calls, 0 graded; 54 random; `tracker` 37 runs of the composite score |
| regime read | `hl/regime.py`, computed live |

So: the *quant* half is real and large. The *reasoning* half has a hash-locked ledger,
a map, a journal — and no data flowing through them.

---

## 4. The design, as it should run on this PC every day

```
 04:00  Tier-0 (already running): collectors, features, positioning, unlocks, sync
 04:30  MEASURE   local projections re-fit for every admitted link (rolling window,
                  per regime, FDR-controlled)            -> data/links.db
 05:00  SLEEVES   each systematic sleeve emits today's book + a promised edge
                  (CTREND-weekly, carry-if-alive, relative-value, event overlays)
 05:10  ALLOCATE  meta-allocator sets sleeve weights from GRADED history per regime
                  (start: inverse-variance of last N net returns × regime match;
                   no RL until >1,000 graded days)      -> data/sleeves.db
 on event  WAKE   anomaly rule fires (calibrated thresholds) or a scheduled event
                  hits its window (the calendar, §14 of the plan)
           THINK  the reasoner (me, in chat, until a local model earns it):
                    1 event → structured (who/what/certainty/novelty/surprise)
                    2 chain: link1 → link2 → … → instrument, each link's MEASURED
                      weight & delay from links.db; the LLM proposes, data prices
                    3 priced-in check: prediction-market odds, positioning, funding
                    4 analogues: past events of the same TYPE and their outcomes
                      (embargoed: only outcomes already older than their horizon)
                    5 thesis → probability, horizon, invalidation, CHECKPOINTS
                      (what each intermediate link should do, by when)
                    6 payoff structure + least-crowded instrument
           WRITE  prediction row: chain + checkpoints + p + horizon + hash
                  (+ a random-arm twin, always)          -> data/predictions.db
 hourly    GRADE  every due checkpoint and every due call: right/wrong, Brier,
                  and WHICH LINK broke when the call was wrong
 weekly    LEARN  calibration curve per chain-type/horizon/regime → correction
                  applied to next week's probabilities; link weights re-fit;
                  sleeve trust re-weighted; scoreboard printed to Dev
 monthly   KILL   any sleeve / chain-type below its random arm after costs is retired
```

Three rules that make it honest, all from the survey and the plan:
1. **Written first, graded later, hash-locked.** Already how `predictions.py` works.
2. **Outcome embargo.** A past call's outcome is invisible to the reasoner until the
   call's horizon has fully passed. No "similar past trade" note may contain what
   happened after it.
3. **Forward only.** No backtesting the reasoner on old news. A 2026 model reading
   2022 headlines already knows 2022. That is the plan's §12.4 hard gate. The price
   is time: clean evidence accumulates at the rate the world produces events.

---

## 5. Connecting strings — three chains, each decomposed into testable links

The point of these is to show what "deep economics" has to look like when it is
written down for a machine to grade. Each link names its data and what would falsify it.

**Chain A — geopolitical supply shock (the WTIOIL template)**
event: credible escalation touching Gulf / Hormuz supply (type: *supply-shock threat*,
not "Iran" — pooled by type so N is in the hundreds, plan §11.4)
- L1 threat → oil: WTI/Brent up within hours; size scales with barrels-at-risk and
  spare capacity. Data: FRED DCOILWTICO / DCOILBRENTEU (missing key). Falsified if
  oil is flat 24h after a confirmed threat → the market judged it non-credible.
- L2 oil → inflation expectations: 5y breakeven up over days. FRED T5YIE (missing).
- L3 breakevens → real yields / dollar: 10y up (have), DXY up (missing DTWEXBGS).
- L4 dollar + yields up → risk assets down: S&P (missing SP500), BTC (have), and
  **high-beta alts more than BTC** (have; `hl/regime.py` beta).
- L5 the crypto-specific twist: energy cost → miners; oil-exporter liquidity;
  stablecoin flows from the Gulf — weak, keep as hypothesis, no weight until measured.
Instruments: WTIOIL perp on the builder dex (direct, L1 only — fewest links, highest
confidence), short high-beta alts vs BTC (L4, more links, wider uncertainty).
Checkpoints: oil +2% by 6h; breakevens +3 bp by 2d; alts underperform BTC by 3d.
Grading: not just "did BTC fall" but *which link broke* — that is the learning.

**Chain B — liquidity → stablecoins → crypto beta**
event: Fed/Treasury liquidity turn (rate path, TGA, bill issuance), or a big
stablecoin mint/burn
- L1 policy → front-end rates (have FEDFUNDS); L2 rates → dollar liquidity proxies
  (need TGA / RRP — FRED); L3 liquidity → stablecoin supply (need on-chain supply, a
  free source exists — DefiLlama stablecoins); L4 stablecoin supply Δ → BTC/alts over
  1–4 weeks (have prices).
Falsified per link. This chain is slow (weeks); it belongs to the weekly sleeve, not
the event wake.

**Chain C — supply event × crowd positioning (fully inside our own data today)**
event: a token unlock ≥ 1% of max supply within 7 days (have sizes since 09-13)
- L1 size × category (insiders/private sale vs ecosystem) → selling pressure
  (measure: event study on our own history as it accumulates; the research note says
  ~88% negative 72h around cliffs — treat as [TO-VALIDATE])
- L2 conditioning: funding positive + retail long share rising into the date
  (have `positioning`, `perp_state`) → crowd is on the wrong side → larger move
- L3 liquidity: thin HL book (have `cv_features.hl_spread_bps`) → move is larger but
  costlier to trade
Instrument: short the coin vs BTC over the window; size by measured spread.
This chain needs no new data. It is the first one the links engine can fit.

**What the reasoner adds that the quant layer cannot:** it knows Hormuz is a strait,
that "ecosystem" unlocks are often already vested to funds that don't sell, that a
Treasury refunding announcement matters more than a Fed speech. That knowledge picks
the chain and the checkpoints. It never picks the number.

---

## 6. Many strategies, learned trust — the sleeves

"Bots don't trade on one strat": the book is a portfolio of sleeves, each with its own
promised edge, each graded, each weighted by graded trust in the current regime.

| sleeve | horizon | evidence today | status |
|---|---|---|---|
| CTREND-weekly (28-indicator combination) | 1 week | published +2.5–3.9%/wk, survives costs, works in large coins; **not yet reproduced on our data** | build next (approved by Dev 09-14; not started) |
| hedged carry | days–weeks | Dev's cryptobot: the only survivor of walk-forward; carry paper: Sharpe 6.45 (2020–25) → negative 2025 | exists in `funding_hedged.py`; needs a live "is carry alive now" gate |
| event theses (chains A/B/C) | hours–days | ledger empty | start writing calls this week |
| relative value / cross-venue | hours | `cv_features` has the inputs; Jane-Street principle from the plan §2 | not built |
| 1-day reversal | 1 day | **dead** after costs on every coin set (09-13 test) | retired |

Meta-allocator v1: weight ∝ recent net edge / variance, per regime label, floored at 0,
re-fit weekly from `sleeves.db`. No reinforcement learning until there are >1,000
graded sleeve-days; the plan's §11.6 explains why (a simulator can't create evidence).

---

## 7. What this will NOT do, said now

- It will not have a validated reasoning edge in a month. Forward-only grading at
  5–20 events a day gives ~100–300 graded calls a month; a Brier difference between
  "me" and "random" needs a few hundred to mean anything. That is the squeeze in the
  plan's §13, and there is no honest shortcut.
- It will not measure Chain A until oil/breakevens/DXY/VIX are in the store. One free
  FRED key fixes all five series.
- It will not "learn economics". It learns *which of my economic stories pay, at what
  horizon, in which regime*, and it learns link weights. The stories still come from
  the reasoner.

---

## 8. The first slice — runnable this week, in order

1. **Keep the box awake** (`powercfg /change standby-timeout-ac 0`) and auto-start the
   backend + watchdog at logon. Without this nothing 24/7 is real. *(Dev: system
   settings — your commands.)*
2. **FRED key** → `macro_sources.py` gets WTI, Brent, 5y breakeven, DXY, VIX, S&P,
   TGA, RRP. One key, eight series, unblocks Chain A and B.
3. **Start the ledger, today.** Every day: I read the live feed + calendar + regime,
   write 3–5 chain-structured calls with checkpoints, each with a random twin;
   `predict.py --resolve` grades hourly under the watchdog. Weekly scoreboard to Dev.
   Cost: zero API (it is this chat). Value: the only thing that makes any of §1 learn.
4. **`hl/links.py`** — local projections per (shock series → target → horizon), rolling,
   per regime, FDR-controlled, results into `links.db`; first links fitted on data we
   already hold: funding→return, positioning→return, unlock-size→return, 10y→BTC,
   FEDFUNDS→BTC, Fear&Greed→alts-vs-BTC. Chain C fully; A/B once step 2 lands.
5. **Fix the news store** — `document` must hold articles, not collection names;
   then the event-extraction stage (LLM → strict struct) writes `event` rows. Until
   then the reasoner reads the live feed directly.
6. **CTREND sleeve** on our data (already approved) — the paying floor.
7. Then the meta-allocator over the sleeves, from graded results only.

Each step stops for Dev to see the real result. None of them is "done" until the
number is on his screen.

---

## Sources
- Agentic Trading: When LLM Agents Meet Financial Markets (survey, Mar 2026) — https://arxiv.org/html/2605.19337v1
- FinMem (ICLR 2024) — https://arxiv.org/abs/2311.13743 · TradingAgents — https://arxiv.org/html/2412.20138
- Evaluating LLMs on Real-World Forecasting Against Expert Forecasters (2025) — https://arxiv.org/html/2507.04562v3 · ForecastBench (ICLR 2025) — https://arxiv.org/pdf/2409.19839 · AI forecasting in 2026, 11 analyses — https://www.lesswrong.com/posts/a82q6yd8zKpYk56cF/ai-forecasting-in-2026-what-11-analyses-say
- Han, Li, Qiao, Zheng — Structured Event Representation and Stock Return Predictability (Dec 2025) — https://arxiv.org/abs/2512.19484
- RD-Agent write-up — https://saulius.io/blog/automated-quant-research-ai-agents-rd-agent · AlphaAgent — https://arxiv.org/html/2502.16789v2 · QuantaAlpha — https://arxiv.org/pdf/2602.07085 · XAlpha — https://arxiv.org/html/2607.08332
- The New Quant: survey of LLMs in financial prediction and trading — https://arxiv.org/html/2510.05533v1
- CTREND / Cakici et al. — see `docs/RESEARCH_FEATURE_SETS_2026-09-14.md`
- The plan this builds on: `newsystem.md` §0–4, §9, §11–14
