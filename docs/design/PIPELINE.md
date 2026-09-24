# The Trade Pipeline v3 — catalyst-first, second-order, web-researched

Rewritten after `research/HOW_PROS_TRADE.md`. The old v1 was a quant-signal
scan with a news check bolted on. The research changed the frame:

**Crypto is a sentiment / positioning / narrative game, not a valuation game.**
But the naive version — "read news, trade it" — is a trap: public news is priced
in ~1 minute and retail is ~47 seconds late, so reading a headline makes you the
*exit liquidity*, not the edge. The reachable edge is the **second-order
reaction**: fade the pop, trade the positioning unwind, short into a scheduled
cliff. News is the **trigger to think**, not the entry. The small quant that
actually survives — **momentum, funding, volatility** — times and sizes it; it
does not pick the trade.

This is not "news instead of features" and not "features instead of news." It is:
**reasoning picks the catalyst and the side, quant times and sizes it.**

Rules above every step (unchanged):
- Only Hyperliquid perps. $100 uniform per trade, 2x default (4x max), stop/
  target/time on every one, logged and hashed before the outcome exists.
- No single number decides a trade. Most ideas die before the last step.
- Enter on a LIVE HL price (`live_hl_price`), never a stale snapshot; no band
  tighter than the coin's spread noise (both enforced in `hl/paper.py`).

---

## Step 1 — Regime gate

What is the whole market doing — risk-on/off, BTC trend, are correlations near 1
(one bet, not many). Source: dashboard. In a violent one-way tape, cut size and
do not fight it. This only *sizes and skews*; it does not pick trades.

## Step 2 — Catalyst scan (the TRIGGER)

The catalyst is what makes a coin worth thinking about. Scan, newest first:
- **Events** (`events.db`): new Upbit/Bithumb/Binance/Bybit notices, HL universe
  changes (new perp, delisting, leverage cut).
- **Scheduled calendar** [BEST risk/reward, per research]: token unlock cliffs,
  index/ETF dates, known events days ahead. *Gap: the free unlock feed 402'd —
  this needs a new source before it is real. Flagged, not pretended.*
- **Attention inflection**: a coin whose social/mention volume is turning UP from
  a low base (the attention factor that works) — NOT one already the loudest
  (that is where the −50%/−77% listings happened).

A coin with a fresh catalyst goes to the front of the queue. No catalyst is fine —
positioning setups (step 5) stand on their own — but a catalyst is what makes the
reasoning worth doing.

## Step 3 — Deep web research (what is it / is the catalyst real)

*New step. The internal feeds see the NUMBERS; they do not see the human/narrative
story crypto actually trades on. This step fills that gap, done by the reasoning
layer (Claude) with real WebSearch/WebFetch — a script cannot judge what a
development means. `hl/research.py` preps the internal packet first (so no wasted
searches) and stores the finding as a timestamped note (so it is remembered).*

For the candidate, actually research the open web:
- **What it is** — the project in one honest sentence; is it a real thing or a ghost.
- **Sector** — the sector it sits in, and is that sector HOT right now (money
  rotates by sector — ETH-staking, AI, RWA, memes — a good coin in a cold sector
  goes nowhere; a mediocre one in the hot sector runs).
- **Is the catalyst genuine** — verify the trigger from step 2 against real
  sources. A "partnership" that is a marketing tweet is not a catalyst.
- **What the crowd is saying** — the actual sentiment on the web/forums, not a
  keyword score. Turning up from a low base is the signal; already-euphoric is the
  fade.
- **Upcoming catalysts** not on an exchange notice (unlocks, mainnet, ETF dates).

Run it for the MAIN/big coins AND the small ones — a small coin with a real
catalyst in a hot sector is exactly the asymmetric setup. Log the note either way.
`python scripts/research.py COIN` prints the packet to research from.

## Step 4 — Is it already priced? (the reasoning gate)

Using step 3: read what actually happened and *when*. Did the move already
happen in the first minute/hour? Is the news public and old? If the edge was
speed, it is gone — I am late by construction. The only tradeable version is the
**second-order** question in the next step. If the catalyst is already fully
priced and there is no positioning angle, KILL it here.

## Step 5 — How is the crowd positioned? (the actual edge)

This is the HL-native edge the research named as strongest. For the coin:
- **Funding** — extreme positive funding = crowded longs paying to hold. Into a
  known catalyst, that is an asymmetric SHORT (belief already fully held). This
  is the one measured effect we have, and it is exactly this.
- **Open interest + top-vs-retail** — is the position crowded and one-sided.
- **The pop** — if it already popped on the catalyst, the trade is the FADE:
  short strength into exhaustion, stop above the wick. (Listings now dump 98% of
  the time post-pop — the fade is the trade, not the chase.)
- **On-chain flow** as a slow bias filter [when we have it]: sustained exchange
  outflows / smart-money accumulation over 1-4 weeks — which side to lean, not a
  trigger.

The trade is usually: **fade the crowded, priced move**, or **ride a catalyst the
crowd has NOT yet piled into** (rare, and the harder call).

## Step 6 — Character & history

How does THIS coin move (from its daily history)? Memecoin that round-trips vs
slow grinder, its normal vol, how it behaved in setups like this. A fade on a
mean-reverting memecoin is a different animal from a fade on an L1. Kill if the
coin's character says this setup usually fails on this type.

## Step 7 — Time it with momentum, size it with vol

- **Momentum / trend** is the most robust crypto predictor — do not enter against
  a strong trend just because positioning says fade; wait for the trend to crack.
- **Volatility** sets the size and the stop distance. A 400%-vol memecoin gets a
  smaller size and a wider stop than a 40%-vol coin — same $100 notional, but the
  stop/target scale to the coin's noise.

## Step 8 — Pre-mortem (kill most trades here)

Write the bull case AND argue the bear case against myself. Check it against the
regime (1), whether it is priced (4), positioning (5), and character (6). State
the clean invalidation = where the stop goes. Honest confidence near 0.5 unless
multiple *independent* things align (catalyst + crowded positioning + trend crack
+ vol-appropriate size). If the bear case is as strong, or the only support is one
weak signal, NO TRADE.

## Step 9 — Fit to the book  *(now ENFORCED at open, not just advised)*

Correlation-checked: am I stacking correlated bets (the alts are 0.6-0.9
correlated; XMR-type names are the rare diversifier)? Do I already hold it? Is the
book already skewed the way this adds to?

**`hl/preflight.py` now enforces this automatically at `open()`** — a proposed trade
is BLOCKED (unless `force=True`) if it would be the 4th position measurably correlated
(|r|≥0.7, from real returns) with the book (L8), if the book is already at the one-side
cap (L8), or if it is a SHORT into a bitcoin-season/melt-up regime (L7). The regime read
comes from `hl/regime.py` (Step 1). This is the enforced version of the two mistakes the
dossier priced: concentration and fighting the tape.

## Step 10 — Log with the full plan

Coin, side, leverage, live entry, **stop** (+why), **target** (+why, ideally a
mechanical/calendar level not a vibe), **hold time**, and the one-paragraph
thesis from 3-7. Auto-closes on stop/target/time at the live HL price, fees both
ways. Scores vs market and vs the random control on close.

---

## The loop, in one line

**Catalyst triggers the thought → reasoning asks "priced? crowd offside?" →
funding/OI/flow name the second-order trade (usually a fade) → momentum times it,
vol sizes it → exit mechanical, not vibes.**

## What's still missing to run this fully

1. A **live/fresh price** path for the catalyst *and* gap signals — the recorded
   5-min snapshots are up to 157 bps stale, enough to manufacture fake gaps.
2. A **token-unlock calendar** feed (the best scheduled edge; the free one 402'd).
3. **Attention-inflection** detection (mention volume turning up from a low base),
   which is the one sentiment signal the research says actually works — and it is
   NOT keyword sentiment scoring, which is null out-of-sample.
