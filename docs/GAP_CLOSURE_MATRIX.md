# REALIGN Gap Closure Matrix

**Baseline:** commit `88b1e13a756c369e4131769ce734ab4dff843ea4`. **Target repo path:** `docs/GAP_CLOSURE_MATRIX.md`.
**Source basis:** `REALIGN_Architecture_vFinal_Execution_Contract.md` and earlier project documents. I could not read the repository itself, so module names are the directories named in the contract (`src/realign/agent/`, `src/realign/physical/`, `src/realign/validation/`, `src/realign/product/`) plus **NEW (proposed)** files. **VERIFY** means Codex must confirm against the code first.

**Severity:** Critical (blocks a truthful claim or the submission), High, Medium, Low.
**Class:** SCI-IMPOSSIBLE, MISSING-DATA, IMPL (implementation defect), UX (unfinished usability), PROCESS (rights, rules, CI).
**Can code solve?** YES, PARTLY (code makes the gap visible or safe but cannot supply the evidence), NO.

## A. Evidence and physical science

| ID | Gap and root cause | Sev | Class | Can code solve? | Module(s) | Objective acceptance test | Physical or human dependency | Fallback |
|---|---|---|---|---|---|---|---|---|
| G-01 | No controlled own recordings, so no real physical claim. Root cause: no rig data exists. | Critical | MISSING-DATA | NO (code only gates and labels) | `src/realign/physical/`; NEW `src/realign/physical/admission.py` | Admission validator accepts a fixture recording and rejects the malformed set; ladder stays below C4 without an admitted file | Owner records stationary, free and peg clips with a calibration reference | Ladder caps at C3a; no physical-model claim anywhere |
| G-02 | Human reference deficit: all 50 SAM shape rejections lie in the first 4 s, and clean reference frames start near 5.23 s. Root cause: reference set biased to easy frames. | Critical for C3b | MISSING-DATA | PARTLY | `src/realign/product/` (`/review`); NEW `scripts/compute_manual_review_metrics.py` | Annotation payload contains no tracker output before lock; metrics script reproduces error, bias, p95 from a fixture label file; frames from 0-4 s are in the queue | Independent human clicks the frames (not the author if possible, not an AI) | Accuracy `NOT_VALIDATED`, shown as such |
| G-03 | Randomized G5 geometry failure (14.477706 mm vs 10 mm) despite 0.7519408442 px trajectory error. Root cause **undetermined**: weak identifiability of peg position from trajectory, or an estimator defect (**VERIFY**). | High | SCI-IMPOSSIBLE or IMPL (undetermined) | PARTLY (diagnostics) | `src/realign/validation/`; NEW `src/realign/diagnostics/geometry_identifiability.py` | Post-mortem report labelled `POST_MORTEM`; ledger test shows no acceptance value changed; if an estimator changes, it is judged only on fresh pre-registered seeds | None | Report mechanism-class selection and geometry with credible interval, never a tight peg-position claim |
| G-04 | Muse and the deterministic comparator had identical predictive error in the recorded case. Root cause: predefined `PEG_ONE_SIDE` model makes both policies converge. | High | Result (not a defect) | YES (honest labelling) | `src/realign/product/`; `src/realign/agent/` | Rule test: when the paired difference is within the registered tolerance the Model Decision view shows "no predictive advantage demonstrated" | None | Contribution claim limited to a traceable, bounded tool-using investigation |
| G-05 | Overclaim risk: predefined peg selection described as discovery or repair. Root cause: marketing language outrunning evidence. | High | UX/PROCESS | YES | `src/realign/product/` strings; README | String-lint test: forbidden phrases ("discover", "repaired a real", "outperforms") fail the build unless the ladder level permits them | None | None needed |
| G-06 | Real versus synthetic provenance can be misread. Root cause: labels are per artifact, not enforced per payload. | Critical | UX | YES | NEW `src/realign/product/claim_ladder.py`; `src/realign/product/` API and front end | Every endpoint returns the evidence header; UI refuses an unlabelled payload; golden ladder test on the current repo state | None | None needed |
| G-07 | External clip has unknown capture time base and physical scale. Root cause: slow-motion source with no metadata. | High | SCI-IMPOSSIBLE (without calibration) | YES (refusal) | `src/realign/physical/` | Test: physical fit and mm display refused for `timing_basis=PTS_ONLY`, `scale=UNKNOWN` | None | The clip stays a perception test only |
| G-08 | AI visual labels (assumed 3 px sigma) could be mistaken for ground truth. Root cause: no enforced separation. | High | PROCESS | YES | `src/realign/product/`; artifact schema for `external_reviews.ai_visual.json` | Test: metrics script refuses AI-labelled files as reference | None | None needed |

## B. Physical action, media and calibration

| ID | Gap and root cause | Sev | Class | Can code solve? | Module(s) | Objective acceptance test | Dependency | Fallback |
|---|---|---|---|---|---|---|---|---|
| G-09 | Pending physical experiment behaviour is not a formal state machine (**VERIFY** what exists). | High | UX/IMPL? | YES | `src/realign/physical/`; NEW `pending_experiment.py` | State-transition tests (`REQUESTED`, `AWAITING_RECORDING`, `VALIDATING`, `ADMITTED`, `REJECTED`, `EXPIRED`); real mode never auto-fills; expiry gives `ABSTAIN` | Owner supplies the requested recording | Auditable pending state with checklist |
| G-10 | Malformed media: truncated files, no video stream, variable frame rate, missing PTS, rotation metadata, zero length. | High | IMPL? | YES | NEW `src/realign/physical/admission.py` | Generated fixture suite (`tests/vfinal/fixtures/`) maps each defect to a typed error code | None | Reject with reason |
| G-11 | Unknown release time or timing basis. | High | MISSING-DATA / IMPL? | PARTLY | `src/realign/physical/` | Release onset detected with uncertainty or the trial is flagged `release_time_unknown`; dynamic fits refused when unknown | A clean recording with visible release | Geometry-only analysis (B2), flagged |
| G-12 | Insufficient calibration (scale, pivot, roll, noise sigma, time base). | High | MISSING-DATA | PARTLY | NEW `calibration_grade` in `src/realign/physical/` | Grade computed from the record; `NONE` or `PARTIAL` forces pixel-only mode | Owner measures a reference, pivot and stationary clip | Pixel-only exploration, no mm |
| G-13 | SAM tracking failures and gaps. | Medium | IMPL? | YES | `src/realign/physical/` | Coverage threshold test; gaps preserved, never interpolated; HSV tracker used only as a cross-check | Better footage if coverage is low | Clip rejected for fitting |

## C. Sealed evaluation integrity

| ID | Gap and root cause | Sev | Class | Can code solve? | Module(s) | Objective acceptance test | Dependency | Fallback |
|---|---|---|---|---|---|---|---|---|
| G-14 | One-shot evaluation and commitment chain need adversarial proof (**VERIFY** what exists). | High | IMPL? | YES | `src/realign/validation/`; NEW `tests/vfinal/test_sealed_adversarial.py` | All 10 adversarial cases in Stage 3 pass (threshold tampering, heldout replay, freeze swap, ledger edit or reorder, nonce mismatch, challenge id mismatch, evaluation before commitment, domain-tag confusion, truncation, duplicate challenge) | None | Report which cases fail |
| G-15 | Commitment lacks domain separation (**VERIFY**). | Medium | IMPL? | YES | `src/realign/validation/` | Commitment hashes a length-prefixed, domain-tagged encoding; a known-answer vector test | None | None |
| G-16 | Boundary around the sealed zone is software-only. | Medium | Limit | PARTLY | `src/realign/agent/`, `src/realign/product/`, `src/realign/validation/` | Import-boundary test plus a tool-allowlist schema test; docs state the limit | Real custodian for any trust claim | Claim only the tested boundary |
| G-17 | No real sealed assessment exists. | Critical for C6 | MISSING-DATA | NO | `src/realign/validation/` | Real custodian measures geometry, controls heldouts, commits before investigation, reveals after freeze | Independent person plus own recordings | Synthetic G5 labelled a workflow exercise |

## D. Product, release and process

| ID | Gap and root cause | Sev | Class | Can code solve? | Module(s) | Objective acceptance test | Dependency | Fallback |
|---|---|---|---|---|---|---|---|---|
| G-18 | README is stale (still describes Task 03/04 states). | High | UX | YES | `README.md` | README matches Task 06 outcomes; a doc-lint test cross-checks the claims against the ladder | None | None |
| G-19 | Browser cannot start an investigation (by design) and there is no first-run guidance. | Medium | UX | YES | `src/realign/product/` | `Run locally` panel lists CLI commands; endpoint audit proves no browser action triggers a credentialed call | None | CLI only |
| G-20 | CI for `88b1e13` was unfinished and one local full run failed on an edit-during-test source-hash mismatch. | High | PROCESS/IMPL? | YES | `.github/workflows/`; NEW `scripts/release_check.*` | `scripts/release_check` runs the suite from a clean `git worktree`; CI link recorded; no "green" claim until green | None | Report exact unresolved failures |
| G-21 | CC BY-SA 4.0 external footage conflicts with typical organizer reuse terms and with the MIT repo. | High | PROCESS | PARTLY | NEW `THIRD_PARTY_NOTICES.md`; `docs/META_COMPLIANCE.md` | Main video contains no external pixels; license files separate; attribution present in retained artifacts | Owner reads the official terms and asks the organizer | Replace with owned footage |
| G-22 | Participant-specific rules, video length, portal fields and bonus eligibility are unverified. | High | PROCESS | NO | `docs/META_COMPLIANCE.md`, `docs/SUBMISSION_CHECKLIST.md` | Each item marked PASS, FAIL, BLOCKED or UNVERIFIED with a source link | Owner confirms in the participant account | Mark UNRESOLVED |
| G-23 | No continuous demo recording of the working product. | High | UX | NO (code can script it) | NEW `scripts/capture_demo.*` (Playwright) | Reproducible capture runs offline from replay; labelled fallback only | Owner records the live narrated version | Replay capture labelled fallback |
| G-24 | Port ambiguity (earlier note said 8765, the contract says 8766 or configurable). | Low | UX | YES | `src/realign/product/` | One configurable port, printed at start and documented | None | None |
| G-25 | Open Weights bonus not demonstrated. | Low | PROCESS | NO | `docs/META_COMPLIANCE.md` | Marked UNRESOLVED; no claim unless a documented open-weight run exists | Organizer eligibility | Do not claim |
