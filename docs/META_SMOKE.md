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
