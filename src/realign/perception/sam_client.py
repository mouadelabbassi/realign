"""Hosted SAM 3.1 adapter using Meta's official Python stream/mask parser.

Protocol reference: https://dev.meta.ai/docs/cookbook/sam-api-basics
No segmentation fallback exists here. Error bodies/headers are never logged.
"""
import asyncio
from contextlib import aclosing
from dataclasses import dataclass
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import numpy as np

MODEL='sam-3.1'
PROMPT='the pendulum bob'
BASE_URL='https://api.meta.ai/v1'


class SamError(RuntimeError):
    def __init__(self,message,*,code='sam_error',calls=()):
        super().__init__(message)
        self.code=code
        self.calls=tuple(calls)


@dataclass(frozen=True)
class SamMask:
    frame_index: int
    object_id: str
    left: int
    top: int
    pixels: np.ndarray
    confidence: float | None = None

    def __post_init__(self):
        p=np.array(self.pixels,dtype=bool,copy=True)
        if p.ndim!=2:
            raise SamError('mask must be a raster',code='mask_shape')
        p.flags.writeable=False
        object.__setattr__(self,'pixels',p)


@dataclass(frozen=True)
class SamRun:
    masks: tuple
    source: str
    video_sha256: str
    receipt: dict


async def parse_sam_events(events, metadata, *, source):
    """Consume SDK events or documented wire mappings using the OFFICIAL parser."""
    from meta_sam_parser import parse_responses_stream,video_segmentation_format,decode_mask_to_raster,ResponsesStreamSourceError
    if source not in ('REAL_API','SIMULATED_API_FIXTURE'):
        raise SamError('explicit API/fixture origin required',code='provenance')
    response_id=None
    async def tapped():
        nonlocal response_id
        async def normalize(event):
            nonlocal response_id
            data=event.model_dump() if hasattr(event,'model_dump') else dict(event)
            response=data.get('response',{})
            if isinstance(response,dict) and isinstance(response.get('id'),str):
                response_id=response['id']
            return data
        if hasattr(events,'__aiter__'):
            async for event in events:
                yield await normalize(event)
        else:
            for event in events:
                yield await normalize(event)
    try:
        async with aclosing(tapped()) as stream:
            async with parse_responses_stream(stream,video_segmentation_format()) as parsed:
                result=await parsed.final_result()
        if result.outcome.status!='completed':
            raise SamError('SAM stream incomplete; no usable completed measurement',code='incomplete')
        if any(d.severity=='error' for d in result.diagnostics):
            raise SamError('official SAM parser rejected malformed records',code='parser_diagnostic')
        masks={}
        for record in result.records:
            if record.kind!='mask':
                continue
            if record.frame is None or not 0<=record.frame.frame_index<len(metadata.pts):
                raise SamError('SAM frame index does not match source PTS',code='frame_mismatch')
            b=record.bounds; mask=record.mask
            values=(b.left,b.top,b.right,b.bottom)
            if any(not np.isfinite(x) or int(x)!=x for x in values):
                raise SamError('noninteger mask placement unsupported',code='mask_bounds')
            if not (0<=b.left<b.right<=metadata.width and 0<=b.top<b.bottom<=metadata.height):
                raise SamError('SAM mask outside displayed source frame',code='frame_mismatch')
            if b.right-b.left!=mask.width or b.bottom-b.top!=mask.height or mask.width*mask.height>metadata.width*metadata.height:
                raise SamError('SAM mask dimensions mismatch',code='mask_shape')
            pixels=np.frombuffer(decode_mask_to_raster(mask),dtype=np.uint8).reshape(mask.height,mask.width).astype(bool)
            item=SamMask(record.frame.frame_index,record.object_id,int(b.left),int(b.top),pixels,record.confidence)
            # Parser snapshots are cumulative; final revisions replace the same identity.
            masks[(item.frame_index,item.object_id)]=item
        receipt={'status':'completed','source':source,'model':MODEL,'prompt':PROMPT,
                 'parser':'meta-sam-parser','parser_version':version('meta-sam-parser'),
                 'response_id':response_id,'mask_records':len(masks),'diagnostic_count':len(result.diagnostics)}
        return SamRun(tuple(masks[k] for k in sorted(masks)),source,metadata.video_sha256,receipt)
    except SamError:
        raise
    except Exception as exc:
        # Raw SDK exceptions can contain request details. Persist type/code only.
        code='stream_source_failed' if isinstance(exc,ResponsesStreamSourceError) else 'parser_failed'
        raise SamError(f'official SAM parsing failed ({type(exc).__name__})',code=code) from None


class SamClient:
    def __init__(self,api,*,source='REAL_API',retry_delay=.5):
        self.api=api
        self.source=source
        self.retry_delay=retry_delay
        self.calls=[]

    @classmethod
    def from_environment(cls,*,standard_tier_confirmed=False):
        key=os.environ.get('MODEL_API_KEY')
        if not key:
            raise SamError('MODEL_API_KEY is not configured locally',code='not_authorized')
        if not standard_tier_confirmed:
            raise SamError('confirm Standard tier in the local manifest before upload',code='tier_unconfirmed')
        from openai import AsyncOpenAI
        return cls(AsyncOpenAI(api_key=key,base_url=BASE_URL,timeout=120,max_retries=0))

    async def _request(self,operation,call):
        for attempt in range(3):
            try:
                result=await call()
                self.calls.append({'operation':operation,'attempt':attempt+1,'status':'completed'})
                return result
            except Exception as exc:
                status=getattr(exc,'status_code',None)
                self.calls.append({'operation':operation,'attempt':attempt+1,'status':'failed',
                                   'error_type':type(exc).__name__,'http_status':status})
                retryable=(isinstance(exc,SamError) and exc.code=='stream_source_failed') or (
                    not isinstance(exc,SamError) and (status is None or status in (408,429) or status>=500))
                if not retryable or attempt==2:
                    raise SamError(f'SAM {operation} failed ({type(exc).__name__}); no fallback',
                                   code=operation+'_failed',calls=self.calls) from None
                await asyncio.sleep(self.retry_delay*2**attempt)

    async def segment_video(self,path,metadata):
        from .video import file_sha256
        path=Path(path)
        first_call=len(self.calls)
        if path.suffix.lower()!='.mp4':
            raise SamError('hosted video workflow accepts an MP4; transcode explicitly and recalibrate if needed',code='media_type')
        if file_sha256(path)!=metadata.video_sha256:
            raise SamError('video changed after metadata extraction',code='input_changed')
        async def upload():
            with path.open('rb') as f:
                return await self.api.files.create(file=(path.name,f,'video/mp4'),purpose='user_data')
        uploaded=await self._request('upload',upload)
        file_id=uploaded.id
        if not isinstance(file_id,str) or not file_id.startswith('file-'):
            raise SamError('Files API returned an invalid file ID',code='file_id',calls=self.calls)
        request={'model':MODEL,'stream':True,'input':[{'type':'message','role':'user','content':[
            {'type':'input_text','text':PROMPT},{'type':'input_video','file_id':file_id}]}]}
        async def segment():
            stream=await self.api.responses.create(**request)
            async with stream:
                return await parse_sam_events(stream,metadata,source=self.source)
        run=await self._request('segmentation',segment)
        receipt=dict(run.receipt,upload_file_id=file_id,
            request_sha256=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest(),
            video_sha256=metadata.video_sha256,calls=list(self.calls[first_call:]))
        return SamRun(run.masks,run.source,run.video_sha256,receipt)

    async def close(self):
        await self.api.close()
