# Implementation Corrections — Blocking errata for Build Spec v1

These decisions were made by independent review of the Build Spec. They override conflicting statements in that spec without changing the frozen five-layer architecture.

1. **Fixed geometry within a mode.** The proposed expression DSL must not allow state-/velocity-/time-dependent pivot or string length while compiling with the constant-length pendulum equation. Reject those dependencies, or derive a valid general Lagrangian before supporting them. Potential must not depend on velocity; check dissipation sign and dimensions.
2. **Contact reachability.** The simplified `abs(release angle) > abs(peg angle)` condition is not a general criterion with damping, arbitrary release side or nonzero initial velocity. Use integration with directed guards, energy/feasibility constraints, and explicit supported initial configurations.
3. **Lossless ideal contact.** Use kappa_in = kappa_out = 1 for the ideal model. Any loss factors are explicitly empirical extensions. Do not assert only their product can be identified from every measurement design; check identifiability under observed event resolution.
4. **Fair agentic ablation.** The comparator with the same fixed library is useful, but must not be the only comparison. Include a bounded deterministic grammar/compositional search with comparable primitives, budgets, and observations for claims of special Muse reasoning value.
5. **Uncertainty units.** Localization covariance entries have units px², not px. Explicitly validate covariance symmetry and positive semidefiniteness and separate timestamp standard deviation in seconds.
6. **Resource isolation.** Import-linter checks are necessary hygiene, not a security boundary. Enforce storage/permission restrictions and tool allowlists so no Muse-accessible process or wrapper can access sealed trials, hidden truth, or reveal nonce before freeze. Audit exposure after reveal is separately gated.

**Additional empirical caveats**
- The original starter's G1 tests are numerical verification over idealized models. They do not validate SAM, physics in the real rig, broad structural discovery, or winning chances.
- The starter `scripts/smoke_meta.py` tests a simple Muse response only; SAM video, structured output and tool round-trip are NOT yet tested. Never label them completed.
- Real video/noise must be measured; synthetic noise defaults are not established SAM performance figures.
- The LLM's proposed model cannot validate itself, and the experiment selected via replay must be labeled replay rather than live execution.
