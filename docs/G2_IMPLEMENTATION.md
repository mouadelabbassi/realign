# Task 02 implementation and verification

**G2 is not passed.** No physical recordings, measured calibration points,
independent human annotations or local Meta API key were available. All rendered
videos, protocol events and reviewed-center references in offline evidence are
explicitly synthetic fixtures. They do not demonstrate SAM accuracy.

## Initial repository verification

The starting tree was clean on main at commit 2c32c6c. Task 01 contained 38 tests,
the G1 numerical kernel, synthetic observations, B0/B1/B2 and reproducible reports.
There was no real video/SAM/calibration pipeline.

Before implementation, installation succeeded and the original full suite passed:
38 passed in 811.76 s. G1 passed 250 randomized cases with 0 failures and 1,516
transitions. Maximum energy drift was 1.709933528104557e-9 J/kg; position jump
1.9849118084270064e-15 m; speed jump 4.440892098500626e-16 m/s; vertical peg period
error 6.247757866617576e-11 s. Baseline reproduction passed all 13 acceptance
checks. Numerical results agree with the prior evidence; scheduling-dependent
elapsed times are not scientific metrics. A duplicate threading/timing test run
was interrupted after the original suite passed; it is not counted as verification.

## Implemented contracts and ingestion

Task 01 Observation/Trial/PlaneProjection remain backwards compatible. Dedicated
VideoMetadata, VideoObservation, VideoTrial, PlanarCalibration, NoiseEstimate and
ReleaseEstimate records extend the contract without relabeling real inputs as
synthetic. The existing fitters dispatch to the video path only for VideoTrial.

Video metadata stores content SHA-256, original integer presentation timestamps,
rational time base, coded/displayed dimensions, display rotation and codec.
Container creation UTC is distinct from independently supplied recording-start
UTC. Unknown capture start stays unknown. Original PTS need not start at zero or
be uniform. Missing/nonmonotone PTS are rejected; nominal fps is not a substitute.
FFmpeg decoding must produce exactly one displayed frame per source PTS.

Video observations preserve the complete raw PTS grid, raw display-pixel centers,
Boolean validity, quality flags and per-frame covariance in px². Invalid centers
are NaN and never interpolated. Recording, calibration, API/fixture origin and
noise references are explicit. REAL_SAM requires REAL_PHONE media and REAL_API
processing; simulated masks cannot be silently promoted. Different provenance
classes cannot be pooled for comparison.

## Official SAM integration

The implementation follows Meta's published Files API MP4 upload with
purpose=user_data, sam-3.1 Responses streaming and the public
meta-sam-parser 0.1.0 APIs. The concept is fixed to "the pendulum bob". No raw rig
media are sent to Muse, and no classical detector substitutes for SAM.

The official parser handles output text lanes, including content_part.done,
terminal outcomes, diagnostics, mask validation and raster decoding. Source-frame
indices and box-local mask bounds are checked against local video metadata.
Cumulative revisions resolve to a final mask per frame/object identity.
Malformed/incomplete/refused/failed output is explicit. Completed empty output
does not imply a usable track.

Uploads/transient HTTP or stream-source errors have at most three attempts.
Authorization and malformed output are not retried as if successful. Receipts
contain model/parser version, response ID, request hash, video hash, operations,
attempts and sanitized status/type codes. They omit keys, headers and raw SDK
error bodies. Caches contain hashed normalized masks and receipts; fixture caches
are rejected by the real workflow. This is reproducibility/integrity hygiene, not
cryptographic proof of the API provider's identity.

## Tracking and calibration

The tracker selects a stable object ID. Multiple identities require explicit
review; it does not choose a new object when the selected one disappears.
Contour-circle RANSAC/refinement estimates bob center, rather than substituting
mask centroid. QA includes missing/empty masks, confidence when available,
contour fit, boundary clipping, area changes, translation-aligned shape IoU and
speed. Unknown confidence remains unknown. Rejected frames stay invalid.
The contour model assumes a compact approximately round bob; occlusion and
perspective distortion of the bob itself still need real validation.

Planar calibration uses measured metric-board/image correspondences, independent
pivot annotation and a hanging gravity reference. It fits a homography, defines
the pivot-origin gravity frame, and reports both fitting RMS and independent
checkpoint RMS. A separate multi-view checkerboard function/CLI estimates camera
intrinsics/distortion; projection/unprojection support those coefficients.
Image coordinates are those of the raw displayed frames. Lens correction, gravity
rotation and projective mapping are applied consistently in both directions.

## Uncertainty and real baseline interface

Stationary covariance and nonnegative common-axis AR correlation are estimated
from observed centers. The stationary estimate has an explicit 1/12 px²
digitization eigenvalue floor, an assumption rather than measured SAM jitter.
Paired manual review reports residual covariance and systematic bias separately.
A conservative isotropic covariance envelope covers the largest measured
localization variance. Contour residuals provide a declared engineering inflation
factor; this factor is not a calibrated confidence interval.

Repeat groups report physical release-angle variation and timing uncertainties
separately. Their trajectory dispersion is not identified as pure measurement
noise. Dynamic measurement errors need same-frame reviewed centers. The workflow
uses only stationary/exploration references for fitting covariance; development
reviews are evaluated after fitting.

Release onset is independently estimated from a visible stationary lead-in and
local from-rest quadratic motion. A profile-based bracket includes frame-scale
uncertainty; it is approximate until validated on real data. An independently
reviewed manual PTS bracket is supported. Full G1 rollouts use actual PTS minus
this offset, with a held initial state before release. There are no observation
resets during rollout.

Whitening includes per-frame localization covariance, independent PTS
quantization and gap/time-aware AR innovations. Release timing is a COMMON
rank-one covariance across the whole trial, not one independent error per frame.
For spatial/AR-whitened timing sensitivity a, the inverse square root of
I + a*aᵀ is applied analytically. This is a linearized, model-dependent uncertainty
calculation, not a full likelihood/parameter-CI calibration. Camera scale, pivot,
gravity, rolling shutter, initial-state error and review bias remain systematics.

B0/B1 use the same existing numerical model and bounded multistart fitter.
B2 fits the calibrated metric-plane trajectory, propagating raw-pixel covariance
through the unprojection Jacobian. Its metric radial reconstruction is primary;
the local-scale pixel equivalent is labeled approximate and is not predictive
trajectory error. Original synthetic numerical paths are preserved.

## Real CLI and collection inputs

See REAL_DATA_COLLECTION_PROTOCOL.md for rig construction, phone settings,
fiducial/pivot measurements, releases, independent reviews and the frozen split.
The manifest workflow processes actual SAM caches or explicitly uploads missing
MP4s, exports clean annotation frames, fits each opaque configuration separately,
saves observation/quality arrays, and writes a real-only report/plot. Failed API
calls remain recorded even if later calibration, annotation or fitting fails.
Sealed/vault/secret paths are rejected; OS-level sealed isolation remains future work.

The example manifest is intentionally incomplete. It cannot invent footage,
coordinates, annotations, measured length or Standard-tier confirmation.
The separate smoke command writes NOT_RUN with zero successful/failed calls when
local authorization/media are missing.

## Evidence, commands and limitations

Install with python -m pip install -e ".[dev,perception]" and ensure ffmpeg/ffprobe
are available. Run python -m pytest -q, python scripts/verify_g1.py,
python scripts/verify_baselines.py, and python scripts/verify_g2.py.
The latter never makes network calls and exits successfully only if its offline
checks pass; G2 still remains NOT PASSED. Exact final run results are recorded
below after verification.

Observed standalone outcomes: python scripts/verify_g1.py passed 250 cases with
zero failures; python scripts/verify_baselines.py passed all 13 checks; python
scripts/verify_g2.py passed all 8 offline checks. The final fixture uses the full
default three-parameter B1 fit: center RMS 0.389472 px, checkpoint RMS
1.633413e-6 px, B0 unseen-recording RMS 15.954945 px and B1 RMS 2.302299 px.
These are synthetic fixture measurements, not SAM performance. Estimated release
time was 0.3945 s for a rendered 0.4 s onset, within the reported uncertainty.
B2 selected one circle. The comparison plot was visually inspected.

The separate smoke command returned NOT_RUN, 0 successful and 0 failed actual
API calls, with exit 2. The example real-recording command returned pending
recordings/calibration with exit 2 and produced no real measurements. YAML
structure/expressions, Python syntax and tracked diff whitespace were checked.
No GitHub-hosted CI execution or real-world validation is claimed.

Regenerated POC-0 numerical records exactly match the prior committed JSON after
excluding the source hash. G1 records exactly match after excluding elapsed time.
The final G2 artifact source hash was checked against the current implementation.
The complete path-by-path change inventory is artifacts/TASK02_FILES.txt.

Final full regression command: python -m pytest -q, with OPENBLAS_NUM_THREADS=1,
OMP_NUM_THREADS=1 and MKL_NUM_THREADS=1. Actual outcome: **72 passed in 1368.67 s
(22 min 48 s)**, comprising the original 38 tests and 34 perception tests; zero
failures or skips. This includes both complete POC-0 report rebuilds and the
rendered-video end-to-end check. The separate perception run also passed all 34
tests. Final standalone verifiers passed 250 G1 cases, 13 baseline checks and 8
offline G2 checks. The GitHub job budget is 60 minutes to accommodate the full
scientific regression plus all reproduction commands.

The installed/tested SDK is OpenAI 1.109.1; the perception extra requires at least
that Responses-capable version and pins the official SAM parser to 0.1.0.

GitHub Actions runs the full suite and all offline reproduction commands on push
and pull request for Python 3.11/3.12, with FFmpeg and single-thread numerical
libraries. It provides no API key and uploads only named synthetic evidence.
The workflow has not been executed on GitHub during this local task.

Existing G1 physics source/oracles/tests are unchanged. No Muse agent, model
compiler, structural repair, frontend, sealed evaluator or real mechanism claim
was added. Full G3 MDE/power/null calibration remains unfinished. Offline codec,
coordinate, timing and integration tests cannot replace actual phone/SAM
validation. G2 is blocked on the collection protocol's real inputs and actual
account/API verification.

## File inventory

New implementation: contracts/video.py; perception/__init__.py, video.py,
sam_client.py, track.py, calibration.py, timing.py, uncertainty.py, pipeline.py,
workflow.py; report/g2_report.py; synth/video_fixture.py and g2_verification.py.
New commands: scripts/verify_g2.py, smoke_sam.py, inspect_video.py,
calibrate_camera.py and process_recordings.py. New tests: tests/test_perception.py.
New delivery/configuration: .github/workflows/ci.yml, configs/g2_manifest.example.json,
configs/calibration_points.example.json, data directory markers, this document,
REAL_DATA_COLLECTION_PROTOCOL.md and the G2 readiness artifacts.

Modified implementation: observation/camera.py and noise.py; fit/robust_fit.py,
baselines.py and circle_fit.py. Modified metadata/docs: pyproject.toml,
.gitignore, README.md, CODEX_EXECUTION_ROADMAP.md, META_SMOKE.md and PROVENANCE.md.
Reproduced G1/POC-0 artifacts may update source hashes/elapsed times; numerical
results are checked against the prior committed evidence.

Official references: [Meta SAM cookbook](https://dev.meta.ai/docs/cookbook/sam-api-basics),
[official parser](https://dev.meta.ai/docs/sam/client-libraries),
[OpenCV calibration](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html),
[ffprobe](https://ffmpeg.org/ffprobe.html).
