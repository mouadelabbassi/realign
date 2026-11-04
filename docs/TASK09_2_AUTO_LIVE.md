# Task 09.2 — Automatic Live Lab

The native controller now supports a server-authorized `AUTO_LIVE` session:
**review target and spending cap → Go Live → automatic capture → startup SAM image → background
SAM video windows → automatic eligible Muse reasoning → human experiment →
independently admitted response → automatic continuation**.

This is an implemented software path verified with explicit `TEST_FIXTURE`
frames and mocked Meta transport. Its real hardware/Meta milestone is still
**NOT_TESTED**. No new paid Meta requests were made during implementation.
The earlier real failure remains a failure; this change does not recertify it.

## Run

Use a native Windows terminal in the repository, with Python 3.11+ and FFmpeg
with libx264 on PATH. The numerical worker uses the existing supported WSL
bridge when independently admitted numerical evidence is available.

```powershell
python -m pip install -e ".[dev,perception,ui-test]"
python scripts/run_live_lab.py --port 8772
```

Open **http://127.0.0.1:8772**. Stop an older Python controller or choose a free
port; refreshing static files alone cannot load new backend code.

1. Select **Find cameras** to search camera inputs 0–7. This local scan never
   uploads, records or authorizes paid calls. Select the detected input; **Connect**
   is available to identify your phone in an offline preview. The backend supports
   an extended scan of up to 16 indices. A driver-open result alone cannot identify
   the phone. No-device guidance covers permissions, USB and webcam apps.
2. Open **Go Live**, enter and confirm your intended visible target, set a finite
   USD spending reserve cap and owner-reviewed per-attempt SAM/Muse estimates,
   and confirm upload consent and Standard tier. Select the setup's **Go Live**.
   This one action authorizes the session, connects the selected camera if needed
   and starts recording. An existing manual recording is saved at a source boundary
   before automatic capture begins. The first recorded, source-mapped frame is
   saved as a PNG and sent to SAM without waiting for an MP4 window. There is no
   second Connect, Start AI or Approve Investigation Event step.
3. Watch the camera stage and its exact-source SAM inset. New completed, usable
   observations trigger Muse automatically within the same authorization.
4. When an experiment appears, review its parameters. Select **I am ready to
   perform this action**, then physically perform it. Auto-Live starts a fresh
   response clip bound to the exact request. This confirms human intent, not
   actuation, completion or scientific validity.
5. Supply independent timing, measured geometry, a stationary reference,
   hash-bound independent human reviews and distinct exploration trials in an
   approved phone manifest. Expand **Supply independent evidence** and select
   **Validate evidence and continue**. Only successful admission resumes Muse;
   no manual reasoning restart is needed. Confirmation alone never bypasses it.

**Pause AI**, **Revoke API calls** and **Stop and analyze** are independent.
Pause/resume preserves the budget and checkpoint. Revocation is irreversible
for that controller and prevents further reservations; in-flight calls may still
bill. A new controller is needed for a fresh session authorization. Offline
preview, manual capture, MP4 import and the original five-view read-only evidence
product remain available (`python scripts/run_realign.py --port 8765`).

## Provenance and presentation

- The documented [SAM image input](https://dev.meta.ai/docs/sam/segmenting) uses
  `input_image.image_url` with a local PNG data URL. Video retains the existing
  Files API/MP4 workflow. Both use the official `meta-sam-parser` 0.1.0, with its
  image and video formats respectively. Confidence is requested; absence remains
  **unknown**, never zero or an invented confidence score.
- Startup PNG, manifest, safe completed receipt, raster cache and result are
  saved under `live-*/startup-*/`. The manifest binds the PNG hash, processed and
  original frame hashes, recording ID/index, software arrival timestamp, target
  phrase and revision. Startup image receipts are not put in the numerical
  video-admission cache. Original clips/arrival sidecars keep their own hashes.
- Complete, parser-validated streaming records can update the presentation
  before the terminal event. **SAM_CONFIRMED** means an authentic parsed SAM
  segmentation for that source frame; a **partial stream** is presentation-only.
  It never enters the trajectory mailbox or scientific evidence. A failed or
  cancelled partial stream becomes **TRACK_LOST**, not completed evidence.
- Masks and boxes are drawn on the exact saved frame in the live camera stage's
  source inset. Source-frame age, service latency, confidence and
  **UNVERIFIED_TIMING** are visible. Historical pixel points are source-bound;
  paths do not silently join identities across responses. No local optical-flow
  estimate is implemented or represented as a SAM measurement. No uninterrupted
  remote tracking or subsecond latency is claimed.
- A completed zero-mask result reports **NO_TARGET_OBSERVED**, keeps recording
  and blocks more automatic SAM requests as well as empty-evidence Muse calls.
  **Authorize revised target** requires a changed phrase and fresh consent for
  additional requests within the original remaining spending cap. It does not reset
  the reserve ledger or silently retry the same prompt.
- The UI starts with four-second windows every twelve seconds; the controller
  adapts the cadence to observed throughput.
  Auto-Live raises its effective interval to at least 1.25 times the last
  observed whole-response service time (capped at 120 seconds). One freshest
  pending video replaces stale work; identical content plus prompt is not
  uploaded again. **Continuous Live has no session duration, recording-count,
  video-window-count or SAM/Muse request-count cutoff.** Original capture rotates
  into source-bound clips of at most 55 seconds and continues until stopped,
  disconnected or a local capture/storage error. Rotation is a storage boundary,
  not a session deadline. Every upload, retry and reasoning attempt still reserves
  against the finite spending cap before dispatch; exhausted authorization blocks
  new paid calls while capture can continue. Pause/revoke, evidence admission,
  bounded queues, finite retries, per-request payloads and numerical tool budgets
  remain enforced. The legacy explicit bounded API remains available.
- Continuous sessions keep bounded audit/trajectory/conversation tails in RAM and
  a disk-backed submitted-content index. Complete source recordings, measurements,
  request receipts and the full hash-linked journal remain on disk. Context
  compaction retains current approved evidence and hypotheses, and never removes
  unresolved tool calls. Stop the session before local storage is exhausted.
- Scientific narrative uses one offline Markdown renderer in the live workspace
  and existing five-view product: headings, paragraphs, emphasis, lists/tasks,
  tables, quotes, links, fenced/inline code and inline/display LaTeX math.
  Bundled Marked + DOMPurify sanitize output; KaTeX uses `trust: false` with
  bounded expansion. Executable HTML, unsafe links and remote images are
  disabled. Raw JSON, identifiers in literal code fields, input values and SVG
  plot labels stay literal. Raw records are expandable, not the primary science
  presentation. Bundled versions and licenses live in `product/static/vendor/`.
- Muse receives bounded actual pixel samples, bounds and displacement with
  source references, not just a mask count. After overlap identity agreement in
  the same source/pixel space, a >45-degree sampled direction change or a clear
  displacement change can trigger reasoning below the regular 20-new-sample
  threshold, still subject to the two-second cooldown. This is a scheduling cue
  only; no physical velocity, model discrepancy statistic or validation result
  is inferred from software timing.

## Terminal debugging

Run the native backend in a terminal to see timestamped, structured lifecycle,
camera discovery/state, authorization reservation, SAM HTTP/partial/final result,
Muse HTTP/reasoning, scientific tool/admission, pause/revoke and safe failure codes.
Use DEBUG for per-frame source sequence and dimensions:

```powershell
python scripts/run_live_lab.py --port 8772 --log-level DEBUG
```

Logs omit credentials, request/response bodies, prompts and image/video payloads.
Raw SDK logging is not enabled. The local evidence journal retains the scientific
records for inspection. Logging does not authorize APIs: ordinary preview,
Find cameras and manual recording remain offline until explicit Go Live consent.
Reserved USD amounts are owner estimates, **not a guarantee of actual Meta billing**.

## Verify without hardware or paid services

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
python -m pytest -q tests/test_continuous_live.py tests/test_auto_live.py tests/test_live_investigation.py tests/test_live_repair.py tests/test_perception.py tests/test_live_lab.py tests/test_live_lab_integration.py
```

Full numerical regression uses Linux/WSL, matching CI's supported worker
isolation. Run `python -m pytest -q` there with the same thread limits.

```powershell
python -m playwright install chromium
$env:REALIGN_BROWSER_TESTS='1'
python -m pytest -q tests/test_product_browser.py tests/test_task06_browser.py tests/vfinal/test_browser.py tests/test_live_lab_browser.py
```

An installed Chrome can instead be selected using
`$env:REALIGN_BROWSER_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'`.
Tests inject the camera and mock SAM/Muse; they do not open the physical camera
or construct an authenticated remote client. The browser suite proves automatic
image detection/reasoning/action, checkpoint retention, slow-response capture,
zero unauthorized spend, zero-mask blocking, pause/revoke and safe Markdown/math
in both products. Read-only forensic inspection also verifies startup evidence:

```powershell
python scripts/inspect_live_session.py <stopped-live-session> --output data/processed/task092/forensic.json
```

## Verification boundary

| Milestone | Status |
| --- | --- |
| Mocked end-to-end automatic software flow | PASS (TEST_FIXTURE only) |
| Real hardware, patched Auto-Live | NOT_TESTED |
| Real Meta SAM, patched Auto-Live | NOT_TESTED |
| Real Muse, patched Auto-Live | NOT_TESTED |
| Independent physical G2/G5 | BLOCKED_INPUTS |

The final local verification receipt and PR CI link record exact regression
results. The physical milestone remains open until separately approved, genuine
phone/Meta testing with fixed pivot/camera, a reviewed visible circular target,
independent exposure timing, measured calibration, independent annotations and
genuinely distinct exploration recordings. Numerical kernels, shape thresholds,
sealed validation and historical G5 evidence are unchanged.
