# Authentic Meta evidence index

**Existing Task 05 executions only. New vFinal Meta calls: 0. Billed spend: UNVERIFIED.**

| Execution | Completed operations | Failed HTTP operations | Actual outcome |
|---|---:|---:|---|
| Capability probe | 4 | 0 | Actual listing, structured output and tool round trip |
| Muse attempt 1 | 3 | 0 | PARTIAL; ABSTAIN |
| Muse attempt 2 | 9 | 0 | PASS; REPAIR_STRUCTURE |
| SAM external | 2 | 0 | 0 mask records; response `resp_6ae7df9a973246ddb0c54eb1` |
| SAM external_yellow_disc | 2 | 0 | 600 mask records; response `resp_6ae7e054bd6a69852d614362` |

Task 05 totals: 20 completed operations, zero HTTP failures. Completion is distinct from scientific success: the first Muse protocol rejection and the initial zero-mask SAM match remain retained.

Requested models: `muse-spark-1.3` and `sam-3.1`. SAM uses the official `meta-sam-parser` 0.1.0. Muse operations are reasoning on SYNTHETIC observations; SAM inputs are REAL_EXTERNAL MikeRun CC BY-SA 4.0 footage.

Muse provider response IDs were not retained in the sanitized receipts; response content SHA-256 values are retained instead. No IDs are invented. The accepted trace reports 118269 input tokens and 7173 output tokens; attempt 01 reports 16896 and 2377. No invoice or authoritative billed-usage record is supplied, so no monetary value is estimated.

## Preserved source records

- [Capability probe](../task05/meta_capability/meta_smoke.json)
- [Live verification and every receipt digest](../task05/live_meta_verification.json)
- [Attempt 01](../task05/live_investigation_attempt_01.json)
- [Attempt 02](../task05/live_investigation_attempt_02.json)
- [Initial SAM empty match](../task05/external/external_verification.json)
- [SAM yellow-disc tracking](../task05/external_yellow_disc/external_verification.json)
- [Matched deterministic comparison](../task05/matched_live_comparison.json)

No key, raw credential, hidden measurement or pre-reveal nonce is included. These retained operations do not establish physical validation, account eligibility, organizer permission or broad model reliability.
