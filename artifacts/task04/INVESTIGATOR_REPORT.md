# First executable investigator evidence

**SYNTHETIC ONLY. Deterministic and mock results are separate from live Muse.**

| Case | Deterministic outcome | Mock outcome | Experiments | Post-freeze prediction RMS px |
|---|---|---|---:|---:|
| no_fault | KEEP_UNCHANGED | KEEP_UNCHANGED | 1 | 0.70127 |
| parameter_mismatch | CALIBRATE_PARAMETERS | CALIBRATE_PARAMETERS | 1 | 0.71410 |
| vertical_peg | REPAIR_STRUCTURE | REPAIR_STRUCTURE | 1 | 0.68557 |
| off_vertical_peg | REPAIR_STRUCTURE | REPAIR_STRUCTURE | 1 | 0.81961 |
| unexcited_peg | ABSTAIN | ABSTAIN | 1 | unavailable |
| measurement_problem | CORRECT_MEASUREMENT | CORRECT_MEASUREMENT | 1 | unavailable |
| insufficient | ABSTAIN | ABSTAIN | 0 | unavailable |

## Scientific acceptance and ambiguity

Null calibration: 20 predeclared independent synthetic datasets, two noise levels and no-fault/parameter-fault strata. Target false repair rate 0.05. Threshold 0.0.
Independent validation: 0/8 false repairs; specificity 1.0000, 95% Clopper-Pearson interval [0.6305833524471807, 1.0].
Sensitivity 1.0000 on 4 excited-peg cases, 95% interval [0.3976353643835253, 1.0]; abstentions 1; failed runs 0.

The empirical tail rank uses (1 + number of null statistics unavailable or at least as large)/(N + 1). The threshold is the maximum of all 20 null replicate scores, floored at zero. Unavailable null fits count as worst-case exceedances; at N=20, any such failure blocks 5% repair acceptance. One formal test is permitted only after the registered four-trial design (0.2, 0.32, 0.65, 0.65 rad; 1.6 s; 20 Hz; IID assumed SD 0.5 or 1.5 px). The statistic is the minimum of the two whole-trial-fold improvements normalized by localization MSE floor. Off-protocol designs, missing data, other noise models and real observations remain uncalibrated.

The 5% figure is a predefined pilot target, not a proven uniform false-repair guarantee. Twenty calibration datasets and a small validation set provide limited tail/power evidence. Calibration null parameter mismatches cover a finite grid; the 0.76 m benchmark is an additional stress case. The wide validation intervals must not be hidden.

KEEP_UNCHANGED means predictive adequacy inside the tested operating envelope. It does not rule out an inactive peg or another observationally equivalent mechanism. The limited-angle unexcited case cannot cover the operating envelope and abstains. REPAIR_STRUCTURE accepts the existing predefined peg model for prediction; it is not open-ended equation discovery or proof of causal uniqueness. All causal-identification flags remain false. Independent geometry/interventions and full G2/G3 are pending.

## Experiment planning

Release, repeat, stationary-reference and camera-calibration actions form a closed discriminated union. Only allowlisted bounded candidates can be requested. Physical execution here is a synthetic replay environment, not a robot or a live rig. Release/repeat score is the 75th percentile of noise-normalized trajectory separation over near-optimal multistart parameter alternatives. The reported ensemble interquartile spread is a heuristic uncertainty diagnostic, not a calibrated posterior. Every sampled candidate must integrate without unsupported dynamics. Reference checks use fixed, declared quality-trigger priorities. Expected information gain remains null; no Bayesian information gains are fabricated.

## Matched comparison and Meta status

Both offline arms receive the same observations, candidate catalog, numerical tools and logical budgets. The mock adapter uses the deterministic policy through the production interface to verify plumbing. Matching mock outcomes are not evidence that Muse reasons successfully or outperforms a planner. Each trace records requested/completed experiments, fit jobs, tool calls and post-freeze prediction error. API latency, token use and monetary cost remain unavailable for offline arms; token prices are not guessed.

Live investigator status: NOT_RUN. No end-to-end live Muse investigation is claimed. A preexisting capability report, if present, is recorded separately with its hash and scope. It does not validate the expanded agent schemas or full investigation.

## Checks

- PASS: all seven deterministic investigations complete
- PASS: all seven mock investigations complete
- PASS: off-vertical investigation actually requests and receives a second round
- PASS: state/evidence replay reproduces the frozen numerical decision
- PASS: mock and deterministic policies have matched frozen outcomes
- PASS: no false structural repairs in independent null validation
- PASS: at least one supported predefined structural selection
- PASS: measurement problem yields a measurement action
- PASS: limited/insufficient evidence does not force structural repair

Source/numerical signature: 2617cb0ce5a5c91d9382bb87233bc69d6f1095246a931103ea247437169c4855.
Reproduce with python scripts/verify_investigator.py --calibrate. Exact traces, all failed fits, calibration restarts and post-freeze validation records accompany the report.
