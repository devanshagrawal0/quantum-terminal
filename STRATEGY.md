# How this system makes money — the honest version

Written after a night of measuring. Every claim here is either [MEASURED] on our
own data tonight, [RESEARCH] from the source docs, or [DESIGN] a decision about
how the system is built. Nothing here is aspirational — if it did not survive a
test it is in the graveyard, not the plan.

---

## The core thesis, corrected

The bot is **not** a factor machine. We tested factors tonight and the maths is
brutal: the standard error on an information coefficient over a year of daily
data is ~0.05, a *good* crypto factor is 0.03–0.05, and break-even after our
costs is IC ~0.012. **You cannot statistically tell a good factor from zero on a
year of data.** [RESEARCH + MEASURED] So single-factor hunting is a game we lose:
everyone has those numbers, with more history.

The edge is **reasoning over the whole picture** — the weak measured effects,
plus events, plus cross-venue structure, plus the human read of a situation that
no single number captures. A crowded-funding coin is a weak signal alone; a
crowded-funding coin *plus* a Korean caution notice *plus* a stalling price is a
call. The reasoning combines what individually clears no bar.

---

## The graveyard — what we tested and killed tonight [MEASURED]

| Feature | Result | Why it died |
|---|---|---|
| Residual 7-day momentum | t_indep +1.0–1.3 | Collapses under overlap correction. 52 indep windows, indistinguishable from zero. |
| 1-day reversal | IC +0.034 but **net −20 bps/day** | Real as a statistic, useless as a trade. Lives entirely in illiquid coins where the spread is wider than the edge. Every route to trade it (cheaper names, vol-sizing, lower turnover) removed the effect — the signature of a spread artifact. |
| Binance positioning (top vs retail) | IC +0.013 | Below the 0.012 cost bar. Below the noise floor on 21 days. |
| Cross-venue basis (feature #1) | untested | Needs weeks of the panel; 2h old. Live now via the prediction log. |

**The lesson, kept:** an IC is not money. Three of these looked alive as a rank
correlation and were dead as a book. Every future signal goes through the same
cost + liquidity + period gauntlet before it is believed.

---

## The one survivor — funding carry [MEASURED]

Over a year of daily bars, 135 coins including delisted ones:

    top-decile-funding coins underperform
    funding-adjusted 7d IC  -0.068   t_indep -4.4   (53 independent windows)

This is the only thing all night that survived overlap correction. But the
decomposition matters and is the honest core of it:

    funding-ADJUSTED 7d IC   -0.068   (t -4.4)
    PRICE-ONLY 7d IC         -0.027   (t -2.2)   <- weak, below our 2.5 bar
    FUNDING-ONLY 7d IC       -0.671   (t -50)    <- the tautology

Most of the effect is **carry you literally collect** by shorting the high-funding
coin — real income, not prediction. A small genuine price bleed sits underneath
(t −2.2, real but under bar on one year). So the trade is **not** "predict the
price of crowded coins." It is **short the highest-funding names and harvest the
carry**, accepting the price is close to a coin-flip and there is squeeze risk.

This is exactly what the cryptobot's CROWDED / SQUEEZE / FUNDSPIKE bots already
target at 48–72h. Independent confirmation they aim at the one real effect.

**The check that decides if it's a strategy [NOT DONE]:** carry collected minus
price bleed minus squeeze-tail. An IC does not answer it; a net-P&L backtest with
funding, costs and a stop does. This is the next quant task.

---

## Where the real money is — events, not factors [RESEARCH + DESIGN]

The move/cost ratio is what makes something tradeable. A 3 bps factor edge dies
to 9 bps fees. A token unlock or a Korean listing moves 3–50% against the same
9 bps. That ratio is the whole argument for building around events:

- **Token unlocks** — ~90% negative pressure, drift starts ~30 days early. Best
  scheduled fit for a 1–7 day hold. *(free source went 402 mid-build; needs a
  new feed — open item.)*
- **Korean listings & caution tags** — Upbit lists ~28 days late, so the coin
  usually already has an HL perp we can trade. Korean titles are the moat.
  **Live in the events collector now.**
- **Delistings / monitoring tags** — direction unambiguous, forced selling,
  uncontested.
- **New HL perps** — universe diff, mechanical, ignored by news traders.
  **Live now.**
- **News as a LABEL, not an entry** — a +6% move with no news snaps back; the
  same move on a listing headline continues. Telling those apart is a bigger
  hole than any threshold, and needs no speed.

---

## The machine that's now running

Five collectors under one watchdog, writing five databases:

    venues        26 exchanges x 177 coins, every 5 min   -> prices, cross-venue features
    positioning   Binance crowd (OI, long/short, taker), hourly + 21d backfill
    events        HL universe diff + Upbit/Bithumb/Binance/Bybit announcements
    social        Telegram/Reddit/4chan/StockTwits, raw + honest first-seen
    predictions   every call hashed before outcome, scored vs market + vs random

**The decision surface** (`hl/dossier.py`): assembles all of the above for any
coin into one brief — cross-venue position, funding percentile, positioning,
regional premia, recent price, recent events — with the coin ranked against the
universe. It states no direction. Reasoning reads it and forms the call.

**The scoring** (`hl/predictions.py`): a call is written down with its entry
price and thesis, content-hashed so it can't be edited after the fact (proven:
tamper detection catches an edited direction). Scored against the equal-weight
market (no credit for beta) and against 40 random control calls (so reasoning
must beat coin-flips or it's decoration). Funding charged.

---

## What has to happen before real money [DESIGN]

1. **Funding-carry net-P&L test** — the one live effect, costed properly with a
   stop. Turns "real effect" into "strategy or not."
2. **A new unlock feed** — the best scheduled edge, and the free source closed.
3. **Event → coin linking** — currently a reasoning step, not automated (ticker
   substring matching is banned; "ME"/"W"/"S" are real tickers). Fine for now
   because the reasoning layer does it; needs a real entity resolver to scale.
4. **Let the prediction log mature** — the claude-vs-random scoreboard needs
   dozens of resolved calls before it means anything. First reasoned calls
   (GMX, STBL funding-carry shorts; REZ/ACE/BOME/STX basis) are logged and
   resolve over the next 1–3 days.
5. **Reboot survival** — the watchdog itself is unsupervised. A Windows logon
   task, pending Dev's OK.

The system does not trade real money until the prediction log shows reasoning
beating the random control over a meaningful sample. That scoreboard is the gate,
and it is now recording.
