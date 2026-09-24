| # | category | smallv2 | b1 | b2 | b3 |
|---|---|---|---|---|---|
| 1 | Information gathering | 0 (rung 0) | 60 (rung 60) | 20 (rung 20) | 65 (rung 60) |
| 2 | Event & chain reasoning | 25 (rung 20) | 63 (rung 60) | 63 (rung 60) | 63 (rung 60) |
| 3 | Cross-sectional awareness | 40 (rung 40) | 40 (rung 40) | 40 (rung 40) | 40 (rung 40) |
| 4 | Crowd reading | 40 (rung 40) | 60 (rung 60) | 60 (rung 60) | 60 (rung 60) |
| 5 | Provenance & anti-hallucination | 20 (rung 20) | 20 (rung 20) | 20 (rung 20) | 20 (rung 20) |
| 6 | Consistency of beliefs | 20 (rung 20) | 20 (rung 20) | 20 (rung 20) | 20 (rung 20) |
| 7 | Memory & learning | 0 (rung 0) | 40 (rung 40) | 25 (rung 20) | 40 (rung 40) |
| 8 | Skeptic | 20 (rung 20) | 20 (rung 20) | 20 (rung 20) | 20 (rung 20) |
| 9 | Risk desk | 25 (rung 20) | 40 (rung 40) | 40 (rung 40) | 40 (rung 40) |
| 10 | Sizing | 20 (rung 20) | 20 (rung 20) | 20 (rung 20) | 5 (rung 0) |
| 11 | Plan quality | 40 (rung 40) | 20 (rung 20) | 45 (rung 40) | 20 (rung 20) |
| 12 | Accountability & grading | 0 (rung 0) | 40 (rung 40) | 40 (rung 40) | 40 (rung 40) |
| 13 | Outcome vs twins | 0 (rung 0) | 0 (rung 0) | 0 (rung 0) | 0 (rung 0) |
| 14 | Robustness | 20 (rung 20) | 20 (rung 20) | 20 (rung 20) | 20 (rung 20) |
| 15 | Calibration & abstention | 20 (rung 20) | 20 (rung 20) | 20 (rung 20) | 20 (rung 20) |
| | **mean** | **19.3** | **32.2** | **30.2** | **31.5** |

## First unmet condition of the next rung

### smallv2
- 1. Information gathering: mean checklist items >= 6
- 2. Event & chain reasoning: >=80% lessons carry verdicts
- 3. Cross-sectional awareness: trades carry attribution
- 4. Crowd reading: links_shown logged
- 5. Provenance & anti-hallucination: 100% cited and rejects logged
- 6. Consistency of beliefs: belief rows >= decisions
- 7. Memory & learning: >=80% closed trades have an experience row
- 8. Skeptic: >=50% verdicts carry basis
- 9. Risk desk: event_blackout in checks
- 10. Sizing: calibration bucket applied on >=50%
- 11. Plan quality: bounce rate <= 20%
- 12. Accountability & grading: 100% lessons carry excess and counterfactuals
- 13. Outcome vs twins: n >= 20
- 14. Robustness: json_schema on 100% calls
- 15. Calibration & abstention: calibration bucket used on >=50% verdicts

### b1
- 1. Information gathering: compute() >=1 per decision
- 2. Event & chain reasoning: admitted link exists
- 3. Cross-sectional awareness: trades carry attribution
- 4. Crowd reading: liquidation/cross-venue in >=50% dossiers
- 5. Provenance & anti-hallucination: 100% cited and rejects logged
- 6. Consistency of beliefs: belief rows >= decisions
- 7. Memory & learning: node/edge tables
- 8. Skeptic: >=50% verdicts carry basis
- 9. Risk desk: stamped/fresh/ledger/preflight checks
- 10. Sizing: calibration bucket applied on >=50%
- 11. Plan quality: >=80% first-time-right on stop/target
- 12. Accountability & grading: loss_class on losses
- 13. Outcome vs twins: n >= 20
- 14. Robustness: json_schema on 100% calls
- 15. Calibration & abstention: calibration bucket used on >=50% verdicts

### b2
- 1. Information gathering: 8/8 items in every decision
- 2. Event & chain reasoning: admitted link exists
- 3. Cross-sectional awareness: trades carry attribution
- 4. Crowd reading: liquidation/cross-venue in >=50% dossiers
- 5. Provenance & anti-hallucination: 100% cited and rejects logged
- 6. Consistency of beliefs: belief rows >= decisions
- 7. Memory & learning: memory consulted in >=90% decisions
- 8. Skeptic: >=50% verdicts carry basis
- 9. Risk desk: stamped/fresh/ledger/preflight checks
- 10. Sizing: calibration bucket applied on >=50%
- 11. Plan quality: stops_report in >=50% decisions
- 12. Accountability & grading: loss_class on losses
- 13. Outcome vs twins: n >= 20
- 14. Robustness: json_schema on 100% calls
- 15. Calibration & abstention: calibration bucket used on >=50% verdicts

### b3
- 1. Information gathering: compute() >=1 per decision
- 2. Event & chain reasoning: admitted link exists
- 3. Cross-sectional awareness: trades carry attribution
- 4. Crowd reading: liquidation/cross-venue in >=50% dossiers
- 5. Provenance & anti-hallucination: 100% cited and rejects logged
- 6. Consistency of beliefs: belief rows >= decisions
- 7. Memory & learning: node/edge tables
- 8. Skeptic: >=50% verdicts carry basis
- 9. Risk desk: stamped/fresh/ledger/preflight checks
- 10. Sizing: >=2 distinct notionals
- 11. Plan quality: >=80% first-time-right on stop/target
- 12. Accountability & grading: loss_class on losses
- 13. Outcome vs twins: n >= 20
- 14. Robustness: json_schema on 100% calls
- 15. Calibration & abstention: calibration bucket used on >=50% verdicts
