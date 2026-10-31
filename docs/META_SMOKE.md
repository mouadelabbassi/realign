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
python scripts/smoke_meta.py
```

**DO NOT** commit the secret, screenshots of it, request headers or full logs
that contain private data.

The script reports Muse connectivity only. This is not a substitute for a real
SAM video smoke test. For video, follow Meta's official cookbook
`python/02_upload_and_segment_video.py` to preserve streamed parsing and
validate masks, then integrate via a dedicated adapter in POC-0 G2.

No Meta API was invoked in creation of this starter repository. The API smoke
report will be generated only when the user runs it with an authorized key.

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
