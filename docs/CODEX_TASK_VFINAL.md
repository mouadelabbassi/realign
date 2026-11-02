# CODEX TASK vFinal: staged engineering mandate

**Baseline:** commit `88b1e13a756c369e4131769ce734ab4dff843ea4`. **Target repo path:** `docs/CODEX_TASK_VFINAL.md`.
**Read first:** `AGENTS.md`, `docs/IMPLEMENTATION_CORRECTIONS.md`, `docs/TASK05_IMPLEMENTATION.md`, `docs/TASK06_IMPLEMENTATION.md`, `artifacts/task06/TASK06_READINESS.md`, `docs/META_COMPLIANCE.md`, `ARCHITECTURE_VFINAL.md`, `GAP_CLOSURE_MATRIX.md`.

## Source limits

The author of this mandate could not read the repository at `88b1e13` and worked from the execution contract. Existing code and tests take precedence over every narrative document. Names marked **NEW (proposed)** must be replaced by an existing equivalent if one exists. Items marked **VERIFY** are hypotheses to confirm before you change anything. Do not report a defect you have not reproduced.

## Hard rules

1. Do not add layers, agents, services, physical domains, a broad physics engine or a generic generated-code executor.
2. Do not rewrite verified G1 to B3 science.
3. Do not change any registered G5 threshold, do not re-run a consumed heldout, and do not use consumed heldout data for tuning.
4. Never mark physical, human or organizer-dependent items complete. Use `PASS`, `FAIL`, `BLOCKED_INPUTS` or `UNVERIFIED`.
5. Do not fabricate, backfill or relabel data. `SYNTHETIC`, `REAL_EXTERNAL` and `REAL_PHONE` are immutable once assigned.
6. Do not make paid API calls except where a stage explicitly requires one. Preserve existing authentic Muse and SAM receipts and do not rerun them for decoration.
7. One coherent checkpoint commit per stage, with tests. No force-push of evidence. Work on a `release/vfinal` branch.

## Hard stop conditions

Stop and report (do not work around) if: a test requires editing a registered threshold; a stage would need a consumed heldout; a secret is found in tracked history; the sealed-boundary import test fails and cannot be fixed without moving sealed code into the agent layer; or any stage's exit condition fails twice.

## Stage 0: baseline lock and truthful test state

**WHY:** one local full run failed on an edit-during-test source-hash mismatch, and CI for `88b1e13` was unfinished. Every later stage needs a trustworthy baseline.
**Do:**
- Pin the SHA and create `release/vfinal`. Run `git status` and `git diff --check`, confirm `.env` exclusion, and run a secret scan over tracked files and history.
- NEW `scripts/release_check.*`: create a clean `git worktree` at the pinned SHA, install, run `python -m pytest -q` plus the repo's documented verify scripts, and write the outcome. Running from a clean worktree removes the edit-during-test race.
- Run the five-view browser checks and JS syntax check that already exist (**VERIFY** their commands in `AGENTS.md`).
- Write `artifacts/release/BASELINE_AUDIT.md` listing exact commands, successes, failures and unresolved items. Record whether validation reports were generated before a commit and update release metadata truthfully, not execution histories.
**Exit:** the audit file exists; every command is recorded with its real outcome; CI status is quoted from the actual run.
**Proof:** the release script exit code, and the CI link stored in `docs/RELEASE_READINESS.md`.

## Stage 1: evidence header and Evidence Ladder (D1, D2, G-05, G-06, G-08)

**WHY:** real-versus-synthetic confusion is the largest credibility risk.
**Files:** NEW `src/realign/product/claim_ladder.py`; extend the API and front end in `src/realign/product/`.
**Contract:**
- Every payload carries `source_domain`, `policy`, `run_id`, `stage` and `ladder_level`.
- `compute_ladder(artifacts) -> LadderState` returns the highest level whose prerequisites are all met (C0, C1, C2, C2-G5, C3a, C3b, C4, C5, C6 as defined in `ARCHITECTURE_VFINAL.md`), the unmet prerequisites of the next level, and the negative-results list (G5 randomized failure, agent-value verdict).
- The front end refuses to render a payload missing any header field and shows an error panel naming the missing field.
- String-lint: forbidden phrases ("discover", "repaired a real", "outperforms") fail the build unless the ladder level permits them.
**Tests (NEW `tests/vfinal/`):** `test_ladder_golden_current_state` (expects C3a with C3b, C4 to C6 locked); `test_ladder_drops_when_artifact_removed`; `test_every_endpoint_has_evidence_header`; `test_ui_refuses_unlabelled_payload` (browser); `test_forbidden_phrase_lint`; `test_ai_labels_never_ground_truth`.
**Exit:** all tests pass; the ladder renders in all five views.
**Deliverable:** screenshots in `artifacts/release/` (labelled fallback only).

## Stage 2: physical admission, pending actions, calibration grade (D4, D5, G-01, G-07 to G-13)

**WHY:** a software agent cannot produce observations, and bad media must be rejected with reasons.
**Files:** `src/realign/physical/` extended; NEW `admission.py`, `pending_experiment.py`; `calibration_grade` in the calibration module.
**Contract:**
- `admit_recording(path, manifest) -> AdmissionResult` returns `ADMITTED` or a typed code: `UNREADABLE_CONTAINER`, `NO_VIDEO_STREAM`, `ZERO_LENGTH`, `MISSING_PTS`, `VARIABLE_FRAME_RATE`, `DUPLICATE_HASH`, `ROTATION_UNHANDLED`, `COVERAGE_BELOW_THRESHOLD`.
- `PendingExperiment` states: `REQUESTED`, `AWAITING_RECORDING`, `VALIDATING`, `ADMITTED`, `REJECTED`, `EXPIRED`. Real mode never advances without an admitted file. Expiry yields `ABSTAIN` with the reason.
- `CalibrationRecord.grade` is `NONE`, `PARTIAL` or `SUFFICIENT` (scale with reference, pivot, roll, noise sigma with source clip hash, verified time base). Below `SUFFICIENT` the API returns pixel units only and refuses physical fits.
- The external clip is permanently `timing_basis=PTS_ONLY`, `scale=UNKNOWN`.
- A simulated response is available only in synthetic mode and tags its output `SYNTHETIC`.
**Tests:** a generated fixture suite under `tests/vfinal/fixtures/` (truncated file, no video stream, variable frame rate, missing PTS, zero length, rotated, duplicate hash) with `test_admission_error_codes`; `test_pending_state_machine`; `test_real_mode_never_autofills`; `test_mm_refused_below_sufficient`; `test_external_clip_never_physical_fit`; `test_gaps_not_interpolated`.
**Exit:** all pass; the Experiment Loop view shows the pending card with checklist and upload.
**Physical dependency:** none for code. Real admission of an owner recording is an owner task (Stage P).

## Stage 3: sealed-evaluation hardening (D6, G-14 to G-16)

**WHY:** one-shot evaluation and the commitment must survive tampering.
**Files:** `src/realign/validation/`; NEW `tests/vfinal/test_sealed_adversarial.py`, `test_import_boundary.py`, `test_tool_allowlist.py`.
**Contract (VERIFY what already exists, add only what is absent):**
- Registration record with a content hash of the thresholds, committed before evaluation.
- Consumption ledger, an append-only hash chain of consumed heldout ids; the evaluator refuses a consumed id.
- Commitment: `SHA256(domain_tag || len(nonce) || nonce || len(measurement) || canonical_measurement)`, with the nonce from `secrets.token_bytes(32)`. Add a known-answer vector test.
- `FrozenModel` content hash binds the decision, spec, parameters, exploration trial hashes, tool-trace head, code SHA, challenge id and validator protocol hash.
**Adversarial tests (all must pass):** edit a registered threshold; replay a consumed heldout; swap the freeze hash; edit one ledger entry; reorder ledger entries; wrong nonce at reveal; wrong challenge id; evaluate before the commitment exists; truncate the ledger; reuse a challenge id.
**Boundary tests:** no import path from `src/realign/agent/` or `src/realign/product/` to the sealed validator modules; Muse tool outputs pass a forbidden-key scan (`nonce`, `truth`, `heldout`, `peg`, `fault`, `registered_threshold` and equivalents).
**Exit:** all pass. Document that the boundary is software-level and that local chronology is not an external timestamp.

## Stage 4: G5 failure analysis, descriptive only (D7, G-03)

**WHY:** the randomized failure (14.477706 mm vs 10 mm, with 0.7519408442 px trajectory error) is the most informative result and must be explained, not hidden.
**Files:** NEW `src/realign/diagnostics/geometry_identifiability.py`; NEW `docs/G5_FAILURE_ANALYSIS.md`.
**Do:**
- Compute, on the consumed instance only, a descriptive profile of trajectory error versus peg position (using the existing forward model through its public interface; **VERIFY** it exposes one) and report whether trajectory error is flat around the true geometry. Label every output `POST_MORTEM`.
- Classify the cause as weak identifiability or an estimator defect, with evidence. If it is a defect, fix it, then judge the fix only on fresh pre-registered seeds, reported beside G5-v1. **G5-v1 stays FAIL.**
- Add a geometry credible interval to the Model Decision view and block any tight geometry claim when the interval half-width exceeds the registered tolerance.
- Optional ensemble: N pre-registered seeds (register N and the seeds before running), one-shot each, deterministic policy only so no paid calls, reporting the pass count and every failure.
**Tests:** `test_postmortem_cannot_change_acceptance` (the ledger shows the consumed heldout untouched and the verdict byte-identical); `test_g5_v1_record_immutable`; `test_geometry_claim_blocked_when_interval_wide`.
**Exit:** the analysis document states a classification with evidence or states it is undetermined and why.

## Stage 5: agent-value report (D8, G-04)

**WHY:** Muse and the deterministic comparator matched in the recorded example, and no superiority claim is allowed.
**Do:** in the Model Decision view, compute the paired predictive-error difference between the Muse-selected model and the B3 comparator on the same exploration data and budget. Register the tolerance before computing it. If the difference is within tolerance, show "no predictive advantage demonstrated". Report separately the properties Muse does show: valid typed specifications, a traceable tool sequence, a physical experiment request, and abstention behaviour.
**Tests:** `test_agent_value_label_on_recorded_case`; `test_no_superiority_text_unless_rule_met`.
**Exit:** the label appears on the recorded case. No new paid calls.

## Stage 6: product views, annotation workflow, run panel (D3, D9, G-02, G-19, G-23, G-24)

**WHY:** the product must make evidence legible and close the human reference deficit.
**Files:** `src/realign/product/` front end and API.
**Do:**
- Implement the view requirements and the UI state matrix from `ARCHITECTURE_VFINAL.md` section 6.
- `/review`: serve overlay-free frames in randomized order from `artifacts/task05/external_yellow_disc/manual_reviews.template.json`, extended into 0-4 s including invalid frames. Withhold tracker and AI labels until lock. On lock write `manual_reviews.json`, hash-bound to frame hashes and original PTS. NEW `scripts/compute_manual_review_metrics.py` computes error, bias, p95, grouped by accepted versus rejected frames, and repeatability if two annotators exist. If no human file is present, accuracy shows `NOT_VALIDATED`.
- `Run locally` panel: exact CLI commands for a new investigation, the required real recordings, and replay. No endpoint may start a credentialed call. One configurable port, printed at start.
**Tests (Playwright, desktop and narrow):** all five views and `/review` load; video play and scrub stay in sync with original PTS; source and policy switching; all saved G5 outcomes render with registered thresholds; the pending state; missing artifacts, missing external video and missing API key behaviours; tamper display; `test_no_endpoint_triggers_paid_call`; `test_annotation_payload_has_no_tracker_output_before_lock`.
**Exit:** all pass. A reproducible offline capture (`scripts/capture_demo.*`) runs from replay and is labelled fallback only.

## Stage 7: release package (D10, G-18, G-20 to G-22, G-25)

**WHY:** a judge should evaluate the project in minutes.
**Do:**
- Rewrite `README.md` as an evaluator quickstart: value proposition, lab scenario, live Meta use, the comparison, observed evidence, limitations (including the G5 failure), a two-minute quickstart and an evidence index. Keep detailed history in linked documents.
- NEW `THIRD_PARTY_NOTICES.md` and a separate license file for external footage. Exclude the footage and derived frames from MIT scope. Main video Cut A contains no external pixels.
- NEW `artifacts/release/meta_evidence_index.md` from the real receipts (request ids, model ids, billed usage). Do not rerun calls.
- Write `docs/RELEASE_READINESS.md`, `docs/META_COMPLIANCE.md` (each requirement `PASS`, `FAIL`, `BLOCKED` or `UNVERIFIED` with a source link), `docs/ARCHITECTURE_VFINAL.md` and `docs/SUBMISSION_CHECKLIST.md`, each traceable to code, evidence and CI.
- Remove scaffolding (`README_COPY_INSTRUCTIONS.md` and any leftover instruction files) or move it out of the public tree.
**Exit:** `scripts/release_check` passes from a clean worktree; CI link recorded; secret scan clean; documents match the ladder.

## Stage P: physical and human tasks (owner only; code cannot close these)

| Task | Deliverable | Gate unlocked |
|---|---|---|
| Record stationary, free-swing and peg clips with a calibration reference, pivot and string length measured, release angle marked | `RecordingManifest` plus original files | C4 |
| Capture-time verification of the time base | Verification record | `SUFFICIENT` grade |
| Independent human annotation of the sampled frames, including 0-4 s | Locked `manual_reviews.json` | C3b |
| Third-party custodian measures the peg, commits the hash, controls heldout recordings | Public commit before the investigation, reveal after the freeze | C6 |
| Continuous narrated screen recording | Video file | Submission |
| Read the accepted official rules and organizer terms, confirm media rights | Owner sign-off in `docs/SUBMISSION_CHECKLIST.md` | Submission |

If Stage P inputs are absent, the system reports `BLOCKED_INPUTS` and the Evidence Ladder caps at C3a. That is an acceptable, truthful submission state.
