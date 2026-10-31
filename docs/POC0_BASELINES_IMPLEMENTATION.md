# Task 01 — Implemented scope and engineering evidence

**SYNTHETIC ONLY — NO META API / REAL-WORLD VALIDATION**

Task 01 continues Architecture v1.1. No G1 physics source, oracle or existing
physics test was changed. This is the Phase 1 vertical slice from the roadmap,
not the full Build Spec's POC-0 definition of done.

## Repository baseline before edits

- Git: clean `main`, tracking `origin/main`, commit `9b74190`.
- Implemented then: event-driven free/peg simulator, ideal analytic periods,
  viscous/quadratic drag, slack rejection, 12 physics tests, G1 synthetic verifier,
  and an unexecuted simple Muse connectivity script. No observation or fitter packages.
- `python -m pip install -e ".[dev]"`: succeeded.
- `pytest -q`: executable unavailable on this shell's PATH. The equivalent
  `python -m pytest -q` passed **12 tests in 2.22 s**.
- `python scripts/verify_g1.py`: PASS; 250 configurations, zero failures,
  1,516 transitions. Maximum absolute energy drift 1.709933528104557e-9 J/kg,
  position jump 1.9849118084270064e-15 m, speed jump 4.440892098500626e-16 m/s,
  vertical-peg period error 6.247757866617576e-11 s. Numerical values match the
  checked-in evidence; elapsed time is machine dependent (this run 7.214 s).

## Contracts and synthetic generation

Validated frozen dataclasses in `contracts` describe the experiment, observation,
known plane projection, and assumed noise. Observations store increasing release-
relative timestamps in s, xy in px, Boolean validity and symmetric PSD covariance
in px². Valid positions must be finite. Invalid rows remain on the original grid
and contain NaN; there is no interpolation into observations. Arrays are copied
and made read-only. Whitening requires positive definite covariance; exactly zero
noise is supported for clean geometric recovery tests, not stochastic likelihoods.

`synth/generator.py` calls the unchanged G1 simulator, which enforces the free-side
release contract and determines contact through directed events. It returns two
separate records: an observation-only `Trial` and an evaluation-only
`SyntheticTruth` defined in `synth/truth.py`. Trial IDs are opaque; there are no
fault, mode, event, true-parameter or hidden-geometry fields in `Trial`.

The explicit synthetic projection is
`u = u0 + scale*x`, `v = v0 - scale*y`; scale is in px/m. This does not implement
real calibration, a homography, rolling shutter, timestamp jitter or mask bias.
The sample grid begins at the prescribed release time. Noise is zero-mean
Gaussian with user-specified marginal covariance C. Optional common-axis AR(1)
uses stationary initialization and innovation covariance `(1-phi²)*C`.
Dropout is reproducible and independent of localization noise. Defaults are
design assumptions, never SAM/phone performance estimates.

## B0 and B1

B0 predicts the original free-pendulum model at nominal parameters. B1 jointly
fits shared length, viscous drag and (by default) quadratic drag on all supplied
training trials. Initial release angle, angular velocity, time, gravity and
projection are prescribed experimental inputs. The fitter never estimates a
new state from each observed frame; every residual uses a complete G1 rollout.

Eight deterministic starts cover the bounded parameter box and nominal start.
The fitter uses SciPy `least_squares`, TRF, soft-L1, Jacobian scaling, and records
every initial point, fitted point, termination status, cost and bound activity.
The robust scale is derived from nominal **training** residual MAD and floored at
one whitened unit. Convergence is not a goodness-of-fit claim. Exhausted budgets,
exceptions, insufficient data and rank deficiency are explicit failures. At/near
bound fits receive warnings, not calibrated intervals or structural conclusions.

Length is optimized in log coordinates. Drag is optimized directly with
nonnegative bounds so exact zero drag remains in the parameter space; log(0)
would exclude that physical null. No tape-measure prior is invented for these
synthetic inputs. This deliberately restricts the full spec's nuisance fitting to
the Task 01 experiment with known release/projection; real nuisances and priors
require Phase 2 calibration evidence.

For residual e, spatial whitening is `z = chol(C)^(-1)*e`. For valid samples i,j
separated by d original grid steps, innovation whitening is
`(z_j - phi^d*z_i)/sqrt(1-phi^(2*d))`. The first valid point uses its marginal
covariance. Innovations restart independently for each trial. This handles gaps
without treating temporally correlated frames as independent.

Scores include Euclidean xy RMSE, raw NRMSE, excess NRMSE, mean squared whitened
innovation per coordinate and consecutive-frame x residual correlation. The
normalizer is the nominal length in pixels, never the hidden true length.
The synthetic expected xy MSE floor is `trace(C)`; it is explicitly not a
repeat-estimated real noise floor. A clipped zero excess score is not proof of
zero model error.

## B2

The original pivot is known from the synthetic projection. The one-circle model
fits its radius. The two-circle family uses this original circle plus one free
center/radius circle, separated by a recurrent polar-bearing boundary and side.
It searches 25 training-bearing quantiles between 18% and 82%, in both directions.
All cycles share the same geometry. It does not use mode labels, true geometry,
simulator outputs, transition times, or release angles for segmentation.

Circle initialization is centered algebraic least-squares, refined using robust
orthogonal radial distance. The finite numerical envelope is center components
within ±10 m, radius (1e-6,10] m. Fewer than 12 points, effectively collinear data,
arc span below 0.20 rad, or sagitta below four localization SD are rejected.
The largest covariance eigenvalue defines a conservative scalar metric SD for
anisotropic noise; this is not an exact anisotropic radial likelihood.

Each training trial is left out in turn; both candidate models are refit to the
remaining whole trials and scored on the omitted trial. The two-circle family
must improve CV squared radial residual/noise scores beyond
`4*log(N_eff) + 2*log(50)`. The four added continuous parameters are center x/y,
second radius and boundary; the search term covers the fixed candidate family.
For correlated noise, CV evidence is conservatively scaled by
`N_eff/N`, using `N_eff = sum N_valid*(1-|phi|)/(1+|phi|)`.
This is a fixed design penalty, not a calibrated likelihood ratio, false-positive
rate, BIC-based decision or final G3 gate. At least two training trials are needed.

Insufficient curvature or failed fold candidates return `ambiguous`. Otherwise,
without sufficient CV improvement the result is `one_circle_only`, with the
explicit warning that unexcited mechanisms remain possible. `two_circle` means
two supported arcs, not a uniquely identified mechanism. Individual rejected
candidate fits are counted rather than concealed.

B2 uses the observed bearing to reconstruct radial distance from fitted circles.
Its radial RMSE cannot be compared as a predictive improvement over B1's complete
xy time trajectory. The inferred second center is compared with truth only after
fitting, in evaluation/report code.

## Reproducible evidence

`python scripts/verify_baselines.py` runs a fixed six-case matrix with two
exploration training releases and one disjoint development release per case.
Base seed is 20261031; NumPy SeedSequence derives and records each trial's seed.
Duration is 4 s, grid 60 Hz, scale 600 px/m, localization SD 0.5 px per coordinate.
The off-vertical case drops 10% of samples. Default report noise is IID; separate
tests verify AR(1), correlated covariance and gap-aware whitening numerically.

Measured unseen-trial xy errors (B0 → B1, px): no fault 0.7204 → 0.7215;
parameter fault 40.7895 → 0.6890; vertical peg 72.2366 → 39.7715;
off-vertical peg 40.2429 → 22.8737; unexcited peg 0.6975 → 0.6968;
short noisy arc 0.6752 → 0.6774. The small no-fault deterioration is expected
sampling/fitting variability, not an improvement claim.

B2 supports second circles on the two excited peg cases. Post-fit peg errors
are 2.49 mm (vertical) and 16.77 mm (off-vertical), despite respective radial
RMSEs near 0.49 and 0.52 px. The latter demonstrates that near-noise radial
error does not guarantee precise center localization. No second pivot is
supported on no-fault, parameter-fault or unexcited-peg cases. The short arc is
explicitly ambiguous. All 48 B1 starts converged in the matrix; some best fits
approach bounds and no parameter CI is claimed. Rejected B2 candidates are listed.

Artifacts:

- `POC0_BASELINES.md`: conditions, measured scores, failures, limitations and plot.
- `poc0_baselines.json`: full start diagnostics, train/development scores,
  leave-one-trial-out geometry scores/penalty, public metadata, source SHA-256,
  observation fingerprints, package versions and all acceptance checks.
- `poc0_baselines.png`: explicitly synthetic held-out observations, B0/B1
  rollouts, geometric fit and residuals; visually inspected after generation.
- `poc0_observations.npz`: observation arrays only, with opaque IDs.
- `poc0_truth_evaluation.json`: separate synthetic parameters, seeds and
  contact/error evaluation, never supplied to fitters.

The observation content hash covers original times, pixel positions and validity;
public experimental/projection/noise metadata are recorded alongside it. Source
hash covers Python implementation and the entrypoint. Outputs omit timestamps
and elapsed times so they can reproduce byte-for-byte in the same environment.
Different numerical-library versions/platforms may change floating-point bits.

## Verification and isolation

The automated suite includes the original G1 tests, controlled-noise recovery,
clean off-vertical center recovery without labels, excited-peg residual structure,
no-peg/no-contact controls, exact unexcited observational equivalence, short-arc
abstention, wrong units/covariance, all-missing data, solver exceptions and budget
exhaustion. Whole-trial splits reject both identical IDs and renamed copies of
the same observation arrays. Perturbing development observations cannot change
fitted parameters or geometric CV results.

Inference packages (`contracts`, `observation`, `physics`, `fit`) have no imports
of synthetic truth/generation or file-reading calls. Tests check those dependencies
and execute fitting in a fresh process that rejects synthetic/vault imports and
truth-file reads, with a truth canary. The caller passes observations only. This
is input/dependency isolation for the current synthetic slice, not a security
boundary against hostile Python or an implementation of the sealed vault.

The report integration test runs the complete matrix twice and compares returned
records plus JSON, Markdown, PNG and observation-archive bytes. Final observed
commands/results after implementation:

| Command | Actual outcome |
|---|---|
| `python -m pytest -q` | **38 passed in 390.11 s**, including 12 original physics tests and 26 new baseline/contract/integration tests; no skipped tests |
| `python scripts/verify_g1.py` | **PASS**: 250 cases, 0 failures, 1,516 transitions; numerical metrics unchanged; final elapsed time 8.783 s |
| `python scripts/verify_baselines.py` | **PASS**: 6 cases, 18 whole trials, 13 acceptance checks; all 48 B1 starts converged |
| `git diff --check` | PASS on tracked changes |

The suite includes two full report builds, not a mocked report test. Meta API,
SAM and physical experiments were **not run**; no network tests are included in
these counts. The initial `pytest -q` PATH issue is recorded above; use the
module form with this Python installation.

## Files created or modified

Created implementation:

- `src/realign/contracts/__init__.py`
- `src/realign/observation/{__init__,camera,noise}.py`
- `src/realign/synth/{__init__,generator,truth}.py`
- `src/realign/fit/{__init__,robust_fit,circle_fit,baselines}.py`
- `src/realign/report/{__init__,baseline_report}.py`
- `scripts/verify_baselines.py`
- `tests/test_baselines.py`
- `docs/POC0_BASELINES_IMPLEMENTATION.md`
- The five baseline artifacts listed above under `artifacts/`.

Modified documentation/metadata: `README.md`, `pyproject.toml`,
`docs/CODEX_EXECUTION_ROADMAP.md`, `docs/ENGINEERING_DECISIONS.md`, and
`docs/PROVENANCE.md`. `artifacts/g1_verification.json` was regenerated; only its
machine-dependent elapsed time changed. The other three G1 artifacts reproduced
without changes. The working tree contains 27 new/modified files, all local and
uncommitted. No G1 source, existing physics tests, architecture/specification,
task instructions or Meta smoke-test code changed.

## Limitations and next phase

This matrix is not 300-trial CI coverage, Monte Carlo false-positive calibration,
an MDE/power curve or interventional causal validation. B2's bearing family and
finite search can miss weak/short contact arcs and does not provide calibrated
center intervals. B1's gamma/quadratic-drag tradeoff and bound behavior need
broader identifiability studies before physical parameter claims. The current
truth boundary must be replaced by storage/permission controls before a real
investigator or sealed evaluator exists.

Task 01 supplies the tested classical comparison foundation. G2 and full G3 are
not passed. Phase 2 requires actual Meta account access tests, separate SAM MP4
tracking with its real parser, frame PTS, real stationary/free/peg recordings,
camera calibration, measured static/dynamic covariance and track quality gates.
No account access, API success, real noise, real measurements, Muse advantage or
five-way autonomous decision is claimed here. No commit or push is authorized
by this implementation task.
