# REALIGN — Repository Instructions for Codex

## Mission
Build REALIGN, a reality-grounded AI investigator that compares phone-video measurements with executable physics models, diagnoses discrepancies, requests informative experiments, proposes typed model revisions, and subjects frozen decisions to independent evaluation. Optimize for actual Meta hackathon evidence, not feature count.

## Source of truth
1. Existing repository code and tests establish **what has been implemented**, never what was merely planned.
2. `docs/REALIGN_Build_Spec_v1.md` contains the detailed proposed design; `docs/IMPLEMENTATION_CORRECTIONS.md` overrides its six known blocking issues.
3. This file and `docs/CODEX_EXECUTION_ROADMAP.md` define scope and phase ordering.
4. If these sources conflict, inspect the affected code and document the smallest defensible resolution. Don't silently rewrite the architecture.

## Frozen architecture
- One modular application, five logical layers: physical/perception; deterministic science; Meta Muse investigator; sealed validation; audit/product.
- Meta SAM 3.1 is the headline vision path; Muse Spark is the runtime scientific reasoning model. Numerical computations must not be fabricated by the LLM.
- `SimulationAdapter` may audit compatible simulators; `RepairableModel` supports typed edits to explicitly represented models only.
- Valid investigation conclusions: KEEP, RECALIBRATE, CORRECT_MEASUREMENT, REPAIR_STRUCTURE, ABSTAIN.
- The investigation agent must never read sealed trials, hidden geometry, reveal secret, or final validation outcomes before the model is frozen.
- No unrestricted execution of LLM-generated code. Use typed grammar, validation, and safe compilation.
- No microservices, second agent, microgrid, arbitrary general-purpose physics engine, or dashboard-centered product without evidence justifying an architectural change.

## Existing implementation
The starter contains a **tested G1 numerical kernel**, not the completed project. Run `python -m pip install -e ".[dev]"`, `pytest -q`, and `python scripts/verify_g1.py` before changing anything. Record results. Check that test counts and generated artifacts really match the repository; never infer success from older documentation.

## Physics invariants
- Plane frame: x right, y up, downward gravity; angular displacement from downward vertical.
- Within each hybrid mode, pivot and string length are constant (unless you derive and implement a more general Lagrangian deliberately).
- Ideal peg contact conserves Cartesian tangential speed; angular rate rescales by mode radii. Empirical contact losses are *not* ideal physics.
- Use event detection, not an angle-only heuristic, to decide reachability. Detect and reject unsupported string slack.
- Keep lengths, time, pixels, covariance, and velocity units explicit. Covariance is in px².

## Scientific integrity
- Every capability must have an objective test, reproducible numerical evidence, and scope limitations.
- Keep simulated and real observations visually and structurally separate. Never invent Meta API success or real measurements.
- Fit and compare on allowed exploration trials only; hold-out trials are never used in tuning or model selection.
- Give deterministic baselines access to comparably expressive model primitives and numerical tools when testing the unique contribution of Muse.
- Report negative controls, failed cases, uncertainties, and correct abstentions.
- Don't conflate predictive performance with identification of the true physical mechanism.

## Development method
- Implement one verified vertical slice at a time from `docs/CODEX_EXECUTION_ROADMAP.md`; the requested task file defines the current phase.
- Inspect the repository and `git status` first. Preserve user changes. Prefer small, testable patches with a clear diff.
- Add tests before claiming a feature is complete. Run existing tests and report exact commands/results.
- No credentials in source, artifacts, tests, prompts, logs, commits, or chat. Read `MODEL_API_KEY` only from local environment.
- Network/API tests require actual account access; mark them skipped/not-run if unavailable.
- Don't commit or push unless the user expressly approves. Do not overwrite the Git history.
- After a task, report: files changed, tests run and their outcomes, generated artifacts, known limitations, next task.
