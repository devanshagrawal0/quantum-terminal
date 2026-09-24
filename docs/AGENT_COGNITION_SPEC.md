# The trader's mind — how the LLM agent investigates, connects, decides, remembers
2026-09-16. Spec, not code. Written after Dev's brief: "it should ask many questions,
look at everything it can, think, connect things and events." Every mechanism below
names the research it comes from and the data in OUR store it runs on.

## 0. What we are replacing
The current LLM agent gets one prompt: a table, five pasted lessons, "answer in JSON".
It cannot ask, look, or argue. It is a rule bot with a language model attached.

## 1. Research basis (what is known to work, and its limit)

| mechanism | source | what it showed | limit we must respect |
|---|---|---|---|
| **Ask follow-up questions explicitly before answering** | Self-Ask (Press et al. 2022) | models that state "Follow up: …" and answer sub-questions close the "compositionality gap" — they often know every fact but fail to compose them | questions must be answerable by a tool, not by the model's memory of history |
| **The model pages its own memory with function calls** | MemGPT (Packer et al. 2023) | a model that calls `search`/`write` on external storage and chains calls ("request heartbeat") answers multi-step questions no single prompt can | every retrieval must be time-locked and logged |
| **Memories link to each other and evolve** | A-MEM (Xu et al. 2025) | new notes trigger link generation to related old notes and update their descriptions — higher-order patterns emerge | links must be earned by shared attributes, not invented |
| **Insights with a lifecycle** | ExpeL (Zhao et al. 2023) | ADD / UPVOTE / DOWNVOTE / EDIT from success-vs-failure pairs; removed at zero | + our quant gate: out-of-sample support before active |
| **Reflect on failures, retry** | Reflexion (Shinn et al. 2023) | verbal self-critique stored and reused beats retrying blind | outcomes arrive with market delay; reflect at close, not at decision |
| **Roles with different eyes, then a debate, then risk** | TradingAgents (Xiao et al. 2024/25) | seven roles (fundamentals / sentiment / news / technical analysts, bull+bear researchers, trader, risk manager) each with its own tools; debate rounds before the trade | their evaluation is 4 tickers, no costs — the ROLE SEPARATION is the transferable idea, the returns claim is not |
| **Skills become code** | Voyager (Wang et al. 2023) | a library of verified executable skills compounds ability and stops forgetting | a skill runs only after the simulator verified it on held-out trades |
| **Written first, outcome embargoed, provenance on every fact** | Agentic Trading survey (2026) | 0 of 19 learning-trader studies reproducible; these three rules are the prescription | non-negotiable |

## 2. The eyes — everything it can look at (all time-locked to the decision moment)

Tools the model can CALL (not data pasted at it). Each returns numbers + a source stamp.

**Market state**
- `market_table(universe)` — the feature columns it asks for, from 145 available (`feat_*`)
- `regime()` — BTC 30-day label + breadth (% coins green 1d/7d) + BTC/ETH dominance trend (`hl/regime.py`)
- `correlations(coins)` — 30-day correlation to BTC and to each other (concentration risk)
- `cross_venue(coin)` — Hyperliquid spread, basis to spot, venue dispersion (`cv_features`)

**Crowd and money**
- `positioning(coin)` — share of Binance accounts long, top-trader share, OI, and their 7-day change (`positioning`)
- `funding(coin)` — current + 7-day funding; who is paying whom (`perp_state`, carry cache)
- `fear_greed()` — index and 30-day path (`macro_series`)

**Events and calendar**
- `unlocks(days)` — token unlocks in the window with size and % of max supply (`unlocks.db`)
- `scheduled(days)` — listings, macro releases, governance votes in the window (`scheduled_event`, 142 rows)
- `macro(series, days)` — Fed funds, US 10y, EUR/USD, euro 10y, policy rates, CPI (`macro_series`); oil/DXY/breakevens/VIX once the FRED key lands
- `prediction_markets(query)` — Kalshi / Polymarket odds (8,500 markets) — the market's stated probability of an event
- `news(days, query)` — live feed for paper trading; historical only once `document` holds articles (today it does not). **Rule: news is forward-only** — masking cannot hide a headline's date from a model that read the internet.
- `geo_events(days)` — 3,122 rows of physical/geopolitical events (`geo_event`)

**Its own mind**
- `similar(coin)` — the 20 most similar past situations by feature distance and what happened
- `evidence(setup, regime)` — decayed track record: n, mean excess, win rate
- `stops_report(setup)` — from counterfactuals: how often the stop fired and the target hit later; which stop/target grid paid
- `analogues(event_type)` — past events of the same TYPE (unlock cliff, Fed day, listing) and what the target did (links to the experiences that traded them — A-MEM links)
- `insights()` — active rules with importance and out-of-sample support
- `calibration()` — its stated confidence vs actual win rate
- `market_view(last_n)` — its own previous weekly views (continuity of thought)
- `recall(query)` — full-text over its lessons
- `write_note(text, tags)` / `link(note_a, note_b, why)` — MemGPT/A-MEM: it may store and link what it wants remembered

Every call is appended to an **evidence log** for that decision: tool, arguments, result, timestamp. The decision's record carries the log. That is provenance.

## 3. The investigation loop — how it asks questions

One decision = a procedure with several model calls ("hats"), same model, different instructions.

**Hat 1 — Investigator.** Must answer a desk checklist, then may ask more:
1. What is the regime, and did it change since my last view?
2. What is crowded? (positioning + funding extremes)
3. What is scheduled in the next 7 days that could move my candidates? (unlocks, macro, listings)
4. What moved unusually this week and why might it have? (vol z-scores, breadth, cross-venue anomalies)
5. What does my own record say about the setups I'm about to take, in this regime?
6. What are the 20 situations most like each candidate, and what happened?
7. What is the market already pricing? (prediction markets, funding, basis)
8. What would make me wrong, and by when?
Each answer is a tool call (Self-Ask: "Follow up: …" then the call). It may ask up to N extra questions. Output: a set of **evidence cards** (fact, source, timestamp) and a 3-line market view (stored).

**Hat 2 — Strategist (connect the strings).** Given the cards, it writes **chains**, not just picks:
```
event/observation → mechanism → affected instrument(s) → expected sign, size, delay
   → falsifier (what would prove it wrong, by when) → checkpoint(s) (what should be
   visible at day 2 / day 4) → order (side, stop, target, hold) → confidence
```
Where a link has a MEASURED response in the links engine (local projections, plan §11.3 — funding→return, positioning→return, unlock-size→return, 10y→BTC, Fear&Greed→alts), the number is shown to it; where not, the chain is tagged `[unmeasured]` and confidence is capped. The model proposes the chain; the data prices the links. This is the rule that keeps chains from being confident fiction.

**Hat 3 — Skeptic.** Gets the orders + the evidence cards + the counter-evidence the engine can find (contradicting similar situations, insights that argue against). Must attack the weakest order: veto, resize, or let stand — with a reason. TradingAgents' bull/bear compressed to one pass; whether it helps is an A/B in the sim, not an assumption.

**Hat 4 — Risk (no model call).** Sizes each surviving order from the model's stated confidence mapped through its actual calibration (meta-labeling), applies the pre-trade rules already in `hl/preflight.py` (no melt-up shorts, no correlated over-concentration), caps total exposure. The model never sizes.

**Hat 5 — Reviewer (at close, losses only + periodic).** Reflexion on each losing close: with the path and counterfactuals, classify the miss — thesis / timing / risk plan / regime — and write the lesson. Every ~20 closes: an ExpeL round over success-vs-failure pairs → ADD / UPVOTE / DOWNVOTE / EDIT insights; proposals enter the quant gate. Checkpoints are graded separately from P&L, so the chain's broken LINK is named, not just the outcome.

**Budget on this box:** ~4 model calls per weekly decision (investigator may take 2 with follow-ups), ~5 min. A simulated year ≈ 4–5 hours in batches. Thinking mode on for the Strategist only, until measured otherwise.

## 4. Memory — what it remembers and how it changes
- **Experience notes** (built): the trade, its numbers, the grade, counterfactuals, lesson.
- **Evidence cards + market views** (new): what it looked at and what it thought each week.
- **Links** (new, A-MEM): a new note is linked to notes sharing event type, setup, coin, or a near feature vector; when a link is made the older note's summary can be updated ("this unlock pattern has now happened 6 times: 5 down"). Analogues come from these links.
- **Insights** (built): lifecycle with the quant gate.
- **Skills as code** (later, Voyager): an active insight becomes a verified executable screen that runs before the model is called.
- **Decay and importance** (Generative Agents): recency × relevance × |excess|.
- **Embargo**: nothing about a trade is retrievable before its close; nothing about an event before its outcome horizon has passed.

## 5. Build order — each step is a small test on the same 8 weeks before the next
1. **Tools + investigator loop** over the data we have (market, positioning, funding, cross-venue, unlocks, scheduled, macro, prediction markets, own memory). Test: does the tool-driven agent make different decisions than the spoon-fed one, and does its evidence log show it actually asked? Measure excess and calibration on the same 8 weeks.
2. **Chains with falsifiers and checkpoints**, graded per link. Test: are checkpoints being hit or missed, and does the miss category vary (not all "thesis")?
3. **Skeptic + calibrated sizing + preflight.** A/B with vs without.
4. **Reviewer**: reflection on losses, ExpeL rounds. Test: insight proposals appear and some earn activation.
5. **Links engine** measured responses shown to the Strategist for the links we can measure today; FRED series when the key lands.
6. **Skills as code.**
7. **Live paper via the Hermes Agent harness** with web tools (forward-only news), same ledger.

## 6. Questions for Dev (the agent should ask; so should I)
1. Cadence in the simulator: weekly decisions only, or also event-driven wake-ups (unlock within 3 days, funding extreme, vol spike)? Event-driven is closer to the plan (§3.1) and costs more calls.
2. Universe: the 40–60 tightest-spread coins as now, or everything with data (172) and let it screen?
3. News: accept forward-only (paper trading) for news reasoning, or invest in a historical article store knowing the model may recognise the headlines?
4. Thinking mode budget: ~2× slower per call. Allow it on the Strategist only?
5. Which measured links first for the engine: funding→return, positioning→return, unlock→return, or the macro ones (need FRED)?

Nothing in this document is built. It is the plan for the next builds, each to be shown on real output before the next.

Sources: Self-Ask https://arxiv.org/abs/2210.03350 · MemGPT https://arxiv.org/abs/2310.08560 ·
A-MEM https://arxiv.org/abs/2502.12110 · ExpeL https://arxiv.org/abs/2308.10144 · Reflexion
https://arxiv.org/abs/2303.11366 · TradingAgents https://arxiv.org/abs/2412.20138 · Voyager
https://arxiv.org/abs/2305.16291 · Generative Agents https://arxiv.org/abs/2304.03442 · Agentic
Trading survey https://arxiv.org/html/2605.19337v1 · plan: newsystem.md §3, §11, §14
