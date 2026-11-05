# REALIGN vFinal — Independent Code Review Addendum

**Review date:** 2026-11-02  
**Verified GitHub baseline:** `mouadelabbassi/realign` @ `88b1e13a756c369e4131769ce734ab4dff843ea4`  
**Role:** This addendum takes precedence over the four original vFinal planning documents **only where they conflict with verified source or scientific integrity**. It is not permission to redesign Architecture v1.1 or erase historical evidence.

## Decision

**Conditionally approve** `ARCHITECTURE_VFINAL.md`, `GAP_CLOSURE_MATRIX.md`, `plans/RELEASE_PLAN.md` and `RELEASE_DEFINITION_OF_DONE.md` as a release-hardening specification. Preserve the five logical layers, the existing read-only offline replay, the authentic Task 05 traces, the Task 06 synthetic G5 pass and failure, and existing science code. No new agent, domain, compiler or service.

The original planning review did not inspect the live repository. Developers must check every `VERIFY` and `NEW (proposed)` instruction against actual source before creating a module or changing a contract.

## Verified baseline corrections

1. **CI is already green.** GitHub Actions run `41533276918` for `88b1e13` completed with success on Python 3.11, Python 3.12, investigator evidence, and product browser. Do not state CI remains in progress. Preserve the known historical edit-during-test source-hash failure in provenance; its isolated stable-source rerun passed. Clean-worktree release verification is useful but not a reason to rewrite the physics code.
2. **G5 commitment format exists and is committed to historical artifacts.** `src/realign/validation/vault.py` binds challenge ID, domain, heldout dataset hash, evaluation protocol, canonical geometry and a 32-byte secret nonce. Existing synthetic G5 post-reveal artifacts MUST still verify. Do not replace the hash encoding in-place with the new proposed length-prefixed scheme. If a security argument justifies changing it, introduce a clearly versioned v2 protocol used **only for new challenges**, with test vectors and backward-compatible v1 verification. A changed hash must never rewrite a spent evaluation or historical verdict.
3. **A broad forbidden-key scan would break legitimate peg hypothesis tools.** `src/realign/tools/registry.py` and `src/realign/contracts/investigation.py` intentionally use `PEG_ONE_SIDE`, `peg` parameters and model-family fields. Do NOT ban generic `peg`, `fault` or `registered_threshold` everywhere. Instead reject precise **sealed-context/private-data fields** (`nonce_hex`, `hidden_geometry`, `ground_truth`, `heldout_observations`, private truth files, etc.) using allowlisted typed schemas and reference/permission checks; verify no sealed ground truth is accessible to tool outputs.
4. **Variable-frame-rate video is not intrinsically invalid.** `src/realign/perception/video.py` preserves original presentation timestamps. Accept monotonic valid timestamps even when spacing varies; reject missing/duplicate/non-monotonic or physically unverified timing only as appropriate. Do not silently resample or assume constant frame rate. For external slow-motion clips keep physical capture-time scaling UNVERIFIED.
5. **The product is deliberately read-only.** `src/realign/product/server.py` rejects POST/PUT/DELETE, and `/review` currently exports local JSON for offline admission. Do not silently add a writable web endpoint to store reviewer files, start paid API requests or access sealed data. A browser-local annotation lock and JSON download followed by explicit CLI import can meet the requirement; server-side writes require a new, independently reviewed security case and explicit authorization.
6. **Evidence-header scope needs compatibility.** `/api/catalog`, `/api/status` and `/api/closure` aggregate multiple source domains, while `/api/runs/<id>` is run-specific. Add a versioned envelope or bounded source-set type for aggregate endpoints rather than falsely tagging all endpoints `SYNTHETIC` or breaking established consumers. Verify all five views, legacy evidence replay and browser tests remain functional.
7. **Do not convert a post-mortem into a second heldout evaluation.** The randomized synthetic G5 verdict remains FAIL at peg-position error 14.477706 mm vs registered 10 mm despite prediction RMSE 0.7519408442 px. Analyze the already revealed report, model, exploration data, and optionally **new independent synthetic simulations**. No refitting, threshold tuning or newly scored candidate model on the consumed heldout. If the original stored heldout is displayed post-reveal, explicitly label it a historical descriptive visualization, not a new evaluation.
8. **Do not promise a credible interval without a defined probability model.** If only local sensitivity/profile methods are available, call it a `profile uncertainty range` or `identifiability diagnostic`; do not use Bayesian `credible interval` terminology without a posterior and assumptions. Lack of numerical identifiability must block precise geometry claims.
9. **Evidence Ladder is a communication layer, not a single global scientific certification.** Synthetic Muse success, actual external SAM tracking, and synthetic G5 workflow verification are separate capability branches. Display *per-domain achieved evidence and the highest legitimate overall claim ceiling*; the randomized failed G5 case and deterministic parity must stay visible. Do not treat `C2-G5` as a scientific pass because the fixed positive control passed.
10. **Use existing modules first.** `src/realign/physical/ingestion.py`, `session.py`, `orchestration.py`, `src/realign/perception/manual_review.py`, `src/realign/validation/vault.py`, `src/realign/product/closure.py`, and `scripts/review_external.py` already implement much of the proposed functionality. Extend with narrowly scoped patches; avoid duplicate state machines, validators, or reviewers.
11. **No unsupported API-cost claim.** The real Meta receipts demonstrate successful operations. Publish billed spend only if authoritative billing/usage records support it; otherwise report request/token counts with cost `UNVERIFIED`.
12. **No final-compliance claim without user action.** The owner must personally verify acceptance, Indie track, portal fields, accepted rules, video and external-footage rights. Keep CC BY-SA media and derivative works outside the code's MIT scope. Do not claim an organizer's rights are settled by attribution alone.

## Revised priority and implementation sequence

### P0-A — Lock and package a stable release
- Create `release/vfinal` from verified Task 06; check status, `.env`, tracked history, missing source, immutable receipts, and official CI.
- Run targeted tests for changed modules, one full clean-worktree suite before release, and browser checks. Do not rerun heavy calibration at every stage.
- Preserve the authentic live Muse run, failed first attempt, actual SAM receipts, positive-control G5 PASS and randomized G5 FAIL.

### P0-B — Make the product judge-ready
- One coherent README with two-minute replay quickstart and honest capability/evidence table.
- Improve provenance labels and a safe per-domain evidence summary without disrupting existing APIs. Expose the old synthetic pass, randomized fail and agent/deterministic parity.
- Keep live API execution explicit in CLI; never silently trigger paid calls from the UI. Keep `/review` read-only with local file export/import.
- Add UI checks for all five views and external video playback/overlay, including missing-media states.
- Prepare a short continuous owner screen recording; an archived screenshot montage is a labelled fallback, not proof of live interaction.

### P0-C — Close only evidence gaps that can be closed from existing data
- Expand independent review frame selection into 0–4s and include both accepted and rejected SAM tracking frames; preserve original PTS and hashes.
- Do not use supplied AI-generated labels as independent ground truth. Provide a simple offline route for genuine human annotations and show accuracy `NOT_VALIDATED` until they arrive.
- Ensure real-phone flow stays `BLOCKED_INPUTS` until actual recording, calibrated pivot/scale, verified capture timing, release bracket, and independent review exist.
- Preserve existing G5 v1 and tests; add narrow adversarial cases only if missing.

### P1 — Optional research improvements, only after P0 is stable
- Descriptive exploration of G5 geometry identifiability without reusing the spent heldout for re-evaluation.
- More sophisticated calibration, compositional repairs, elastic tether and new physical domains are **not** release blockers.

## Acceptance criteria

1. Verified CI success and a documented local clean-worktree release check.
2. Five product views plus `/review` remain functional, honest and readable in a continuous screen recording.
3. Real Muse and SAM receipts are preserved and labelled with correct domains; no new API expenditure without explicit authorization.
4. Both Task 06 G5 verdicts remain byte-for-byte authentic and reproduce under their **original** protocol.
5. Tool and agent cannot access sealed truth; no general word blacklist that rejects legitimate peg models.
6. No fabricated human/phone/physical result. Unknown physical G2/G5 stays `BLOCKED_INPUTS`.
7. README, scientific claims, media notices, video, participant checklist and portal submission status are separated into software, science and competition gates.
8. Each stage reports actual modified files, tests, failures, surviving limitations and final Git SHA.

## Owner work that code cannot replace

- Independently annotate source frames (including early rejections) without seeing SAM or AI predictions.
- If a controlled rig exists, record stationary/free/peg trials with physical scale, measured geometry and genuine heldouts. Without these, no real-world structural-repair claim.
- Record a continuous, narrated product demo; confirm third-party media permissions and complete the participant submission portal.

**Stop rule:** Stop a *specific unsafe operation* (e.g. consuming a heldout twice, changing a registered threshold, releasing a nonce early), not all release work. Escalate blockers while continuing unaffected P0 tasks. Never force a historical G5 outcome to PASS.
