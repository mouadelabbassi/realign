# Narrow investigator tool handoff v1.0

These are **schemas only**, not an implemented Muse investigator, numerical tool
registry, experiment planner, compiler or sealed evaluator. Architecture v1.1
remains unchanged. Export exact JSON Schema with:

    python scripts/export_tool_schemas.py

The executable definitions are in src/realign/contracts/investigator_tools.py;
docs/investigator_tool_schemas.json contains all five input/output pairs. Records
are frozen, reject additional fields, validate finite numerical fields and use
opaque 64-character content hashes instead of paths or semantic rig names.

| Tool | Typed input | Typed output | Numerical implementation next task |
|---|---|---|---|
| inspect_discrepancy | Exploration trial refs, fitted model ref | Evidence ref, status, quality flags, valid count, trajectory RMS px, innovation mean square, lag-1 correlation | Reuse calibrated observation residuals; add vetted discrepancy diagnostics |
| fit_candidate_model | Exploration trial refs, FREE/PEG_ONE_SIDE, nominal model ref, budget ref, declared wrap side | Fitted model ref, evidence ref, cost, attempted/converged starts, actual residual calls, flags | Wrap existing B1/B3; resolve immutable budgets and persist fitted artifacts |
| compare_candidate_models | Fitted model refs, exploration trial refs, fixed protocol ref | Per-model trial-CV MSE px²; separately named geometric radial MSE m²; calibration ref; calibrated-support enum | Refit on whole exploration folds; add Monte Carlo null calibration before calibrated support |
| inspect_identifiability | Exploration trial refs and fitted model ref | Scaled singular values, rank, local identifiability, uncertainty ref, flags; global identification fixed false | Wrap B3 sensitivity and add profiles/coverage evidence |
| score_candidate_experiment | Fitted model refs, one bounded release experiment, feasibility-protocol ref | Feasibility, EIG nat, separation sigma, numerical uncertainty, evidence ref | Not implemented: integrate parameter uncertainty and test feasibility/EIG calibration |

Numerical values may be null when unavailable. Missing calculations must produce
FAILED, AMBIGUOUS or NOT_IMPLEMENTED with closed flags, never invented zero scores
or successful estimates. No arbitrary source code, expressions, file paths,
Python function names, network endpoints or free-form dictionaries are accepted.
The arithmetic function in the API smoke test is a separate allowlisted test
tool; it is not a placeholder scientific implementation of these contracts.

Before implementing handlers, the next phase must provide an exploration-only
reference resolver and immutable protocol/budget lookup. A syntactically valid
hash grants no access. Resolve every reference against the current investigation's
allowlist, reject development/sealed/hidden resources even if their hashes are
known, and validate model provenance. The agent cannot choose arbitrary bounds
or tune a protocol on hold-out outcomes. Whole-trial CV folds are made from
exploration trials; confirmatory development scoring stays outside the agent
tool outputs. No sealed measurements appear in inputs or results.

Outputs carry fitted-model and numerical-evidence references, not generator
labels, true parameters, source filenames, raw frames/masks, hidden event labels,
secret geometry or sealed statistics. Fitted peg estimates in a numerical model
artifact are inferred quantities, not independent geometry measurements. The
resolver must expose only an approved fitted-model projection when needed.
External filenames/attribution remain in perception provenance records, not the
investigator's diagnostic payloads.

Pydantic validation, opaque references and import tests are hygiene, not a
security boundary. Storage permissions/process isolation and audited allowlists
must be implemented before granting Muse tool access, as required by
IMPLEMENTATION_CORRECTIONS.md. No tool handlers or full agent were added here.

Tests reject extra hidden/sealed fields, non-hash paths and a sealed zone. The
future handler tests must additionally deny access to real forbidden resources,
test canaries across every output and check audit provenance after model freeze.
