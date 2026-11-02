# Task 05 readiness

Date: 2026-11-02. **The integrated synthetic investigation and actual Meta
integrations are executable. Full physical G2 acceptance remains pending.**
Start the product with `python scripts/run_realign.py`, then open
http://127.0.0.1:8765. Cached playback performs no API calls or numerical fitting.

| Evidence domain | Actual status | Scope |
|---|---|---|
| G1 numerical regression | PASS: 250 cases, zero failures, 1,516 transitions | Existing synthetic physics |
| Initial targeted tests | PASS: 68 tests, 10.02 s | Physics, API protocol fixtures and contracts |
| Existing scientific regression suite | PASS: 149 tests | Includes B0/B1/B2/B3 and byte-for-byte baseline reports |
| New offline product/adapter/external tests | PASS: 102 tests, 27.35 s | No live requests or real-world ground truth |
| Isolated browser tests | PASS: six tests, 36.34 s | All five views, mobile, failures and actual video overlay |
| WSL investigator integration | PASS: nine tests, one platform-only skip, 766.80 s | Actual isolation, bounded investigation and fresh replay |
| Native Windows isolation check | PASS: one test, 5.27 s | Unsupported isolation fails closed |
| Final local HTTP regression | PASS: nine tests, 13.07 s | Read-only routes and evidence/media admission |
| Portable product admission | PASS: all five checks; sixteen recorded runs | Post-freeze human replay |
| Live Muse capability probe | PASS: four successful HTTP operations, zero failures | Actual model listing, structured output and tool round trip |
| Live Muse attempt 01 | PARTIAL: three HTTP successes; local protocol rejection, ABSTAIN | Retained unsuccessful investigation |
| Live Muse attempt 02 | PASS: nine HTTP successes, zero failures; two rounds, one experiment | Actual model reasoning over synthetic observations |
| SAM initial concept | Two HTTP successes; completed zero-mask match; tracking quarantined | Actual external video, failed tracking selection |
| SAM `yellow disc` | Two HTTP successes; 600 masks, 550 accepted centers, 50 shape rejects | Actual external video tracking |
| Human tracking comparison | NOT_PROVIDED; RMSE/bias unavailable | Requires independent annotations |
| Controlled REAL_PHONE recordings | NOT_PROVIDED | Physical G2 not passed |
| Blind structural discovery / Muse superiority | NOT_DEMONSTRATED | No claim authorized by this slice |

Actual Task 05 HTTP totals: **20 successful, 0 failed**. HTTP completion is
distinct from scientific or tracking success: the first Muse protocol attempt
and the first SAM empty-match attempt are retained and visibly unsuccessful.
An earlier report-package import failure occurred before API requests and is
recorded separately with zero requests. No API key or raw sensitive reply is
stored in these artifacts.

## Synthetic comparison

The successful live and deterministic runs use identical initial observation
capability hashes, the same candidate models, numerical tools and declared
budgets. Both select the predefined peg-contact predictive model and obtain
post-freeze development trajectory RMSE **0.8196110265191848 px**. Live uses
eight logical fit jobs/twelve tool calls; deterministic uses eight/fourteen.
Each receives one release experiment action containing two new trajectories.
This one-case equality demonstrates integration, not a Muse performance advantage
or unique causal identification. B2 radial error is not compared with trajectory
RMSE. See [matched_live_comparison.json](matched_live_comparison.json).

On this same development set, B0's trajectory RMSE is 7.245683831043045 px,
B1's is 7.0338835992568445 px and B3's is 0.8196110265191848 px. These values
come from complete predictions with the frozen exploration fits.
One of two live investigation attempts completed the whole protocol; this small
attempt count is not a reliability estimate. No official-documentation wire
contract mismatch was found. The first local response-bound rejection concerns
the application's bounded protocol, not a confirmed Meta API contract error.

The live attempt records 118,269 input tokens, 7,173 output tokens and
34.368466103 s API latency. Verified monetary pricing is unavailable; cost is null.
All nine live acceptance checks passed in
[live_meta_verification.json](live_meta_verification.json).

## External perception evidence

The video is MikeRun's Wikimedia Commons blocked-pendulum footage, licensed
CC BY-SA 4.0, explicitly REAL_EXTERNAL. Its source URL, attribution and original
and processed hashes are retained in the provenance exports. The actual pipeline
uses SAM 3.1, the official `meta-sam-parser` 0.1.0, original video PTS and the
existing tracking QA. No classical tracker substitutes for SAM.

`external_yellow_disc/` contains the real receipt, 600 PTS/center rows,
per-frame quality flags, eighteen overlays, twenty clean review frames and blank
independent-annotation templates. Object identity is `0`; the rejection fraction
is 50/600 = 8.3333%. SAM confidence values are unavailable in all 600 frames.
The original zero-mask attempt remains in `external/`.

Manual error, systematic localization bias, physical capture-time scaling,
metric scale and pivot calibration are unverified. They remain null/pending.
No physical acceleration or peg geometry is inferred from this slow-motion
footage. The real external tracking is separate from the synthetic investigation.

## Product and scientific boundaries

All five views are connected to admitted artifacts. Source and policy labels are
explicit, exploration and development are separated, and earlier rounds do not
show future fits as contemporaneous evidence. Whole-bundle hashes, numerical
resource references, linked audits and frozen decisions are checked before
display. Hashes provide integrity relative to a trusted local catalog, not
cryptographic third-party attestation.

CORRECT_MEASUREMENT is explained as **Measurement correction required**.
No bundle claims an applied or independently verified correction. A reference
check alone cannot complete a correction. The numerical contracts remain
backward compatible.

The existing calibrated numerical gate is reused unchanged. G1 and B0-B3 source,
numerical tools, isolated-worker boundary and scientific acceptance rules were
preserved. No null recalibration was necessary. API adapters now expose sanitized
local protocol/budget diagnostics and explicit bounds in their prompt.

## Reproduction

```powershell
python -m pip install -e ".[dev,perception]"
python scripts/run_realign.py
python scripts/prepare_demo.py
python scripts/verify_task05.py
# Explicit live operations; .env stays local.
python scripts/verify_task05.py --env-file .env --run-live --run-sam --standard-tier-confirmed
```

Windows preparation/verification uses the existing Ubuntu WSL runtime; ordinary
cached viewing uses the native Python environment. Meta calls are explicit and
can consume quota. A matching real-SAM cache is reused. Missing authorization is
reported, never replaced by mock output.

## Final verification record

Initial regression: 68 passed in 10.02 s. G1 rerun: 250 cases, zero failures,
maximum energy drift 1.709933528104557e-9 J/kg, maximum position jump
1.9849118084270064e-15 m and maximum tangential-speed jump
4.440892098500626e-16 m/s. The post-export integration command reports all five
checks passed with sixteen runs.

```powershell
python -m pytest -q tests/test_product.py tests/test_task05_adapters.py tests/test_product_external.py --tb=short --junitxml=artifacts/task05/offline_product_tests.xml
# Optional isolated browser tests:
python -m pip install -e ".[ui-test]"
python -m playwright install chromium
$env:REALIGN_BROWSER_TESTS = "1"
python -m pytest -q tests/test_product_browser.py --junitxml=artifacts/task05/browser_tests.xml
```

The first command passed 102 tests in 27.35 s. The actual browser command used
`REALIGN_BROWSER_EXECUTABLE` pointing to the installed Chrome 156.0.8078.48 and
passed six tests in 36.34 s. It covers all views, the two-round experiment loop,
live/failure traces, correction wording, malformed responses, responsive views
and actual video seeking with a PTS-aligned tracked-center overlay. Fresh
profiles, no model key and blocked external requests keep replay independent of
API access. Screenshots in `screenshots/` were inspected. CUA/Sky desktop-control
hosts were unavailable; this verification used isolated Playwright automation.

New offline checks also exercise frozen/audited policy and model parameters,
original PTS, unavailable/malformed evidence, simulated-versus-real sources and
sanitized API/cleanup failures. An isolated wheel build succeeded with static
assets and current product module bytes verified, recorded in
[packaging_verification.json](packaging_verification.json). The existing numerical gate still loads and scientific source
paths have an empty Git diff; no null calibration was recomputed.

The existing Task 04 GitHub Actions
[run 41367511893](https://github.com/mouadelabbassi/realign/actions/runs/41367511893)
completed all three jobs successfully. Task 05 browser CI is configured but has
not yet been pushed or executed remotely. The isolated WSL integration command
below passed nine tests with the native-Windows-only test skipped, in 766.80 s.
The separate native Windows fail-closed check passed in 5.27 s; the final HTTP
subset passed nine tests in 13.07 s. The broader Windows scientific suite passed
all **149 tests**, including the byte-for-byte B0/B1/B2 and B3 report checks.
Its actual pytest wall time was **51,341.81 s (14:15:41)** and includes a long
host/process interruption. It must not be interpreted as a compute-performance
benchmark. There are no remaining unrecorded test outcomes.

```powershell
wsl -d Ubuntu -- bash -lc 'cd /mnt/c/Users/mouad/Downloads/REALIGN && /home/mouad/.cache/realign-task04-venv/bin/python -m pytest -q tests/test_investigator_integration.py --junitxml=data/processed/task05_investigator_tests.xml'
python -m pytest -q tests/test_investigator_integration.py -k native_windows --tb=short --junitxml=artifacts/task05/native_isolation_tests.xml
python -m pytest -q tests/test_product.py -k http --tb=short --junitxml=artifacts/task05/http_tests.xml
python -m pytest -q tests/test_physics.py tests/test_baselines.py tests/test_perception.py tests/test_meta_validation.py tests/test_structural.py tests/test_investigator_contracts.py --junitxml=data/processed/task05_regressions.xml
```

JUnit records are retained beside this report. These checks verify the real
isolated numerical workflow, sanitized abstention, fresh replay and the native
fail-closed boundary. They make no Meta requests.
The WSL JUnit copy is
[isolated_investigator_tests.xml](isolated_investigator_tests.xml); G1 evidence is
retained as [G1_REPORT.md](G1_REPORT.md) and
[g1_verification.json](g1_verification.json). CLI elapsed times above include
pytest startup and can differ slightly from the inner JUnit suite timer.
The broad suite is retained as
[scientific_regression_tests.xml](scientific_regression_tests.xml), and
[verification_summary.json](verification_summary.json) records every command,
test count, API operation total and remaining physical-validation boundary.

See [TASK05_IMPLEMENTATION.md](../../docs/TASK05_IMPLEMENTATION.md) for algorithms,
the implementation inventory, detailed receipts and runtime constraints, and
[TASK05_DEMO_SCRIPT.md](../../docs/TASK05_DEMO_SCRIPT.md) for the presentation.
The exact Task 05 paths and excluded preexisting user changes are recorded in
[modified_files.json](modified_files.json). No Task 05 commit or push was made.

## Inputs needed next

1. Independent reviewed centers for the external-video clean reference frames,
   with frame indices, processed video hash, reviewer and annotation uncertainty.
2. Controlled phone stationary, repeated free-swing and peg-contact recordings;
   original capture timing; measured calibration points, scale and pivot; release
   brackets; manual reference centers; fixed recording partition assignments.
3. Real measurement uncertainty validation and a real-data model acceptance study
   before structural acceptance on physical observations.

Follow [REAL_DATA_COLLECTION_PROTOCOL.md](../../docs/REAL_DATA_COLLECTION_PROTOCOL.md).
No further architecture expansion or general compiler is needed to collect these
inputs. Full G2, broad identification claims and sealed evaluation remain open.
