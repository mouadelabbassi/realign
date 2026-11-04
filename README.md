# REALIGN

**Can a lab still trust its simulator after the mechanism changes?** REALIGN
compares observations with executable pendulum models, inspects discrepancies,
requests an informative experiment and freezes an evidence-cited decision.
Meta Muse Spark 1.3 reasons through bounded tools; Meta SAM 3.1 tracks the bob.
Deterministic code computes the physics, fits and scores.

The five-view product replays authentic Meta investigations on **synthetic
observations** beside actual SAM tracking on **licensed external footage**.
Controlled phone physics and independent localization accuracy remain unvalidated.

See the [documentation index](docs/README.md) for run guides and evidence, and the
[developer guide](docs/DEVELOPER_GUIDE.md) for the code layout and control flow.

## Two-minute replay

Use Python 3.11+ from this repository. After dependencies are installed:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[perception]"
python scripts/run_realign.py --port 8766 --no-browser
```

On Linux/macOS, activate the environment with `source .venv/bin/activate`.

Open **http://127.0.0.1:8766**. Playback needs **no API key, paid calls, WSL or
refitting**. Select "Live Muse investigation - attempt 02" and inspect:

1. **Reality vs Simulation:** scrub observations, B0/B1/B3 predictions and residuals.
2. **Investigation:** actual recorded hypotheses and scientific tool calls. This is replay.
3. **Experiment Loop:** a scored release request and two new **synthetic** trajectories; no actuator is claimed.
4. **Model Decision:** frozen model and a matched deterministic comparison. Selection is among predefined typed models.
5. **Evidence:** both original G5 outcomes, registered thresholds, provenance and safe CLI commands.

The optional ignored external video is not bundled as owned footage. Without it,
the player reports missing media while source/tracking records remain inspectable.
No replacement video is displayed.

## Local Live Physical Lab

Launch capture explicitly in a second native Windows terminal (FFmpeg and
`.[perception]` are required):

```powershell
python scripts/run_live_lab.py --port 8770
```

Open **http://127.0.0.1:8770**. Offline preview, manual recording and importing
an original local MP4 need no API key or paid calls. The controller stores MP4 bytes, SHA-256,
ordered software arrival timestamps, source provenance and original container
PTS separately under ignored `data/raw/live_lab/`. Software CFR playback is
**not independently verified physical time**. A saved or WhatsApp-compressed
pilot remains **BLOCKED_INPUTS**, with exact missing references shown.

The existing five-view product shows the library under **Real Phone**. Refresh
local evidence after recording. To show an existing phone investigation output:

```powershell
python scripts/run_realign.py --port 8766 --phone-output data/processed/phone_investigation --no-browser
```

The evidence product stays read-only. In the redesigned Live Lab, select
**Find cameras** to select your input, then open **Go Live** and review the target,
owner-reviewed USD reserves and finite spending cap. The setup's **Go Live**
authorizes and connects in one action. Capture, a startup SAM image request,
background video tracking and eligible Muse reasoning start automatically.
Continuous Live has no session-duration or API request-count cutoff; each paid
attempt still reserves against the spending cap. **Pause AI**, **Stop and analyze**
and **Revoke API calls** are independent. Ordinary preview, camera discovery and
manual capture remain offline. Run `python scripts/run_live_lab.py --port 8772 --log-level DEBUG`
for timestamped terminal diagnostics including frame traces. Credentials and raw
payloads are excluded; billing remains unverified. Scientific prose now renders safe Markdown, tables, code and math
in both workspaces, with raw JSON retained in an expandable audit view.

SAM results remain preliminary pixels until independent timing, measured
calibration, release review and the existing phone admission all pass. Muse uses
the same bounded scientific tools and waits for human experiment responses.
Original MP4 import and the existing Task 06 workflow remain available. See the
[Auto-Live run guide and verification boundary](docs/TASK09_2_AUTO_LIVE.md), the
[concurrent investigation guide, verification and limitations](docs/TASK09_LIVE_INVESTIGATION.md)
and the [capture/import guide](docs/TASK08_LIVE_LAB.md).

The first real live test produced no usable SAM observations and no completed
scientific investigation. The [Task 09.1 forensic repair guide](docs/TASK09_1_LIVE_REPAIR.md)
documents the saved evidence, selected-target prompt, empty-mask diagnostics,
local readiness without wasted Muse calls, and bounded backlog policy. A new
owner-approved phone/Meta test is still required; no real end-to-end success is claimed.

## What is demonstrated

| Evidence branch | Actual result | Boundary |
|---|---|---|
| G1 physics | 250 cases, zero failures, 1,516 hybrid transitions | Ideal planar taut-string model, one supported peg wrap side |
| B0-B3 | Nominal free, fitted free, circle geometry and fitted peg dynamics | Synthetic baselines; B2 radial error is separate from trajectory RMSE |
| Actual Muse | Successful two-round run: 9 completed operations, one experiment | Synthetic observations; first rejected attempt retained |
| Matched prediction | Muse and deterministic: **0.8196110265191848 px** development RMS | **No predictive advantage demonstrated** in this recorded case |
| Fixed synthetic G5 | **PASS**: 0.6930905745225341 px RMS; 5.602553 mm peg error | Workflow positive control |
| Randomized synthetic G5 | **FAIL**: 0.7519408442222819 px RMS; **14.477706 mm** peg error vs **10 mm** | Accurate prediction did not establish accurate geometry; failure preserved |
| Actual external SAM | 600 masks; 550 accepted centers, 50 rejected | REAL_EXTERNAL; physical capture timing and metric scale unknown |
| Independent localization accuracy | **NOT_VALIDATED** | Genuine human references pending; AI labels excluded |
| Controlled phone G2 / physical G5 | **BLOCKED_INPUTS / NOT_PASSED** | Actual recordings, calibration and independent validation missing |

The per-domain Evidence Ladder currently caps the overall claim at **C3a**:
SAM tracking on real external footage. Synthetic Muse and G5 are separate branches.
No physical discovery, causal uniqueness, credible interval or billed cost is
invented. [G5 failure analysis](docs/G5_FAILURE_ANALYSIS.md) reports archived local
sensitivity with its limitations. Billed Meta spend is **UNVERIFIED**.

## Independent review and real data

Open **http://127.0.0.1:8766/review**: forty clean shuffled frames include twenty
from early 0-4 s tracking intervals. Supply centers and uncertainty or mark not
visible, attest independent review, lock locally and download JSON. No server
writes or predicted-center hints are supplied. Independence is self-declared.

```powershell
python scripts/review_external.py evaluate --output-dir artifacts/release/manual_review --annotations data/reviews/external_independent.json
python scripts/prepare_release.py
python scripts/investigate_recordings.py configs/phone_investigation.example.json
```

The phone example exits 2 with exact blockers and zero API calls. Follow the
[collection protocol](docs/REAL_DATA_COLLECTION_PROTOCOL.md) and
[real workflow](docs/TASK06_IMPLEMENTATION.md). Physical actions wait for actual
new validated recordings. Synthetic calibration cannot authorize real repair.
Original monotonic PTS, including valid variable frame rate, are preserved.

## Evidence and reproduction

```powershell
python scripts/export_evidence.py --output data/processed/REALIGN_evidence.zip
python scripts/export_evidence.py --verify data/processed/REALIGN_evidence.zip
python scripts/verify_g5.py reproduce artifacts/task06/g5_demo
python scripts/verify_g5.py reproduce artifacts/task06/g5_positive_control
```

G5 reproduction checks the original revealed scores; it does not evaluate another
model. Windows numerical investigation/reproduction requires the existing Ubuntu
WSL isolation runtime (`python scripts/setup_investigator_runtime.py`). Native
Windows refuses unsupported worker isolation. Ordinary product replay needs no WSL.
Live execution remains explicit CLI-only and needs separate authorization. Keep
MODEL_API_KEY local. No browser endpoint starts a paid request.

- [Release readiness, exact tests and revisions](docs/RELEASE_READINESS.md)
- [Actual Meta receipts and request/token accounting](artifacts/release/meta_evidence_index.md)
- [Computed evidence summary](artifacts/release/evidence_summary.json)
- [Randomized G5 failure](artifacts/task06/g5_demo/validation.json) and [fixed control](artifacts/task06/g5_positive_control/validation.json)
- [G1](artifacts/G1_REPORT.md), [B0/B1/B2](artifacts/POC0_BASELINES.md), [B3](artifacts/B3_BASELINES.md)
- [Submission checklist](docs/SUBMISSION_CHECKLIST.md), [Meta compliance](docs/META_COMPLIANCE.md)
- [vFinal architecture](docs/ARCHITECTURE_VFINAL.md), [independent review corrections](docs/REALIGN_vFinal_Code_Review_Addendum.md)
- [Earlier implementation history](docs/IMPLEMENTATION_HISTORY.md)

Task 06 baseline: `88b1e13a756c369e4131769ce734ab4dff843ea4`.
[CI 41533276918](https://github.com/mouadelabbassi/realign/actions/runs/41533276918)
passed all four jobs. Release-specific verification is reported at its actual SHA.

Original software is MIT. MikeRun's external media and derived frames retain
**CC BY-SA 4.0**, outside MIT: [third-party notices](THIRD_PARTY_NOTICES.md).
Participant eligibility, organizer media rights, portal submission and the owner's
continuous narrated demo remain separate unresolved obligations.
