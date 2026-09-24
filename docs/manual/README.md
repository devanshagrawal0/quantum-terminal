# The desk manual — what the agent is taught before it trades

Purpose: the model measured ~58/100 on textbook knowledge and ~35/100 on desk knowledge
(`scratchpad/exam2_answers.json`, 42 questions, 2026-09-17). This manual is the knowledge
layer. It teaches *reading*, never *calculating*: every number the desk needs is computed by
the engine and handed over; the manual says what the number means and what to do.

Rules for every chapter: plain English; tables over prose; one worked example with units; a
"common misreads" list built from the model's real exam errors; every number either
**[measured in our store]** (our 172-coin Hyperliquid data) or cited with a URL; nothing
invented. Chapters are delivered per hat (investigator, strategist, skeptic, watcher), not as
one dump — a knowledge document that helps one task can hurt another
(https://www.alphaxiv.org/abs/2606.15390), so each chapter's effect is measured on the exam and
on the benchmark and a chapter that hurts a category is rewritten or cut.

| # | chapter | file | status |
|---|---|---|---|
| 1 | What you are trading: perpetual swaps (mark/index, funding, OI, basis, liquidations, fees) | `ch01_perpetuals.md` | written 2026-09-17 (agent), read + 2 slips fixed by me — not yet tested on the model |
| 2 | The economic foundation: why prices move; what every feature measures | `ch02_economic_foundation.md` | written 2026-09-17 (agent), read + 2 slips fixed by me — not yet tested on the model |
| 3 | BTC is the market: beta, R², dominance, crashes, hedging | `ch03_btc_is_the_market.md` | written 2026-09-17 — not yet tested on the model |
| 4 | Coin types and sectors: the trader's taxonomy | `ch04_coin_types.md` | written 2026-09-17 (agent), read + 2 slips fixed by me — not yet tested on the model |
| 5 | The crowd: funding, OI, CVD, liquidations, positioning, sentiment | `ch05_the_crowd.md` | written 2026-09-17 — not yet tested on the model |
| 6 | Correlation, clusters and the book | `ch06_correlation_clusters_portfolio.md` | written 2026-09-17 — not yet tested on the model |
| 7 | Volatility, stops and sizing (own moves, √365, noise vs thesis stops, vol targeting, Kelly) | `ch07_volatility_stops_sizing.md` | written 2026-09-17 — not yet tested on the model |
| 8 | News, events and catalysts (types, measured reactions, priced-in checks, sources, novelty) | `ch08_news_events.md` | written 2026-09-17 — not yet tested on the model |
| 9 | Time: sessions, funding times, weekends, opex, the macro calendar | `ch09_time.md` | written 2026-09-17 — not yet tested on the model |
| 10 | The feature dictionary: every column in the store, what it measures, what it is for, its limits | `ch10_feature_dictionary.md` | written 2026-09-17 — not yet tested on the model |
| 11 | How to be a trader: what to look at first, thesis → falsifier → checkpoint, cutting, adding, exits, the journal, expectancy, how accounts die | `ch11_how_to_be_a_trader.md` | written 2026-09-17 — not yet tested on the model |
| 12 | Our desk: the rules and why, the memory, the benchmark, the misreads list | `ch12_our_desk.md` | written 2026-09-17 — not yet tested on the model |

Measurement plan: rerun the 42-question exam with the relevant chapters attached (before /
after per area), then Window A with the manual on vs off through `scripts/benchmark.py`.
Nothing here is verified to help until those numbers exist.
