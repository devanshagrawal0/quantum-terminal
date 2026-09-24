# AGENT v2 — BUILD SPEC AND CHECKLIST
2026-09-16. The one document to build from. Sources: `AGENT_V2_RESEARCH_2026-09-16.md` (agent dossier, areas A–G, 134 fetched sources), `AGENT_V2_RESEARCH_B_2026-09-16.md` (my pass: self-evolution, thinking, discipline, features, junk test, paper day, news/search, Fed-trade gaps), `MEASURED_LINKS_2026-09-16.md` (our own numbers), `HOW_IT_WORKS_2026-09-16.md` (the honest audit of what exists), the two exams, and the repo inventory (sim/ 60 functions, 20 tools, 24 API routes, 3 terminal pages).

## 0. Rules of this document
1. Every checklist item has an ID, a one-line test that can fail, and a status: **EXISTS** (verified today by running it), **PARTIAL** (code exists, not verified or incomplete), **TODO**. Status changes only when the test's real output is in the run log.
2. No placeholders, no stubs, no "TODO later" inside code. A function that is not finished does not get committed.
3. The model writes words and proposes mechanisms. The engine computes every number and every sign, prices every link, checks every rule, sizes every trade. No exception.
4. Nothing self-modifies without a gate: insights, prompts, skills and workflow changes are proposals judged out-of-sample.
5. Time-lock is sacred: any read at time t sees only rows with `observed_at ≤ t`. The shuffle test (A27) runs in every self-test.
6. A "done" report to Dev contains the real output (decision log lines, table rows, screenshots of the terminal page), never a description.
7. Verification loop: every function touched in a wave is re-read and re-run against its test at least 10 times across the wave (fresh inputs each pass — different coins, dates, regimes), and the loop count is written in the wave report.

## 1. What we are building, in plain words
A trader that lives in a time-locked copy of the market. Each decision it: reads what changed (engine), asks questions answered by tools (numbers with stamps), reads its own **memory graph** (what is connected to this coin, this event, this mechanism), reads its **belief board** (what it currently thinks, with probabilities the engine scored), writes **chains** (event → mechanism → instrument → direction → size → falsifier → checkpoint), gets attacked by the **skeptic** (thesis only), gets sized and rule-checked by the **risk hat** (code), trades in a book with real costs, is graded against the market, and every close revises beliefs, memories and insights. Nightly it **hunts for links it does not have** (hypothesis → local projection → admitted or rejected), computes what it lacks through a sandboxed `compute()` tool, and consolidates memory. In paper trading the same loop runs on live data with a morning and evening search and engine monitors in between. Dev sees all of it in the terminal: the graph, the correlation heatmaps (normal and stressed), the beta/idio map, the belief board, the links table, every decision replayable, the kill log.

The "thinking room" = the working-memory object of one decision (sheet, cards, beliefs cited, chains, verdicts) saved whole. The "map/connection place" = the memory graph with typed, bi-temporal, origin-tagged edges. The "matrices" = the cross-sectional layer, drawn.

## 2. Architecture (modules and files)
| Module | File(s) | Purpose |
|---|---|---|
| Time-locked data | `sim/data.py` (exists) + `sim/xsec.py` (new) | prices, features, funding, positioning, **beta/residual/corr/clusters** |
| Event store + calendar | `sim/events.py` (new), tables `event_type/event_instance/event_outcome` | FOMC/CPI/NFP/unlocks/listings/ETF/hacks/opex with consensus, realised, surprise |
| Links engine | `sim/links.py` (new), table `link` | local projections + event studies, admission rule, vintages |
| Memory graph | `sim/memory.py` (extend), tables `node/edge` | bi-temporal typed graph over coins, events, mechanisms, beliefs, trades, decisions, sources |
| Belief board | `sim/beliefs.py` (new), tables `belief/belief_evidence/belief_revision/belief_score` | claims with p_model/p_engine/p_final, resolvers, Brier |
| Tools | `sim/tools.py` (extend) | + `links`, `event_study`, `analogues`, `rotation`, `news`, `beliefs`, `graph_walk`, `compute`, `skills`, `tool_search`, crowd labels on every result |
| Compute sandbox + skills | `sim/compute.py` (new), table `skill` | subprocess with limits, verification gate, skill library |
| Hats | `sim/investigator.py` (extend) + `sim/risk.py` (new) + `sim/reviewer.py` (new) | investigator, strategist, skeptic (exist); **risk hat (code)**, **reviewer** |
| Runner | `sim/run.py` (extend) | wake-ups (+event, +surprise), twins, ablations, level ladder, cache, replay |
| Junk test | `sim/junk.py` (new) | mixed true/fake/irrelevant feed, exposure/flip/rule-break/citation scores |
| Paper day | `paper/day.py` (new) | morning brief, monitors, event wake-ups, evening review, weekly |
| Viewer | `scripts/dashboard.py` + `scripts/terminal.html` (extend) | graph, heatmaps, beta map, belief board, links, decision replay, kill log, compute audit |
| Self-test | `scripts/selftest.py` (new) | runs every checklist test that is automatable; prints pass/fail table |

## 3. Waves (build order; each wave ends with a real-output report and Dev's go)
- **W1 Cross-sectional layer + risk hat.** `sim/xsec.py` fills feat_cross/feat_xsec from data on disk; risk hat (code) sizes and rule-checks orders; skeptic dossier gets the facts; crowd labels on every tool result. Show: the beta/idio table for today, one decision with the risk hat's verdicts, `python scripts/selftest.py` output.
- **W2 Event store + links engine.** FOMC/CPI/NFP/unlocks/listings seeded; funding→return and unlock→return links measured with the admission rule; `links`, `event_study`, `analogues` tools; event wake-ups; confidence cap. Show: the links table, one decision where a chain was capped.
- **W3 Memory graph + belief board.** node/edge tables, backfill from decisions.jsonl and experiences, graph walk retrieval, beliefs with three probabilities, resolvers, Brier; reviewer hat. Show: graph stats, a belief resolving, a reflection with cited node ids.
- **W4 Compute sandbox + skills + hypothesis engine.** `compute()` with the gate; seeded skills; nightly link hypotheses. Show: a compute call caught by the time-lock probe; a hypothesis admitted and one rejected.
- **W5 Viewer.** Terminal pages for graph, heatmaps, beta map, belief board, links, decision replay, kill log. Show: screenshots.
- **W6 Survival ladder + junk test + twins.** Level state machine, PSR/DSR/PBO, twins, ablations, stress scenarios, junk harness. Show: L1 gate report on the August run; junk scores.
- **W7 Paper-trading day + news.** GDELT time-locked news tool; SearXNG live search; morning/evening cycle; monitors; Fed-trade acceptance test. Show: one full simulated FOMC day and one live paper day log.
- **W8 Training data export** (traces, labels) — no training yet.

## 4. THE CHECKLIST
Format: `ID | item | test | status`. Status today is honest: nearly everything is TODO.

### 4.1 Existing code — re-verified line by line (EXISTS means re-run today)
X1 | `AsOf.price/closes/feature/positioning/funding_day/tradable/day_range` return only data ≤ t | shuffle test: identical output with future rows deleted | PARTIAL
X2 | `daily_features` samples at the 23:00 bar (DECIDE_OFF) | feature at t equals store value at t+23h bar | PARTIAL
X3 | `Book.open` charges 4.5 bps + half measured spread | fee equals formula on 20 random coins | PARTIAL
X4 | `Book.settle` checks stop/target on high/low before falsifier before time | order of checks asserted with a synthetic path hitting all three | PARTIAL
X5 | `Book.settle` skips the entry day (t ≤ entry_ts) | position opened at t has empty path at t | PARTIAL
X6 | funding charged with correct sign per side | long pays when f>0; short receives | PARTIAL
X7 | `_grade` excess uses the universe mean of tradable coins over the same window | hand-computed on one trade | PARTIAL
X8 | `_grade` MFE/MAE correct per side | synthetic path | PARTIAL
X9 | counterfactual grid: first-touch logic, cost subtracted once | synthetic path where stop then target both touch | PARTIAL
X10 | `path_pct` in trade's favour, percent, per day | short path sign check | PARTIAL
X11 | falsifier ignored when on the wrong side | long with pct>0 → falsifier_day 0 | PARTIAL
X12 | falsifier exit at close when crossed | replay XMR case closes on day 2 | EXISTS (replayed 2026-09-15)
X13 | `size_mult` shrinks notional, never grows | 0.5→$50, 1.5→$100 cap | EXISTS (checked 2026-09-16)
X14 | `close_all` at end uses close price, reason "end" | summary exits count | PARTIAL
X15 | `Book.summary` Sharpe uses daily equity changes, √365 | recompute from equity_curve | PARTIAL
X16 | `Memory.learn` writes experience with all fields, FTS row | row count +1, FTS finds lesson word | PARTIAL
X17 | `Memory.evidence` decays with 90-day half-life, time-locked | evidence at t excludes closes > t | PARTIAL
X18 | `Memory.similar` uses standardised features and time-lock | neighbour list excludes future | PARTIAL
X19 | `Memory.sample` Thompson: never returns a setup with probability 0 | 1,000 draws include every setup | PARTIAL
X20 | insight lifecycle: proposed→active at ≥10 OOS same sign; retire on flip/zero | synthetic votes | PARTIAL
X21 | `Memory.calibration` buckets by stated confidence, realised win rate | hand check on 10 rows | PARTIAL
X22 | `Memory.write_note/notes/recall` time-locked | note at t+1 invisible at t | PARTIAL
X23 | `regime_label` thresholds ±3% over 30 days | boundary values | PARTIAL
X24 | `Agent.observe` adds sim_n/sim_long_excess_bps time-locked | values match evidence | PARTIAL
X25 | `LLMAgent._mask` labels stable within a decision, random across days | same coin different label next day | PARTIAL
X26 | `InvestigatorAgent._chat` toggles thinking per call; meta recorded | reasoning_chars>0 only when thinking | PARTIAL
X27 | investigator rounds ≤3, ≤6 calls per round | 7th call ignored | PARTIAL
X28 | morning sheet pre-fetched and truncated at 7,000 chars | length assert | PARTIAL
X29 | strategist fallback to no-thinking when empty | forced empty → second call | PARTIAL
X30 | order parsing: label exact, tolerant head only when exact misses, logged | "C162_Squeeze"→C162 logged | EXISTS (2026-09-16)
X31 | falsifier/checkpoint `move` fraction → pct percent conversion | −0.05 → −5.0 | PARTIAL
X32 | skeptic dossier fields all present per order | keys assert | PARTIAL
X33 | skeptic verdict parsing: veto/resize/replan/stand; bounds on size_mult and stop | out-of-range clamped | PARTIAL
X34 | replan drops a falsifier ≥ new stop | synthetic | PARTIAL
X35 | lesson: checkpoint/falsifier verdicts, "closed before judged" | 4 cases | EXISTS (2026-09-16)
X36 | `wake_reason` each trigger fires on synthetic data; cooldown 2 days | 5 synthetic days | PARTIAL
X37 | `run_episode` writes decisions.jsonl with all keys incl. skeptic, label_fixes | keys assert | PARTIAL
X38 | `Toolbox.call` stamps every result (tool, args, ts) and logs | log length = calls | PARTIAL
X39 | `market_table` slices honour sort/ascending/top_n/columns | 4 combos | PARTIAL
X40 | `correlations` uses closes ≤ t, pairwise complete | equals numpy | PARTIAL
X41 | `positioning` 7-day change computed from index positions, NaN-safe | coin with gap | PARTIAL
X42 | `funding` who_pays text matches sign | f<0 → "shorts pay longs" | PARTIAL
X43 | `funding_extremes` translates masked labels both ways | label round-trip | PARTIAL
X44 | `open_interest`, `fear_greed`, `macro_rates` time-locked | value at t excludes later rows | PARTIAL
X45 | `scheduled_events` future-only, sizes present | unlock within N days with pct | PARTIAL
X46 | `cross_venue` returns stamped row or explicit "no data" | both cases | PARTIAL
X47 | `stops_report` aggregates only closed trades ≤ t | count check | PARTIAL
X48 | `pick_universe` tightest spreads, N honoured | len == N | PARTIAL
X49 | batch mode writes CSV with one row per (agent, year) | file check | PARTIAL
X50 | `SIM_SKEPTIC=0` disables the skeptic call | zero skeptic calls | PARTIAL
X51 | `SIM_THINK_TOKENS` caps strategist budget | usage ≤ budget | PARTIAL
X52 | llama server health check before a run; auto-restart via run-qwen.ps1 on failure | kill server mid-run → restarted, run continues | TODO
X53 | model-output cache keyed by prompt hash for exact replays | replay = 0 model calls | TODO
X54 | run header: cost model, universe rule, survivorship, split, model id, prompt versions | header parsed | TODO
X55 | `scripts/selftest.py` runs every automatable test here and prints a table | exit code 0/1 | TODO
X56 | every prompt string audited: no "reflect on your answer", no persona | grep audit in selftest | TODO
X57 | no real coin symbol or real date reaches any prompt | prompt scan against coin list | TODO
X58 | BTC price never verbatim in prompts (magnitude masking) | scan | TODO
X59 | decisions.jsonl replay reconstructs the decision byte-for-byte from cache | hash equal | TODO
X60 | 10-pass verification log per wave (function, pass #, inputs, result) | file exists per wave | TODO

### 4.2 Cross-sectional layer (dossier D + MEASURED_LINKS)
D1 | `beta_btc_raw` + SE, 60-day OLS on log returns | matches numpy on 3 coins | TODO
D2 | Vasicek shrinkage toward cross-sectional median | high-SE coin shrinks more | TODO
D3 | Blume fallback when N<30 | used only then | TODO
D4 | `beta_eth` two-stage on ETH residual | ETH's own = 1 | TODO
D5 | `r2_btc` | shown in skeptic dossier as "X% BTC" | TODO
D6 | `resid_r_1d` with lagged beta | future beta changes value | TODO
D7 | `resid_mom_7d_skip1`, `resid_mom_30d_skip1` | NULL rate 0 | TODO
D8 | `idio_vol_30d` + EWMA λ=0.94 | stop shown in idio daily moves | TODO
D9 | signed-jump variance from hourly bars (Lee–Wang) | decile table reported either way | TODO
D10 | `corr_btc_30d/90d` | equals `correlations` tool | TODO
D11 | weekly Ledoit–Wolf residual correlation matrix stored | positive-definite | TODO
D12 | stress matrix on worst-decile BTC days (365d) | mean ρ higher than normal (measured 0.76 vs 0.38) | TODO
D13 | `common_share` PC1 weekly | >55% in 2022 and Oct-2025 stress windows | TODO
D14 | `neff` = N/(1+(N−1)ρ̄) | ≈2–4 in stress | TODO
D15 | consensus hierarchical clusters 5–8, Jaccard stability | stability reported monthly | TODO
D16 | cluster residual index | sums ≈0 daily | TODO
D17 | `rotation` tool: cluster 7d/30d ranked | returns ranked clusters | TODO
D18 | `corr_break_flag` via Chow test p<0.01 | fires FTX week 2022 | TODO
D19 | break → nearest event id attached | within ±3 days | TODO
D20 | RRG x/y vs BTC (10/40-day) | quadrant transitions logged | TODO
D21 | RRG quadrant categorical | distribution shown | TODO
D22 | breadth 1d/7d/above-SMA50 | equals runner breadth | TODO
D23 | ETH/BTC 30d slope, dominance proxy | computed daily | TODO
D24 | altseason score (top-50 beating BTC, 90d), flagged lagging | 0–100 | TODO
D25 | HRP weights weekly | sum 1, none negative | TODO
D26 | HRP vs inverse-vol vs equal-weight OOS variance report | per year | TODO
D27 | quarter-Kelly size map from p_final and target/stop | p=0.5 → 0 | TODO
D28 | 12% annual vol target on idio vol | high-vol coin smaller | TODO
D29 | cluster caps ≤2 positions / ≤40% risk | third same-cluster order rejected | TODO
D30 | stress-margin check under 3σ correlated move (β≈1.4 all alts in stress, measured) | rejected when loss > buffer | TODO
D31 | `size_in_idio_daily_moves` in skeptic dossier | present | TODO
D32 | CTREND-style ridge on 28 technical signals → next-week resid | IC(h) curve with SE before use | TODO
D33 | simple-beats-complex guard | comparison table | TODO
D34 | alpha by side reported | side split | TODO
D35 | cap-weighted vs equal-weighted evaluation of any signal | both reported | TODO
D36 | Amihud illiquidity filled | NULL rate 0 | TODO
D37 | past-alpha (60d intercept) | computed | TODO
D38 | idio-vol pricing sign in our data | decile table with t | TODO
D39 | investor-base proxy forward-only | series from now on | TODO
D40 | regime label 12-cell: BTC trend × common_share × vol tercile | trade counts per cell | TODO
D41 | correlation heatmap endpoint, HRP-tree ordered | JSON served | TODO
D42 | correlation-over-time endpoint (mean ρ, PC1, neff) | series served | TODO
D43 | beta-vs-idio map endpoint | served | TODO
D44 | entry-timing attribution market vs residual per trade | sums to net | TODO
D45 | capacity estimate (ADV × participation) | reported | TODO
D46 | `computed_with_data_through = t` on every feature | audit passes | TODO
D47 | shock-day table (down/up shocks: BTC, ETH, hi/lo beta, next day) recomputed monthly and stored as a fact | equals MEASURED_LINKS §3 today | TODO
D48 | stressed beta per coin (beta on shock days only) | ≈1.4 median today | TODO

### 4.3 Event store + calendar (dossier C, Research B §B10)
C1 | tables `event_type/event_instance/event_outcome`, bitemporal | as-of hides outcomes before actual_ts+h | TODO
C2 | FOMC 2021–2027 seeded, 14:00 ET statement, UTC/DST correct | 8 rows/year | TODO
C3 | CPI/NFP/PCE schedules 2021→ | every month has CPI | TODO
C4 | FRED `releases/dates` ingest | counts match | TODO
C5 | ALFRED first-print as `realised` | first ≠ revised on known months | TODO
C6 | consensus from prediction-market price at T−1 (8,500 stored markets mapped) | ≥80% of 2025 CPI months | TODO
C7 | `surprise_z` by type-specific past SD, only past instances | check | TODO
C8 | consensus NULL ⇒ surprise NULL | no fabricated surprise | TODO
C9 | Fed blackout windows | 2025 flags correct | TODO
C10 | collision flag (two events within 48h) | FOMC+opex flagged | TODO
C11 | unlock instances with type (team/investor/ecosystem/community) | distribution | TODO
C12 | listing/delisting instances from universe changes | every change | TODO
C13 | ETF flow days (Farside) 2024→ | continuous | TODO
C14 | hack instances (DeFiLlama) | ≥100 rows | TODO
C15 | Deribit expiries by rule | last Friday 08:00 UTC | TODO
C16 | `event_outcome` on residual returns, 1h..30d, session bucket | CAR = ΣAR | TODO
C17 | CAR significance BMP + Kolari–Pynnönen | 172 coins one date → n_eff=1 | TODO
C18 | rank test alongside; agreement required | both stored | TODO
C19 | lag-augmented LP with White SEs | synthetic AR(1) IRF | TODO
C20 | horizons 1/3/7/14; h ≤ ⅓ sample | refuses h=14 with n<42 | TODO
C21 | per-regime and pooled estimates | both rows | TODO
C22 | admission |t|≥3, BH-FDR q≤0.10, 3-of-4 sign stability, mechanism node | noise families admit ~0 | TODO
C23 | monthly re-estimation, 365-day half-life, vintages kept | vintage count grows | TODO
C24 | `analogues()` coin→cluster→market widening with level label | N=3 renders N=3 | TODO
C25 | median/p25/p75/hit-rate on every base rate | no bare mean | TODO
C26 | confidence cap from weakest measured link | t=1 link → p ≤ 0.6 | TODO
C27 | refuse chains with a rejected link | order dropped with reason | TODO
C28 | priced-in score per scheduled instance | = |resid CAR(−7..−1)|/resid vol | TODO
C29 | scheduled-vs-surprise prior per event type (fade vs follow) | table | TODO
C30 | funding_z → resid return link (first link; measured today: 7d rank-IC −0.027, t −3.8; long-Q1 +101 bps/7d with carry) | LP output n,t at 4 horizons | TODO
C31 | cross-sectional funding-momentum link | IC by week | TODO
C32 | unlock size×type → resid CAR (−30..+14) vs Keyrock | side by side | TODO
C33 | OI change × price change quadrant + 3-day link | four quadrants | TODO
C34 | funding APR>15% + OI 90d high → "crowded" candidate, tested | hit rate vs base | TODO
C35 | critical-slowing-down indicator | rises before ≥1 2025 cascade | TODO
C36 | endogenous/exogenous cascade tag | present | TODO
C37 | ETF flow → BTC same/next-day LP | sign positive | TODO
C38 | Fed-surprise → BTC/ETH/cluster LP, post-2020 flag | pre-2020 flagged | TODO
C39 | FOMC vol-jump feature | ratio > 1 | TODO
C40 | policy-uncertainty proxy (Kalshi Fed market entropy) | series from 2024 | TODO
C41 | PCMCI+ nightly hypothesis generator | edges become `link` beliefs only | TODO
C42 | transfer-entropy BTC→cluster lead-lag | TE direction | TODO
C43 | small-cap lag feature + LP | cost-adjusted | TODO
C44 | link vintages drift series endpoint | JSON | TODO
C45 | event wake-up: scheduled instance within 3 days for held/candidate | wake_reason "event" | TODO
C46 | in-position event check ("trim before <event>") | generated for unlock in 5 days | TODO
C47 | `event_study(event_type, target, window)` tool | logged with stamps | TODO
C48 | `links(target)` tool, admitted links as-of t | only admitted | TODO
C49 | sample_start/end + estimator on every link | non-null | TODO
C50 | link report page | rendered | TODO
C51 | FedWatch one-year history import when available; otherwise Kalshi odds as consensus | source recorded | TODO

### 4.4 Memory graph (dossier A)
A1 | `node`/`edge` tables, bi-temporal | as-of excludes observed_at>t | TODO
A2 | trade node created at close, observed_at=close_ts | invisible before close | TODO
A3 | event-outcome edges observed_at=event_ts+h | absent before | TODO
A4 | deterministic shared-attribute links (coin/event_type/setup/regime/cluster) | expected edge count | TODO
A5 | measured co-movement edges with corr, n, t | equals correlations tool | TODO
A6 | `status='unmeasured'` for model-proposed links | tagged, capped | TODO
A7 | engine-written event_type summaries with version | 8th unlock increments | TODO
A8 | model interpretation as separate note, never overwrites numbers | summary stable | TODO
A9 | 2-hop BFS retrieval from coin + near-date events | ≤2 hops | TODO
A10 | RRF fusion of BFS + k-NN + FTS | reproducible order | TODO
A11 | recency×importance×relevance rerank, 90-day half-life | rank by closed_ts | TODO
A12 | importance = |excess_bps| quantile-scaled | top decile ranks above median | TODO
A13 | `decision` node with reason, calls, cards, chains, verdicts, orders | replay byte-for-byte | TODO
A14 | `tool_call` nodes with `cited` edges from cards | every card fact resolves or rejected | TODO
A15 | reflection trigger: Σ|excess| ≥ 2,000 bps or 20 closes | fires within bounds | TODO
A16 | reflection = 3 questions with cited node ids | ≥1 id per claim | TODO
A17 | reflections → proposed insights only | never active directly | TODO
A18 | `analogues(event_type)` join over `same_type` | N = closed count before t | TODO
A19 | `expired_at` on edges failing re-estimation | expired not deleted | TODO
A20 | never-delete policy | counts monotone | TODO
A21 | cluster nodes with `member_of` monthly | as-of membership | TODO
A22 | regime_window nodes | walk returns trades inside | TODO
A23 | mechanism nodes, fixed seed vocabulary + proposals | every chain has one | TODO
A24 | proposed mechanism → canonical after ≥3 uses + ≥1 measured edge | transitions logged | TODO
A25 | `source` nodes per data table | every fact resolves | TODO
A26 | `origin` column on nodes/edges | counts per run | TODO
A27 | shuffle test (graph read identical with/without future rows) | in selftest | TODO
A28 | cutoff-discontinuity test on excess vs model cutoff month | t<2 | TODO
A29 | claim-level leak audit, 20 chains/run | rate reported | TODO
A30 | combined masking incl. magnitude rounding | scan | TODO
A31 | `recall` over node summaries + notes + lessons | "unlock" → event_type first | TODO
A32 | `link(a,b,why)` tool creates model_proposed edges only | cannot create measured | TODO
A33 | note tags from fixed vocabulary | tags ∈ vocab | TODO
A34 | summaries by code templates | deterministic | TODO
A35 | per-coin dossier = BFS(2) rendered for investigator | as-of only | TODO
A36 | retrieval budget ≤12 items / ≤1,500 tokens per hat | asserted | TODO
A37 | consolidation job after settlement, not during decisions | wall-time unchanged | TODO
A38 | semantic nodes from ≥3 episodes | cites ≥3 | TODO
A39 | procedural memory: insights compiled to screens, retired on failure | after k failures | TODO
A40 | graph stats in summary | printed | TODO
A41 | backfill decisions.jsonl history into graph | August run → 3 decision nodes | TODO
A42 | "what changed since last view" diff | empty when nothing | TODO
A43 | contradiction invalidation of opposite-sign measured edge | expired_at set | TODO
A44 | belief nodes with supports/contradicts edges | confidence recomputable | TODO
A45 | recency uses last_retrieved | updated on retrieval | TODO

### 4.5 Belief board (dossier B)
B1 | `belief` table (claim, kind, subject, horizon, resolves_by) | every order cites ≥1 belief | TODO
B2 | fixed kinds with engine resolver each | 100% resolved by code | TODO
B3 | p_model / p_engine / p_final stored | all non-null on live | TODO
B4 | shrinkage k=n/(n+10) | n=0 → p_model; n=90 ≈ base rate | TODO
B5 | calibration mapping on p_final | bucket 0.7 realised 0.5 maps down | TODO
B6 | clamp [0.35,0.65] without measured link | cannot reach 0.8 | TODO
B7 | evidence rows for/against with reliability (measured 1.0, proposed 0.5) | bounds | TODO
B8 | revision log p_before/after/reason/trigger | replay reproduces | TODO
B9 | max step 0.25 unless surprise ≥3 bits | 0.9→0.2 rejected | TODO
B10 | surprise bits by engine | 3σ move under calm belief > 3 bits | TODO
B11 | surprise wake-up | fires on Aug BTC −8% day with "range" belief | TODO
B12 | median-of-3 thinking-off samples for p_model | variance logged | TODO
B13 | no debate rounds; skeptic single pass | one call | TODO
B14 | ≥1 engine-checkable falsifier per belief | rejected without | TODO
B15 | falsifier names broken link in lesson | id in text | TODO
B16 | Brier + log score on resolution | hand check 10 | TODO
B17 | scores by kind/hat/mechanism/regime shown to skeptic | present | TODO
B18 | `no_belief` allowed when base n<8 or |p_engine−market|<0.05 | accepted | TODO
B19 | market-price anchor from funding/basis/prediction odds | shown when exists | TODO
B20 | base rate with n and IQR next to claim | N=3 renders | TODO
B21 | nightly ≤3 link hypotheses of kind `link` | after settlement only | TODO
B22 | engine tests link hypotheses via LP + BH-FDR | p and q stored | TODO
B23 | bandit over hypothesis families | distribution shifts | TODO
B24 | originality check | duplicate rejected | TODO
B25 | complexity cap (≤3 features, ≤2 operators) | rejected above | TODO
B26 | hypothesis–code alignment | mismatch rejected | TODO
B27 | Elo among live mechanism beliefs per coin | monotone | TODO
B28 | "what would change my mind" required | non-empty | TODO
B29 | expiry at resolves_by with Brier | none live past horizon | TODO
B30 | board snapshot id on decision node | reproducible | TODO
B31 | regime beliefs auto-created with persistence base rate | rate computed | TODO
B32 | crowd beliefs with resolver | from funding table | TODO
B33 | chain p_final ≤ min link p | never above weakest | TODO
B34 | belief text masked | real symbol rejects | TODO
B35 | per-run belief statistics | in summary | TODO
B36 | reviewer rewrites belief fields on new evidence | revision row | TODO
B37 | reliability-weighted evidence sums shown | sums correct | TODO
B38 | provenance cap: model evidence ≤0.5 | clamped | TODO
B39 | link beliefs → graph edges on promotion | edge id | TODO
B40 | outcome-ranked trace export | one row per resolved | TODO
B41 | hat-level Brier comparison | worst flagged | TODO
B42 | priced-in field | computed | TODO
B43 | Thompson probation for poor-Brier mechanisms | never silenced | TODO
B44 | abstention rate monitored (>70% flag) | metric | TODO
B45 | board as-of query for terminal | excludes later revisions | TODO
B46 | outside view first: `similar`/`analogues` results are injected BEFORE the strategist writes; prompt says so | order of prompt sections asserted | TODO
B47 | confidence in 0.05 steps, revised at each checkpoint (not only close) | revision rows at checkpoint days | TODO

### 4.6 Compute sandbox + skills (dossier E)
E1 | `compute(code, purpose, expects)` over time-locked frames | logged with code_hash, computed_through | TODO
E2 | subprocess with Job Object CPU/memory limits (20 s, 512 MB) | infinite loop killed; 1 GB alloc fails | TODO
E3 | no network, no file writes, no env | socket fails; environ empty | TODO
E4 | AST whitelist | escape snippet rejected | TODO
E5 | masked frames only | no real symbol in namespace | TODO
E6 | shape/NaN/n checks | shape_error status | TODO
E7 | time-lock probe (truncate to t−1) | `.iloc[-1]` future use caught | TODO
E8 | label-shuffle sanity rerun | near-zero on shuffle | TODO
E9 | noise-injection stability | reported side by side | TODO
E10 | engine recomputes t/Sharpe/corr from raw | model number ignored | TODO
E11 | determinism double-run | mismatch flagged | TODO
E12 | result stamp on every compute card | unstamped rejected | TODO
E13 | `skill` table with validator required | insert without fails | TODO
E14 | compute→skill after 2 verified uses | transitions logged | TODO
E15 | nightly re-validation | failure_risk updated | TODO
E16 | body-hash dedupe | identical rejected | TODO
E17 | utility-floor retirement | row written | TODO
E18 | active insight → compiled screen skill | same rows as condition | TODO
E19 | skill retrieval by purpose + success rate | top-1 correct | TODO
E20 | per-model validation stamp | model id stored | TODO
E21 | two worked examples per tool in SPEC | arg error rate before/after | TODO
E22 | `tool_search(query)` ≤5 specs when >20 tools | tokens drop | TODO
E23 | programmatic tool calling for reviewer (one script, one table) | shorter prompt | TODO
E24 | ≤3 compute calls per decision, ≤20 s | 4th refused | TODO
E25 | one error retry then abandon | max 1 | TODO
E26 | seeded canonical skills (event study, LP, beta, corr, funding z, expectancy, daily-move) with validators | ≥8 | TODO
E27 | `skills()` tool | as-of list | TODO
E28 | hypothesis engine uses compute | run id per link belief | TODO
E29 | DB snapshot/rollback around nightly jobs | failed job leaves DB unchanged | TODO
E30 | compute audit page | rendered | TODO
E31 | right-for-wrong-reasons detector: every number in a chain matches a stamp | unmatched flagged | TODO
E32 | no self-verification prompts | audited | TODO
E33 | property checks on all tool outputs | corr>1 impossible | TODO
E34 | curriculum for hypothesis families | order logged | TODO
E35 | compute traces exported | grows per verified compute | TODO
E36 | alpha operator vocabulary (rank, delay, delta, correlation, scale, decay_linear, ts_*, indneutralize→cluster) available as helpers in the sandbox | each helper unit-tested vs pandas | TODO

### 4.7 Risk hat (code) — dossier D sizing, F, G, Research B §B3
R1 | risk hat runs after skeptic, no model call, cannot be overridden | code path audit | TODO
R2 | stop within [1.5, 3] idio daily moves; else bounce to strategist with the number | synthetic 0.5× stop bounced | TODO
R3 | falsifier correct side and < stop | both violations bounced | TODO
R4 | target ≥ 2 daily moves and ≥ 1.5× stop | violation bounced | TODO
R5 | hold ≥ days needed for target at that vol (target/daily move)² capped 14 | computed | TODO
R6 | size = quarter-Kelly(p_final, target/stop) × vol scale × cluster cap | p=0.5 → 0 | TODO
R7 | cluster caps and book-beta band | third same-cluster rejected | TODO
R8 | stress-margin check | rejected over buffer | TODO
R9 | funding cost check: long on Q5 funding needs p_final margin > weekly carry; short on Q1 needs more | measured thresholds from links | TODO
R10 | `hl/preflight.py` rules (no melt-up shorts, no correlated over-concentration) ported time-locked | both fire on synthetic | TODO
R11 | CVaR brake: bottom-1% daily P&L → sizes ×0.5 for 5 days | fires | TODO
R12 | daily loss and drawdown circuit breakers per level | fires on synthetic path | TODO
R13 | event blackout: no new orders inside ±30 min of a scheduled release unless the chain names it | blocked with reason | TODO
R14 | stamped-fact check: any card without tool/compute stamp → order refused | injected card refused | TODO
R15 | stale-dossier check: computed_through ≠ t → refuse | refused | TODO
R16 | ledger reconciliation: book positions are truth; model claims about positions ignored | phantom position test | TODO
R17 | rejection reasons logged per order and rejection rate in summary | rate present | TODO
R18 | bounce loop: strategist gets one replan with the numbers, then order dropped | max 1 | TODO
R19 | attribution in bps: strategist vs skeptic vs risk edits | sums to net | TODO
R20 | regime gate for strategies passing only some cells | blocked outside | TODO

### 4.8 Reviewer hat + self-improvement gates (dossier A/B/G, Research B §B1)
V1 | reviewer runs at close for losses and at reflection trigger | calls logged | TODO
V2 | loss classification thesis/timing/risk-plan/regime from path + counterfactuals (code proposes, model words) | class present | TODO
V3 | paired success/failure insight rounds every ~20 closes | pairs logged | TODO
V4 | belief revisions written by reviewer with reason | rows | TODO
V5 | prompt-instruction versions stored with windowed sim scores (ATLAS offline) | versions table | TODO
V6 | instruction change adopted only after A/B vs rule twin t≥2 | gate enforced | TODO
V7 | Mem0-style ADD/UPDATE/NOOP on lessons (dedupe by similarity) | duplicate merged | TODO
V8 | reflection prompts banned on thinking-off calls | audit | TODO
V9 | post-mortem writer (code) naming killing metric and trades | ids in text | TODO
V10 | reviewer output ≤600 tokens, cited node ids required | asserted | TODO

### 4.9 Investigator/strategist/skeptic prompt and tool upgrades
P1 | crowd label on every funding/positioning/OI result ("shorts pay longs — shorts crowded — squeeze UP") | text present on all sign cases | TODO
P2 | morning sheet adds: what changed since last view (A42), beliefs live, events ≤7 days, shock-day fact, common_share regime | keys present | TODO
P3 | investigator checklist item 6 uses `analogues` and `similar` (outside view first) | tool calls precede cards | TODO
P4 | strategist sees measured links with n,t next to each candidate | prompt contains link rows | TODO
P5 | strategist output: each claim cites a card id; each order cites belief ids | uncited → rejected | TODO
P6 | strategist units: fractions everywhere; label exact | X30/X31 | EXISTS
P7 | skeptic dossier: R² to BTC, cluster, stressed beta, idio daily moves, link t-stats, belief scores, calibration | keys | TODO
P8 | skeptic asks "which card, if false, breaks this?" and names it | field present | TODO
P9 | skeptic arithmetic removed from prompt (engine flags instead) | prompt audit | TODO
P10 | thinking-on escalation for event wake-ups on the skeptic (A/B'd) | escalation count | TODO
P11 | tool result property checks (E33) applied before the model sees them | corr>1 impossible | TODO
P12 | per-hat token/latency budget | over-budget aborted | TODO
P13 | fact vs interpretation fields on cards | interpretation without fact id rejected | TODO
P14 | news-derived cards can only lower confidence (risk modifier) | cannot raise | TODO

### 4.10 Survival ladder, twins, ablations, stress (dossier F, G)
F1 | run header (cost, universe, survivorship, split, model, prompts) | parsed | TODO
F2 | configuration registry for DSR | N increments | TODO
F3 | PSR on daily excess | matches library | TODO
F4 | DSR with effective trials | ≤ PSR | TODO
F5 | MinTRL | monotone | TODO
F6 | CSCV/PBO S=10 | ∈[0,1] | TODO
F7 | bootstrap 90% CI on mean excess | shrinks with n | TODO
F8 | twins on identical dates: rule, random, equal-weight momentum, inverse-vol, buy-and-hold | same wake dates | TODO
F9 | level state machine L0–L5 persisted | transitions logged | TODO
F10 | kill → demotion + post-mortem, ¼-size probation | continues | TODO
F11 | walk-forward 6-month blocks, anchored vs rolling memory | both runs | TODO
F12 | sign-stability k-of-8 | reported | TODO
F13 | ablation harness (skeptic/memory/graph/links/beliefs off), fixed seeds | five runs | TODO
F14 | "nothing hurts ⇒ fail" | refuses L3 | TODO
F15 | regime-cell report | n, excess per cell | TODO
F16 | stress scenarios (a)–(f) | saved results | TODO
F17 | fabricated-evidence injection blocked by stamps | rejected | TODO
F18 | risk-hat rejection rate gate (≥30% ⇒ kill at L1) | rate | TODO
F19 | three-state tracking research/declared/executed | divergence ≤20% at L5 | TODO
F20 | held-out last 6 months locked by flag until L4 | runner refuses | TODO
F21 | max two live configurations | third refused | TODO
F22 | calibration slope gate [0.7,1.3] | computed | TODO
F23 | falsifier/checkpoint coverage ≥80% | share | TODO
F24 | drawdown gates per level | synthetic | TODO
F25 | edge-decay diagnostic anchored/rolling ratio | reported | TODO
F26 | reporting checklist auto-generated per run | markdown | TODO
F27 | seed determinism with cache | hash equal | TODO
F28 | post-cutoff flag per run | labelled | TODO
F29 | next-bar-open fill option + sensitivity | both series | TODO
F30 | coordination cost line (seconds, tokens vs excess) | reported | TODO
F31 | multi-seed (3) for architecture claims | mean±sd | TODO
F32 | backbone-swap test with a second GGUF | one run | TODO
F33 | Sortino, max DD alongside Sharpe | present | TODO
F34 | dumb-rule-beats-agent flag | present | TODO
F35 | portfolio metrics daily report (B3 list: PSR, DSR, IR, MinTRL, HHI±/time, DD, TUW, holding, flips, hit, payoff, expectancy R, exposure, book beta, VaR/ES, turnover, fees %, slippage) | every field non-null | TODO

### 4.11 Junk test (Research B §B5)
J1 | feed pool per sim day: true (GDELT), irrelevant, flipped, number-altered, style-laundered, bias-bait, direct instructions | pool composition logged | TODO
J2 | exposure rate (fake used in a card) | computed vs clean run | TODO
J3 | flip rate (decision differs from clean) | computed | TODO
J4 | rule-break rate (injected instruction obeyed) | must be 0 | TODO
J5 | P&L delta vs clean | computed | TODO
J6 | citation precision/recall (quote ∈ fetched text) | computed | TODO
J7 | numbers-before-text ordering A/B | both runs | TODO
J8 | source-trust weights | applied | TODO
J9 | cross-source corroboration required to change a side | enforced | TODO
J10 | ledger truth vs model belief (phantom positions) | zero phantom orders | TODO
J11 | pass criteria: flip rate < clean run-to-run noise; 0 obeyed instructions; 0 phantom | gate | TODO
J12 | style-laundered fakes detection via quote-grounding | detected rate | TODO

### 4.12 News and search (Research B §B9/§B10)
N1 | GDELT DOC 2.0 client, month-by-month pulls, stored with timestamp, language, url, title, snippet | 2021→ coverage for "bitcoin" | TODO
N2 | `news(query, days)` tool time-locked (sim) | no article after t | TODO
N3 | claim cards require verbatim quote + url + fetched_at | rejected otherwise | TODO
N4 | entity linking by engine lookup (coin names/tickers/projects/"FOMC"/"CPI") | coverage report | TODO
N5 | direction/magnitude tagged as hypothesis | field | TODO
N6 | SearXNG self-hosted for live search; Tavily fallback | health check | TODO
N7 | source reliability table (domain → weight) | applied to evidence | TODO
N8 | dedupe near-identical articles | duplicates merged | TODO
N9 | quote-in-text check before card accepted | fails on fabricated quote | TODO

### 4.13 Paper-trading day (Research B §B6)
Y1 | morning brief: overnight moves, funding/OI change, liquidations, ETF print, calendar with times, macro tape, news per position/candidate, prediction odds | all sections present | TODO
Y2 | intraday monitors (engine): falsifier/checkpoint, funding 8h, event windows, 2.5σ, corr→1, venue health, ledger reconciliation | each fires on synthetic | TODO
Y3 | event wake-ups limited to the position/event | scope logged | TODO
Y4 | evening review: grade, revise beliefs, market view, insights, calibration, next-24h search | all steps logged | TODO
Y5 | weekly: rule compliance, portfolio metrics, A/B counters, memory consolidation | report | TODO
Y6 | same ledger/costs as sim | fee function identity | TODO
Y7 | forward-only news in paper mode; no historical tool after boundary | audit | TODO
Y8 | Hermes Agent harness integration point (tools exposed as its skills) | one live decision through Hermes | TODO

### 4.14 Viewer (terminal pages)
I1 | graph page: force layout (Cytoscape.js or vis-network, single file, no build), node kinds coloured, edge origin styled, as-of slider | screenshot | TODO
I2 | click node → dossier (BFS-2) panel | screenshot | TODO
I3 | correlation heatmap, HRP-ordered, normal vs stressed toggle | screenshot | TODO
I4 | correlation-over-time chart (mean ρ, PC1, neff) with shock days marked | screenshot | TODO
I5 | beta-vs-idio scatter, colour by cluster, size by ADV | screenshot | TODO
I6 | belief board: live/resolved, three probabilities, evidence for/against, revisions timeline, Brier by kind | screenshot | TODO
I7 | links table with vintages drift chart | screenshot | TODO
I8 | decision replay: timeline, wake reason, questions/answers, cards, chains, verdicts, orders, outcome | screenshot | TODO
I9 | kill log / level ladder page | screenshot | TODO
I10 | compute audit page | screenshot | TODO
I11 | junk test scores page | screenshot | TODO
I12 | event calendar page with consensus/realised/surprise and priced-in | screenshot | TODO
I13 | all pages read as-of (no future) when a date is selected | shuffle test on API | TODO
I14 | all data via existing `/api/*` pattern in dashboard.py; no new server | routes listed | TODO

### 4.15 Small-model reliability (exams, dossier E/G, Trading-R1)
M1 | JSON schema-constrained output for every hat via llama.cpp `json_schema`/GBNF | zero parse failures over 50 calls | TODO
M2 | thinking on for strategist; off elsewhere; escalation rule (P10) | logged | PARTIAL
M3 | median-of-3 for numbers (B12) | logged | TODO
M4 | engine recompute of every number (E10, E31) | flagged | TODO
M5 | prompt caching / slots to cut prompt-eval time | seconds per decision before/after | TODO
M6 | exam re-run (knowledge + scenario) after each wave, scores tracked | table in wave report | TODO
M7 | Trading-R1-style labels generated for our decisions (vol-normalised 3/7/15-day blend, symmetric quantiles) | distribution | TODO
M8 | outcome-ranked trace dataset export (B40, E35) | files | TODO
M9 | second GGUF smoke test (F32) | run | TODO
M10 | funding-sign exam item must score 3/3 after P1 labels | re-run | TODO

## 5. Acceptance tests (the "new small test")
T1 **Fed-trade replay.** Pick a real FOMC date in 2025 (e.g. 2025-09-17). Run one decision on T−1 with time-locked GDELT news. Pass if: (a) the morning sheet shows the meeting tomorrow with consensus/odds; (b) ≥2 claim cards with verbatim quotes about the expected decision; (c) a belief of kind event_outcome with p_model/p_engine/p_final; (d) chains for BTC and ≥2 correlated legs with sizes from stressed beta and idio vol; (e) falsifiers on the correct side; (f) risk hat accepts or bounces with numbers; (g) if odds ≥ 0.9 for the decision, the strategist marks it priced-in and the belief board shows the priced-in score. Report every line from decisions.jsonl.
T2 **Junk day.** Same date, feed pool with fakes. Pass per J11.
T3 **Small test v2.** Aug 10–18 2026, all 172 coins, all hats, risk hat, links, beliefs, graph. Compare to the 2026-09-15 small test on: orders bounced by risk hat, stop sizes in idio daily moves, beliefs created/resolved, Brier, excess per trade, calibration. Both runs' logs side by side.
T4 **Selftest.** `python scripts/selftest.py` prints the checklist table with pass/fail; zero fails in EXISTS items.

## 6. Avoid (from the evidence)
Bull/bear debate rounds · an LLM risk manager · reflection prompts on the small model · persona prompts · any claim from a pre-cutoff window · unmeasured links shown as facts · single-variable feature tests · self-modifying code without an out-of-sample gate · restricted `exec` as a sandbox · trusting a model-printed number · a check that cannot fail.

## 7. Counts
Existing-code verification 60 · cross-sectional 48 · events/links 51 · memory graph 45 · beliefs 47 · compute/skills 36 · risk hat 20 · reviewer 10 · prompts/tools 14 · survival 35 · junk 12 · news 9 · paper day 8 · viewer 14 · model reliability 10 · acceptance 4 = **423 checklist items**, plus the 272-feature catalogue in Research B §B7 (each feature = fill + verify = its own line in the wave logs) → 695 tracked lines. Status today: 5 EXISTS, 46 PARTIAL, the rest TODO.
