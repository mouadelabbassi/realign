# Checkpoint A: stable release baseline

Baseline `88b1e13a756c369e4131769ce734ab4dff843ea4` (`6`); branch
`release/vfinal`. Initial working tree was clean. The five supplied contracts
are retained in `docs/`; the independent review addendum overrides their
conflicting proposals. No existing scientific source or evidence is replaced.

- GitHub Actions [41533276918](https://github.com/mouadelabbassi/realign/actions/runs/41533276918)
  was fetched through the authenticated GitHub connector: Python 3.11, Python
  3.12, investigator evidence and product browser all completed **success**.
  Earlier documents' pending CI is historical, not current.
- `python -m pip install -e ".[dev,perception]"`: succeeded.
- `python -m pytest -q tests/test_physics.py tests/test_independent_validation.py tests/test_task06_product.py --tb=short --junitxml=data/processed/vfinal_initial_tests.xml`:
  **40 passed, 1 Linux-only skip**, JUnit elapsed 8.603 s.
- `python scripts/scan_release_secrets.py --output data/processed/vfinal_secret_scan.json`:
  **PASS**, 449 reachable historical blobs, zero credential-pattern findings.
  Pattern scanning is not proof against every possible secret encoding. Local
  `.env` remains ignored; no key is read or printed.
- `scripts/release_check.py` creates a detached clean worktree at an explicit
  revision, uses a separate venv and outputs logs outside that worktree. It runs
  full offline tests, G1, baseline/G2/B3 verifiers, historical G5 reproduction,
  browsers and JS syntax checks. No Meta requests are enabled. A pinned-baseline
  run is started under `data/processed/release/baseline`; final results will be
  recorded separately, without altering this checkpoint's execution history.

The historical edit-during-test source-hash failure remains in Task 06 evidence;
its stable-source rerun passed. Clean release checks remove that race by design.
No registered G5 thresholds, original commits, verdicts, holdouts or live receipts
are modified. No paid API operations are authorized by this release task.

Owner-only blockers persist: independent human labels, controlled physical data,
participant/portal sign-off, continuous narrated demo and third-party media rights.
