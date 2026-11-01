# Task 03 readiness and acceptance

**Offline implementation verified. Live Meta and real physical validation remain pending. G2 and full G3 are NOT PASSED.**

## Verified synthetic scientific behavior

The final complete suite passed **115 tests, zero failures/errors/skips**, reported
elapsed 3065.21 s. G1 passed 250 configurations with zero failures and 1516
transitions. Existing baseline reproduction passed 13 checks; offline G2 passed
8 checks; the B3 report passed 9 checks. G1 source/tests were unchanged.

Full eight-case B3 numerical records reproduced exactly after excluding the
source hash. Representative integration tests independently reproduce JSON,
Markdown, PNG and observation-archive bytes. The final source hash is recorded
in TASK03_VERIFICATION.json and b3_baselines.json. The final Markdown sampling
clarification was rendered from the frozen measured JSON without refitting.

Development trajectory RMSE, px (B2 is a geometric diagnostic):

| Case | B0 | B1 | B3 | B2 geometry |
|---|---:|---:|---:|---|
| No fault | 0.722311 | 0.720490 | 0.723749 | One circle |
| Parameter fault | 34.748305 | 0.719287 | 0.718566 | One circle |
| Vertical peg | 44.627802 | 32.777710 | 0.680284 | Two circles |
| Off-vertical peg | 25.802755 | 19.572740 | 0.707100 | Two circles |
| Unexcited peg | 0.694053 | 0.697875 | 0.697875 | One circle |
| Noisy peg | 25.806544 | 19.690919 | 3.664269 | Ambiguous |
| Short arc | 0.700754 | 0.705190 | Rejected | Ambiguous |
| Insufficient data | 0.626540 | Rejected | Rejected | Ambiguous |

B3 uses bounded deterministic multistart fitting of the existing event-driven
one-peg dynamics. Parameters are fitted on two exploration trials; whole-trial
exploration CV and five disjoint development predictions are separate. B2 radial
reconstruction error is not compared against temporal RMSE. The assumed ordinary
localization SD is 0.5 px per coordinate, versus 2.5 px with AR(1) and missing
observations in the noisy case. These are synthetic assumptions.

The paired whole-trial bootstrap intervals for B1 minus B3 MSE exclude zero on
the three excited peg cases. These are descriptive intervals conditional on the
fixed training fits, not a calibrated structural-repair test. The parameter-fault
interval includes zero. No-fault B3 is slightly worse on development. An unexcited
peg has rank 3/5 and B1/B3 predictions differ by only 0.00000769 px. Such data do
not identify peg presence. Local full rank alone is not a mechanism certificate.

See B3_BASELINES.md for all intervals, uncertainty, search budgets and limitations;
b3_baselines.json retains full-training restart diagnostics and exploration CV
scores/failures. Conditional Gaussian standard deviations and multistart spread
are not coverage-validated confidence intervals or global identifiability claims.

## Verified live Meta API behavior

**NOT_RUN. Actual successful calls: 0. Actual failed calls: 0.**

MODEL_API_KEY is absent. Structured-output and arithmetic tool-round-trip probes
are implemented and tested with explicitly simulated responses. The actual Muse
Spark 1.3 calls, SAM 3.1 upload, streamed parsing and mask tracking have not run.
The official SAM parser remains the production path; no classical replacement is
used. Official documentation versus observed live behavior is NOT_ASSESSED.

    python scripts/smoke_meta.py --standard-tier-confirmed
    python scripts/smoke_sam.py data/raw/external/blocked-pendulum.mp4 --external-source artifacts/external_source_verified.json --standard-tier-confirmed --output-dir data/processed/task03_api_external

Both actual smoke commands returned exit 2 with zero attempted calls. Evidence:
meta_smoke.json and sam_external_api_verification.json. Mocked failures and valid
fixtures are not counted as actual API calls. Credentials remain local.

## Verified external real-video behavior

MikeRun's CC BY-SA 4.0 physical blocked-pendulum video was downloaded, hashed,
visually inspected, transcoded and fully decoded. The original is 1,759,473 bytes;
the derivative is 1280 by 720 with 600 frames. Maximum original/derivative PTS
difference is 0.0003333333333337407 s, within container quantization. Original
timestamps are also retained in the evidence. A fresh invocation of the CLI's
transcode/decode path passed using the cached original.

REAL_EXTERNAL is distinct from REAL_PHONE and SYNTHETIC_RENDER. The attribution,
license, original URL and both hashes are retained in external_video_ingestion.json
and external_source_verified.json. The original and derivative remain ignored raw
media. The derivative retains CC BY-SA 4.0. Source:
https://commons.wikimedia.org/wiki/File:Blocked-pendulum-slow-motion.webm.

**Actual external SAM tracking: NOT_RUN. Metric external dynamics: NOT VALIDATED.**
This is slow-motion playback with unverified physical capture time scale and no
measured camera calibration/pivot/length or reviewed centers. It is rejected for
dynamics until physical timing is verified. It cannot satisfy the phone G2 gate.

## Reproduction and retained evidence

Run with OPENBLAS_NUM_THREADS=1, OMP_NUM_THREADS=1 and MKL_NUM_THREADS=1 in the
installed virtual environment. Exact executed commands, dependency versions,
initial failures and their corrections are in TASK03_VERIFICATION.json and
docs/TASK03_IMPLEMENTATION.md. The final JUnit record is task03_tests.xml.

    python -m pytest -q --junitxml=data/processed/task03_full_tests.xml
    python scripts/verify_g1.py
    python scripts/verify_baselines.py --output-dir data/processed/task03_regression/baselines
    python scripts/verify_g2.py --output-dir data/processed/task03_regression/g2
    python scripts/verify_structural.py
    python scripts/prepare_external_video.py
    python scripts/export_tool_schemas.py

Original G1/Task 01/Task 02 artifacts were retained. The prior baseline's largest
cross-environment B1 RMSE drift is 0.00662038 px; all B2 decisions and acceptance
checks are unchanged. New artifacts identify their actual package versions.

The existing hosted GitHub workflow was green for commit 5bdc734. The updated
push/PR workflow includes the full suite and B3 reproduction with a 90-minute
budget and no API credentials. Its updated version has not run on GitHub yet.

## Inputs and checks still required

- Locally authorized MODEL_API_KEY and confirmed Standard tier, then actual SAM
  and Muse capability probes. Do not send the key in chat or add it to Git.
- Phone stationary references, repeated free-swing and peg-contact trials, with
  disjoint development recordings following REAL_DATA_COLLECTION_PROTOCOL.md.
- Measured planar calibration points, pivot/scale and relevant lens intrinsics;
  release brackets and independently reviewed frame annotations.
- Monte Carlo null calibration, broader seed/effect/noise and power/CI-coverage
  studies, parameter profiles, independent geometry and peg-removal interventions.

The five closed input/output schema pairs are ready for the next bounded tool
wrapper implementation. They are schema designs only. Agent handlers, experiment
scoring, Muse investigator, general compiler, frontend and sealed evaluator are
not implemented. Storage isolation and allowlists remain prerequisites to actual
agent access. No structural discovery, repair, causal uniqueness, real tracking
accuracy or full G3 acceptance is claimed.

Exact changed-file inventory: TASK03_FILES.txt. The pre-existing root is.py
deletion was preserved. No commit or push was performed in Task 03.
