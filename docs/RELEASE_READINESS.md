# vFinal release readiness

Baseline: `88b1e13a756c369e4131769ce734ab4dff843ea4`. Branch: `release/vfinal`.
The independent review addendum governs conflicts with the planning documents.

## Independent verdicts

- SOFTWARE_RELEASE_READY: **UNVERIFIED until the final clean-checkout run finishes**.
- PHYSICAL_VALIDATION_STATUS: **BLOCKED_INPUTS**. Physical G2/G5 NOT_PASSED;
  independent external accuracy NOT_VALIDATED.
- SUBMISSION_STATUS: **UNVERIFIED / OWNER_ACTION_REQUIRED**. No portal or
  participant sign-off, continuous narrated owner demo or media reuse permission.

This is an in-progress release record. Final command results are recorded under
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
