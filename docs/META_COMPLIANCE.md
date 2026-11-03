# Meta event and evidence compliance record

Checked against public primary sources on **2026-11-02**. This records what was
verified and what the owner still has to establish. **Overall submission status:
UNRESOLVED.** Successful SDK requests do not establish participant eligibility,
submission rights, account terms or acceptance by the organizers.

## Applicable event and public rules

The identified event is the **Meta Global AI Developer Hackathon**, linked by
Meta to Cerebral Valley. Meta's public page lists the October 26-November 4,
2026 event, a November 4 submission deadline of 9:00 PM ET, two tracks and the
Muse Spark/SAM 3.1 tooling. It reserves date changes. Recheck the actual accepted
participant notice and portal before submission. [Meta event page](https://dev.meta.ai/events/global-hackathon)

The organizer's public waiver contains **Hackathon Terms & Conditions
(Official Rules) and Event Waiver**, dated October 25, 2026. The public HTML
includes the rules document even though the text-only web reader returned a
nearly blank waiver page. Inspection used an unauthenticated public HTTP fetch,
not account access. [Official rules and waiver](https://cerebralvalley.ai/e/meta-ai-developer-hackathon/waiver)

| Public-rule item verified | REALIGN status |
|---|---|
| Each participant needs acceptance, must be 18+ and legally adult, and must satisfy location, sanctions and affiliation restrictions. | UNRESOLVED: personal facts/acceptance not supplied. |
| One track per participant/project; Indie teams have up to four members. Teams appoint an authorized representative and identify members. | UNRESOLVED: owner confirms roster, track and authority. |
| Submit through the Cerebral Valley project portal. Judging weights: impact 30%, Meta tooling 25%, technical execution 20%, demo 25%. | Working product/evidence available; final form and submission unverified. |
| Submission requires originality, ownership/rights warranties and grants organizers broad reuse rights. Open-source components require license compliance. | Repository disclosure exists; third-party media compatibility needs resolution. |
| Bonus categories remain organizer-discretionary. | No guaranteed agentic bonus or prize eligibility claimed. |

The public rules also contain releases and publicity/recording terms; the owner
must personally review and accept the complete contract. They are not replaced
by this engineering record. [Official rules](https://cerebralvalley.ai/e/meta-ai-developer-hackathon/waiver)

For change detection, the public rules' structured document was retrieved at
2026-11-02T16:30:29Z. SHA-256 of its canonical JSON was
`6480915e2c8f941a16cd5684cda98b1113e3a58fa4bd2154c974e452dfae5c6a`
(30,422 UTF-8 bytes; sorted object keys, compact separators, unescaped Unicode).
This is a content fingerprint of that public document, not an organizer
signature or proof of the participant's accepted version.

The public pages do not settle the owner's accepted-participant amendments,
final submission fields, required video duration, repository visibility,
pre-existing-code declarations or AI-assistance disclosure requirements.
Those items remain UNRESOLVED. Build Spec A.9's secondary summaries and tentative
claims are historical design context; this record uses the primary sources.

## API terms and actual integration evidence

| Concern | Verified source / project treatment |
|---|---|
| Hosted API models | Official docs identify `muse-spark-1.3` and `sam-3.1`. Their use does not imply an open-weight license. [Models](https://dev.meta.ai/docs/models) |
| Standard versus Contributor | Pay-as-you-go model IDs select the documented mode. Coding-harness subscriptions instead depend on account settings and default to Contributor. The owner's actual account/subscription authorization remains UNRESOLVED; the local confirmation flag is not an account audit. [Model-designation policy](https://dev.meta.ai/legal/geographic-use-policy), [API terms](https://dev.meta.ai/legal/terms-of-service) |
| Content handling | Standard content is not used to train Meta models; this does not mean zero retention or confidentiality against every processing purpose. Use the full applicable terms when deciding what can be uploaded. [Models](https://dev.meta.ai/docs/models), [API terms](https://dev.meta.ai/legal/terms-of-service) |
| Geography | API geography and event eligibility are separate. Access/deployment must satisfy the API policy; technical circumvention is prohibited. No conclusion about the owner's location follows from a successful request. [Geographic-use policy](https://dev.meta.ai/legal/geographic-use-policy) |
| Rights and credentials | The API terms require necessary input/data rights and confidential keys. The app reads a local key into process environment, never publishes it, and excludes it from isolated numerical workers. [API terms, sections 3-4](https://dev.meta.ai/legal/terms-of-service) |

The Task 05 receipts demonstrate actual Muse structured outputs, scientific tool
calls and a two-round investigation over **synthetic** observations. SAM receipts
demonstrate actual segmentation of **REAL_EXTERNAL** footage. The first Muse
protocol rejection and initial zero-mask SAM match remain preserved. One
successful full investigation out of two attempts is not a reliability study.
[Live receipts](../artifacts/task05/live_meta_verification.json),
[SAM receipt and tracking](../artifacts/task05/external_yellow_disc/external_verification.json)

The official SAM recipe specifies MP4 upload, streamed responses, official parser
use and a short visual concept; a completed empty match is valid. The official
Muse tool recipe requires the assistant tool-call message plus matching tool
results. These are the integrated paths. No mismatch with those wire contracts
was demonstrated; REALIGN's stricter local tool-batch bound is application
policy. [SAM workflow](https://dev.meta.ai/docs/cookbook/sam-api-basics),
[tool workflow](https://dev.meta.ai/docs/cookbook/tool-function-calling)

No sealed recording, hidden geometry or reveal nonce belongs in a SAM upload,
Muse context, public demo, prompt or pre-reveal artifact. A successful Model API
request does not waive that scientific isolation requirement.

## Code, AI assistance and third-party media

The repository's [LICENSE](../LICENSE) is MIT for its original software and
documentation. [PROVENANCE.md](PROVENANCE.md) records collaborative AI assistance
and staged implementation history. Preserve that history and identify supplied
specifications, prior work and dependencies accurately. Owner review of any
event-specific declaration remains UNRESOLVED.

The external clip is **Blocked-pendulum-slow-motion.webm**, by **MikeRun**, dated
October 28, 2025, licensed **CC BY-SA 4.0**. It is not REALIGN's recording.
[Creator's file page](https://commons.wikimedia.org/wiki/File:Blocked-pendulum-slow-motion.webm)

CC BY-SA requires credit, the license link, change identification and appropriate
share-alike treatment for adaptations; it does not grant every possible privacy
or publicity right. Keep original and processed hashes, source/creator details
and transcode changes in the supplied provenance. Retain CC BY-SA notices on
derived video/frame/overlay media; the code's MIT notice does not relicense the
clip. [Creative Commons license summary](https://creativecommons.org/licenses/by-sa/4.0/),
[recorded provenance](../artifacts/external_source_verified.json)

**UNRESOLVED: third-party footage in the final competition submission.** The
organizer's ownership warranties and broad reuse grant need to be reconciled
with the retained third-party license. Existing attribution demonstrates source
honesty, not authorization to make every organizer-requested grant. The owner
must confirm the submission's treatment of this media with the organizers or
use independently owned, permission-cleared recordings. Do not claim ownership
of this clip or remove its license to resolve the issue.

## Scientific claims permitted by the current evidence

| Claim | Current boundary |
|---|---|
| Executable synthetic physics, bounded fitting, actual Muse orchestration | Supported by the existing reproducible evidence; narrow model family and tested scope only. |
| Actual external SAM tracking | Supported by real receipts; pixel measurement accuracy is NOT_VALIDATED until independent reviewed references exist. |
| Muse contribution | Actual hypotheses, tool requests, experiment choice and proposed decision; numerical values and final admissibility come from deterministic code. |
| Muse superiority | NOT_DEMONSTRATED: matched deterministic/live final prediction errors were equal in the recorded case. |
| Controlled phone G2 / physical G5 | NOT_PASSED without independent physical recordings, calibration, uncertainty and held-out validation. |
| Blind challenge | Label synthetic and real separately. A synthetic commitment/reveal cannot establish physical blind discovery. |

This source check does not submit the project, accept terms, attest personal
eligibility or resolve participant-specific obligations. Next owner inputs are
the accepted rules/amendments, participant/track confirmation, final portal
checklist and third-party media submission permission. Engineering work can
continue while these remain unresolved.

## vFinal release update

Baseline CI run [41533276918](https://github.com/mouadelabbassi/realign/actions/runs/41533276918)
at `88b1e13` is **PASS in all four jobs**, confirmed through GitHub. It is not
pending. New release-branch tests identify their own revisions separately.

vFinal makes **zero new Meta calls**. Request/token accounting from the authentic
Task 05 receipts is indexed in `artifacts/release/meta_evidence_index.md`; billed
spend remains **UNVERIFIED**. No hosted-model usage is relabelled open weights.
Original external media and derived frames retain CC BY-SA 4.0 outside the MIT
scope, documented in `THIRD_PARTY_NOTICES.md` and `licenses/EXTERNAL_MEDIA.md`.
The scripted Cut A is a labelled offline fallback with no external pixels, not
the owner's continuous narrated submission demo.

Software evidence does not complete participant acceptance, track/roster,
organizer reuse permission, final video or portal upload. Those requirements
remain **UNVERIFIED** or **BLOCKED_INPUTS** in
[SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md). No permission or successful
submission has been invented.
