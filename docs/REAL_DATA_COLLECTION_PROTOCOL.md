# REALIGN real data collection protocol — G2

No real recordings, calibration measurements or human annotations were supplied
for Task 02. This protocol is not evidence of completed physical experiments.
Numerical budgets below are design targets, not measured SAM performance.

## Construct and measure one planar rig

Use a rigid support, light inextensible string and compact round bob. Measure
effective free length from pivot to bob center in metres. Record instrument
resolution, bob radius, attachment geometry and visible pivot dimensions. A
roughly 0.7 m string is a practical starting configuration, not a substitute for
your measurement. Keep support and swing plane fixed.

Place a flat metric reference board in the bob-center motion plane, rather than
substantially behind it. Mark at least ten well-separated points spanning the
full expected arc. Measure their board coordinates in metres. Use at least six
points for homography fitting and reserve at least four different checkpoints.
Four fitted corners can have zero residual without validating calibration.
Use a consistently oriented board basis: x increases to the right and y upward
as viewed by the phone. Do not supply image-style downward-y metric coordinates.
The hanging reference rotates this board basis into gravity alignment.

Make the physical pivot clearly identifiable. Annotate its image location
independently of the moving trajectory, repeating the annotation to assess
ambiguity. Do not estimate it from a potentially faulty swing. The calibrated
origin is the pivot; the stationary hanging bob defines downward gravity. Plane
x goes right and y up. Board edges need not be exactly vertical.

For peg clips use a fixed small peg, one wrap side and a free-side release. Start
with modest angles, approximately 0.3–0.6 rad. Avoid slack, support motion and
out-of-plane swings. Bob size, peg radius, friction and impact losses are potential
real systematics; a real contact is not automatically ideal. Keep peg geometry
and fault labels out of inference manifests. Preserve independent apparatus
notes locally for later evaluation.

For the first peg setup, a peg directly below the pivot and right-side releases
give the kernel's traditional left-side wrap. A roughly 0.15 m pivot-to-peg
distance is a proposed starting setting for a roughly 0.7 m string, not a measured
value. Measure the actual apparatus independently. The suggested release range
is about 17–34 degrees; mark repeatable positions and release without a push.

## Position and lock the phone

Mount the phone rigidly, approximately front-on. Keep pivot, board and complete
swing in frame with margin. Use good lighting, locked focus/exposure, no digital
zoom changes and stabilization off where available. Prefer at least 60 captured
frames/s and sufficiently short exposure to resolve the bob boundary. The code
uses original PTS, never requested/nominal fps. Avoid slow-motion exports that
alter playback time.

Keep lens, focus, zoom, resolution, camera position and stabilization unchanged
for calibration, stationary and dynamic clips. Any change needs a new calibration
ID. Prefer MP4/H.264. MOV conversion is explicit preprocessing: preserve and
inspect output timestamps, then annotate/calibrate the uploaded MP4 itself.
Never annotate a resized screenshot or differently rotated crop.

Current ingestion supports right-angle display rotations, clips up to 60 s,
10,000 frames, and 4096 pixels on either displayed dimension.

## Collect calibration and stationary measurements

1. Film the board, pivot and stationary hanging bob without moving the camera.
2. Export full-resolution displayed frames:

       python scripts/inspect_video.py data/raw/stationary/stationary_01.mp4 --output-dir data/calibration/setup_01 --frame-index 0 --frame-index 60

3. Use an image viewer exposing original pixel coordinates. Record each measured
   board point, pivot center and hanging bob center. Image u goes right, v down.
   Use exported dimensions, including display rotation. Average independently
   repeated hanging/pivot annotations rather than inventing exact coordinates.
4. Copy configs/calibration_points.example.json to data/calibration/points.json.
   Fill image_size=[width,height], board_xy_m, image_xy_px, pivot_px, hanging_px,
   and the separate check_board_xy_m/check_image_xy_px arrays. Set source to
   REAL_MEASURED only after measuring. Required coordinates cannot remain null.
5. Inspect calibration:

       python scripts/calibrate_camera.py data/calibration/points.json --output data/calibration/calibration_result.json

The processing manifest references the original points.json, so calibration is
reproducible. Checkpoint RMS should meet the 1 px design budget. Investigate
failed geometry, measurements or distortion; do not drop inconvenient checkpoints.
Scale/pivot/gravity uncertainty is systematic, not independent frame noise.

If distortion matters, acquire at least five, preferably 10–15, checkerboard views
covering different image positions and tilts at the same lens settings. Measure
square size in metres. Detect or independently verify matching corners. The lens
CLI accepts JSON with object_points_m (Nx3 per view), image_points_px (Nx2 per
view), and image_size:

    python scripts/calibrate_camera.py data/calibration/lens_corners.json --lens --output data/calibration/lens_result.json

Copy its camera_matrix, distortion and lens_rms_px into points.json and provide
a stable intrinsics_id. Without these, lens correction remains unverified.
Reprojection RMS does not cover board nonplanarity or rolling shutter.

Record a 10–15 s stationary hanging clip. Apparent covariance includes tracking
noise, physical drift and camera drift; these cannot be silently conflated.
Use the same camera configuration throughout.

## Collect releases and freeze recording roles

Each clip should include at least one second of a held, visible bob, a release
from rest without a push, and at least three subsequent oscillations. A total
7–10 s clip is usually suitable for the suggested rig. Keep hand, string, peg and
bob distinguishable. Do not trim to an assumed release instant. Unknown recording
creation time remains unknown; original PTS still define all video timing.

For the free configuration, record three separate repeats at one marked angle,
one additional exploration angle and at least one separate development recording.
A repeat and an unseen angle in development are preferable. For the peg setup,
record at least two exploration angles and one separate development clip;
three repeats per angle are preferable. Freeze roles before inspecting scores.

Use a separate opaque comparison_group for every fixed rig configuration.
Different configurations are not pooled in one shared parameter fit. Repeats
contain real release-angle, velocity and timing variation. Repeat dispersion is
reported separately, not identified as tracker noise. Dynamic tracking errors
are checked against manual centers in the same frames.

## Directory and manifest layout

    data/
      raw/stationary/       stationary_01.mp4
      raw/free/            run_001.mp4 ... run_004.mp4
      raw/peg/             run_101.mp4 run_102.mp4
      raw/development/     dev_001.mp4 dev_101.mp4
      calibration/         measured points, lens inputs/results, exported frames
      reviews/             annotations.json and reviewer notes
      processed/           SAM caches, observations and real reports
      sealed/              FUTURE ONLY; not read or uploaded by this pipeline

Copy configs/g2_manifest.example.json to configs/g2_manifest.local.json.
Fill the measured nominal length, document nominal drag assumptions, set paths
and keep recording IDs opaque. Paths resolve relative to the manifest. The same
video bytes under renamed files are rejected across stationary, exploration and
development. These development trials are not sealed evaluation. Do not revise
models after inspecting their scores and still call them untouched holdouts.

Raw videos, actual calibration/reviews, processed data and sealed contents are
ignored by Git. Directory markers and examples are tracked. Keep MODEL_API_KEY
in the local environment, never manifests, screenshots, logs, artifacts or chat.
The pipeline rejects sealed/vault/secret paths; this guard is not the future
OS-enforced vault.

## Execute SAM separately and process the recordings

Install FFmpeg with ffmpeg and ffprobe on PATH, then:

    python -m pip install -e ".[dev,perception]"
    python scripts/smoke_sam.py data/raw/free/run_001.mp4 --standard-tier-confirmed --output-dir data/processed/sam_smoke

Confirm your account uses Standard tier before passing that flag or setting
standard_tier_confirmed=true in the local manifest. The adapter follows the
official MP4 Files API upload with purpose=user_data, SAM Responses streaming and
meta-sam-parser 0.1.0. The fixed concept prompt is "the pendulum bob". No classical
segmentation substitutes for SAM. Completed empty output is not a usable track.
If more than one object ID is returned, review the candidates and set object_id
explicitly. Never select a track using hidden geometry.

    python scripts/process_recordings.py configs/g2_manifest.local.json --run-api --output-dir data/processed/g2

The command uploads only missing recordings, reuses matching completed real SAM
caches, preserves PTS, extracts contour centers, flags bad frames, estimates
release onset, propagates uncertainty and compares B0/B1/B2 per configuration.
Without --run-api it uses existing real receipts/caches; fixture caches are
rejected. Errors receive bounded retries and sanitized reporting.

It exports deterministic random clean review frames and templates under
data/processed/g2/review_frames/. There are no fitted-center hints. Review at
least twenty valid frames per recording, adding fast, turning-point, contact and
difficult frames. Fill center_px=[u,v], positive annotation_sigma_px and reviewer;
retain recording_id and frame_index. Repeated independent clicks help estimate
annotation uncertainty. Combine rows into data/reviews/annotations.json.
Duplicate frame rows are rejected.

Stationary and exploration reviews estimate fitting noise. Development reviews
are checked after fitting and never calibrate training covariance. Rerun without
--run-api after annotating. Missing masks remain invalid; observations are not
interpolated.

If automatic release timing is unresolved, inspect original frames and add
release_bracket_pts_s=[last_definitely_held_pts,first_definitely_released_pts]
to that recording. Values are absolute presentation seconds from video metadata,
not frame index divided by fps. The bracket must lie inside the recording.
The midpoint has nonzero uncertainty; it is not declared exact.

Exit 0 means the G2 assessment passed; exit 2 means pending evidence; exit 1 means
a top-level CLI/configuration error. Inspect G2_READINESS.md, g2_readiness.json,
the observation arrays, track quality and retained SAM receipts. Declared targets
are checkpoint RMS <=1 px, reviewed tracking RMS <=2 px, rejection <=10%, and
release sigma <=50 ms. They do not establish full G3 discrimination or causal
mechanism/repair.

## Inputs to supply next

Provide the stationary clip, three matched free releases and another exploration
angle, peg exploration clips, disjoint development clips for both setups,
measured effective length/apparatus dimensions, six-plus board fit points and four
separate checkpoints in metric/pixel coordinates, pivot/hanging annotations,
lens data if relevant, twenty reviewed frames per clip with annotation uncertainty,
and locally configured Standard-tier Meta access. Do not send the key in chat.

Official references: [Meta SAM cookbook](https://dev.meta.ai/docs/cookbook/sam-api-basics),
[official parser](https://dev.meta.ai/docs/sam/client-libraries),
[OpenCV calibration](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html),
[ffprobe](https://ffmpeg.org/ffprobe.html).
