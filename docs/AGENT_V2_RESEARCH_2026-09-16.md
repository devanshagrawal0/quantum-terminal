# Agent v2 research dossier — memory graph, belief board, measured events, quant layer, compute tool, survival ladder, multi-agent evidence, information inventory, viewing, small-model reliability

2026-09-16. Written for Dev by a single research agent (no subagents). Every URL cited below was
fetched in this session with WebFetch or WebSearch; anything not fetched is marked [unfetched].
Where a paper's number is quoted, it is quoted as the paper states it; whether it was replicated
is stated separately. Plain English, terms explained on first use.

Status: IN PROGRESS — sections are appended as they are researched. Executive summary is written
last and placed here.

## Executive summary

(written at the end — see bottom of file for the "Executive summary (final)" section if this
placeholder is still here, the run was interrupted before the summary was written)

---

## What exists today (the ground truth this dossier designs against)

From `docs/HOW_IT_WORKS_2026-09-16.md`, `sim/*.py`, and the two exams:

- Event-driven simulator over 172 Hyperliquid coins, daily bars 2021→2026, time-locked (`sim/data.py AsOf`),
  coin names masked C1..C172, dates hidden. Wake-ups: weekly, regime flip, breadth ≥90%/≤10%, BTC >2.5σ day,
  |funding| >0.3%/day on 3+ coins, 2-day cooldown (`sim/run.py wake_reason`).
- Three model "hats" in `sim/investigator.py`: Investigator (thinking off, ≤3 rounds × 6 tool calls, JSON
  follow-ups), Strategist (thinking on, chains with mechanism/falsifier/checkpoint/order/confidence), Skeptic
  (thinking off, engine-built counter-dossier, veto/resize/replan/stand). No Risk hat, no Reviewer hat.
- Tools in `sim/tools.py`: market_table, regime, correlations (30d, on the fly), positioning, funding,
  funding_extremes, open_interest, fear_greed, macro_rates, scheduled_events (unlocks only), cross_venue,
  plus memory tools (evidence, similar, stops_report, insights, calibration, market_view, recall, write_note).
- Memory in `sim/memory.py`: flat SQLite — `experience` (one row per closed trade with features, thesis,
  confidence, net/excess/MFE/MAE, counterfactual grid, lesson; FTS5), `note`, `insight` (proposed→active→
  retired, ≥10 out-of-sample same-sign trades to activate), evidence (decayed, 90-day half-life, Thompson
  sample), similar (k-NN over standardised feature vectors). NO graph, NO links, NO belief board, NO event nodes.
- Empty or NULL: feat_cross / feat_xsec (beta, corr, residual, idio vol, clusters, RRG), feat_calendar,
  feat_onchain, feat_options, feat_deriv's z-score/cascade columns, `scheduled_event` beyond 142 unlock rows,
  `geo_event` (all earthquakes), prediction markets (stored, no tool), news (no historical store).
- Model: Qwen3.6-35B-A3B MoE (3B active) on CPU via llama.cpp, ~11 tok/s, OpenAI-compatible endpoint,
  `chat_template_kwargs.enable_thinking` toggled per call. Measured: knows rules but does not apply them
  (0.55× daily-move stops with vol printed), flips funding sign in 1 of 3 phrasings, arithmetic wrong with
  thinking off, chains events well with thinking on (~2 min per call).
- Terminal: `scripts/terminal.html` (3,190 lines, vendored three.js, no build step) served by
  `scripts/dashboard.py` (3,002 lines).

Design principle already decided and confirmed by the exams: the model proposes mechanisms and reads
evidence; the engine computes every number and every sign, prices links, checks rules, and sizes.

---

# A. AGENT MEMORY AS A GRAPH

## A(i) Findings, with URLs

**Zep / Graphiti — temporal knowledge graph for agents.** Paper: https://arxiv.org/abs/2501.13956 and
full text https://arxiv.org/html/2501.13956v1 ; docs https://help.getzep.com/graphiti/graphiti/overview ;
code https://github.com/getzep/graphiti
- Three sub-graphs: *episode* nodes (raw text/JSON as ingested), *semantic entity* nodes with entity edges
  ("facts"), and *community* nodes (clusters of strongly connected entities with a summary).
- **Bi-temporal edges** — every edge carries four timestamps: `t_created` / `t_expired` (when *we* learned
  and retired it — the "transaction" timeline) and `t_valid` / `t_invalid` (when the fact *was true* in the
  world). When a new fact contradicts an old one on an overlapping interval, the old edge's `t_invalid` is
  set to the new edge's `t_valid`. Nothing is deleted; you can query "what did we believe as of date X".
- Retrieval = three search functions (cosine on embeddings, BM25 full text, breadth-first graph walk over n
  hops) fused by rerankers (reciprocal rank fusion, maximal marginal relevance, episode-mention count,
  node-distance from a focal node, optional cross-encoder). Communities found by label propagation.
- Numbers (as stated by the authors, not independently replicated): DMR 94.8% (gpt-4-turbo) vs MemGPT
  93.4%; LongMemEval 71.2% vs 60.2% baseline with gpt-4o; median latency 2.6–3.2 s vs ~28–31 s baseline.
- README warning that matters to us: "very small models frequently emit JSON that doesn't match the
  requested schema, which surfaces as extraction failures" — Graphiti's entity/edge extraction is LLM-driven.

**A-MEM — Zettelkasten-style evolving notes.** https://arxiv.org/abs/2502.12110 ; full text
https://arxiv.org/html/2502.12110
- Each note stores: content, timestamp, LLM keywords, LLM tags, LLM contextual description, embedding,
  and a set of links. On insert: retrieve top-k (k=10) nearest notes by cosine, then an LLM decides which
  to link ("common attributes"). *Memory evolution*: the linked old notes' description/keywords/tags get
  rewritten so the summary of an old note reflects new evidence.
- LoCoMo multi-hop F1: 27.0 (A-MEM, gpt-4o-mini) vs 25.0 (LoCoMo baseline); **Qwen-1.5B 18.2 vs 9.1, Qwen-3B
  12.6 vs 4.6** — the gain is largest on small models. Ablation (gpt-4o-mini): no links & no evolution 9.7
  → links only 21.4 → full 27.0. So link generation carries most of the effect; evolution adds the rest.
  These are the authors' numbers; I found no independent replication.

**HippoRAG.** https://arxiv.org/abs/2405.14831 — builds a graph from OpenIE triples plus synonym edges;
retrieval runs Personalized PageRank from the query's entities. Claims up to +20% on multi-hop QA and
10–30× cheaper / 6–13× faster than iterative retrieval. Point for us: a *graph walk seeded at the entities
in the question* is a cheap way to pull in "everything connected to this coin/event" without an LLM.

**Generative Agents (Park et al. 2023).** https://arxiv.org/abs/2304.03442 ; full text
https://arxiv.org/html/2304.03442
- Retrieval score = recency + importance + relevance, each normalised to [0,1], weights all 1. Recency is
  exponential decay 0.995 per game hour since *last retrieved*; importance is a 1–10 LLM rating; relevance
  is embedding cosine.
- Reflection is triggered when the sum of importance of recent events exceeds 150; the agent asks the 3
  most salient questions, retrieves for each, writes insights *citing the memory ids as evidence*; leaf =
  observations, inner nodes = increasingly abstract thoughts (a tree).
- Ablation (TrueSkill μ, higher = more believable): full 29.9; no reflection 26.9; no reflection+planning
  25.6; no memory at all 21.2. The 2026 survey (below) quotes that without reflection behaviour degenerated
  to repetitive responses within 48 simulated hours.

**MemGPT / Letta.** https://arxiv.org/abs/2310.08560 — OS-style hierarchy: small in-context "core"
memory the model edits with function calls, plus recall (conversation search) and archival (vector)
stores; a "heartbeat" lets it chain calls. (The Letta docs URL https://docs.letta.com/concepts/memory
returned 404 — [unfetched].)

**Mem0.** https://arxiv.org/abs/2504.19413 — extract facts, then ADD/UPDATE/DELETE/NOOP against existing
ones. Graph variant adds ~2% over the base on LoCoMo (authors' number). Take-away: most of the value came
from the *update discipline* (dedupe, supersede) rather than from the graph itself.

**CoALA.** https://arxiv.org/abs/2309.02427 — working memory vs long-term memory split into episodic
(what happened), semantic (facts), procedural (rules/code); decision cycle = retrieve → reason → learn →
act, where "learn" means writing to each memory type. Letta, Mem0, LangChain all use this taxonomy
(LangChain memory concepts https://docs.langchain.com/oss/python/concepts/memory — hot-path writes vs
background consolidation; background needs a trigger/cadence).

**2026 memory surveys.** https://arxiv.org/html/2603.07670v1 ("Memory for Autonomous LLM Agents") —
three axes: temporal scope (working/episodic/semantic/procedural), substrate (context text / vectors /
structured DB / executable code), control policy (rules / prompted / learned). Says consolidation
(episodic → semantic) is an *open problem* with "dual-buffer consolidation (probation before promotion)"
proposed but largely unimplemented; only MemoryAgentBench tests forgetting and no system passes it;
MemoryArena shows systems near-perfect on LoCoMo drop to 40–60% on interdependent multi-session tasks.
Quotes Voyager 15.3× faster tech-tree progress, Reflexion 91% vs 80% pass@1. No finance systems covered.
https://arxiv.org/abs/2512.13564 ("Memory in the Age of AI Agents") — forms (token/parametric/latent),
functions (factual/experiential/working), dynamics (formation/evolution/retrieval); open: automation, RL,
multimodal, multi-agent, trustworthiness.

**Procedural memory.** https://arxiv.org/pdf/2512.10696 ("Remember Me, Refine Me") — skills/rules stored,
reinforced on success, retired on repeated failure, retrieved by similarity + historical success rate. The
fetch summary gave no concrete numbers; treat as a design pattern, not a measured result.

**Financial knowledge graphs.** FinReflectKG https://arxiv.org/abs/2508.17906 (KG from 10-K filings,
reflection-agent extraction 64.8% rule compliance — text extraction quality, no trading numbers). Search
results also surfaced FinKario (event-enhanced financial KG, https://arxiv.org/pdf/2508.00961 [unfetched]),
CEGNet (causal event KG for stock movement, Springer [unfetched]), Janus-Q (event-driven trading via reward
modelling, https://arxiv.org/pdf/2602.19919 [unfetched]). None report a costed, walk-forward trading result.

**Embargoing the future in an agent's memory (time-lock).**
- https://arxiv.org/html/2602.17234v1 ("All Leaks Count, Some Count More") — decomposes an LLM's rationale
  into claims and measures which claims are post-cutoff knowledge (Shapley-weighted). Stock ranking: 17% of
  decision-critical claims were leaked in baselines; their TimeSPEC (pre-cutoff-only retrieval, claim
  verification, closed-world constraint) cuts it to 0.1% and *the baseline's apparent skill disappears*.
- https://arxiv.org/html/2608.02985 ("Temporal Leakage in LLM Backtesting") — you cannot detect leakage from
  a backtest alone; need a cutoff regression-discontinuity or a matched clean control; single leaked
  document ≈ +0.01 Brier, 16 documents ≈ +0.04; proposes leakage-adjusted scores.
- https://arxiv.org/pdf/2601.13770 (LookAheadBench) — dual-period benchmark; fetch summary reports
  40–60% Sharpe inflation for equal-weight and 2–3× for momentum when future info leaks, and that date
  masking alone is insufficient because models reconstruct dates from context; combine date masking +
  entity masking + retrieval cutoffs. (Numbers as extracted by the fetch summariser from the PDF; I could
  not open the tables to confirm them — treat as indicative.)
- TradingAgents issue #805 https://github.com/TauricResearch/TradingAgents/issues/805 [unfetched, from
  search] — users report model-level future knowledge contaminating that framework's backtests.
Our masking (C1..C172, hidden dates) is the right instinct; these papers say it must be paired with a
*retrieval* cutoff (which `AsOf` gives) and, for any text we ever add, a claim-level leak check.

## A(ii) What is proven vs claimed

| Claim | Status |
|---|---|
| Linking new memories to old ones (A-MEM) helps small models most | Authors' ablation on LoCoMo; Qwen-1.5B/3B doubled multi-hop F1. Not independently replicated; benchmark is conversational QA, not trading. |
| Reflection (summaries citing evidence) prevents degeneration | Generative Agents ablation (TrueSkill 29.9 vs 26.9), one study, believability metric, not P&L. |
| Bi-temporal edges enable honest "as of" queries | Design fact (Graphiti implements it); no benchmark needed — it is a correctness property. |
| Graph beats flat vector store | Mem0's own graph variant: +2% only. Zep: big latency gain, modest accuracy gain. **Graph pays for relational questions ("what is connected to X"), not for lookups.** |
| Importance × recency × relevance retrieval | Generative Agents; widely copied; no ablation isolating the three weights. |
| Consolidation episodic → semantic | Open problem per both 2026 surveys; "probation before promotion" is exactly our insight lifecycle. |
| LLM backtests leak future knowledge unless retrieval is cut off AND text is masked | Three 2026 papers agree; magnitudes differ by task. |

## A(iii) Design recommendation for OUR system

**Keep SQLite. Add a graph as two tables, not a new database.** Graphiti needs Neo4j/FalkorDB and an
LLM that emits schema-perfect JSON for every extraction — the README itself warns small models fail at
this. Our nodes are *already structured* (coins, trades, tools, events are rows), so entity extraction by
LLM is unnecessary; the model is only needed to write *summaries* and to propose *mechanism* links.

```
node(id, kind, key, label, created_ts, observed_ts, attrs_json, summary, summary_version)
   kind ∈ {coin, event_instance, event_type, mechanism, belief, trade, decision, source, tool_call,
           insight, note, regime_window, cluster, macro_series}
edge(id, src, dst, rel, weight, n, tstat, horizon_days, sign, valid_from, valid_to,
     observed_at, expired_at, origin, evidence_json)
   rel ∈ {traded, cited, about, caused_by_claim, measured_response, co_moves, member_of,
          analogue_of, supports, contradicts, revised_to, triggered_wakeup, same_type}
   origin ∈ {engine_measured, engine_rule, model_proposed, human}
```
- **Bi-temporal on every edge** (`valid_from/valid_to` = when true in the world; `observed_at/expired_at`
  = when we could know it). `AsOf(t)` graph reads filter `observed_at <= t AND (expired_at IS NULL OR
  expired_at > t)`. A trade node's edges get `observed_at = close_ts` so nothing about an open trade leaks.
  An event's *outcome* edges get `observed_at = event_ts + horizon`.
- **Links are earned, not invented.** Three link origins, each with a rule:
  1. `engine_rule`: shared attributes (same coin, same event_type, same setup, same regime label, same
     cluster_id) — deterministic, free.
  2. `engine_measured`: co-movement links carry `weight = corr`, `n`, `tstat`, `horizon`; event→coin links
     carry the local-projection coefficient (Area C). Threshold to *exist*: |t| ≥ 3 after BH-FDR within the
     family (from newsystem §16.15), else the edge is stored with `status='unmeasured'` and weight NULL.
  3. `model_proposed`: the strategist's mechanism chains become `caused_by_claim` edges with weight NULL and
     confidence capped (Area B/C) until an `engine_measured` edge on the same (src,dst,horizon) exists.
- **A-MEM-style evolution, but engine-written.** When a new trade node links to an event_type node, the
  event_type's `summary` is regenerated by *code* ("7 unlock trades: 5 down into the date, median −4.1%,
  IQR …") and `summary_version += 1`. The model may add one sentence of interpretation, stored separately
  as a note, never overwriting the numbers.
- **Retrieval = graph walk + k-NN + FTS, fused.** For a candidate coin at time t: (a) 2-hop BFS from the coin
  node and from any event nodes within ±7 days (HippoRAG/Graphiti walk); (b) existing k-NN `similar`;
  (c) FTS5 `recall`; fuse by reciprocal rank fusion; rerank by Generative-Agents score
  `recency(90-day half-life, on closed_ts) + importance(|excess_bps| scaled) + relevance(feature distance
  or cosine)`. Return ≤12 items with node ids so the strategist can cite them.
- **Per decision, store** (a `decision` node): wake reason, the morning sheet hash, every tool call
  (existing log) as `tool_call` nodes with `cited` edges to the cards that used them, the cards, market
  view, chains (as `caused_by_claim` edges), skeptic verdicts, risk-hat verdicts, orders, and the
  belief-board snapshot ids. That is provenance you can replay in the terminal (Area I).
- **Reflection trigger** (Generative Agents): run the Reviewer hat when the sum of |excess_bps| of closes
  since the last reflection exceeds a threshold (start: 2,000 bps, tune to fire every ~10–20 closes), or
  every 20 closes, whichever first. Reflection output = ≤3 questions, each answered with cited node ids;
  stored as `insight(status=proposed)` — the existing quant gate then decides promotion.
- **Forgetting**: never delete; `expired_at` on edges whose measured link fails re-estimation; recency
  decay does the rest. MemoryAgentBench says nobody has solved selective forgetting — don't try to.
- **Embargo tests to keep forever**: (1) shuffle test — a graph read at t must be byte-identical whether or
  not future rows exist in the DB; (2) "cutoff discontinuity" — agent performance must not jump at the
  model's training cutoff month (2608.02985's route 1); (3) claim-level leak audit on a sample of chains
  when we add any text source.

## A(iv) Feature list — Area A (each: what — source — how verified)

1. `node` / `edge` tables added to `sim/memory.py` with bi-temporal columns — Graphiti 2501.13956 — test: as-of read at t excludes rows with observed_at>t.
2. Trade node created at *close* with observed_at=close_ts — Graphiti/our embargo rule — test: open-trade node invisible to `similar`/walk before close.
3. Event-outcome edges observed_at = event_ts+horizon — 2602.17234 — test: at t < horizon the edge is absent.
4. Deterministic shared-attribute links (coin/event_type/setup/regime/cluster) — A-MEM link generation without the LLM — test: inserting a trade creates exactly the expected edge count.
5. Measured co-movement edges with corr, n, t — newsystem §16.8 — test: edge weight equals the `correlations` tool output for the same window.
6. Edge `status='unmeasured'` for model-proposed links — A(ii) table — test: strategist chain with no measured edge is tagged and confidence capped.
7. Engine-written summaries on event_type nodes with version counter — A-MEM evolution — test: adding the 8th unlock trade increments version and changes the numbers.
8. Model interpretation stored as a note attached by edge, never overwriting numbers — Mem0 update discipline — test: summary text stable across model runs.
9. 2-hop BFS retrieval from coin + near-date events — HippoRAG / Graphiti — test: returns nodes reachable in ≤2 hops only.
10. Reciprocal rank fusion of BFS + k-NN + FTS — Graphiti — test: RRF ordering reproducible for a fixed seed.
11. Recency×importance×relevance rerank with 90-day half-life — Generative Agents — test: identical items differ in rank only by closed_ts.
12. Importance = |excess_bps| scaled to [0,1] by run-wide quantile — Generative Agents importance — test: top-decile excess trade ranks above median trade at equal recency/relevance.
13. `decision` node stores wake reason, tool calls, cards, chains, verdicts, orders — provenance rule (Agentic Trading survey) — test: replay reconstructs the decision JSON byte-for-byte.
14. `tool_call` nodes with `cited` edges from cards — Generative Agents citations — test: every card fact resolves to a tool_call id or is rejected.
15. Reflection trigger by cumulative |excess| threshold or 20 closes — Generative Agents (150 threshold) — test: counter resets on trigger; fires within bounds on the August run.
16. Reflection = 3 salient questions each answered with cited node ids — Generative Agents — test: insight text contains ≥1 valid node id per claim.
17. Reflections feed `insight(status=proposed)` only — our quant gate — test: no reflection creates an `active` insight directly.
18. `analogues(event_type)` = join over `same_type` edges with N, median, IQR — newsystem §14.5 — test: N equals count of closed trades of that event_type before t.
19. `expired_at` set on edges that fail re-estimation (|t|<3 or sign flip) — §16.15 — test: after a synthetic sign flip the edge is expired, not deleted.
20. Never-delete policy; forgetting by decay only — 2603.07670 survey — test: row counts monotone non-decreasing across runs.
21. Community/cluster nodes from residual-corr clustering (Area D) with `member_of` edges refreshed monthly — Graphiti communities — test: cluster membership as-of t uses only data ≤ t.
22. `regime_window` nodes (label, start, end) with trades linked — Graphiti temporal nodes — test: walk from a regime node returns only trades opened inside it.
23. Mechanism nodes (e.g. "supply overhang", "short squeeze", "dollar/real-yield tightening") as a small fixed vocabulary the engine seeds; strategist must pick or propose — A-MEM tags — test: every chain has a mechanism node id.
24. Proposed mechanism nodes require ≥3 uses + ≥1 measured edge to become `canonical` — probation-before-promotion (2603.07670) — test: status transitions logged.
25. `source` nodes for every data table with `about` edges to facts — provenance — test: every fact's source resolves to a table + timestamp.
26. Node/edge `origin` column (engine_measured / engine_rule / model_proposed / human) — §11.7 two-trap rule — test: UI colours differ; counts reported per run.
27. Shuffle test: graph read at t identical with/without future rows — 2602.17234 — test: automated in `scripts/selftest.py`.
28. Cutoff-discontinuity test on agent excess vs model training-cutoff month — 2608.02985 — test: no significant jump at cutoff (t<2).
29. Claim-level leak audit for any text source (sample 20 chains/run, flag outcome-like claims) — 2602.17234 TimeSPEC — test: leak rate reported per run.
30. Combined masking (coins, dates, and *magnitude rounding* of well-known prices like BTC) — LookAheadBench mitigations — test: BTC price never appears verbatim in prompts.
31. `recall` upgraded to FTS5 over node summaries + notes + lessons — Graphiti BM25 — test: query "unlock" returns event_type node first.
32. `link(a,b,why)` tool for the model, creating a `model_proposed` edge only — MemGPT/A-MEM — test: cannot create engine_measured edges.
33. `write_note` notes get keyword tags from a fixed vocabulary — A-MEM tags without LLM drift — test: tags ∈ vocabulary.
34. Node summaries rewritten only by code templates with numbers — Mem0 lesson (update discipline > graph) — test: template output deterministic.
35. Per-coin "dossier" view = BFS(2) from the coin node rendered as text for the investigator — HippoRAG entity-seeded walk — test: dossier contains only as-of facts.
36. Retrieval budget: ≤12 items, ≤1,500 tokens per hat — latency (Zep 90% latency reduction rationale) — test: token count asserted.
37. Memory consolidation job ("sleep-time") runs after settlement, not during decisions — LangChain background writes — test: decision wall-time unchanged by consolidation size.
38. Consolidation writes `semantic` nodes (facts with n) from episodic trades — CoALA episodic→semantic — test: each semantic node cites ≥3 episodes.
39. Procedural memory = active insights compiled to screens (Area E) with success-rate tracked and retired on failure — 2512.10696 — test: retirement fires after k failures.
40. Graph stats in run summary (nodes, edges by origin, unmeasured share) — honesty table habit — test: numbers printed.
41. Import of `decisions.jsonl` history into the graph (backfill) — provenance — test: August run's 3 decisions become decision nodes with correct edges.
42. "What changed since my last view" diff = edges with observed_at in (last_decision, t] — Zep incremental updates — test: diff empty when no new data.
43. Edge invalidation by contradiction: a new measured edge with opposite sign on the same (src,dst,horizon) expires the old one — Graphiti invalidation — test: old edge gets expired_at = new observed_at.
44. Belief nodes (Area B) linked `supports`/`contradicts` to evidence nodes — Generative Agents citations — test: belief confidence recomputable from linked edges.
45. Recency decay uses *last retrieved* as well as created — Generative Agents — test: retrieval updates `last_used_ts`.

---

# B. BELIEF BOARD / WORLD MODEL / HYPOTHESIS ENGINE

## B(i) Findings, with URLs

**LLM forecasting vs humans — what the numbers actually are.**
- Halawi et al. 2024, https://arxiv.org/abs/2402.18563 (full text https://arxiv.org/html/2402.18563): retrieval +
  reasoning + aggregation system. Brier 0.179 vs crowd 0.149 overall (accuracy 71.5% vs 77.0%); GPT-4 alone 0.208.
  Ablation: no fine-tuning 0.186; no retrieval + no fine-tuning 0.206 — **retrieval was worth ~0.02, fine-tuning
  ~0.007**. Ensembled 6 forecasts by trimmed mean. It *beats* the crowd only in a selective regime: when the crowd
  is itself uncertain (0.3–0.7) AND ≥5 relevant articles retrieved AND early in the question's life — 22% of
  questions, 0.240 vs 0.247. Calibration RMS 0.42 vs crowd 0.38. Lesson: an LLM forecaster is worth using
  *where the base rate is genuinely uncertain and evidence is plentiful*, and it should abstain elsewhere.
- Schoenegger et al. 2024, https://arxiv.org/abs/2402.19379: a crowd of 12 LLMs is statistically indistinguishable
  from the human crowd; showing an LLM the human median improved its accuracy 17–28% but simple averaging of human
  + machine beat that. **Anchoring on a crowd number helps a model.** (For us: the prediction-market odds and the
  funding/basis "market price of the view" are that anchor.)
- ForecastBench, https://arxiv.org/abs/2409.19839 (full https://arxiv.org/html/2409.19839): superforecasters Brier
  0.096, public 0.121, best LLM 0.122 (Claude-3.5-Sonnet). Giving models recent news did *not* help; the best
  prompts used "freeze values" (the current value of the series being forecast) plus a scratchpad. LLMs are worst on
  *combination* questions (joint probabilities of dependent events) — exactly what a chain of events is.
- KalshiBench, https://arxiv.org/pdf/2512.16030: LLMs systematically overconfident on real market questions; scale
  helps a little, does not fix it. (Fetch summary gave no ECE table.)
- "LLMs can teach themselves to better predict the future", https://arxiv.org/pdf/2502.05253 (full
  https://arxiv.org/html/2502.05253): self-play DPO on outcome-ranked reasoning traces from 9,800 Polymarket
  questions took Phi-4-14B Brier 0.221→0.200 and DeepSeek-R1-14B 0.211→0.197, matching GPT-4o (0.196). The ranking
  rule is simply |p − outcome|. **This is the cheapest documented route to a better-calibrated small model, and our
  decisions.jsonl + outcomes is exactly that dataset shape** (Area J).
- Tian et al. 2023 "Just ask for calibration", https://arxiv.org/abs/2305.14975: verbalised confidences from RLHF
  models cut expected calibration error by ~50% relative to token probabilities. So: ask for a number in the JSON,
  then *correct it through the model's own calibration table* (we already store calibration).

**Superforecasting practice (Tetlock / Good Judgment Project).** https://aiimpacts.org/evidence-on-good-forecasting-practices-from-the-good-judgment-project/
— a one-hour training in base rates / outside view / bias avoidance produced gains lasting ≥1 year; teams helped;
frequent *small* updates helped; GJP aggregate beat ordinary forecaster averages by >60% and intelligence analysts
by 25–30%; superforecasters' calibration error ≈0.01 and *rounding their probabilities hurt*. The practice is:
start from the outside view (base rate, "how often does this kind of thing happen"), adjust with the inside view,
update in small increments as news arrives, keep score.

**Belief states in LLM agents.**
- "Agentic Forecasting using Sequential Bayesian Updating of Linguistic Beliefs", https://arxiv.org/html/2604.18576v4:
  belief state = {probability, confidence low/med/high, key evidence for, key evidence against, open questions};
  each step ingests date-filtered search results, runs a leak classifier, then the LLM *rewrites the belief with an
  explicit reason for the probability change*. ForecastBench Brier-index 73.3 vs GPT-5 70.2; adjusted 71.0 ≈ human
  superforecaster median 70.9. Explicit likelihood-based Bayesian updates were tried and were "much worse" than the
  linguistic update (Appendix J). Failure mode: high run-to-run variance (σ=0.20) — over-updating.
- "When does belief-based agent memory help?" (Nous), https://arxiv.org/html/2606.22030: beliefs as categorical
  distributions per (entity, attribute) with Bayesian updates weighted by per-source reliability; the auditable
  artefact is the *delta* (how an observation changed the belief). Honest finding: on ordinary QA the Bayesian
  update was **inert** (last-write-wins scored the same, 36.8 vs 36.3 F1); it only paid when observations carry
  reliability scores and contradict each other (100% vs 67% for last-write-wins). Trust = min(provenance, content)
  stopped 50-message poisoning floods (0% success) at the cost of under-weighting legitimate low-trust corrections.
- AutoDiscovery (Bayesian surprise), https://arxiv.org/pdf/2507.00310: elicit prior and posterior probabilities by
  sampling the model before/after showing evidence; surprise = KL(prior‖posterior); MCTS over experiments; claims
  LLMs cannot combine priors with evidence without an explicit update step.
- POPPER (Stanford, ICML 2025), https://arxiv.org/pdf/2502.09858 and https://github.com/snap-stanford/POPPER
  [unfetched]: turn a free-form hypothesis into measurable *falsification* sub-tests, each yielding a p-value;
  convert to e-values (a betting-score version of a p-value that can be multiplied across sequential tests);
  reject the null when the product exceeds 1/α; Type-I error controlled by construction; claims ~10× faster than
  human scientists on biology hypotheses with comparable accuracy. Many published economics/sociology hypotheses
  failed its tests.

**Hypothesis→backtest loops in quant.**
- R&D-Agent-Quant (Microsoft), https://arxiv.org/abs/2505.15155 (full https://arxiv.org/html/2505.15155): research
  loop (hypothesis from domain priors) + development loop (code agent Co-STEER, real backtest) with a bandit
  scheduler choosing which loop to run. CSI300: IC 0.053 vs Alpha158 0.034, annualised return 14.2% vs 5.7%,
  max drawdown −7.4%. Out-of-sample 2024–25: CSI500 IC 0.029, NASDAQ-100 IC 0.016. 44 loops in 12 hours, <$10.
  Ablation: bandit scheduler (IC 0.053) > LLM-chosen (0.048) > random (0.045). The LLM never sees raw market data
  or split dates — only schema. Splits: train 2008–14, valid 2015–16, test 2017–20.
- AlphaAgent, https://arxiv.org/abs/2502.16789: three regularisers against alpha decay — originality (AST distance
  to existing factors), hypothesis–factor alignment (LLM checks the code matches the stated idea), complexity
  (AST size cap). Claims reduced decay on CSI500/S&P500; no numbers in the abstract.
- Alpha-GPT, https://arxiv.org/abs/2308.00016: human-in-the-loop alpha mining; EMNLP demo track; no numbers.
- QuantAgent, https://arxiv.org/abs/2402.03755: inner loop writer/judge over a knowledge base, outer loop tests in the
  real world and writes back; "provable efficiency"; numbers not in abstract.
- The AI Scientist, https://arxiv.org/abs/2408.06292: idea → experiment → paper → automated review at <$15 per paper;
  the automated reviewer is "near-human" on paper scores. (Its known failure modes — wrong numbers in write-ups,
  editing its own time limits — are in the paper body; not confirmed from the abstract.)
- AI co-scientist (Google), https://arxiv.org/abs/2502.18864: generate → reflect → rank (Elo tournament) → evolve →
  proximity (novelty) → meta-review; hypotheses compete in pairwise debates; validated in wet-lab (AML drug
  repurposing, liver fibrosis targets, bacterial gene transfer mechanism).

**Reasoning scaffolds — what is real.**
- Self-consistency, https://arxiv.org/abs/2203.11171: sample k chains, majority vote: GSM8K +17.9, SVAMP +11.0.
- Multi-agent debate (Du et al.), https://arxiv.org/abs/2305.14325 (full https://arxiv.org/html/2305.14325): 3 agents
  × 2 rounds: arithmetic 67→81.8, GSM8K 77→85, biography factuality 66→73.8, MMLU 63.9→71.1.
- **"Debate or Vote"**, https://arxiv.org/html/2508.17536v1 — on Qwen2.5-7B/32B and Llama-3.1-8B, majority voting
  alone got 0.769 average vs 0.711–0.738 for debate variants; more debate rounds *hurt* (arithmetic 0.99→0.67 at 5
  rounds); debate helped only with heterogeneous personas and by a hair (0.842 vs 0.824 on one MMLU subset). The
  authors prove debate is a martingale — expected belief does not change. **For a small open model, vote, don't
  debate.** Search also surfaced "Stay Focused: problem drift in multi-agent debate" https://arxiv.org/pdf/2502.19559
  [unfetched] and a matched-ceiling study https://arxiv.org/pdf/2605.09618 [unfetched] with the same conclusion.
- Tree of Thoughts, https://arxiv.org/abs/2305.10601: Game of 24 4%→74% with search over thoughts; cost is many
  calls (not quantified in abstract) — impractical at 2 min per thinking call on our CPU.
- Reflexion, https://arxiv.org/abs/2303.11366: verbal self-critique in an episodic buffer, retry; HumanEval 91 vs 80;
  needs a reliable success signal and can loop. Our success signal is the graded trade — reliable but delayed.
- Self-Ask, https://arxiv.org/abs/2210.03350: compositionality gap does not shrink with scale; explicit "Follow up:"
  questions + a search tool improves multi-hop — the pattern our investigator already uses.

**Leakage in LLM trading agents (belongs here because a belief board must be scored honestly).**
- Profit Mirage, https://arxiv.org/abs/2510.07920 (full https://arxiv.org/html/2510.07920): five LLM agents
  (QuantAgent, FinCon, TradingAgents, FinMem, …) lose 51–62% of Sharpe and 50–72% of return moving from Q2–Q3 2021
  (inside training data) to Q3–Q4 2024 (after cutoff). FinLake-Bench shows the models recall past prices (85%),
  event impacts (93%), rankings (90%), trends (90%). FactFin (counterfactual perturbations + code strategy + MCTS +
  RAG) improved out-of-sample return 31.9% and Sharpe 22.7% over baselines (authors' numbers).
- The Alpha Illusion, https://arxiv.org/abs/2605.16895: reported alpha from FinCon/FinMem/TradingAgents cannot be
  separated from temporal contamination, unmodelled frictions, short-window Sharpe noise, narrative fitting and
  hidden factor exposure; proposes tiered reporting P1–P6 and **"LLM as auditable information interface upstream of
  independent calibration, risk and execution"** — which is our architecture.

## B(ii) What is proven vs claimed

| Claim | Status |
|---|---|
| LLMs forecast about as well as the public, worse than superforecasters | Proven across 3 benchmarks with leak-free designs (ForecastBench, Halawi, Schoenegger). |
| Retrieval helps, news dumps do not | Halawi (+0.02 Brier from retrieval) vs ForecastBench (news did not help): *structured, relevant* retrieval helps; raw news does not. |
| Explicit belief state with for/against evidence and reasoned updates | One system (2604.18576) at superforecaster-median level on ForecastBench; numeric Bayesian update was worse; high run variance. Not replicated. |
| Bayesian belief memory beats last-write-wins | Only when sources carry reliability and contradict (Nous). In plain QA it was inert. |
| Debate improves answers | Du et al. yes on GPT-3.5/4; "Debate or Vote" no on 7B–32B open models — voting is the whole effect. |
| Self-consistency voting helps arithmetic/reasoning | Proven, large, cheap. |
| LLM-proposed hypotheses tested by backtest produce alpha | R&D-Agent-Quant has real OOS numbers (IC 0.016–0.029) on equities; every other quant loop reports in-sample only. |
| Sequential falsification with e-values | POPPER: Type-I control is a theorem; empirical power claims from authors. |
| Backtests inside the model's training window are contaminated | Proven (Profit Mirage, LookAheadBench, TimeSPEC). Our masking + AsOf mitigates but the leak audit (A) must run. |
| Small-model self-play on outcomes improves calibration | One paper, two 14B models, +7–10% Brier. Plausible and cheap for us. |

## B(iii) Design recommendation — the Belief Board

A belief is a *claim about the world with a probability that the engine can score*. It is not a trade.
Trades cite beliefs. Beliefs are revised by evidence with a logged delta. The model writes the words;
the engine owns the numbers.

```
belief(id, claim_text, kind, subject_node, horizon_days, resolves_by_ts,
       p_model, p_engine, p_final, conf_band, base_rate, base_rate_n,
       status ∈ {proposed, live, resolved_true, resolved_false, expired, retired},
       created_ts, observed_at, last_revised_ts, revision_n, owner_hat, mechanism_node)
belief_evidence(belief_id, node_id, side ∈ {for, against}, weight, reliability, added_ts, added_by)
belief_revision(belief_id, ts, p_before, p_after, reason_text, trigger_node, surprise_bits)
belief_score(belief_id, brier, log_score, resolved_ts)
```
- **Kinds of belief** (fixed vocabulary): `direction` (coin/cluster/BTC up or down over h), `event_outcome`
  (surprise sign of a scheduled print), `mechanism_active` (e.g. "unlock overhang is the dominant force on X"),
  `regime` (label persists ≥ h), `crowd` (funding stays extreme / flips), `link` (measured link holds this month).
  Each kind has an engine resolver that can mark it true/false from data alone.
- **Three probabilities, always shown side by side**: `p_model` (the verbalised number, per Tian et al.),
  `p_engine` (the outside view: base rate from `analogues`/links engine with n and IQR, or the market's own price —
  funding/basis/prediction-market odds, per Schoenegger anchoring), `p_final = calibrate(shrink(p_model → p_engine,
  k=base_rate_n/(base_rate_n+10)))` through the calibration table. The strategist sees all three and the shrink.
- **Confidence cap by measured link** (Area C): a `direction` belief whose mechanism has no `engine_measured` edge
  has `p_final` clamped to [0.35, 0.65] — "unmeasured chains are capped" made concrete.
- **Revision = a linguistic update with a numeric guard** (2604.18576's finding): the Reviewer hat rewrites
  {p, evidence for, evidence against, open questions, what would change my mind} when a new evidence node links to
  the belief; the engine rejects a revision that moves p by more than `max_step = 0.25` per event unless the
  surprise bits `−log2 P(observation | belief)` exceed 3 (Nous's surprise score) — an over-updating brake.
- **Self-consistency, not debate** ("Debate or Vote"): for the belief's number, sample the *thinking-off* model
  k=3 (cheap, ~20 s each) and take the median p; the thinking-on strategist is called once. No bull/bear rounds.
- **Falsification-first** (POPPER): every belief carries ≥1 falsifier that the engine can check on data
  (price level by day, funding flip, checkpoint miss). At close, falsifiers resolve the belief; the chain's
  broken link is named from *which* falsifier fired (we already grade checkpoint/falsifier per trade).
- **Scoring**: Brier and log score per belief, aggregated per kind, per hat, per mechanism, per regime; shown in
  the board and fed back as the calibration table the skeptic already reads. Keep-score is the single practice GJP
  found essential.
- **Selective forecasting** (Halawi): the strategist may return `no_belief` when `p_engine` base rate n < 8 or when
  the outside view and market price agree within 5 points — that is where LLM forecasts add nothing.
- **Bayesian-surprise wake-up** (AutoDiscovery): when a live belief's observed evidence has surprise ≥ 3 bits, the
  runner wakes the agent even if no other trigger fired. Ties the belief board to `wake_reason`.
- **Hypothesis engine (research loop, not decision loop)**: nightly, the Reviewer proposes ≤3 *link hypotheses*
  ("funding z < −2 → +3d return") as beliefs of kind `link`; the engine tests each with the local-projection code
  (Area C) under BH-FDR; survivors become `engine_measured` edges; R&D-Agent-Quant's bandit picks which family to
  test next based on recent hit rate. This is the loop that "finds what it doesn't have."
- **Leak defence for beliefs**: any belief text containing a coin name or a date is rejected (masking); claim-level
  audit sample per run (Area A).

## B(iv) Feature list — Area B

1. `belief` table with claim, kind, subject, horizon, resolves_by — 2604.18576 schema — test: every strategist order cites ≥1 belief id.
2. Fixed belief-kind vocabulary with an engine resolver per kind — POPPER measurable implications — test: 100% of resolved beliefs were resolved by code, not by the model.
3. `p_model` / `p_engine` / `p_final` stored separately — Tian 2023 + Schoenegger anchoring — test: all three non-null on every live belief.
4. Shrinkage of p_model toward base rate with k = n/(n+10) — GJP outside view — test: n=0 gives p_final = p_model after calibration; n=90 gives ≈ base rate.
5. Calibration mapping applied to p_final from the stored calibration table — LEARNING_ENGINE_V2 rule 6 — test: bucket 0.7 with realised 0.5 maps down.
6. Confidence clamp [0.35,0.65] for beliefs with no measured link — Area C cap — test: unmeasured chain cannot produce p_final=0.8.
7. `belief_evidence` rows with side for/against and reliability — Nous — test: reliability ∈ (0,1]; engine_measured evidence reliability = 1.0, model_proposed 0.5.
8. `belief_revision` log with p_before/p_after/reason/trigger — Nous "delta is the artefact" — test: replay of revisions reproduces p_final.
9. Max step 0.25 per revision unless surprise ≥ 3 bits — over-updating brake (2604.18576 variance finding) — test: synthetic 0.9→0.2 rejected without surprise.
10. Surprise bits = −log2 P(obs | belief) computed by engine — AutoDiscovery/Nous — test: a 3σ move under a "calm" belief yields > 3 bits.
11. Surprise wake-up in `wake_reason` — AutoDiscovery — test: fires on the August BTC −8% day if a "range" belief was live.
12. Median-of-3 thinking-off samples for p_model — self-consistency, "Debate or Vote" — test: variance of p across 3 samples logged; median used.
13. No bull/bear debate rounds; skeptic remains a single pass — "Debate or Vote" martingale result — test: A/B in sim (Area F) decides if even the skeptic stays.
14. Every belief has ≥1 engine-checkable falsifier — POPPER — test: belief without falsifier rejected at write.
15. Falsifier resolution names the broken link in the lesson — our lesson writer — test: lesson text includes falsifier id.
16. Brier + log score per belief on resolution — GJP keep-score — test: sums match hand calc on 10 beliefs.
17. Scores aggregated per kind/hat/mechanism/regime and shown to the skeptic — calibration feedback — test: JSON present in skeptic prompt.
18. `no_belief` allowed when base-rate n<8 or |p_engine − market price| < 0.05 — Halawi selective regime — test: strategist output accepted with empty orders.
19. Market-price anchor: p_engine from funding/basis/prediction-market odds when available — Schoenegger — test: BTC "up 7d" belief shows the implied anchor when a Kalshi market exists.
20. Base rate with n and IQR from `analogues` shown next to the claim — Tetlock outside view, §14.7 — test: N=3 renders as N=3.
21. Nightly link-hypothesis proposals (≤3) of kind `link` — R&D-Agent-Quant research loop — test: rows appear after settlement, not during decisions.
22. Engine tests link hypotheses with local projections + BH-FDR — §11.7 — test: p-values and q-values stored.
23. Bandit over hypothesis families by recent hit rate — R&D-Agent-Quant bandit > LLM > random — test: family pick distribution shifts after synthetic wins.
24. Originality check: new hypothesis text/feature AST must differ from existing — AlphaAgent — test: duplicate rejected.
25. Complexity cap on hypothesis expressions (≤3 features, ≤2 operators) — AlphaAgent — test: rejected above cap.
26. Hypothesis–code alignment check (feature names in code ⊆ names in the stated hypothesis) — AlphaAgent — test: mismatch rejected.
27. Elo-style tournament among live `mechanism_active` beliefs per coin, updated by resolution outcomes — AI co-scientist — test: Elo monotone in win/loss.
28. Belief "what would change my mind" field, required — superforecasting practice / 2604.18576 open questions — test: non-empty.
29. Belief expiry at resolves_by_ts with status `expired` and Brier scored against the last p — GJP — test: no live belief past its horizon.
30. Belief board snapshot id stored on each decision node — provenance — test: snapshot reproducible from revisions ≤ t.
31. Kind `regime` beliefs auto-created by the engine from the regime label with base-rate persistence — freeze values (ForecastBench) — test: persistence rate computed from history.
32. Kind `crowd` beliefs ("funding stays < −0.3% for 3 days") with engine resolver — our crowd data — test: resolves from funding table.
33. Combination-question guard: a chain belief's p_final ≤ min(p of its links) — ForecastBench weakness on joint events — test: chain p never above weakest link.
34. Belief text masked (no coin names, no dates) — leak defence — test: regex-free check via the coin map: any real symbol in text rejects the write.
35. Per-run belief statistics: count, resolved, Brier by kind, over/under-confidence — honesty table — test: printed in summary.json.
36. Reviewer hat rewrites belief fields on new linked evidence (linguistic update) — 2604.18576 — test: revision row written with reason.
37. Reliability-weighted evidence sum shown to the strategist as "for: 3 (w 2.4) / against: 2 (w 1.9)" — Nous — test: weights sum correctly.
38. Provenance cap: model_proposed evidence cannot raise reliability above 0.5 — Nous min(provenance, content) — test: attempt is clamped.
39. Beliefs of kind `link` become graph edges on promotion — Area A — test: promoted belief has an edge id.
40. Outcome-ranked trace dataset export (prompt, trace, p, outcome, |p−o|) — 2502.05253 — test: file grows by one row per resolved belief.
41. Hat-level Brier comparison (strategist p vs median-of-3 vs engine base rate) — GJP aggregation — test: table in summary; the worst source is flagged.
42. Belief "priced-in" field: |CAR over T−7..T−1| / vol for the subject — newsystem §16.13 — test: computed by engine, shown on the board.
43. Thompson-sampled probation for beliefs of a mechanism with poor Brier — LEARNING_ENGINE_V2 rule 1 — test: mechanism never fully silenced.
44. Abstention rate monitored; if >70% of decisions produce no belief, flag — Halawi/our exam ("over-fires abstain") — test: metric in summary.
45. Belief board as-of query for the terminal (Area I) — Graphiti point-in-time — test: board at t excludes revisions after t.

---

# C. EVENTS → PRICE, MEASURED

Terms once: an **event study** measures how a price behaved around a dated event compared with what it
"should" have done (the *abnormal return*, AR = actual − expected; **CAR** = cumulative AR over a window).
A **local projection** (LP) is a regression of the future change of y at horizon h on a shock today; one
regression per h gives the whole response curve with error bars. **Consensus** is the median forecast before
a release; **surprise** = actual − consensus, usually standardised by its historical standard deviation.

## C(i) Findings, with URLs

**Event-study method.** https://mike-data-analysis.share.connect.posit.cloud/sec-event-studies.html (Data
Analysis guide, ch. 39): estimation window 90–250 days with a 6–45-day gap before the event; event window
1 day for timestamped announcements, 2–10 days for slow events; market model AR; tests: cross-sectional t,
Patell (standardised residuals), BMP (event-induced variance), **Kolari–Pynnönen adjustment for clustered
event dates** — multiply the BMP statistic by √[(1−r̄)/(1+(n−1)r̄)] where r̄ is the average pairwise residual
correlation. Small samples: "a few dozen carefully curated cases" can work if the window is sharp; run one
parametric and one rank test and require agreement. Kolari & Pynnönen RFS 2010 abstract page
https://academic.oup.com/rfs/article-abstract/23/11/3996/1605665 [unfetched, from search].
For crypto this matters enormously: 172 coins reacting to one FOMC date are ~1 event, not 172.

**Local projections — how to run them.** Montiel Olea & Plagborg-Møller, Econometrica 2021,
https://joseluismontielolea.com/lp_inference_ecta.pdf: use **lag-augmented** LPs (add lags of the outcome and
shock as controls); then plain heteroskedasticity-robust (White) standard errors are valid — no HAC needed;
valid for persistent data and horizons up to ~⅓ of the sample. Inoue, Jordà & Kuersteiner
https://arxiv.org/abs/2306.03073: precision of a single-horizon estimate, shape across horizons, and
significance each need a different inference procedure. Jordà & Taylor's JEL survey (NBER w32822) PDF did not
parse — [unfetched]. Stata `lpirf` manual surfaced in search as a reference implementation [unfetched].

**Fed → Bitcoin, measured.**
- NY Fed staff report 1052 (Benigno & Rosa, Feb 2023) https://www.newyorkfed.org/research/staff_reports/sr1052:
  intraday event study; "Bitcoin is orthogonal to monetary and macroeconomic news" over their sample — a
  puzzle the authors flag. This is the null we must beat.
- Search result (Research in International Business and Finance 2022, "Monetary policy shocks and Bitcoin
  prices", ScienceDirect 403 — [unfetched]): on FOMC days a 1 bp unexpected rise in the 2-year yield ↔ −0.25%
  BTC, comparable to gold; Karau (2023) finds the contractionary effect *after 2020* only.
- ScienceDirect (April 2026, "Scheduled FOMC statements and intraday macro event risk in cryptocurrency
  markets", 403 — [unfetched], numbers from the search snippet): volatility jumps 0.44 pp (BTC) and 0.50 pp
  (ETH) above matched controls; volume 2.4–2.8× — the *vol* effect is robust even when the *direction* is not.
- https://arxiv.org/abs/2311.10739 (MSM-VAR, monthly 2010–2023): monetary-policy uncertainty lowers BTC
  returns by −0.028 in the calm regime and −0.44 in the volatile regime — regime-conditioning is mandatory
  (newsystem §11.5).
- https://arxiv.org/html/2604.08825 (2026): Qwen2.5-7B scored 118k StockTwits $FED messages hawkish/dovish;
  the resulting expectations index Granger-causes BTC at lags 2–6 days, ranked 6th of 19 predictors, and
  mattered most in the 2022 tightening. Modest effect; shows a 7B model *can* build a macro-expectations
  series — but only forward-only for us (no time-locked social archive).
Conclusion: the Fed→BTC link exists after 2020, is regime-dependent, is strongest in *volatility* and in
*surprise* terms, and disappears in samples that include 2014–2019. Any link we store must carry its sample.

**Macro surprises — how they are built and where consensus comes from.**
- Fed note https://www.federalreserve.gov/econres/notes/feds-notes/macroeconomic-news-and-stock-prices-over-the-fomc-cycle-20201014.html:
  surprise = actual − Bloomberg median, divided by its historical SD; 94 series (69 activity, 25 price);
  a 1-SD activity surprise → +0.06% S&P daily; price surprise → −0.03%; together ~20% of inter-FOMC
  variation. Bloomberg consensus is paid; free substitutes: FRED/ALFRED *vintages* (first-release values,
  https://fred.stlouisfed.org/docs/api/fred/releases_dates.html — `releases/dates` with `realtime_start`
  gives every release date; first-print values via ALFRED), BLS schedules (CPI page
  https://www.bls.gov/schedule/news_release/cpi.htm — 8:30 ET, prior years archived, ICS subscription),
  FOMC calendar https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm (2021–2027 listed,
  statements, minutes 3 weeks later, SEP meetings starred). **Consensus without Bloomberg**: (a) the market's
  own price — CME FedWatch (site timed out — [unfetched]; derives from 30-day fed-funds futures, which FRED
  does not carry historically), (b) prediction markets: Kalshi candlesticks (1-min/1-h/1-day) and a
  *historical* endpoint for archived markets, public market data without auth
  (https://docs.kalshi.com/llms.txt → get-market-candlesticks, get-historical-market-candlesticks,
  quick_start_market_data); Polymarket `/v2/prices-history` per outcome token with bucketed history
  (1-min ≥7 days, 5-min ≥60 days, 30-min ≥90 days, 3-h/12-h forever), no auth
  (https://docs.polymarket.com/market-data/prices-order-books.md). Our 8,500 stored Kalshi/Polymarket markets
  are the consensus source for "what did the market expect" on CPI/FOMC from 2024 on.

**Token unlocks (the best-measured crypto event).** Keyrock, "From locked to liquidity: what 16,000+ token
unlocks teach us" https://keyrock.com/from-locked-to-liquidity-what-16000-token-unlocks-teach-us/ — 16,000+
unlocks across 40 tokens, ETH-beta-normalised: 90% negative pressure; decline starts ~30 days before, price
stabilises ~14 days after; large (5–10% of supply) unlocks fall 2.4× harder; team unlocks −25%, ecosystem
unlocks +1.18%, investor unlocks small (OTC/hedged); volatility peaks day 1. Practice: exit 30 days before,
re-enter 14 days after. Not peer-reviewed; a single vendor study; consistent with our own `hl/unlocks.py`
observations and with the 2025-26 kill test's "unlock landmine" case. Our test: replicate on our 142 unlock
rows with residual returns (Area D) before trusting the −25% number.

**Exchange listings.** ChainCatcher 2024 report https://www.chaincatcher.com/en/article/2175717 — 10
exchanges; Binance best day-7 mean *and* median; OKX positive mean/negative median (outliers); most medians
negative by day 30; exchanges that list more tokens show weaker 30-day performance. CoinDesk 2023 (search
snippet, [unfetched]): 26 coins, +41% day 1 after Binance listing, +24% by day 3; Messari 2021 Coinbase +91%
in 5 days (earlier era). Pattern: announced listings rally *into* the date; surprise listings jump on day 1;
both fade by day 30 → "scheduled ⇒ fade, surprise ⇒ follow" (newsystem §16.13) holds here.

**ETF flows.** SSRN 6592830 "The Price Impact of Spot Bitcoin ETF Flows" (SSRN 403 — [unfetched]; numbers
from the search snippet): 5 largest US spot ETFs, Jan 2024–Apr 2025, 313 days; flows explain 21% of daily
return variance; $100M net flow ↔ +53 bp same day (OLS) / +74 bp (IV); predicts next-day return; **no reversal
at 1–20 days**; flows↔returns feedback loop. Farside https://farside.co.uk/btc/ [unfetched, search] is the
free daily tape (history from Jan 2024).

**Funding extremes → forward returns.** Presto Research
https://www.prestolabs.io/research/can-funding-rate-predict-price-change — BTC on Binance 2021–24: funding
*changes* explain 12.5% of *same-week* price variance but R² ≈ 0 for next period on a single asset;
cross-sectional funding momentum across the top-50 had a "highly favourable" Sharpe with extreme turnover.
Search snippets: the hedged carry (short perp / long spot) Sharpe 6.45 for 2020–25, 4.06 from 2024, negative in
2025 (arXiv 2510.14435 "Cryptocurrency as an investable asset class" [unfetched]). This matches our
memory: only carry survived, and it is fading. **Recommendation: measure funding→return as a link with LP on
*residual* returns, cross-sectionally, and expect a small number.**

**Liquidation cascades / OI–price divergence.** https://cryptodaily.co.uk/2026/08/seven-liquidation-cascades-crypto-crash-models
— seven cascades 2022–25: price-based "critical slowing down" appeared before 5 of 7, absent before the two
tariff-news shocks → endogenous build-up vs exogenous shock; slippage-at-risk (order-book) led the Oct-2025
event. Amberdata https://blog.amberdata.io/leverage-liquidations-the-31b-deleveraging: OI +82% ($30B→$54.7B)
while price peaked earlier; funding 29.9% APR before the break ("above 15% APR historically signals crowded
longs"); OI −42% after; liquidation intensity >4.82% approached a 5% "cascade threshold"; $31.4B liquidated in
2025, 60% longs. Vendor analytics, not peer-reviewed; the thresholds are theirs. Our `feat_deriv` cascade
columns should compute exactly these (OI change vs price change, funding APR, liquidation share of OI) and be
*tested* as a wake-up, not assumed.

**Stablecoin depegs / hacks.** Search found narrative pieces (Chainalysis, Coindesk) and one 2026 paper
"Tracing stablecoin contagion during the USDC depeg" (https://pith.science/paper/2606.07442 [unfetched]);
USDC fell to $0.87, CEX outflows $1.2B/hour, only USDC-linked assets showed price deviation. No clean CAR
study of hack→token found; DeFiLlama hacks feed (Area H) is the data to build one.

**Causal discovery tools.** Tigramite https://github.com/jakobrunge/tigramite — PCMCI (assumes causal
stationarity, no contemporaneous links, no hidden variables), PCMCI+ (contemporaneous), LPCMCI (latent
confounders), J-PCMCI+ (multiple datasets); tests ParCorr/RobustParCorr/GPDC/CMIknn; `CausalEffects` class;
Python 3.10+. Lead-lag literature (search): BTC Granger-causes altcoins at high frequency with small caps
lagging (Springer 2026, paywalled [unfetched]); transfer entropy finds direction where linear Granger does not
(PMC7514459 [unfetched]); kimchi-premium lag structure is asymmetric and time-varying (MDPI 403 —
[unfetched]). Take-away: run PCMCI+ on daily residual returns + funding + OI + macro as a *hypothesis
generator* for links, then confirm each with LP; never trade a PCMCI edge directly (stationarity is violated in
crypto — §11.5).

## C(ii) Proven vs claimed

| Link | Evidence quality |
|---|---|
| Unlock → negative drift starting ~30 d before, 2.4× for 5–10% supply | One vendor study on 40 tokens; direction widely corroborated; magnitudes unreplicated. |
| Fed surprise → BTC down (post-2020) | Several academic papers; NY Fed finds orthogonality in older samples; sign robust post-2020, size ~0.25%/bp (one paper). |
| FOMC → vol/volume spike | Robust (matched controls). |
| ETF flow → same-day return, no reversal | One SSRN paper, 313 days; strong R²; plausibly a mechanical flow effect. |
| Funding extreme → reversal (single asset) | Presto: R² ≈ 0 next period. Cross-sectional version has a signal with turnover cost. |
| OI/price divergence + high funding → cascade | Vendor case studies; 5/7 early-warning hit rate for endogenous cascades. Untested as a rule. |
| Listing → +day-1, fade by day 30 | Multiple vendor reports; agrees across years. |
| PCMCI/transfer entropy on crypto | Methods sound; crypto applications mostly descriptive; none traded with costs. |

## C(iii) Design recommendation — the links engine and the event store

**Event store (fills the empty `scheduled_event` and `feat_calendar`).**
```
event_type(id, name, family ∈ {macro_release, cb_decision, unlock, listing, delisting, hack, depeg,
           etf_flow_day, opex, governance, regulatory, cascade}, scheduled BOOL, default_horizons)
event_instance(id, event_type, entity, scheduled_ts, actual_ts, ts_precision, consensus, consensus_source,
           realised, surprise_raw, surprise_z, surprise_source, observed_at, valid_from, source_url)
event_outcome(instance_id, target ∈ {BTC, ETH, cluster_k, coin}, horizon_h ∈ {1h,4h,1d,3d,7d,14d,30d},
           ar, car, resid_car, session_bucket, computed_at)   -- observed_at = actual_ts + h
```
- Bitemporal (§14.7). `surprise_z` = (realised − consensus)/SD(past surprises of this type) — the Fed-note
  recipe; consensus from ALFRED first-print + prediction-market price at T−1 when available; otherwise
  `consensus NULL` and `surprise` undefined (never faked).
- Seed sources: FOMC calendar (2021–27), BLS CPI/NFP/PCE(BEA) schedules with archives, FRED `releases/dates`,
  DefiLlama unlocks (have), HL universe diff (have), Farside ETF daily tape (2024→), DeFiLlama hacks,
  Deribit expiries (rule: monthly last Friday 08:00 UTC), Kalshi/Polymarket markets mapped to instances.

**Links engine (`links` table = `engine_measured` edges in Area A).**
```
link(id, shock_type, shock_var, target, horizon_h, regime, beta, se, tstat, n_events, n_eff, q_fdr,
     sample_start, sample_end, estimator ∈ {LP_lagaug, CAR_KP}, sign_stable_k_of_m, updated_at, status)
```
- Estimator 1 (scheduled/dated events): CAR on **residual** returns (Area D) with BMP + Kolari–Pynnönen
  correction for clustered dates; report median and IQR as well as mean; `n_eff` = number of distinct event
  dates, not coin-events.
- Estimator 2 (continuous shocks: funding z, OI change, surprise z, ETF flow, 10y change): lag-augmented LP
  per horizon h ∈ {1,3,7,14} days with White SEs; controls = 2 lags of target and shock; sample ≥ 3h·3
  observations; run per regime label and pooled.
- Admission: |t| ≥ 3 (Harvey-Liu-Zhu bar from §16.15) after BH-FDR q ≤ 0.10 *within the family*, AND sign
  agreement in ≥ 3 of 4 non-overlapping sub-periods, AND an economic mechanism node attached. Otherwise
  `status='unmeasured'` (edge exists, weight NULL) or `status='rejected'`.
- Re-estimation monthly with an exponential weight (half-life 365 days) so 2021 links fade; store every
  vintage (never overwrite) so the terminal can show how a link drifted.
- **What this coin did around this event type**: `analogues(event_type, target=coin)` = join event_outcome
  for this coin (own history) → if n < 5, widen to its cluster → if n < 5, widen to all coins; always
  return `{n, level ∈ {coin, cluster, market}, median, p25, p75, hit_rate}` — §14.7's "N=3 renders as N=3".
- **Confidence cap from measured link strength** (the rule Dev asked for): for a chain whose weakest link has
  measured `(beta, se)`, cap the belief's `p_final` at `Φ(|beta|/se) · hit_rate` shrunk toward 0.5 by
  n_eff/(n_eff+20); a chain with any `unmeasured` link is capped at 0.65; a chain with a `rejected` link is
  refused.
- **Priced-in score** on every scheduled event instance: |resid CAR over T−7..T−1| / resid vol — shown to the
  strategist; "scheduled ⇒ fade, surprise ⇒ follow" becomes a measured prior per event type, not a slogan.
- First links to build, in this order (data we have): funding_z → resid return (13 months, 172 coins);
  unlock size/type → resid CAR (142 rows, ETH/BTC beta-normalised like Keyrock); OI change × price change
  regime → next-3d resid return; breadth extremes → BTC 3d; Fear&Greed → alt resid 7d; then FOMC/CPI surprise
  → BTC/ETH/cluster (after the calendar is seeded, 2021→ gives ~40 FOMC and ~60 CPI instances — small; report
  it small).
- PCMCI+ nightly on (BTC, ETH, cluster residual indices, funding median, OI total, DXY, 10y, F&G) with lags
  1–5 days as a *hypothesis generator* feeding the belief board's `link` beliefs (Area B). Stationarity check
  per window; never admit a PCMCI edge without the LP confirmation.

## C(iv) Feature list — Area C

1. `event_type` / `event_instance` / `event_outcome` tables, bitemporal — §14.5 — test: as-of query hides outcomes before actual_ts+h.
2. FOMC dates 2021–2027 seeded from the Fed calendar with statement time 14:00 ET — federalreserve.gov — test: 8 rows per year, times in UTC correct for DST.
3. CPI/NFP/PCE schedules seeded from BLS/BEA archives with 08:30 ET — bls.gov schedule — test: every month 2021→ has a CPI instance.
4. FRED `releases/dates` ingest for all US releases — FRED API — test: release count per year matches FRED.
5. ALFRED first-print values as `realised` — FRED vintages — test: CPI first print ≠ revised value on known revision months.
6. Consensus from prediction-market price at T−1 when a matching market exists — Kalshi/Polymarket APIs — test: CPI-month markets mapped for ≥80% of 2025 releases.
7. `surprise_z` standardised by type-specific SD of past surprises — Fed note — test: SD computed only from instances before each release.
8. `consensus NULL ⇒ surprise NULL` (no fabrication) — honesty rule — test: no surprise without consensus_source.
9. Fed blackout windows derived (2nd Saturday before → day after) — §14.4 — test: `in_fed_blackout` flag correct for 2025 meetings.
10. Collision flag when two events within 48h — §14.4 — test: FOMC+opex coincidences flagged.
11. Unlock instances from `unlocks.db` with type (team/investor/ecosystem/community) — Keyrock — test: type distribution reported.
12. Listing/delisting instances from `hl_universe_changes` — our data — test: every universe change has an instance.
13. ETF flow days from Farside daily tape — SSRN 6592830 — test: 2024-01-11 onward continuous.
14. Hack instances from DeFiLlama hacks endpoint with loss/mcap — Area H — test: ≥100 rows 2021→.
15. Deribit monthly/quarterly expiry instances by rule — §14.2 — test: last Friday 08:00 UTC each month.
16. `event_outcome` computed on residual returns at 1h..30d with session bucket — §16.13 — test: CAR equals sum of AR.
17. CAR significance with BMP + Kolari–Pynnönen clustered correction — RFS 2010 — test: 172 coins on one date give n_eff=1.
18. Rank test alongside parametric; agreement required — event-study guide — test: both stats stored.
19. Lag-augmented LP estimator with White SEs — Montiel Olea & Plagborg-Møller — test: reproduces textbook IRF on synthetic AR(1).
20. Horizons 1/3/7/14 d; horizon ≤ ⅓ sample enforced — same — test: refuses h=14 with n<42.
21. Per-regime and pooled estimates stored — 2311.10739 regime dependence — test: both rows exist.
22. Admission rule |t|≥3 & BH-FDR q≤0.10 & 3-of-4 sign stability & mechanism node — §16.15 — test: synthetic noise families admit ~0.
23. Monthly re-estimation with 365-day half-life weights; vintages kept — §11.5 — test: vintage count grows monthly.
24. `analogues()` widening coin→cluster→market with level label — §14.7 — test: N and level correct on a coin with 2 unlocks.
25. Median/p25/p75/hit-rate on every base rate — §14.7 — test: no bare mean returned.
26. Confidence cap from weakest measured link — Dev's rule — test: chain with t=1 link cannot exceed p 0.6.
27. Refuse chains with a `rejected` link — same — test: strategist order dropped with reason.
28. Priced-in score per scheduled instance — §16.13 — test: equals |resid CAR(−7..−1)|/resid vol.
29. Scheduled-vs-surprise prior per event type measured (fade vs follow hit rates) — listings/unlock evidence — test: table rendered.
30. Funding_z → resid return link (first link) — Presto/our data — test: LP output with n, t at 4 horizons.
31. Cross-sectional funding-momentum link (rank of funding change → next-week rank of return) — Presto — test: IC by week with SE.
32. Unlock size × type → resid CAR link replicating Keyrock windows (−30..+14) — Keyrock — test: our numbers vs theirs reported side by side.
33. OI change × price change quadrant feature and its 3-day link — §16.6 — test: four quadrants populated.
34. Funding APR > 15% + OI at 90-day high → "crowded" wake-up candidate, tested not assumed — Amberdata — test: hit rate of subsequent −5% within 7d vs base rate.
35. Critical-slowing-down indicator (rolling AR(1) of residual returns, rolling variance) — seven-cascade study — test: rises before ≥1 of the 2025 cascades in our data.
36. Endogenous vs exogenous tag on cascade instances (was there a scheduled/news shock within 24h?) — same — test: tag present.
37. ETF flow → BTC same-day/next-day LP — SSRN 6592830 — test: coefficient sign positive, no 1–20d reversal check reported.
38. Fed-surprise → BTC/ETH/cluster LP with post-2020 sample flag — Karau / NY Fed null — test: pre-2020 sample flagged as "orthogonal" if that is what we find.
39. FOMC vol-jump feature (realised vol on meeting day vs matched control) — 2026 FOMC paper — test: ratio > 1 on average.
40. Monetary-policy-uncertainty proxy (Kalshi Fed-decision market entropy) — 2311.10739 — test: entropy series exists from 2024.
41. PCMCI+ nightly hypothesis generator over macro+crypto daily series — tigramite — test: output edges written as `link` beliefs, never as measured links.
42. Transfer-entropy lead-lag BTC→cluster residuals at 1–3 day lags — search literature — test: BTC→alt TE > alt→BTC TE on average.
43. Small-cap lag feature: yesterday's BTC residual move as a predictor for small-cap cluster today — Springer 2026 [unfetched] — test: LP coefficient with cost-adjusted P&L.
44. Link vintages drift chart data (beta over time) for the terminal — §11.5 — test: JSON endpoint returns series.
45. Event wake-up: scheduled instance within 3 days for a held/candidate coin — §14.3 — test: `wake_reason` includes "event".
46. In-position event check: "trim X before <event> on <date>" action rows — §14.3(b) — test: generated for a position with an unlock in 5 days.
47. `event_study(event_type, target, window)` tool for the investigator returning CAR path + n_eff — Self-Ask tools — test: tool logged with stamps.
48. `links(target)` tool listing measured links into a coin with t and horizon — Area A edges — test: returns only admitted links as-of t.
49. Every link row carries `sample_start/sample_end` and the estimator name — honesty — test: non-null.
50. Link report page: family, admitted/unmeasured/rejected counts, FDR q — §11.7 — test: rendered in terminal.

---

# D. CROSS-SECTIONAL QUANT LAYER

Terms once: **beta** = how much a coin moves per 1% BTC move; **residual (idiosyncratic) return** = the
part of a coin's move BTC does not explain; **shrinkage** = pulling a noisy estimate toward a sensible
prior so a 30-day beta of 3.2 does not get trusted as 3.2; **HRP** = a way to split risk across clusters
of correlated assets without inverting a covariance matrix; **RRG** = a 2-D chart of relative strength vs
its momentum against a benchmark; **meta-labeling** = a second model that decides *whether/how much* to
take a first model's signal; **Kelly fraction** = the bet size that maximises long-run growth (full Kelly)
— practitioners use a fraction of it.

## D(i) Findings, with URLs

**Crypto factor structure.**
- Liu, Tsyvinski & Wu, JF 2022 (SSRN page https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3379131
  [unfetched, search snippet]): crypto market, size, momentum three-factor model explains the ten
  characteristic long-shorts that work.
- CTREND (Fieberg, Liedtke, Poddig, Walker, Zaremba), JFQA Nov 2025,
  https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/trend-factor-for-the-cross-section-of-cryptocurrency-returns/4C1509ACBA33D5DCAF0AC24379148178:
  ML aggregation of 28 technical (price+volume, multi-horizon) signals over 3,000+ coins 2015–22;
  robust across 55,296 design variants (search snippet), survives costs, persists in big liquid coins,
  not subsumed by known factors. Exact decile spreads not in the abstract.
- Cakici, Shahzad, Będowska-Sójka & Zaremba, IRFA 2024 (search snippet; SSRN 4295427 [unfetched]): 40
  characteristics; key predictors **price, past alpha, illiquidity, momentum**; simple models as good as
  complex ones; alphas mostly in small/illiquid/volatile coins and *from the long side*.
- "From Hypotheses to Factors: Constrained LLM Agents in Cryptocurrency Markets", https://arxiv.org/html/2604.26747v1:
  LLM proposes falsifiable hypotheses → constrained point-in-time factor DSL → deterministic gates (mean IC
  and IC-t thresholds on train only); splits 2020–22 train / 2023 valid / 2024–26 pure OOS; 5 bps one-way
  costs; ~25 factors over 5 rounds; ridge-combined equal-weight portfolio 44.6% annualised, Sharpe 1.55 in
  the 2024–26 OOS after costs; **cap-weighted versions performed poorly** (small-cap alpha, capacity-limited);
  "scarcity and trend" hypotheses stable, "range/volume recovery" noisy. This is the closest published
  analogue to what we are building, on crypto, with an honest OOS.
- Lee & Wang, JFQA 2025 "Variance decomposition and cryptocurrency return prediction",
  https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/variance-decomposition-and-cryptocurrency-return-prediction/9995E58095453CB44A3BC3C9C111969F:
  higher variance → lower next-week return, driven by **positive signed-jump variance and jump-robust
  variance**, strongest in small/illiquid/retail/positive-sentiment coins (lottery preference).
- "Correlation Without Factors in Retail Cryptocurrency Markets", https://arxiv.org/html/2412.04263v1:
  mean pairwise correlation 54–60%; a 14-coin portfolio has only N* ≈ 2 effective independent assets; the
  data fit an *isotropic* (everything-equally-correlated) model better than a linear factor model (χ² 21 vs
  573). Implication stated by the author: BTC-beta hedging may be ineffective; diversification ~1/√N*.
- "Crypto Pricing with Hidden Factors", https://arxiv.org/abs/2601.07664: Giglio-Xiu three-pass latent
  factors on weekly data; premia differ materially from Fama-MacBeth once latent factors are controlled;
  state variables include Fear & Greed, Altcoin Season Index, hacked-value/mcap.
- Search snippet (2026, unfetched): APC factor model on 38 cryptoassets 2018–2026 finds two regimes —
  "systemic stress" with common share >55% and "speculative" <30% — i.e. **the share of variance explained by
  the market factor is itself a regime label.**
- Idiosyncratic vol: Izadyar & Zamani https://arxiv.org/abs/2211.13274 — investor-base growth (subreddit
  followers) raises idio vol controlling for size/momentum/liquidity/volume. Search snippet: idio vol is
  *positively* priced in crypto (ScienceDirect [unfetched]) — opposite of the equity puzzle; do not assume
  the equity sign.

**Estimation choices.**
- Beta shrinkage (search results, tandfonline 2025 "Adaptive Beta Shrinkage" [unfetched]; UCLA notes
  [unfetched]): Blume = ⅔·β̂ + ⅓·1; Vasicek = Bayesian, shrink more when the standard error is larger,
  toward the cross-sectional mean β. Vasicek is the right one for 172 coins with different histories.
- Covariance shrinkage (search results): Ledoit–Wolf linear; nonlinear QIS "quadratic inverse shrinkage"
  (https://github.com/Jebel-Quant/shrinkage [unfetched]); a 2026 arXiv comparison
  https://arxiv.org/html/2601.20643v1 [unfetched]. The Ethereum-scale MPT paper
  https://arxiv.org/html/2605.20528v1 used a 60-day window with Ledoit–Wolf and mean shrinkage λ=0.5 on
  116M accounts / 4,562 tokens, and found **entry month explained 70–79% of return variance; allocation choice
  almost nothing; cap-weighting beat every MPT strategy**. Sizing sophistication is second-order to timing
  in crypto.
- HRP (López de Prado 2016; Wikipedia summary https://en.wikipedia.org/wiki/Hierarchical_Risk_Parity):
  distance d = √(½(1−ρ)), single-linkage tree, quasi-diagonalisation, recursive bisection with
  inverse-variance; Monte Carlo out-of-sample variance HRP 0.067 vs IVP 0.093 vs CLA 0.116. Crypto
  applications (Springer/ScienceDirect, search [unfetched]) report HRP handles tail risk better than IV/MV.
- Stable clustering: https://arxiv.org/abs/2505.24831 — Louvain community detection + consensus clustering
  over 5 years of daily closes; consensus clusters that persist are used for portfolios; positive and stable
  up to a 14-day horizon, tighter tail control. Take: cluster *stability* across windows is the quality
  metric, not modularity on one window.
- Volatility-managed momentum (search snippets; ScienceDirect 403 / Springer paywalled — [unfetched]):
  risk-managing crypto momentum raised weekly return 3.18%→3.47% and Sharpe 1.12→1.42; another paper nearly
  doubled Sharpe with a constant 12% vol target; crypto momentum crashes are sharp, not prolonged.
- Correlation regimes: BTC–S&P correlation 0.01 (2017–19) → 0.36 (2020–21) → 0.738 at FTX (search snippet);
  https://arxiv.org/pdf/2512.12815 (DCC-GARCH): BTC–equity correlation rose after the Jan-2024 ETF approval;
  BTC–gold ~0/negative; BTC–DXY negative and stable. Chow test on rolling correlations is the standard break
  test (search snippet). Our `corr_break_flag` needs a *test*, not a threshold.
- RRG (Julius de Kempenaer; https://www.relativerotationgraphs.com/blog/resources/construction-of-relative-rotation-graphs):
  RS line = coin/benchmark; RS-Ratio = normalised trend of the RS line (100 = benchmark); RS-Momentum =
  normalised rate of change of RS-Ratio, leads RS-Ratio; exact formulas are proprietary — the public
  construction is a z-scored ratio and its ROC (StockCharts ChartSchool, search [unfetched]).
- Meta-labeling (Hudson & Thames replication https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/):
  random-forest secondary model on S&P futures raised mean-reversion accuracy 17%→63% (precision
  0.17→0.20) and trend accuracy 48%→55%; Sharpe improved; **they had not implemented bet sizing** — the
  probability→size map is still the missing piece in the public literature.
- Fractional Kelly (search snippets, practitioner guides): half-Kelly keeps ~75% of growth with far smaller
  drawdowns; full Kelly sees 50–80% drawdowns in 1,000-bet simulations; use 25–50% of Kelly because the edge
  estimate is wrong. No academic paper fetched; standard practice.
- Breadth / dominance / altseason (search snippets, vendor pages): the Altcoin Season Index (share of top
  coins beating BTC over 90 days) is a *lagging confirmation*; the useful signal is the convergence of falling
  BTC dominance, rising ETH/BTC and rising breadth. No predictive study found — treat as descriptive state.

## D(ii) Proven vs claimed

| Item | Status |
|---|---|
| Market/size/momentum explain the crypto cross-section | Published JF; replicated by many. |
| Trend/technical aggregate (CTREND) survives costs in liquid coins | JFQA with a 55k-variant robustness sweep — strongest single crypto factor result. |
| Simple > complex ML; price/alpha/illiquidity/momentum | IRFA 2024; consistent with our own kill test. |
| LLM-proposed factors with gates give OOS Sharpe 1.5 | One 2026 arXiv, small-cap capacity-limited, 2-year OOS. |
| Signed-jump variance → lower returns | JFQA 2025; one paper. |
| Correlation ≈ isotropic 0.55–0.6; N* ≈ 2 | One arXiv on 14 retail coins; consistent with common experience; implies clusters may be weak. |
| HRP lower OOS variance than IV/MV | Monte Carlo from the inventor + several applied papers. |
| Vol-managed momentum improves Sharpe | Multiple papers; sizes vary. |
| Allocation choice barely matters vs entry timing | One large on-chain study, 60-day windows. |
| RRG | A chart convention, no predictive study. |
| Meta-labeling improves precision | Replications on equities; sizing map unproven. |

## D(iii) Design recommendation — exactly what to compute for `feat_cross` / `feat_xsec`

Daily job after the 23:00 bar, from daily closes we already have (all windows in trading days; all
estimates as-of t; stored per (coin, day)):

| Column | Computation | Window / cadence |
|---|---|---|
| `beta_btc_raw`, `beta_btc_se` | OLS of coin log return on BTC log return with intercept | 60d rolling, daily |
| `beta_btc` | Vasicek shrink: β = (β̂/se² + β̄/τ²)/(1/se² + 1/τ²) with β̄ = cross-sectional median β̂, τ² = cross-sectional var of β̂ | daily |
| `beta_eth` | same, on ETH residual of BTC (two-stage) | daily |
| `r2_btc` | R² of the 60d regression | daily |
| `resid_r_1d` | r − β_btc·r_BTC (β from t−1 to avoid look-ahead) | daily |
| `resid_mom_7d_skip1`, `resid_mom_30d_skip1` | sum of resid_r over (t−8..t−2), (t−31..t−2) | daily |
| `idio_vol_30d` | std of resid_r, annualised; also EWMA λ=0.94 | daily |
| `signed_jump_var_30d` | Lee–Wang: Σ r² over |r| > 3·bipower σ, split by sign; needs hourly bars — we have them | daily |
| `corr_btc_30d`, `corr_btc_90d` | Pearson on log returns | daily |
| `corr_matrix_60d` (table `xsec_corr(day, i, j, rho)`) | Ledoit–Wolf shrunk correlation of *residual* returns; store lower triangle | weekly (Mon), 60d |
| `corr_stress_matrix` | same on the worst-decile BTC days in the last 365d only | monthly |
| `common_share` | share of variance of the first principal component of the 60d return matrix | weekly — regime label: >55% stress, <30% speculative |
| `neff` | N/(1+(N−1)ρ̄) effective independent assets | weekly |
| `cluster_id`, `cluster_stability` | consensus clustering: hierarchical (d = √(½(1−ρ))) on residual corr, cut for 5–8 clusters, run on 3 overlapping 90d windows; stability = Jaccard of memberships | monthly |
| `corr_break_flag`, `corr_break_p` | Chow test on the 30d vs 90d BTC correlation with rolling structural-break p; flag when p<0.01 | daily |
| `rrg_x`, `rrg_y` | RS = close/BTC close; rrg_x = 100 + 10·z(RS 10d SMA / RS 40d SMA − 1) over 250d; rrg_y = 100 + 10·z(ROC_10(rrg_x)) | daily |
| `breadth_1d`, `breadth_7d`, `breadth_above_sma50` | share of universe with r>0 / above SMA50 | daily |
| `btc_dominance_proxy`, `eth_btc_trend` | from our universe mcap where available; ETH/BTC 30d slope | daily |
| `hrp_weight` | HRP over cluster covariance (Ledoit–Wolf) for the tradable universe | weekly |
| `size_resid_vol` | risk hat input: position notional = risk_budget / idio_vol_30d (never total vol) | at order |
| `stress_margin_use` | portfolio loss under a 3σ BTC move using β and the stress matrix vs HL margin | at order |

**Sizing rule for the Risk hat (no model call):** `size = base × f(p_final)` where f is the calibrated
probability mapped through fractional Kelly: `f = clip((2·p_final − 1) / (target/stop), 0, 1) × 0.25`
(quarter-Kelly), then × vol scale (12% annual target / idio_vol) and cluster cap (≤2 positions per
cluster, ≤40% of risk in one cluster), and the stress-margin check. This is the meta-labeling→size map the
literature leaves open, made explicit and testable.

**Re-estimation cadence:** betas/corr daily (cheap); matrices weekly; clusters monthly with a stability
report; stress matrix monthly. Store every vintage.

## D(iv) Feature list — Area D

1. `beta_btc_raw` + SE from 60d OLS — standard — test: matches numpy on one coin.
2. Vasicek-shrunk `beta_btc` toward the cross-sectional median — beta shrinkage literature — test: high-SE coins shrink more.
3. Blume fallback when N<30 coins — same — test: used only when cross-section is thin.
4. `beta_eth` two-stage — §16.8 — test: ETH's own beta_eth = 1, beta_btc from stage 1.
5. `r2_btc` — §4 of HOW_IT_WORKS ("this coin is 92% BTC") — test: shown as a fact in the skeptic dossier.
6. `resid_r_1d` with lagged beta (no look-ahead) — time-lock — test: recomputing with future beta changes values.
7. `resid_mom_7d_skip1`, `resid_mom_30d_skip1` — §16.1 — test: NULL rate 0 after backfill.
8. `idio_vol_30d` + EWMA — §16.14 — test: stop distance shown in *idio* daily moves too.
9. Signed-jump variance from hourly bars — Lee & Wang JFQA — test: positive-jump decile has lower next-week return in our data (report either way).
10. `corr_btc_30d/90d` — existing tool parity — test: equals `correlations` tool.
11. Weekly Ledoit–Wolf residual correlation matrix stored — shrinkage literature — test: positive-definite.
12. Stress matrix on worst-decile BTC days — §16.14 — test: mean ρ higher than normal matrix.
13. `common_share` (PC1 variance share) weekly — 2026 APC regime paper — test: >55% during the 2022 and Oct-2025 stress windows.
14. `neff` effective assets — 2412.04263 — test: ≈2–4 in stress, higher in calm.
15. Consensus hierarchical clusters (5–8) with Jaccard stability — 2505.24831 — test: stability reported monthly.
16. Cluster residual index (equal-weight resid returns per cluster) — §16.8 — test: sums to ~0 across clusters daily.
17. Cluster rotation table (7d/30d cluster index returns) exposed to investigator — Dev's "money moving down the risk curve" — test: tool `rotation` returns ranked clusters.
18. `corr_break_flag` via Chow test p<0.01 — search literature — test: fires at FTX week in 2022 data.
19. Break-trigger event id linking to the event store — §16.8 — test: nearest event within ±3 days attached.
20. RRG x/y per coin vs BTC with 10/40-day construction — de Kempenaer — test: quadrant transitions logged.
21. RRG quadrant as a categorical feature (leading/weakening/lagging/improving) — same — test: distribution shown.
22. Breadth features (1d, 7d, above-SMA50) — existing wake-up parity — test: equals runner's breadth.
23. ETH/BTC 30d slope and dominance proxy — altseason convergence heuristic — test: computed daily.
24. Altseason score = share of top-50 beating BTC over 90d — vendor definition — test: 0–100, lagging flagged in docs.
25. HRP weights weekly for the tradable universe — López de Prado — test: sum to 1, no negatives.
26. HRP vs inverse-vol vs equal-weight OOS variance report on our universe — HRP Monte Carlo — test: numbers printed per year.
27. Quarter-Kelly size map from p_final and target/stop — practitioner guidance — test: p=0.5 gives size 0.
28. 12% annual vol target scale on idio vol — vol-managed momentum papers — test: high-vol coin gets smaller notional.
29. Cluster caps (≤2 positions, ≤40% risk per cluster) — §16.14 — test: third same-cluster order rejected.
30. Stress-margin check under 3σ correlated move — §16.14 — test: order rejected when projected loss > margin buffer.
31. `size_in_idio_daily_moves` shown in skeptic dossier — HOW_IT_WORKS §4 — test: present.
32. CTREND-style aggregate: ridge on 28 technical signals to predict next-week resid return, trained on ≤t — CTREND — test: IC(h) curve with SE reported before use.
33. Simple-beats-complex guard: any ML aggregate must beat rank-average of its inputs OOS — Cakici et al. — test: comparison table.
34. Long-side bias flag: report alpha by side — Cakici finding — test: side split in summary.
35. Cap-weighted vs equal-weighted evaluation of any cross-sectional signal — 2604.26747 negative — test: both reported.
36. Illiquidity feature (Amihud log, winsorised, median) filled — §16.3 / Cakici predictor — test: NULL rate 0.
37. Past-alpha feature (60d intercept of the beta regression) — Cakici predictor — test: computed.
38. Idio-vol sign check in our data (positively priced?) — ScienceDirect [unfetched] — test: decile table reported with t.
39. Investor-base proxy (Reddit/X follower growth) *forward-only* — 2211.13274 — test: series exists from now on.
40. Regime label upgraded: (BTC trend) × (common_share regime) × (vol tercile) — §16.11 — test: 12-cell label; per-cell trade counts.
41. Correlation heatmap endpoint (coin×coin, cluster-ordered by the HRP tree) — Dev's heatmap — test: JSON served.
42. Correlation-over-time endpoint (mean ρ, PC1 share, neff series) — Dev's "market becomes one trade" — test: series served.
43. Beta-vs-idio map endpoint (x=beta, y=idio vol, colour=cluster) — Dev's map — test: served.
44. Entry-timing attribution: per-trade P&L split into market (β·r_BTC) vs residual — 2605.20528 finding — test: sums to net.
45. Signal capacity estimate (ADV × participation) per coin — 2604.26747 capacity issue — test: reported for small caps.
46. Every feature carries `computed_with_data_through` = t — time-lock — test: audit query passes.

---

# E. THE AGENT COMPUTES WHAT IT LACKS

## E(i) Findings, with URLs

**ReAct**, https://arxiv.org/abs/2210.03629 — interleave "thought / action / observation"; +34 pp on ALFWorld
and +10 pp on WebShop over prior methods; failure mode named by the authors: reasoning derailed by
uninformative tool results. Our investigator already runs this loop with JSON follow-ups.

**Voyager**, https://arxiv.org/abs/2305.16291 — the three ideas that matter for us: (1) a *skill library* of
executable code where a skill is stored only after it ran successfully (execution = verification), retrieved by
embedding; (2) iterative prompting with *environment feedback, execution errors, and self-verification*; (3) an
automatic curriculum. Numbers: 3.3× more items, 2.3× longer distances, 15.3× faster tech-tree; GPT-4 via API,
no fine-tuning. Ablations are in the paper body (not confirmed from the abstract).

**Skill libraries in 2026.** SkillOps https://arxiv.org/html/2605.13716v1 — treats a skill library as software
with technical debt (redundant clones, stale clones, **missing validators**, interface drift, low-utility skills);
per-skill Utility U(s), Failure-risk F(s), Validation-gap G(s); five rule-based gates (utility, compatibility,
validator-required, redundancy by body-hash, risk propagation through the dependency graph) with "nearly zero
library-time LLM calls"; under 15–90% degraded libraries of 200–2,000 skills it kept 79.5% task success vs 35.9%
for plain retrieval. Search also surfaced Group-of-Skills retrieval, SkillGraph, Skill-as-Pseudocode, and
"Skill is Not One-Size-Fits-All" (87% of tasks have at least one model that gains nothing from a given skill —
skills must be validated *per model*) — all https://arxiv.org/pdf/2605.xxxxx [unfetched].

**Data-analysis agents and how badly they verify themselves.**
- DS-1000 https://arxiv.org/abs/2211.11501 — 1,000 StackOverflow-derived numpy/pandas/scipy tasks; Codex-002
  43.3%; evaluation accepts wrong code only 1.8% of the time thanks to test execution + API constraints.
- InfiAgent-DABench https://arxiv.org/abs/2401.05507 — 257 closed-form questions over 52 CSVs; ReAct agent with
  a Docker Python sandbox; their fine-tuned DAAgent beats GPT-3.5 by 3.9 pp.
- **Sanity Checks for Agentic Data Science** (Microsoft) https://arxiv.org/abs/2604.11003 — two cheap
  perturbation checks (label shuffling, noise injection) in the PCS framework; on 11 real datasets an agent's
  affirmative conclusion was *not supported* in 6; "self-reported confidence is poorly calibrated to the
  empirical stability of its conclusions." This is the verification gate we need: re-run the agent's
  computation on shuffled labels; if the "finding" survives the shuffle it was noise.
- **Right-for-Wrong-Reasons** https://arxiv.org/html/2601.00513 — 7–9B models reach correct answers via flawed
  steps 50–69% of the time (Qwen-2.5-7B 69.3%); calculation errors dominate (60.3%); a step-level Reasoning
  Integrity Score with a distilled classifier (F1 0.86, 100× faster) catches it; retrieval helps (d 0.23–0.93);
  **meta-cognitive "reflect on your answer" prompts hurt in 78% of conditions** — pseudo-reflection amplifies
  errors. Direct implication for our exams: do not ask the small model to check its own arithmetic; have code
  check it.
- Property-based testing of LLM code (search snippets; ACM FSE 2025 https://doi.org/10.1145/3696630.3728702
  [unfetched]): 30–32% of generated solutions only partly satisfy properties, 18–23% fail outright, even when
  example tests pass — "cycle of self-deception" when the model writes both code and tests.

**Sandboxing.** https://opencomputer.dev/guides/python-sandbox/ — restricted `exec`/RestrictedPython are *not*
sandboxes (`().__class__.__base__.__subclasses__()` escape; RestrictedPython's own maintainers say so);
Docker ≈100 ms–1 s start, shared kernel; gVisor/Firecracker stronger; Pyodide/WASM ≈1 s start, strong isolation
for pure compute, numpy/pandas available as Emscripten wheels, no arbitrary C extensions; wasmtime-CPython
passes all their security vectors but no pip. Recommendation for local data analysis: WASM tier. Search
snippets add: cgroup-level limits, `--network none`, read-only rootfs; `/proc/<pid>/environ` leaks env secrets
inside Docker (so never pass keys by env into the sandbox). Transactional sandbox
https://arxiv.org/abs/2512.12806 — policy interception + filesystem snapshots, 100% rollback, 14.5% overhead.

**How the labs do it.** Anthropic code-execution tool (docs
https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/code-execution-tool [unfetched, search]) and
"advanced tool use" https://www.anthropic.com/engineering/advanced-tool-use — *programmatic tool calling*: the
model writes a script that orchestrates tool calls and processes results in the sandbox; only the final output
returns to the model (37% fewer tokens on research tasks; small accuracy gains); *tool search* cut tool-definition
tokens 85% and raised accuracy 49→74% (Opus 4); *tool-use examples* raised complex-parameter accuracy 72→90%.
The last two are cheap wins for our `Toolbox.SPEC` prompt.

## E(ii) Proven vs claimed

| Claim | Status |
|---|---|
| Execution-verified skills compound ability | Voyager (one environment, GPT-4); SkillOps (synthetic degraded libraries). Pattern is sound; magnitudes environment-specific. |
| Small models get right answers for wrong reasons ~⅔ of the time | Measured on 7–9B; matches our exam ("headline before the sum"). |
| Asking the model to self-reflect fixes it | **No** — hurt in 78% of conditions. |
| Shuffle/noise sanity checks expose false findings | Microsoft, 11 datasets, one agent — strong design, small sample. |
| WASM sandboxes are adequate for pandas analysis on one box | Practitioner consensus; CVE-2026-5752 Pyodide escape reported (search snippet, unverified) — keep resource limits and no secrets in the sandbox regardless. |
| Tool-use examples in the spec raise accuracy | Anthropic's own numbers on their models; plausible for Qwen; test it. |

## E(iii) Design recommendation — the `compute(code)` tool

**What it is.** A tool the investigator (and the nightly hypothesis engine) can call with a short Python
snippet that runs against the *time-locked* dataframe and returns numbers with a provenance stamp. The model
proposes the computation; the engine runs it, verifies it, and stamps it. Skills that pass become library
entries the engine can run without the model.

```
compute(code: str, purpose: str, expects: {"columns": [...], "shape": "scalar|series|table"})
   -> {result, columns, n, computed_through: t, code_hash, checks: {...}, status}
```
- **Environment**: a separate Python process (not the sim process) with `resource`/Job-Object limits (Windows:
  Job Objects for memory/CPU; Linux: rlimits + `--network none` if containerised), 20 s CPU, 512 MB, no network,
  no filesystem writes, no env vars, a whitelist import set (`numpy`, `pandas`, `scipy.stats`, `statsmodels`
  minimal), and the data injected as pre-built DataFrames: `prices` (masked coin labels, daily OHLCV ≤ t),
  `feats` (feat_* ≤ t), `funding`, `positioning`, `macro`, `events` (as-of), `graph` (edges as-of). Coin
  names and real dates are *not* present (labels C1..Cn, day index d0..dN). WASM/Pyodide is the upgrade path
  if we ever expose it beyond the local box; on this PC a hardened subprocess is enough and 10× simpler.
- **Verification gate before the result is shown to the model (all by code):**
  1. Static: AST whitelist (no `import os/sys/subprocess/socket`, no `open`, no `eval/exec`, no dunder access);
     size ≤ 60 lines.
  2. Shape check against `expects`; NaN/inf share ≤ 5%; n reported.
  3. **Time-lock probe**: rerun with the data truncated at t−1 day; the result for rows ≤ t−1 must be identical
     (catches any accidental use of the last row's future — the same shuffle test as Area A).
  4. **Sanity perturbation** (Microsoft): if the purpose is a *finding* (a correlation, a spread, a rule
     hit-rate), rerun on (a) label-shuffled returns and (b) returns + noise of 1 idio-σ; the finding must vanish
     under (a) and survive (b); report both numbers next to the original.
  5. **Property checks** the engine knows: correlations ∈ [−1,1]; Sharpe recomputed from the returned
     returns; returns sum consistency; a t-stat is recomputed from n and mean/sd — the model's own printed
     numbers are never trusted (Right-for-Wrong-Reasons).
  6. Determinism: run twice; results must match.
- **Skills-as-code library** (`skill` table): `id, name, purpose, code, code_hash, inputs, outputs, validator_code,
  created_by, created_ts, runs, successes, last_used, utility, failure_risk, status`. A `compute` that passed the
  gate and is used twice becomes a `proposed` skill; the nightly job re-runs every skill's validator on fresh
  data; SkillOps gates: validator required, body-hash dedupe, utility floor, failure-risk retirement. Active
  insights (Area A #39) compile to skills — a rule becomes an executable screen with a validator.
- **Tool-use examples** in `Toolbox.SPEC` (two worked calls per tool) and a `tool_search(query)` that returns
  only the 5 relevant tool specs when the list grows past ~20 — Anthropic's measured wins.
- **Programmatic tool calling for the engine, not the model**: the Reviewer/hypothesis loop writes one script
  that calls several tools and returns one table; the strategist sees a table, not 12 tool results.
- **Never** ask the model to reflect on its own arithmetic (2601.00513). The skeptic's cost arithmetic moves to
  the Risk hat (code).
- **Budget**: ≤3 `compute` calls per investigator decision (each ≤20 s), unlimited in the nightly job.

## E(iv) Feature list — Area E

1. `compute(code, purpose, expects)` tool over time-locked frames — ReAct/Voyager — test: tool logged with code_hash and computed_through.
2. Subprocess isolation with CPU/memory limits (Job Objects on Windows) — sandbox guides — test: infinite loop killed at 20 s; 1 GB alloc fails.
3. No network, no file writes, no env vars in the sandbox — /proc environ leak finding — test: `socket` import fails; `os.environ` empty.
4. AST whitelist (imports, no dunder, no open/eval/exec) — RestrictedPython caveat (defence in depth, not the boundary) — test: escape snippet rejected.
5. Masked frames only (labels, day index) — leak defence — test: no real symbol string reachable in the sandbox namespace.
6. Shape/NaN/n checks against `expects` — engine verification — test: wrong shape returns status=shape_error.
7. Time-lock probe (truncate to t−1, compare overlapping rows) — Area A shuffle test — test: a snippet using `.iloc[-1]` of a future-padded frame is caught.
8. Label-shuffle sanity rerun for findings — 2604.11003 — test: a "finding" on shuffled data reports near-zero.
9. Noise-injection stability rerun (1 idio-σ) — 2604.11003 PCS — test: stable finding survives, reported side by side.
10. Engine recomputes any t-stat/Sharpe/corr from returned raw series — 2601.00513 — test: model-printed number ignored; engine number shown.
11. Determinism double-run — sandbox practice — test: mismatch → status=nondeterministic.
12. Result stamp `{code_hash, computed_through, n, checks}` on every evidence card built from compute — provenance — test: card without stamp rejected.
13. `skill` table with validator_code required — SkillOps validator gate — test: insert without validator fails.
14. Promotion compute→skill after 2 verified uses — Voyager execution-verified storage — test: status transitions logged.
15. Nightly re-validation of all skills on fresh data — SkillOps — test: failure_risk updated.
16. Body-hash dedupe of skills — SkillOps redundancy gate — test: identical code rejected.
17. Utility floor retirement (unused 90 days or F(s) > 0.3) — SkillOps — test: retirement row written.
18. Active insight → compiled screen skill with validator — Area A #39 — test: the screen returns the same rows as the insight's condition.
19. Skill retrieval by purpose text (FTS) + past success rate — Voyager embedding retrieval, 2512.10696 — test: top-1 is the highest-utility match.
20. Per-model skill validation (a skill validated under Qwen3.6 is re-validated if the model changes) — "Skill is Not One-Size-Fits-All" — test: model id stored on validation.
21. Two worked examples per tool in `Toolbox.SPEC` — Anthropic tool-use examples — test: exam re-run measures arg-format error rate before/after.
22. `tool_search(query)` returning ≤5 specs when tools > 20 — Anthropic tool search — test: prompt token count drops.
23. Engine-side programmatic tool calling for the Reviewer (one script, one table) — Anthropic programmatic calling — test: strategist prompt shorter, same facts.
24. ≤3 compute calls per decision, ≤20 s each — budget — test: fourth call refused with reason.
25. Compute call error text returned to the model *once* for a retry, then abandoned — Voyager iterative prompting bounded — test: max 1 retry.
26. Library of engine-written canonical skills seeded (event study, LP, beta, corr matrix, funding z) so the model composes rather than reinvents — Voyager skill composition — test: ≥8 seeded skills with validators.
27. `skills()` tool listing available skills with signatures — MemGPT-style self-directed calls — test: list as-of model version.
28. Hypothesis engine uses compute to test `link` beliefs (Area B) — R&D-Agent-Quant development loop — test: each link belief has a compute run id.
29. Snapshot/rollback of the memory DB around nightly jobs — 2512.12806 transactional sandbox — test: failed job leaves DB unchanged.
30. Compute audit page: calls, pass/fail by check, top failing checks — honesty — test: rendered in terminal.
31. "Right-for-wrong-reasons" detector on strategist chains: every number in the chain must match a tool/compute stamp within rounding — 2601.00513 — test: unmatched numbers flagged.
32. Refuse model self-verification prompts (no "double-check your arithmetic") — 2601.00513 (78% harm) — test: prompt strings audited.
33. Property checks table (bounds, identities) applied to all tool outputs, not only compute — DS-1000 multi-criteria idea — test: corr > 1 impossible.
34. Curriculum for the hypothesis engine: start with families that have the most data (funding, momentum), unlock event families as the calendar fills — Voyager automatic curriculum — test: family order logged.
35. Export compute traces (code, checks, result) as training data for Area J — Trading-R1 data need — test: file grows per verified compute.

---

# F. SURVIVAL CONDITIONS IN A SIMULATOR

Terms once: **Sharpe** = average return divided by its volatility (per year); **PSR** (probabilistic Sharpe)
= the probability the true Sharpe is above a benchmark given how many observations you have and how
fat-tailed/skewed they are; **DSR** (deflated Sharpe) = PSR after raising the benchmark for how many
variants you tried; **PBO** = probability of backtest overfitting: the chance the configuration that looked
best in-sample is below median out-of-sample; **walk-forward** = fit on the past, test on the next block,
roll; **anchored** = the fit window grows, **rolling** = it slides.

## F(i) Findings, with URLs

**Statistical gates.**
- PSR formula (quantdare https://quantdare.com/probabilistic-sharpe-ratio/):
  PSR(SR*) = Φ[ (SR − SR*)·√(n−1) / √(1 − γ₃·SR + (γ₄−1)/4 · SR²) ] with γ₃ skew, γ₄ kurtosis (their
  rendering also shows an alternate "1 + ½SR²" form; the López de Prado form is the one above). Worked
  example: SR 1.63 with worse tails had PSR 93.0% vs SR 1.55 with PSR 95.2% over 52 weeks.
- DSR / MinTRL / CPCV are implemented in https://github.com/eslazarev/purged-cross-validation (purging =
  drop training rows whose label window overlaps the test; embargo as time/observations/fraction, e.g. 1%;
  CPCV with N blocks and K test blocks gives C(N−K+1,K) backtest paths, e.g. N=6,K=2 → 5 paths; DSR uses the
  *effective* number of correlated trials) and in https://github.com/WatchTree-19/overfit (CSCV default S=10
  blocks; **PBO > 0.5 means the in-sample winner is *worse* than median OOS — selection is actively
  misleading**). The original PBO paper PDF https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf did not
  parse [unfetched]; DSR SSRN page 403 [unfetched]; Wikipedia DSR page 404.
- Harvey, Liu & Zhu (RFS 2016; search snippet, SSRN/NBER pages [unfetched]): with the factor-mining history
  accounted for, a new factor needs **t > 3.0**, not 2.0.
- Walk-forward (https://kiploks.com/research/anchored-vs-rolling-walk-forward-windows-which-should-you-use):
  no universal window; "mirror in research the refit cadence you will run in production"; anchored suits
  slow signals (add regime checks), rolling suits adaptive ones; running both and comparing tells you how
  fast the edge decays.

**How the field evaluates trading agents (and fails).**
- Agentic Trading survey https://arxiv.org/abs/2605.19337 — 77 studies screened, 19 empirical; **0 of 19
  reach the top reproducibility tier; 15/19 are R0**; only 1/19 states a transaction-cost model; only 1/19
  documents survivorship/universe; 2/19 have extractable time-consistent splits. Prescription: comparable
  protocols, explicit execution semantics, reproducible artefacts, a reporting checklist.
- FORESIGHT-9 https://arxiv.org/html/2608.29372 — evaluates adaptive agents *prospectively* across nine
  counterfactual worldlines (sanctions, internet splintering, nuclear escalation, Minsky moment, JPY
  disorder, inflation regime shift, financial fragility, Hormuz energy crisis, pandemic/automation) from a
  July-2026 information boundary; keeps three states per run — research (factor library), declared
  (ensemble), executed (holdings) — and scores process separately from P&L. Findings: retrospective
  rankings do not transfer (median Spearman −0.80 vs prospective); the backtest winner is first in only
  1/9 worldlines; **equal-weight and inverse-vol rules each beat 31 of 36 agent runs**; one agent made +86%
  while its factor library had collapsed to zero (earnings without adaptation). "No configuration passed
  all three levels."
- TradeTrap https://arxiv.org/html/2512.02261 — stress-tests agents on four surfaces (market intelligence,
  strategy formulation, ledger, execution); fabricated news cut an adaptive agent's Sharpe 4.34→3.20; prompt
  injection cut return 7.81%→0.89%; memory poisoning Sharpe 5.72→1.58; state tampering concentration
  39%→63% and a −61% loss for the procedural agent. Procedural pipelines were more robust to fake news,
  less to state tampering.
- Poisoning Agentic Alpha https://arxiv.org/html/2608.24069 — the **Risk Manager role is the single point of
  failure** (98.9% attack success when jailbroken); bull/bear researcher 47.6% via persuasion; news analyst
  20.5% via poisoning; majority-vote architectures had the best clean returns but the largest degradation
  under attack (−12 pp); "majority voting provides thresholded, not gradual, robustness". Decision flips
  do not track dollar harm.
- Adversarial synthetic markets https://arxiv.org/html/2601.17008 — macro-conditioned GAN (46 FRED
  indicators) where an adversary perturbs macro inputs to minimise trader returns; robust policy cut DBB
  max drawdown 33.3%→11.0%, ARR 13.6%→26.0%; Wilcoxon p<0.05 across 9 ETFs. Relevant idea: stress
  scenarios generated by *perturbing the macro drivers*, not by random noise.
- Trading-R1 https://arxiv.org/pdf/2509.11420 (fetched in Area J): SFT then RL with an **easy-to-hard
  curriculum**.
- Search snippets (unfetched practitioner pieces): a promotion rule of "≥20 settled signals and a
  bootstrap 90% CI on forward returns excluding zero, with the DSR recorded next to the decision"; capacity
  models; "a Sharpe 1.5 found after 200 variants is weaker evidence than 0.9 found first try."

## F(ii) Proven vs claimed

| Claim | Status |
|---|---|
| t>3 / DSR / PBO are necessary for any claimed edge | Published, standard; the exact formulas come from the López de Prado line of work (fetched via implementations, not the papers themselves). |
| Backtest rank does not predict forward rank for adaptive agents | FORESIGHT-9, 36 runs, one paper — strong design, single group. |
| Simple rules beat most adaptive agents | FORESIGHT-9 (31/36) and 2605.20528 (cap-weight beat MPT) agree. |
| A single risk-approval role is the weakest link | One adversarial study; consistent with TradeTrap. |
| Nobody in the LLM-trading literature reports costs/splits properly | Survey of 19 studies. |
| Curriculum easy→hard helps training | Trading-R1 uses it; ablation not fetched. |

## F(iii) Design recommendation — the survival ladder for OUR agent

The agent is a *candidate strategy*. It climbs levels; each level has an unlock and a kill. Every number
below is a starting value to be revisited after the first full-year run; "kill" means demotion one level
and a written post-mortem, not deletion (Thompson probation keeps it alive at small size).

**Level 0 — Plumbing (no P&L judged).** Unlock: the shuffle test, cutoff-discontinuity test, claim-leak
audit (Area A) pass; every tool result stamped; `decisions.jsonl` replays byte-identical; cost model
(4.5 bps + half spread + funding) and universe/survivorship rule written in the run header (the survey's
two missing items). Kill: any of these fails.

**Level 1 — Paper year, in-sample era (2025).** Run the full 2025 year in batches with skeptic on; twins:
rule-agent baseline, random-control, equal-weight-momentum (FORESIGHT-9's "does the agent beat a dumb
rule?"). Unlock to L2: n ≥ 60 closed trades; mean **excess** per trade > 0 with bootstrap 90% CI excluding 0;
PSR(0) ≥ 0.90 on daily excess; beats the equal-weight rule on excess with t ≥ 2; calibration slope ∈ [0.7,
1.3]; max drawdown ≤ 15% of the $10k book; falsifier/checkpoint verdicts graded on ≥ 80% of trades.
Kill: excess CI includes 0 after n ≥ 60, or drawdown > 25%, or ≥ 30% of orders rejected by the Risk hat
(the model is not learning the rules).

**Level 2 — Walk-forward + ablations (2021→2026, both directions of time).** Rolling 6-month test blocks
with memory *anchored* (grows) and a second run with memory *rolling* (365-day window) — the decay diagnostic.
Ablations (each a separate run, same seeds): skeptic off; memory off; graph retrieval off; links engine off;
belief board off. Unlock to L3: excess > 0 in ≥ 5 of 8 test blocks (sign stability), DSR ≥ 0.95 counting
*every* configuration ever run (we keep the count), PBO ≤ 0.3 over the configuration set (CSCV S=10), and at
least two ablations show a measured loss (if nothing hurts, nothing is working). Kill: PBO > 0.5, or the
anchored run beats rolling by more than 2× (the "edge" is an old regime).

**Level 3 — Regime-specific + curriculum.** Report per regime label (12-cell, Area D): excess, n,
hit-rate, Brier. Curriculum in the *evaluation* sense: the agent must first pass calm regimes (CHOP, low
common-share) before its results in stress regimes count; a strategy that only wins in one regime gets a
regime-gate (Risk hat blocks trading outside it). Unlock: no regime cell with n ≥ 15 and mean excess < −50
bps; stress-regime max drawdown ≤ 20%. Kill: two consecutive stress windows with drawdown > 20%.

**Level 4 — Adversarial / stress.** Synthetic scenarios generated by *perturbing drivers* (2601.17008):
(a) BTC −25% in 3 days with all correlations → 0.9 (stress matrix), (b) liquidity vanishes (spreads ×5,
fills at the stop level +2%), (c) funding flips sign on every held coin, (d) an unlock calendar error (event
moved 7 days), (e) fabricated evidence card injected into the investigator's results (TradeTrap), (f) the
skeptic's dossier replaced by stale data. Unlock: survives (a)–(c) with loss ≤ 2× the historical stress
drawdown; the Risk hat blocks all trades on (e)–(f) (fact stamps fail). Kill: any scenario liquidates > 40%.

**Level 5 — Prospective paper (forward-only, live data).** 90 days minimum, same ledger, same costs, news
tools forward-only; three states tracked like FORESIGHT-9 (research state = active insights/skills; declared
= belief board; executed = book). Unlock to real money: excess > 0 with n ≥ 30, calibration holds, no
state divergence (declared beliefs must map to executed positions ≥ 80%). Kill: any Risk-hat bypass, any
unstamped fact in a decision, drawdown > 15%.

**Standing rules at every level:** two configurations at a time maximum; every configuration counted toward
DSR; the last 6 months of 2026 held out untouched until L4; A/B is always vs the *rule twin on the same
dates*, never vs raw P&L; kills are logged with the number that killed.

## F(iv) Feature list — Area F

1. Run header records cost model, universe rule, survivorship handling, split protocol — Agentic Trading survey — test: header present and parsed.
2. Configuration registry counting every run for DSR — DSR — test: N increments per run.
3. PSR on daily excess in summary.json — PSR formula — test: matches library on a sample.
4. DSR with effective number of trials — purged-cross-validation lib — test: DSR ≤ PSR always.
5. MinTRL reported ("need n more days for PSR 0.95") — MinTRL — test: monotone in target.
6. CSCV/PBO over the configuration set, S=10 — overfit package — test: PBO ∈ [0,1], reported.
7. Bootstrap 90% CI on mean excess per trade — practitioner promotion rule — test: CI shrinks with n.
8. Twins on identical dates: rule agent, random, equal-weight momentum, inverse-vol — FORESIGHT-9 — test: same wake-up dates.
9. Level state machine (L0–L5) persisted with unlock/kill reasons — this ladder — test: transitions logged with the number.
10. Kill → demotion + post-mortem note, never deletion — Thompson probation — test: probation trades continue at ¼ size.
11. Walk-forward 6-month blocks, anchored vs rolling memory — kiploks guidance — test: both runs produced.
12. Sign-stability count across blocks — §16.15 — test: k-of-8 reported.
13. Ablation harness (skeptic/memory/graph/links/beliefs off) with fixed seeds — F(iii) — test: five runs, diff table.
14. "Nothing hurts ⇒ fail" rule — F(iii) — test: gate refuses L3 if no ablation loses.
15. Regime-cell report (12 cells) — Area D — test: n and excess per cell.
16. Regime gate in Risk hat for strategies that only pass some cells — curriculum — test: order blocked outside allowed cells with reason.
17. Stress scenario runner with driver perturbations (a)–(f) — 2601.17008, TradeTrap — test: each scenario has a saved result.
18. Correlation-to-0.9 scenario uses the stress matrix — Area D — test: projected loss reported.
19. Liquidity-vanish scenario (spread ×5, gap fills) — §6 gap-modelling gap — test: exit prices worse than level.
20. Fabricated-evidence injection test: stamped-fact check must block — Area E stamps — test: injected card rejected.
21. Stale-dossier test — TradeTrap state tampering — test: skeptic prompt refuses when computed_through ≠ t.
22. Risk-hat is code-only and cannot be prompted — 2608.24069 (risk role = single point of failure) — test: no model call in the risk path.
23. Risk-hat rejection rate as a learning metric (≥30% ⇒ kill at L1) — HOW_IT_WORKS §9 — test: rate in summary.
24. Three-state tracking (research/declared/executed) with divergence metric — FORESIGHT-9 — test: divergence ≤ 20% at L5.
25. Prospective 90-day paper stage with forward-only tools — FORESIGHT-9 prospective — test: no historical tool calls after boundary.
26. Held-out last 6 months locked by a file flag until L4 — §16.15 — test: runner refuses dates in the hold-out.
27. Max two live configurations — standing rule — test: third run refused.
28. Kill-log page in the terminal — Area I — test: rendered.
29. A/B always vs rule twin on same dates — LEARNING_ENGINE_V2 proof — test: comparison rows share dates.
30. Calibration slope gate [0.7, 1.3] — Area B — test: computed from calibration table.
31. Falsifier/checkpoint coverage ≥ 80% — chain grading — test: share reported.
32. Drawdown gates per level (15/25/20/40/15%) — F(iii) — test: triggers on synthetic equity path.
33. Edge-decay diagnostic: anchored vs rolling excess ratio — kiploks — test: ratio reported.
34. Capacity estimate per strategy (ADV participation) — practitioner snippet — test: reported for L5.
35. Reporting checklist auto-generated per run (the survey's checklist) — 2605.19337 — test: markdown emitted.
36. Seed-determinism check (two runs same seed ⇒ same decisions given same model outputs cached) — reproducibility R3 — test: hash equal.
37. Model-output cache keyed by prompt hash for exact replays — reproducibility — test: replay uses cache, zero model calls.
38. Regime-conditioned kill (two consecutive stress windows > 20% DD) — F(iii) — test: fires on synthetic path.
39. "Dumb-rule beats agent" flag when equal-weight twin wins the block — FORESIGHT-9 — test: flag present.
40. Post-mortem writer (code) naming the killing metric and the trades behind it — Reviewer hat input — test: text includes trade ids.

---

# G. MULTI-AGENT TRADING ARCHITECTURES — WHAT ACTUALLY WORKED

## G(i) Findings, with URLs

**The named systems and their claims.**
- **TradingAgents** https://arxiv.org/abs/2412.20138 (full https://arxiv.org/html/2412.20138): roles =
  fundamental/sentiment/news/technical analysts, bull vs bear researchers with a facilitator choosing the
  number of rounds, trader, risk team; gpt-4o-mini for quick tasks, o1-preview for deep. Reported: AAPL
  Sharpe 8.21, GOOGL 6.39, AMZN 5.60, max drawdown 0.9–2.1%, on **Jan 1–Mar 29 2024 only** (three bullish
  months, inside the models' training window); **no transaction costs modelled**. Users report model-level
  leakage (issue #805).
- **FinCon** https://arxiv.org/abs/2407.06567 (full https://arxiv.org/html/2407.06567): manager–analyst
  hierarchy; within-episode risk control fires when a day's P&L is in the bottom 1% (CVaR); over-episode
  "conceptual verbal reinforcement" updates beliefs by comparing profitable vs unprofitable sequences.
  Oct 2022–Jun 2023: TSLA +82.9% (Sharpe 1.97), NFLX +69.2%, COIN +57.1%, GOOG +25.1%. Ablation on GOOG:
  without CVaR −1.5%; without belief updates −11.9%; with both +25.1%. (Two things we should copy: a
  *code-triggered* risk brake and belief updates from win/loss *pairs*.)
- **FinMem** https://arxiv.org/abs/2311.13743: layered memory (working; short/mid/long with decay),
  tunable "character" and perceptual span; single-stock results vs baselines (numbers not in abstract).
  The 2026 evaluation paper below reports FinMem's MSFT +23% **reversed to −22% under controlled
  conditions**.
- **FinAgent** https://arxiv.org/abs/2402.18485: multimodal (numbers, text, charts), dual-level reflection,
  tool-augmented decisions; claims +36% average profit over 9 baselines on 6 datasets incl. crypto; one
  dataset +92%. No cost model in abstract.
- **FinRobot** https://arxiv.org/abs/2405.14767: a platform whitepaper — four layers, "financial
  chain-of-thought", separation of numeric computation from narration; no evaluation numbers.
- **Trading-R1** https://arxiv.org/pdf/2509.11420 (full https://arxiv.org/html/2509.11420): Qwen3-4B; 100k
  samples, 14 US equities, Jan 2024–May 2025; labels = volatility-normalised blend of 3/7/15-day EMA
  returns (weights 0.3/0.5/0.2) cut at asymmetric quantiles into strong-buy 15% / buy 32% / hold 38% / sell
  12% / strong-sell 3%; three-stage curriculum (structure → claims with opinion-quote-source grounding →
  decision), each SFT then GRPO; results Jun–Aug 2024: NVDA Sharpe 2.72, AAPL 1.80, AMZN 1.72, SPY 1.60,
  max drawdown 1.5–3.8%; beat GPT-4.1, DeepSeek and base Qwen3-4B; **untrained small models had negative
  Sharpe and reasoning models drifted**. Compute: 8×H100 for SFT, 8×H200 for RL; inputs 20–30k tokens,
  outputs 6–8k.
- **Crypto multi-agent portfolio** https://arxiv.org/html/2501.00826v3: three agents (crypto time-series,
  news, trading) in hierarchical / collaborative / debate modes; 52 weeks of **2025, strictly post-cutoff**;
  top-15 L1 coins; best = hierarchical + skill-augmented: +133.5%, Sharpe 1.50 (GPT-4o) vs single-agent
  −8.8% to −26%, TimesNet +83.4%, buy-and-hold negative. **Ablation**: remove crypto (numbers) agent −42.6
  pp; remove memory −11.5 pp; remove news agent −0.9 pp return but +6.8% volatility — the news agent is a
  *risk dampener*, not an alpha source. Multi-agent beat single-agent under all three backbones (Claude avg
  +33%).
- **FS-ReasoningAgent** https://arxiv.org/abs/2410.12464: split reasoning into fact vs subjectivity; +7%
  BTC, +2% ETH, +10% SOL; stronger models sometimes did worse because they discount subjective news;
  subjective reasoning helped in bull markets, factual in bear markets.
- **ATLAS** https://arxiv.org/html/2510.15949v2: market/news/fundamental analysts → central trading agent
  → StockSim; Adaptive-OPRO rewrites the *instruction block* of the prompt from a 5-day windowed score;
  o4-mini went −1.3% → +9.1% ROI; **reflection prompts hurt in volatile regimes (r = −0.78 between baseline
  quality and reflection gain)**; ablation: removing market data or news each hurt in different regimes
  (news mattered in sideways markets).
- **TrustTrade** https://arxiv.org/abs/2603.22567: selective consensus — weight agents by semantic and
  numerical agreement, discount divergent/weakly grounded outputs; moved behaviour from extreme
  risk-return to a mid-risk profile in 2024-Q1 and 2026-Q1 noise regimes; numbers not in abstract.

**The evaluations that check the claims.**
- Toward Reliable Evaluation of Financial MAS https://arxiv.org/html/2603.27539v1: five systematic
  failures (look-ahead, survivorship ≈0.9%/yr drag, overfitting — FinMem +23% → −22%, cost neglect — only 2
  of 12 systems model costs, regime blindness — TradingAgents' Sharpe from one 3-month bull window); **no
  system meets all five minimum standards**; "Coordination Primacy Hypothesis" (coordination protocol
  matters more than backbone) is stated as *falsifiable but not yet validated*; coordination pays only when
  spread < "coordination break-even spread" — low single-digit bps, i.e. **not in 20–100 bp crypto spreads**;
  recommends hybrid small-model architectures escalating to frontier models selectively.
- StockBench https://arxiv.org/abs/2510.02209: 20 DJIA stocks, Mar–Jun 2025 (82 days, post-cutoff);
  **most LLM agents fail to beat equal-weight buy-and-hold**; some have better drawdown/Sortino.
- Memory-controlled benchmark https://arxiv.org/pdf/2605.28359: agents "generally struggle to outperform
  buy-and-hold when realistic trading costs are included" (PDF tables not legible in fetch).
- Execution assumptions https://arxiv.org/pdf/2606.08285: fill-at-close vs next-open, costs and slippage
  shift results materially (the fetch summary's "10–50%" figure could not be verified against the tables —
  treat as unconfirmed); recommends next-bar-open fills and sensitivity tables.
- Profit Mirage and The Alpha Illusion (Area B): 51–62% Sharpe collapse post-cutoff; "language confidence
  is not tradable probability".
- Agentic Trading survey (Area F): 0/19 reproducible at the top tier.
- Poisoning Agentic Alpha and TradeTrap (Area F): the risk-manager role and majority voting are the fragile
  parts; procedural pipelines resist fake news better.

## G(ii) Proven vs claimed

| Question | Answer from the evidence |
|---|---|
| Does role separation (numbers agent / news agent / trader) help? | Yes in the one post-cutoff crypto study (2501.00826): the *numbers* agent drives alpha; news dampens risk. |
| Does a bull/bear debate help? | No evidence it beats voting for open models ("Debate or Vote"); TradingAgents' debate results are inside-training-window, costless. Unproven. |
| Does a risk-manager *LLM* help? | FinCon's *code* CVaR brake helped (+26 pp on GOOG). An LLM risk role is the top attack surface. Make it code. |
| Does reflection help? | Mixed: FinCon's belief updates from win/loss pairs helped; ATLAS and 2601.00513 show reflection prompts hurt in volatile regimes / small models. |
| Does memory help? | −11.5 pp when removed (crypto MAS); FinMem's layered memory reversed sign under control. Memory helps when it is *time-locked and graded*, otherwise it is leakage. |
| Do reported Sharpes survive costs and cutoff? | No: FinMem reversed; 5 agents lost half their Sharpe post-cutoff; most fail buy-and-hold on StockBench. |
| Does a fine-tuned 4B beat prompting? | Trading-R1: yes on 5 equities over 3 months; base 4B had negative Sharpe. One study, short window. |
| Does coordination pay in crypto spreads? | The break-even analysis says no unless the coordination adds tens of bps of signal. |

## G(iii) What to copy, what to avoid — for OUR system

Copy:
1. **Hierarchy, not debate**: investigator (numbers) → strategist → skeptic single pass → Risk hat (code).
   The crypto MAS hierarchical mode won; debate adds cost and no measured edge.
2. **FinCon's two brakes in code**: a within-run CVaR brake (bottom-1% daily P&L → halve sizes for 5 days)
   and belief updates from *paired* profitable/unprofitable sequences (our insight rounds already pair
   success/failure — keep it).
3. **Trading-R1's label recipe** for our own SFT data (Area J): volatility-normalised multi-horizon blend cut
   at quantiles that reflect crypto's *symmetric* drift (not equities' upward skew).
4. **Fact / subjectivity split** on evidence cards: engine-stamped facts vs model interpretation, kept in
   separate fields (FS-ReasoningAgent; also our provenance rule).
5. **Selective consensus** for the number (median of 3 thinking-off samples, discount divergent ones) —
   TrustTrade / self-consistency.
6. **Prompt-instruction optimisation offline** (ATLAS's Adaptive-OPRO) on the *system prompt* of each hat
   using windowed sim scores — never on the runtime content. Cheap, measurable, no fine-tune needed.
7. **Evaluation discipline**: post-cutoff windows, buy-and-hold and equal-weight twins, next-bar fills,
   costs in the header (StockBench, 2603.27539, 2606.08285).

Avoid:
- Bull/bear debate rounds; LLM risk manager; reflection prompts on the small model; any claim from a
  pre-cutoff window; adding agents for their own sake (coordination break-even).

## G(iv) Feature list — Area G

1. Hierarchical hat order fixed: investigator → strategist → skeptic → Risk(code) — 2501.00826 — test: no hat can call a later hat.
2. Numbers agent is the alpha source; news is a risk modifier only (may resize down, never up) — 2501.00826 ablation — test: news-derived cards cannot raise confidence.
3. Code CVaR brake: bottom-1% daily P&L → sizes ×0.5 for 5 days — FinCon — test: fires on synthetic loss day.
4. Paired success/failure insight rounds every ~20 closes — FinCon CVRF / ExpeL — test: pairs logged.
5. Fact vs interpretation fields on every card — FS-ReasoningAgent — test: interpretation without a fact id rejected.
6. Selective consensus for p_model (median of 3, divergent sample flagged) — TrustTrade — test: dispersion logged.
7. Offline prompt-instruction optimisation loop with 5-day windowed sim scores — ATLAS Adaptive-OPRO — test: instruction versions stored with scores.
8. Instruction changes A/B'd against the rule twin before adoption — ATLAS + our proof rule — test: adoption requires excess gain with t≥2.
9. Post-cutoff evaluation window flag on every run (model release date vs sim dates) — Profit Mirage — test: runs inside the cutoff are labelled "contaminated-possible".
10. Buy-and-hold and equal-weight twins in every summary — StockBench — test: present.
11. Next-bar-open fill option and sensitivity table (close vs next open) — 2606.08285 — test: both P&L series produced.
12. Coordination cost line: model-call seconds and tokens per decision vs excess bps — 2603.27539 CBS — test: reported.
13. Hat ablation results kept as a standing table (skeptic on/off etc.) — G(ii) — test: updated each level run.
14. No debate rounds; skeptic single pass with engine dossier — "Debate or Vote" — test: exactly one skeptic call per decision.
15. Risk hat has no model call and cannot be overridden by any hat — 2608.24069 — test: code path audit.
16. Regime-split reporting (bull/bear/chop) for every hat's contribution — 2410.12464 (subjective helps in bull, factual in bear) — test: table per regime.
17. Trading-R1-style label generator for our decisions (vol-normalised 3/7/15-day blend, symmetric quantiles) — Trading-R1 — test: label distribution printed.
18. "Claims with sources" format enforced in strategist output (each claim cites a card id) — Trading-R1 stage II — test: uncited claim → order rejected.
19. Memory ablation twin (memory off) every level — 2501.00826 −11.5 pp — test: run exists.
20. Reflection prompts banned for thinking-off calls — ATLAS r=−0.78 / 2601.00513 — test: prompt audit.
21. Small-model-first, escalate only on flagged decisions (e.g., wake reason = event) — 2603.27539 hybrid SLM — test: escalation count logged (even if the "big" model is the same model with thinking on).
22. Survivorship rule: delisted HL coins stay in the universe until delisting date — 2603.27539 (0.9%/yr drag) — test: universe as-of includes later-delisted coins.
23. Cost model applied to *every* twin identically — Agentic Trading survey — test: same fee function object.
24. Per-hat token/latency budget enforced — coordination cost — test: over-budget call aborted.
25. Decision-level "who added value" attribution: strategist vs skeptic vs risk edits, in bps — FinCon ablation style — test: attribution sums to net.
26. News tool (forward-only) outputs a *risk modifier* field, not a direction — 2501.00826 — test: schema.
27. Character/persona parameters removed (no "aggressive trader" prompts) — FinMem reversal — test: prompt audit.
28. Sortino and max drawdown alongside Sharpe in every summary — StockBench metrics — test: present.
29. Multi-seed runs (3 seeds) for any architecture claim — 2603.27539 (gains don't replicate across seeds) — test: mean±sd reported.
30. Backbone-swap test (a second local model) before any architecture conclusion — 2603.27539 — test: at least one run with a different GGUF.

---
