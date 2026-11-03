# Installing the Codex Handoff into Your Existing REALIGN Repository

1. Open your **existing** `realign_poc0` project folder in VS Code. Do not replace the physics source or tests with the contents of this handoff.
2. Extract this ZIP **into that existing project root**. It adds `AGENTS.md`, new files under `docs/`, and `tasks/CODEX_TASK_01_POC0_BASELINES.md`.
3. Before working, make a git commit of the current working G1 state yourself (after reviewing it). Commit/push should always be an explicit user action; Codex should not rewrite history.
4. Open the **Codex** extension or CLI inside this workspace.
5. Paste this exact first task: `Read AGENTS.md and tasks/CODEX_TASK_01_POC0_BASELINES.md, inspect the live repo, then implement the authorized task end-to-end. Run tests and produce the real artifacts. Do not implement later phases or claim unrun Meta API tests.`
6. When Codex finishes, inspect its diff, the test results, and `artifacts/POC0_BASELINES.md`. Then send its implementation summary or GitHub PR to ChatGPT for an independent review.

Local initial commands from the project root:

```sh
python -m pip install -e ".[dev]"
pytest -q
python scripts/verify_g1.py
```

Meta API credentials remain local (`MODEL_API_KEY` environment variable). Never put them into chat, screenshots, source, logs, or git.
