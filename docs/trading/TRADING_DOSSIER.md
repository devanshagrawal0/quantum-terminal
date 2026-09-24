# TRADING DOSSIER — HYPERDESK Paper Book

*The training record: every bet, every win, every mistake, every rule. Auto-generated from the live databases so it never goes stale.*  
*Regenerate: `python scripts/report.py`*

---
## 1 · Scoreboard

**Live book:** 7 open · exposure $700 · unrealized -$0.92 · realized -$5.84 · **total -$6.00**
**Closed record:** 16 trades · win 31% · net -$5.47 · avg hold 5.7h

**By setup — what actually works:**

| Setup | Trades | Win % | Net P&L |
|---|---|---|---|
| `melt-up-momentum-long` | 4 | 75% | +$11.28 |
| `enforcement-test` | 1 | 0% | -$0.10 |
| `regime-cut` | 1 | 0% | -$0.41 |
| `stale-price-artifact` | 2 | 50% | -$0.62 |
| `over-concentration-cut` | 2 | 0% | -$4.39 |
| `short-into-meltup` | 4 | 0% | -$11.86 |

**By side:**

| Side | Trades | Win % | Net P&L |
|---|---|---|---|
| long | 8 | 50% | +$7.53 |
| short | 8 | 12% | -$13.00 |

**Currently open:**

| Coin | Side | Entry | Mark | P&L $ | P&L % |
|---|---|---|---|---|---|
| PENGU | long | 0.0100935 | 0.009927 | -$1.77 | -3.5% |
| SOL | long | 101.095 | 100.585 | -$0.60 | -1.2% |
| BTC | long | 80203.5 | 79870.5 | -$0.51 | -1.0% |
| LINK | long | 11.7335 | 11.7025 | -$0.37 | -0.7% |
| TRUMP | long | 2.45355 | 2.45025 | -$0.26 | -0.5% |
| ETH | long | 2469.95 | 2488.35 | +$0.65 | +1.3% |
| UNI | long | 4.32555 | 4.41475 | +$1.94 | +3.9% |

---
## 2 · Rulebook & Lessons

Living file. Every hard lesson and every rule we trade by. Updated as we learn.
The point of paper-trading first is exactly this: each mistake caught here is one
that did NOT cost real money.

---

## RULES (how we trade)

1. **Only Hyperliquid perps.** If it is not in the tradable set, it does not exist.
2. **Every trade is one uniform size ($100 notional), 2x default (4x max).** Same
   size each so the track record is comparable — one trade cannot matter more
   than another just because it was bigger.
3. **Write the full plan BEFORE the outcome exists** — entry, stop, take-profit,
   hold time, thesis — and hash it so it cannot be edited after. That is what
   makes the record honest.
4. **Take-profit is a realistic % ON THE MONEY, not a greedy price level.** Bank
   a quick +10-15% on the money; do not hold for +16%+ and watch it round-trip.
   (Lesson L1.)
5. **No single number decides a trade.** The edge is combining catalyst +
   positioning + reasoning; every factor alone is too weak. Most ideas should be
   KILLED before they are logged.
6. **News is the trigger to THINK, not the entry.** Public news is priced in ~1
   minute; reading a headline and buying makes us the exit liquidity. Trade the
   SECOND-ORDER reaction (fade the pop, positioning unwind, scheduled cliff).
7. **Regime gates everything.** In a melt-up, fades get run over — favour
   momentum-continuation longs on liquid names; in a downtrend, favour the fades.
   Never fight a violent one-way tape with size.
8. **Enter on a LIVE price, never a stale snapshot.** (Lesson L2.)
9. **Correlation-check the book.** The alts are 0.6-0.9 correlated — five alt
   trades can be one bet. XMR-type low-correlation names are the rare diversifier.
10. **No hardcoded keyword classification of news** ("if title contains X →
    bearish"). Linking news to a coin is reasoning, not a substring match.

---

## LESSONS (mistakes, dated, so we do not repeat them)

**L1 — Greedy targets (2026-08-24).** STX ran to +11.5% on the money and reversed
because the take-profit was parked at +8% price = +16% on money. The gain
evaporated. → Set take-profits as a realistic % on the money. Also: the dashboard
P&L% is leverage-inflated (on margin), NOT the price move — never confuse them.

**L2 — Stale prices (2026-08-24).** The recorded price snapshots are 5 minutes
apart and were measured up to 157 bps off the live price. This (a) closed tight
gap-trades in 1 minute on staleness not convergence, (b) made the dashboard flash
a fake +$10, (c) contaminated the gap-convergence backtest. → Entries now fetch a
live HL price; the gap SIGNAL and its backtest still need fresh prices before
trusted. The whole cross-venue feature layer inherits this staleness.

**L3 — Ghost fees (2026-08-24).** Wiping test trades left their fees in the
account's running total (off by ~$0.25). → Account totals recomputed from the
actual trades table, which is the source of truth.

**L4 — Every quant factor tested has been too weak or unreachable.** Momentum
(dies under overlap correction), 1-day reversal (spread artifact, lives in
illiquid coins), positioning (below cost bar), funding carry (real but mostly
mechanical carry + fails the both-halves test in liquid names). → Crypto has no
fundamental anchor, so smooth factors have nothing to revert toward. The edge is
reasoning over catalysts + positioning, not a factor book. [see HOW_PROS_TRADE.md]

**L5 — Bottom-up-only scanning misses the news.** First trades came from quant
extremes (STX/XMR/GRAM) which are socially SILENT. The loud coins (ZEC, TRUMP)
were never scanned top-down. → Scan BOTH directions: quant extremes AND what is
loud/catalysed; the edge is where they overlap.

**L6 — Suspect / stale venue data.** Delisted markets show frozen prices (fake
arbitrage), ticker collisions (Bybit PURR ≠ HL PURR), dated futures mistaken for
perps, base-vs-quote volume units, KRW/INR not converted. All caught and guarded,
but the lesson stands: NEVER trust a cross-venue number without the consistency
and staleness checks.

**L7 — Shorts die in a melt-up; momentum-longs win (2026-08-25, MEASURED on real closed trades).**
First full batch resolved. By setup: **momentum-continuation LONG = 4 trades, 75% win, +$11.28.
SHORT-into-melt-up = 3 trades, 0% win, −$10.78** (XMR −6.10, BTC −2.09, XRP −2.60 all stopped).
By side: long +$11.28 / short −$11.82. Every short — even the highest-conviction RSI>90 XRP fade,
even XMR with +66% funding carry paid to us — got run over by the up-tape. The one long that lost
(ETHFI) was an *extended* entry, not a fresh breakout. → In a confirmed melt-up: ride momentum longs
on fresh breakouts, bank ~+10% (HYPE did, cashed clean), and do NOT short on "overbought" or carry.
Regime dominates every micro-signal.

**L8 — Correlation is the hidden risk; "9 longs" was really 3 bets (2026-08-25, MEASURED).**
Chasing L7 (momentum-longs win), I loaded the book to 9 all-long positions and felt
diversified. Then the melt-up PAUSED for one hour and every position dropped together
(−$10.73 unrealized) because they were 3 correlated clusters, not 9 bets: DeFi ×4
(AAVE/MORPHO/PENDLE/UNI), memes ×3 (TRUMP/PENGU/DOGE), + ETH/LINK. One market wobble
hit all three piles at once. Forced to realize ~−$4.4 cutting AAVE+DOGE to de-risk.
→ **HARD PORTFOLIO RULES (new):** max 3 positions per correlated sector; max ~6-7 open
in one direction; count *clusters*, not tickers, when judging diversification; an
all-one-side book is a single leveraged beta bet no matter how many names. Being right
on the setup does not save you from concentration.

---

## WHAT ACTUALLY HAS A PULSE (best current read)

- **Funding carry into a catalyst** — extreme funding + crowded longs into a known
  event = asymmetric short. The one measured effect, and the most HL-native.
- **Scheduled catalysts** — unlocks (~88% negative in 72h), Korean listings,
  delistings. Reward preparation over speed. (Unlock feed needs a source — 402'd.)
- **Fade the listing/news pop** after exhaustion, not the chase (listings dump 98%).
- **Momentum + volatility** — to TIME and SIZE, not to pick the trade.
- **Deep web research on the coin** (this new layer) — the human/sentiment/
  developer/sector story the internal feeds cannot see.

---
## 3 · Per-Bet Reports — every closed trade

### AIXBT · SHORT · LOSS -$0.85  `[stale-price-artifact]`

- **Result:** -$0.85 · exit *stop* · held 0.01h · moved -0.6% our way
- **Trade:** entry 0.020971 → exit 0.0210968
- **Lesson:** Closed in 36 SECONDS on the stale-price bug, not on thesis. Opened on a 5-min-old snapshot, then the first fresh mark gapped through the stop. NOT a real test of the idea - it is an artifact of L2 (stale entry). Since fixed with live_hl_price at entry + min-band guard. Discard as signal.

### ZORA · SHORT · WIN +$0.22  `[stale-price-artifact]`

- **Result:** +$0.22 · exit *target* · held 0.01h · moved 0.4% our way
- **Trade:** entry 0.00693 → exit 0.00690228
- **Lesson:** Also closed in 36 SECONDS - hit target on the same stale-price gap. A LUCKY artifact, not a real win: the 'move' was the snapshot-vs-live gap, not convergence. Same L2 bug. Do not count this +0.22 as edge. Fixed since.

### GRAM · SHORT · LOSS -$0.41  `[regime-cut]`

- **Result:** -$0.41 · exit *manual* · held 1.02h · moved -0.3% our way
- **Trade:** entry 1.47005 → exit 1.47375
- **Lesson:** I manually cut this short after the Step-1 regime gate showed an 89%-breadth MELT-UP - a thesis-less short fighting momentum. The -0.41 was the cost of OPENING a short with no catalyst in a melt-up, not of cutting it. Lesson: in a confirmed melt-up, do not open fades without a specific catalyst; the cut itself was correct and fast.

### SOL · LONG · WIN +$3.40  `[melt-up-momentum-long]`

- **Result:** +$3.40 · exit *target* · held 4.32h · moved 3.5% our way
- **Trade:** entry 96.4325 → exit 99.8076
- **Signals at entry:** 1d +1% · 7d +28% · 30d +29% · funding +11%APR · BTC7d +23% · ETH7d +30%
- **Lesson:** WIN +$3.40 (target). Momentum long on real catalysts (speed upgrade + ETF inflows) in the melt-up. Clean: rode the trend, hit target. Confirms momentum-continuation longs are the edge in this regime.

### XRP · SHORT · LOSS -$2.60  `[short-into-meltup]`

- **Result:** -$2.60 · exit *stop* · held 6.48h · moved -2.5% our way
- **Trade:** entry 1.47805 → exit 1.515
- **Signals at entry:** 1d +3% · 7d +52% · 30d +38% · funding +11%APR · BTC7d +23% · ETH7d +30%
- **Lesson:** LOSS -$2.60 (stop). SHORT fade of RSI>90 blow-off. Highest-conviction short of the batch and STILL stopped out. Even a genuinely extreme/crowded reading is not enough to fade a melt-up - the tape overrode it.

### BTC · SHORT · LOSS -$2.09  `[short-into-meltup]`

- **Result:** -$2.09 · exit *stop* · held 6.49h · moved -2.0% our way
- **Trade:** entry 78799.5 → exit 80375.5
- **Signals at entry:** 1d +0% · 7d +23% · 30d +21% · funding +11%APR · BTC7d +23% · ETH7d +30%
- **Lesson:** LOSS -$2.09 (stop). SHORT fade of BTC RSI-82 into resistance. The 'overbought' read was correct on paper but fading a major in a melt-up squeezed through the stop. Overbought is not a short signal in a strong trend.

### ETHFI · LONG · LOSS -$5.15  `[melt-up-momentum-long]`

- **Result:** -$5.15 · exit *stop* · held 9.67h · moved -5.0% our way
- **Trade:** entry 0.619795 → exit 0.588805
- **Signals at entry:** 1d +6% · 7d +23% · 30d +47% · funding +11%APR · BTC7d +23% · ETH7d +30%
- **Lesson:** LOSS -$5.15 (stop). The ONE long that lost. Research-driven ETH-staking long - right sector, right regime, but entry was extended and it round-tripped to the stop. Being a long in the melt-up wasn't enough; entry timing on an already-run name still matters. A momentum long works best on a fresh breakout, not after a big run.

### STX · LONG · WIN +$7.87  `[melt-up-momentum-long]`

- **Result:** +$7.87 · exit *target* · held 10.53h · moved 8.0% our way
- **Trade:** entry 0.22598 → exit 0.244058
- **Signals at entry:** 1d +7% · 7d +92% · 30d +62% · funding -43%APR · BTC7d +23% · ETH7d +30%
- **Lesson:** WIN +$7.87 (target, +16% on money). Momentum long into the melt-up; hit its profit target. Note the target was on the greedy side (+16% on money) yet it worked because the melt-up was strong enough - got lucky the tape didn't reverse first. Keep targets realistic even when they hit.

### XMR · SHORT · LOSS -$6.10  `[short-into-meltup]`

- **Result:** -$6.10 · exit *stop* · held 12.64h · moved -6.0% our way
- **Trade:** entry 429.22 → exit 454.973
- **Signals at entry:** 1d -1% · 7d +4% · 30d +18% · funding +76%APR · BTC7d +23% · ETH7d +30%
- **Lesson:** LOSS -$6.10 (stop, biggest single loss). SHORT into an 89%-breadth MELT-UP. Defended it TWICE on a funding-carry thesis (+66% APR paid to us). The carry was real but irrelevant - a short in a violent up-tape gets run over, and it did. The funding edge is a rounding error vs the directional move. LESSON: in a confirmed melt-up, do NOT hold shorts on a carry rationale.

### HYPE · LONG · WIN +$5.17  `[melt-up-momentum-long]`

- **Result:** +$5.17 · exit *manual* · held 12.8h · moved 5.3% our way
- **Trade:** entry 77.4905 → exit 81.5755
- **Signals at entry:** 1d +2% · 7d +42% · 30d +41% · funding +11%APR · BTC7d +23% · ETH7d +30%
- **Lesson:** WIN +$5.17 (+10%). Momentum-continuation long on Hyperliquid's own token, new ATH on REAL fundamentals (SEC pre-IPO perp filing, $6.5M/day fees, $13B OI). Rode the melt-up WITH the trend, banked at +10% on the money per the take-profit discipline instead of getting greedy. Textbook of what works in this regime.

### BNB · SHORT · LOSS -$1.08  `[short-into-meltup]`

- **Result:** -$1.08 · exit *manual* · held 11.97h · moved -1.0% our way
- **Trade:** entry 702.885 → exit 709.805
- **Signals at entry:** 1d +1% · 7d +16% · 30d +24% · funding +11%APR · BTC7d +23% · ETH7d +30%
- **Lesson:** LOSS -$1.08. The last short fighting the melt-up (laggard-short thesis). Cut it deliberately when the data proved shorts-into-meltup = 0/3. Confirms L7: no shorts in a melt-up, even the 'weak laggard' one.

### AAVE · LONG · LOSS -$2.90  `[over-concentration-cut]`

- **Result:** -$2.90 · exit *manual* · held 13.8h · moved -2.8% our way
- **Trade:** entry 133.875 → exit 130.13
- **Signals at entry:** 1d +10% · 7d +63% · 30d +50% · funding +11%APR · BTC7d +23% · ETH7d +30%
- **Lesson:** LOSS -$2.90 (cut, not stopped). Not a bad SETUP - a good DeFi momentum long - but a CONCENTRATION mistake: I already held MORPHO (same DeFi-lending bet). When the melt-up paused, the whole DeFi cluster dropped together and AAVE was the most underwater + nearest its stop, so I cut the redundant one to de-correlate. The loss is the cost of over-stacking one sector (L8).

### DOGE · LONG · LOSS -$1.49  `[over-concentration-cut]`

- **Result:** -$1.49 · exit *manual* · held 0.33h · moved -1.4% our way
- **Trade:** entry 0.0920975 → exit 0.0908205
- **Signals at entry:** 1d +1% · 7d +34% · 30d +34% · funding +11%APR · BTC7d +23% · ETH7d +30%
- **Lesson:** LOSS -$1.49 (cut). Weakest of 3 correlated meme longs (TRUMP/PENGU/DOGE); only +1% on the day, momentum fading, CLARITY catalyst already dead on XRP. Cut to shrink the meme cluster and de-risk an all-long book. Again the cost of L8 concentration, not a bad read on the coin itself.

### MORPHO · LONG · LOSS -$0.05  `[untagged]`

- **Result:** -$0.05 · exit *manual* · held 0.7h · moved 0.1% our way
- **Trade:** entry 2.6688 → exit 2.6717
- **Signals at entry:** 1d +16% · 7d +34% · 30d +38% · funding +11%APR · BTC7d +23% · ETH7d +30%

### PENDLE · LONG · WIN +$0.68  `[untagged]`

- **Result:** +$0.68 · exit *manual* · held 0.7h · moved 0.8% our way
- **Trade:** entry 1.7855 → exit 1.8002
- **Signals at entry:** 1d +14% · 7d +53% · 30d +30% · funding +19%APR · BTC7d +23% · ETH7d +30%

### XMR · SHORT · LOSS -$0.10  `[enforcement-test]`

- **Result:** -$0.10 · exit *manual* · held 0.0h · moved -0.0% our way
- **Trade:** entry 447.215 → exit 447.215
- **Signals at entry:** 1d -1% · 7d +4% · 30d +18% · funding +11%APR · BTC7d +23% · ETH7d +30%
- **Lesson:** NOT A REAL TRADE — force=True end-to-end test of the Phase-5 enforcement override. Opened and closed immediately to prove force bypasses preflight. Discard from edge stats.

---
## 4 · Mistake Catalogue — losing patterns, named

- **`short-into-meltup`** — 4 trades, 0% win, cost **-$11.86**. See per-bet lessons for the fix.
- **`over-concentration-cut`** — 2 trades, 0% win, cost **-$4.39**. See per-bet lessons for the fix.
- **`stale-price-artifact`** — 2 trades, 50% win, cost **-$0.62**. See per-bet lessons for the fix.
- **`regime-cut`** — 1 trades, 0% win, cost **-$0.41**. See per-bet lessons for the fix.
- **`enforcement-test`** — 1 trades, 0% win, cost **-$0.10**. See per-bet lessons for the fix.

---
## 5 · Open Contradictions (Watchlist)

- **TAO** — bull: MOMENTUM: +7.6% today, +22%/7d, AI-narrative leader, on altseason watchlists.  
  bear: NEWS: Fidelity report (Aug 20) casting DOUBT that AI agents drive value to chains like Bittensor. Stuck at $214 resistance. Sentiment split.  
  since flagged: +0.6% (momentum ▲ winning) · lean: *unsure*
- **EIGEN** — bull: MOMENTUM: +11% today, +37%/7d, only +12%/30d (fresh breakout), in a melt-up.  
  bear: NEWS/FUNDAMENTAL: ether.fi (its biggest restaker, $3.3B) EXITED restaking, cutting to <1% headed to zero by Q3. Restaking narrative deteriorating. Aug-1 unlock. EigenCloud launch dumped -5.6%.  
  since flagged: -0.1% (news ▼ winning) · lean: *bear (news should win once momentum fades)*

---
## 6 · Decision Framework (the distilled playbook)

1. **Regime first.** Melt-up (breadth >80% green, majors trending) → momentum-continuation LONGS on fresh breakouts. Do NOT short on 'overbought' or carry — proven 0/3, −$10.78 (L7).
2. **News is the trigger to think, not the entry.** Verify the catalyst is real (deep web research). A momentum-up / news-down coin is a TRAP → Watchlist, don't trade (EIGEN).
3. **Fresh breakout, not extended.** A long after +100%/30d round-trips (ETHFI −$5.15). Enter on the push, not the exhaustion.
4. **Correlation cap (L8).** Max 3 per sector; count clusters not tickers; an all-one-side book is one leveraged bet. 9 correlated longs cost us the session.
5. **Realistic take-profit.** Bank ~+10-12% on the money (HYPE +10% cashed clean); don't hold for greedy targets and watch them reverse (L1).
6. **Every trade: stop + target + time, hashed at open.** First to hit closes it. Enter on a LIVE price, band wider than spread noise (L2).

*Generated 2026-08-25 15:12 · 16 closed trades on record.*
