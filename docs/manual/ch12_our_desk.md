# Chapter 12 — Our desk: who does what, the rules and why, the memory, the benchmark, and the list of things you got wrong

This is the chapter about the room you work in. Everything here is what the code does
today (`sim/`), not a plan. Where a rule has a number, the number is in `sim/risk.py`; where
a fact is measured, it is in `docs/MEASURED_LINKS_2026-09-16.md`.

## 1. The four hats and the desk

| hat | who | job | what it may not do |
|---|---|---|---|
| **Investigator** | model, thinking off | work the 8-item checklist by asking questions and answering each with a tool call; produce a market view, evidence cards (each citing the tool call), candidates | invent a number; cite memory as a source |
| **Strategist** | model, thinking on | write chains for up to 3 trades from the cards, the candidate rows, the own record, the similar situations and the measured links | compute stops/targets/holds (copy the printed bands); trade a coin already held |
| **Skeptic** | model, thinking off | attack the weakest order using the dossier the engine gathered (own record, similar, crowd, funding, vol vs stop, correlations); veto / resize / replan / stand, with a reason | grow a trade; do arithmetic (the dossier carries the numbers) |
| **Risk desk** | code only | every number and every rule (below); size; one replan round with the strategist; then final | be overridden |
| **Engine** | code | prices, fees, funding, stop/target/falsifier exits at the daily bar, MFE/MAE, counterfactual grid, lessons, memory | — |

The checklist the engine gates (a decision is not allowed to end until each is covered; the
engine covers what the model skipped and logs it as `auto_cover`):
1 regime · 2 crowd (funding extremes / positioning) · 3 scheduled events · 4 movers
(market_table sorted by vol z / returns) · 5 own record (evidence / stops_report /
insights) · 6 similar situations · 7 funding / cross-venue / fear-greed · 8 every order has
a falsifier.

## 2. The tools (what each returns; chapter to read it with)
| tool | returns | chapter |
|---|---|---|
| `market_table` | a slice of the 172-coin table, sorted by a column | 10 |
| `regime` | regime label, BTC 30d, breadth | 3 |
| `correlations` | correlation to BTC and pairwise for named coins | 6 |
| `positioning`, `open_interest`, `funding`, `funding_extremes`, `cross_venue` | crowd and derivatives facts with a **crowd label in words** ("shorts pay longs — shorts crowded — squeeze UP") | 5 |
| `fear_greed`, `macro_rates` | sentiment index; Fed funds, 10y, EUR/USD | 5, 8 |
| `calendar`, `scheduled_events`, `event_history` | what is scheduled, hours away; what happened around past events of that type | 8, 9 |
| `links` | measured shock → return links with n, t and status (admitted / unmeasured) | 5 |
| `similar`, `evidence`, `stops_report`, `insights`, `calibration`, `market_view`, `recall` | your own memory: k-NN similar trades, decayed record by side/regime, which stop/target plans paid, active insights, stated-vs-real win rate, past views, lessons by words | 11, 12 |
| `write_note` | a note to your future self | 11 |
Tools take **one** coin label; there is no ALL. Coins are anonymised (C1…Cn) and the date is
hidden so you cannot use hindsight.

## 3. The rules and why each exists **[our desk]**
| rule | number | why |
|---|---|---|
| stop | 1.5–3.0 own daily moves | inside 1.5 = noise stop; the model set 0.55× moves when left alone |
| target | ≥ 2 own moves and ≥ 1.5 × stop | must pay for costs and the stop's hit rate |
| hold | engine-set from the target: ceil((target/move)²), ≤ 14 days | a target needs time ∝ moves²; never a violation |
| falsifier | correct side, inside the stop, has a day; 0% is not a falsifier (desk sets 60% of stop) | thesis death must fire before the stop |
| cluster cap | ≤ 2 positions per residual cluster | a cluster is one story |
| beta band | net beta $ ≤ 50% of risk capital ($2,000 = 20 units × $100) | survive a BTC shock |
| net / gross | with 4+ positions, net ≤ 60% of gross | the book may lean, not be one bet |
| stress | 3σ BTC move × stressed beta (1.4 default) ≤ 10% of risk capital | crash correlation ~0.76 |
| funding rule | long on a top-quintile-funding coin needs p ≥ 0.60; short on a bottom-quintile coin needs p ≥ 0.65 | a Q5 long pays ~22 bps/wk; a Q1 short pays ~48 bps/wk against it **[measured]** |
| repeat after loss | same coin & side, lost within 7 days → p ≥ 0.65 | outside view first |
| link cap | with no admitted measured link, p_final ≤ 0.65 | a chain built on an unmeasured link is a hypothesis |
| event blackout | macro event inside 24 h → chain needs an `event_note` or waits | the first hour is not our game |
| p_final | (1−k)·stated + k·own win rate, k = n/(n+10); then the calibration bucket (n ≥ 10) | the model's 0.8s are not 0.8 |
| size | quarter-Kelly(p_final, stop/target) × clip(12% / own vol, 0.25, 1) × brakes | edge, then vol, then book, then brakes |
| brakes | CVaR day → ×0.5 for 5 days; drawdown > 15% of risk capital or day loss > 3% → no new trades | survive to trade next week |
| provenance | a card without a tool citation is dropped; numbers in cards must match the cited result | the model's memory is not a source |
| replan | the desk bounces once with the numbers in the strategist's units; unanswered or garbage → desk applies its own numbers and says so | a good trade is not lost to a rounding argument |

## 4. The memory (what you can learn from) **[memory.db]**
| table | holds | tool |
|---|---|---|
| experience | every closed trade: features at entry, chain, confidence, net/excess bps, MFE/MAE, exit reason, days, counterfactual grid, lesson with checkpoint/falsifier verdicts | `similar`, `evidence`, `stops_report` |
| insight | rules with support (active only with out-of-sample support; 0 active today) | `insights` |
| note | market views and notes, full-text searchable | `market_view`, `recall` |
| calibration | stated confidence bucket vs realised win rate (needs n ≥ 10 per bucket) | `calibration` |
Evidence decays with age; k-NN similarity uses the entry features; a run's memory is copied
into its run folder so it is never lost.

## 5. The benchmark (how a version is judged) — `docs/BENCHMARK_PROTOCOL.md`
15 categories, each with rungs 20/40/60/80/100 of measurable conditions read from the logs:
C1 information gathering · C2 event & chain reasoning · C3 cross-sectional awareness · C4
crowd reading · C5 provenance · C6 consistency of beliefs · C7 memory & learning · C8 skeptic
· C9 risk desk · C10 sizing · C11 plan quality · C12 accountability · C13 outcome vs twins ·
C14 robustness · C15 calibration & abstention. Score = mean of the 15; the same artefacts
always give the same score. **Last measured: 31.5 / 100** (Window A, batch 3). Model output
is never evidence of a capability — only what the engine logged or computed.

## 6. The list of things you got wrong (from the 42-question exam, 2026-09-17) — and the fix
| you said | the truth | chapter |
|---|---|---|
| negative funding → "crowded long, squeeze down" | negative = shorts pay = crowded **short** = squeeze **UP** | 1, 5 |
| "short 150 BTC" as a hedge | hedge = beta × notional in **dollars of BTC** ($150) | 3 |
| rising CVD + falling price = "aggressive selling" | rising CVD = net aggressive **buying**; that combo is absorption | 5 |
| √252 | **√365** | 7 |
| Kelly 0.125 for p 0.58, b 1.33 | f\* = p − (1−p)/b = **0.265**; the desk uses a quarter | 7 |
| opex "third Friday" | Deribit: **last Friday 08:00 UTC**; the drift is after quarterly expiry, not on it | 9 |
| "utility / governance / security / NFT" coin types | BTC, ETH, L1, L2, DeFi, exchange, meme, AI, RWA, stable, new listing — each with driver, beta, move, trap | 4 |
| 0.85 residual correlation = "two distinct bets" | about one bet; size the pair as one | 6 |
| short-squeeze signs: borrow fees, short interest | perps have no borrow; signs are negative funding + OI falling + short liquidations + perp CVD leading | 5 |
| hack → "50–90% in the first hour" | tens of percent, case by case; the first hour is not tradeable | 8 |
| "the stop comes first; the falsifier can override" | the falsifier is the plan; the stop is the net | 11 |
| "idiosyncratic" = low correlation this week | 7-day R² well below 90-day R², own vol up | 6 |
| a stop at 0.55 daily moves with the vol printed | 1.5–3 own moves; the desk bounces the rest | 7 |
| a chain citing nothing | dropped; every card cites a tool call | 12 |

## 7. What you must copy and what you must decide
| copy (the engine printed it) | decide (only you can) |
|---|---|
| own daily move, stop band, target minimum, hold days | the mechanism: who has to trade and why |
| beta, R², cluster, crowd label, funding quintile | which candidate, which side, which horizon |
| the book's room in words | the falsifier and the checkpoint |
| p_final, size | your honest confidence before shrink |
| the event note requirement | what the event does to this trade |

## 8. Sources
- `sim/investigator.py`, `sim/risk.py`, `sim/engine.py`, `sim/memory.py`, `sim/tools.py`, `sim/events.py`, `sim/links.py`, `sim/xsec.py`; `docs/BENCHMARK_PROTOCOL.md`; `docs/BENCHMARK_SCORES_2026-09-16.md`; `docs/MEASURED_LINKS_2026-09-16.md`; `scratchpad/exam2_answers.json`.
