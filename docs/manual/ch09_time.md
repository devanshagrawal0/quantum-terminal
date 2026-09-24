# Chapter 9 — Time: sessions, funding clocks, weekends, expiries and the macro calendar

Crypto never closes, but it is not the same market at every hour. Flows have clocks:
funding settles on a schedule, US data lands at fixed minutes, options expire at a fixed
hour, and the people trading at 03:00 UTC are not the people trading at 14:30 UTC. The
engine stamps every fact with UTC time and computes "hours to the next event"; this chapter
is what those clocks mean. **[measured in our store]** marks our data
(`docs/CALENDAR_SEASONALITY.md`: BTC + ETH 2017→2026, 3,295 days; FOMC/CPI on 12 coins
2020→2026); **[our calendar]** marks `sim/events.py`.

## 1. The clocks

| clock | when (UTC) | what happens |
|---|---|---|
| Hyperliquid funding | **every hour** [source: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding] | payment between longs and shorts; the displayed rate is hourly |
| CEX funding (Binance, Bybit, OKX) | historically every 8 h at **00:00, 08:00, 16:00**; Binance since 2026-01-02 switches contracts between 1 h and 4 h when rates are extreme [source: https://www.binance.com/en/support/faq/360033525031] | positions get opened/closed around the print to receive or avoid it |
| Deribit options expiry | **last Friday of the month, 08:00** (quarterly = Mar/Jun/Sep/Dec) **[our calendar]** | dealer hedges unwind; "max pain" folklore |
| FOMC decision | 8 scheduled meetings a year, statement 14:00 New York (18:00 UTC in summer, 19:00 in winter — the engine converts NY→UTC with DST) **[our calendar]** | the biggest scheduled macro move |
| CPI, NFP, PCE | 08:30 New York (12:30 / 13:30 UTC) **[our calendar]**; NFP first Friday of the month | macro surprise → rates → BTC → alts |
| sessions **[our calendar]** | asia 00–08 · europe 08–13 · us 13–21 · late 21–24 | who is at the desk |
| US equity cash hours | 13:30–20:00 UTC (summer) | risk-on/off spillover; ETF flows print at the close |
| weekend | Saturday–Sunday | thinner books, retail-heavy, no ETF flows, no macro |

## 2. Why it matters (the economics)

Time tells you **who is on the other side**. During US hours the marginal flow is
institutional and macro-driven and correlations to equities are highest; in Asian hours and
at weekends the marginal flow is retail and leverage-driven, books are thinner, and the same
dollar moves price more — so weekend and late-session moves are more often noise and more
often reversed, and liquidation cascades find less resting liquidity. Scheduled clocks
concentrate forced flow into known minutes: a funding print pulls position changes toward
it, an expiry unwinds hedges, a macro release moves everything at once. Knowing the clock
lets you decide *when* a thesis is allowed to be tested and when a move is not information.

## 3. Reading rules

### 3a. Calendar effects that survived significance **[measured in our store]**
| pattern | BTC | ETH | how to use |
|---|---|---|---|
| FOMC decision day (12 coins) | +1.01% (t ~2) | across all 12: +0.66% to +2.39%, all positive | a day-of long tilt; the day after gives some back |
| CPI day | not directional (t 0–1.2) | same | volatility event; no side |
| October | **+0.50%/day, t 3.1** | +0.15% (weak) | the strongest calendar tilt we have; skew long |
| Thursday | −0.34%/day (vs base t −2.1) | **−0.54%/day (t −2.4)** | do not open fresh risk on a Thursday; a trim day |
| Wednesday | +0.35%/day (t 2.1) | — | mid-week bid |
| Saturday | — | +0.30%/day (t 2.0) | weekend retail bid on ETH |
| turn of month (last 1 + first 3 days) | +0.23% (t 1.9) | **+0.36% (t 2.3)** | mild long tilt |
| after quarterly expiry (3 days) | +0.24% (weak) | **+0.62% (t 2.2)** | ETH drifts up after quarterly opex |
| June | −0.24% | **−0.47% (t −2.1)** | size down |
| Chinese New Year window (−5..+2 d) | +0.89%/day (t 2.1) | — | opposite of the "pre-CNY selling" folklore |
Noise (do not trade): Santa rally, the expiry day itself, US federal holidays, Thanksgiving,
most other months. These are **tilts of 0.3–0.5%/day on size and timing**, not trades; they
stack with a positioning or catalyst setup and never replace one. Nine years is thin for
holidays (8–9 observations each); day-of-week (~470) and month (~270) are solid.

### 3b. Around the funding print
| situation | reading |
|---|---|
| price drifts toward the print and snaps back after | positions opened/closed to collect or dodge funding; not information |
| a big funding print with no price move | the crowd is paying and not being rewarded (chapter 5) |
| Hyperliquid hourly vs CEX 8-hourly | to compare, multiply the hourly rate by 8; do not read a small hourly number as a small 8-hour number |

### 3c. Around expiry
- The drift, where it exists, is **after** the quarterly expiry (ETH +0.62%/day for 3 days
  **[measured]**), not on the day. "Max pain" pinning is folklore; we have no measurement.

### 3d. Around a macro release **[our desk]**
- Inside **24 h** of FOMC/CPI/NFP, every new chain must carry an `event_note` (how the
  event affects this trade) or wait. The first hour after the release is not tradeable by
  a model that decides every few hours; the chain should say what it expects *after* the
  first hour.
- The shock-day table (chapter 3) is the size prior: alts ≥ ETH > BTC on the day.

### 3e. Session and weekend rules
| when | rule |
|---|---|
| Asia session / late session | a sharp move on thin books with no news is more often noise; check OI and CVD before believing it |
| weekend | no ETF flows, no macro; thin books; liquidation cascades run further; checkpoints that fall on a weekend are judged on Monday's reaction, not Sunday's print |
| US open | the hour where macro and equity beta express themselves; a checkpoint set here is tested by real flow |
| daily bar | the engine's "day" closes at the **23:00 UTC** bar; a decision at that moment sees the full day |

### 3f. How fast is "fast"
- Majors reprice a scheduled macro surprise within minutes; small alts follow through beta
  over the hour and through their own flow over the day.
- A story in the news feed: the coin's own move usually precedes or coincides with the first
  articles; by the time a story has many articles and no new facts, its flow is over
  (chapter 8, novelty).
- Our own latency: candles hourly, funding/OI hourly, positioning hourly, news every 15 min
  when the pipeline exists; decisions every few hours. Anything faster than that is not our
  game — do not write a chain that needs a 10-minute reaction.

## 4. Worked example

Thursday 12:00 UTC, FOMC statement today at 18:00 UTC, CPI was yesterday (no direction).
Candidate C12 (beta 1.3, R² 0.5) long on a funding-squeeze read.
- Clock: 6 h to FOMC → inside the 24 h blackout → the chain needs an `event_note`.
- Calendar tilt: FOMC day-of has been positive across all 12 measured coins; Thursday has
  been a weak day for both majors. Two small tilts, opposite signs: neither is a reason.
- Shape: the squeeze thesis is a 7-day effect (chapter 5); the FOMC move is a day-of event
  with give-back the next day. Note: "expect a beta move of ±1.3 × BTC on the statement;
  thesis is not about it; falsifier is on the coin's *own* move after the first hour, not on
  the BTC-driven wick." Checkpoint on day 3, after the give-back day.
- Weekend: day 3 is Sunday → the checkpoint is judged on Monday's US session.

## 5. Common misreads

1. **Opex on the "third Friday".** Deribit monthly/quarterly expiries are the **last Friday,
   08:00 UTC** **[our calendar]**; and the measured drift is after, not on the day.
2. **Reading a Hyperliquid hourly funding rate as an 8-hour rate.** ×8 to compare.
3. **Trading a calendar tilt as a trade.** They are 0.3–0.5%/day tilts; stack them, never
   lean on them.
4. **Chasing an Asian-session spike.** Thin books; check OI/CVD; usually noise.
5. **Judging a checkpoint on a weekend print.** Wait for Monday's flow.
6. **Ignoring the blackout.** A chain that does not say what FOMC does to it is not a plan.
7. **CPI "beat = up".** Not directional in our data; it is a vol event.

## 6. Sources
- Our store: `docs/CALENDAR_SEASONALITY.md` (BTC/ETH 2017→2026; FOMC/CPI 12 coins 2020→2026; t-stats as printed); `sim/events.py` (sessions, NY→UTC DST, Deribit rule); `sim/data.py` (23:00 bar).
- Hyperliquid funding cadence — https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding
- Binance funding intervals — https://www.binance.com/en/support/faq/360033525031
