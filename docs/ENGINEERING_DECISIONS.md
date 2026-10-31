# REALIGN POC-0 — Implementation Decisions (2026-10-31)

Source basis: `REALIGN_Build_Spec_v1.md`, overridden by `IMPLEMENTATION_CORRECTIONS.md`.

| ID | Decision | Verification |
|---|---|---|
| D1 | Point-like peg, one explicitly selected wrap side | Event continuity, mirror symmetry |
| D2 | Constant pivot and string length *within* a dynamical mode | Free and contact ODE derivation |
| D3 | Ideal contact is lossless, no impact; optional κ ≤ 1 is labeled empirical | Speed and energy checks |
| D4 | Reachability is determined by integration/event crossing, not amplitude shortcut | Out-of-reach test |
| D5 | Slack is outside the supported model and is raised, not silently simulated | Slack test |
| D6 | G1 simulation evidence is independent of real video, Meta integration and agent claims | Reports explicitly labeled synthetic |
| D7 | Inference/agentic benchmark will include fair deterministic compositional search | Pending G3/G4 |
| D8 | Sealed evaluator must have resource access restrictions, not only import rules | Pending evaluation implementation |

## Scientific boundaries

The current POC-0 does **not** discover physics. It establishes a mechanically valid numerical simulator, with robust integration and diagnostics, to serve as a reference when real data arrive.

## Original detailed plan

The full Build Spec is checked in at `docs/REALIGN_Build_Spec_v1.md`. Task 01 adds
observation contracts, synthetic generation, B0/B1/B2 fitting and reproducible
synthetic evidence without changing G1. See `POC0_BASELINES_IMPLEMENTATION.md`
for the precise scope, measured results and remaining G2/G3 work. Later packages
in the plan are not claimed to exist.
