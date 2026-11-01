"""Download/cache, transcode and audit a public licensed physical video.

No API calls. Output is external ingestion evidence, never calibrated dynamics.
"""
import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from realign.contracts.external import ExternalVideoSource
from realign.perception.video import file_sha256, probe_video, iter_video_frames


def prepare(manifest, original, processed, *, download=False):
    source = ExternalVideoSource(**manifest['provenance'])
    if manifest.get('source_kind') != 'REAL_EXTERNAL':
        raise ValueError('explicit REAL_EXTERNAL manifest required')
    if not original.is_file():
        if not download:
            raise ValueError('original file absent; use --download to retrieve the attributed public file')
        original.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(source.original_video_url, headers={'User-Agent': 'REALIGN-research-validation/0.1'})
        with urllib.request.urlopen(request, timeout=45) as response:
            data = response.read(50_000_001)
        if len(data) > 50_000_000:
            raise ValueError('external media exceeds the 50 MB download budget')
        import hashlib
        if hashlib.sha256(data).hexdigest() != source.original_sha256:
            raise ValueError('download differs from the approved original hash')
        original.write_bytes(data)
    if file_sha256(original) != source.original_sha256:
        raise ValueError('original content hash mismatch')
    original_meta = probe_video(original, source_kind='REAL_EXTERNAL',
                                external_source=replace(source, processed_sha256=source.original_sha256))
    if processed.is_file() and file_sha256(processed) != source.processed_sha256:
        raise ValueError('cached derivative differs from its manifest; supply its verified provenance or transcode to a new path')
    if not processed.is_file():
        processed.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['ffmpeg', '-v', 'error', '-noautorotate', '-i', str(original), '-map', '0:v:0', '-an',
                        '-fps_mode', 'passthrough', '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', str(processed)],
                       check=True, capture_output=True, timeout=120)
    actual = replace(source, processed_sha256=file_sha256(processed))
    meta = probe_video(processed, source_kind='REAL_EXTERNAL', external_source=actual)
    if (meta.width, meta.height, len(meta.pts)) != (original_meta.width, original_meta.height, len(original_meta.pts)):
        raise ValueError('transcode changed display dimensions or frame count')
    import numpy as np
    from fractions import Fraction
    delta = float(np.max(np.abs(meta.t_s-original_meta.t_s)))
    if delta > float(Fraction(meta.time_base))+float(Fraction(original_meta.time_base)):
        raise ValueError('transcode changed presentation times beyond quantization')
    decoded = sum(1 for _ in iter_video_frames(processed, meta))
    return {'status': 'PASS', 'scope': 'REAL_EXTERNAL ingestion only; no SAM masks or physical dynamics measurements',
            'metadata': asdict(meta), 'original_metadata': asdict(original_meta),
            'decoded_frames': decoded, 'max_transcode_timestamp_difference_s': delta,
            'processed_hash_matches_example': actual.processed_sha256 == source.processed_sha256,
            'actual_sam_processing': 'NOT_RUN', 'phone_g2_evidence': False,
            'limitations': manifest.get('limitations', []), 'source_manifest': {'source_kind': 'REAL_EXTERNAL', 'provenance': asdict(actual)}}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, default=ROOT/'configs/external_video.example.json')
    p.add_argument('--original', type=Path, default=ROOT/'data/raw/external/blocked-pendulum-original.webm')
    p.add_argument('--processed', type=Path, default=ROOT/'data/raw/external/blocked-pendulum.mp4')
    p.add_argument('--download', action='store_true')
    p.add_argument('--output-dir', type=Path, default=ROOT/'artifacts')
    args = p.parse_args()
    try:
        report = prepare(json.loads(args.manifest.read_text(encoding='utf-8')), args.original, args.processed, download=args.download)
    except Exception as exc:
        report = {'status': 'FAIL', 'error_type': type(exc).__name__, 'http_status': getattr(exc, 'code', None)}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir/'external_video_ingestion.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    if report['status'] == 'PASS':
        (args.output_dir/'external_source_verified.json').write_text(json.dumps(report['source_manifest'], indent=2)+'\n', encoding='utf-8')
    print('External ingestion:', report['status'])
    raise SystemExit(0 if report['status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
