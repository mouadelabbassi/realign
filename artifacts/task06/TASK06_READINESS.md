# Task 06 readiness

Date: 2026-11-02. **Evidence-closure functionality is executable. Physical G2 and
full physical G5 have not passed.** No new Meta API requests were made for this
task. Existing Task 05 live receipts and unsuccessful attempts remain unchanged.

The verified current local server is **http://127.0.0.1:8766** and its clean
review page is **http://127.0.0.1:8766/review**. Launch it with
`python scripts/run_realign.py --port 8766 --no-browser`. An older service still
responded on 8765 without Task 06 routes, so the current build was verified on
a fresh port. `local_http_verification.json` records all three successful routes.

## Evidence domains and measured results

| Domain | Verified result | Remaining boundary |
|---|---|---|
| Synthetic physics | Fresh G1: 250 randomized cases, 0 failures, 1,516 mode transitions. | Numerical kernel only; no real measurements. |
| Synthetic investigator/validation | Actual isolated numerical continuation; immutable freeze, pre-investigation commitment, one-shot evaluation, reveal verification, negative controls and failed cases tested. | Narrow predefined models; local custodian/host trusted. |
| Fixed synthetic positive control | 99 held-out samples; RMS **0.6930905745225341 px**, peg-position error **0.0056025527215726005 m**; SYNTHETIC_EXERCISE_PASS. | Fixed known fixture; not a blind-discovery claim or reliability study. |
| Privately randomized synthetic exercise | 99 held-out samples; RMS **0.7519408442222819 px**, peg-position error **0.014477706074618239 m**; SYNTHETIC_VALIDATION_FAIL. | Prediction passed 2 px tolerance; geometry failed 0.01 m tolerance. Preserved without a replacement attempt. |
| Public post-reveal reproduction | Both scores and per-trial prediction/timestamp digests match exactly; 0 fits, 0 APIs. | Reproduction of spent evaluations, not a second independent evaluation. |
| Actual SAM on REAL_EXTERNAL | Prior Task 05 actual processing preserved: 600 masks, 550 accepted centers, 50 rejected. | Tracking acceptance does not establish measurement accuracy. |
| Independent external accuracy | **NOT_VALIDATED**; RMSE/bias/median/p95/context metrics null. | Twenty clean frames await human centers and uncertainty. The sample starts at 5.233333 s and omits the early failure interval. |
| REAL_PHONE ingestion/investigation | Validated offline protocol tests; truthful BLOCKED_INPUTS report, 0 requests. | Actual phone recordings, timing, calibration, reviews and uncertainty absent. End-to-end real execution NOT_RUN. |
| Physical action continuation | Bounded pending checkpoint and supplied-recording admission implemented. Actual numeric replay tested with an explicitly synthetic controller fixture. | No physical action, actuator or supplied real response has been demonstrated. |
| Actual Muse | Prior authentic attempt 02 remains available: 9 successful operations, 2 rounds, 1 experiment over synthetic observations. | No new Task 06 calls; no controlled real investigation or superiority demonstrated. |
| Full physical G2 / G5 | **NOT_PASSED**. | Independent physical data and a qualified real acceptance protocol remain required. |

G1 maximum energy drift was 1.709933528104557e-9 J/kg, position discontinuity
1.9849118084270064e-15 m, speed discontinuity 4.440892098500626e-16 m/s and vertical
peg-period error 6.247757866617576e-11 s. No physics or fitting mathematics changed.
The original synthetic null-calibration signature remains
`2617cb0ce5a5c91d9382bb87233bc69d6f1095246a931103ea247437169c4855`.

The random challenge's frozen model content SHA-256 is
`1c328af3a5c0fb8b0b5bfd4fa80e301ae4e4a1a2dcd8c6533d49c37989f46095`.
Its commitment preceded investigation; geometry and nonce were released only
after the frozen model consumed its heldout once. The public reveal now permits
reproduction. Local ordering is not external timestamp attestation.

## Exact verification commands

Commands use the repository virtual environment. Windows investigator commands
delegate to the existing Ubuntu WSL runtime. No API key is required by tests.
JUnit records are under [tests/](tests/); the verification summary records final
counts and durations. Skips distinguish platform-specific isolation branches
and opt-in browser tests from completed checks.

```powershell
python -m pip install -e ".[dev,perception]"
python -m pytest -q tests/test_physics.py tests/test_investigator_contracts.py tests/test_product.py tests/test_product_external.py tests/test_task05_adapters.py tests/test_independent_validation.py tests/test_manual_review.py tests/test_physical_investigation.py tests/test_task06_product.py --tb=short --junitxml=data/processed/task06_final_targeted_tests.xml
# 218 passed, 2 Linux-only skips; 34.19 s.

wsl.exe -d Ubuntu --cd /mnt/c/Users/mouad/Downloads/REALIGN -- env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/mouad/.cache/realign-task04-venv/bin/python -m pytest -q tests/test_physical_investigation.py tests/test_independent_validation.py --tb=short --junitxml=data/processed/task06_runtime_final_tests.xml
# 29 passed, 1 native-Windows-only skip; 14.26 s.

$env:REALIGN_BROWSER_TESTS='1'
$env:REALIGN_BROWSER_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
$env:REALIGN_SCREENSHOT_DIR='artifacts/task06/screenshots'
python -m pytest -q tests/test_product_browser.py tests/test_task06_browser.py --tb=short --junitxml=data/processed/task06_browser_final_tests.xml
# 8 passed; 20.37 s. Browser requests restricted to the local test server.
# Linux CI installs Playwright Chromium instead of using a Windows browser path.

python scripts/verify_task06.py
# exit 0: offline closure admission PASS; accuracy NOT_VALIDATED; phone BLOCKED_INPUTS.
python scripts/verify_g5.py reproduce artifacts/task06/g5_demo
python scripts/verify_g5.py reproduce artifacts/task06/g5_positive_control
# Both exit 0: exact post-reveal reproduction PASS; original verdicts unchanged.
node --check src/realign/product/static/app.js
git diff --check
```

The initial pre-change targeted verification passed 148 tests in 36.10 s.
New manual-review tests passed 33 tests in 7.23 s. Earlier development runs
exposed a wrong exception class and an incomplete test-fixture constructor;
these were fixed and the affected suites rerun successfully. They were not API
failures or experimental measurements. The legacy investigator integration
tests also ran; final full-suite/reproduction results are recorded in
`verification_summary.json` and the corresponding JUnit evidence.

The complete Linux offline run used:

```powershell
wsl.exe -d Ubuntu --cd /mnt/c/Users/mouad/Downloads/REALIGN -- env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/mouad/.cache/realign-task04-venv/bin/python -m pytest -q --tb=short --junitxml=data/processed/task06_full_offline_tests.xml
# 329 passed, 10 skipped, 1 failed; 951.23 s.
# The sole failure was the report's source-hash comparison: source files were
# edited during the run. All other report fields were identical. No assertion
# was weakened and no numerical source was changed to mask this failure.
wsl.exe -d Ubuntu --cd /mnt/c/Users/mouad/Downloads/REALIGN -- env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/mouad/.cache/realign-task04-venv/bin/python -m pytest -q tests/test_baselines.py::test_report_integration_and_reproducibility --tb=short --junitxml=data/processed/task06_baseline_reproduction_final.xml
# Stable-source rerun: 1 passed; 300.20 s. Includes both byte-identical reports,
# plots and observation arrays, plus all baseline acceptance conditions.
```

The full run's failure is retained, not described as an all-green full run.
The affected test passed on rerun; the final targeted tests cover subsequent
Task 06 helper additions. All nine legacy Linux investigator checks passed in
the full run. Its eight opt-in browser skips were exercised separately (8/8
passed); its other two skips are native-Windows-only branches. Windows-specific
fail-closed checks passed in the final Windows targeted suite.

G1 was run through the unchanged verifier with `OUT` redirected to
`data/processed/task06_initial/g1` to avoid replacing older evidence:

```powershell
python -c "import importlib.util; from pathlib import Path; s=importlib.util.spec_from_file_location('g1','scripts/verify_g1.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.OUT=Path('data/processed/task06_initial/g1'); m.OUT.mkdir(parents=True,exist_ok=True); m.main()"
```

Latest inspected GitHub CI: [run 41479588109](https://github.com/mouadelabbassi/realign/actions/runs/41479588109),
commit `fb3f8ffab48c2a4ce1caca5ff441e61514e5241a` (`5`): all four jobs succeeded
(Python 3.11, Python 3.12, investigator evidence, product browser). That run
validates the previous commit, not these uncommitted Task 06 changes. CI now
also runs the two new browser checks and writes Task 06 screenshots separately
from immutable Task 05 media. Offline tests automatically discover new modules.

## Reproducible artifacts

- [task06_verification.json](task06_verification.json): honest domain/readiness status.
- [manual_review/measurement_validation.json](manual_review/measurement_validation.json):
  null accuracy plus actual interval QA, input hashes and limitations.
- [manual_review/review.html](manual_review/review.html): twenty clean original
  frames, blank center inputs, reviewer uncertainty/contexts and downloadable JSON.
- [phone_status.json](phone_status.json): exact missing-input blockers, no fake
  requested/completed physical action or frozen model.
- [g5_demo/validation.json](g5_demo/validation.json): randomized case, preserved failure.
- [g5_positive_control/validation.json](g5_positive_control/validation.json): separate fixed control.
- Both G5 directories contain commitment, public start receipt, investigation,
  frozen model receipt, actual OS-isolation probe, post-reveal synthetic records
  and exact numerical reproduction. Private pre-reveal vault files remain ignored
  under `data/vault/task06/`; neither product routes nor model tools serve them.
- [g1_regression/g1_verification.json](g1_regression/g1_verification.json),
  [ci_jobs.json](ci_jobs.json), JUnit test records and inspected screenshots.
- `changed_files.json`: exact Task 06 file inventory, excluding unrelated changes.

Task 05 artifacts and the original numerical sources have no Task 06 diff.
Unrelated pre-existing changes to `artifacts/g1_verification.json`,
`artifacts/meta_smoke.json`, `is.py`, `.vscode/` and
`artifacts/task04/investigation.json` are preserved and excluded from this delivery.
Task 06 has not been committed or pushed; prior approval for commit `5` applied
to Task 05.

## Inputs needed next

1. Open the local app's `/review` page and independently annotate its twenty
   clean frames, uncertainty and applicable contexts; supply the downloaded JSON
   to `review_external.py evaluate` / `verify_task06.py`. Do not use SAM centers.
2. Supply original stationary/repeated free/peg phone recordings, measured scale,
   pivot and calibration/checkpoints, verified physical capture timing, release
   brackets and independent reviewed centers. Follow the collection protocol and
   `configs/phone_investigation.example.json`. Keep distinct rig configurations
   separate. No controlled measurements currently exist.
3. Have a custodian reserve disjoint heldouts and independent geometry before
   starting a new G5 investigation. Keep those records outside investigator
   manifests/contexts; never tune against a consumed holdout. Real structural
   acceptance additionally needs a preregistered real-data calibration protocol.
4. Resolve participant-specific eligibility, track, accepted terms, portal fields
   and third-party media submission rights under
   [META_COMPLIANCE.md](../../docs/META_COMPLIANCE.md). Public source checks are
   complete; personal/account obligations remain UNRESOLVED.

Implementation details and operational commands:
[TASK06_IMPLEMENTATION.md](../../docs/TASK06_IMPLEMENTATION.md).
The next engineering phase can collect independent measurements and exercise
the real path; it must retain the present missing-evidence and abstention gates.
