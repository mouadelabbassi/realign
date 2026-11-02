# Task 04 readiness — measured offline evidence

Date: 2026-11-02. **Bounded offline Task 04 acceptance passed. Live investigator
and physical validation remain pending.** G1 and the B0/B1/B2/B3 numerical source
are unchanged. The exact file inventory is TASK04_FILES.txt; commands, JUnit
records and implementation history are in TASK04_VERIFICATION.json and verification/.

## Implemented

- Five executable numerical tools with closed v1.1 schemas, immutable capability
  references, exploration-only admission, bounded search and audit logging.
- One bounded investigator with OBSERVE/HYPOTHESIZE/TEST/REQUEST_EVIDENCE/
  DECIDE/FREEZE transitions and a separate scientific proposal validator.
- Release, repeat, stationary-reference and camera-check actions. A transparent
  predictive-discrimination ensemble score; expected information gain is null.
- Official Muse Spark 1.3 structured/tool protocol adapter, explicit offline mock,
  deterministic comparator, sanitized failures and budgeted retries.
- Independent synthetic null calibration, matched offline study cases,
  post-calibration validation, post-freeze development scoring and numerical replay.
- Linux Landlock/seccomp numerical isolation, including x32 ABI rejection,
  actual file/network/memory/write/credential checks and Windows-to-WSL CLIs.
- Push/PR regression CI and a separate bounded offline evidence reproduction job.
  The new workflow has not run on GitHub; the previous main CI at f027860 passed.

## Actual verification

| Command / environment | Observed result |
|---|---|
| Initial Windows pytest before implementation | 115 passed |
| verify_g1.py | 250 configurations, zero failures, 1516 transitions; numerical metrics unchanged |
| Complete final Linux/WSL pytest suite | 158 passed, one native-Windows-only skip, 1728.19 s |
| Final Windows investigator tests | 37 passed, seven Linux/WSL-only skips |
| Baseline byte-for-byte reproduction retest | One passed; JSON, Markdown, PNG and NPZ identical across two builds |
| verify_g2.py with separate output directory | Eight offline checks passed; zero real recordings/API calls |
| Twenty-dataset final null calibration | 20/20 evaluable, threshold 0.0, 20 unique seeds |
| verify_investigator.py | Exit 0; all nine offline acceptance checks passed |
| Active evidence inspection | All 26 trace audit/context/state checks and logical budgets passed |
| Fresh off-vertical numerical replay | Same frozen decision and numerical evidence hash |
| Single-run CLI and its replay | CORRECT_MEASUREMENT; two rounds, one completed reference check |
| Live CLI without available authorization | NOT_RUN, exit 2, zero successful/failed requests |
| Python compileall / pip check | Passed / no broken requirements |

An intermediate Windows suite reported 149 passed, seven skips and one failure:
only source_sha256 differed while source was edited between two report builds.
All eight other report fields were identical. The isolated byte-reproduction
retest passed, and the final full Linux run passed after source was held stable.
The original failure record is retained rather than relabelled as a success.
Raw test elapsed times include host scheduling and are not algorithm benchmarks.

The native Windows LPAC prototype failed private-registry isolation. No registry
values were read. Native execution is now unconditionally refused; the unsupported
launcher was removed. Windows investigator commands use Ubuntu WSL. A serial
Linux calibration attempt was deliberately stopped after six datasets to avoid
sharing a one-hour worker CPU lifetime across the whole study. The complete
accepted calibration was recomputed using individually bounded workers. The
report process was then deliberately restarted to load final validation seed
scheduling; no unfinished calibration was accepted as a gate.

## Measured synthetic outcomes

Both independently executed offline arms obtained seven of seven prescribed
benchmark outcomes and identical frozen model/decision hashes. The mock policy
intentionally mirrors the deterministic planner; this tests interface plumbing,
not Muse reasoning or superiority.

| Case | Accepted outcome | Post-freeze development xy RMS, px |
|---|---|---:|
| No fault | KEEP_UNCHANGED, within the tested envelope | 0.701275 |
| Parameter mismatch | CALIBRATE_PARAMETERS | 0.714099 |
| Excited vertical peg | REPAIR_STRUCTURE, predefined predictive candidate | 0.685571 |
| Off-vertical peg | REPAIR_STRUCTURE, predefined predictive candidate | 0.819611 |
| Limited-angle unexcited peg | ABSTAIN | Unavailable |
| Measurement problem | CORRECT_MEASUREMENT | Unavailable |
| Insufficient samples | ABSTAIN | Unavailable |

The off-vertical demonstration starts with two low-angle observations and rank
3/5 PEG sensitivity. It requests a 0.65 rad release action with two repeats,
receives two new exploration trajectories, refits and compares on whole-trial
folds. Final normalized minimum-fold improvement is 142.151025465 and empirical
tail rank is 1/21 = 0.047619. The supported predefined PEG prediction is frozen
before three new development trajectories are generated. No generator parameters,
event labels or development measurements appear in any agent context.

All five main fitting cases use eight logical fit jobs and fourteen tool calls,
within the identical budgets. Measurement correction uses zero fits/three tool
calls; insufficient data uses two fit jobs/three tool calls. Six benchmark cases
complete one experiment action; the insufficient case completes none. A release
action contains two physical-trial equivalents, not one trajectory.

## Negative controls, uncertainty and failures

Independent validation uses twelve distinct noise streams, disjoint from the
twenty calibration seeds: eight null and four excited-peg cases. Accepted false
repairs: **0/8**. Accepted peg selections: **4/4**. Specificity is 1.0 with
Clopper–Pearson interval [0.630583, 1]; sensitivity is 1.0 with interval
[0.397635, 1]. There is one abstention and zero failed runs. These are small,
heterogeneous synthetic study counts, not broad population guarantees.

The important non-success is parameter-mismatch seed 2042000 at SD 0.5 px.
The raw comparison flags PEG at a very small normalized gain 0.00237589:
FREE CV MSE 0.42999564 px² versus PEG 0.42852969 px², both below the assumed
0.5 px² localization MSE floor. PEG rank is 4/5 with a near-bound parameter.
The adapter proposes parameter calibration; the separate validator rejects the
conflicting proposal and freezes ABSTAIN. Its broad UNEXCITED flag is a validator
reason, not a measured physical contact event. Thus the raw comparison has one
null flag in eight cases, while the complete acceptance rule makes zero repairs.
Do not present the raw empirical comparison alone as a reliable repair rule.

Calibration records contain 960 attempted starts, including **174 nonconverged
starts**. The 26 main investigation records contain 1424 fitted-model starts,
including **137 nonconverged starts**. These outcomes, costs and residual-call
diagnostics are preserved; a successful multistart fit does not imply all starts
converged or a global optimum was found. Insufficient-data rejection, simulated
API errors, missing receipts, unapproved resources, malformed arguments, budget
exhaustion, changed audits and failed isolation also have automated tests.

The null target is 5%, with one formal look under a fixed four-trial design and
two whole-trial folds. Unavailable null fits count as worst-case exceedances;
any one at N=20 prevents 5% acceptance. Every final null comparison was available.
All null statistics were negative, so the threshold is clipped to zero.
The finite parameter grid and two assumed noise levels do not establish uniform
false-repair control, uncertainty coverage or a minimum-detectable-effect curve.
The parameter-mismatch validation case is outside that finite null length grid.
"Registered" means fixed in executable code, not externally preregistered or sealed.

## Meta, real observations and next inputs

Current Task 04 actual Meta requests: **0 successful, 0 failed; NOT_RUN**.
MODEL_API_KEY is not available to this process. The separately preserved local
artifacts/meta_smoke.json reports four successful basic capability calls and zero
failures. It is explicitly recorded as preexisting local evidence, not a live
Task 04 investigator run. Expanded structured schemas, long tool conversations,
latency/tokens/cost and matched live Muse performance remain unverified.

There are no new phone recordings or actual SAM results in this task. Full G2,
G3, G4 and sealed G5 acceptance remain pending. KEEP does not exclude an inactive
mechanism. REPAIR_STRUCTURE selects an existing predictive model and never claims
open-ended discovery, unique causality or a physical rig repair. No agentic
superiority, general compiler, frontend or sealed evaluator was implemented.

Supply next:

1. Authorized MODEL_API_KEY in the local launch environment and confirmed account
   tier, then run the separate live capability and investigator commands. Do not
   put the key in Git, manifests, artifacts or chat.
2. Actual stationary, repeated free-swing and peg recordings with original capture
   timing; measured planar fiducials, pivot/scale and lens calibration as needed;
   independent release brackets and manually reviewed centers.
3. Recording IDs and frozen exploration/development/future-sealed assignments,
   following ../../docs/REAL_DATA_COLLECTION_PROTOCOL.md. Real data require their
   own empirical calibration; the synthetic structural gate does not authorize
   real-data repair acceptance.

The next engineering slice is live protocol validation and real measurement
integration, followed by broader identifiability/power studies. Any future unique
Muse-value claim also needs matched live measurements and the planned comparable
deterministic grammar/compositional search. It cannot be inferred from this mock.
