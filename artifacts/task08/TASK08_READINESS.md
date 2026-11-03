# Task 08 verification and delivery

**Software extension: locally verified. Physical evidence: BLOCKED_INPUTS.**

Base: `91613066fe16b725ff0068ba6cae753cfa7392ac`.
Tested implementation: `bfe7981c7b52777490848de2bf13adfb42ba69a6`.
The following delivery commit adds verification metadata only; application,
scripts and tests remain identical to this tested implementation.

## Completed checks

| Check | Actual result |
|---|---|
| Required editable install | PASS after retrying sandbox-denied package-index access |
| Required G1 verifier | PASS: 250 cases, 0 failures, 1,516 transitions |
| MVP before product integration | 8 passed |
| Final native targeted capture/admission/product tests | 45 passed, 1 Linux-only continuation skip |
| Complete scientific/unit/integration suite, clean committed WSL checkout | **385 passed, 17 skipped**, 942.24 s |
| Native Chrome, existing and new browser tests | **15 passed**, 56.47 s |
| JavaScript syntax | Both product and controller PASS |
| Tracked tree and reachable-history credential pattern scan | PASS, 589 historical blobs, no findings |
| Protected numerical source and original G5 artifacts | No diff from the verified baseline |
| Offline phone CLI | BLOCKED_INPUTS with exact missing timing/calibration/review/length/recordings |
| New Meta requests | **0** |

The full suite's skips include opt-in browser tests and native-Windows-only
security branches. Browser tests ran separately in native Chrome. Hardware is
not required in CI: the controller uses injected camera frames, actual H.264
encoding and the existing FFmpeg decoder/PTS preflight in its tests.

## Retained failures and corrections

The first native sandbox full-suite attempt produced 218 passes, 22 skips,
142 fixture errors and 3 failures under temporary-directory ACL/Git/sandbox
restrictions. The unrestricted native product baseline then passed 47 tests.

The initial WSL baseline run produced 369 passes, 15 skips and one source-hash
reproducibility failure because new source files changed during its two report
builds. This is not represented as a successful stable baseline run. The exact
failed test passed from a separate unchanged `9161306` checkout (1 passed,
384.01 s). The final full feature run used a separate immutable committed
checkout and passed all 385 applicable tests. No source edits occurred during it.

Browser testing found the old navigation implicitly switched from phone to
synthetic evidence. Task 08 keeps the phone source through its five views. One
existing regression test now explicitly selects the synthetic source before
its unchanged historical G5 assertions. The new browser tests separately prove
phone-view navigation and saved H.264 playback. No scientific assertion or
registered threshold was weakened.

## Hardware evidence and limits

An actual Windows DSHOW camera at index 0 opened and provided preview frames.
A three-second controller test saved 34 decoded H.264 frames at 640×480.
Observed arrival rate: 11.1067237682 fps; encoded nominal rate: 30 fps.
The report explicitly flags ENCODED_ARRIVAL_TIMEBASE_MISMATCH. This clip is
BLOCKED_INPUTS, physical time UNVERIFIED, SAM NOT_RUN, calibration NONE,
physical model comparison NOT_RUN and independent physical validation NOT_RUN.

Phone identity and pendulum motion are **NOT_VERIFIED**. Physical unplug testing
was not performed; device loss was exercised through an injected camera. Driver
stalls may require restarting the native controller. No real pendulum experiment,
calibrated observation or physical model acceptance is claimed.

The owner's original local pilot path was not supplied. Earlier WhatsApp-video
diagnostics were not rerun or represented as SAM output. The pilot importer and
framing-sample workflow are tested, but actual owner-video inspection remains
pending. Controlled rig measurements, independent physical timing, genuine human
references and a fresh independent custodian/evaluation remain owner inputs.

## Reproduce

```powershell
python scripts/run_live_lab.py --port 8770
python scripts/run_live_lab.py --list-devices
python scripts/run_live_lab.py --import-video "C:\actual\owner\pilot.mp4" --role pilot
python scripts/run_realign.py --port 8772 --phone-output data/processed/task08/phone_smoke --no-browser
python -m pytest -q tests/test_live_lab.py tests/test_live_lab_integration.py tests/test_physical_investigation.py tests/test_task06_product.py tests/vfinal/test_admission_review.py
$env:REALIGN_BROWSER_TESTS='1'
$env:REALIGN_BROWSER_EXECUTABLE='C:/Program Files/Google/Chrome/Application/chrome.exe'
python -m pytest -q tests/test_live_lab_browser.py tests/test_product_browser.py tests/test_task06_browser.py tests/vfinal/test_browser.py
```

The complete suite ran with the existing WSL Python runtime, PYTHONPATH set to
the immutable checkout's `src`, and OPENBLAS_NUM_THREADS, OMP_NUM_THREADS and
MKL_NUM_THREADS all set to 1. The exact command, JUnit counts/hashes, checkout
and runtime paths are recorded in TASK08_VERIFICATION.json. Full suite and
failed-attempt reports, native browser screenshots, private hardware clips and
arrival logs remain under ignored `data/processed/task08/` and
`data/raw/live_lab/`; they are not published as scientific evidence.

The explicitly launched demo instances are capture at `http://127.0.0.1:8770`
and read-only product at `http://127.0.0.1:8772`. No camera opens on page load.
The existing release instance and main branch were left untouched.

See [the demonstration procedure](../../docs/TASK08_LIVE_LAB.md) and
[exact changed files](TASK08_FILES.txt). Remote feature CI was in progress when
this metadata was written; no remote success or merge is claimed here.
