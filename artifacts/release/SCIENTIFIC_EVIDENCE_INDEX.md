# Scientific evidence index

Evidence branches are separate; overall claim ceiling is C3a.

| Evidence | Inspect | Interpretation |
|---|---|---|
| Original numerical physics/baselines | [G1](../G1_REPORT.md), [B0/B1/B2](../POC0_BASELINES.md), [B3](../B3_BASELINES.md) | Synthetic numerical verification only |
| Reproduced numerical reports | [Reproduced benchmarks](reproduced/) | Same registered benchmark protocols at the tested release source; not new physical validation |
| Actual Muse/SAM | meta_evidence_index.md | Original Task05 operations; no new API test |
| Fixed G5 control | ../task06/g5_positive_control/validation.json | Synthetic PASS, 0.6930905745225341 px, 5.602553 mm peg error |
| Randomized G5 | ../task06/g5_demo/validation.json | Synthetic FAIL, 0.7519408442222819 px, 14.477706 mm vs 10 mm |
| Geometry sensitivity | ../../docs/G5_FAILURE_ANALYSIS.md | Archived descriptive diagnostics; cause UNDETERMINED, no credible interval |
| Independent review | manual_review/measurement_validation.json | NOT_VALIDATED; forty clean frames await genuine human references |
| Software validation | RELEASE_STATUS.json and validation/ | Exact source SHA, commands, tests and documented CI exception |
| Physical and submission gates | ../../docs/SUBMISSION_CHECKLIST.md | BLOCKED_INPUTS / UNVERIFIED; owner action required |

No consumed G5 holdout was used for new fitting, candidate scoring or acceptance.
Public post-reveal reproduction retains each original frozen model and verdict.
