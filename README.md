# REALIGN — Scientific Baselines and G2 Perception Pipeline

**Status: verified physics/baselines and an offline-tested video/SAM pipeline. G2 is NOT PASSED: actual SAM processing and real recordings remain pending.**

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
- A **not-yet-executed** Meta Muse API connectivity smoke-test script.

## Install and run

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
python -m pip install -e '.[dev,perception]'
python -m pytest -q
python scripts/verify_g1.py
python scripts/verify_baselines.py
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
evaluation and G3 acceptance remain unfinished. No agent, compiler or frontend is
implemented. Synthetic truth isolation here is a tested dependency/input boundary,
not the future storage/permission-enforced vault.

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
completed real SAM caches. Fixture caches are rejected. No Muse agent, compiler,
frontend or sealed evaluator was added.

Models have not been called by this package. Use `MODEL_API_KEY` locally for
the Muse connectivity script and consult Meta's official SAM cookbook for the
video API. Full accepted-participant hackathon rules must still be checked.
