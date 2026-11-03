# POC-0 Classical Scientific Baselines

**SYNTHETIC ONLY — NO META API / REAL-WORLD VALIDATION**

Protocol seed: `20261031`. Acceptance checks: **PASS**.

Reproduce: `python scripts/verify_baselines.py` (install with `python -m pip install -e ".[dev]"`).

## Measured baseline results

Each case uses two exploration training releases and one disjoint development release. These development trials are ordinary synthetic checks, **not sealed validation**. Scores below are on the unseen whole trial. B2 does not predict time trajectories; its radial reconstruction RMSE is a different statistic.

| Case | B0 xy RMSE (px) | B1 xy RMSE (px) | B1 excess NRMSE | B2 result | B2 radial RMSE (px) | Peg error after fit (mm) |
|---|---:|---:|---:|---|---:|---:|
| no_fault | 0.7204 | 0.7215 | 0.0003 | one_circle_only | 0.5097 | unavailable |
| parameter_fault | 40.7895 | 0.6891 | 0.0000 | one_circle_only | 0.4862 | unavailable |
| vertical_peg | 72.2366 | 39.7647 | 0.0920 | two_circle | 0.4881 | 2.4936 |
| off_vertical_peg | 40.2429 | 22.8766 | 0.0529 | two_circle | 0.5240 | 16.7712 |
| unexcited_peg | 0.6975 | 0.6968 | 0.0000 | one_circle_only | 0.5133 | unavailable |
| short_arc | 0.6752 | 0.6774 | 0.0000 | ambiguous | unavailable | unavailable |

## Conditions, algorithms and units

- All observations are simulated. Duration 4 s; full grid 60 Hz; known scale 600 px/m; image pivot (640,160) px. Plane x right/y up, image x right/y down. Gravity 9.80665 m/s².
- IID Gaussian localization noise has marginal covariance diag(0.25,0.25) px² (0.5 px SD per coordinate). Off-vertical trials drop 10% of samples independently; invalid rows remain NaN and are excluded. AR(1) generation and gap-aware whitening are unit-tested; this report uses phi=0. None of these noise levels was measured from a phone or SAM.
- Nominal B0: L=0.72 m, gamma=0.06 s⁻¹, quadratic drag=0.02 m⁻¹. Release angle, release velocity=0 and release time=0 are prescribed and known. Projection, gravity and initial conditions are not inferred from the test trial.
- B1: shared L, gamma and quadratic drag fitted to both training trials with eight deterministic starts, bounded SciPy TRF least-squares and soft-L1 loss. L uses log coordinates; nonnegative drag coefficients use direct coordinates to include exact zero. Bounds: L [0.4,1.1] m; gamma [0,0.6] s⁻¹; quadratic drag [0,0.6] m⁻¹. No tape prior is invented. Loss scale=max(1,1.4826*MAD) on whitened nominal training residuals. Every start, cost, bound hit, warning and failure appears in JSON.
- Each B0/B1 prediction is one complete simulator rollout from release, with no resets to observations. Whitening uses spatial Cholesky covariance and phi^(sample-index gap) AR innovations. NRMSE divides Euclidean xy RMS by nominal length in pixels. The floor is the **assumed synthetic** trace(covariance), not a repeat-estimated real noise floor. Excess NRMSE subtracts that expectation before taking a square root.
- B2: known original pivot, free first radius; search a polar-bearing boundary and either side; fit a free second center/radius with algebraic initialization followed by robust geometric least-squares. No hidden mode, event time or peg coordinate enters fitting. Short arcs fail minimum sample, span and noise-relative sagitta checks. Candidate geometry is compared by leave-one-whole-training-trial-out CV and a fixed conservative search/complexity penalty. The rule is a design diagnostic, not a null-calibrated p-value or a G3 decision gate. JSON gives both CV scores and penalty.
- B2 uses observed bearing to assign a point to an arc. This is an observation-conditioned distance-to-geometry evaluation; it must not be compared numerically as a trajectory-prediction win over B1.

## Fitted parameters and residual diagnostics

| Case | L (m) | gamma (s⁻¹) | quadratic drag (m⁻¹) | B1 train xy RMSE (px) | Held-out innovation mean square / coordinate | Held-out lag-1 x |
|---|---:|---:|---:|---:|---:|---:|
| no_fault | 0.7200 | 0.0605 | 0.0195 | 0.7059 | 1.0412 | 0.0212 |
| parameter_fault | 0.7600 | 0.1094 | 0.0503 | 0.7160 | 0.9496 | 0.0230 |
| vertical_peg | 0.6711 | 0.0000 | 0.1494 | 39.6618 | 3162.4602 | 0.9978 |
| off_vertical_peg | 0.6935 | 0.0000 | 0.1112 | 23.9088 | 1046.6820 | 0.9971 |
| unexcited_peg | 0.7200 | 0.0632 | 0.0149 | 0.7233 | 0.9711 | -0.0366 |
| short_arc | 0.7201 | 0.0567 | 0.0000 | 0.6847 | 0.9178 | -0.1083 |

## Negative controls, failures and limitations

- PASS: B1 solver converged on every attempted case
- PASS: no_fault: B1 held-out xy RMSE < 1.2 px
- PASS: no_fault: fitted L within 2 mm
- PASS: no_fault: no spurious second pivot
- PASS: parameter_fault: B1 held-out xy RMSE < 1.2 px
- PASS: parameter_fault: fitted L within 2 mm
- PASS: parameter_fault: no spurious second pivot
- PASS: vertical_peg: B1 leaves >8 px held-out discrepancy
- PASS: vertical_peg: B2 supports second circle with <20 mm post-fit peg error
- PASS: off_vertical_peg: B1 leaves >8 px held-out discrepancy
- PASS: off_vertical_peg: B2 supports second circle with <20 mm post-fit peg error
- PASS: unexcited peg has no contact or invented second pivot
- PASS: short noisy arcs produce an explicit ambiguous geometry result
- `no_fault` B2: no supported second pivot; unexcited mechanisms remain possible. Rejected candidate fits: 30.
- `parameter_fault` B2: no supported second pivot; unexcited mechanisms remain possible. Rejected candidate fits: 29.
- `vertical_peg` B2: two recurring arcs improve whole-trial CV beyond the design penalty. Rejected candidate fits: 32.
  B1: best fit is at or near physical bounds; no unconstrained parameter/CI claim.
- `off_vertical_peg` B2: two recurring arcs improve whole-trial CV beyond the design penalty. Rejected candidate fits: 31.
  B1: best fit is at or near physical bounds; no unconstrained parameter/CI claim.
- `unexcited_peg` B2: no supported second pivot; unexcited mechanisms remain possible. Rejected candidate fits: 99.
- `short_arc` B2: degenerate short arc: curvature below localization uncertainty. Rejected candidate fits: 0.
  B1: best fit is at or near physical bounds; no unconstrained parameter/CI claim.

A single observed circle cannot distinguish an absent peg from an unexcited peg. The short-arc case intentionally abstains geometrically. Peg cases leave systematic fixed-structure residuals; B2 localizes a second center but does not identify a unique causal mechanism.

This small fixed-seed matrix is not an MDE/power study, false-positive calibration, CI-coverage experiment or real-world benchmark. No 300-trial coverage claim, bootstrap CI, SAM result, Muse result, sealed evaluation, structural dynamics fit or repair is claimed. B2 assumes one recurring bearing boundary and a known pivot/projection; arbitrary partial occlusion, multiple pegs, outliers, camera errors and correlated radial likelihood calibration remain limitations. B1 checks solver convergence/rank and reports bounds, but provides no calibrated parameter CIs.

## Provenance and phase readiness

Observations are exported separately to `poc0_observations.npz`, with public metadata and per-trial SHA-256 fingerprints in JSON. Synthetic truth is written to `poc0_truth_evaluation.json` only for post-fit evaluation. Inference packages have no truth imports or file reads; tests also run fitting in a subprocess denying synthetic imports. This is a dependency/input boundary, not the future OS-enforced sealed vault.

Source SHA-256: `5002cbf821202321b378a7f59a4f9e9f5843337733e7c3a724c905a7b02984c2`.

Environment: `{"matplotlib": "3.11.2", "numpy": "2.5.4", "python": "3.14.4", "scipy": "1.18.1"}`.

G1 physics source is unchanged. Phase 1 acceptance is checked here; G2 and full G3 are **not passed**. Next: actual Meta access/structured-tool smoke tests, separate SAM MP4 tracking, PTS extraction, stationary and dynamic noise measurement, camera calibration and real recording QA (Phase 2). Real media and account access remain external blockers.

Method reference: [SciPy least_squares documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html).

![Synthetic held-out observations and model predictions](poc0_baselines.png)
