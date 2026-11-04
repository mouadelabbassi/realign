# Developer guide

REALIGN compares observations with executable pendulum models. SAM supplies
source-bound visual observations, Muse requests bounded scientific operations,
and deterministic code computes numerical results. An independent evaluator
assesses a frozen decision. The evidence product and Live Lab are two interfaces
to this application.

## Repository layout

| Location | Responsibility |
| --- | --- |
| `src/realign/physics`, `fit`, `observation` | Mechanics, parameter estimation and observation models |
| `src/realign/perception` | SAM parsing, video timing, calibration, mask QA and review |
| `src/realign/physical` | Capture, Live workers, scientific admission and human actions |
| `src/realign/agent`, `tools`, `contracts` | Muse protocol, typed requests and isolated numerical execution |
| `src/realign/validation`, `audit` | Sealed evaluation, exposure records and hash-linked journals |
| `src/realign/product` | Evidence APIs, claim grading and the browser interfaces |
| `scripts` | Supported launch, inspection, verification and evidence commands |
| `tests` | Numerical, contract, security, integration and browser checks |
| `configs` | Public examples; machine-specific settings use ignored `*.local.json` files |
| `artifacts` | Recorded evidence, reports and historical positive and negative controls |
| `data` | Local inputs and outputs; private recordings, reviews and sealed data stay ignored |
| `docs/plans` | Historical implementation plans |

Editor settings, virtual environments, build output and caches are local files.
They do not belong in a source handoff. Keep `.env` and private data outside commits.
Licenses, attribution, provenance and verification evidence belong with the project.

## Start the interfaces

Use Python 3.11+ and install the project from the repository root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,perception,ui-test]"
python scripts/run_realign.py --port 8766 --no-browser
```

On Linux/macOS, activate the environment with `source .venv/bin/activate`.
The evidence interface at `http://127.0.0.1:8766` replays cached results without
paid model calls or new fitting.

Run capture in a native Windows terminal with FFmpeg/libx264 available:

```powershell
python scripts/run_live_lab.py --port 8772 --log-level DEBUG
```

The Live Lab is at `http://127.0.0.1:8772`. Camera discovery, offline preview and
manual recording make no Meta requests. Go Live requires an explicit target,
upload consent and a spending reserve cap. Keys are loaded on the backend from
`MODEL_API_KEY`; they do not enter browser payloads, journals or terminal logs.
Restart the backend to load Python changes.

## Live control flow

`CaptureController` in `physical/live_lab.py` owns the camera and original MP4s.
It records source frame indices and host arrival timestamps separately from
container presentation timestamps. Continuous capture rotates source clips at
most every 55 seconds; rotation does not end the session.

`LiveInvestigation` in `physical/live_investigation.py` runs separate encoding,
SAM and science workers. The first recorded frame produces a startup image
request. Short video windows follow with adaptive cadence. Bounded queues and
one freshest pending video prevent a backlog when the service is slower than
capture. Repeated content and target pairs are deduplicated. Capture does not
wait for network responses.

Partial streaming masks are presentation evidence only. The overlay uses the
exact delayed source frame and displays age, latency and known or unknown
confidence. Failed streams cannot become completed scientific observations.
Completed empty responses block repeated automatic requests until the operator
revises the target and confirms consent within the remaining budget.

`RequestLedger` reserves before every upload, segmentation, reasoning attempt
and retry. Continuous mode has no duration or request-count cutoff. Its finite
reserve cap remains enforced; amounts use at least .001 USD and at most
microdollar precision. These are owner-reviewed estimates, not verified invoices.
Pause preserves the checkpoint and budget. Revocation blocks new reservations;
already dispatched calls can still bill. Cancellation epochs prevent late
responses from changing the active scientific state.

Original recordings and the complete hash-linked journal remain on disk.
Continuous sessions keep bounded presentation histories and a disk-backed upload
index. `inspect_live_session.py` reads saved evidence without replaying API calls.

## Scientific boundaries

`LiveScientificSession` in `physical/live_science.py` sends eligible pixel
observations to Muse. Empty or unchanged evidence does not require a paid
explanation. Pixel displacement is not metric velocity, and software CFR or
host arrival time is not independently verified physical time.

Metric tools require successful admission of independently timed, calibrated,
reviewed evidence. A human confirms and performs requested experiments; the
controller records a new request-bound response clip. Confirmation alone does
not establish action completion or physical validity. Successful admission
resumes reasoning without a separate reasoning approval button.

The numerical worker accepts typed capabilities through `tools/client.py` and
`tools/registry.py`. It cannot execute arbitrary model-generated code or read
sealed truth. The supported numerical isolation runtime is Linux; Windows
investigator entry points use the WSL bridge. A failed sandbox probe must fail
closed. `AGENTS.md` also serves as an existing forbidden-file probe target, so
it remains part of the repository.

Physics uses x right and y up, with downward gravity. Pivot and string length
are constant within each mode. Ideal peg contact conserves Cartesian tangential
speed; slack is rejected. Preserve explicit pixel, metre, time and covariance
units. Fit on permitted exploration trials, freeze the decision, then evaluate
on independently sealed data. Keep synthetic, external and phone domains distinct.

## Debugging and verification

INFO logs cover capture state, reservations, API attempts, safe failures,
scientific activity and human-action transitions. DEBUG adds frame sequences
and dimensions. Raw API bodies, prompts and media payloads are excluded from
terminal telemetry. Expand the UI audit records or inspect the local journal
for scientific details.

Run the complete numerical suite on Linux/WSL with constrained numerical threads:

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
python -m pytest -q
python scripts/verify_g1.py
```

Run browser checks with injected cameras and mocked APIs:

```powershell
python -m playwright install chromium
$env:REALIGN_BROWSER_TESTS='1'
python -m pytest -q tests/test_product_browser.py tests/test_task06_browser.py tests/vfinal/test_browser.py tests/test_live_lab_browser.py
```

An installed Chrome can be selected with `REALIGN_BROWSER_EXECUTABLE`.
Fixture clocks coordinate with local encoding when preparing windows; they
never wait for held SAM responses to prove continued capture. Preserve negative
controls, missing-input blockers and failed historical runs. Mocked tests do not
establish real hardware, paid API or independent physical success.

CLI module docstrings remain because they supply help text and can contribute
to runtime schema descriptions. Third-party source and license notices remain
verbatim. Development explanations belong in these guides rather than inline
comments in first-party code.
