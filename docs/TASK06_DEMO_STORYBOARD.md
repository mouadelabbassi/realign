# REALIGN: evidence closure demo storyboard

Start with `python scripts/run_realign.py` and open http://127.0.0.1:8765.
Use recorded evidence for the presentation; viewing does not make API calls or
refit models. Keep the source, policy and evidence-status labels visible.
This is a compact presentation guide, not an assertion that pending physical
checks have passed. Final recording length must follow the owner's actual
submission form; no event video-duration requirement has been assumed.

| Time | View / action | Narration and evidence |
|---|---|---|
| 0:00-0:25 | Reality versus Simulation; SYNTHETIC, deterministic two-round run | "REALIGN tests whether an executable model explains observations. These are synthetic measurements with known assumed localization noise." Scrub time, compare B0/B1/B3 and residuals. |
| 0:25-0:55 | Investigation; switch to live Muse attempt 02 | "This trace came from actual Muse Spark 1.3. Muse formed hypotheses and requested these scientific tools; deterministic code computed the numbers." Show actual calls and evidence references. |
| 0:55-1:20 | Experiment Loop; Round 1 to Round 2 | "Limited-angle data were ambiguous. Muse selected an approved release experiment and received two new synthetic exploration trials." Show action, score, receipt and updated comparison. This is synthetic execution, not an actuator. |
| 1:20-1:45 | Model Decision and Evidence | "The accepted predefined peg model was frozen before independent development scoring." Show the freeze reference and recorded 0.819611 px RMS. The deterministic arm obtained the same error; claim orchestration, not superiority or unique mechanism identification. |
| 1:45-2:15 | REAL_EXTERNAL | "Actual SAM 3.1 tracked MikeRun's licensed third-party clip. It is not our phone experiment." Show source/credit, masks/centers, original PTS and 550/600 accepted centers. Tracking acceptance is not localization accuracy. |
| 2:15-2:40 | Independent review status | If references exist, show reviewer/frame/hash provenance, RMSE, horizontal/vertical bias, median/p95 error and interval/event strata from the actual report. Otherwise say: "Accuracy remains NOT_VALIDATED; independent centers have not been provided." Never annotate from SAM centers or turn missing strata into zero error. |
| 2:40-3:05 | Pending physical action / REAL_PHONE | "A requested physical experiment becomes a pending action. The system only admits a recording after it is supplied and validated." Show actual pending requirements or the truthful missing-data state. No synthetic trajectory may stand in for that recording. |
| 3:05-3:30 | Evidence; freeze and independent validation | Show an actual validation record if available, including source domain, frozen hash, commitment chronology, held-out score and reveal status. Label a synthetic blind challenge SYNTHETIC. If physical data are absent, show NOT_PASSED/INCONCLUSIVE and explain the blocker. |

The five product views remain the presentation structure. Review, pending-action
and validation panels extend their evidence, without adding a new frontend
framework or another investigator. Use only panels and records present in the
actual build; do not edit a success screen into the final video.

## What the judge should be able to inspect

- The actual live Muse trace and numerical evidence, with the unsuccessful first
  attempt retained. Nine completed requests in the successful run are protocol
  evidence, not a broad reliability guarantee.
- Exploration versus post-freeze development/held-out boundaries; a frozen model
  content reference and independent validation result, with no tuning afterward
  against the same holdout.
- Independent manual annotation status. Missing references remain NOT_VALIDATED;
  missing event-stratum samples remain unavailable.
- A physical experiment receipt only after a real validated recording arrives.
  Missing scale, pivot, capture timing, release timing or uncertainty are explicit
  blockers. Synthetic calibration cannot authorize a real structural repair.
- A blind commitment created before investigation. A later reveal verifies that
  commitment; it does not itself prove blinding or real-world discovery. Never
  expose the nonce or hidden measurements before reveal.
- Accurate attribution and remaining submission obligations in
  [META_COMPLIANCE.md](META_COMPLIANCE.md). The external clip keeps its CC BY-SA
  credit; controlled phone G2 and physical G5 remain pending independent data.

For reproducible startup and the retained live evidence, see
[TASK05_IMPLEMENTATION.md](TASK05_IMPLEMENTATION.md). Use the completed Task 06
implementation/readiness command list when recording its new validation panels;
do not infer successful execution from this storyboard.
