# Offline SAM protocol fixtures

No fixture in this project was produced by a Meta API request. The generator is
src/realign/synth/video_fixture.py, outside the real perception path.

- Media: deterministic 640x480 H.264 MP4, a white round bob on black, rendered
  from the unchanged G1 simulator. Nominal frames are 25 Hz. A separate VFR case
  uses two actual presentation intervals and checks FFmpeg-decoded frame count.
- Protocol: documented Responses event dictionaries, with a text delta,
  content_part.done and terminal outcome. Only the official meta-sam-parser
  consumes the SAM grammar and decodes rasters.
- Mask: our own 17x17 binary disk, radius 8 pixels and 197 foreground pixels.
  Its committed one-bit payload was generated once using the pinned parser's
  test codec. Production/fixture execution uses public parser APIs, not a
  private encoder. Per-frame source boxes place this known disk in each image.
- Missing data: frames 13 and 37 deliberately have no SAM mask; their original
  video PTS remain present and observations stay invalid.
- Failure cases: malformed mask, missing terminal event, incomplete/failed/
  refused responses, outside-source frame index, ambiguous identity, exhausted
  upload retries and unavailable local key. Mocked HTTP attempts are not counted
  as actual API verification.
- Known rendered centers are explicit synthetic validation/annotation references.
  No synthetic truth object is imported by the real ingestion or fitting path.

Reproduce with python scripts/verify_g2.py. Generated MP4s are under
artifacts/synthetic_fixture_media/ (ignored by Git); the report, JSON and plot
are deliverable evidence. The report source hash and dependency versions identify
the implementation. Different FFmpeg versions can change video bytes, so source
hashes are recorded rather than presented as cross-platform golden media.
