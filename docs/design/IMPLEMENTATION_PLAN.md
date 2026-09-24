# Implementation Plan — turn the market-dynamics study into the system's brain

*Goal: take every insight in `MARKET_DYNAMICS.md` and the lessons in
`LEARNINGS_AND_RULES.md` and make them LIVE — computed signals the decisions actually
gate on, rules the system enforces, gaps closed. Not a document that sits there; wiring
that changes what we trade. Built in small phases, each verified on the real dashboard
before the next.*

Principle: **every insight becomes one of three things — a live SIGNAL (computed each
cycle), a MONITOR (an alert that fires), or a RULE (a check the pipeline enforces).**
If it stays prose, it doesn't count.

---

## Phase 1 · Regime Engine  *(the foundation — everything gates on it)*
The #1 finding: **regime decides the whole game.** Right now I eyeball it. Make it a
computed, live read.
- **Build** `hl/regime.py` → computes, each cycle: BTC dominance, ETH/BTC ratio + its
  trend, TOTAL3 proxy (alt market cap ex BTC/ETH), breadth (already have), aggregate
  funding, an Altseason-index proxy. Emits a **regime label**: `risk-off / bitcoin-season
  / early-rotation / altseason` + a confidence.
- **Surface** it: a Regime strip on the dashboard (top of Overview) + a `/api/regime`.
- **Wire into decisions**: pipeline Step 1 reads this label, not my gut. Each new trade is
  stamped with the regime at open (so the journal grades calls *by regime*).
- **Gap closed**: "I decide regime by feel" → measured, logged, gradable.
- *Verify: regime panel renders with the current read (should say bitcoin-season).*

## Phase 2 · Breaking-Point + Crash monitors  *(risk — the thing that saves the book)*
- **Breaking-point score** (`hl/regime.py` or a monitor): OI-rising-into-stalling-price +
  funding richness + RSI lower-highs at resistance. Alert when ≥ threshold near a level.
- **Crash / contagion detector**: breadth collapsing + cross-coin correlation spiking +
  our alts' beta jumping → a `RISK-OFF` alert. When it fires, the enforced rule is
  **"alts are not a haven — de-risk to BTC/stables, cut high-beta"** (from §2 of the study).
- **Wire in**: these run in the trigger loop (alert-only), shown in Watchers.
- **Gap closed**: we have no early warning for a top or a cascade today.

## Phase 3 · Rotation signals  *(when to move BTC→ETH→alts and back)*
- **ETH/BTC ratio turning up** + **TOTAL3 breaking out** + **dominance < ~55%** →
  `rotation-to-alts` signal (the counterpart to today's rotate-to-majors).
- **Wire in**: when it flips, the system flags "rotate the book down the risk curve" — the
  reverse of what we did today. Surfaced as a signal + logged.
- **Gap closed**: today's rotation was a manual read; make the *return* signal automatic.

## Phase 4 · Overnight-mover radar  *(catch the +60% movers early)*
- **Attention-inflection** computed live: mentions turning UP from a low base (the one
  leading sentiment signal), from our social scrape → ranked.
- **Funding/OI extremes** + **fresh exchange notices** (events.db) + **coins with low
  BTC-corr/high-vol** (from the study) → a **Catalyst Radar** ranked list on the dashboard.
- **Fix the unlock-calendar gap**: the free feed 402s — research a replacement source
  (research first) so scheduled unlock cliffs are back in play.
- **Gap closed**: unlock calendar dead; attention-inflection not yet computed live.

## Phase 5 · Bake into sizing, memory & the pipeline  *(make it enforced, not optional)*
- **Beta-aware correlation cap** (L8 with real numbers): use measured beta + sector to
  block over-concentration *before* the trade, not after the loss. Position sizing scales
  the stop/target to the coin's measured vol/beta.
- **Update the canon**: `PIPELINE.md` Step 1 + Step 4/8 reference the live regime + beta;
  `LEARNINGS_AND_RULES.md` links the dynamics; the dossier's Decision Framework becomes
  executable checks.
- **Memory**: save the durable dynamics (regime ladder, contagion asymmetry, beta table,
  mover catalysts) to persistent memory so they survive sessions.
- **Gap closed**: rules are prose; make the key ones machine-enforced at open().

## Phase 6 · Close the learning loop  *(grade decisions, not just trades)*
- Every trade auto-annotated at open with **regime + beta + correlation-to-current-book**.
- The journal/dossier then grades **by regime** ("momentum-longs: 75% in bitcoin-season")
  so we learn what works *in which regime* — the next level of the training record.
- **Gap closed**: we grade trades; start grading *decisions in context*.

---

## Order & gating
Phase 1 is the foundation and unblocks 2/3/5/6 — **start there.** Each phase ships one
verified piece, shown on the real dashboard, then Dev gates the next. Research-first on
the one true unknown: the **unlock-calendar replacement source** (Phase 4).

**Starting now: Phase 1 — the Regime Engine.**
