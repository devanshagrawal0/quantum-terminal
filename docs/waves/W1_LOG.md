# Wave 1 verification log — cross-sectional layer + risk hat + crowd labels + selftest
2026-09-16. Spec: docs/AGENT_V2_BUILD_SPEC_2026-09-16.md §3 W1. Rule 7: every touched function re-read and re-run ≥10 times with fresh inputs across the wave; passes are numbered here.

## Files touched
- `sim/xsec.py` (new, 250 lines) — beta/residual/idio/corr/stress/clusters/universe series; writes `feat_cross` (191,845 rows).
- `sim/risk.py` (new, 250 lines) — RiskHat: 9 rules, sizing, brakes, one bounce round.
- `sim/data.py` — `_cached` now stamps the data vintage and rebuilds when the store has newer candles; feature cache key made stable (md5) — bug: `hash()` was randomised per process, 12 duplicate 18 MB caches existed and no run ever hit the cache.
- `sim/investigator.py` — `chain_point()` at module level; `_xsec_facts()`; candidate rows carry own_daily_move_pct / btc_share_r2 / beta_crash_days / cluster; strategist told the risk bands; `_risk_pass()` with one replan round (units converted for the model); skeptic dossier gets `btc_relationship`.
- `sim/tools.py` — `crowd_label()`; funding results carry it; `funding_extremes` carries the convention line.
- `sim/memory.py` — Thompson sd floored at 100 bps (identical outcomes silenced a setup completely).
- `sim/run.py` — risk hat wired for LLM agents; `data.xsec` attached in single and batch modes; `risk` logged in decisions.jsonl.
- `scripts/selftest.py` (new) — 41 tests (X engine/memory 22, D layer 9, R risk 10).

## Passes
| pass | what | inputs | result |
|---|---|---|---|
| 1 | first build of xsec | full closes | ran; universe series printed; found: stress matrix on raw vs normal on residual (inconsistent) → added raw matrices |
| 2 | Ledoit–Wolf ρ term | derivation re-check | bug: diagonal θ terms included → excluded (`off` matrix) |
| 3 | selftest first run | synthetic + real | 32/41: 6 test-input errors (hold rule), similar() needs ≥5 records (by design), sample() signature, regime ramp 2.997% |
| 4 | selftest after fixes | same | 40/41; X19 showed 6 identical losses silence a setup → sd floor 100 bps; test rewritten to the design claim (one loss keeps 25–60% positive draws) |
| 5 | selftest | same | 41/41 |
| 6 | risk.py line-by-line | — | stress-loss total used pre-sizing notional → sized; Vasicek τ² from plain variance → MAD; stressed beta ignored NaN days in denominator → masked means |
| 7 | xsec rebuild v2 + D/R tests | full closes | 20/20 |
| 8 | layer sanity table | latest day | betas: median 1.13, crash-day 1.27; ACE −0.68 raw → 0.99 shrunk (SE huge), idio 22.7%/day; **clusters: 156/172 in one blob** (average linkage) |
| 9 | clustering methods compared | resid/raw × average/complete/ward × k=6/8 | Ward k=8 balanced (51/26/22/17/16/16/12/11) with recognisable groups → adopted; **month-to-month Jaccard stability median 0.25** — clusters churn; consensus clustering over overlapping windows (spec D15 full) is the follow-up; the cluster cap is a coarse control until then |
| 10 | xsec v3 + D tests | full closes | 9/9; D15 tightened (no cluster > 50% of universe) |
| 11 | investigator `_risk_pass` re-read | — | replan prompt showed falsifier in percent while asking for fractions → converted; dropped list missed round-2 rejects → fixed |
| 12 | live decision 2026-08-13 with all four hats | model | see below |

## Known limits carried forward
- Hourly candles in `store.db` end 2026-08-31 (Binance archive monthly zips) — spec X61, W7 blocker.
- Cluster stability low (0.17–0.31); risk cluster cap is coarse.
- `feat_cross.beta_eth` not computed yet (D4 TODO).
- Live decision ran on xsec v1 numbers (cache renamed mid-run); next run uses v3.
