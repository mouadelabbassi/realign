# Task 09 — Concurrent Live Investigation

## Run

```powershell
python -m pip install -e ".[dev,perception,ui-test]"
python scripts/run_live_lab.py --port 8770
```

Open http://127.0.0.1:8770, connect and identify the phone, then start ordinary
recording. This remains offline. Expand the authorization panel, review the
SAM 3.1/Muse Spark 1.3 models, upload strategy, caps and estimated USD reserves,
confirm Standard tier and explicitly authorize AI. The backend reads
`MODEL_API_KEY` from its environment, or loads only that key from local `.env`
after authorization when a model is first needed. No key enters the frontend.

For the numerical worker on Windows, install the existing supported Ubuntu/WSL
runtime once with `python scripts/setup_investigator_runtime.py`. Capture remains
native Windows. A fixed stdio bridge uses the same isolated `WorkerClient`
under WSL; it introduces no service, second investigator or alternate physics.
Linux uses that worker directly. Failed isolation is never bypassed.

## Implemented pipeline

The existing camera owner writes the original local capture and software-arrival
sidecar. It offers downscaled samples through a nonblocking bounded queue to a
separate window encoder. Separate SAM and scientific workers consume finalized
windows and immutable observation snapshots. No network response is awaited by
the camera thread. The normal local writer can still be limited by disk/encoder
or driver performance; this is not a hard real-time camera guarantee.

Defaults are four-second arrival-clock windows, 0.5-second overlap, 12 Hz maximum
sample rate, at most 640×480 pixels, eight queued frames and two queued windows.
Each worker is independent. Window length, overlap, sample rate, queue bounds,
timeout and total window count have validated server-side configuration bounds.
The UI exposes length and overlap; other settings can be supplied in `windowing`
to `/api/ai/start`. Defaults are an initial test configuration, not a claim of
measured hosted-service throughput. Original local capture retains the existing
55-second limit per recording; a new recording can feed the same investigation.
Up to 128 windows are finalized per authorization. Drops and saturation are
explicit telemetry; skipped finalized clips remain on disk.

SAM uses the existing official Meta Files/Responses adapter and
`meta-sam-parser`, with at most two attempts per operation and a 90-second
per-window deadline. The hosted API accepts a submitted MP4 and streams its
response; this application does not claim an unbounded camera-stream API.
Reference: https://dev.meta.ai/docs/cookbook/sam-api-basics.
Malformed, partial, empty and failed responses cannot become complete validated
tracks. Camera recording continues through these failures. There is no RGB
detector fallback. The existing contour/identity/area checks operate on SAM masks;
the physical speed gate is disabled for preliminary software-CFR windows.

Each `data/raw/live_lab/live-*/window-*/` folder retains an input MP4, its hash,
integer PTS, window/source frame map, independent arrival clock labels, processing
transform, source identity, masks, parser/API receipt and outcome. Frame-map rows
also retain the hash of each pre-encode processed frame. Finalization of the
original recording adds its source MP4 hash, arrival-sidecar hash and original
PTS to the journal. Mask/index and result hashes bind consumed observations to
the append-only hash-linked `timeline.jsonl`.

Overlaps deduplicate on recording ID, capture sequence and arrival timestamp.
Consumed coordinates never get overwritten. SAM object IDs remain response
scoped: a following window only reports continuity when overlapping source
frames agree in object ID and position; otherwise it reports discontinuity.
Distinct windows from one source recording cannot count as independent trials.

## Timing and physical admission

`HOST_MONOTONIC_ARRIVAL_AFTER_READ` is a software observation, not camera exposure
time. `SOFTWARE_CFR_PLAYBACK` is an encoded-media clock, not independently verified
physical time. Neither sampling frequency nor nominal FPS grants metric fitting.
Live output starts as `PRELIMINARY_OBSERVATION`, in processed-frame pixels.

Supply an approved local phone manifest through the workspace admission control.
It calls `ingest_phone(run_api=False)` and reuses the existing calibration,
independent human reviews, noise/release checks and controlled-phone provenance.
No admission request can start an additional SAM call. Hash-indexed live caches
are in `live-*/sam_cache/`. Original phone imports can use existing actual caches;
all missing inputs remain explicit blockers.

For any live-CFR exploration window, a bare `capture_time_scale_verified` flag
is insufficient. The manifest must additionally map its video hash to an
independent exposure reference JSON through `live_window_timing`. That reference
must bind the exact window manifest hash and source capture sequence, identify
the independent instrument, declare `source: INDEPENDENT_EXPOSURE_MEASUREMENT`
and `independent_of_encoded_fps: true`, and supply `uncertainty_s` and a `frames`
array of `{capture_sequence, exposure_time_s}`. Exposure times must be finite,
strictly increasing, their uncertainty below a tenth of the smallest exposure
interval, and their relative timeline must agree with original window PTS within
twice that declared uncertainty. A mismatch blocks admission. This check does
not manufacture an exposure reference or retime a mismatched MP4. Independent
instrument validity and human attestations still require operator review.

## Running investigation and human actions

The single persistent Muse adapter is scheduled on at least twenty new unique
observations, informative identity changes (at most once every two seconds), an
admitted snapshot or an operator-approved event. It is never called per frame.
Preliminary evidence references bind visual snapshots/calibration status only;
no metric tools can execute without admitted `VideoTrial`s. Muse can request a
typed stationary reference or camera calibration, or abstain.

After admission, the existing `ScientificSession`, `Investigator` context,
state machine, five bounded tools, budgets, model families and `PhysicalValidator`
are reused incrementally. The calibrated nominal overlay uses the existing free
predictor, without optimization or holdout access. All actual proposals and tool
outputs are journaled. A decision must pass the existing physical validator;
real structural repair remains blocked by the existing lack of a registered
physical structural calibration. No sealed trials, thresholds or consumed
holdouts are read or changed. Live decisions do not claim independent G5.

A typed requested action appears exactly in the UI. The operator must confirm it;
subsequent frame maps bind the request ID. The budget, conversation, hypotheses,
context hashes and audit chain persist. Confirmation does not admit a response.
An independently admitted response must bind `response_to_request_id`; calibrated
responses use the existing physical response checks before the same session
continues. There is no autonomous actuator. The investigation retains its one
experiment/two-round contract.

## Authorization, accounting and stopping

Authorization uses the existing loopback/origin/unpredictable-token boundary.
The server validates separate SAM and Muse attempt caps (1–32 each), positive
owner-reviewed per-attempt USD reserves and a positive estimated spending ceiling
(at most USD 100). Every upload, segmentation and Muse attempt reserves its
quota atomically and journals/fsyncs the reservation **before** SDK dispatch.
Failures, retries and unknown interrupted attempts are not refunded. SDK internal
retries remain disabled. There is no unbounded billable queue.

Reserves enforce an authorized **estimated spending** ceiling. They are supplied
by the owner and are not verified Meta prices or a provider billing guarantee.
Actual billed costs may differ; in-flight requests may still bill. Set the
provider account's own spending controls when a hard billed-dollar cap is needed.
The UI reports attempts and reservations rather than invented billed totals.

`Stop AI calls` revokes new attempts immediately, independently of other controller
actions, cancels the asynchronous SAM stream and leaves ordinary recording active.
A Muse result arriving after stop is recorded but not applied. Camera disconnect
also stops AI. Reauthorizing within the same controller cannot silently reset a
budget. `/api/investigations` inspects existing journals without issuing calls.

After a process interruption, artifacts and conservative reservations remain
inspectable; no action, network request or scientific decision automatically
replays. Automatic reconstruction of an in-memory live numerical session after
process death is not implemented. Continue reviewing the preserved evidence or
use the existing separately authorized physical checkpoint workflow. This is a
safe stopped recovery, not an assertion of transparent process-level resume.

## Verification and limits

Run deterministic tests with no credentials or hardware:

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
python -m pytest -q
python scripts/verify_g1.py
$env:REALIGN_BROWSER_TESTS='1'
python -m playwright install chromium
python -m pytest -q tests/test_product_browser.py tests/test_task06_browser.py tests/vfinal/test_browser.py tests/test_live_lab_browser.py
```

Tests inject explicitly labeled `TEST_FIXTURE` frames and mocked Meta transports,
while running real H.264 finalization, integer-PTS probing and the official SAM
parser. They cover four-second overlapped windows under a held SAM response,
failed uploads, partial/empty streams, queue saturation, timeout, cancellation,
immutable overlap deduplication, object-ID changes, request caps/retries,
interrupted/tampered journals, timing mismatch, human confirmation and calibrated
tool admission. Browser tests demonstrate recording, a delayed processed frame,
an exact physical request and AI stop while capture continues.

Release measurements and exact test counts are recorded in
`artifacts/task09/VERIFICATION.json`. The committed fixture timeline and screenshot
are software demonstrations, not camera/SAM/Muse service performance measurements.
No real hardware or Meta request was authorized for Task 09. Real service latency,
phone identity, independent exposure timing, physical calibration and independent
physical G2/G5 remain unverified. Earlier Task 08 hardware results do not validate
this concurrent pipeline.
