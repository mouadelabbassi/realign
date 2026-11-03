# Task 08: local operator-assisted physical lab

This extension starts from verified main `91613066fe16b725ff0068ba6cae753cfa7392ac`
on `feature/live-physical-lab`. The original local worktree was clean on
`release/vfinal` at `a6052a7`; that branch and main were preserved. The build
spec's five layers remain unchanged. Task 08 explicitly permits a separate
localhost capture controller, while the evidence product remains read-only.

## Inspected implementation and checkpoint results

Reviewed AGENTS.md, architecture, roadmap, collection protocol, Task 06,
release-readiness, product, perception and physical orchestration. Existing
`probe_video`/`iter_video_frames`, SAM adapter, ingestion, ScientificSession,
PhysicalEnvironment, checkpoint validation, prefix replay and independent
evaluation are reused. No second tracker, numerical engine, agent or validator
was introduced. G1–B3 numerical source and original G5 artifacts are unchanged.

Stage 0 required install succeeded after the initial sandbox network denial.
`python scripts/verify_g1.py`: PASS, 250 cases, zero failures, 1,516 transitions.
Fresh reports were preserved under ignored `data/processed/task08/baseline_g1`;
the verifier's original tracked outputs were restored byte-for-byte.
The first native sandbox `pytest -q` attempt produced 218 passes, 22 skips,
142 fixture errors and 3 failures: temporary-directory ACLs, Git safe-directory
and sandbox restrictions prevent treating that attempt as baseline verification.
The unrestricted native product baseline passed 47 tests. Complete WSL baseline
and final regression results are recorded in the Task 08 verification report.

Checkpoint A: capture/import core passed eight tests before product integration.
Checkpoint B: HTTP origin/token checks, offline admission and read-only product
projection passed thirteen tests. An actual Windows DSHOW camera 0 was enumerated,
previewed and recorded: 34 H.264 frames, 640×480, about 11.1 arrival fps and
30 encoded fps. The phone identity and pendulum motion were NOT_VERIFIED.
This is hardware-access evidence only, not a controlled physical experiment.
Physical disconnection is tested with an injected device; unplug testing remains
owner-operated. Browser test images use explicitly injected frames, never
physical evidence. Browser screenshots and local hardware reports stay ignored.

The owner has not supplied a local pilot path in this session. The earlier
16.25 s / 335-frame / 478×850 and classical detection counts remain provisional;
they are not this implementation's findings and are not SAM measurements.

## Run locally

Install Python 3.11+, the existing perception dependencies and FFmpeg with
`ffmpeg` and `ffprobe` on PATH. Run capture natively on Windows, outside WSL:

```powershell
python -m pip install -e ".[dev,perception,ui-test]"
python scripts/run_live_lab.py --list-devices
python scripts/run_live_lab.py --port 8770
```

No device opens on page load. Click Find cameras, identify the phone, Connect,
then Start recording / Stop and analyze. Devices are indexed through OpenCV
DSHOW on Windows; enumeration does not identify phone make/model. Scan probes
indices 0–5; connect supports indices 0–15. For import-only use:

```powershell
python scripts/run_live_lab.py --import-video "C:\actual\owner\pendulum.mp4" --role pilot
```

Replace the placeholder with the actual owner-supplied path. Exit 2 means
BLOCKED_INPUTS, including when media preflight succeeds. Invalid/nonexistent
paths exit 1. The browser also accepts the original local path. It copies bytes
without transcoding and verifies SHA-256 before/after. Imported and recorded
MP4s use the same original PTS parser and full decoder-count validation. Valid
VFR is reported and retained; missing/reversed/duplicate PTS are rejected by
the existing parser. Clips above the existing 60-second limit remain blocked.

Each unique `data/raw/live_lab/clip-<uuid>/` contains:

- `recording.mp4`, retained locally and ignored by Git;
- `provenance.json` binding source, operator declarations and file hash;
- `arrivals.jsonl` for camera captures, ordered frame index, capture sequence
  and host monotonic nanoseconds after `read()`;
- `capture.json` with arrival-rate/gap statistics, encoded FPS, stop reason and
  sidecar SHA-256; `capture_in_progress.json` retains the initial crash marker;
- `report.json` with original integer PTS/time base, decoded count, dimensions,
  framing-review requirements and exact physical-input blockers;
- five clean framing samples and `phone_manifest.draft.json` using the existing
  controlled-phone grammar, with missing measurements left null.

No detector is run in pilot analysis. Samples support human framing inspection,
not automatic pivot-motion or bob-coverage certification. Human tracking review
is still performed by the existing independent frame workflow after SAM.

## Timing, failure and admission boundaries

H.264 is encoded at software CFR for portable playback. Every frame read is
written in order with no interpolation or nominal-FPS timestamp substitution
in analysis. Camera exposure timestamps and hardware frame counters are not
available through this integration. Arrival intervals, encoded PTS and physical
time must not be conflated. A >10% arrival-span/playback-span difference is an
explicit blocker. Even agreement does not independently validate capture time.
Prefer an original phone recording with independent timing references for
scientific use. Gap indicators use >1.5× median interval; exact dropped frames
remain unknown. There is no audio synchronization or rolling-shutter correction.

Recording stops at 55 arrival seconds or 55 encoded seconds, conservatively
inside the existing media limit. Missing frames/resolution changes finalize the
partial clip and fail the controller. Writer/disk errors fail closed. A stalled
driver is flagged after three seconds without a frame; OpenCV device drivers
do not guarantee bounded blocking reads, so a wedged driver may require stopping
the terminal and reconnecting the camera. Unfinalized folders remain local for
manual recovery and never enter accepted evidence. Use one controller process.

Software capture is available without MODEL_API_KEY. The HTTP controller has
loopback binding, exact Host/Origin validation, no CORS, an unpredictable control
token and fixed file routes. It has no paid-call or scientific execution route.
It does not read keys. The evidence API only reads local saved reports. Import
and camera capture cannot promote a clip to ANALYSIS_READY or RESPONSE_RECORDED.

## Reuse the existing science and physical response loop

Assign stationary/exploration roles before analysis; combine their draft records
in one local phone manifest. Supply the actual measured length/calibration,
separate check points, independent physical timing verification, twenty
hash-bound human centers per clip, release brackets and bounded analysis windows
as specified in REAL_DATA_COLLECTION_PROTOCOL.md. `rig_id` and an MP4 hash are
operator provenance, not proof of controlled geometry. A hand-held pivot or
incomplete framing requires re-recording or a scientifically justified window;
no unchecked pilot is silently admitted.

Per-clip draft video paths are relative to their containing folder, so the drafts
work on both Windows and the existing WSL runtime. When moving records into a
combined manifest under `configs/`, rebase video paths to
`../data/raw/live_lab/clip-<uuid>/recording.mp4`; use forward slashes. Do not put
Windows absolute paths inside a manifest that will execute under WSL.

```powershell
# Offline/cache-only commands; missing inputs are reported explicitly.
python scripts/process_recordings.py configs/phone_investigation.local.json
python scripts/investigate_recordings.py configs/phone_investigation.local.json --output-dir data/processed/phone_investigation
python scripts/run_realign.py --port 8766 --phone-output data/processed/phone_investigation --no-browser
```

Only after explicit account authorization, existing `--run-api` uploads complete
MP4s through SAM 3.1. Optional `--live --standard-tier-confirmed` authorizes Muse
Spark 1.3. These flags can incur charges and external data transfer. Review the
manifest's selected clips, Budget call/token limits and Standard-tier settings
before executing them. Current request counts/receipts are reported by the
existing runtime; billed cost remains UNVERIFIED. No calls were authorized or
made by Task 08. No continuous video-stream inference is implemented.

When Muse requests an action, the original runtime saves its hash-checked
checkpoint and halts. Record the actual action with the request ID in the capture
metadata. Add it to a separate response manifest with matching
`response_to_request_id`; complete real admission before continuing:

```powershell
python scripts/investigate_recordings.py configs/phone_investigation.local.json --resume data/processed/phone_investigation/checkpoint.json --response-manifest configs/phone_response.local.json --output-dir data/processed/phone_investigation
```

Capture request-ID text is only a label. The existing PhysicalEnvironment checks
the matching request, new video hashes, required repeat count, measured release
angle (0.08 rad tolerance), and fresh calibrated reference clips. Prefix replay
preserves the original investigation, verifies numeric context hashes and does
not resend historical paid calls. Task 08 additionally archives checkpoints,
traces and terminal status snapshots by digest under `history/` before updating
the convenient current filenames. Never modify an archive to repair a run.

`lab_progress.json` records hash-linked CLI stages for operator display:
ADMISSION → REVIEW_REQUIRED when blocked; otherwise ANALYSIS_READY →
INVESTIGATING → PENDING_PHYSICAL_ACTION, and only after existing response
admission RESPONSE_RECORDED → another request / FROZEN / ABSTAIN / FAILED.
The capture controller separately records IDLE → CAMERA_CONNECTED → RECORDING →
SAVED → ADMISSION → REVIEW_REQUIRED. Progress is last recorded state, not a
heartbeat, independent attestation or permission to bypass scientific gates.

Physical model acceptance remains limited by the existing real-data protocol.
The synthetic null gate cannot accept real structural repair. G5 still needs a
fresh independent precommitment, custodian, frozen accepted model and sealed
recordings; it remains separate from model fit and is NOT_PASSED here.

## Demonstration procedure

1. Keep the verified evidence replay open at port 8766. Show the original
   synthetic investigation and its separate fixed-PASS/randomized-FAIL G5 results.
2. Launch port 8770 explicitly. Find/Connect the real camera, confirm the phone
   identity and show the fixed pendulum rig in the preview. If unavailable, show
   that error truthfully and use original MP4 import instead.
3. Set the role/operator/rig, start recording, physically release the bob and
   stop. Show the saved clip, source SHA, ordered arrival statistics and original
   PTS. Do not call this verified physical timing.
4. Inspect the clean framing samples and exact admission blockers. Import the
   owner's WhatsApp pilot separately as `pilot`; show why calibration/framing,
   timing, SAM and independent human references remain unresolved.
5. In Real Phone, refresh saved evidence; visit all five views. Show comparison
   NOT_RUN unless sufficient admitted real evidence exists. Keep the successful
   synthetic replay accessible as its own clearly labelled branch.
6. If an actual admitted phone run requests an experiment, show its request
   hash/action, preserved checkpoint and no frozen model. Perform the requested
   action, admit the fresh response and resume using the command above. Without
   that evidence, show the pending/blocker state; do not invent a physical request.
7. Show independent physical evaluation separately as NOT_RUN/INCONCLUSIVE unless
   its real precommitted evidence exists. No automatic or new paid calls occur.

Owner prerequisites still required: original pilot path, phone identity,
pendulum-in-view physical recording, measured calibration/geometry and timing,
independent annotations and an independent sealed-evaluation custodian.
