# Chapter 11 — How to be a trader: what to look at first, how a trade is built, cut, exited and learned from

Knowledge (chapters 1–10) tells you what things mean. This chapter is the *process*: the
order you look at things, the shape every trade must have, when you leave, and what you
write down so the next trade is better. Most of it is enforced by the engine; this is the
reason behind each rule so you apply it in the parts the engine cannot see.

## 1. What a trade is

A trade is a **claim with a price and a deadline**: "because of X (mechanism), this coin
should move Y (expected move) by day D (checkpoint); if instead it does Z (falsifier) I am
wrong and I leave; if it does neither by day H I leave (time)". Every one of those five
parts is required. This is the *triple barrier* — profit target, stop, time limit — that
quantitative desks use to define an outcome rather than "predict a price" [source: López de
Prado's triple-barrier method, https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/],
plus the falsifier, which is the trader's version: a *reason-based* exit that fires before
the price-based one.

Expectancy is the only thing that matters over many trades: **mean R** per trade, where R
is the profit or loss divided by the amount risked at the stop [source:
https://www.pnlledger.com/expectancy-r-multiples-the-plain-english-guide/]. A 35% hit rate
is profitable when winners average > 1.9R; a 60% hit rate loses when losers are bigger
than winners. Van Tharp's benchmark for a professional system is roughly 0.2–0.8R per
trade, and he argued you cannot judge an edge on fewer than ~50 trades [source:
https://crosstrade.io/learn/performance-metrics/r-multiple]. **[our desk]** the memory
stores every trade's excess vs BTC, MFE, MAE and exit reason so mean R is computed, not felt.

## 2. Why the process matters (the economics)

The market charges you on both sides: a round trip costs ≈ 12–15 bps (4.5 bps taker + half
spread, each side) before funding. The measured edges in this market are **small and slow**:
the funding link is ~24 bps over 7 days before carry, ~100 bps with carry on the paid side,
nothing at 1–3 days **[measured in our store]**; calendar tilts are 0.3–0.5%/day. That
arithmetic decides the trader's behaviour: trades must be multi-day, few, sized by
volatility, and free of the two things that destroy small edges — over-trading (paying the
round trip for nothing) and one big uncontrolled loss (which no edge of 30 bps/week can
repay). Discipline is not a virtue here; it is the only way the numbers add up.

## 3. The process

### 3a. What to look at first, in this order (the checklist the engine gates)
| step | question | tool / chapter |
|---|---|---|
| 1 | What regime? BTC's 30-day trend, breadth, correlation level (calm vs stressed) | `regime`; ch3, ch6 |
| 2 | Where is the crowd? Funding extremes, positioning, OI | `funding_extremes`, `positioning`; ch5 |
| 3 | What is on the clock? Macro inside 24 h, unlocks, listings, expiry | `calendar`, `scheduled_events`; ch8, ch9 |
| 4 | Who moved and why? Movers by own move, vol z-score, 7-day return | `market_table`; ch10 |
| 5 | What does my own record say about this kind of trade? | `evidence`, `stops_report`; ch12 |
| 6 | What happened the last times this situation occurred? | `similar`, `event_history`; ch8 |
| 7 | What kind of coin is each candidate? beta, R², own move, cluster, spread | candidate rows; ch3, ch7 |
| 8 | What kills the idea? Write the falsifier before the order | ch11 §3b |
The outside view (steps 5–6) comes **before** the story, not after; a story you already
believe will find its own evidence.

### 3b. Building the chain
| part | rule | typical failure |
|---|---|---|
| mechanism | names *who has to trade* and why (forced flow, crowd unrewarded, catalyst, rotation) — not "it looks strong" | a description of the chart |
| expected move | in own daily moves, with the horizon the mechanism needs (funding: 7 days; unlock: the month before; FOMC: the day) | a target with no horizon |
| falsifier | the observation that proves the mechanism wrong, on the correct side, smaller than the stop, with a day | a price level that is just a tighter stop |
| checkpoint | what should have happened by day D if the mechanism is working | none, so the trade is never judged until it ends |
| order | stop 1.5–3 own moves, target ≥ 2 moves and ≥ 1.5× stop, hold from the target (ch7) | stop inside the noise |
| confidence | your honest probability of finishing positive after costs; it will be shrunk toward your record and mapped through your calibration | 0.8 on everything |
| event note | if a macro event is inside 24 h: what it does to this trade | ignoring it |
Write the falsifier **before** the mechanism is finished; if you cannot say what would prove
it wrong, it is not a thesis.

### 3c. Leaving a trade — in this order
| exit | when | who decides |
|---|---|---|
| **falsifier** | the mechanism was proven wrong (price falsifier on its day; or the thesis falsifier: funding flipped, the event resolved the other way, the story was denied) | first — before the stop |
| **checkpoint missed** | day D arrived and the expected move did not | re-think: trim or leave; do not "give it more time" without a new reason |
| **target** | reached | leave, or trail after the checkpoint if the path suggests more |
| **time** | hold days over | leave; a thesis that needs more time was mis-specified |
| **stop** | price at the stop | last resort; if you reach it often without the falsifier firing first, the falsifiers are too loose |
| **batch cut** | the *theory* behind several trades died (e.g. "alts rotate on falling dominance" and dominance turned) | all trades on that theory, together — do not wait for each stop |
| **book brake** | drawdown / day-loss / CVaR brake | the desk; no new trades |

### 3d. Adding, scaling, holding
- **Never add to a loser** to lower the average; a loser is a thesis under doubt, and doubt
  is not a reason to increase size. Add only on the *checkpoint hitting* (the mechanism is
  working) and only inside the book rules.
- **Trim** when a checkpoint is late but the falsifier has not fired; **cut** when it fires.
- **Hold longer** only when the coin is trading on its own story (7-day R² down, own vol up,
  ch6 §3e) *and* the stop is set on the larger own move; hold shorter when the coin has
  become a BTC trade and your thesis is not about BTC.
- Repeating the same trade within 7 days of losing it needs p ≥ 0.65 **[our desk]** — the
  outside view says most repeats are the same mistake.

### 3e. The journal — what is written for every closed trade **[our desk, memory.db]**
| field | why |
|---|---|
| the chain as written at entry (mechanism, falsifier, checkpoint, order, confidence) | you judge the *decision*, not the outcome |
| exit reason, days held, net bps, **excess vs BTC** | was it skill or the market |
| MFE / MAE | was the stop right; was the target reachable |
| checkpoint HIT/MISSED, falsifier TRIGGERED/not | did the mechanism work |
| the counterfactual grid: 9 stop/target plans and the opposite side on the same path | would a different plan have paid; is the edge in the entry or the exit |
| price 5 days after exit (to build) | perfect exit / left money / got out in time |
| loss class (to build): thesis / timing / risk-plan / regime | which part to fix next time |
| what was visible and unused (to build) | the fact that should have changed the call |
Lessons feed the `similar`, `evidence`, `stops_report`, `calibration` tools. An insight is
only "active" when it has out-of-sample support (n ≥ 10 per setup); before that it is a
hypothesis, and the desk treats it as one.

### 3f. How accounts die (and the rule that prevents each)
| cause | rule |
|---|---|
| one oversized loss | size by vol and quarter-Kelly; stop always set; brakes |
| no invalidation ("it will come back") | falsifier written before the order; checkpoints |
| ten trades that are one trade | cluster cap, net/gross rule, stressed correlation (ch6) |
| over-trading small edges into costs | multi-day holds; a chain must name a horizon the mechanism needs |
| revenge / repeat | the 7-day repeat rule; the outside view first |
| ignoring carry | a Q5 long pays ~22 bps/week; a Q1 short pays ~48 **[measured]**; the thesis must beat it |
| trading the headline after the flow | novelty and positioning checks (ch8) |
| believing your own confidence | shrink toward the record; calibration buckets |

## 4. Worked example — one trade, start to finish

Morning sheet: BTC +2% over 30 days, breadth 55% green, correlation regime calm. Funding
extremes: C88 at Q1 (−0.04%/8h), OI +20% in 5 days, price flat 4 days, top traders net
short. Calendar: CPI in 2 days (vol event), no unlock. Own record: longs on funding
squeezes 7 of 11 positive, +38 bps mean excess. Similar situations: 3 of 4 worked over 5–8 days.
- Mechanism: crowded shorts paying, unrewarded for 4 days; forced buying if price ticks up.
- Expected move: +2 own moves (C88 own move 5%) over 7 days = +10%.
- Falsifier: day 2, −3% (0.6 × stop) — "shorts were right after all"; thesis falsifier:
  funding turns positive (crowd flipped) → leave regardless of price.
- Checkpoint: day 4, +4% (OI should be *falling* — shorts covering).
- Order: stop 0.075 (1.5 moves), target 0.12 (2.4 moves), hold 6 days (engine), confidence 0.60.
- Event note: "CPI in 2 days is a vol event, not a direction; the falsifier is judged on
  the close after the release, not the wick."
- Day 4: +5%, OI −8% → checkpoint HIT; hold. Day 6: +11% → target near; time exit at +11%.
- Journal: excess vs BTC +9%; MFE +12%, MAE −2%; checkpoint HIT, falsifier not triggered;
  counterfactual grid says the 3-move target would have paid +14% by day 9 → next time on
  this setup, 3 moves / 9 days. Loss class: n/a. Visible and unused: none.

## 5. Common misreads

1. **"The stop comes first, the falsifier can override it if I choose."** Backwards: the
   falsifier is the plan; the stop is the safety net for when the plan was not judged in time.
2. **Adding to a loser.** Only add when the checkpoint hits.
3. **Judging by outcome.** A losing trade with a correct process is a good decision; a
   winning trade with no falsifier is a bad one. The journal records the decision.
4. **Trusting the first 10 trades.** ~50 before an edge is believable; until then, small.
5. **A thesis with no horizon.** Funding is 7 days; unlocks are the month before; FOMC is
   the day. A chain must say which.
6. **Waiting for the stop when the theory died.** Batch-cut all trades on a dead theory.
7. **Reading MFE as "should have held".** Only when the exit was stop/time and MFE reached
   the target (ch7 §3e).

## 6. Sources
- R-multiples and expectancy — https://www.pnlledger.com/expectancy-r-multiples-the-plain-english-guide/ ; Van Tharp benchmarks and the 50-trade minimum — https://crosstrade.io/learn/performance-metrics/r-multiple
- Triple-barrier labelling and meta-labelling (López de Prado) — https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/
- Pre-trade checklist: define the invalidation before sizing — https://fortraders.com/blog/trade-entry-exit-checklist
- Our desk: `sim/investigator.py` (checklist gate, chain fields), `sim/risk.py` (rules), `sim/engine.py` (falsifier exit, MFE/MAE, counterfactual grid), `sim/memory.py` (experience rows), `docs/MEASURED_LINKS_2026-09-16.md` (the sizes of the edges).
