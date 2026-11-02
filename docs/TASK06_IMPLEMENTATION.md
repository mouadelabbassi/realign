# Task 06: evidence closure and independent validation

Architecture v1.1 remains unchanged. Task 06 adds review, controlled-recording
orchestration and a local independent-validation custodian to the existing
application. It does not add an investigator, compiler, physics domain or frontend
framework. G1 physics, B0–B3 mathematics, Task 05 receipts and the synthetic null
calibration are preserved.

## Current measured status

| Evidence | Actual result |
|---|---|
| Independent centers for the existing external clip | **NOT_VALIDATED**: none supplied; RMSE, bias, median, p95 and context errors remain null. |
| Actual external SAM output, retained from Task 05 | 600 frames; 550 accepted centers and 50 shape rejections. Acceptance is not accuracy. |
| Controlled phone workflow | **BLOCKED_INPUTS**, zero new API operations. No phone footage, measured calibration or independent annotations supplied. |
| Fixed synthetic G5 positive control | Prediction RMS 0.693090574523 px; peg-position error 5.602553 mm; **SYNTHETIC_EXERCISE_PASS**. This fixed fixture is a workflow control. |
| Privately randomized synthetic G5 exercise | Prediction RMS 0.751940844222 px; peg-position error 14.477706 mm against a 10 mm tolerance; **SYNTHETIC_VALIDATION_FAIL**. No retry to replace the failure. |
| Post-reveal numerical reproduction | Both recorded scores and prediction digests reproduced exactly, with zero fits/API calls. Original verdicts unchanged. |
| Full physical G2 / G5 | **NOT_PASSED**. Synthetic exercises and external tracking cannot satisfy these gates. |

The randomized case predicted well but failed geometry validation. It is evidence
against equating predictive accuracy with recovery of the hidden mechanism or
geometry. Neither example estimates discovery reliability. The fixed and random
cases have separate challenge IDs, models, commitments and held-out datasets.
The app displays the randomized case separately from the earlier Task 05 run.

## Independent external measurement review

`perception/manual_review.py` packages the **existing twenty clean Task 05
reference images** without masks, predicted centers or tracking acceptance hints.
The self-contained annotation page accepts a bob center, positive localization
uncertainty and visual context labels (`reversal`, `occlusion`,
`apparent_contact`). It exports JSON and never sends annotations to an API.
Reviewer identity, timestamp, independence attestation, original video SHA-256,
reference-manifest hash, image hashes, frame indices and exact PTS bind inputs.
Identity and independence are self-declarations, not external certification.

The scorer computes Euclidean localization RMS, signed x/y bias, median and
linear-interpolated p95 distance. It reports tracking acceptance in half-open
two-second presentation-time intervals and errors within reviewed context strata.
Missing/rejected SAM centers receive no invented residual. Empty strata remain
unavailable. Annotation sigma is reported; it is not silently subtracted from
observed agreement error or treated as error-free ground truth.

The twenty exported frames start at frame **157 / 5.233333 s**. They do not sample
the early rejection interval: 0–2 s has 22/60 accepted frames, 2–4 s 48/60,
and 4–20 s 480/480. Even a complete review will not establish whole-video
accuracy, occlusion robustness or physical contact detection. Additional
independent frames would be required for that study. This clip is licensed
**REAL_EXTERNAL**, not a controlled phone recording; physical time scale and
metric calibration are unverified.

```powershell
python scripts/review_external.py prepare
python scripts/run_realign.py
# Open http://127.0.0.1:8765/review; annotate independently and download JSON.
python scripts/review_external.py evaluate --annotations data/reviews/external_independent.json
python scripts/verify_task06.py --annotations data/reviews/external_independent.json
```

Without annotations, `evaluate` exits 2 and preserves NOT_VALIDATED. Invalid
identity/hash/PTS/uncertainty inputs are rejected. The UI recomputes the admitted
assessment from its bound inputs. Automated browser clicks are cleared before
test downloads and are never used as measurement references.

If an earlier app is still answering on the default port, start the current
build with `python scripts/run_realign.py --port 8766 --no-browser` and open
http://127.0.0.1:8766/review. The final local HTTP checks used that fresh port.

## Controlled phone investigation

`physical/ingestion.py`, `session.py` and `orchestration.py` connect the existing
SAM workflow, video contracts, calibrated observations, numerical tools,
investigator and audit exporter. They use actual REAL_PHONE / REAL_SAM /
REAL_API / REAL_MEASURED inputs only. There is no synthetic fallback.

Copy `configs/phone_investigation.example.json` to a local manifest and follow
[REAL_DATA_COLLECTION_PROTOCOL.md](REAL_DATA_COLLECTION_PROTOCOL.md). Supply:

1. Original stationary and at least two distinct exploration recordings from
   one fixed rig/comparison group, with measured nominal length. Four dynamic
   recordings permit the existing two-fold exploration comparison. Prefer the
   protocol's repeated angles and varied excitation.
2. Measured metric/pixel fiducials, independent pivot/hanging reference, at least
   four separate calibration checkpoints (RMS <= 1 px), and distortion data if
   relevant. Fit points and checkpoints must be distinct.
3. Independent capture-timing verification and its reference. Nominal encoded
   FPS or slow-motion playback PTS do not establish physical time scale.
4. Twenty independently reviewed centers per stationary/exploration recording,
   positive annotation sigma, reviewer and video hashes. The JSON envelope has
   `annotation_source: INDEPENDENT_HUMAN`, `independent_of_sam: true`, `reviewer`
   and `rows`; each row retains `recording_id`, integer `frame_index`,
   `video_sha256`, `center_px` and `annotation_sigma_px`. Start from the clean
   frames exported by `process_recordings.py`, independently review, then wrap
   the supplied rows; never copy SAM predictions into this document.
5. Independently reviewed absolute release brackets where necessary. Optional
   `analysis_window_pts_s: [start, end]` selects a contiguous window retaining
   the release bracket. It preserves original integer PTS, frame map, missing
   observations and covariance; it never resamples at a nominal frame rate.
   Existing tool limits remain <=256 samples and <=4 post-release seconds.

```powershell
# No key needed: missing inputs produce the exact blockers and exit 2.
python scripts/investigate_recordings.py configs/phone_investigation.example.json
# Opt-in actual SAM + Muse; requires authorized local account access.
python scripts/investigate_recordings.py configs/phone_investigation.local.json --run-api --live --standard-tier-confirmed --env-file .env --output-dir data/processed/phone_investigation
```

The SAM manifest's Standard-tier confirmation and CLI Muse confirmation must
reflect actual account settings. Neither flag establishes account eligibility.
Omit `--live` for the deterministic policy. Omit `--run-api` to use matching
completed **real** SAM caches. Current SAM operations and cumulative Muse attempts
are accounted separately; historical cached SAM processing is not counted as a
new request. Default offline closure commands make no Meta requests.

Only exploration records enter `ScientificSession`. The orchestrator does not
open manifest development paths. It exports current B0 discrepancy, B1/B3 fit
diagnostics and matching exploration cross-validation scores from actual tool
results, explicitly NOT_RUN when absent. B2 circle radial errors remain separate
from dynamical trajectory RMS. Robust fitting cost is not relabeled as RMS.
All tools keep the existing budgets, typed model family and bounded optimizer.

An unsupplied agent-requested physical experiment stops at REQUEST_EVIDENCE,
exports a hash-checked `checkpoint.json` and structured pending action, and
**does not freeze or issue a completed experiment receipt**. After collecting
the action, supply a separate manifest with `response_to_request_id` matching
the checkpoint's pending request. Dynamic releases require fresh recordings,
the requested repeat count and measured release within 0.08 rad of the requested
angle; this is a declared admission tolerance, not a measurement accuracy claim.
Reference actions need a new validated stationary/reference recording; their
manifest may reuse the original dynamic clips. Recording receipts prove admitted
files, not actuator control or independently timestamped interventions.

```powershell
python scripts/investigate_recordings.py configs/phone_investigation.local.json --resume data/processed/phone_investigation/checkpoint.json --response-manifest configs/phone_response.local.json --output-dir data/processed/phone_investigation
# Add --live and the same explicit authorization flags for live continuation.
python scripts/verify_task06.py --phone-output data/processed/phone_investigation
```

Continuation recomputes the recorded numerical prefix and verifies exact context
hashes before admitting the response. It does not resend historical Meta calls.
A new model conversation continues from the current approved context with prior
request/token accounting retained. This is action replay, not byte-for-byte
recreation of a remote model conversation. Prefix mismatch fails closed.

**Real structural acceptance remains uncalibrated.** The real validator rejects
REPAIR_STRUCTURE, and the synthetic null gate is never installed for phone data.
The existing registered comparison also excludes real-video designs, so numerical
fits may be informative while KEEP/CALIBRATE proposals still abstain. This task
does not invent a real-data acceptance protocol. A completed ABSTAIN freeze is
a valid partial result; it supplies no accepted predictive model to G5.

## Independent validation boundary

`validation/` is a trusted custodian module in the same application, outside
the investigator and numerical worker API. Its immutable typed resources and
hash-linked ledger enforce:

1. PREPARED: canonical geometry, fixed evaluation tolerances, held-out dataset
   hash and a fresh >=256-bit secret nonce produce the public commitment.
2. INVESTIGATION_STARTED: a public start receipt is created before investigation.
   Its hash is bound into the investigation audit and final freeze. An old
   Task 05 freeze cannot be attached retrospectively to a fresh challenge.
3. MODEL_FROZEN: canonical immutable model bytes/content hash bind the model,
   exploration references, proposal decision, commitment and start receipt.
4. EVALUATION_SPENT: dataset fingerprints and raw video hashes are irreversibly
   consumed **before** prediction, including a solver failure/crash. Renaming a
   challenge, changing a window or changing centers in the same video cannot
   obtain another look in that vault.
5. EVALUATION_RECORDED, then REVEALED: forward prediction without fitting;
   only afterward may nonce/geometry be revealed and the commitment checked.

The trusted host checks exploration/response records against the private heldout
set before provisioning the worker. Actual Linux Landlock/seccomp probes deny
the worker access to the private geometry/nonce/heldout file and ledger, parent
memory, network, credentials and imports of the synthetic generator. Native
Windows refuses an unisolated worker; use the existing Ubuntu WSL runtime.
Vault resources are not HTTP endpoints or scientific tools.

The custodian/host administrator is trusted. File permissions and a local ledger
are not remote notarization, protection against an administrator replacing the
whole vault, or proof that a human never saw the rig. Geometry qualifications
are evidence declarations; full physical G5 remains false even if a future
REAL_PHONE_CONSISTENCY_PASS is achieved. External clips cannot become controlled
phone validation. Numerical prediction is distinct from mechanism identification.

Default preregistered tolerances are trajectory RMS <=2 px, >=2 trials, >=12
valid samples/trial, missing fraction <=25%, sufficient excitation >=0.3 rad,
and length/peg-position errors <=10 mm. These engineering tolerances are not
calibrated confidence levels. Negative controls, insufficient excitation,
unqualified real inputs and prediction failures are explicit/inconclusive.

```powershell
# New privately randomized synthetic challenge; a new run may FAIL/ABSTAIN.
# Use a new output folder; this is not a command for replacing retained evidence.
python scripts/verify_g5.py demo --seed 66500 --output-dir data/processed/new_synthetic_exercise
# Reproduce both retained evaluations without fitting, APIs or private vault access:
python scripts/verify_g5.py reproduce artifacts/task06/g5_demo
python scripts/verify_g5.py reproduce artifacts/task06/g5_positive_control
```

Synthetic public records were exported **after** gated reveal. Before reveal,
the export API refuses them; it never exports real recordings. Reproduction
checks the frozen content hash and exactly matches prediction/timestamp digests
and numerical scoring fields. It does not issue a second evaluation or change
the original verdict. The random challenge's geometry was private before freeze;
the published noise seed alone did not disclose it.

For future controlled G5, an independent custodian collects a disjoint recording
set and measured geometry, then prepares the commitment **before** investigation:

```powershell
python scripts/verify_g5.py prepare-recordings configs/custodian.local.json --geometry-file data/calibration/private_geometry.json --vault-dir data/vault/phone --challenge-id phone-01 --public-output data/processed/phone_commitment.json
python scripts/investigate_recordings.py configs/phone_investigation.local.json --vault-dir data/vault/phone --challenge-id phone-01 --output-dir data/processed/phone_investigation
```

The private custodian manifest uses the same exploration-shaped ingestion codec
solely to parse its own recordings; they are immediately stored as development
contracts and never registered with investigator tools. Keep custodian outputs
private and separate from exploration. Input paths use `data/raw/development/`;
the existing perception path guard refuses sealed/vault/secret input paths.
Actual sealed contracts live in the separate vault. Geometry JSON follows
`GeometryMeasurements`: explicit m units, pivot-relative x-right/y-up,
independently measured length/peg xy and positive uncertainty, method
INDEPENDENT_PHYSICAL_MEASUREMENT and bounded reference IDs. No hidden event/mode
labels are supplied to the investigator. An accepted predictive model and the
original pre-investigation receipt are required to evaluate; ABSTAIN remains
INCONCLUSIVE without opening holdouts to the agent.

## Product, preservation and verification

The existing five views gain measurement review, real-input blockers/pending
actions, frozen-model hashes, separate independent verdicts and an explanation
of actual Muse contribution. Read-only `/api/closure` admits a fixed allowlist of
public resources; `/review` serves only the pinned clean-frame page with a script
hash CSP and no network access. Neither route exposes custodian files or runs
fits/API calls. Muse chose hypotheses, tool calls and an experiment in the retained
live synthetic run; deterministic tools supplied the numerical values. Matched
deterministic/live prediction errors were equal, so no superiority is claimed.

See [TASK06_READINESS.md](../artifacts/task06/TASK06_READINESS.md) for exact local
tests, preserved failures, generated artifacts and changed-file inventory.
[META_COMPLIANCE.md](META_COMPLIANCE.md) records official-source checks and
unresolved owner-specific obligations; [the storyboard](TASK06_DEMO_STORYBOARD.md)
shows only evidence that actually exists. Task 06 makes zero new Meta requests.
Prior live successes and logical failures remain in their original Task 05 files.
