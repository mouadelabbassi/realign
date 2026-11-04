# Task 09.2 — Automatic Live Lab

The native controller now supports a server-authorized `AUTO_LIVE` session:
**authorize once → connect → automatic capture → startup SAM image → background
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

1. Select **Set up Auto-Live**. Enter one descriptive intended target phrase,
   confirm it, review the window strategy, and set SAM/Muse attempt caps, an
   estimated USD ceiling and owner-reviewed per-attempt reserves. Confirm upload
   consent and Standard tier. Select **Authorize Auto-Live** once.
2. Select **Find cameras** to scan camera inputs 0–7. The labeled button shows
   search progress, populates the device selector with detected indices/backends,
   and reports permission/connection guidance if none are found. Scanning opens
   and releases local probes; it never uploads video, starts capture or spends
   API authorization. The backend accepts a bounded `maximum` up to 16 for an
   extended scan. A driver-open result does not identify the phone: select
   **Connect** and verify the preview. Capture
   starts automatically. The first recorded, source-mapped frame is saved as a
   PNG and sent to SAM immediately, without waiting for an MP4 window. There is
   no second Start AI or Approve Investigation Event button.
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
  additional requests within the original remaining limits. It does not reset
  caps or silently retry the same prompt.
- The initial four-second window/every-twelve-second strategy is configurable.
  Auto-Live raises its effective interval to at least 1.25 times the last
  observed whole-response service time (capped at 120 seconds). One freshest
  pending video replaces stale work; identical content plus prompt is not
  uploaded again. Original capture rotates at most sixteen 55-second clips per
  controller. Skips, queue lag, errors and coalescing remain inspectable.
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

## Verify without hardware or paid services

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
python -m pytest -q tests/test_auto_live.py tests/test_live_investigation.py tests/test_live_repair.py tests/test_perception.py tests/test_live_lab.py tests/test_live_lab_integration.py
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
