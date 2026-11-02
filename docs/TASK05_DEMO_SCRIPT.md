# REALIGN Task 05 demonstration

Run `python scripts/run_realign.py` from the repository root. Open
http://127.0.0.1:8765. The interface plays recorded, verified artifacts; viewing
does not make API requests or rerun fits. Use `python scripts/verify_task05.py`
before presenting to recheck the portable evidence.

## Three-minute walkthrough

1. **Reality versus Simulation.** Select SYNTHETIC and the deterministic
   two-round pendulum investigation. Say: "These observations are reproducible
   synthetic measurements. We begin with two limited-angle trials. The nominal
   free model and fitted alternatives can be compared at the original times."
   Scrub the trajectory, switch models and show residuals and localization
   uncertainty. Keep the source label visible.

2. **Investigation.** Show the competing recorded hypotheses and actual
   numerical tool results. Say: "The investigator cannot invent a fit. These
   deterministic tools return bounded fits, prediction comparisons and
   identifiability diagnostics using exploration observations only. Initial
   evidence does not justify a structural conclusion."

3. **Experiment Loop.** Show the requested larger-angle release and its score.
   Say: "The system requests one approved experiment action, which provides two
   new synthetic trajectories. The receipt records what arrived." Switch to
   Round 2 and show the updated hypotheses/model comparison. This is simulated
   experiment execution, not a physical actuator.

4. **Model Decision and Evidence.** Show the selected predefined peg model,
   accepted scope, frozen model reference and post-freeze development result.
   Say: "The model is frozen before these independent development trajectories
   are created and scored. The selected model predicts them at 0.819611 px RMS.
   This is predictive selection within a fixed model family, not unique causal
   identification or open-ended equation discovery." The baseline chart uses
   comparable trajectory errors; geometric circle error is not on that axis.

5. **Actual live Muse.** Select the live investigation, attempt 02. Keep
   SYNTHETIC visible. Say: "This reasoning trace came from actual Muse Spark 1.3
   requests: nine successful requests, genuine scientific tool calls, two rounds
   and one received experiment. Its initial data and numerical budgets match
   the deterministic policy. Both reach the same development error; we do not
   claim superiority." Briefly select attempt 01 to show the retained protocol
   failure and honest abstention, then return to attempt 02. Say: "One of these
   two attempts completed the protocol; this is not a reliability estimate."

6. **Actual SAM, separate source.** Select REAL_EXTERNAL. Play or scrub the
   third-party blocked-pendulum video and its tracked-center overlay. Say:
   "This is MikeRun's CC BY-SA 4.0 footage, not our phone experiment. Actual
   SAM 3.1 returned 600 masks; 550 centers passed tracking QA and fifty were
   rejected by shape checks. Original playback timestamps are preserved.
   Human review, capture-time verification and physical calibration are still
   pending, so we make no dynamics or discovery claim from this clip."

7. **Honest pending work.** Select REAL_PHONE to show the missing controlled
   recordings. If time permits, select the synthetic measurement-quality case
   and its decision: "Measurement correction required means exactly that; a
   reference check has not applied and verified a correction."

The product joins evidence presentation, not incompatible success claims. The
live synthetic investigation and real external SAM tracking are independently
demonstrated. Full physical G2 acceptance awaits the recordings and measurements
in [REAL_DATA_COLLECTION_PROTOCOL.md](REAL_DATA_COLLECTION_PROTOCOL.md).

## Offline fallback and troubleshooting

- The deterministic demonstration and the retained live trace replay without
  API credentials. Do not replace a failed live execution with mock results
  while leaving a LIVE_MUSE label visible.
- If the local MP4 is absent, external tracking receipts remain available but
  video playback cannot be shown. Restore the approved media from its documented
  source and verify its processed hash; do not relabel another clip.
- If an evidence file is missing, malformed or changed, the interface refuses
  to display it as verified. Run `python scripts/verify_task05.py` to diagnose
  the local artifact set. This command uses the existing WSL runtime on Windows.
- Starting a new live run requires explicit CLI flags and account access;
  neither opening a view nor replaying a trace spends API quota.
- Reproduce the optional browser checks with `python -m pip install -e ".[ui-test]"`,
  `python -m playwright install chromium`, then set `REALIGN_BROWSER_TESTS=1`
  in the launch environment and run
  `python -m pytest -q tests/test_product_browser.py`. The recorded local check
  passed six browser tests; no credentials or external requests are required.
