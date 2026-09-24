# Chapter 8 — News, events and catalysts: what moves what, for how long, and how to tell if it is already in the price

A catalyst is a *reason* for a flow. The question is never "is this news good" but "who has
to trade because of it, when, and has that already happened". **[measured in our store]**
marks our data; other numbers carry a URL. Where we have no measurement and no source, it
says so.

## 1. What it is — the event families

| family | examples | scheduled? | who is forced to trade |
|---|---|---|---|
| central bank | FOMC decision + dot plot + press conference | yes, exact | macro funds re-pricing rates; leveraged crypto longs/shorts on the first move |
| macro release | CPI, NFP, PCE | yes, exact (08:30 ET) | same; a *surprise* vs consensus is what moves, not the number |
| token supply | unlocks (team / investor / ecosystem), emissions | yes, weeks ahead | recipients who sell, hedgers who short the perp beforehand |
| venue | exchange listings, delistings, perp launches | listing: sometimes announced; delisting: announced | listing: buyers who could not buy before, airdrop sellers; delisting: forced sellers |
| flows | spot ETF creations/redemptions, stablecoin mint/burn | published daily (ETF) | APs; visible spot flow |
| derivatives | monthly/quarterly options expiry, funding extremes | yes | dealers hedging; leveraged crowd |
| protocol | hack, depeg, outage, governance vote, fee switch | no (except votes) | holders exiting, arbitrageurs |
| narrative | sector rotation (AI, RWA, memes), a large-account thread | no | attention-driven retail flow |

## 2. Why it matters (the economics)

Scheduled events are **priced in advance** by people who can hedge; the move on the day is
the *surprise* plus the *unwinding of hedges*. Unscheduled events are priced in minutes on
the majors and in hours on small coins, then over-shoot and partially revert as forced flow
exhausts. So two different plays exist: *before* a scheduled event (position for the
expected flow, or step aside) and *after* an unscheduled one (fade the over-shoot or follow
the forced flow, depending on who is forced). The trap in both is trading the headline
after the flow it caused is already over.

## 3. Reading rules — what actually happened, measured

### 3a. Central bank and macro **[measured in our store]** (12 coins, 2020→2026, `docs/CALENDAR_SEASONALITY.md`)
| event | day-of | day after | reading |
|---|---|---|---|
| FOMC decision day | **every one of 12 coins positive, +0.66% to +2.39%**, several individually significant (MATIC +2.39 t 3, ADA +1.71, LINK +1.43, LTC +1.36, BTC +1.01) | mostly gives some back | risk-on relief into the decision; a *day-of* tilt, not a hold |
| CPI day | small, not significant (t ≈ 0–1.2) | — | a **volatility** event, not a direction; trade the size of the move, not a side |
| FOMC hawkish surprise (from the shock-day table) | BTC down, ETH down more, alts down most (alts ≥ ETH > BTC) | partial bounce | the chain "Fed surprise → BTC → alts more" is real on the day |
Desk rule **[our desk]**: a chain on a coin with a macro event inside 24 h must carry an
`event_note` saying how the event affects the trade, or wait.

### 3b. Exchange listings **[measured in our store]** — 178 Hyperliquid listings since 2023 (49 later delisted), returns from the first daily close
| horizon | median | share positive | mean |
|---|---|---|---|
| 1 day | −0.6% | 48% | +16% |
| 3 days | −3.0% | 44% | +34% |
| 7 days | −4.1% | 45% | +74% |
| 30 days | **−11.8%** | **44%** | +115% |
| best point inside 7 days | **+10.5%** | 69% | +105% |
Reading: the *typical* listing fades (median −12% by day 30, only 44% up), but 69% spike at
some point in the first week and a few go many-fold (the mean is huge, the median is
negative). That is a **fade-after-the-spike** shape, not a "short every listing" shape: a
short from day 0 eats the +10% spike first. Published CEX studies agree in shape: announced
listings rally *into* the date, surprise listings jump day 1, most medians negative by day
30 [source: ChainCatcher 2024 https://www.chaincatcher.com/en/article/2175717, via
`docs/AGENT_V2_RESEARCH_2026-09-16.md`]. **"Scheduled ⇒ fade, surprise ⇒ follow."**

### 3c. Unlocks [source: Keyrock, 16,000+ unlock events, https://keyrock.com/from-locked-to-liquidity-what-16000-token-unlocks-teach-us/]
| fact | number |
|---|---|
| unlocks followed by short-term declines | ~90% |
| when the drift starts | ~30 days **before** the date |
| team unlocks, average | ≈ −25% |
| ecosystem unlocks | ≈ +1.2% |
| unlocks > 5% of circulating supply, 30-day window | median drop 8–15% |
| price stabilises | ~14 days after |
Reading: the event is the *month before*, not the day. On the day, much of it is done. A
vendor study, not peer-reviewed; consistent with our own unlock cases (the "unlock
landmine" in the kill test). Our own replication on 142 unlock rows is still to do.

### 3d. Spot ETF flows [source: SSRN 6592830 "The Price Impact of Spot Bitcoin ETF Flows" — numbers from the search snippet, paper unfetched, via `docs/AGENT_V2_RESEARCH_2026-09-16.md`]
- flows explain ~21% of BTC's daily return variance (313 days, 2024–25); $100M net flow ↔
  about +53 bp same day; predicts next day; **no reversal at 1–20 days**.
- Reading: a visible spot flow that does not mean-revert quickly — a *follow* signal for
  BTC, and through beta for the majors. Five green days tell you demand is there; they do not
  tell you the size of tomorrow's flow.

### 3e. Hacks, depegs, outages — **no clean measurement in our store, no clean study found**
What is known: USDC fell to $0.87 in its 2023 depeg with ~$1.2B/hour CEX outflows and only
USDC-linked assets deviating [source: https://pith.science/paper/2606.07442, unfetched
snippet]. For a protocol hack the honest statement is: price falls immediately, the size
depends on loss ÷ treasury/mcap and on whether funds are recoverable; typical first-day
drops are tens of percent, not "50–90% in the first hour" (the exam answer) — but we have
no table, so treat every hack case-by-case and do not trade the first hour.

### 3f. Is it already priced in? Three checks the engine can do
1. **Move before the event vs history**: the coin's return over the run-up compared with the
   median run-up before the same event type (`event_history` tool; `hist_move_median` in the
   calendar features). If it has already done its usual pre-event move, the event is in.
2. **Positioning**: funding and OI already stretched in the direction of the expected
   outcome = the crowd is positioned; the asymmetric move is the *other* way (chapter 5).
3. **Novelty**: has the same story been in the feed for days (many articles, no new facts)?
   Old stories move nothing; a *new* fact in an old story does.
Options-implied vol is a fourth check when we have it (`feat_options`, mostly empty today).

### 3g. Sources and confirmation
- A rumour on X is not a fact. Confirmation = the exchange's or project's official channel,
  a filing, or an on-chain transaction. Until then it is a *watch*, not a trade.
- Every card the model writes must cite the tool call it came from; the engine drops
  uncited cards **[our desk]**. Model memory is not a source.

## 4. Worked example

Coin C41, an L2 token. Calendar: 8% of circulating supply (investor tranche) unlocks in
5 days. Funding −0.02%/8h, OI +30% over two weeks, price −18% over 30 days.
- Unlock reading: the drift usually starts ~30 days before — this coin is already down 18%
  with 5 days to go; much of the "event" has happened. Investor tranches are often hedged
  (short the perp beforehand): the negative funding and rising OI are consistent with that.
- Crowd reading: shorts crowded and *paying*; squeeze risk up **after** the supply clears.
- Trade shape, if any: **not** a short into the date (late to the flow, paying against you);
  a long is early until the date passes — plan it for day +1 to +3 with the falsifier "price
  makes a new low on rising OI after the unlock" and an `event_note`. Stabilisation ~14 days
  after is the hold horizon.

## 5. Common misreads

1. **Trading the unlock on the day.** The move is the month before; the day is often the low.
2. **"Short every listing."** Median fades, but 69% spike first; short the fade after the
   spike, or stand aside.
3. **Reading CPI as a direction.** It is a vol event **[measured]**; a side must come from
   the surprise, not the release.
4. **Fading FOMC day.** **[measured]** 12 of 12 coins up on the day; the give-back is the
   day after.
5. **Hack = −50–90% in an hour.** No; case by case, usually tens of percent, and the first
   hour is not tradeable.
6. **A five-day ETF inflow streak means tomorrow is up.** It means demand exists and has
   not reverted; it does not size tomorrow's flow.
7. **Treating a rumour as a catalyst.** A watch until confirmed by an official channel.
8. **A card with no tool citation.** Dropped by the engine; write only what a tool returned.

## 6. Sources
- Our store: `docs/CALENDAR_SEASONALITY.md` (FOMC/CPI, 12 coins 2020→2026); `data/carry_cache/listings.parquet` measured 2026-09-17 (178 listings since 2023, incl. 49 delisted); `sim/events.py`, `sim/risk.py` (event blackout rule).
- Keyrock unlock study — https://keyrock.com/from-locked-to-liquidity-what-16000-token-unlocks-teach-us/
- ChainCatcher listing study (2024) — https://www.chaincatcher.com/en/article/2175717
- Spot ETF flow impact (SSRN 6592830, snippet only) and USDC depeg contagion (2606.07442, snippet only) — via `docs/AGENT_V2_RESEARCH_2026-09-16.md`.
