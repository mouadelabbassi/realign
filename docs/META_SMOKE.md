# Meta API verification checklist

Official references (verified 2026-10-31):
- Muse tool calling: https://dev.meta.ai/docs/cookbook/tool-function-calling
- SAM API basics: https://dev.meta.ai/docs/cookbook/sam-api-basics

The official cookbook confirms `muse-spark-1.3` on Chat Completions, with
`OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"])`.
It also documents hosted `sam-3.1` for uploaded MP4 and a streamed parser
(`meta_sam_parser`).

Run the implemented Muse connectivity smoke test from the repository root:

```bash
export MODEL_API_KEY='YOUR_PRIVATE_KEY'     # or set with your OS secret mechanism
python scripts/smoke_meta.py --standard-tier-confirmed
```

**DO NOT** commit the secret, screenshots of it, request headers or full logs
that contain private data.

Task 03 extends this script to check model availability, closed-schema
structured output and a genuine model-emitted numerical tool call followed by
a matching tool-result message and verified final answer. It uses the documented
Chat Completions contract, tool_choice=auto and bounded low-reasoning token
budgets. A direct answer without a tool call fails the tool probe. Raw replies,
request bodies, credentials and raw server errors are not saved. API response
validation failures are distinct from transport call failures.

No Meta API was invoked during these implementation tasks. Missing local key
or Standard-tier confirmation produces a NOT_RUN report and exit 2, with zero
successful/failed actual calls. Mock tests are separate fixtures, not API evidence.

## Task 02 SAM integration

The adapter now uses the official meta-sam-parser 0.1.0 and documented MP4 Files
upload / Responses stream. Offline protocol fixtures are explicitly simulated;
they are not evidence of an API call. The fixed concept is "the pendulum bob".

    python -m pip install -e ".[dev,perception]"
    python scripts/smoke_sam.py path/to/actual.mp4 --standard-tier-confirmed

This command records upload/segmentation attempt counts, sanitized failures,
response/request references and quality. Missing key/media produces NOT_RUN and
exit 2. It never silently falls back to another tracker. Actual requests require
locally configured MODEL_API_KEY and Standard-tier confirmation. No key is
included in tests, manifests or GitHub Actions.

Task 02 verification in this environment: actual successful API calls 0; actual
failed API calls 0; actual SAM/real-phone checks NOT RUN. See
artifacts/sam_api_verification.json and artifacts/G2_READINESS.md.

## Task 03 external media and live verification status

    python scripts/prepare_external_video.py --download
    python scripts/smoke_sam.py data/raw/external/blocked-pendulum.mp4 --external-source artifacts/external_source_verified.json --standard-tier-confirmed

The source manifest preserves REAL_EXTERNAL, creator/license URLs, original and
derived SHA-256, modification history and whether physical capture time is
verified. The example is MikeRun's CC BY-SA 4.0 physical blocked pendulum;
slow-motion playback prevents dynamic interpretation without an independently
verified time scale. It is never relabeled REAL_PHONE. The original and derivative
are stored only in ignored data/raw/external. Encoder-dependent bytes are recorded
in the generated verified manifest. See TASK03_IMPLEMENTATION.md for attribution.

Observed Task 03 live status: Muse NOT_RUN and SAM not_run, both with zero actual
successful and zero actual failed calls because MODEL_API_KEY is absent. External
download/probe/decode evidence is separate from SAM evidence. Official API versus
observed live behavior is NOT_ASSESSED. The initial external-media HTTP 429 is a
public file-download failure, not a Meta API call.

Official references rechecked 2026-11-01:

- https://dev.meta.ai/docs/cookbook/structured-output
- https://dev.meta.ai/docs/cookbook/tool-function-calling
- https://dev.meta.ai/docs/cookbook/sam-api-basics
- https://dev.meta.ai/docs/protocols/chat-completions
