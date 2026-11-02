# Task 04: executable bounded scientific investigator

This is one investigator in Architecture v1.1. G1 and the B0/B1/B2/B3 numerical
modules are unchanged. No general compiler, generated executable code, frontend,
sealed evaluator or additional investigator was introduced.

The measured acceptance results are in
[INVESTIGATOR_REPORT.md](../artifacts/task04/INVESTIGATOR_REPORT.md) and
[investigator_results.json](../artifacts/task04/investigator_results.json).
The verification record and exact file inventory accompany those artifacts.
Synthetic evidence, simulated API fixtures and live network evidence have
different provenance and must not be combined into a success claim.

## Runtime and reproduction

The supported numerical isolation runtime is **Linux x86-64 with Landlock ABI
3 or newer and seccomp**. Unsupported isolation fails closed. The Windows CLI
uses the existing Ubuntu WSL distribution to run the same application. This
is a local child process, not a service or another investigation agent.

Install the ordinary project first:

```powershell
python -m pip install -e ".[dev,perception]"
# Windows: install the separate Linux dependencies into the WSL user cache.
python scripts/setup_investigator_runtime.py
python scripts/verify_investigator.py --calibrate
python scripts/run_investigator.py --mode deterministic --case off_vertical_peg --seed 51300
python scripts/run_investigator.py --mode mock --case insufficient
python scripts/replay_investigation.py artifacts/task04/traces/deterministic_off_vertical_peg.json
```

The complete perception test suite additionally needs FFmpeg and ffprobe in
the Linux environment (Ubuntu: sudo apt-get install ffmpeg). Investigator
direct-trajectory fixtures do not upload or decode phone footage.

On Linux, use the same commands without the WSL setup step. On Windows the
four investigator CLIs delegate automatically to Ubuntu. The setup helper
requires an installed Ubuntu WSL distribution and installs the project extras
into `~/.cache/realign-task04-venv`; it does not configure or request credentials.
Absolute drive-letter argument paths are translated to the corresponding
`/mnt/<drive>/...` paths. Native Windows numerical isolation is not supported.

Calibration artifacts are bound to the physics, fitting, observation, tool,
protocol, fixture and calibration source, Python version, platform and numerical
library versions. Recalibrate after these change. The gate loader accepts only
artifacts below `artifacts/task04`. Do not copy a threshold into a different
environment and represent it as reproduced.

Without a gate, numerical work and two-round investigations remain executable
with `--uncalibrated`; structural acceptance is unavailable. A bounded example:

```powershell
python scripts/run_investigator.py --mode mock --case off_vertical_peg --uncalibrated
```

Live execution is separately opt-in and never substitutes the mock policy:

```powershell
python scripts/run_investigator.py --mode live --case off_vertical_peg --standard-tier-confirmed
python scripts/verify_investigator.py --run-live --standard-tier-confirmed
```

These commands read `MODEL_API_KEY` only from the local environment. On Windows,
WSL receives it through the local environment, not a command argument or file.
The numerical child receives a stripped environment without that variable.
The full live benchmark uses the same seven cases, seeds, candidates and budgets
as the deterministic and mock arms. Missing authorization produces NOT_RUN with
zero requests. The report records actual attempts, failures, latency and available
token counts; monetary costs remain null until verified pricing is supplied.
Offline reproduction schedules up to four independent study cases concurrently,
with one investigator and private numerical session in each case. Cases do not
communicate or share observations, fits or budgets. Live benchmark cases run
serially. Completion order never changes report order or registered seeds; host
wall times under batch scheduling are not reasoning-speed comparisons.
The single-run command exits 2 for NOT_RUN and 1 for failed isolation.

## Evidence capabilities and OS boundary

The trusted application host admits only exploration `Trial`/`VideoTrial`
records and independent reference measurements. Arrays are copied to a strict
data-only envelope; semantic recording IDs are replaced with content-derived
IDs. Development records, duplicate observations, unknown fields and mixed
synthetic/real provenance are rejected. Admission is atomic.

The numerical child receives an allowlisted copy of numerical source and runtime
dependencies, never the generator, agent adapter, reports, data directories or
credentials. Landlock restricts reads to that runtime and required OS library
paths. It denies writes to the runtime. Seccomp denies network, process spawning,
parent-memory access and alternate process/I/O escape interfaces. The x32
syscall-number flag is explicitly rejected, with a harmless getpid startup
probe; checking the x86-64 architecture field alone is insufficient. Core dumps,
memory, file descriptors and CPU time are bounded. JSON pipe messages are bounded.
Every worker must pass actual forbidden-file, network, parent-memory, generator,
write and credential-environment checks before admitting any observation.

An experimental native Windows LPAC launcher was tested. A stricter probe found
that Python's required registry-read capability can open the real user's
environment registry key. **No registry values were read.** Removing that
capability prevented interpreter bootstrap. The native implementation therefore
refuses startup; it does not weaken the probe or silently fall back to ordinary
Python. Its preliminary numerical traces are quarantined in an ignored local
`native_windows_prototype` folder and are not accepted investigator evidence.

This boundary protects the numerical tool process against accidental or
model-directed resource access. The host provisioning code and installed OS/
Python/runtime packages are trusted. It is not a defense against a compromised
host administrator, kernel, Python installation or malicious dependency. No LLM
text is executed as code. No storage vault or sealed validation API is added here.

## Five executable tools

Runtime contracts are version 1.1 in
`realign.contracts.investigation`, exported as
[investigator_runtime_schemas.json](investigator_runtime_schemas.json). Task 03's
schema-only v1.0 remains intact for reproducibility. All objects forbid extra
fields, nonfinite numbers, arbitrary paths, instructions and executable code.
Resources are immutable kind-scoped SHA-256 capabilities, not filesystem names.

| Tool | Numerical behavior |
|---|---|
| inspect_discrepancy | Full-trajectory RMS, whitened innovation mean square, residual lag diagnostic, missingness and independently measured quality checks |
| fit_candidate_model | Existing deterministic eight-start B1 FREE or B3 PEG_ONE_SIDE fitting; bounded physical parameters; explicit failures |
| compare_candidate_models | Two whole-trial exploration CV folds, matched current fit resources, registered-order checks and empirical null gate |
| inspect_identifiability | Existing local sensitivity/rank, bound and uncertainty diagnostics; global identification always false |
| score_candidate_experiment | Bounded trajectory-separation ensemble score or declared reference-check priority; no invented information gain |

Default budget: two rounds, one requested experiment, 32 response steps, 24 tool
calls, ten logical fit jobs, eight deterministic starts, 40 optimizer evaluations
per start and 24 actual API attempts including retries. Cached fits still consume
logical fit jobs, so one arm cannot obtain extra computation by repeating calls.
Each numerical operation has a 600-second host timeout. The worker has a one-hour
CPU lifetime limit and 2 GiB virtual-memory limit. Budget exhaustion is evidence
failure and causes abstention, never a fabricated score.

Per-frame real observations retain the existing PTS/covariance/release interfaces
in the fitter. However, this task's empirical selection gate and release planner
are calibrated only for the registered synthetic design. A real observation
cannot inherit that synthetic structural-acceptance calibration.

## State machine and decision acceptance

The state sequence is OBSERVE -> HYPOTHESIZE -> TEST -> REQUEST_EVIDENCE ->
OBSERVE (second round), or TEST -> DECIDE -> FREEZE. Errors route to DECIDE and
ABSTAIN. FREEZE rejects further tool mutation. Audit events and decisions use
canonical finite JSON with linked SHA-256 hashes. Recorded contexts are deep
snapshots; later fits cannot mutate previous evidence.

The adapter proposes a decision and citations. A separate scientific validator
accepts it only with current, approved evidence. Low training loss alone never
passes. KEEP_UNCHANGED and CALIBRATE_PARAMETERS map to architecture outcomes KEEP
and RECALIBRATE. The other outcome names are unchanged. KEEP means adequacy in
the explored operating envelope, not proof that an inactive peg is absent.
REPAIR_STRUCTURE selects an existing predefined predictive candidate; it does
not identify a unique physical cause or constitute open-ended equation discovery.

Measurement decisions require a quality failure and an actually completed
stationary/calibration check. Structural acceptance requires a calibrated
whole-trial prediction improvement, an inadequate FREE model, acceptable PEG
prediction error and local identifiability. Rejected proposals become ABSTAIN.
Frozen model and audit references are independent of the adapter's self-report.

## Experiment planning

The closed union supports RELEASE (0.1--0.7 rad, two repeats), REPEAT (two or
three approved-source repeats), STATIONARY_REFERENCE and CAMERA_CALIBRATION.
Only a host-provisioned finite catalog can be requested. The current demonstrator
executes those actions through a labelled synthetic environment, not a physical
actuator. A real operator/approved-recording environment remains a future adapter.

For release/repeat, integrate the FREE fit and up to eight near-optimal PEG
multistart alternatives. Score the 75th percentile of RMS trajectory separation
divided by the localization RMS floor. Report half the interquartile range as
ensemble spread. This is a heuristic predictive-discrimination score, not a
posterior, confidence interval or expected information gain. Invalid sampled
rollouts make the action infeasible. Reference checks have explicit quality-
triggered priorities (100 for missing/bad, zero otherwise). Unavailable uncertainty
or unsupported real-video planning returns null metrics and an explicit flag.

## Registered false-repair pilot

The protocol was fixed before post-calibration evaluation: angles 0.2, 0.32,
0.65, 0.65 rad; 1.6 seconds; 33 actual timestamps; IID localization SD 0.5 or
1.5 px; one supported wrap side; nominal length 0.72 m. Fit L, viscous/quadratic
drag and, for PEG, peg fraction/angle within the published protocol bounds.

Twenty independent null datasets use five base seeds, two noise levels and
no-fault/parameter-fault strata. Noise streams differ across strata. Fit on
whole exploration trials, cross-validate two fixed trial folds, and define
T = min_fold((MSE_FREE - MSE_PEG) / trace(localization covariance)). Threshold
is max(0, all finite null T). Tail rank is
(1 + count(null T unavailable or null T >= observed T))/21.
The target is 0.05, with one formal look after the registered four-trial design.
Initial two-trial comparisons do not produce pretend CV metrics or a formal test.

Failed null comparisons count as worst-case tail exceedances. At N=20, even one
unavailable null prevents a 5% structural acceptance. At least 16/20 must be
numerically evaluable for a gate artifact to load. Each independent calibration
dataset gets its own worker lifetime; four datasets run concurrently and the
final rows are ordered by the registered design, not completion time. An
explicitly invalid progress checkpoint cannot be loaded as a gate.
Finite-grid nulls are not exchangeable with
every possible free-model parameter choice, correlated noise or camera error.
Report the independent validation false positives, sensitivity, specificity,
abstentions and binomial intervals; do not advertise a universal 5% guarantee.

Seven benchmark cases and twelve post-calibration validation cases use different
seeds from calibration. Validation uses distinct noise streams across mechanism
and noise strata, rather than rescaling shared draws. "Registered" means fixed
in the executable protocol; this is not an externally preregistered or sealed
study. Disjoint development trajectories are created and scored
only after each frozen decision. They do not tune the gate, model parameters,
experiment planner, budget or accepted proposal. B2 radial geometry is not
compared to time-trajectory prediction RMS.

## Muse protocol and limitations

The adapter uses the official Meta Chat Completions endpoint, muse-spark-1.3,
closed structured AgentTurn JSON, nested function tools and tool_choice=auto.
Every call name and JSON argument is validated before execution; duplicate JSON
keys, unknown names, reused call IDs and malformed batches fail. Original model
assistant tool-call messages and matching raw tool IDs are retained only in
request memory for the genuine next turn. Audit IDs are hashed local IDs. Actual
backend results are supplied as tool messages; the model never supplies them.

Retry only transport/timeouts, 408, 429 and 5xx errors, at most three attempts per
request and within the global request budget. Raw replies, request bodies, keys
and exception bodies are not persisted. Error receipts contain type/status only.
The offline SDK-shaped fixtures test protocol wiring, not Meta service behavior.
The mock policy intentionally matches the deterministic policy; no reasoning
performance or agentic superiority can be inferred from their agreement.

Official references: [tool calling](https://dev.meta.ai/docs/cookbook/tool-function-calling),
[structured output](https://dev.meta.ai/docs/cookbook/structured-output),
[Chat Completions](https://dev.meta.ai/docs/protocols/chat-completions),
[Landlock](https://docs.kernel.org/userspace-api/landlock.html),
[AppContainer isolation](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation).

Pending: actual end-to-end live Muse investigation and matched comparison,
real phone measurements/SAM validation, broader power/MDE and uncertainty
coverage studies, non-synthetic null calibration, independent geometry and
interventions, comparable deterministic grammar/compositional search for any
future unique-Muse-value claim, and the separate sealed evaluation phase.
Full G2, G3, G4 and G5 acceptance is not implied by this bounded offline slice.
