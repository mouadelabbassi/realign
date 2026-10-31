# Implementation provenance

- Creation date: 2026-10-31 (hackathon event window as supplied by project owner).
- This starter implementation was generated collaboratively with ChatGPT, based on the REALIGN Build Spec v1 document provided by the project owner.
- Original code in this starter repository implements only the G1 scientific kernel and local synthetic verification.
- The owner should check official competition rules before making claims about authorship, licensing, and required disclosure.
- Generated G1 verification uses a deterministic NumPy seed, `20261031`.
- Task 01 adds synthetic observations and classical B0/B1/B2 baselines, with
  protocol seed `20261031`, per-trial seeds, observation fingerprints, source
  SHA-256 and dependency versions recorded in `artifacts/poc0_baselines.json`.
- Synthetic ground truth is generated independently of fitters and consulted only
  after fitting for the explicitly labeled evaluation fields. Development trials
  are disjoint whole synthetic trials; these are not the future sealed trials.
- No Meta API request or real hardware experiment was performed in this environment.
- Task 02 adds an offline-tested physical observation pipeline, official SAM
  parser integration and separately executable live commands. Synthetic rendered
  MP4s and simulated API events remain labeled fixtures. They are not SAM output,
  human annotations or physical measurements. G2 remains pending real evidence.
- Original G1 source and numerical baseline algorithms are preserved; video
  records use separate validated contracts and calibrated fitting dispatch.
