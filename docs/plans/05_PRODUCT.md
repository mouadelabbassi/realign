# REALIGN — PRODUCT IMPLEMENTATION PLAN: LIVE META INVESTIGATION AND END-TO-END PRODUCT SLICE

Repository: https://github.com/mouadelabbassi/realign

Architecture v1.1 is frozen. Task 04 delivered five scientific tools, an isolated numerical runtime, a bounded investigator, experiment planning, synthetic null calibration, audit replay and matched deterministic/mock studies.

Your assignment is to turn this existing system into a verifiable, integrated Meta-powered product experience.

**Do not redesign the architecture. Do not add additional agents or services.**

## PHASE A — Verify Task 04

Read AGENTS.md, TASK04_IMPLEMENTATION.md, TASK04_READINESS.md, the agent/tool code, scientific validation rules and current CI results.

Run targeted regression tests and fix confirmed failures.

Preserve G1 and B0–B3 scientific behavior. Avoid rerunning expensive complete calibration unnecessarily when a valid unchanged calibration artifact exists.

## PHASE B — Actual Muse Spark integration

Use the existing `MuseAdapter` and the documented Meta API.

Verify:
- Genuine structured outputs.
- Valid scientific tool calling.
- Multi-turn tool-response handling.
- Two-round investigation with a requested experiment.
- Accepted decision or justified abstention.
- Request budgets, error handling and audit receipts.

When MODEL_API_KEY and account authorization are available, execute the actual live investigation and compare it with the deterministic policy on the same synthetic evidence and numerical tools.

Do not claim Muse superiority unless matched live results demonstrate it.

If credentials are unavailable, complete every offline integration check but mark live validation NOT_RUN.

Do not substitute the mock in live mode.

## PHASE C — Actual SAM video integration

Use our existing REAL_EXTERNAL video ingestion and provenance system.

Process the open-license blocked-pendulum MP4 with real SAM 3.1 when authorization exists.

Export:
- Video and license provenance.
- Original frame timestamps.
- SAM tracking receipts.
- Tracked bob centers.
- Quality flags.
- Tracking overlays.
- Manual review comparisons.

Do not present external video as our own physical experiment.

Do not infer physical acceleration or peg geometry from slow-motion playback unless capture timing and calibration are independently verified.

If live SAM processing is unavailable, preserve the tested offline pipeline and clearly report the blocker.

## PHASE D — Correct the measurement-decision semantics

Review the CORRECT_MEASUREMENT outcome.

A reference check alone must not be presented as completed physical measurement correction.

Either implement an evidence-supported calibration or measurement revision followed by verification, or distinguish the outcome as "measurement correction required" in the product explanation.

Maintain backward compatibility with the approved decision contracts where possible and document any changed semantics.

Add tests proving that an unverified check does not become a claimed successful correction.

## PHASE E — Build the first integrated REALIGN product interface

Create a usable scientific investigation interface connected to existing backend data.

Required views:

1. **Reality versus Simulation:** measured trajectories, model predictions, residuals and uncertainty.
2. **Investigation:** competing hypotheses, selected numerical tools, actual evidence and model comparisons.
3. **Experiment Loop:** requested experiment, feasibility score, received data and updated hypotheses.
4. **Model Decision:** keep, recalibrate, measurement correction required, predefined structural model selection or abstention.
5. **Evidence:** frozen model/version, evaluation results, audit replay, baseline comparisons and provenance.

The interface must distinguish:
- SYNTHETIC observation data.
- REAL_EXTERNAL SAM processing.
- REAL_PHONE controlled trials.
- Mock versus deterministic versus LIVE_MUSE investigation.
- Exploration evidence versus independent evaluation.

Never combine separate evidence sources into a false end-to-end real-world discovery.

Use a lightweight implementation suited to the existing Python modular application. Avoid unnecessary frontend/backend infrastructure.

The interface must be visually strong, responsive and intelligible to a hackathon judge. No fake metrics, hardcoded success screens or fabricated tool traces.

## PHASE F — Reproducible demonstration

Build one complete synthetic investigation demonstration with an actual model comparison, an experiment request, a second observation round and a frozen predictive model.

Allow replay from recorded artifacts without rerunning every numerical fit.

If the live Muse run succeeds, preserve its authentic trace separately and make it selectable in the interface.

If live validation fails, show the failure accurately and retain the working deterministic demonstration.

## PHASE G — Verification and delivery

Add automated integration tests for:
- Backend-to-UI evidence serialization.
- Authentic versus synthetic source labels.
- Missing or malformed investigation results.
- Model freeze and audit integrity.
- No hidden truth or sealed data in agent-visible payloads.
- No falsely reported measurement correction.
- Graceful handling of API authorization and network failures.

Generate:
- `docs/TASK05_IMPLEMENTATION.md`
- `artifacts/task05/TASK05_READINESS.md`
- Live Meta verification receipts when available.
- Real SAM tracking evidence when available.
- A reproducible end-to-end demo command.
- A concise demonstration script for hackathon presentation.
- Exact test results, limitations and modified-file inventory.

The user must be able to start REALIGN and see a legitimate investigation with observable model behavior, not just read numerical reports.

Do not implement open-ended equation generation or claim real blind model discovery in this task.

**Implement working code, execute available tests, and deliver the demonstrable integrated product slice.**
