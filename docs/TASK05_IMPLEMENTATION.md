# Task 05: live Meta investigation and local product slice

Implemented on 2026-11-02 within Architecture v1.1. The application now plays
back an actual two-round Muse investigation and actual external-video SAM
tracking in separate, clearly labelled views. This is a synthetic scientific
investigation plus an independently verified external perception integration.
It is not an end-to-end physical discovery demonstration. Full G2 remains open.

The measured acceptance record is
[TASK05_READINESS.md](../artifacts/task05/TASK05_READINESS.md). Historical Task 04
reports retain their original no-authorization status; Task 05's new receipts
supersede that status only for the executions recorded here.

## Start and reproduce

From the repository root, with the existing environment installed:

```powershell
python -m pip install -e ".[dev,perception]"
python scripts/run_realign.py
```

Open http://127.0.0.1:8765. The command opens the default browser unless
`--no-browser` is supplied. `--port` selects another loopback port. The app is a
single Python application with static HTML/CSS/JavaScript and a read-only local
HTTP interface. It does not call Meta, optimize parameters or execute an
experiment when viewed. The checked-in `artifacts/task05/demo` catalog makes
ordinary playback independent of WSL, API access and numerical refitting.

Rebuild the portable presentation, or verify its integrity:

```powershell
python scripts/prepare_demo.py
python scripts/verify_task05.py
```

These commands reconstruct only declared synthetic fixtures, verify exact
exploration observation capability hashes against each recorded investigation,
and predict with the already fitted parameter values. They perform no fitting
or API calls. On Windows they delegate to the existing Ubuntu WSL numerical
environment so reconstruction uses the original numerical dependencies. If that
runtime is not installed, use `python scripts/setup_investigator_runtime.py`.
See [TASK04_IMPLEMENTATION.md](TASK04_IMPLEMENTATION.md) for runtime requirements.

Live verification is separate and explicitly opt-in:

```powershell
python scripts/verify_task05.py --env-file .env --run-live --run-sam --standard-tier-confirmed
```

This may consume account quota. `--run-live` alone starts another bounded
off-vertical synthetic investigation; `--run-sam` alone processes the approved
external video. The latter reuses a matching real-API mask cache if present.
The default visual SAM concept is `yellow disc`; `--concept` overrides it and
`--object-id` selects an explicitly reviewed tracking identity. Copy the blank
`artifacts/task05/external_yellow_disc/manual_reviews.template.json` into
`data/reviews/external_reviews.local.json`, fill the reviewed pixel centers,
reviewer and annotation standard deviation, and supply that independent file
with `--manual-reviews data/reviews/external_reviews.local.json`. Keep completed
annotations separate from generated template/output files.

The optional environment loader reads only `MODEL_API_KEY` from the chosen local
file into the launching process. Existing environment values take precedence.
It does not evaluate shell expressions, persist keys, load unrelated variables
or log values. SDKs continue to read the environment. The isolated numerical
worker receives no model credential. API commands without authorization report
NOT_RUN; live mode never substitutes the mock policy.

## Product data and integrity boundary

The five views are Reality versus Simulation, Investigation, Experiment Loop,
Model Decision and Evidence. A trajectory scrubber, round selector, model
predictions, residuals and localization covariance expose actual recorded
behavior. The investigation view displays recorded hypotheses and numerical
tool outputs. Experiment Loop shows the selected action, its bounded feasibility
score, receipt and second-round evidence. Model Decision explains the accepted
scope. Evidence exposes frozen model references, audit chains, baseline prediction
errors and post-freeze development results.

The run selector separately identifies DETERMINISTIC, MOCK_POLICY and LIVE_MUSE.
The source selector separates SYNTHETIC, REAL_EXTERNAL and REAL_PHONE. Mock
investigations are explicitly labelled; their intentional agreement with the
deterministic planner is an interface test. No phone recordings have been supplied.

Presentation export is trusted, post-freeze, human-only code. Task 04 traces
contain observation hashes rather than raw trajectory arrays. The exporter
therefore explicitly regenerates the declared synthetic observations and admits
them only when every exploration capability equals the original recorded
capability. It also verifies the frozen model and the independently scored
development error. This path is unavailable to real recordings. It does not
serialize hidden generator parameters, event ground truth or sealed trials.

Portable bundles include full-trajectory predictions from B0, B1 and B3 where
the investigation actually produced those fits. Round 1 cannot display a
Round 2 fit as contemporaneous evidence. Development results are human-visible
only after freeze, never investigator inputs. B2 radial reconstruction error is
not placed on the trajectory-RMSE chart.

The catalog pins every whole presentation document with SHA-256. Admission
rechecks audit linkage, the frozen decision hash and fitted model capability
content. Model parameters must match the audited resource. Hash chains detect
changes relative to a trusted local catalog; they are not external signatures
or proof against an administrator replacing every artifact. The server is
loopback-only, serves allowlisted resources, rejects writes and nonlocal
Host/Origin requests, and exposes no general filesystem or credential endpoint.
Missing or altered evidence produces an explicit error rather than a success
screen. Media serving is conditional on the approved video hash.

## Live Muse evidence

The existing `MuseAdapter` uses `muse-spark-1.3` through the documented structured
output and tool-calling API. The actual numerical tools supply every fit and
comparison; the model supplies hypotheses, requests and a proposed decision.

| Actual execution | Result | Successful / failed HTTP operations |
|---|---|---:|
| Basic capability smoke | Model listing, structured output and genuine tool-response round trip passed | 4 / 0 |
| Investigation attempt 01 | Local model-protocol rejection; ABSTAIN before a second round | 3 / 0 |
| Investigation attempt 02 | Accepted two-round investigation with one received experiment | 9 / 0 |

Attempt 01 remains in the selectable trace list and is not counted as a completed
scientific success. Its HTTP requests completed; a response subsequently violated
the local bounded protocol. That older trace does not identify the precise
rejection code. The adapter now states the two-tool response bound, concise
citation bound, required evidence order and measurement semantics explicitly.
It emits static protocol/budget failure codes; the controller audits sanitized
execution failures without exception bodies. These changes do not modify the
tool schemas, science validator, optimizer, acceptance threshold or physics.

Attempt 02 made nine requests, used 118,269 input and 7,173 output tokens and
recorded 34.368466103 seconds of API latency. Monetary cost is unavailable and
remains null. It executed twelve numerical tool calls and eight logical fit jobs,
within the same limits as the deterministic comparison. It requested a release
experiment, received two new synthetic exploration trajectories, completed a
second round and froze an accepted predefined PEG_ONE_SIDE model.

| Matched synthetic comparison | Deterministic | Live Muse attempt 02 |
|---|---:|---:|
| Initial exploration capability hashes | Identical | Identical |
| Experiments received | 1 action | 1 action |
| Logical fit jobs | 8 | 8 |
| Numerical tool calls | 14 | 12 |
| Selected-model development xy RMSE, px | 0.8196110265191848 | 0.8196110265191848 |

The comparison uses the same initial evidence, candidate primitives, numerical
tools and budgets. Equal final predictive error in one case does not demonstrate
agentic superiority, unique mechanism identification or blind discovery.
One of two live investigation attempts completed the full protocol; these two
attempts are not a reliability estimate. No wire-contract mismatch between
official Meta documentation and the observed successful requests was found.
The earlier two-tool response-bound issue concerns this application's stricter
local protocol, not a demonstrated Meta API contract error.
Receipts and the comparison are in
[live_meta_verification.json](../artifacts/task05/live_meta_verification.json)
and [matched_live_comparison.json](../artifacts/task05/matched_live_comparison.json).

## Actual external-video SAM evidence

The approved video is [Blocked-pendulum-slow-motion.webm by MikeRun](https://commons.wikimedia.org/wiki/File:Blocked-pendulum-slow-motion.webm),
under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). It is
REAL_EXTERNAL, not self-recorded phone footage. The original and derived hashes,
source URLs, creator, license and transcode description are retained in
`artifacts/external_source_verified.json` and each exported provenance document.
The 1280 by 720 H.264 MP4 contains 600 frames with original presentation timestamps
represented in its recorded 1/15360 time base. Physical capture-rate scaling is
not independently verified.

Both actual attempts used the official video upload/streamed SAM 3.1 workflow
and `meta-sam-parser` 0.1.0. No response schema or tracking output was invented.

| Visual concept | Calls | Parsed mask records | Accepted centers | Result |
|---|---:|---:|---:|---|
| `the pendulum bob` | 2 successful, 0 failed | 0 | 0/600 | Completed empty match; tracking quarantined |
| `yellow disc` | 2 successful, 0 failed | 600 | 550/600 | Tracking QA passed; 50 shape rejects |

A completed empty match is valid API behavior, not parser success for a tracked
object. The failed tracking attempt is preserved in `artifacts/task05/external`.
The successful visual-concept attempt is in `artifacts/task05/external_yellow_disc`.
Actual masks are saved before QA so rejection does not erase diagnostic evidence.
No classical tracker silently replaces SAM.

The export contains all original frame PTS, centers and validity/quality flags,
the real SAM receipt, eighteen mask/center overlay frames, twenty clean reference
frames and human-annotation templates. The selected object identity is `0`.
The API supplied no confidence values for any of the 600 frames; those values
remain unavailable. An 8.3333% shape-rejection fraction is not a localization
uncertainty estimate. Human reference centers have not been supplied, so manual
RMSE and bias remain null with status NOT_PROVIDED.

There is no independent physical scale, pivot calibration or capture-time
verification for this footage. It is not used to infer acceleration, peg
geometry, dynamic model acceptance or real-world structural repair. The live
synthetic Muse investigation and this real external SAM run remain separate
evidence streams. Actual Task 05 totals are twenty successful HTTP operations
and zero failed HTTP operations, with one locally rejected Muse protocol attempt
and one empty-match SAM tracking attempt retained separately.

## Measurement-decision semantics

The approved `CORRECT_MEASUREMENT` identifier remains backward compatible.
The product says **Measurement correction required**. A completed reference
check can diagnose unresolved quality but does not apply a calibration change.
Every current bundle sets both `correction_applied` and `correction_verified`
to false; admission rejects a bundle claiming otherwise. A future correction
must carry an actual supported revision and independent verification before
those semantics can change.

## Verification and preserved science

Before implementation, the targeted Windows regression command was:

```powershell
python -m pytest -q tests/test_physics.py tests/test_meta_validation.py tests/test_investigator_contracts.py --junitxml=data/processed/task05_initial_tests.xml
```

Result: **68 passed in 10.02 seconds**. G1 was rerun with output redirected to
`data/processed/task05_initial/g1` to preserve preexisting root artifacts:
250 randomized configurations, zero failures, 1,516 transitions. Maximum energy
drift was 1.709933528104557e-9 J/kg, maximum position jump 1.9849118084270064e-15 m,
maximum speed jump 4.440892098500626e-16 m/s and period error
6.247757866617576e-11 s. Existing numerical behavior was unchanged.
Copies of the measured record are retained as
[G1_REPORT.md](../artifacts/task05/G1_REPORT.md) and
[g1_verification.json](../artifacts/task05/g1_verification.json).

The existing WSL gate loaded with the unchanged numerical source signature
`2617cb0ce5a5c91d9382bb87233bc69d6f1095246a931103ea247437169c4855`.
No expensive null recalibration was performed. During implementation a missing
tracked report package caused an import failure before API execution; the
original files were restored and its zero-request infrastructure failure retained
separately. No numerical correction or new physical equation was required.

The new product, adapter and external-export tests were run with:

```powershell
python -m pytest -q tests/test_product.py tests/test_task05_adapters.py tests/test_product_external.py --tb=short --junitxml=artifacts/task05/offline_product_tests.xml
```

Result: **102 passed in 27.35 seconds**. Tests cover artifact serialization and
provenance, missing/malformed results, model capabilities and audit/freeze
integrity, private-data exclusion, measurement wording, local environment
loading, explicit simulated fixtures, API failures and sanitized cleanup failure.
Review-driven fixes bind policy/API accounting to audited identity, fitted
parameters to audited capabilities, nominal and frozen model references to the
record, decision wording to verified semantics and external display times to
original PTS. A client cleanup failure now retains the original result and
sanitized receipt rather than discarding evidence.

Browser tests are an opt-in test dependency, not part of normal viewing:

```powershell
python -m pip install -e ".[ui-test]"
python -m playwright install chromium
$env:REALIGN_BROWSER_TESTS = "1"
python -m pytest -q tests/test_product_browser.py --junitxml=artifacts/task05/browser_tests.xml
```

Optionally set `REALIGN_BROWSER_EXECUTABLE` to an installed Chrome/Edge binary.
The actual local run used Chrome 156.0.8078.48 and passed **six tests in
36.34 seconds**. It exercised all five views, Round 2, trajectory scrubbing,
post-freeze development, live and failed traces, measurement-required semantics,
desktop/mobile layouts, malformed backend responses, actual external-video
decoding and PTS-aligned center overlays. Browser contexts use fresh profiles,
strip the model key and block external requests. Desktop/mobile screenshots were
visually inspected. The interactive CUA/Sky control hosts were unavailable;
verification used isolated Playwright browser automation of the local app.

The isolated WSL investigator integration run passed **nine tests with one
native-Windows-only skip in 766.80 seconds**. It exercised actual OS isolation,
the two-round observation-only workflow, sanitized protocol-failure abstention
and fresh numerical replay. The native Windows fail-closed check separately
passed **one test in 5.27 seconds**. The final local HTTP subset passed **nine
tests in 13.07 seconds**. Exact commands and copied JUnit records are in
[TASK05_READINESS.md](../artifacts/task05/TASK05_READINESS.md). These checks make
no model API requests. The broader Windows scientific regression also passed
**149 tests**, including both byte-for-byte baseline report checks. Its recorded
wall time was 51,341.81 seconds, including a long host/process interruption;
this is not a computation performance benchmark. Its exact command, copied
JUnit and all final results are in
[verification_summary.json](../artifacts/task05/verification_summary.json).

An isolated PEP 517 wheel build succeeded and includes current product modules
and all three static assets, checked against their current source bytes. Its
SHA-256 is `5f957028d1d72150de57c9115c268e9f3f49c63634b38ad8fc6be9080a8aba6a`;
see [packaging_verification.json](../artifacts/task05/packaging_verification.json).
The unchanged scientific source paths have an empty Git diff, and the existing
gate loaded successfully without recalibration.

The existing Task 04 GitHub Actions run
[41367511893](https://github.com/mouadelabbassi/realign/actions/runs/41367511893)
completed successfully in all three jobs. The new Task 05 browser CI is
configured but has not been pushed or executed on GitHub.

## Changed implementation inventory

- New `src/realign/product/`: evidence admission, synthetic presentation export,
  read-only catalog/server, external SAM evidence export, decision wording,
  demo preparation and static interface.
- New `src/realign/local_environment.py`: explicit, nonlogging local key bootstrap.
- New `scripts/prepare_demo.py`, `scripts/run_realign.py`, `scripts/verify_task05.py`.
- Modified `agent/adapters.py` and `agent/investigator.py`: bounded prompt guidance
  and sanitized diagnostic codes/events.
- Modified `perception/sam_client.py`: configurable short visual concept with the
  original default preserved; official parser remains unchanged.
- Modified `investigator_platform.py`, `scripts/_wsl_entry.py`: two new approved
  entrypoints; `pyproject.toml`: static product assets and optional browser-test
  dependencies; README startup guidance and CI product/browser checks.
- New Task 05 tests, documentation, receipts, portable playback bundles,
  external tracking exports and verification artifacts. The generated
  [modified_files.json](../artifacts/task05/modified_files.json) inventory records
  the exact paths and separately identifies preserved preexisting user changes.

Validated G1, B0/B1/B2/B3, observation contracts, numerical tools and Task 04
acceptance rules remain intact. No Muse-generated executable code, model
compiler, additional product agent/service or sealed evaluator was introduced.

## Remaining acceptance work

Supply the controlled stationary, repeated free-swing and peg recordings listed
in [REAL_DATA_COLLECTION_PROTOCOL.md](REAL_DATA_COLLECTION_PROTOCOL.md), measured
calibration points/pivot/scale, original capture timing and release brackets,
independent reviewed pixel centers and fixed exploration/development assignments.
For the current external video, filling the supplied review template enables a
pixel-localization comparison without inventing physical timing or calibration.
Real observations need their own validated uncertainty and acceptance calibration;
they cannot inherit the synthetic empirical null gate. Broader live studies,
identifiability/power coverage and independent sealed evaluation remain future work.

Official API references:
[structured output](https://dev.meta.ai/docs/cookbook/structured-output),
[tool calling](https://dev.meta.ai/docs/cookbook/tool-function-calling),
[SAM video workflow](https://dev.meta.ai/docs/cookbook/sam-api-basics).
