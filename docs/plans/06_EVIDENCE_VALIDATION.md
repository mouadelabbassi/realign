# REALIGN — EVIDENCE VALIDATION PLAN: EVIDENCE CLOSURE AND INDEPENDENT VALIDATION

Repository: https://github.com/mouadelabbassi/realign

Architecture v1.1 is frozen. Task 05 delivered the working five-view product, successful live Muse investigation over synthetic observations, actual SAM processing of licensed external footage, authenticated audit replay and verified offline tests.

Your objective now is to close the scientific evidence gap—not add new architectural complexity.

## Phase A — Inspect and preserve

Read AGENTS.md, TASK05_READINESS.md, TASK05_IMPLEMENTATION.md, REAL_DATA_COLLECTION_PROTOCOL.md, the current product/investigator implementation and the live Meta verification reports.

Check the latest GitHub CI results. Fix confirmed regressions.

Preserve validated G1–B3 numerical behavior, the live Muse traces, the original SAM receipts, the synthetic null calibration and the five-view application.

## Phase B — Independent SAM measurement validation

Implement a simple manual annotation and review workflow for the existing REAL_EXTERNAL footage.

Use the 20 exported clean reference frames. Support the user's independent bob-center annotations, annotation uncertainty, frame indices and original video hashes.

Compute:
- Euclidean localization RMSE.
- Systematic horizontal and vertical bias.
- Median and 95th-percentile localization error.
- Tracking acceptance and rejection by time interval.
- Errors near motion reversals, occlusions and apparent contact events.

Never generate reference annotations from SAM's own predicted centers.

If annotations are missing, preserve NOT_VALIDATED. Do not manufacture accuracy values.

## Phase C — Connect real observations to investigation

Implement an end-to-end orchestration entrypoint using the existing real video pipeline, calibration, observation contracts, scientific tools, investigator runtime and evidence exporter.

The workflow must support:

REAL_PHONE recordings → actual SAM observations → calibrated trajectories → B0/B1/B2/B3 comparisons → bounded investigator → frozen model decision → separate evaluation report.

Do not reuse the synthetic environment as if it were a real physical experiment.

For an agent-requested physical experiment, return a structured pending action and accept the resulting new recording only after it is actually supplied and validated.

Prevent acceptance of real structural repair using the synthetic-only null calibration.

If independent real measurements are missing, report the exact blockers and preserve a replayable partial investigation without claiming G2 completion.

## Phase D — Independent evidence validation

Implement a separate G5 evaluation module with:
- Immutable model freeze and content hash.
- Held-out dataset permissions enforced outside the agent runtime.
- No post-evaluation model tuning against the same holdout.
- Reproducible independent numerical prediction scoring.
- Blind commitment and reveal with a secret random nonce and canonical geometry measurements.
- Distinct SYNTHETIC and REAL evidence verdicts.
- Negative controls and explicit inconclusive outcomes.

The commitment must be created before the investigation, and the nonce must remain secret until reveal.

The agent must never access sealed measurements, truth records, or final holdout scores during investigation.

Do not represent a synthetic blind challenge as a real physical blind discovery.

## Phase E — Final submission readiness

Preserve the existing product and improve only demonstrated usability or correctness issues.

Update the application to display:
- Verified measurement accuracy when manual references exist.
- Pending physical experiment actions.
- Frozen model versions and independent validation status.
- Real versus synthetic evidence boundaries.
- A clear demonstration of the actual Muse reasoning contribution.

Prepare:
- `docs/TASK06_IMPLEMENTATION.md`
- `artifacts/task06/TASK06_READINESS.md`
- `docs/META_COMPLIANCE.md`
- A compact final demo storyboard.
- Reproducible validation commands.
- Exact test results and changed-file inventory.

Verify event requirements against official rules available to the project owner. Mark any unverified participant-specific obligations as unresolved.

## Verification

Run targeted scientific, integration, provenance, isolation and product regression tests.

Require tests for:
- No ground-truth leakage.
- Immutable model freezing.
- Valid and invalid blind reveals.
- Held-out evaluation isolation.
- External versus controlled-video provenance.
- Missing physical calibration.
- Unverified manual annotations.
- Real-data structural decisions rejected when only synthetic calibration exists.
- Preservation of previous G1–G4 results.

Implement and test the deliverables. Do not stop at planning.

Do not introduce more agents, microservices, additional physics domains, unrestricted generated code, or a new frontend framework.

At completion, distinguish:
1. Fully verified executable functionality.
2. Functionality verified only on synthetic data.
3. Functionality validated with real SAM output.
4. Physical model claims still awaiting independent measurements.

Do not claim full G2/G5 completion without appropriate real data.
