# REALIGN — INVESTIGATOR IMPLEMENTATION PLAN: FIRST EXECUTABLE SCIENTIFIC INVESTIGATOR

Repository: https://github.com/mouadelabbassi/realign

Architecture v1.1 is frozen. Task 03 implemented classical B3 hybrid-dynamics fitting and five typed scientific tool contracts.

We now need REALIGN's first functioning, evidence-grounded agentic investigation.

Your assignment is to IMPLEMENT and TEST a bounded scientific investigator using the existing physics and fitting modules.

## 1. Inspect the existing project

Read AGENTS.md, the engineering corrections, Task 03 implementation, investigator contracts, and relevant source code.

Verify that the current repository tests pass. Check GitHub Actions and fix actual regressions.

Preserve G1/B0/B1/B2/B3 behavior unless a demonstrated error requires a documented correction.

## 2. Implement the exploration-only evidence and tool layer

Implement executable handlers for:

- `inspect_discrepancy`
- `fit_candidate_model`
- `compare_candidate_models`
- `inspect_identifiability`
- `score_candidate_experiment`

Reuse the existing verified numerical methods.

Use strict typed inputs and outputs, immutable content references, resource allowlists, bounded computation budgets, and audit logging.

No tool may access synthetic hidden truth, development data, sealed validation data, or unapproved filesystem paths.

Tool handlers must not return ground-truth mechanism labels.

A missing metric must remain unavailable, not be replaced with an invented score.

## 3. Implement the investigator state machine

Create one bounded investigator with the following stages:

OBSERVE → HYPOTHESIZE → TEST → REQUEST_EVIDENCE or DECIDE → FREEZE.

Support five possible outcomes:

- KEEP_UNCHANGED
- CALIBRATE_PARAMETERS
- CORRECT_MEASUREMENT
- REPAIR_STRUCTURE
- ABSTAIN

Decisions must be evidence-supported and allow uncertainty.

The investigator must not automatically choose the lowest training-loss model.

Separate the agent's proposal from the scientific validator's acceptance.

## 4. Build real experiment-planning functionality

Expand the experiment schema using a strict discriminated union, without arbitrary instructions or unsafe physical actions.

Support:

- Physical release-angle experiment.
- Repeat recording.
- Stationary-reference check.
- Camera calibration check.

Implement an explicit, bounded experiment-scoring method.

If expected information gain cannot be calibrated, use a transparent predictive-discrimination score with uncertainty and label it correctly.

Do not invent Bayesian information gain values.

Provide a deterministic planner using the same experiment candidates and scoring tools for comparison.

## 5. Integrate Muse Spark 1.3

Build a production adapter using the officially documented Meta API.

Requirements:

- Structured agent responses.
- Genuine multi-turn tool calling.
- Strict tool-name and argument validation.
- Budgeted tool calls and investigation rounds.
- Retries only where appropriate.
- Error handling and explicit abstention.
- Sanitized audit trail.
- No invented tool responses.

Implement a mock adapter for offline CI that follows the same interface.

A mock run is not evidence that Muse works.

## 6. Demonstrate an investigation

Use observation-only synthetic cases for:

- No fault.
- Parameter mismatch.
- Excited vertical peg.
- Off-vertical peg.
- Unexcited peg.
- Measurement problem.
- Ambiguous/insufficient evidence.

The most important demonstration must include a genuine two-round investigation:

1. Initial observations support multiple explanations.
2. The investigator requests a discriminating experiment.
3. The environment provides a new permitted observation.
4. The investigator updates its competing hypotheses.
5. A supported decision or abstention is produced.

The investigator must not see hidden generator parameters or event labels.

Use explicit scientific fixtures and record every numerical result.

## 7. Prevent false structural-repair claims

Implement a conservative, empirically calibrated structural-comparison decision for the supported FREE versus PEG_ONE_SIDE candidates.

Calibrate the null using synthetic no-fault/parameter-fault trials across several seeds and noise levels, with a predefined false-repair target.

Do not use development or sealed data to tune the gate.

Report sensitivity, specificity, ambiguity and failure cases.

Do not call predefined peg-model selection open-ended equation discovery.

Actual repair acceptance must be separated from hypothesis proposal.

## 8. Benchmark Muse against deterministic planning

Give Muse and the deterministic planner equivalent access to candidate models, numerical tools, evidence, experiment options and computational budgets.

Compare:

- Correct supported decisions.
- False repairs.
- Abstentions.
- Number of experiments.
- Predictive error.
- API latency and token cost.

Clearly distinguish mocked, deterministic and live Muse results.

Do not claim agentic superiority without matched measured comparisons.

## 9. Verification and deliverables

Implement unit tests, integration tests, adversarial tool-input tests, evidence-leakage tests and reproducible investigation replays.

Produce:

- Executable investigator CLI.
- Investigation traces and reports.
- Baseline comparison results.
- State-machine transition tests.
- Error/abstention demonstrations.
- Live Meta capability status.
- Exact files changed and commands run.

Keep the existing scientific regression suite intact.

If the local Meta API key is unavailable, implement the complete testable runtime and report live validation as NOT_RUN.

Do not redesign the architecture, introduce multiple agents, generate arbitrary executable Python, implement a general-purpose compiler, or create the frontend in this task.

Do not stop at writing a plan. Implement working code and test it.

At completion, report precisely what has been implemented, what the experiments actually proved, and what remains unverified.
