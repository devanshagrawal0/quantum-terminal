# How the trading agent works — every part, honestly, and what is missing
2026-09-16. Written for Dev in plain English after he asked "tell me how it works in each way,
the connection to events and chains, beta and correlation, idiosyncratic coins, heatmaps, all the
quant things you said you researched and made." Every claim below was checked against the code
and the database on this date. Where I said something was made and it was not, it says so here.

---

## 0. The honesty table first: what I said vs what actually exists

I described several things as if they were part of the agent. Some are. Some exist only for the
live terminal and the simulated agent cannot see them. Some exist as an empty table with a nice
column list. Some are only sentences in a plan. Here is the real state:

| Thing | Where it stands today | Can the agent use it right now? |
|---|---|---|
| Event → mechanism → coin → direction chains | The strategist is asked to write them and does (see §3). The MEASURED strength of each link ("Fed surprise → BTC −X% over 1 day, n=, t=") is **not built** — plan §11.3 (local projections) only. | Chains yes; measured links **no** |
| Fed / rates data | `macro_series` has US Fed funds daily 1954→2026 (26k rows), US 10y (16k rows), ECB rate, EUR/USD (500 rows from 2024-09), Fear&Greed 2021→. Tool `macro_rates` reads it. | **Yes**, as levels and changes |
| Fed meeting calendar (FOMC dates, surprise vs consensus) | `scheduled_event` has **only token unlocks (142 rows)**. No FOMC dates. The `consensus/realized/surprise` columns exist but nothing fills them. `feat_calendar` (days to next event, historical move) is an **empty table**. | **No** |
| Beta to BTC, correlation matrix, residual (idiosyncratic) return, idio vol, clusters, RRG rotation | `feat_cross` and `feat_xsec` tables exist with exactly these columns — **0 rows**. `resid_r_1d / resid_mom_7d_skip1` columns in `feat_price` are **all NULL**. | **No.** Only the on-the-fly `correlations` tool (30-day corr to BTC and pairwise, from daily closes) works — that one is real |
| Heatmaps | One exists: the calendar-seasonality heatmap (`scripts/seasonality.py`, `docs/CALENDAR_SEASONALITY.md`). A correlation heatmap, a funding heatmap, a beta-vs-idio map: **not built** | **No** |
| Regime | Sim: BTC 30-day return only (UPTREND/DOWNTREND/CHOP) + breadth. Live terminal: `hl/regime.py` (adds dominance, funding lean) and `hl/macro_regime.py` (the −100..+100 tide score) — **live-only, not time-locked, not wired to the sim** | Basic yes; the good one **no** |
| Rotation (BTC → ETH → large → small → memes ladder), top/contagion risk monitors | `hl/rotation.py`, `hl/risk.py` — live terminal only, read live APIs | **No** |
| Connection map (a coin's web of drivers), per-coin dossier and intel reports | `hl/graph.py`, `hl/dossier.py`, `hl/intel.py` — live terminal only | **No** |
| Crowd: funding, long-share, top-trader share, OI | Real and wired: funding daily from 2025-08-13, Binance positioning from 2026-08-02, OI from 2026-08-23. Tools `funding`, `funding_extremes`, `positioning`, `open_interest` | **Yes** |
| Unlocks with size and % of supply | `hl/unlocks.py`, tool `scheduled_events` | **Yes** |
| Geopolitical / physical events ("3,122 rows") | `geo_event` — **all 3,122 rows are USGS earthquakes**. Nothing political | Not exposed; and would be useless as is |
| Prediction markets (8,500 Kalshi/Polymarket) | Stored. **Not exposed** to the agent (no tool) | **No** |
| News | Live feed exists for the terminal; historical `document` store is junk. Sim: forward-only, **no news tool yet** | **No** |
| On-chain (exchange netflow, stablecoin supply, whale flips) | `feat_onchain` — **empty table** | **No** |
| Options (IV, skew, gamma exposure) | `feat_options` — **2 rows** | **No** |
| Derivatives features in `feat_deriv` (funding z-score, cascade fragility, liquidation clusters) | Table has 26k rows but those columns are **NULL**; only spot basis is filled | **No** (the raw funding/positioning above is what works) |
| Liquidity (spread, depth, Amihud) | `feat_liq` spread_bps filled (26k rows); Amihud etc. NULL. Spreads are used for costs | Costs **yes**; the rest **no** |
| Own memory: experiences, evidence, similar situations, insights, notes, calibration, counterfactuals | Built and wired (§7) | **Yes** |
| Simulator with real costs, stops on daily range, funding, excess-vs-market grading, MFE/MAE, counterfactual grid, falsifier exits | Built and wired (§6) | **Yes** |
| Three "hats": investigator (asks, uses tools), strategist (chains, thinking on), skeptic (attacks, veto/resize/replan) | Built and wired; skeptic's arithmetic is unreliable (§9) | **Yes**, with the known weaknesses |
| Risk hat (engine sizes and rule-checks orders, no model call) and Reviewer hat (reflection on losses, insight rounds) | **Not built** | **No** |

So: the crowd data, the unlock calendar, the macro levels, the memory, the simulator and the three
hats are real. The cross-sectional quant layer (beta / residual / clusters), the event calendar
beyond unlocks, the measured event→price links, the heatmaps, and the live terminal's brain
modules are either empty tables or not connected to the agent. I should have said that plainly
each time instead of describing the plan as if it were the product.

---

## 1. The whole loop in one page

One simulated day at a time, from 2021 to today, the agent lives inside a time-locked copy of
our data. At 23:00 UTC of each day it can only see what existed by then. It never sees the
future, coin names are hidden (C1..C172), dates are hidden.

```
                    ┌──────────────────────────────────────────────────────────┐
 our store.db ───►  │ AsOf(t): daily prices, 145 features at the 23:00 bar,     │
 (time-locked)      │ funding, positioning, spreads, macro, unlocks             │
                    └──────────────────────────────────────────────────────────┘
                                             │
   wake-up? (weekly, or regime flip, breadth extreme, BTC >2.5σ day, funding extreme)
                                             │
 ┌──────────────────── one DECISION (about 8 minutes on this PC) ─────────────────────┐
 │ Hat 1 INVESTIGATOR (thinking off, up to 3 rounds, 6 tool calls each)               │
 │   gets a morning sheet (regime, unusual volume, momentum extremes)                  │
 │   asks follow-up questions → each answered by a TOOL (real numbers, stamped)        │
 │   ends with: market view (3 lines), evidence cards (fact + source), candidates       │
 │ Hat 2 STRATEGIST (thinking ON)                                                       │
 │   only the cards + candidate rows (with each coin's typical daily move)              │
 │   writes CHAINS: observation → mechanism → expected move → falsifier → checkpoint    │
 │   → order (side, stop, target, hold) → confidence                                    │
 │ Hat 3 SKEPTIC (thinking off)                                                          │
 │   engine builds a counter-dossier per order (funding, crowd, own record, similar     │
 │   situations, stop in daily moves, correlation between orders)                       │
 │   must name the weakest order; veto / resize / replan / stand each, with a reason    │
 └──────────────────────────────────────────────────────────────────────────────────────┘
                                             │
                    BOOK opens survivors at the close, $100 each, real fee + half spread
                                             │
   every following day: settle at that day's high/low/close (stop, target, falsifier, time)
                                             │
   at close: GRADE (net, excess vs market, best/worst point, counterfactual plans, path)
             → LESSON (plan vs outcome vs best plan; checkpoint HIT/MISSED; falsifier TRIGGERED)
             → MEMORY (experience row, evidence tables, similarity index, insight votes)
                                             │
   next decision: the tools `evidence`, `similar`, `stops_report`, `insights`, `calibration`,
   `market_view`, `recall` read that memory back — that is the learning loop
```

The runner writes `decisions.jsonl` in the run folder: every question asked, every tool result,
the cards, the strategist's raw answer, the skeptic's raw answer, what opened. Nothing is hidden.

---

## 2. The data it sees (and the data it does not)

**Prices.** Hourly OHLCV for 172 Hyperliquid coins, rebuilt into daily open/high/low/close. Stops
and targets are checked against the day's real high and low, so an intraday hit counts.

**145 features at the 23:00 bar** from the `feat_*` tables that are actually filled: returns at
1d/3d/7d/30d, momentum skipping the last day, RSI, MACD, ADX, moving-average distances, realised
vol (7d, 30d), ATR, Bollinger/Keltner widths, drawdown, volume z-score, spread. The agent asks
for any slice of any of these through `market_table`.

**Crowd.** Funding per coin per day (who pays whom), Binance long-share of accounts, top-trader
long share, open interest, and their 7-day changes.

**Macro.** Fed funds, US 10y, ECB rate, EUR/USD, Fear & Greed — as levels and recent changes.

**Calendar.** Token unlocks in the next N days with size and % of max supply.

**Its own mind.** Everything in §7.

**What it cannot see today** (from the table in §0): beta and residual returns, clusters,
rotation, FOMC dates, prediction-market odds, news, on-chain, options, the live terminal's regime
and risk monitors.

---

## 3. Events → chains: how the "Fed hikes, BTC falls" trade works here

This is the part Dev cares about most, so here is exactly how it is supposed to run, what runs
today, and what is missing.

**The idea.** An event (Fed surprise hike) has a mechanism (dollar and real yields up → risk
premium up → leveraged longs get liquidated) that hits instruments in an order (small caps >
ETH > BTC, funding compresses in the same order) with a size and a delay, and there is something
that would prove it wrong by a date (DXY reverses, funding flips, price reclaims the high).
Writing the chain out forces the model to say WHY, WHICH, WHICH WAY, HOW MUCH, WHEN, and WHAT
KILLS IT — not "BTC bearish".

**What runs today.**
- The strategist prompt demands that structure and the model produces it. Real output from the
  Aug 13 decision: *"Extreme negative funding (−1.58%) combined with falling OI and rising long
  share indicates shorts are trapped and covering → squeeze up → long, stop 15.8% (1.5 daily
  moves), falsifier: price −5% by day 2, checkpoint +10% by day 4."*
- The falsifier is enforced by the book: if price crosses it on that day, the trade closes with
  reason `falsifier` (replayed on the small test: the XMR short closed on day 2 at −4.3% instead
  of the stop at −6%).
- The checkpoint and falsifier are graded into the lesson: *"falsifier day 2: limit +3%, got
  +4.3% → TRIGGERED"*. So the chain's broken LINK gets named, not just the P&L.
- Macro levels are available (`macro_rates`): the model can see Fed funds moved +50 bps this
  week. It cannot see that a meeting is scheduled, or that the move was a surprise.

**What the exam showed.** Given the Fed-surprise scenario with thinking off, the model said "no
edge" and flipped both signs; with thinking on it ranked alt > ETH > BTC down with sizes and a
falsifier. Thinking stays on for the strategist for that reason.

**What is missing, in build order.**
1. **The event calendar beyond unlocks.** FOMC dates (published years ahead), CPI/NFP release
   times, with consensus and realised values so `surprise` can be filled. The `scheduled_event`
   table already has the columns. Then `feat_calendar` (days to next event, what the coin did
   historically around that kind of event) stops being empty. Dev's rule from the plan: any date
   a scheduling body announces goes in the calendar.
2. **The links engine (plan §11.3).** For each (event type → target → horizon) a local
   projection: "after a +25 bp Fed surprise, BTC moves −x% over 1h / 1d / 3d, n=, t-stat=".
   The first link is funding → return (Dev's pick), because we have 13 months of funding history
   now; Fed links need the calendar first. The measured number is then SHOWN to the strategist
   next to its chain; a chain with no measured link is tagged `[unmeasured]` and its confidence
   is capped. That rule is what stops chains being confident fiction.
3. **Event analogues in memory (A-MEM links).** When an unlock trade closes, it links to every
   other unlock trade; `analogues("unlock")` returns "6 unlock trades, 5 went down into the
   date" — a learned event response, separate from the statistical one.

---

## 4. Beta, correlation, idiosyncratic — what it means and where it stands

**What the words mean.**
- **Beta to BTC**: if BTC moves 1%, this coin moves β%. β=2 is a leveraged BTC bet; β≈0 moves on
  its own.
- **Correlation matrix**: for every pair of coins, how much they move together over the last
  30/60/90 days. Four alts at 0.85 correlation are one bet, not four.
- **Residual (idiosyncratic) return**: the coin's move AFTER removing what BTC explains
  (`r − β·r_BTC`). Momentum on residual returns is the coin's OWN story; momentum on raw returns
  is mostly BTC's story wearing a costume.
- **Idio vol**: volatility of the residual. The plan's rule: size on residual vol, never total
  vol.
- **Clusters**: groups found from residual-return correlations (not hand-labelled sectors),
  re-estimated monthly; rotation between clusters is what "money moving down the risk curve"
  looks like in numbers.
- **The heatmap Dev means**: the coin × coin correlation matrix drawn as colour, and the same
  thing over time (does the market become one trade during a crash — yes, correlations go to
  0.9+ in stress; the plan calls for a "stressed correlation matrix" computed only on the worst
  10% of days).

**What exists.** The on-the-fly `correlations` tool (30-day, to BTC and pairwise) — real, used
by the skeptic to check whether proposed orders are one bet. `hl/graph.py` builds a 60-day
correlation web for the live terminal. Everything else — `beta_btc`, `corr_btc_30d/90d`,
`resid_r_*`, `idio_vol`, `r2_btc`, `cluster_id`, `rrg_x/y`, `corr_break_flag` — is a column
name in an empty table. The kill test never tested residual momentum because it was NULL.

**What to build.** A daily job that fills `feat_cross` from the closes we already have (β shrunk
toward 1, 30/90-day corr, residual returns, idio vol, R²), then the clusters, then expose them
as columns the agent can ask for and the skeptic's dossier uses (residual vol for stop sizing;
"this coin is 92% BTC" as a fact). The correlation heatmap is a drawing of that table.

---

## 5. The crowd: funding, positioning, open interest

This is the strongest real data the agent has, and it is where the model is weakest at signs.

- **Funding**: positive = longs pay shorts = crowded longs; negative = shorts pay longs = crowded
  shorts, squeeze risk is UP. The `funding` tool returns `who_pays` in words. The exam showed the
  model gets this backwards in one phrasing out of three, so the next change is that every tool
  result carries the engine's own label ("shorts crowded — squeeze risk UP") and the model is
  never asked to infer it.
- **Long share of accounts / top-trader share**: how many Binance accounts are long; top traders
  vs retail. 7-day change tells whether the crowd is piling in or leaving.
- **Open interest**: money in the perp. OI up + price down = new shorts; OI up + price flat +
  funding flat = hedged positioning, not a directional bet (the model got this one right).
- **Wake-ups**: the runner wakes the agent when |funding| > 0.3%/day on 3+ coins — two of the
  three small-test decisions were funding wake-ups.
- Not built: funding z-score vs its own history, cascade-fragility (OI × funding × leverage),
  liquidation clusters. The columns exist; nothing fills them.

---

## 6. The simulator: how a trade is judged

- **Costs**: 4.5 bps taker + half of that coin's measured spread, on entry and exit. Funding is
  charged/credited daily where we have it.
- **Exits**: stop or target on the day's high/low (filled at the level, no gap modelling —
  optimistic, stated); falsifier at that day's close; time expiry at the close.
- **Grade at close**: net P&L; **excess** = net minus the average move of every tradable coin over
  the same window in the trade's direction (so a long that made 3% while everything made 5% is a
  −2% decision); MFE/MAE (best and worst point reached); a **counterfactual grid** — the same
  entry under stops 3/6/9% × targets 6/12/18% and the opposite side, on the observed path; the
  daily path in the trade's favour.
- **Lesson**: written by code, no model: plan vs outcome vs the best plan on that path, plus the
  checkpoint/falsifier verdicts. Example from the small test: *"long ACE: stop after 1d, net −477
  bps; reached +5,479 for / −535 against. Best plan on this path: long s6:t18 → +1,822 bps."*
  That single line is what taught the strategist to size stops in daily moves.
- **Summary per run**: trades, net, per-trade bps, excess per trade, hit rate, Sharpe, max
  drawdown, exit mix, memory stats.

---

## 7. Memory — what it remembers and how it changes its mind

- **Experience** (one row per closed trade): features at open, setup, regime, thesis, confidence,
  net/excess/MFE/MAE, exit reason, counterfactuals, lesson. Full-text searchable (`recall`).
- **Evidence** (`evidence(setup, regime)`): the decayed track record of a setup — n, mean excess,
  win rate — with a 90-day half-life so 2021 lessons fade unless repeated. Time-locked: nothing
  from after the decision date, nothing from a trade still open.
- **Similar situations** (`similar(coin)`): the 20 past situations nearest in feature space (a
  k-NN over the stored feature vectors) and what happened to longs there. This is how "have I
  seen this before" works.
- **Thompson sampling**: when the rule agents choose setups, they sample from the posterior of
  each setup's excess instead of picking the best mean — so a setup that failed once is not
  closed forever, it is just tried less until evidence changes (the fix Dev demanded after v1).
- **Insights**: a rule proposed from a statistically bad pattern enters as `proposed`; it is
  voted on by every later out-of-sample trade; it becomes `active` only with ≥10 out-of-sample
  trades of the same sign; retired when importance decays to zero or the sign flips. This is
  ExpeL's add/upvote/downvote with a quant gate in front.
- **Notes** (`write_note`, `market_view`): the agent's own weekly view, stored and read back next
  week, so its thinking has continuity.
- **Calibration**: its stated confidence vs realised win rate per bucket; the skeptic sees it.
- **Stops report**: from the counterfactual grid, how often the stop fired before the target
  would have hit, and which stop/target plan paid best for that side.

Not built: links between memories (A-MEM), event analogues, the Reviewer hat that reflects on
losses in words and runs the insight rounds, skills-as-code (an active insight becoming an
executable screen).

---

## 8. Wake-ups: why it is event-driven

Every day is settled; the model is only called when something happened: weekly baseline; the
regime label flipped; ≥90% or ≤10% of coins green on the day; a BTC day beyond 2.5σ; funding
beyond 0.3%/day on 3+ coins; 2-day cooldown. In August 2026 that produced 3 decisions in 8
days. When the calendar gets FOMC/CPI dates, "event within 3 days" becomes a wake-up too.

---

## 9. What the two exams found (the model's real ability)

Knowledge exam (32 questions) and scenario exam (18 invented situations), answers saved in
`scratchpad/exam_answers.json` and `scratchpad/iq_answers.json`.

| Faculty | Thinking off | Thinking on | Evidence |
|---|---|---|---|
| Recalling mechanisms (macro, perps, factors) | 50 | — | textbook-correct on most, invents literature details, funding annualisation wrong (21.9% vs 54.75%) |
| Funding sign convention | 45 | — | flips in 1 of 3 phrasings; wrote "negative funding means you pay to hold longs" |
| Arithmetic in-line | 45 | 80 | "0.21 / 7.0 = 0.03 daily moves"; "8.4%/day" for −1.2%/8h; headline before the sum |
| Event → instrument chaining | 62 | 85 | Fed-surprise: "no edge" and both signs flipped, vs alt>ETH>BTC down with falsifiers |
| Judgement on a table | 55 | 65 | shorted the unlock landmine (off); set 0.55× daily-move stops with the vol printed (both) |
| Deferring to own record | 85 | — | correct expectancy arithmetic, named overriding evidence |
| Attacking a thesis | 60 | 90 | found the weak link both ways; cost arithmetic wrong off |
| Learning from an outcome | 88 | — | ACE case: "risk plan wrong, stop ≥1.5–2× daily range" |
| Abstaining | 95 | — | but over-fires on hard questions |

The finding that matters: it states the stop rule perfectly when asked and breaks it ten minutes
later when trading. It knows the funding convention two times out of three and still writes theses
with it backwards. Knowledge is not the bottleneck — application is. That decides the design:
every number and every sign is computed by the engine and handed over as a fact; the model
proposes mechanisms and reads evidence; the engine prices links, checks rules, and sizes.

---

## 10. Build order from here (each step shown on real output before the next)

1. **Crowd labels in every tool result** ("shorts pay longs — shorts crowded — squeeze UP") and
   a small local fact library the investigator can read (perp mechanics, unlock mechanics, our
   own measured facts like "1-day reversal is real and dead after costs").
2. **Risk hat (no model call)**: stop in daily moves within [1.5, 3], falsifier on the correct
   side and smaller than the stop, correlation between orders and open positions, size from
   stated confidence through calibration, `hl/preflight.py` rules. Orders that fail go back to
   the strategist with the number, not into the book.
3. **Fill `feat_cross`** (beta, corr 30/90, residual returns, idio vol, R²) from data we already
   have; expose to the agent; residual vol for sizing; the correlation heatmap as a page in the
   terminal.
4. **Event calendar**: FOMC, CPI, NFP with consensus/realised/surprise; `feat_calendar`; event
   wake-ups; historical move around each event kind.
5. **Links engine**: funding → return first (local projections at 1d/3d/7d, with n and t-stat),
   then unlock-size → return, then Fed-surprise → BTC once the calendar exists; measured numbers
   shown to the strategist; unmeasured chains capped.
6. **Reviewer hat**: reflection on losses in words; ExpeL insight rounds every ~20 closes;
   event analogues via memory links.
7. **Full-August run** (~8 decisions), then a 2025 year in batches, then the same year with
   the skeptic off (A/B) — that is where "does it trade well" starts to be answerable.
8. Later: skills as code; teacher-run dataset from these decisions → fine-tune a 4B model on
   graded examples (Trading-R1 style) so the rules become habits instead of prompts.

---

## 11. Where everything lives

| Piece | File |
|---|---|
| Time-locked data view | `sim/data.py` (`AsOf`) |
| Book, costs, exits, grading, counterfactuals, falsifier exit | `sim/engine.py` |
| Memory (experience, evidence, similar, insights, notes, calibration) | `sim/memory.py` |
| Rule agents, regime label, lesson writer | `sim/agents.py` |
| The tools (what the investigator can ask) | `sim/tools.py` (`Toolbox.SPEC`) |
| Investigator / strategist / skeptic | `sim/investigator.py` |
| Runner, wake-ups, decisions log | `sim/run.py` |
| Run outputs | `data/sim/runs/<stamp>_investigator/decisions.jsonl`, `summary.json` |
| Memory database | `data/sim/memory_investigator.db` |
| Model server | `C:\llm\run-qwen.ps1` (llama.cpp, Qwen3.6-35B-A3B, port 8080) |
| The cognition spec this follows | `docs/AGENT_COGNITION_SPEC.md` |
| The master plan (links engine §11, calendar §14, features §16) | `newsystem.md` |
| Kill test of single features (why no single feature is traded) | `docs/KILL_TEST_2026-09-13.md` |
| Learning engine v2 rationale | `docs/LEARNING_ENGINE_V2.md` |
| The two exams | `scratchpad/exam.py`, `scratchpad/iq_test.py` + their `*_answers.json` |
