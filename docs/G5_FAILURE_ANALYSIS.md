# G5-v1 randomized failure: descriptive post-mortem

**POST_MORTEM. Original acceptance result remains SYNTHETIC_VALIDATION_FAIL.**
This report reads the revealed result and archived exploration-fit diagnostics.
It does not refit, predict with another candidate, rescore the consumed heldout,
change thresholds, or run another experiment. No estimator is changed.

The randomized case predicted its 99 held-out samples at 0.7519408442222819 px
Euclidean RMS (registered limit 2 px), but peg-position error was
0.014477706074618239 m (registered limit 0.01 m). The separate fixed control
passed with 0.6930905745225341 px RMS and 0.0056025527215726005 m peg error.
Neither result is physical validation, causal identification, or a reliability
study. Both commitments, original thresholds, heldouts and verdicts are retained.

The randomized frozen exploration fit reports local numerical rank 5, condition
number 300.7785472588139 and scaled singular values
4078.6139058744916, 1028.8774885132316, 583.7644173847667,
65.91405742250103 and 13.560188860028394. Its weakest scaled direction is mainly
peg-fraction/angle. The archived conditional local Gaussian standard deviations
include **0.01851172342969823 m** for peg distance and
**0.018319061195347045 rad** for peg angle. These are local linear sensitivity
diagnostics under the assumed noise model, not calibrated coverage guarantees.
Full rank is therefore compatible with insufficient precision at the 10 mm
scale. The tiny spread among converged multistart solutions establishes optimizer
repeatability in those starts; it is not a geometry confidence interval.

**Classification: UNDETERMINED.** These diagnostics are consistent with weak
geometry precision relative to the registered tolerance. They do not separate
finite-noise sensitivity, model/estimator assumptions, nonlinear/global ambiguity
and an implementation defect. No verified source defect has been demonstrated.
A defensible profile study would use allowed exploration data and a declared
objective; it must not refit or score new candidates against the consumed heldout.
No such profile was run for this P0 release. The product reports
`profile_uncertainty_range=NOT_RUN`, `credible_interval=NOT_AVAILABLE` and
withholds a precise-geometry claim. It does not invent a posterior interval.

The optional fresh pre-registered ensemble is not a release blocker and was not
run. Any later estimator study must register fresh disjoint cases before running
and publish every outcome beside G5-v1, never in place of it. A local custodian
ledger is not independent external timestamp attestation or proof against an
administrator replacing an entire vault.

Sources: [original randomized result](../artifacts/task06/g5_demo/validation.json),
[archived exploration fit](../artifacts/task06/g5_demo/investigation.json),
[fixed control](../artifacts/task06/g5_positive_control/validation.json).
`python scripts/prepare_release.py` exports these archived diagnostics into the
public evidence summary with zero fitting, prediction, evaluation or Meta calls.
