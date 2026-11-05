# Third-party notices

The root MIT LICENSE covers REALIGN's original software and documentation. It
does **not** relicense third-party media, extracted frames, masks or overlays.

**Blocked-pendulum-slow-motion.webm**, creator **MikeRun**, October 28, 2025:
[original file and attribution](https://commons.wikimedia.org/wiki/File:Blocked-pendulum-slow-motion.webm).
License: [CC BY-SA 4.0 International](https://creativecommons.org/licenses/by-sa/4.0/).
Changes include MP4 transcoding, frame extraction, tracking and review presentation.
Original/processed hashes, creator, source and changes are retained in
`artifacts/external_source_verified.json` and SAM reports.

External pixels in `artifacts/task05/external_yellow_disc/review_frames/`,
`artifacts/task06/manual_review/` and `artifacts/release/manual_review/` retain
that license, including embedded images in HTML and media portions of screenshots.
[Separate media license record](licenses/EXTERNAL_MEDIA.md).

Attribution does not settle organizer reuse rights. Those remain UNVERIFIED.
The scripted release Cut A visits synthetic/numerical views only and contains
no external footage pixels. The owner's final video needs its own rights review.
No ownership of MikeRun's recording is claimed.

Dependencies retain upstream licenses: [NumPy](https://github.com/numpy/numpy/blob/main/LICENSE.txt),
[SciPy](https://github.com/scipy/scipy/blob/main/LICENSE.txt),
[Pydantic](https://github.com/pydantic/pydantic/blob/main/LICENSE),
[Matplotlib](https://matplotlib.org/stable/project/license.html),
[OpenCV](https://github.com/opencv/opencv/blob/4.x/LICENSE),
[pytest](https://github.com/pytest-dev/pytest/blob/main/LICENSE),
[Playwright](https://github.com/microsoft/playwright/blob/main/LICENSE),
[OpenAI SDK](https://github.com/openai/openai-python/blob/main/LICENSE).
Windows camera enumeration uses
[cv2-enumerate-cameras](https://github.com/lukehugh/cv2_enumerate_cameras),
distributed under the MIT license as an optional Windows perception dependency.
Meta hosted models are API services; using them does not establish an open-weight
license or bonus. This notice does not relicense upstream software or model APIs.
