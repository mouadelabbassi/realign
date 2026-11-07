# REALIGN — Development Roadmap

**Status on starter handoff:** G1 physics kernel implemented, initial tests and synthetic verifier present. Everything else must be inspected/implemented and verified, not assumed.

## Phase 0 — Repository orientation & scientific regression
- Run tests and `scripts/verify_g1.py` and inventory the exact functionality.
- Check Git status; preserve user changes. Verify any failures independently.
- Ensure realistic claims in README and artifact provenance.

## Phase 1 — POC-0 mathematical baselines
- Implement deterministic synthetic observation generation, well-defined noise and experiment conditions, B0/B1 fixed-structure fitting, B2 one-versus-two-circle geometric fitting.
- Include unexcited/ambiguous and no-fault cases; do not leak true fault labels into algorithms.
- Write a reproducible baseline report and comprehensive test coverage.
- Task: `docs/plans/01_BASELINES.md`.
- Implemented Task 01 evidence: `artifacts/POC0_BASELINES.md`, reproduced by
  `python scripts/verify_baselines.py`. This completes the bounded synthetic
  baseline slice, not the full POC-0/G3 research program. See
  `docs/POC0_BASELINES_IMPLEMENTATION.md` for verification and limitations.

## Phase 2 — G2 perception with real SAM 3.1 (offline implemented; real checks pending)
- Test actual Meta access with `MODEL_API_KEY` locally: Muse response, structured output and tool call; separately SAM MP4 tracking using the documented parser.
- Add frame-PTS extraction, calibration/coordinate frames, localization uncertainty, track QA and explicit missing frame handling.
- Obtain a real stationary recording, free pendulum video, and peg video from the user; no invented media or claims.
- Integrate observations and simulator predictions in one coordinate frame and measure noise.
- Task 02 implements offline ingestion/calibration/tracking/uncertainty and real
  baseline interfaces. Reproduce fixture evidence with python scripts/verify_g2.py.
  G2 is NOT PASSED: actual phone recordings, measured references, manual reviews
  and live SAM verification remain pending. Follow REAL_DATA_COLLECTION_PROTOCOL.md.

## Phase 3 — G3 structural distinguishability
- Compare B0/B1/B2 and bounded structural B3 on disjoint trials, controlled configurations and noise sweeps.
- Demonstrate both identifiable and observationally ambiguous cases, and measure a minimum detectable effect curve.
- Freeze experimental splits before inspecting holdout outcomes.

## Phase 4 — Typed model revisions and Muse agent
- Task 04 implements a bounded investigator over the existing FREE/PEG models,
  five numerical tools, four experiment types, separate proposal validation,
  synthetic null calibration and offline replay. See TASK04_IMPLEMENTATION.md.
  This is a requested bounded slice, not full G3/G4 acceptance or the general
  typed structural compiler. Live matched Muse evidence remains a separate gate.
- Implement typed `ModelSpec` and validated edits (fixed geometry within each mode), deterministic fit/simulate/compare/score tools, and bounded investigation state machine.
- Implement experiment scoring with uncertainty, quality checks and admissibility rules.
- Muse proposes alternatives/experiments/edits, with numeric evidence from tools; it never invents scores or sees sealed outcomes.
- Verify all five decisions and ABSTAIN on synthetic cases.

## Phase 5 — Independent G5 validation
- Freeze model hash and decisions, blind peg geometry commitment (publish only hash, reveal secret after freeze), sealed trials, and failure-inclusive audit.
- Run matched classical ablations including grammar-compositional search with equal evidence and budgets.
- Report actual performance vs B0–B4 and uncertainty; distinguish structural accuracy from predictive accuracy.

## Phase 6 — Hackathon delivery
- Interactive real-versus-sim replay and investigation timeline, model revision diff and evidence report.
- Public GitHub repo, reproducibility commands, licensing, attribution, source honesty, results and limitations.
- Verify actual participant-specific Meta hackathon rules and submission checklist; do not assume bonus eligibility.
- A recording is not represented as live execution. A mathematical proof is not represented as experimental evidence.

## Stop gates
G1 correct numerical physics → G2 measurable real observation → G3 structural distinguishability → G4 attributable Muse value → G5 independent blinded repair. Record a test artifact for each gate, including failures.
