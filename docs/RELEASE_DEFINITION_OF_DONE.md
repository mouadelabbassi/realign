# REALIGN Release Definition of Done

**Baseline:** commit `88b1e13a756c369e4131769ce734ab4dff843ea4`. **Target repo path:** `docs/RELEASE_DEFINITION_OF_DONE.md`.
**Status values:** `PASS`, `FAIL`, `BLOCKED_INPUTS` (needs physical or human input), `UNVERIFIED` (needs the owner or organizer). Only an item with a recorded command, artifact or sign-off may be `PASS`.

**Three independent gates.** Software readiness does not imply physical-science readiness, and neither implies submission readiness. The public claims on the README, in the UI and in the video are limited by the lowest gate that supports them, and the Evidence Ladder computes that limit.

**Source basis:** the execution contract and earlier project documents. I could not read the repository at `88b1e13`, so statuses below are initial values from the contract, not code verification.

## 1. Software readiness

| ID | Criterion | Objective check | Initial status |
|---|---|---|---|
| S-1 | Source pinned, release branch exists | `release/vfinal` at a recorded SHA | UNVERIFIED |
| S-2 | Tests and CI truthful | `scripts/release_check` passes from a clean worktree; CI link recorded; no "green" claim before it is green | FAIL at audit (CI unfinished; one local run failed on a source-hash mismatch) |
| S-3 | Application starts reliably | One documented command, one configurable port printed at start | UNVERIFIED |
| S-4 | All five views plus `/review` work | Playwright suite on desktop and narrow sizes, including missing artifacts, missing external video and missing API key | UNVERIFIED |
| S-5 | Evidence header on every payload; Evidence Ladder computed | `test_every_endpoint_has_evidence_header`, `test_ladder_golden_current_state` | FAIL (not yet implemented) |
| S-6 | Existing real Muse and SAM traces inspectable and correctly labelled | Trace view loads receipts with request ids and domain labels | UNVERIFIED |
| S-7 | Synthetic G5 reproduced exactly: fixed control PASS (0.6930905745 px, 5.602553 mm) and randomized FAIL (0.7519408442 px, 14.477706 mm vs 10 mm) | Replay shows both outcomes with registered thresholds read-only | UNVERIFIED |
| S-8 | Sealed-evaluation adversarial tests pass | The 10 adversarial cases and the import-boundary and allowlist tests pass | UNVERIFIED |
| S-9 | Physical pending state and admission work | Fixture suite of malformed media maps to typed codes; real mode never auto-fills | UNVERIFIED |
| S-10 | A real controlled recording can be admitted, or the system reports `BLOCKED_INPUTS` | Admission test with a valid fixture; blocked state test | UNVERIFIED |
| S-11 | Agent-value rule shows "no predictive advantage demonstrated" on the recorded case | `test_agent_value_label_on_recorded_case` | FAIL (not yet implemented) |
| S-12 | No browser action can trigger a credentialed API call | `test_no_endpoint_triggers_paid_call` | UNVERIFIED |
| S-13 | No secrets in tracked files or history | Secret scan over the tree and history | UNVERIFIED |
| S-14 | README rewritten, evidence index and release documents present | Doc-lint cross-checks README claims against the ladder | FAIL (README stale) |

**Software ready when:** S-1 to S-14 are `PASS`, or each exception is listed with its exact reason.

## 2. Physical-science readiness

| ID | Criterion | Objective check | Initial status |
|---|---|---|---|
| P-1 | Independent human pixel labels | Locked `manual_reviews.json`, hash-bound to frame hashes and original PTS; error, bias and p95 reported, grouped by accepted versus rejected frames; the 0-4 s interval sampled | BLOCKED_INPUTS (accuracy `NOT_VALIDATED`) |
| P-2 | Controlled real recordings | Own stationary, free-swing and peg clips admitted with manifests | BLOCKED_INPUTS |
| P-3 | Calibration `SUFFICIENT` | Scale with reference object, pivot, roll, noise sigma from a stationary clip, verified time base | BLOCKED_INPUTS |
| P-4 | Verified physical timing and release | Capture-time verification record; release onset estimated with uncertainty | BLOCKED_INPUTS |
| P-5 | Independently measured geometry | A person other than the investigator measures peg and pivot; measurement committed | BLOCKED_INPUTS |
| P-6 | Fresh reserved heldouts | Heldout recordings withheld from the investigation and the agent | BLOCKED_INPUTS |
| P-7 | Real-data baselines | B0 and B1 (and B2, B3) applied to calibrated real observations; failures reported | BLOCKED_INPUTS |
| P-8 | Acceptable uncertainty | Geometry credible interval narrower than the registered tolerance, or the claim is withheld | BLOCKED_INPUTS |
| P-9 | Real sealed G5 verdict | Independent custodian, commitment before investigation, one-shot evaluation, reveal, report whether PASS or FAIL | BLOCKED_INPUTS |
| P-10 | Fair scientific claims | No agent superiority claim while the comparator matches; no equation-discovery claim for `PEG_ONE_SIDE`; no causal-uniqueness claim | PASS (as a rule; enforced by the string-lint test once implemented) |

**Physical validation is claimed only when:** P-1 to P-9 are `PASS`. Otherwise the submission may state only what the Evidence Ladder supports (currently up to C3a: SAM tracking on real external footage with accuracy not validated).

## 3. Competition submission readiness

Only the owner can confirm the items marked `UNVERIFIED`. Scores are from the rubric (Impact 30%, Meta tooling 25%, Demo 25%, Technical depth 20%).

| ID | Criterion | Objective check | Initial status |
|---|---|---|---|
| C-1 | Participant status and accepted official rules | Owner confirms in the participant account | UNVERIFIED |
| C-2 | Work period and authorship | Commit history sits inside the build window (Oct 26 to Nov 4); only event work is demoed; third-party code credited; AI-assistance provenance recorded in `docs/PROVENANCE.md` and checked against the rules | UNVERIFIED |
| C-3 | Public repository | Public, license present, scaffolding removed, third-party notices present | UNVERIFIED |
| C-4 | Media rights for CC BY-SA 4.0 external footage | Main video contains no external pixels (Cut A); attribution and license files kept for retained artifacts; organizer answer recorded, or footage replaced with owned footage | UNVERIFIED |
| C-5 | Not a banned or overdone project type | Product reads as an investigation workflow, not a dashboard, image analyzer or basic RAG app | UNVERIFIED |
| C-6 | Meta tooling evidence | `artifacts/release/meta_evidence_index.md` from real receipts: request ids, model ids `muse-spark-1.3` and `sam-3.1`, billed usage | UNVERIFIED |
| C-7 | Demo video | Continuous narrated screen recording per the storyboard, within the portal's length limit, with the G5 failure visible; montage only as a labelled fallback | BLOCKED_INPUTS (owner recording) |
| C-8 | Evaluator quickstart | A stranger can run replay in about two minutes from the README | UNVERIFIED |
| C-9 | Submission form and portal | Fields, upload, acknowledgement saved | UNVERIFIED |
| C-10 | Deadline | Official deadline per the public event page: November 4, 2026, 9 PM ET, subject to organizer changes; submit early enough for upload problems | UNVERIFIED (owner confirms) |
| C-11 | Social post (Viral bonus) | If entered: post with the demo link by November 8, 11:59 PM ET, per the kickoff slide | UNVERIFIED |
| C-12 | Open Weights bonus | No claim unless a documented open-weight run exists and eligibility is confirmed | UNVERIFIED (do not claim) |

**Submission-ready when:** S-1 to S-14 pass (or exceptions are documented), C-1 to C-9 and C-10 are `PASS`, and the README, UI and video claims match the Evidence Ladder.

## 4. Release verdict rule

1. The released claim level is the **minimum** of what the three gates support.
2. A `BLOCKED_INPUTS` or `UNVERIFIED` item is never written as complete in any document.
3. The recorded failures stay in the submission: the randomized G5 geometry failure, the comparator parity, and the unvalidated external accuracy.
4. The honest submission state if no physical inputs arrive: software ready, Evidence Ladder at C3a, physical gate `BLOCKED_INPUTS`, and claims narrowed accordingly. That state is acceptable. A manufactured physical claim is not.
