# Task 09.1 — Failed live investigation: diagnosis and repair

## Saved evidence, inspected without model calls

Baseline: `c7c4151d9d6e09c93034fc532d69c7587f13960c`. The owner's stopped
session was inspected locally, including six original window MP4s, manifests,
SAM cache/index/arrays, result records, the original 609-frame recording,
arrival sidecar and hash-linked timeline. The inspection verified 33 files
unchanged. No real media, raw model responses or credentials are published here.
During the later validation, the existing controller appended one
`CAMERA_DISCONNECTED` stop event. The initial 29-event journal prefix remained
byte-identical and the other 32 files remained unchanged. No forensic process
rewrote that journal; both inspection states are retained locally.

Evidence anchors:

| Record | SHA-256 |
| --- | --- |
| Original captured MP4 | `04a1a90aa4dd458466c791b8c48cd9d4295117f37342ad0dcd688b5aff482ec5` |
| Window 0001 MP4 | `e97f9c06bdec5570ff7f7835ae6d67cd1a026c2e154daf9199f8cafde15e7949` |
| Initially inspected 29-event timeline prefix | `890a1895c33e282d9dc5a71eda0d2160176d62e71b97e4e898aa93a8bef4fb1a` |

### What failed

- Window 0001's actual completed `sam-3.1` response returned **zero mask
  records**, with zero parser diagnostics. The saved mask index is empty.
  Replaying those exact cached results gives 42 missing frames, zero valid
  centers, and zero shape/area/identity/confidence rejections. Lowering contour
  thresholds cannot repair this empty detection.
- The prompt was the fixed `the pendulum bob`. Frames were reduced from
  1280×720 to 640×360, preserving embedded black padding: scale 0.5 in both
  axes. Human inspection shows a small blue-grey suspended object, sometimes
  blurred, in a cluttered scene. It does not establish that the model recognized
  the intended target, or that the target has a usable circular silhouette.
  Prompt mismatch, framing and visibility are plausible contributors; the saved
  response does not establish which caused the zero-mask outcome.
- One upload attempt recorded `_DeadlockError`, then a retry and segmentation
  completed. CPython defines this as an import-lock deadlock error; the absence
  of an HTTP status and concurrent first SDK uses are consistent with a local
  initialization problem, not proof of a remote HTTP rejection. No stack was
  preserved, so its exact import dependency cannot be reconstructed.
  See [CPython import locking](https://github.com/python/cpython/blob/3.14/Lib/importlib/_bootstrap.py).
- The recorded 10.8256 seconds is **whole-window service time**, including
  upload/retry and parsing, not an isolated segmentation latency. The first
  window also waited 5.9405 seconds; the second waited 13.1303 seconds. This
  exceeded the configured 3.5-second window-start cadence. Windows 4–6 were
  explicitly skipped on queue saturation; window 2 was cancelled after stop,
  and window 3 has no processed result.
- All three scientific rejections were operator events. Legacy readiness
  allowed an operator event to invoke Muse without usable observations. The
  two-slot scientific queue could fill while `next()` blocked. The owner
  reported two dropped events, but their individual records were not journaled;
  the exact dropped events cannot be recovered from the saved timeline.
- Each Muse rejection retained only `AdapterFailure`. Its typed code, HTTP
  status and adapter receipt were discarded. **Whether those three failures
  were HTTP, transport or structured/tool-protocol errors is indeterminable
  from the saved evidence.** This repair does not invent a retrospective cause
  or claim an untested endpoint fix.
- The legacy `OVERLAP_AGREEMENT` on an empty result was a boolean error:
  `not self.trajectory` was true even when there were no rows to compare.

Five SAM and three Muse attempts were reserved, totaling estimated USD 0.532.
This includes the local upload failure and interrupted work. Actual provider
billing and exact successfully dispatched HTTP counts remain unverified.
No usable trajectory, Muse hypothesis, scientific tool result, physical action
or model comparison was produced. This was not real end-to-end scientific success.

## Repairs

- The operator selects and confirms a visually grounded target phrase before
  real uploads. It is immutable for the authorization and bound to each window
  manifest and SAM receipt. Processing width is explicitly selectable at 640,
  960 or 1280 pixels, preserving aspect ratio, source padding and frame maps.
- Diagnostics expose returned masks and IDs, valid/missing/rejected frames,
  original QA flags, prompt binding, processing scale and mask-based size when
  available. Zero masks are distinguished from rejected masks and ambiguous
  identities. A first nonempty window is unverified; empty windows report
  `NO_OBSERVATIONS`, never overlap agreement. Semantic identity is not invented.
- Circular contour/area/confidence criteria are unchanged. No RGB detector,
  synthetic substitute or relaxed shape threshold was added.
- Empty observations produce a clearly labeled deterministic local readiness
  explanation and operator guidance. They do not construct a Muse client or
  reserve Muse attempts. Unchanged evidence cannot repeat a failed Muse call.
  New valid observations or newly admitted numerical evidence can enable Muse.
- Failures retain closed diagnostic fields: code, category, safe HTTP status,
  exception type and safe receipt hashes/outcomes. HTTP/transport/SDK failures,
  model-protocol rejection and scientific admission rejection are distinct.
  Raw messages, response bodies, headers and credentials are not logged.
- A tool round refused by the controller is closed with explicit
  `LOCAL_CONTROLLER_GATE`, `executed: false` feedback. It emits no numerical
  result or evidence reference. New eligible evidence can resume the same Muse
  conversation instead of leaving it permanently waiting for an unavailable tool.
- The UI initially proposes nonoverlapping four-second windows starting every
  twelve seconds. This is a conservative starting policy informed by the saved
  service time, not a throughput guarantee. The low-level configuration retains
  explicit overlapping cadence when `analysis_interval_s=0`. Other configured
  intervals must be at least window duration minus overlap.
- One freshest pending SAM window replaces stale pending work. Every skipped
  window remains saved with a reason and zero new attempts. A content-hash plus
  prompt key prevents redundant uploads within an authorization, including
  retries through later identical windows. Original capture is independent.
- Scientific snapshots coalesce in one bounded latest slot, preserving cumulative
  unique-observation accounting. Operator/admission controls have a separate
  bounded queue and priority. Rejections and coalescing are journaled. HTTP
  controls report `COALESCED` honestly. Human confirmation and AI stop are not
  silently discarded behind a slow frontend refresh.

SAM still uses the existing official parser and hosted MP4 workflow, as described
in [Meta's SAM API reference](https://dev.meta.ai/docs/cookbook/sam-api-basics).
No new paid Meta calls or physical-camera tests were performed for this repair.

## Reproduce offline

The following reads saved bytes and cached masks only. Choose a stopped session
containing `timeline.jsonl`; incomplete authorization directories are not evidence.

```powershell
python scripts/inspect_live_session.py data/raw/live_lab/<live-session> --output data/processed/task091/forensic.json
```

Output must be outside the original recording library. The reader validates the
audit chain, window/source hashes, consumed result hashes, mask cache and original
recording/arrival hashes. It never rewrites originals or constructs a model client.
The legacy empty response remains empty on replay; that is the expected result.

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
python -m pytest -q tests/test_live_repair.py tests/test_live_investigation.py
python -m pytest -q
$env:REALIGN_BROWSER_TESTS='1'
python -m pytest -q tests/test_product_browser.py tests/test_task06_browser.py tests/vfinal/test_browser.py tests/test_live_lab_browser.py
```

`TEST_FIXTURE` tests use mocked Meta transport and the official stream parser.
They verify empty/valid/invalid masks, immutable source-bound trajectories,
prompt binding, no repeated empty-evidence Muse spend, typed safe failures,
coalescing/control priority, cadence, duplicate suppression and capture under slow
SAM. The original evidence and historical G5 records are not test write targets.

For the UI, run `python scripts/run_live_lab.py --port 8770` after stopping an old
controller, or use another free port. A running Python backend must be restarted
to load this repair; replacing static files alone does not update imported code.
Recording remains offline until a fresh explicit authorization.

## Owner-dependent prerequisites

Before separately approving a new paid test, review the visible target phrase
and its circular silhouette, size, contrast and motion blur. Fix the camera and
pivot rigidly; the saved clip's hand-held support and moving framing cannot
establish that requirement. Supply measured geometry, an independent exposure
timeline, a stationary reference, hash-bound independent human annotations and
genuinely distinct exploration trials through the unchanged admission gate.
Software CFR and arrival clocks do not become physical time through this repair.
Independent holdouts, registered thresholds, numerical kernels and historical
G5 evidence are unchanged. No real repair or real end-to-end success is claimed
until the owner tests the repaired system with phone and Meta services.
