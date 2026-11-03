"""Read actual integer presentation timestamps, never nominal-FPS timestamps."""
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import subprocess
import numpy as np
from realign.contracts.video import VideoMetadata


class VideoError(ValueError):
    pass


def file_sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def metadata_from_ffprobe(data, *, video_sha256, source_kind,recording_start_utc=None,external_source=None):
    try:
        stream=data['streams'][0]
        pts=[]
        for frame in data['frames']:
            value=frame.get('pts')
            if isinstance(value,bool) or not re.fullmatch(r'-?\d+',str(value)):
                raise VideoError('missing or malformed original PTS; no FPS fallback is allowed')
            pts.append(int(value))
        time_base=stream['time_base']
        if Fraction(time_base)<=0:
            raise VideoError('invalid video time base')
        rotation=next((x['rotation'] for x in stream.get('side_data_list',[]) if 'rotation' in x),
                      stream.get('tags',{}).get('rotate',0))
        rotation=float(rotation)
        if not np.isfinite(rotation) or rotation%90!=0:
            raise VideoError('unsupported display rotation')
        rotation=int(rotation)%360
        w,h=int(stream['width']),int(stream['height'])
        width,height=(h,w) if rotation%180 else (w,h)
        return VideoMetadata(video_sha256,source_kind,width,height,w,h,tuple(pts),time_base,
                             stream.get('codec_name','unknown'),rotation,recording_start_utc,
                             stream.get('tags',{}).get('creation_time',data.get('format',{}).get('tags',{}).get('creation_time')),external_source)
    except (KeyError,IndexError,TypeError,ValueError,ZeroDivisionError) as exc:
        raise VideoError(f'invalid video metadata/PTS: {exc}') from exc


def probe_video(path, *, source_kind='REAL_PHONE',recording_start_utc=None,external_source=None):
    path=Path(path).resolve()
    if not path.is_file():
        raise VideoError('video file does not exist')
    try:
        p=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-read_intervals','%+61',
                          '-show_frames','-show_streams','-show_format','-of','json',str(path)],
                         capture_output=True,check=True,timeout=60)
        data=json.loads(p.stdout)
        if float(data.get('format',{}).get('duration',0))>60.1:
            raise VideoError('recordings must be <=60 seconds')
        return metadata_from_ffprobe(data,video_sha256=file_sha256(path),source_kind=source_kind,
                                     recording_start_utc=recording_start_utc,external_source=external_source)
    except (OSError,subprocess.SubprocessError,json.JSONDecodeError) as exc:
        raise VideoError(f'ffprobe failed ({type(exc).__name__}); install FFmpeg and use a valid local clip') from exc


def iter_video_frames(path, metadata):
    """Decode one RGB frame per original PTS; reject any count mismatch."""
    if file_sha256(path)!=metadata.video_sha256:
        raise VideoError('video content changed after timestamp extraction')
    command=['ffmpeg','-v','error','-noautorotate','-i',str(Path(path).resolve()),
             '-map','0:v:0','-an','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgb24','pipe:1']
    try:
        process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    except OSError as exc:
        raise VideoError('FFmpeg decoder unavailable') from exc
    size=metadata.coded_width*metadata.coded_height*3
    try:
        for _ in metadata.pts:
            raw=process.stdout.read(size)
            if len(raw)!=size:
                raise VideoError('decoded frame count does not match PTS')
            frame=np.frombuffer(raw,dtype=np.uint8).reshape(metadata.coded_height,metadata.coded_width,3)
            if metadata.rotation_deg:
                frame=np.rot90(frame,k=metadata.rotation_deg//90)
            yield frame.copy()
        if process.stdout.read(1):
            raise VideoError('decoded video has extra frames without matching PTS')
        process.wait(timeout=30)
        if process.returncode:
            raise VideoError('FFmpeg decoding failed')
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=10)
