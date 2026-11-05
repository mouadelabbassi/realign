# BASELINE IMPLEMENTATION PLAN — Implement the POC-0 Classical Scientific Baselines

## Objective
Continue the existing REALIGN starter from its actual code state. Add reproducible synthetic observations and strong non-LLM comparators before agent coding. Preserve the numerical G1 kernel unless a test exposes an actual bug.

## Read first
1. `AGENTS.md`
2. `docs/IMPLEMENTATION_CORRECTIONS.md`
3. `docs/DEVELOPMENT_ROADMAP.md`
4. `docs/REALIGN_Build_Spec_v1.md`, especially Sections B, C, D, F and the known corrections
5. Existing `src/realign/physics/*.py`, `tests/test_physics.py`, `scripts/verify_g1.py`, `README.md`, and `pyproject.toml`.

## Initial inspection
- Show `git status --short` (or explain if not a git repo).
- Run `python -m pip install -e ".[dev]"`, `pytest -q` and `python scripts/verify_g1.py` with an appropriate local Python environment.
- Report actual verification results and any discrepancy from G1_REPORT. Do not change the G1 oracle on speculation.

## Authorized implementation scope

### A. Minimal observation & experiment contracts
Add lightweight typed records needed for the baseline slice (Pydantic if justified, otherwise dataclasses validated explicitly): observation positions/timestamps/validity, reference coordinate frame and units, experiment release angle/duration, noise configuration, and a sealed synthetic-truth object **not importable or visible to the fitters**. Avoid implementing full model DSL or Muse classes yet.

### B. Synthetic trial generator
- Generate deterministic free-pendulum and peg-contact trials through the **existing** physics simulator, with reproducible seeds.
- Include at least: null (no peg), identifiable peg, off-vertical peg, and unexcited/ambiguous peg trials. Respect the simulator's free-side release contract.
- Add Gaussian localization noise and optionally reproducible AR(1) noise / dropped samples; mark synthetic defaults as assumptions, not measured phone noise.
- Use a simple explicit metric-to-pixel projection with known scale for these tests; reserve true camera calibration for Phase 2.
- Store ground truth apart from observations exposed to estimators.

### C. B0 and B1 baseline
- B0: predictions from nominal original free-pendulum model.
- B1: fit the *same fixed model structure* using `scipy.optimize.least_squares`; fit physically admissible parameters (e.g. L, gamma) with bounds and multiple initial starts. Use only permitted observations and documented initial-condition handling.
- Predict full trajectories without resetting the model to observations every frame. Implement fair in-sample and out-of-sample evaluations on disjoint trials.
- Report fit failures; no silent success and no access to true hidden peg geometry.

### D. B2 geometric baseline
- One-circle vs two-circle trajectory geometry, using only observed xy positions, not simulator mode labels, hidden peg coordinates or known transition times.
- Estimate candidate circle centers/radii, reject degenerate short arcs, handle noise, find change points or a defensible segmentation, and compare with a controlled complexity penalty or held-out trials.
- Do not force two circles when the trajectory never contacts the peg; allow an ambiguous outcome.
- Record peg-location error only in evaluation after fitting; do not use it for inference.

### E. Reproducible report
Produce a single command such as `python scripts/verify_baselines.py` that generates:
- `artifacts/POC0_BASELINES.md`
- `artifacts/poc0_baselines.json`
- one honest plot showing reference observations and model predictions for a reproducible simulated trial.
The report must include B0/B1/B2 scores, failed cases, named seed, units, conditions, and explicit labels **SYNTHETIC ONLY — NO META API / REAL-WORLD VALIDATION**.

## Required tests
1. G1 previous tests and verifier still pass.
2. Same input seed produces identical generated observations.
3. No-fault B1 recovers suitable identifiable parameter values to tolerance justified by the simulated noise.
4. On a sufficiently excited peg case, the fixed-structure baseline leaves a detectable systematic discrepancy.
5. B2 recovers a second center/peg position on at least one clean synthetic case without hidden labels.
6. No peg and no contact cases do not force a fake second pivot.
7. Degenerate arcs, missing samples, wrong units and solver failures are handled explicitly.
8. Fit evaluation uses disjoint whole trials (not random interleaved frames) when producing held-out scores.
9. Data and model code cannot import or read hidden-truth objects at inference time.

## Acceptance gate
Do not claim G3 is fully passed merely by implementing B1/B2. The task passes when the above tests succeed, report artifacts reproduce from exact commands, and the remaining distinguishability limitations are clearly documented.

## Not authorized in this task
No full Muse agent, no generic DSL compiler, no sealed evaluation/commit-reveal, no complete frontend, no arbitrary generated code, no microgrid, no guessed real video data, no API calls without keys, no external push/commit without approval.

## Final response to project owner
Report: (1) actual baseline repository test results before edits; (2) files changed; (3) algorithms and assumptions; (4) commands run and observed results; (5) numerical baseline findings, including cases that fail; (6) blockers and the next Phase 2 task. Continue actual implementation until this task is done rather than returning another architecture proposal.
