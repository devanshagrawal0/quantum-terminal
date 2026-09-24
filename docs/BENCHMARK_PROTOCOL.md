# Benchmark protocol — fixed rules, applied identically to every version
2026-09-16. This replaces the hand-scored table in `BENCHMARK_2026-09-16.md` as the authority. The scorer is `scripts/benchmark.py`; it reads only artefacts on disk and prints, per category, the rung reached, the score, and the exact condition that failed for the next rung. A person contributes one number (C6 view consistency) by applying the written rule in §3 and recording it in `judged.json` in the run folder; everything else is computed.

## 1. What a benchmark run is
- **Window A (small):** 2026-08-10 → 2026-08-18, all 172 coins, `--fresh-memory`, `SIM_THINK_TOKENS=3000`, same model file and server flags (`C:\llm\run-qwen.ps1`). This is the window every version is scored on first.
- **Window B (full month):** 2026-08-01 → 2026-08-31, same settings; required for rungs that need ≥ 20 trades.
- **Window C (year):** 2025-01-01 → 2025-12-31 in monthly batches with memory carried; required for rungs that need ≥ 60 trades, twins, walk-forward.
- Artefacts the scorer reads: `decisions.jsonl`, `trades.csv`, `summary.json`, `judged.json` (optional), the memory db for that run id, `selftest_result.json` (written by `scripts/selftest.py --json`), and, when they exist: `twins.json`, `junk_report.json`, `stress_report.json`, `replay_hash.json`, `ablations.json`, `calendar` tables in `store.db`, `link`/`belief`/`node` tables in the memory db.
- Model output is never trusted as evidence of a capability: a rung is met only by something the engine logged or computed.

## 2. Scoring rule
Each category has rungs 20/40/60/80/100, each a list of measurable conditions. The category's rung = the highest rung whose conditions are **all** met, and every lower rung's too. Score = rung + round(10 × share of the *next* rung's conditions that are met). Mean of the 15 is the version's number. Two versions with the same artefacts get the same score, always.

## 3. The one judged input: C6 view consistency
Rule a person applies per decision, recorded as `judged.json: {"view_consistency": [1,0,1]}` (one entry per decision):
- List every coin label the market view names with a directional reading (squeeze up, crowded long = downside, momentum long, avoid X, etc.).
- The decision is **consistent (1)** if every order's side agrees with the reading given for that coin, and no order is placed on a coin the view says to avoid, and no order is placed on a coin the view gives the opposite reading for. Orders on coins the view does not mention are neutral. Otherwise **0**.

## 4. Category rungs (conditions the scorer checks)

**C1 Information gathering** — checklist item → tools: 1 `regime`; 2 `funding_extremes|positioning|funding`; 3 `scheduled_events`; 4 `market_table` sorted by `vol_zscore|r_1d|r_7d`; 5 `evidence|stops_report|insights`; 6 `similar`; 7 `funding|cross_venue|fear_greed`; 8 every order has a falsifier.
- 20: mean items covered per decision ≥ 6.
- 40: 8 of 8 in every decision.
- 60: ≥ 2 investigator rounds in ≥ 80% of decisions (tool log carries `round`), and in ≥ 50% of decisions a call names a coin that appeared in an earlier round's result (conditional question).
- 80: `compute` called ≥ 1 per decision on average; every order's coin was queried by ≥ 2 distinct tools before the order (cross-check).
- 100: ≥ 30 decisions in the scored windows with 8/8 coverage in ≥ 95%.

**C2 Event & chain reasoning**
- 20: ≥ 90% of orders carry mechanism + falsifier + checkpoint in the chain.
- 40: lessons of ≥ 80% of closed trades carry a checkpoint/falsifier verdict; ≥ 1 trade in the window closed by `falsifier` or a verdict says "not triggered"/"TRIGGERED".
- 60: `event_instance` table exists with ≥ 3 event families and ≥ 1 non-unlock instance inside the window; decisions log an `events` section in the sheet.
- 80: `link` table has ≥ 1 admitted link; ≥ 80% of chains carry a `link` field (measured with n,t or `unmeasured`); confidence cap applied (verdict check `link_cap`).
- 100: `acceptance/T1.json` exists with `pass: true`; ≥ 30 chains graded per link.

**C3 Cross-sectional awareness**
- 20: `feat_cross` has rows through the window; skeptic dossiers carry `btc_relationship`.
- 40: ≥ 90% of risk verdicts carry `beta_btc`, `beta_stress`, `stress_loss_3sigma`, `vol_scale`, `cluster`.
- 60: each closed trade has `attribution` (market vs residual bps) and cluster stability median ≥ 0.5 (`xsec.cluster_stability`).
- 80: `/api/xsec_corr` and `/api/xsec_map` respond (viewer) and ≥ 1 order is a hedged leg or residual-sized (`hedge` field).
- 100: ≥ 60 trades with attribution summed to net.

**C4 Crowd reading**
- 20: `funding` or `positioning` called ≥ 1 per decision on average; results carry `crowd` labels.
- 40: ≥ 90% verdicts carry `funding_quintile`; `open_interest` called or `oi_change_7d_usd` in dossier in ≥ 50% decisions.
- 60: decisions log `links_shown` with the funding→return link (n,t) in the strategist prompt.
- 80: dossier carries liquidation and cross-venue fields non-null in ≥ 50% decisions.
- 100: carry sleeve live result ≥ 60 trades.

**C5 Provenance & anti-hallucination**
- 20: ≥ 80% of cards cite a tool called that decision.
- 40: 100% (engine rejects the rest, `cards_rejected` logged) and ≥ 90% of numbers in card text appear in the cited tool's result (rounded to 2 significant figures).
- 60: text-source cards carry `quote` + `url` + `fetched_at`; `citation_precision`/`recall` in decision log.
- 80: `junk_report.json` exists with exposure/flip/rule-break/citation scores.
- 100: junk report passes J11 (flip rate < clean run-to-run noise, 0 obeyed instructions, 0 phantom positions).

**C6 Consistency of beliefs**
- 20: market view present in every decision; `judged.json` mean view_consistency ≥ 0.67.
- 40: `belief` table has ≥ 1 row per decision with p_model/p_engine/p_final.
- 60: ≥ 90% orders cite `belief_ids`; `contradiction_blocked` logged ≥ 0 with no bypass.
- 80: `belief_revision` rows exist with surprise bits; `belief_score` rows with Brier.
- 100: ≥ 100 resolved beliefs, calibration slope in [0.7, 1.3].

**C7 Memory & learning**
- 20: ≥ 80% of closed trades have an experience row with a lesson.
- 40: `evidence` or `similar` consulted in ≥ 90% of decisions (or engine pre-fetch logged as `outside_view`); ≥ 80% lessons carry verdicts.
- 60: `node`/`edge` tables exist; `graph_walk` or `analogues` logged in ≥ 50% decisions; ≥ 1 reflection row with cited node ids.
- 80: ≥ 1 active insight; ≥ 1 skill row.
- 100: `ablations.json` shows memory-off twin excess lower than agent by ≥ 25 bps/trade.

**C8 Skeptic**
- 20: verdicts for ≥ 90% of orders with non-empty reason; 0 `words_vs_json` mismatches.
- 40: ≥ 50% verdicts carry `basis` ⊆ dossier keys (non-empty); prompt contains no arithmetic request (`skeptic_prompt_version ≥ 2`).
- 60: ≥ 80% verdicts carry `breaks_if_false` naming a card index; ≥ 1 `contradiction` verdict in the window.
- 80: `ablations.json` skeptic-off twin shows lower excess by ≥ 25 bps/trade.
- 100: same across ≥ 3 regime labels.

**C9 Risk desk**
- 20: risk verdicts on 100% of orders; ≥ 6 rule checks evaluated on ≥ 90% of verdicts (counting violations would reward bad plans).
- 40: ≥ 90% verdicts carry `funding_quintile`, `cluster`, `beta_btc`, `stress_loss_3sigma`; verdict checks carry `event_blackout`.
- 60: verdict checks carry `stamped_facts`, `dossier_fresh`, `ledger_ok`, `preflight`; rejection rate in summary.
- 80: `stress_report.json` with scenarios a–f and pass flags.
- 100: `level.json` with L ≥ 2.

**C10 Sizing**
- 20: ≥ 2 distinct notionals; verdict checks carry `kelly_scale` and `vol_scale`.
- 40: `calibration_bucket` applied on ≥ 50% of verdicts (needs n ≥ 10 per bucket).
- 60: `twins.json` has equal-weight and inverse-vol twins on the same dates.
- 80: ≥ 100 trades; agent excess ≥ both twins.
- 100: `capacity` field on every order.

**C11 Plan quality**
- 20: 100% of opened orders have stop in [1.5, 3] own daily moves and target ≥ 2 moves.
- 40: ≥ 80% of round-1 verdicts had no stop/target violation (the strategist got it right first time). Hold days are engine-derived from the target and the coin's own move (batch 2, 2026-09-16) and are never a violation.
- 60: bounce rate ≤ 20%; `stops_report` called in ≥ 50% decisions.
- 80: every order on a coin with an event inside its hold carries `event_note`.
- 100: noise-stop rate (exit = stop and mfe ≥ target) < 20% over ≥ 60 trades.

**C12 Accountability & grading**
- 20: 100% of lessons carry excess and counterfactuals.
- 40: ≥ 80% lessons carry checkpoint/falsifier verdicts.
- 60: losses carry `loss_class` (thesis/timing/risk-plan/regime) from the reviewer.
- 80: `belief_score` rows and per-hat `attribution_bps` in decisions.
- 100: `states.json` (research/declared/executed) over a full year.

**C13 Outcome vs twins**
- 20: n ≥ 20 trades and `twins.json` exists.
- 40: n ≥ 60 and bootstrap 90% CI of excess/trade excludes 0.
- 60: PSR ≥ 0.95 and DSR reported.
- 80: walk-forward sign stability ≥ 5/8 and ≥ 2 ablations show loss.
- 100: held-out H2-2026 and 90-day prospective pass.

**C14 Robustness**
- 20: `selftest_result.json` all pass; 0 decision errors in the window.
- 40: call meta shows `json_schema` on 100% of calls; ≥ 1 garbage/empty/server-down path exercised live (`unanswered_desk_fixed`, `error`, or `attempt ≥ 2` present in any run of the version).
- 60: `junk_report.json` exists.
- 80: `seeds.json` (3 seeds, mean±sd), `replay_hash.json` equal, `backbone.json` (second GGUF run).
- 100: `stress_report.json` all pass.

**C15 Calibration & abstention**
- 20: confidence on 100% of orders.
- 40: `calibration_bucket` used on ≥ 50% verdicts (n ≥ 10 per bucket).
- 60: strategist meta shows `samples: 3` (median-of-3) and ≥ 1 decision with `no_trade_reason` logged.
- 80: calibration slope in [0.7, 1.3] over ≥ 50 resolved.
- 100: ≥ 100 resolved across ≥ 3 regimes.

## 5. Fields the runner must log for the scorer (added as the waves land)
`round` on every tool-log entry (W1 patch below) · `events`, `links_shown`, `cards_rejected`, `outside_view` in the decision record (W2/W3) · `basis`, `breaks_if_false` on skeptic verdicts (W3) · `event_blackout`, `stamped_facts`, `dossier_fresh`, `ledger_ok`, `preflight` in risk checks (W2/W6) · `attribution`, `loss_class` on lessons (W3) · `samples`, `no_trade_reason` (W3) · `json_schema` in call meta (W4/M1).
