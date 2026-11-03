# vFinal release readiness

Baseline: `88b1e13a756c369e4131769ce734ab4dff843ea4`. Branch: `release/vfinal`.
The independent review addendum governs conflicts with the planning documents.

## Independent verdicts

- SOFTWARE_RELEASE_READY: **PASS**, with the documented remote-CI exception below.
- PHYSICAL_VALIDATION_STATUS: **BLOCKED_INPUTS**. Physical G2/G5 NOT_PASSED;
  independent external accuracy NOT_VALIDATED.
- SUBMISSION_STATUS: **UNVERIFIED / OWNER_ACTION_REQUIRED**. No portal or
  participant sign-off, continuous narrated owner demo or media reuse permission.

This is the completed local release record. Final command results are recorded under
`artifacts/release/`; their source SHA identifies exactly what was tested.

## Preserved baseline and checkpoints

GitHub [CI 41533276918](https://github.com/mouadelabbassi/realign/actions/runs/41533276918)
completed successfully in all four jobs at the baseline. Earlier documents'
pending CI is historical. Release-branch CI is not inferred from that run.

- A: `14493ce` locks contracts and adds clean-worktree verification.
- B: `d0ad45c` adds compatible evidence headers, per-domain claims and judge views.
- C: `3f5ecd5` separates public reveal verification, guards precise private fields,
  and adds a ledger frontier without replacing v1 commitments.
- D: `639c48b` extends independent review to forty clean frames and strengthens
  media admission, calibration grades and the existing physical action lifecycle.

Checkpoint tests: initial 40 passed/1 platform skip; B 92 passed and 11 browser
tests; C 39 passed/1 platform skip; D 60 passed/1 platform skip and 12 browser
tests. A Windows CRLF/CSP mismatch found in the new review page was corrected
and its lock/export test passed. It did not affect physics or real measurements.
The final source adds missing-media and packaging checks beyond those counts.

The first release-runner development attempt lacked isolated-venv dependencies;
no scientific check succeeded in that attempt. The corrected runner installs
dependencies constrained to the verified runtime versions. The clean baseline
full suite subsequently passed **331 tests, 10 skips**. Logs preserve both
attempts. The final vFinal run is separate and mandatory.

## Scope and remaining limits

The overall claim ceiling is C3a, with separate synthetic science/Muse/G5 and
REAL_EXTERNAL tracking branches. Fixed synthetic G5 PASS and randomized FAIL
are preserved with original commitments, thresholds, heldouts and verdicts.
No model was fitted or newly evaluated against a spent holdout. The optional
research ensemble/profile study was not run; archived local sensitivity is
descriptive and no credible interval or precise geometry claim is supplied.

Read-only APIs carry compatible versioned evidence headers. Aggregate endpoints
declare bounded source sets; old payload fields remain. No endpoint starts model
execution or writes annotations. The expanded review lock is browser-local and
checks file integrity, not authorship. AI-labelled files cannot validate accuracy.
Rejected SAM centers have no invented localization errors. Two-reviewer
disagreement is available through the existing review CLI; real references remain
missing. Physical release variation remains distinct from tracking uncertainty.

Valid VFR is accepted through original monotonic PTS; missing/duplicate/reversed
PTS, invalid containers, duplicate recording hashes and low coverage are typed
rejections. Calibration below SUFFICIENT permits pixel units only. The external
slow-motion clip remains PTS_ONLY/UNKNOWN scale and cannot enter physical fitting.
Physical requests have admission history and explicit optional expiry; no real
recording or actuator is simulated into that path. Real structural acceptance
still refuses the synthetic-only null gate; real-data decisions may abstain.

The public verifier imports no custodian implementation. Actual isolated workers
and typed tools remain the enforcement boundary. A local ledger/frontier detects
tampering/truncation but is not external notarization or defense against a host
administrator replacing the whole vault. Historical v1 ledgers remain readable;
new writes add a frontier. A crash between ledger and frontier writes fails closed.

## Reproduce

```powershell
python scripts/run_realign.py --port 8766 --no-browser
python scripts/export_evidence.py --output data/processed/REALIGN_evidence.zip
python scripts/export_evidence.py --verify data/processed/REALIGN_evidence.zip
python scripts/release_check.py --revision HEAD --output-dir data/processed/release/final
```

Replay is standalone and needs no key/WSL. Numerical checks on Windows use the
existing WSL runtime. The release script creates a separate clean checkout,
installs constrained dependencies and captures logs outside it. Browser setup
requires Playwright Chromium; on this Ubuntu 26.04 runtime Playwright 1.58 used
its explicitly labelled Ubuntu 24.04 fallback build. Native Windows Chrome
browser checks also ran. Billed spend remains UNVERIFIED; vFinal Meta calls: 0.

One-shot scores are reproduced only from already released frozen models and
observations, preserving the original verdicts. This is public post-reveal
reproduction, not another custodian evaluation. Raw frozen evidence remains
unchanged. JSON evidence uses LF transport hashes to handle existing Windows
CRLF checkouts without altering numbers; hash-bound review HTML is checkout-stable.

The owner must supply genuine labels, controlled recordings/calibration/timing,
an independent custodian and a narrated demo, and complete the
[submission checklist](SUBMISSION_CHECKLIST.md). Software cannot supply those.


## Completed stable clean-checkout validation

Tested source: `e9a6f0818aa061d96b6e07a366dc5c866ba9e7be`. The final delivery commit contains validation metadata only; `src/` and `scripts/` remain identical.

The complete checker exited **0** with every stage PASS. Full suite: **370 passed, 15 skipped**. Linux browser: **12 passed, 1 skipped**. Native browser: **13 passed** with the approved local external video available. Native targeted tests: **156 passed, 7 skipped**. JUnit durations and exact commands are retained in `artifacts/release/validation/` and `RELEASE_STATUS.json`.

The first final run passed all 370 scientific/unit/integration checks and numerical verifiers, but its browser header-rejection assertion inspected the loading shell after only five seconds. A test-only synchronization commit waits for completed bootstrap before the same exact error assertion. The clean synchronization rerun and full stable rerun pass. Original failure records are retained in `validation_attempts.json`. No scientific threshold or assertion was relaxed.

G1, B0/B1/B2, offline G2 and B3 verifiers all passed; both historical G5 scores reproduced exactly without a new model fit or custodian evaluation. Fresh derivative reports are under `artifacts/release/reproduced/`; original evidence is unchanged. The original baseline runner additionally lacked a system Node executable; its supplemental bundled-Node check passed. The stable runner resolves that dependency and exits 0.

Remote-CI exception: baseline CI is verified green; new release-branch CI is **UNVERIFIED**, because no push was authorized or performed. This is not described as a green CI run for the new commit. The local software gate passes with that explicit exception. Physical validation remains **BLOCKED_INPUTS**, submission remains **UNVERIFIED**, and billed spend remains **UNVERIFIED**.

The verified running app is http://127.0.0.1:8767 (launch with `python scripts/run_realign.py --port 8767 --no-browser`); `/review` serves the forty-frame independent queue. Port 8766 is the configurable README example. A busy Windows port now fails visibly rather than sharing a stale listener.
