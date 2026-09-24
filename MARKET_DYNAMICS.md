# Market Dynamics — how the crypto machine actually moves

*A study of the questions that decide our trades: where BTC breaks, whether everything
falls together, whether BTC rising lifts the small coins, and what really drives the
+60%-overnight movers. Combines external research with numbers MEASURED from our own
120-day price history (77 liquid coins). Where our data and the textbook disagree, that
disagreement is the most important thing on the page — so it's flagged, not smoothed over.*

---

## 1 · The breaking point — spotting BTC's top / pullback

BTC doesn't break on a schedule; it breaks when the *fuel* runs out. The tells, in order
of reliability:

- **Leverage, not price, tops first.** The cleanest warning is **open interest rising
  while the move slows** — that's new leverage piling in without new spot buying
  ("deleveraging into strength"). Price-up + OI-up is healthy; price-up + OI-*down* is a
  rally running on fumes. A liquidation cascade needs crowded leverage to feed it.
- **Funding extremes.** Mildly positive funding (our majors sit ~+11% APR) = healthy.
  When funding spikes to +50-100%+ APR, longs are paying dearly to hold — the crowd is
  all-in one way, and that's the setup for a violent unwind (the flush clears it).
- **RSI exhaustion.** Daily RSI **82-86** = "powerful momentum but high odds of a
  sideways stall or pullback." Not a short signal by itself (we proved that — L7), but a
  *lower-high* on RSI while price makes a higher high is a real divergence warning.
- **The structural level.** BTC just cleared its **200-day EMA** (~$71.5k), which had
  capped every rally since February. As long as it holds *above* that, dips are
  buy-the-dip; a decisive close back *below* it is the regime flipping.

**How WE watch it:** the dashboard already logs funding + OI per coin and returns for RSI.
The armed **BTC ≥ $82k alert** marks the resistance test. The breaking point is not a
single number — it's *OI climbing into a stalling price with funding rich and RSI making
lower highs*. When three of those line up near resistance, cut size.

---

## 2 · Does everything fall together? — the contagion question

**This is regime-dependent, and our own data proves the nuance.**

Measured over our last 120 days (77 coins):

| | avg correlation to BTC | avg beta |
|---|---|---|
| **BTC-UP days** | 0.44 | **+1.16** |
| **BTC-DOWN days** | 0.30 | **+0.76** |
| whole period | 0.52 | — |

Read literally, our data says: **on down days alts were LESS correlated and fell LESS
than they rose.** That looks like it contradicts the famous "in a crash, correlations go
to 1, everything dies together." **It doesn't — it exposes a trap:** our 120-day window
has been a *bull/melt-up*. Its "down days" were orderly dip-buys inside an uptrend, not a
real liquidation crash. So our sample measures the *rally* regime, where alts amplify the
ups and dips get bought.

**What actually happens in a REAL crash** (research + crypto history, which our sample
simply doesn't contain): correlations **spike toward 1** — capital flees to the largest,
most-liquid asset (BTC) to de-risk, stablecoin liquidity dries up, and **the smaller/
higher-beta a coin is, the harder it falls.** "When liquidity shrinks, altcoins feel the
pressure *before* BTC does." So:

- **Mild pullback in an uptrend** (what we've seen): rotation & dispersion — some coins
  hold, money rotates, not everything falls. *This is why our alts didn't all collapse.*
- **Real crash / liquidation cascade** (not in our sample yet): everything falls
  together, high-beta alts fall **hardest**, BTC falls **least**. Correlation → 1.

**The rule this gives us:** in a genuine BTC breakdown, do **not** expect our alts to be a
haven or to "rotate" — they are high-beta and will fall more than BTC. The place to hide
in a crash is BTC itself or stables, not alts. (This is the flip side of L8: an all-alt
book is a *leveraged* bet on BTC not crashing.)

---

## 3 · BTC up → do the small coins go up too? — the rotation ladder

Yes, but **with a lag and a strict order**, and only in "risk-on." Capital ladders *down
the risk curve*:

**BTC → ETH → large-cap L1s (SOL/AVAX/LINK) → mid-caps → small-caps → memes.**

- **BTC first.** It's the gateway — most liquid, most institutional, the "safe" crypto.
  Money enters here. **Rising BTC dominance (now 58.1%) = still at this stage.**
- **ETH/BTC ratio is the starting gun.** When ETH starts *outperforming* BTC (ETH/BTC
  rising), capital is stepping out the risk curve — that's the first sign the rotation is
  moving past BTC. **Watch this ratio.**
- **Then large alts,** then — only in late-stage — small/mid caps. **TOTAL3** (total
  market cap excluding BTC & ETH) breaking to new highs is the clearest "small-caps are
  running now" signal.
- **Beta does the amplifying.** Our data: on up days alts run at **+1.16 beta** to BTC —
  they move *more* than BTC, not less. Small caps have the highest beta (see §4), so when
  the flow finally reaches them they move violently.

**Where we are now (Aug 2026):** BTC dominance **58.1%**, Altcoin-Season Index **33-37**
= firmly *Bitcoin season*. The flow is still at the **BTC/ETH** rung. Our majors (BTC,
ETH, SOL) are on the right rung; our alts (TRUMP/PENGU/LINK/UNI) are one-to-two rungs
*ahead* of where the money is — which is exactly why they've lagged. **Trigger to rotate
into alts: dominance breaking below ~55% + ETH/BTC turning up + TOTAL3 breaking out.**
Until then, majors lead.

---

## 4 · The +60% overnight movers — what drives them, how to spot them early

These are **not** BTC-beta moves — they're **idiosyncratic, catalyst-driven** moves.
Our data proves it: the coins that move most on their *own* news have **low BTC
correlation + high daily vol** (they march to their own drum):

| coin | daily vol | BTC corr |
|---|---|---|
| ACE | 15% | +0.06 |
| TST | 11% | +0.04 |
| JTO | 8% | +0.15 |
| WLD | 8% | +0.20 |
| LIT | 7% | +0.31 |

**The catalysts that cause them (ranked by how tradeable):**

1. **CEX listing** (Binance/Coinbase/Upbit). The single most consistent pump. Tokens
   build on DEXs, then rip on the *rumor/confirmation* of a major listing. → *We record
   exchange notices in `events.db`.* But the pop is priced in ~1 min; the edge is the
   **fade of the exhaustion**, not the chase (L6: listings dump 98% post-pop).
2. **ETF / institutional news** (ZEC +79% on the Grayscale ETF; ENA +102% on the FalconX
   facility + Hayes). Real, dated, big. The tradeable version is *before* full pricing or
   the **sell-the-news fade** (our armed ZEC watcher).
3. **Buyback / revenue** (PUMP +180% on 50%-of-revenue buy-and-burn; UNI fee-switch).
   A *sustained* mechanical bid — the healthiest kind, can trend for weeks.
4. **Short squeeze.** When BTC breaks up, crowded shorts get force-closed → the rally
   becomes a liquidation-driven vertical. **Spot it via funding:** funding spiking one way
   = crowded positioning = squeeze fuel. High beta names squeeze hardest.
5. **Narrative rotation** (AI, RWA, DePIN, memes taking turns) — money rotates by *sector*,
   so a mediocre coin in the hot sector outruns a good coin in a cold one.

**How to PREDICT (before, not after):**
- **Attention inflection** — social/mention volume turning UP *from a low base* (not
  already the loudest). This is the one sentiment signal that actually leads. *We compute
  this from our social scrape.*
- **Funding + OI extremes** — crowded one-sided positioning = squeeze setup.
- **Scheduled catalysts** — unlock cliffs, ETF dates, listing calendars, known events days
  out. Reward preparation over speed. *(Gap: our unlock-calendar feed still 402s.)*
- **Exchange-notice latency** — a fresh Upbit/Binance notice before the crowd fully reacts.

**The honest caveat:** many low-cap pumps are pure hype/manipulation — up in minutes, down
just as fast. The +60% move you can *catch* is the one with a **real, verifiable catalyst
in a hot sector on a coin with rising-but-not-yet-euphoric attention**. Everything else is
gambling, and the low-cap ones are where manipulation lives.

---

## 5 · Putting it together — our operating map

1. **Regime gate** (dominance, breadth, ETH/BTC, funding) decides the whole game. We're in
   *Bitcoin season* → own majors, not lagging alts.
2. **BTC breaking point** = OI climbing into a stalling price + rich funding + RSI lower-
   highs at resistance. Three lining up → cut size. (Watch the 200-day EMA as the line.)
3. **Contagion** is asymmetric: dips rotate, **crashes correlate to 1** and hit high-beta
   alts hardest — alts are never a crash haven.
4. **Rotation ladders** BTC→ETH→large→small; ride the rung the money is on, not the one
   ahead. ETH/BTC + TOTAL3 tell you when to step out the curve.
5. **Overnight movers** are catalyst-driven (low BTC corr, high vol); predict via attention
   inflection + funding + scheduled catalysts, trade the second-order reaction, and never
   confuse a manipulated low-cap for a real catalyst.

*Measured from 120 days of our own recorded prices + external research, Aug 2026. The
numbers are regime-specific — re-measure after the next real crash; that sample will show
the correlation-to-1 our current bull sample cannot.*
