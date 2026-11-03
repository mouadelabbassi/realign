# B3 structural dynamics evidence

**SYNTHETIC ONLY - NO LIVE META OR REAL DYNAMICS VALIDATION**

Reproduce: python scripts/verify_structural.py. Seed: 20261101.

Two exploration releases; five disjoint development releases per case. All candidate structures, bounds, starts, controls, noise levels and splits are fixed in code before scoring. Leave-one-exploration-trial-out refits are reported separately. Development data never choose parameters or structures.

| Case | B0 trajectory RMS px | B1 trajectory RMS px | B3 trajectory RMS px | B2 radial RMS px (different statistic) | B3 local rank |
|---|---:|---:|---:|---:|---:|
| no_fault | 0.7223 | 0.7205 | 0.7237 | 0.5028 | 5 |
| parameter_fault | 34.7483 | 0.7193 | 0.7186 | 0.5114 | 5 |
| vertical_peg | 44.6278 | 32.7778 | 0.6803 | 0.4886 | 5 |
| off_vertical_peg | 25.8028 | 19.5778 | 0.7071 | 0.5042 | 5 |
| unexcited_peg | 0.6941 | 0.6979 | 0.6979 | 0.4886 | 3 |
| noisy_peg | 25.8065 | 19.6906 | 3.6643 | 3.1443 | 5 |
| short_arc | 0.7008 | 0.7052 | failed/unavailable | failed/unavailable | failed |
| insufficient_data | 0.6265 | failed/unavailable | failed/unavailable | failed/unavailable | failed |

B2 radial reconstruction is conditioned on each observed point; it is never ranked against a trajectory prediction.

| Case | Mean B1 minus B3 trial MSE px² | Paired whole-trial bootstrap 95% interval | Prediction disagreement RMS px |
|---|---:|---|---:|
| no_fault | -0.0047 | [-0.010881672756211325, -0.0006671394925487628] | 0.0494 |
| parameter_fault | 0.0010 | [-0.00022401326631431572, 0.0023350503648099873] | 0.0199 |
| vertical_peg | 1073.9199 | [939.840697958801, 1207.5447654455559] | 32.7220 |
| off_vertical_peg | 379.4623 | [274.0008835479492, 489.8155052350806] | 19.5588 |
| unexcited_peg | 0.0000 | [1.7876876250433328e-07, 1.7208190651318844e-06] | 0.0000 |
| noisy_peg | 375.8957 | [268.54243383426217, 477.64104274254527] | 19.5638 |

## Algorithms and uncertainty

- B0/B1/B2 implementations are preserved. B1 and B3 fit the same L, viscous drag and quadratic drag. B3 additionally fits peg distance fraction and angle, for a declared wrap side and ideal lossless contact.
- B3: eight deterministic starts, bounded TRF soft-L1 least squares, complete directed-event G1 rollouts. The common robust scale is computed from nominal exploration residual MAD. Observation-only B2 geometry initializes one start; remaining starts cover the permitted peg geometry. No modes, event times or hidden parameters enter fitting.
- Bounds: L [0.4,1.1] m, gamma and quadratic [0,0.6] in s^-1 and m^-1, peg distance/L [0.005,0.55], peg angle [-0.9,0.9] rad intersected with the declared free-side training controls. Maximum 60 solver evaluations and 420 residual calls per start, including numerical finite differences. Preprocessing has a fixed 50-candidate geometry search; final sensitivity adds ten residual evaluations. A domain/slack/event failure aborts that start and is recorded; budget exhaustion is not convergence.
- Local uncertainty uses an independent central-difference whitened-residual Jacobian scaled by search ranges. A relative singular-value cutoff of 1e-5 flags numerical rank deficiency. Conditional Gaussian standard deviations are emitted only at interior full-rank fits; these ignore model misspecification and are not coverage-validated CIs. Near-optimal multistart spread is a diagnostic, not a posterior or profile likelihood.
- Synthetic projection is known (600 px/m). Requested sampling rate is 25 Hz. The preserved adapter rounds duration times rate: 63 timestamps over 2.5 s give an actual 24.8 Hz grid; the insufficient case has 9 timestamps over 0.3 s (26.6667 Hz). Actual timestamps drive every rollout. Release controls/time are prescribed, not fitted from hidden truth. Ordinary covariance is diag(0.25,0.25) px²; noisy case diag(6.25,6.25) px² with AR(1) phi=0.35 and 15% dropouts. These are assumed noise models, not measured SAM accuracy. JSON contains exact trials, hashes, fit failures and CV folds.
- The 2000-resample paired bootstrap resamples five whole development trials, conditional on the exploration fit. It does not integrate training-fit variability. This small design is descriptive; a positive interval is not a calibrated structural-repair test.

## Acceptance checks

- PASS: no_fault: B1 explains observations at the assumed floor
- PASS: parameter_fault: B1 explains observations at the assumed floor
- PASS: vertical_peg: full held-out B3 trajectory improves over B1
- PASS: off_vertical_peg: full held-out B3 trajectory improves over B1
- PASS: unexcited_peg: B1 explains observations at the assumed floor
- PASS: unexcited peg: no mechanism identification claimed
- PASS: noisy_peg: full held-out B3 trajectory improves over B1
- PASS: short_arc: B3 explicitly rejects insufficient evidence
- PASS: insufficient_data: B3 explicitly rejects insufficient evidence

## Limits and pending evidence

No structural decision or discovery is claimed. An unexcited peg can be observationally equivalent to the free model; small prediction differences at the assumed noise floor do not establish different mechanisms. Short arcs and insufficient data explicitly fail the B3 excitation/sample gate. A locally full-rank fit is not global or causal identification.

The full Architecture v1.1 B3 selection gate still requires Monte Carlo null calibration, broader seed/effect/noise sweeps, CI coverage/power, profile uncertainty, and peg-removal interventions. No uncalibrated threshold is promoted to REPAIR_STRUCTURE. Fixed library comparison is classical model fitting, with no claim about Muse value.

Real phone G2, live SAM, live Muse structured outputs/tool calling, metric external-video dynamics and sealed evaluation are NOT demonstrated here. The separately ingested external slow-motion clip has no verified physical time scale or measured camera calibration.

![Synthetic held-out trajectory comparison](b3_trajectories.png)

Source SHA-256: 40a9e50b49e191760779071a3404e3e9232a1586709a5996a69cb666b2fc367d. Environment: {"numpy": "2.5.4", "python": "3.14.4", "scipy": "1.18.1"}.
