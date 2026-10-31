# REALIGN — POC-0/G1 Starter Repository

**Status: working physics reference kernel; not yet the completed REALIGN AI investigator.**

REALIGN aims to audit physics simulations against phone-measured reality,
request discriminating experiments, propose typed structural corrections and
validate them using sealed independent evidence.

This starter repository implements the **first tested scientific foundation**:

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
- A **not-yet-executed** Meta Muse API connectivity smoke-test script.

## Install and run

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
python -m pip install -e '.[dev]'
pytest -q
python scripts/verify_g1.py
```

Outputs: `artifacts/G1_REPORT.md`, `artifacts/g1_verification.json`,
`artifacts/synthetic_trajectory_comparison.csv`, and (with matplotlib)
`artifacts/synthetic_discrepancy.png`.

## Scientific scope

The initial release begins on the free side of the peg, with one designated
contact side. A peg on both sides, flexible or slack string, finite-size peg,
3D motion, and stick-slip contact are **not** implemented. Velocity continuity
is enforced for ideal point-peg contact; the angular speed changes with the
radius. These constraints are scientific scope boundaries, not hidden features.

## What's next

1. Independently calibrate the physical rig and camera.
2. Run a real SAM 3.1 uploaded-MP4 video smoke test using the official parser.
3. Implement timestamped observation and covariance contracts.
4. Implement parameter-only and geometric two-circle baselines, then G2/G3.
5. Only then integrate Muse tool-use and the sealed model-revision evaluation.

See `docs/ENGINEERING_DECISIONS.md` and `docs/META_SMOKE.md`.

## Meta API and eligibility

Models have not been called by this package. Use `MODEL_API_KEY` locally for
the Muse connectivity script and consult Meta's official SAM cookbook for the
video API. Full accepted-participant hackathon rules must still be checked.
