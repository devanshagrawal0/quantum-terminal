# Learnings & Rules — the hyperliquid-bot trading system

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

**L9 — The momentum-long "edge" is BETA, not alpha (2026-08-25, BACKTESTED, corrects L7).**
Re-validated on the full 365-day history (79 coins, no lookahead, net of ~0.1% fee),
across 16 parameter sets (signal 3-30d × hold 1-5d) and 3 regimes. Result: buy-the-top-
gainers returns **+0.1% to +0.7%/trade at a 49-54% win rate** — but it **underperforms
buying the market** (negative alpha −0.23%). It only "makes money" because the market
drifted up = pure BETA. Fading the overbought LOSES net of fees. **Win rates are coin-
flips (46-54%) in every config.** → The journal's "momentum-long 75% win, +$11.28" was a
4-trade small-sample fluke in a bull window, NOT an edge (corrects the read that grew out
of L7). We have NO proven mechanical edge; this re-confirms L4. Our only untested hope is
the DISCRETIONARY catalyst/news/reasoning approach (which a mechanical backtest can't
measure) — so stop treating momentum-continuation as a measured edge, and judge the
reasoning approach only on a large sample of clean, real closed trades.

**L10 — Funding-carry is our best edge candidate, but regime-dependent (2026-08-25, BACKTESTED).**
Backtested on `funding_daily_365.parquet` (74 coins, 377 days): market-neutral L-S — SHORT
top-K funding coins, LONG bottom-K, collect the funding. Weekly rebalance (daily loses to
fees): **+35% ann, Sharpe 1.95, net of fee; still +21%/Sharpe 1.14 at 3× fees.** Unlike
momentum (L9) this is market-NEUTRAL (not beta), fee-robust, and mechanistically carry-
driven with a small crowded-long reversion kicker. BUT it FAILS the both-halves test:
first-half Sharpe 0.39 (~nothing), second-half 4.51 (the melt-up, when funding got
extreme). → The edge scales with how extreme funding is; strong in high-conviction/melt-up
markets, weak in chop. Best candidate we have, but NOT proven consistent — needs
out-of-sample confirmation and beware survivorship (delisted high-funding coins excluded).
Must hold weekly+, never daily. Delta-neutral on a perp-only venue = the L-S structure.

## WHAT ACTUALLY HAS A PULSE (best current read)

- **Funding carry into a catalyst** — extreme funding + crowded longs into a known
  event = asymmetric short. The one measured effect, and the most HL-native.
- **Scheduled catalysts** — unlocks (~88% negative in 72h), Korean listings,
  delistings. Reward preparation over speed. (Unlock feed needs a source — 402'd.)
- **Fade the listing/news pop** after exhaustion, not the chase (listings dump 98%).
- **Momentum + volatility** — to TIME and SIZE, not to pick the trade.
- **Deep web research on the coin** (this new layer) — the human/sentiment/
  developer/sector story the internal feeds cannot see.

**L11 — My discretionary directional judgment has no edge either (2026-08-25, BLIND SIM).**
Backtested ME, not a rule: 9 blind hands (anonymized coins, past-only features, future
masked, I commit picks then reveal). Result: avg edge vs market **−6% , 4/9 positive =
a losing coin-flip.** I internalized L7 (after hand 1 I stopped shorting uptrends/longing
downtrends — the regime filter then caught nothing because I made no regime-fighting
picks) and STILL lost. The bleed is SHORTS getting run over by rallies the trailing
regime failed to predict. → Confirms L9 from the other side: no alpha in directional
stock-picking, mechanical OR discretionary; shorting is where the damage is (market drift
punishes it). The ONLY thing that backtested as a real edge is funding-carry (L10),
market-neutral, mechanical, weekly. Stop trying to pick directional winners.

**L12 — The score composite was DEAD; only funding+relative-strength at a 10-day hold
survived (2026-08-25, UNBIASED BACKTEST — `scripts/backtest_scores.py`).** Wired the
live signal engine's scores and tested them point-in-time (94 coins × 376d, every
feature shift()ed so day t sees only ≤t, forward return BTC-neutralized, net of
0.20%/side, long top-quintile / short bottom-quintile). The FAST blend of all factors
(1-7d) is dead: **IC t −1.3, loses net of fees, fails both-halves** — it blends factors
that work at OPPOSITE horizons (a 1-day reversal fighting a 7-day carry) so they cancel
to noise. Per-factor decomposition: momentum ≈0 at all H (re-confirms L9); 3-day reversal
weak only at H=1 (t+1.6); **funding (short crowded) IC t +2.4 @H=7** and **relative-
strength-vs-BTC (resid7) IC t +2.9 @H=7** are the only live ones. Their combined score
strengthens monotonically with horizon and at **H=10** gives **IC t +3.99, Sharpe +1.41
net, hit 65%, POSITIVE in BOTH halves (+0.76 / +2.21)** — the FIRST thing to clear the
both-halves + fee + significance bar. → The live COMPOSITE is now THAT score only
(funding + rel-strength, ~10-day hold), with the measured numbers shown on the UI so it
can't be oversold. Same family as L10 (carry), one notch slower — re-confirms "slower
beats faster." CAVEATS: H was searched (mild selection), needs true out-of-sample,
survivorship (delisted high-funding coins excluded), and resid7 at extremes (97%ile) may
revert. Intel REPORT scores (catalyst/smart-money/etc.) have NO history → can't be
backtested, only forward-tracked; do not treat them as proven.

**L13 — LONG-ONLY. The short leg has no edge and makes the book unstable (2026-08-25,
BACKTESTED, corrects L12's long-short claim).** Tested long-only vs long-short on the live
funding+relative-strength score at H=10 (`scripts/backtest_scores.py long_only_vs_ls`,
net 0.20%/leg, both-halves). **Long-SHORT quintile: Sharpe −0.09, fails both-halves — and
NOT robust: the same book read Sharpe +1.41 before a routine data refresh and −0.09 after
(≈2 days of new data flipped it).** The instability comes entirely from the short leg,
which rides noisy extreme-funding coins. **Long-only HEDGED (long top quintile, short BTC
as hedge): Sharpe +1.34 (decile +2.00), positive in BOTH halves (+1.20/+1.92), hit 55%,
and HALF the fee drag (1 leg).** Long-only UNhedged (eat the beta) is bad (−0.70, first
half −3.91) — you must hedge the market. This matches the forward tracker's backfill (long
+0.87% vs short +0.16% BTC-neutral). → **The live composite is now LONG-ONLY:** a negative
score is an "AVOID / don't own it", NOT a short (`traded=False`, dir "AVOID" in the UI).
The tracker still LOGS shorts to keep measuring that they stay dead, but we do not trade
them. NOTE: the L-S flip means even the long-only Sharpe (in-sample) is not to be trusted
on magnitude — the LIVE tracker is the only real judge; this is a directional call (long
good / short dead / hedge the beta), not a promise of Sharpe 1.3.
