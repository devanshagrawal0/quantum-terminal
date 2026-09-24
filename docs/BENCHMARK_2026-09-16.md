# The 15-category benchmark — strict, absolute scale
2026-09-16. Runs compared: **old** = `20260915_185413_investigator` (first small test: investigator + strategist only) and **new** = `20260916_174147_investigator` (small test v2: + skeptic + risk desk + cross-sectional layer + falsifier exits). Same dates (Aug 10–18 2026), same 172 coins, fresh memory, 3 decisions and 5 trades each.

**How to read the scale.** 100 = the standard the research says a world-class, verifiable desk meets (sources: the two research dossiers, MEASURED_LINKS, the spec). It is *absolute*: five clean orders do not earn it, a validated capability over a real sample does. Each category has rungs with observable criteria; a run gets the highest rung it fully meets, plus up to +10 for partial progress toward the next rung that is visible in the logs. "Judged" lines quote the log. Scores under 20 are normal at this stage and are the point of the exercise: the gap column is the build list.

Reference: the minimum-rule pass rates (`scripts/benchmark.py`) are in `scratchpad/benchmark_passrates_2026-09-16.md`; they are compliance checks, not quality scores.

| # | category | old | new | biggest gap to 100 |
|---|---|---|---|---|
| 1 | Information gathering | 14 | 12 | asks less than the checklist, never computes, no cross-check |
| 2 | Event & chain reasoning | 8 | 12 | no calendar, no measured links, chains unverified |
| 3 | Cross-sectional awareness | 0 | 22 | facts shown; not reasoned with; clusters unstable |
| 4 | Crowd reading | 10 | 24 | funding only; no OI/liquidation/cross-venue; no measured strength |
| 5 | Provenance & anti-hallucination | 12 | 16 | no quotes, no number verification, no junk test |
| 6 | Consistency of beliefs | 6 | 14 | no belief board; consistency is luck, not a mechanism |
| 7 | Memory & learning | 12 | 14 | flat tables; outside view not enforced; no insights earned |
| 8 | Skeptic | 0 | 10 | restates arithmetic (wrongly); never attacks a thesis with evidence |
| 9 | Risk desk | 0 | 24 | 9 rules, 3 exercised live; no events, no validation |
| 10 | Sizing | 0 | 12 | formula unvalidated; p uncalibrated |
| 11 | Plan quality | 6 | 28 | stops now vol-aware by force; model still proposes noise stops |
| 12 | Accountability & grading | 18 | 30 | falsifier/checkpoint graded; no mechanism grading, no Brier, no reviewer |
| 13 | Outcome vs twins | 2 | 2 | n=5; no twins run; no statistics possible |
| 14 | Robustness | 6 | 18 | 57 tests; no junk test, no live error path, no seeds, no replay |
| 15 | Calibration & abstention | 4 | 4 | n=5; overconfident; no abstention logic |
| | **mean** | **6.5** | **16.1** | |

---

## 1. Information gathering — "asks everything it can"
**100 means:** every decision answers all 8 checklist questions with a tool result *and* asks second-order questions conditioned on the answers (Self-Ask), computes at least one number it did not have (`compute()`), cross-checks any fact that changes a side against a second source, and reads the calendar and news for every candidate. Measured over ≥30 decisions with checklist coverage ≥95%.
**Rungs:** 0 none · 20 covers ≥6/8 questions on average with first-order questions only · 40 covers 8/8 every decision · 60 + conditional follow-ups visible in the log · 80 + `compute()` used and cross-checks · 100 + measured over ≥30 decisions.
**old 14** — distinct tools 7/8/8 but four of those are the pre-fetched sheet; real questions 12/10/10 per decision, all first-order; no second-order follow-ups ("funding is extreme — how did the last 5 extremes resolve?"); no compute; no calendar beyond unlocks.
**new 12** — 5/7/5 distinct tools; Aug 17 asked only `regime, funding_extremes, scheduled_events, fear_greed` and stopped — skipped positioning, own record, similar situations. Fewer questions than old.
**Gap:** engine gate on `done` (checklist coverage), `compute()` tool (W4), event calendar + news (W2/W7), conditional-question prompt pattern.

## 2. Event & chain reasoning — Dev's Fed trade
**100 means:** knows every scheduled event (FOMC/CPI/NFP/unlocks/listings/expiries) with consensus and priced-in score; writes chains event → mechanism → instruments → direction → size → falsifier → checkpoint; every link carries a *measured* response (local projection / event study with n, t) or is tagged unmeasured and capped; chains are graded per link at close; replay of a real FOMC date passes acceptance test T1.
**Rungs:** 0 none · 20 chains written with mechanism + falsifier + checkpoint · 40 + falsifier/checkpoint enforced and graded · 60 + calendar with consensus and priced-in score used · 80 + measured link strengths cap confidence · 100 + T1 passes and per-link grading over ≥30 chains.
**old 8** — chains written (mechanism, falsifier, checkpoint) but nothing enforced or graded; the calendar is unlocks only; no measured links.
**new 12** — chains enforced (2 falsifier exits) and graded ("falsifier day 2 … TRIGGERED", "closed before it could be judged"); still no calendar beyond unlocks, no measured links shown (funding→7d measured in MEASURED_LINKS but not wired), no priced-in score. The chains themselves are shallow: every mechanism this run was "negative funding → squeeze"; no event was connected to anything.
**Gap:** W2 entirely (event store, links engine, `links`/`event_study`/`analogues` tools, confidence cap), then T1.

## 3. Cross-sectional awareness — beta, idiosyncratic, clusters, stress
**100 means:** the agent reasons with beta, R², residual momentum, idio vol, crash-day beta, cluster membership (stable, consensus-clustered), the stressed correlation matrix and PC1 share; hedges or sizes accordingly; the correlation heatmaps and beta map exist and are used; validated by attribution (market vs residual P&L) over ≥60 trades.
**Rungs:** 0 none · 20 layer computed and shown as facts · 40 + strategist references them in mechanisms and the skeptic uses them · 60 + stable clusters used for caps, stressed matrix used in risk · 80 + hedged legs / residual sizing shown in trades and attribution reported · 100 + validated over ≥60 trades.
**old 0** — nothing existed (empty tables).
**new 22** — layer built and written (191,845 rows); strategist saw own_daily_move / btc_share_r2 / beta_crash_days / cluster and quoted "Low BTC share (0.013) isolates the move"; desk uses idio vol, cluster cap, stressed beta. Below 40 because: clusters churn (Jaccard 0.17–0.31), the skeptic never used the facts, no heatmap/map exists, no hedged legs, no attribution.
**Gap:** consensus clustering (D15), viewer pages (W5), attribution (D44), hedged-leg logic.

## 4. Crowd reading — funding, positioning, OI, liquidations
**100 means:** funding, long-share, top-trader share, OI change, liquidation clusters, cross-venue basis/dispersion all read with engine labels; crowding enters sizing and direction through *measured* link strengths (funding→7d: rank-IC −0.027, t −3.8; long-Q1 +101 bps/7d with carry); the funding-cost rule prices every order; validated by the carry sleeve's live result.
**Rungs:** 0 none · 20 funding + positioning read with labels · 40 + funding quintile rule in the desk and OI used · 60 + measured link strength shown and used to cap/size · 80 + liquidations/cross-venue/cascade fragility · 100 + validated live over ≥60 trades.
**old 10** — funding/positioning read; shorted a crowded-short coin (paid 48 bps/week against it); no rule.
**new 24** — engine crowd labels on every funding/positioning result; desk funding-quintile rule; 5/5 orders aligned; OI change not used; measured strength not shown; no liquidation or cross-venue data in the rule.
**Gap:** wire MEASURED_LINKS §4/§4b into the strategist prompt and desk (W2), OI/liquidation features (C33–C36), cross-venue.

## 5. Provenance & anti-hallucination
**100 means:** every fact on a card carries a tool stamp or a verbatim quote + URL + fetch time; every number in a chain matches a stamp within rounding (right-for-wrong-reasons detector); orders with unstamped facts are refused; citation precision/recall measured (ALCE/AIS); the junk test (fakes, flips, instructions) shows flip rate below clean run-to-run noise and 0 obeyed instructions.
**Rungs:** 0 none · 20 cards name a tool · 40 + unstamped cards rejected, numbers checked against tool output · 60 + quotes for text sources and citation P/R measured · 80 + junk test run with scores · 100 + junk test passed at J11 and re-run per wave.
**old 12** — 7/9 cards named a called tool; nothing checked; the exam showed it invents literature details.
**new 16** — 8/9; nothing checked; no quotes (no text sources yet); no junk test.
**Gap:** A14/R14 (reject unstamped), E31 (number matching), N3/N9 (quotes), J1–J12 (junk harness).

## 6. Consistency of beliefs
**100 means:** an explicit belief board (claim, kind, p_model/p_engine/p_final, evidence for/against, falsifier, revision log, Brier); every order cites belief ids; the engine refuses an order that contradicts a live belief; beliefs revised with logged deltas; Brier per kind over ≥100 beliefs.
**Rungs:** 0 none · 20 market view written and orders consistent with it by a reader's judgement · 40 + beliefs stored with p and evidence · 60 + orders cite beliefs and contradictions are blocked · 80 + revisions with surprise-bits brake and Brier scored · 100 + ≥100 resolved beliefs with calibration slope in [0.7, 1.3].
**old 6** — Aug 13 view said "avoid … extreme shorts like C160" and it shorted that coin.
**new 14** — 3/3 decisions consistent with their view by my reading; no mechanism exists, so this is not a capability.
**Gap:** W3 belief board (B1–B47).

## 7. Memory & learning
**100 means:** episodic + semantic + procedural memory (CoALA); a bi-temporal graph with earned links; retrieval = graph walk + k-NN + FTS fused, outside view *first* (GJP's strongest practice: Brier 0.17 vs 0.26); insights earn activation out of sample and compile to skills; reflection triggered by surprise; memory ablation shows a measured loss (the crypto MAS paper: −11.5 pp without memory).
**Rungs:** 0 none · 20 experiences stored with grades and lessons · 40 + evidence/similar/recall consulted every decision (enforced) and lessons carry verdicts · 60 + graph retrieval, analogues, reflections with cited node ids · 80 + active insights compiled to skills, belief revisions · 100 + ablation shows memory adds ≥ X bps over the rule twin.
**old 12** — experiences + lessons; 3/3 decisions used memory tools by choice; 2/4 lessons with verdicts; 0 insights.
**new 14** — 4/4 lessons with verdicts; 1/3 decisions used memory tools — worse; 0 insights; flat tables.
**Gap:** B46 (outside view pre-fetched, enforced), W3 graph, reflection trigger, insight rounds (V3).

## 8. Skeptic
**100 means:** the skeptic attacks the *thesis*: names the card that, if false, breaks it; brings counter-evidence (contradicting similar situations, insights, measured links against); catches contradictions between view and orders; never does arithmetic (engine flags numbers); its verdicts change outcomes, proven by an A/B (skeptic on vs off) over ≥60 trades.
**Rungs:** 0 none · 20 exists, verdicts with reasons · 40 + reasons cite counter-evidence from the dossier, arithmetic removed from its job · 60 + "which card if false breaks this" answered and contradiction catches logged · 80 + A/B shows positive contribution · 100 + validated across regimes.
**old 0** — none.
**new 10** — exists; 5/5 verdicts with a number, none with counter-evidence; all five were stop-width remarks, one of them wrong (ACE: "4.3% = 1.5 daily moves", actually 0.19) because it measured with raw vol — fixed after the run, unverified live. It has never vetoed for a thesis reason in v2.
**Gap:** P8/P9 (thesis-only prompt, engine flags), dossier with measured links and contradicting analogues, A/B (F13).

## 9. Risk desk
**100 means:** code-only desk with the full rule set (vol bands, falsifier geometry, target/hold, cluster caps on stable clusters, book beta band, stress margin under measured crash betas, funding cost, event blackout, stamped-fact check, stale-dossier check, ledger truth, CVaR brake, drawdown breakers, preflight rules); every rule exercised by a live case; rejection rate tracked as a learning metric; validated by the stress scenarios (F16).
**Rungs:** 0 none · 20 desk exists with vol/falsifier/target/hold rules exercised live · 40 + funding, cluster, beta, stress rules exercised live and events/blackout rule present · 60 + stamped-fact/stale/ledger checks, preflight ported, rejection rate tracked · 80 + stress scenarios (a)–(f) passed · 100 + validated over a full year with level ladder.
**old 0** — none.
**new 24** — 9 rules coded, 57 tests; live exercised: hold, stop band, target, falsifier side (single-decision runs) — cluster/beta/stress/funding/CVaR rules only in synthetic tests; no event blackout, no stamped-fact check, no preflight port; bounce loop worked 5/5.
**Gap:** R10, R13–R16, F16, exercise every rule live.

## 10. Sizing
**100 means:** size = quarter-Kelly on a *calibrated* probability × vol target on residual vol × cluster/capacity caps; the probability→size map validated against equal-weight and inverse-vol twins over ≥100 trades (HRP Monte Carlo, meta-labeling literature leaves this open — it must be measured, not assumed).
**Rungs:** 0 flat size · 20 size varies with vol and stated p by formula · 40 + p passes through shrink + calibration with n ≥ 10 per bucket · 60 + twins run and compared · 80 + validated over ≥100 trades · 100 + capacity-aware and stress-consistent.
**old 0** — $100 flat.
**new 12** — $5–$20 by formula (kelly × vol scale); calibration inactive (n<10); p shrink toward own record active with n=1–4 (nearly no effect); no twins.
**Gap:** F8 twins, n, B4/B5.

## 11. Plan quality — stops, targets, holds
**100 means:** the strategist itself proposes stops/targets/holds from residual vol, event timing and liquidity; the desk rarely needs to bounce; stop-out-by-noise rate measured from counterfactuals and low; plans adapt to regime (stress mode assumes crash betas).
**Rungs:** 0 noise stops · 20 desk forces vol bands · 40 + strategist proposes within bands ≥80% of the time · 60 + holds and targets right first time, stops_report used · 80 + event-aware and regime-aware plans · 100 + measured noise-stop rate < 20% over ≥60 trades.
**old 6** — three of five stops at 0.22–0.68 daily moves (ACE, KAITO×2).
**new 28** — all five orders in band *after the desk*; the strategist proposed 3/5 within the stop band but 0/5 with an adequate hold and, on Aug 17, a 0.19-move stop; the desk fixed everything. Two falsifier exits and one stop-out on five trades: noise rate unknown at n=5.
**Gap:** strategist prompt with the hold formula and stops_report, event awareness, measure noise-stop rate.

## 12. Accountability & grading
**100 means:** every chain link graded at close (mechanism held? checkpoint hit? falsifier fired? which link broke?), Brier per belief, a reviewer classifies losses (thesis/timing/risk-plan/regime), lessons feed insight rounds, per-hat attribution in bps, three states tracked (research/declared/executed).
**Rungs:** 0 P&L only · 20 excess vs market + counterfactuals + lesson text · 40 + checkpoint/falsifier verdicts · 60 + mechanism grading and loss classification by a reviewer · 80 + Brier and per-hat attribution · 100 + three-state tracking over a full year.
**old 18** — excess, counterfactuals, lessons; verdicts on 2/4.
**new 30** — verdicts on 4/4 incl. "closed on day N before it could be judged"; no mechanism grading, no reviewer, no Brier, no attribution.
**Gap:** V1–V10 reviewer, B16, R19.

## 13. Outcome vs twins
**100 means:** excess per trade > 0 with bootstrap 90% CI excluding 0 over n ≥ 60, PSR ≥ 0.95, DSR counting every configuration, beats rule / random / equal-weight / inverse-vol / buy-and-hold twins on the same dates, sign-stable across ≥5 of 8 walk-forward blocks, survives the held-out 2026 H2.
**Rungs:** 0 nothing measurable · 20 n ≥ 20 with twins run · 40 excess CI excludes 0 at n ≥ 60 · 60 + PSR/DSR gates · 80 + walk-forward sign stability and ablations · 100 + held-out and prospective 90 days.
**old 2** — 5 trades, −$0.2, +23 bps excess, no twins.
**new 2** — 5 trades, +$7.9 from one ACE trade (+46% in a day), +597 bps excess, hit 20%; no twins. Both are noise.
**Gap:** F1–F35; the full-August and 2025 runs.

## 14. Robustness
**100 means:** junk test passed (J11), every error path exercised live (server down, garbage JSON, empty answers), replay cache byte-identical, 3 seeds, second backbone, schema-constrained output with 0 parse failures over 50+ calls, sign/unit errors at 0 over ≥100 orders, stress scenarios (F16).
**Rungs:** 0 crashes on garbage · 20 tests cover engine/rules; clean runs · 40 + garbage/empty/server-down handled and exercised live; schema-constrained output · 60 + junk test run · 80 + seeds, backbone swap, replay · 100 + stress scenarios passed.
**old 6** — no tests; would have crashed on a garbage order (float() on junk).
**new 18** — 57 tests (engine, memory, layer, desk, bounce loop with garbage/empty replans); 16 audit defects fixed today; but garbage paths never hit live, no schema constraint, no junk test, no seeds/replay; the model still produced sign/unit errors in 3 of today's ~8 single decisions.
**Gap:** M1 (json_schema), J-suite, F27/F31/F32, live error-path evidence.

## 15. Calibration & abstention
**100 means:** stated probabilities map to realised frequencies (slope 0.7–1.3, ≥100 resolved beliefs), granular (0.05 steps), revised at checkpoints; abstains where the outside view and market price agree or base-rate n < 8 (Halawi's selective regime) and *does not* abstain when a call is warranted (the exam's Fed-scenario "no edge" reflex); median-of-3 for the number.
**Rungs:** 0 no confidences · 20 confidences stated and stored · 40 + calibration table active (n ≥ 10/bucket) and used in sizing · 60 + median-of-3 and abstention rule with logged reasons · 80 + slope in range over ≥50 beliefs · 100 + over ≥100 across regimes.
**old 4** — stated 0.57 mean vs 40% hit (n=5).
**new 4** — stated 0.64 mean vs 20% hit (n=5); calibration inactive; no abstention logic (it never returned "no trade" in 3 decisions; the exam showed it over-abstains on hard questions and under-abstains on trades).
**Gap:** B3–B5, B12, B18, B44; n.

---

## Ranking of where to work, by (gap × how much other categories depend on it)
1. **Event & chain reasoning (2)** — the calendar and measured links unlock 4, 5, 8, 11 and Dev's acceptance test. Score 12.
2. **Information gathering (1) + Memory (7)** — one fix (engine-enforced checklist and outside-view pre-fetch) lifts both from ~13 to the 40 rung.
3. **Provenance (5)** — reject unstamped cards, match numbers to stamps; it is cheap and removes a whole class of hallucination.
4. **Skeptic (8)** — make it thesis-only with counter-evidence; verify live.
5. **Beliefs (6)** — W3.
6. **Risk desk (9) / Sizing (10) / Plan (11)** — exercise every rule live; twins.
7. **Outcome / Calibration / Robustness (13, 15, 14)** — need n: the full-August run and a 2025 year, plus the junk harness.

Nothing in this table is verified beyond what the quoted logs show; the scores are my strict reading of those logs against the rungs above.
