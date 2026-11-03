# Submission checklist: owner actions remain separate

Status vocabulary: PASS, FAIL, BLOCKED_INPUTS, UNVERIFIED. Software release,
physical validation and competition submission are independent gates. No portal
action, acceptance, organizer permission or owner sign-off is fabricated here.

| Requirement | Status | Evidence / owner action |
|---|---|---|
| Baseline Task 06 CI | PASS | [41533276918](https://github.com/mouadelabbassi/realign/actions/runs/41533276918), all four jobs at `88b1e13` |
| vFinal local source/tests | See release record | [RELEASE_READINESS.md](RELEASE_READINESS.md); tests identify their actual commit |
| Original Meta integrations and failures preserved | PASS | [Meta evidence index](../artifacts/release/meta_evidence_index.md); no new calls |
| Request/token usage | PASS for retained accounting | Recorded operations/tokens; billed currency UNVERIFIED |
| Indie/startup track and roster | UNVERIFIED | Owner confirms accepted participant account, track, representative and members |
| Age, location, affiliation and acceptance | UNVERIFIED | Personal facts and accepted official terms are owner-only |
| Work period, prior work, AI assistance and dependencies | UNVERIFIED | Owner reviews commit history and [PROVENANCE.md](PROVENANCE.md) against accepted rules |
| Public repository and exact release SHA | UNVERIFIED for submission | Local checkpoint commits exist; owner confirms required visibility and submitted revision |
| External media attribution/license scope | PASS | [Third-party notices](../THIRD_PARTY_NOTICES.md); CC BY-SA media excluded from MIT |
| Organizer reuse permission / external footage in submission | UNVERIFIED | Attribution alone does not authorize every organizer grant. Owner obtains confirmation or uses cleared media |
| Scripted fallback Cut A | Software-generated fallback only | `capture_demo.py` uses synthetic/numerical views, no external pixels; no owner narration claimed |
| Continuous narrated owner demo | BLOCKED_INPUTS | Owner records and checks actual portal duration/content constraints |
| Independent human review | BLOCKED_INPUTS | Forty-frame queue includes early failures; no real reference labels supplied |
| Controlled phone measurements and real G5 | BLOCKED_INPUTS | Rig, calibration, timing, reviewed trials and independent custodian required |
| Portal fields, uploads and acknowledgement | UNVERIFIED | Owner completes and retains confirmation |
| Actual final deadline | UNVERIFIED for owner acceptance | Public [Meta page](https://dev.meta.ai/events/global-hackathon) lists November 4, 2026, 9 PM ET, subject to changes; owner checks current portal |
| Open Weights / social or other bonus eligibility | UNVERIFIED; no claim | Hosted API usage alone does not establish an open-weight run or bonus qualification |

Primary sources: [Meta event](https://dev.meta.ai/events/global-hackathon),
[organizer rules/waiver](https://cerebralvalley.ai/e/meta-ai-developer-hackathon/waiver).
The [compliance record](META_COMPLIANCE.md) preserves the source check and its
limits. Organizer amendments and participant-specific portal details have not
been supplied. No automatic submission is performed.
