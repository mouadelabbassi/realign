# REALIGN — Scientific Baselines and Bounded Investigator

**Status: verified physics/baselines, an offline-tested perception pipeline, and an executable bounded investigator. Real phone validation and end-to-end live investigator validation remain pending. G2 is NOT PASSED.**

REALIGN aims to audit physics simulations against phone-measured reality,
request discriminating experiments, propose typed structural corrections and
validate them using sealed independent evidence.

Implemented and tested:

- Ideal ordinary pendulum and exact nonlinear period oracle (elliptic integral).
- Hybrid peg-contact pendulum using SciPy `solve_ivp`, directed event guards,
  explicit Cartesian position and tangential speed preserving reset maps.
- One selectable wrapped side of a fixed point peg (off-vertical supported).
- Viscous and quadratic bob drag, and optional explicitly empirical contact
  loss coefficients (ideal default = 1).
- Unsupported slack-string conditions rejected rather than silently ignored.
- Automated physics tests and deterministic randomized configuration sweep.
- Synthetic-only comparison of an original fixed-pivot simulator with a peg
  reference, clearly labeled as *not* real measurements or AI model repair.
- Validated observation/experiment records with explicit px, px², s and plane frames.
- Seeded synthetic localization noise, optional stationary AR(1) correlation and
  missing samples, with separate observation and evaluation-only truth records.
- B0 nominal free-pendulum prediction; B1 bounded multistart nonlinear fitting of
  length, viscous and quadratic drag using complete trajectory rollouts.
- B2 recurring one-circle/two-circle geometry, with short-arc rejection and
  leave-one-whole-training-trial-out comparison.
- Disjoint synthetic development trials, no-fault and unexcited controls, explicit
  ambiguous cases, solver-failure tests and truth dependency/input checks.
- Separately executable Meta capability probes and a budgeted Muse adapter; live
  investigation evidence is reported separately from local capability probes.
- Five executable numerical tools, isolated exploration-only resources, a bounded
  state machine, experiment planning, conservative synthetic model selection and
  immutable investigation traces with fresh numerical replay.

## Install and run

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
python -m pip install -e '.[dev,perception]'
python -m pytest -q
python scripts/verify_g1.py
python scripts/verify_baselines.py
python scripts/verify_structural.py
```

Outputs: `artifacts/G1_REPORT.md`, `artifacts/g1_verification.json`,
`artifacts/synthetic_trajectory_comparison.csv`, and (with matplotlib)
`artifacts/synthetic_discrepancy.png`.

The baseline command produces [POC0_BASELINES.md](artifacts/POC0_BASELINES.md),
`poc0_baselines.json`, `poc0_baselines.png`, `poc0_observations.npz` and the separate
post-fit `poc0_truth_evaluation.json`. It exits nonzero when its acceptance checks fail.
Use `--output-dir PATH` to write a separate evidence run; the named default seed is
`20261031`. The integration test reproduces JSON, Markdown, plot and observation
archive bytes twice in the same environment.

## Actual synthetic results

**SYNTHETIC ONLY — NO META API / REAL-WORLD VALIDATION**

Two training trials and one unseen whole development trial per case; 4 s at 60 Hz;
assumed localization SD 0.5 px per coordinate; known scale 600 px/m.

| Case | B0 held-out xy RMSE (px) | B1 held-out xy RMSE (px) | B2 geometry |
|---|---:|---:|---|
| No fault | 0.7204 | 0.7215 | One circle only |
| Parameter fault | 40.7895 | 0.6890 | One circle only |
| Vertical peg | 72.2366 | 39.7715 | Two circles; peg error 2.49 mm |
| Off-vertical peg, 10% missing samples | 40.2429 | 22.8737 | Two circles; peg error 16.77 mm |
| Unexcited peg | 0.6975 | 0.6968 | One circle only; peg presence remains ambiguous |
| Short noisy arc | 0.6752 | 0.6774 | Ambiguous |

B2 measures observation-conditioned radial reconstruction, **not** a time-trajectory
prediction. Its residual is reported separately in the evidence report. Near-floor
B0/B1 differences in no-fault data do not establish improvement. A low radial
residual does not guarantee precise center recovery or a unique physical cause.

Methods, verification results, scope resolutions and limitations are documented in
[POC0_BASELINES_IMPLEMENTATION.md](docs/POC0_BASELINES_IMPLEMENTATION.md).

## Scientific scope

The initial release begins on the free side of the peg, with one designated
contact side. A peg on both sides, flexible or slack string, finite-size peg,
3D motion, and stick-slip contact are **not** implemented. Velocity continuity
is enforced for ideal point-peg contact; the angular speed changes with the
radius. These constraints are scientific scope boundaries, not hidden features.

This phase assumes known projection, gravity, release angle, release velocity and
release time. It has no measured phone noise, camera calibration or fitted camera
nuisances. A single observed circle cannot rule out an unexcited peg. B2 uses a
fixed bearing-boundary hypothesis family and an uncalibrated conservative CV
penalty. MDE/power studies, parameter CI coverage, causal identification, sealed
evaluation and full G3 acceptance remain unfinished. Task 04 adds the bounded
investigator described below. No general compiler or frontend is implemented.
The numerical tool process now has OS-enforced resource isolation; a separate
sealed storage/evaluation system remains future work.

## Meta API and eligibility

Task 02 adds original-PTS video ingestion, the official SAM 3.1 streamed parser,
mask contour centers and tracking QA, planar/lens calibration, independent release
timing, uncertainty and calibrated B0/B1/B2 interfaces. Original synthetic
contracts and G1 physics are preserved. Real and synthetic evidence are separate.
GitHub Actions is configured to run offline tests and verifiers on pushes/pull requests without keys.

    python scripts/verify_g2.py

Read [G2_READINESS.md](artifacts/G2_READINESS.md),
[G2_IMPLEMENTATION.md](docs/G2_IMPLEMENTATION.md) and the
[real data collection protocol](docs/REAL_DATA_COLLECTION_PROTOCOL.md).
The protocol specifies rig construction, phone placement, measured fiducials/pivot,
stationary/repeated recordings, independent annotations and the frozen split.
Tracked data folders contain empty markers; example inputs contain no invented
footage, coordinates or measured length.

Separate actual SAM verification and real processing:

    python scripts/smoke_sam.py data/raw/free/run_001.mp4 --standard-tier-confirmed --output-dir data/processed/sam_smoke
    python scripts/process_recordings.py configs/g2_manifest.local.json --run-api --output-dir data/processed/g2

Configure local access and complete the example manifest/measurements first.
Missing inputs produce a pending report. Run without --run-api to reuse matching
completed real SAM caches. Fixture caches are rejected. This perception workflow
does not implement a compiler, frontend or sealed evaluator.

Keep MODEL_API_KEY local and use the separate smoke commands. Capability reports
and end-to-end investigations are separate evidence. Full accepted-participant
hackathon rules must still be checked.

## Task 03 structural dynamics and API readiness

B3 fits the validated peg-contact dynamics with deterministic bounded multistart
least squares, directed events, complete trajectories, explicit failed starts
and local sensitivity diagnostics. Run python scripts/verify_structural.py for
the fixed synthetic comparison on whole exploration/development trials. See
[B3_BASELINES.md](artifacts/B3_BASELINES.md) and
[TASK03_IMPLEMENTATION.md](docs/TASK03_IMPLEMENTATION.md). B2 radial error remains
a separate geometric statistic. Predictive accuracy alone does not identify a
physical mechanism. Task 04 adds a finite synthetic null-calibration pilot;
broad structural acceptance and full G3 remain pending.

Muse structured output and a validated local numerical tool round trip remain
separately executable probes:

    python scripts/smoke_meta.py --standard-tier-confirmed

External physical video ingestion has its own REAL_EXTERNAL provenance with
source URLs, creator, open license and original/processed hashes:

    python scripts/prepare_external_video.py --download
    python scripts/smoke_sam.py data/raw/external/blocked-pendulum.mp4 --external-source artifacts/external_source_verified.json --standard-tier-confirmed

The attributed MikeRun CC BY-SA 4.0 example is slow motion. It has no verified
physical time scale or measured camera calibration and cannot supply dynamics
metrics or satisfy the phone G2 gate. Actual SAM/Muse API checks remain NOT_RUN
without a locally configured key. No external clip is classified as self-recorded
phone footage. Public external provenance is separate from synthetic test fixtures.

The Task 03 design has five closed typed schema pairs in
[INVESTIGATOR_TOOL_CONTRACTS.md](docs/INVESTIGATOR_TOOL_CONTRACTS.md) and
[investigator_tool_schemas.json](docs/investigator_tool_schemas.json).
Those v1.0 schemas remain reproducible. Task 04 implements the five tools using
the backwards-preserved numerical modules and closed runtime v1.1 contracts.

## Task 04 executable investigation

The investigator observes, hypothesizes, tests, requests one bounded experiment,
and submits an evidence-cited proposal to a separate scientific validator before
freezing. Outcomes include KEEP_UNCHANGED, CALIBRATE_PARAMETERS,
CORRECT_MEASUREMENT, REPAIR_STRUCTURE and ABSTAIN. Structural acceptance selects
the predefined peg-contact model for prediction, not a uniquely identified cause
or an open-ended equation. The mock policy is explicitly not Muse evidence.

```powershell
# Windows requires Ubuntu WSL; Linux x86-64 uses Landlock/seccomp directly.
python scripts/setup_investigator_runtime.py
python scripts/verify_investigator.py --calibrate
python scripts/run_investigator.py --mode deterministic --case off_vertical_peg --seed 51300
python scripts/replay_investigation.py artifacts/task04/traces/deterministic_off_vertical_peg.json
# Separate opt-in live arm; absent authorization is NOT_RUN, never a mock.
python scripts/verify_investigator.py --run-live --standard-tier-confirmed
```

See [Task 04 implementation and operating limits](docs/TASK04_IMPLEMENTATION.md),
[runtime schemas](docs/investigator_runtime_schemas.json) and the measured
[investigation report](artifacts/task04/INVESTIGATOR_REPORT.md). The registered
pilot uses twenty synthetic null datasets and disjoint post-calibration seeds.
The [readiness assessment](artifacts/task04/TASK04_READINESS.md) records exact
test outcomes, the noise-scale false comparison flag, conservative abstention,
optimizer failures and live/real-world checks still pending.
Calibration is environment-bound; regenerate it after numerical version changes.
Real phone recordings, measured calibration and actual SAM output are still
needed under the [collection protocol](docs/REAL_DATA_COLLECTION_PROTOCOL.md).
Matched live Muse performance, broader power/coverage studies and G2/G3/G4/G5
acceptance are not established by the offline investigator.
