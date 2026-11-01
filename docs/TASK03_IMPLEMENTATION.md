# Task 03 implementation and evidence boundaries

Task 03 continues Architecture v1.1. G1 source and existing B0/B1/B2 numerical
algorithms remain unchanged. Added B3 fits the already validated one-peg hybrid
pendulum, rather than compiling a new structural model.

## Initial verification

Before implementation, installed with the local virtual environment:

    python -m pip install -e ".[dev,perception]"
    python -m pytest -q
    python scripts/verify_g1.py

Observed: **72 passed in 783.61 s**; G1 **250 cases, zero failures, 1516 mode
transitions**. Maximum energy drift 1.709933528104557e-9 J/kg, position jump
1.9849118084270064e-15 m, speed jump 4.440892098500626e-16 m/s, vertical peg
period error 6.247757866617576e-11 s. G1 numerical records match prior evidence.

The existing GitHub push workflow for 5bdc734cffedb904b986d56895c0507e1fe787fd
completed successfully: https://github.com/mouadelabbassi/realign/actions/runs/41249571396.
No existing CI regression was observed. The updated workflow also runs B3 tests
and reproduction on Python 3.11/3.12; its new version needs a future push to run.
The job budget is 90 minutes for the full bounded multistart/CV regressions and
all reproduction commands; live API calls and downloads are excluded from CI.

Old baseline artifacts are retained. Reproduction into
data/processed/task03_regression used NumPy 2.5.4/SciPy 1.18.1, while the committed
Task 01 report used NumPy 2.3.4/SciPy 1.16.3. All 13 checks and all B2 decisions
remain unchanged; the largest B1 development RMSE difference is 0.00662038 px
(vertical peg). This is observed cross-environment numerical drift, not a
demonstrated scientific regression or a reason to change G1. The preservation
comparison is included in the final Task 03 verification record.

The working tree contains a user deletion of root is.py. It is preserved.
This task does not commit, push, or overwrite remote history.

## Structural fitting and comparisons

    python scripts/verify_structural.py

See artifacts/B3_BASELINES.md and b3_baselines.json for actual measured synthetic
results, numerical budgets, failed starts and held-out scores. The command also
writes observed arrays, a separate post-fit evaluation record and a trajectory
plot. The observation-only fitter imports no synthetic generator or truth.

B3 fits L, viscous and quadratic bob drag, peg-distance/L and peg angle with
eight deterministic starts. One observation-derived geometric start is augmented
with a fixed bounded search. Contact side is declared; both supported sides are
tested separately. Contact loss factors remain ideal at one. The free-side
condition constrains training releases; directed events determine actual contact.
Every residual is a complete G1 rollout with missing observations excluded.
Real-video prediction preserves PTS, the pre-release held pose, release offset
and the existing common timing covariance whitening interface.

CV refits use whole exploration trials; disjoint development trials are scored
only after fitting. No development data tune parameters, starts or thresholds.
B2 radial reconstruction is reported separately from time-trajectory RMSE.
Failed fits, invalid trajectories, numerical rank, active bounds, conditional
local standard deviations and near-optimal multistart spread are retained.

This is a valid predefined dynamical candidate comparison. It is not the full
Architecture v1.1 null-calibrated structural-selection gate. Monte Carlo null
thresholds, broad power/MDE curves, uncertainty coverage, global equivalence,
independent geometry measurement and peg-removal interventions remain pending.
The implementation emits no structural-discovery or automatic repair decision.
Local sensitivity rank is not a mechanism-identification certificate.
Near-optimal multistart spread uses a diagnostic robust-cost window of best
cost plus 2.3; it has no chi-square, posterior-mass or confidence-level meaning.

## Measured synthetic comparison

Measured synthetic development results from the fixed protocol (xy trajectory
RMSE, px; B2 is deliberately omitted from this temporal score table):

| Case | B0 | B1 | B3 |
|---|---:|---:|---:|
| No fault | 0.722311 | 0.720490 | 0.723749 |
| Parameter fault | 34.748305 | 0.719287 | 0.718566 |
| Vertical peg | 44.627802 | 32.777710 | 0.680284 |
| Off-vertical peg | 25.802755 | 19.572740 | 0.707100 |
| Unexcited peg | 0.694053 | 0.697875 | 0.697875 |
| Noisy peg | 25.806544 | 19.690919 | 3.664269 |
| Short arc | 0.700754 | 0.705190 | Rejected: insufficient excitation |
| Insufficient data | 0.626540 | Rejected | Rejected |

Nine protocol checks passed. Both exploration CV folds favor B3 strongly on the
excited peg cases. Parameter-fault folds disagree about a small B3 advantage;
the paired development interval includes zero. Under no fault, B3 is slightly
worse on development. B1/B3 prediction disagreement is only 0.04924 px for no
fault, 0.01990 px for parameter fault and 0.00000769 px for the unexcited peg.
These are below the assumed localization uncertainty and do not identify a peg.
The unexcited fit has numerical rank 3/5. Some null-like fits can be locally full
rank by fitting tiny noise-scale features; this still does not justify a repair.

The requested synthetic sampling rate is 25 Hz. The preserved Experiment.times
adapter rounds duration times requested rate: 2.5 s therefore gives 63 timestamps
(actual uniform rate 24.8 Hz); the 0.3 s case gives 9 timestamps (26.6667 Hz).
Actual timestamps drive all fitting/scoring; no nominal-rate approximation enters
the dynamics. This distinction is documented rather than changing the validated
synthetic adapter. Video predictions continue to use original PTS.

Two initial B3 unit checks failed and were corrected: the uncertainty failure
branch omitted its null standard-deviation field; a test incorrectly assumed a
0.65 m peg distance must cause slack at 1.4 rad release. Direct integration showed
that short-radius configuration stays taut. A lossless 0.30 m probe produces
SLACK_VIOLATION at 0.79879997 s; the corrected unit test also rejects the
corresponding damped case. G1 was unchanged. The rerun of affected and
related checks passed 26 tests (17 deselected) in 412.22 s.

The initial structural test command reported 18 passed/2 failed and elapsed
45742.99 s across a session that spanned a long wall-clock gap. That is the raw
reported elapsed value, not a runtime benchmark. The final verification record
records fresh suite outcomes separately.

## External physical media details

The publicly attributed source is MikeRun's Blocked-pendulum-slow-motion.webm,
dated 2025-10-28, CC BY-SA 4.0:

- Source: https://commons.wikimedia.org/wiki/File:Blocked-pendulum-slow-motion.webm
- License: https://creativecommons.org/licenses/by-sa/4.0/
- Original SHA-256: b51517e260e620b306a91f8b2dbd1cc8c2fa8d74250cc05e5210cfe7f8f4315a
- Local H.264 derivative SHA-256: 8989ec961c6bcfd86edb6826a0b1b9569cb8bb4d11d5097904afd4aa5ad82213

An initial media request returned HTTP 429. A bounded retry with a research user
agent downloaded 1,759,473 bytes and verified the hash. A decoded frame was
visually inspected and shows a physical laboratory pendulum. The local derivative
removes audio, uses H.264 CRF18/yuv420p and retains dimensions, frame count and PTS
within quantization. Derived media retains CC BY-SA 4.0 and the attribution.
Raw/downloaded media stays in ignored data/raw/external. Public attribution/hash
metadata is retained in configs/external_video.example.json and evidence JSON.

    python scripts/prepare_external_video.py --download
    python scripts/smoke_sam.py data/raw/external/blocked-pendulum.mp4 --external-source artifacts/external_source_verified.json --standard-tier-confirmed

The preparation command verifies the original digest, records the actual local
encoder's derivative digest, checks timestamps/dimensions and decodes every
frame. Different FFmpeg builds can produce different bytes; use the generated
external_source_verified.json for the actual derivative. Never rename a changed
hash to match the example. External provenance requires creator, source and
license URLs, original/processed hashes and explicit modifications.

REAL_EXTERNAL, REAL_PHONE and SYNTHETIC_RENDER remain distinct video sources.
Actual external masks can be REAL_SAM only after actual SAM processing. External
and phone recordings cannot be mixed in a fitted comparison. The existing phone
G2 gate still requires REAL_PHONE. This slow-motion clip has **unverified physical
time scale**, no measured planar calibration, no measured length/pivot and no
reviewed centers: it is tracking-integration media only. The real measurement
pipeline rejects it for dynamical fitting until its capture time scale is verified.

## Actual Meta integration status

No local MODEL_API_KEY is configured. Actual successful calls **0**, actual failed
calls **0**. Muse structured output, genuine network tool round trip, SAM upload,
streaming masks and external-video SAM tracking are **NOT_RUN**. Offline fixtures
are explicitly simulated and never counted as live API calls.

    python scripts/smoke_meta.py --standard-tier-confirmed
    python scripts/smoke_sam.py path/to/phone.mp4 --standard-tier-confirmed

Both commands remain separately executable and exit 2 when required inputs are
absent. Credentials are read only from the local environment, not manifests.
The Muse probe independently validates closed-schema JSON, validates and executes
an allowlisted bounded numerical sum, appends the full assistant tool-call message
and matching tool result, then verifies the returned value. It requires an actual
model-emitted call: a direct answer does not pass the round-trip probe. Calls use
tool_choice=auto, the documented supported choice. No arbitrary code is executed.
Errors retain types/status codes only; raw server messages and replies are not
saved. Fixtures test malformed outputs, wrong tool names, bad arguments, missing
tool calls and transport failures without a key.

Official references checked for the wire contracts:

- https://dev.meta.ai/docs/cookbook/sam-api-basics
- https://dev.meta.ai/docs/cookbook/structured-output
- https://dev.meta.ai/docs/cookbook/tool-function-calling
- https://dev.meta.ai/docs/protocols/chat-completions

No official-documentation-versus-live-behavior mismatch can be assessed without
an authorized request. Missing inputs are not API failures. The previous simple
smoke script's raw exception-message persistence was removed because it could
persist sensitive request/server data; the scientific kernels are unaffected.

The initial dependency install succeeded. A later repeat hit a DNS resolution
failure while fetching isolated setuptools, and the venv lacked a local build
backend for the no-isolation retry. An editable wheel was built without network
using the already installed global setuptools 80.9.0. Required runtime packages
were already installed and pip check reported no broken requirements. This
environment/network issue is separate from Meta authorization and test outcomes.

## Handoff and pending gates

Final verification: **115 passed in 3065.21 s**, zero failures/errors/skips.
Standalone verifiers passed 250 G1 cases, 13 existing baseline checks, 8 offline
G2 checks and 9 B3 checks. All eight B3 numerical case records reproduce exactly
excluding source hash. The final sampling-text clarification was rendered from
the frozen numerical JSON; no fitted values were changed. Exact commands,
versions and results are saved in artifacts/TASK03_VERIFICATION.json, with the
JUnit record in artifacts/task03_tests.xml. See artifacts/TASK03_READINESS.md for
the acceptance assessment and artifacts/TASK03_FILES.txt for the exact inventory.

See INVESTIGATOR_TOOL_CONTRACTS.md and investigator_tool_schemas.json for the
five typed input/output contracts. They are design artifacts with executable
schema validation, not implemented tool handlers. No Muse loop, compiler,
frontend, experiment planner or sealed evaluator was added.

Next inputs: a locally configured authorized API key and confirmed Standard tier;
stationary and repeated physical free/peg recordings; measured planar fiducials,
pivot, physical scale and lens calibration where necessary; release brackets and
independently reviewed frame centers. Follow REAL_DATA_COLLECTION_PROTOCOL.md.
External media cannot replace these physical measurements. G2 and full G3 remain
unpassed until their independent evidence requirements are actually satisfied.
