"""Hosted SAM 3.1 adapter using Meta's official Python stream/mask parser.

Protocol reference: https://dev.meta.ai/docs/cookbook/sam-api-basics
No segmentation fallback exists here. Error bodies/headers are never logged.
"""
import asyncio
import base64
from contextlib import aclosing
from dataclasses import dataclass
import hashlib
from importlib.metadata import version
import json
import os
import re
from pathlib import Path
import numpy as np
import time
from realign.audit.terminal import emit

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


def _decode_records(records, metadata, *, image=False):
    from meta_sam_parser import decode_mask_to_raster
    masks = {}
    for record in records:
        if record.kind != 'mask': continue
        index = 0 if image and record.frame is None else record.frame.frame_index if record.frame else -1
        if not 0 <= index < len(metadata.pts):
            raise SamError('SAM frame index does not match source', code='frame_mismatch')
        b, mask = record.bounds, record.mask
        if any(not np.isfinite(v) or int(v) != v for v in (b.left,b.top,b.right,b.bottom)):
            raise SamError('noninteger mask placement unsupported', code='mask_bounds')
        if not (0 <= b.left < b.right <= metadata.width and 0 <= b.top < b.bottom <= metadata.height):
            raise SamError('SAM mask outside displayed source frame', code='frame_mismatch')
        if b.right-b.left != mask.width or b.bottom-b.top != mask.height:
            raise SamError('SAM mask dimensions mismatch', code='mask_shape')
        pixels = np.frombuffer(decode_mask_to_raster(mask), dtype=np.uint8).reshape(mask.height,mask.width).astype(bool)
        item = SamMask(index,record.object_id,int(b.left),int(b.top),pixels,record.confidence)
        masks[(index,item.object_id)] = item
    return tuple(masks[k] for k in sorted(masks))


async def parse_sam_events(events, metadata, *, source, media_kind='video', on_partial=None):
    """Consume SDK events or documented wire mappings using the OFFICIAL parser."""
    from meta_sam_parser import parse_responses_stream,video_segmentation_format,image_segmentation_format,ResponsesStreamSourceError
    if source not in ('REAL_API','SIMULATED_API_FIXTURE'):
        raise SamError('explicit API/fixture origin required',code='provenance')
    if media_kind not in ('image','video'): raise SamError('unsupported media',code='media_type')
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
            format_ = image_segmentation_format() if media_kind == 'image' else video_segmentation_format()
            async with parse_responses_stream(stream,format_) as parsed:
                if on_partial is not None:
                    consumed = 0
                    async for snapshot in parsed:
                        if any(d.severity == 'error' for d in snapshot.diagnostics):
                            raise SamError('official parser rejected partial records',code='parser_diagnostic')
                        masks = _decode_records(snapshot.records[consumed:],metadata,image=media_kind=='image')
                        consumed = len(snapshot.records)
                        if masks:
                            on_partial(SamRun(masks,source,metadata.video_sha256,
                                {'status':'streaming','media_kind':media_kind,'model':MODEL,
                                 'response_id':response_id,'parser_revision':snapshot.revision,
                                 'completed_scientific_evidence':False}))
                result=await parsed.final_result()
        if result.outcome.status!='completed':
            raise SamError('SAM stream incomplete; no usable completed measurement',code='incomplete')
        if any(d.severity=='error' for d in result.diagnostics):
            raise SamError('official SAM parser rejected malformed records',code='parser_diagnostic')
        masks = _decode_records(result.records,metadata,image=media_kind=='image')
        receipt={'status':'completed','source':source,'model':MODEL,'prompt':PROMPT,
                 'parser':'meta-sam-parser','parser_version':version('meta-sam-parser'),
                 'response_id':response_id,'mask_records':len(masks),'diagnostic_count':len(result.diagnostics),
                 'media_kind':media_kind}
        return SamRun(masks,source,metadata.video_sha256,receipt)
    except SamError:
        raise
    except Exception as exc:
        # Raw SDK exceptions can contain request details. Persist type/code only.
        code='stream_source_failed' if isinstance(exc,ResponsesStreamSourceError) else 'parser_failed'
        raise SamError(f'official SAM parsing failed ({type(exc).__name__})',code=code) from None


class SamClient:
    def __init__(self,api,*,source='REAL_API',retry_delay=.5,concept=PROMPT,
                 before_request=None,max_attempts=3):
        if not isinstance(concept,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 -]{0,79}',concept):
            raise SamError('one short visual noun phrase required',code='concept')
        self.api=api
        self.source=source
        self.concept=concept
        self.retry_delay=retry_delay
        self.calls=[]
        self.before_request=before_request
        self.on_partial=None
        self.request_confidence=False  # Existing offline request shape stays stable.
        if type(max_attempts) is not int or not 1<=max_attempts<=3: raise ValueError('retry limit')
        self.max_attempts=max_attempts

    @classmethod
    def from_environment(cls,*,standard_tier_confirmed=False,concept=PROMPT):
        key=os.environ.get('MODEL_API_KEY')
        if not key:
            raise SamError('MODEL_API_KEY is not configured locally',code='not_authorized')
        if not standard_tier_confirmed:
            raise SamError('confirm Standard tier in the local manifest before upload',code='tier_unconfirmed')
        from openai import AsyncOpenAI
        return cls(AsyncOpenAI(api_key=key,base_url=BASE_URL,timeout=120,max_retries=0),concept=concept)

    async def _request(self,operation,call,*,first_call=0):
        for attempt in range(self.max_attempts):
            if self.before_request is not None: self.before_request('sam',operation)
            started=time.monotonic()
            emit('SAM_HTTP_STARTED',model=MODEL,operation=operation,attempt=attempt+1)
            try:
                result=await call()
                emit('SAM_HTTP_COMPLETED',model=MODEL,operation=operation,attempt=attempt+1,latency_s=time.monotonic()-started)
                self.calls.append({'operation':operation,'attempt':attempt+1,'status':'completed'})
                return result
            except Exception as exc:
                status=getattr(exc,'status_code',None)
                emit('SAM_HTTP_FAILED',model=MODEL,operation=operation,attempt=attempt+1,
                    error_type=type(exc).__name__,http_status=status if type(status) is int else None)
                category=('SAM_PROTOCOL' if isinstance(exc,SamError) else 'META_HTTP' if type(status) is int else
                          'META_TRANSPORT' if type(exc).__name__ in ('APIConnectionError','APITimeoutError') else 'SDK_RUNTIME')
                self.calls.append({'operation':operation,'attempt':attempt+1,'status':'failed',
                                   'error_type':type(exc).__name__,'http_status':status if type(status) is int and 100<=status<=599 else None,
                                   'category':category,'code':exc.code if isinstance(exc,SamError) else category+'_ERROR'})
                retryable=(isinstance(exc,SamError) and exc.code=='stream_source_failed') or (
                    not isinstance(exc,SamError) and (status is None or status in (408,429) or status>=500))
                if not retryable or attempt==self.max_attempts-1:
                    raise SamError(f'SAM {operation} failed ({type(exc).__name__}); no fallback',
                                   code=operation+'_failed',calls=self.calls[first_call:]) from None
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
        uploaded=await self._request('upload',upload,first_call=first_call)
        file_id=uploaded.id
        if not isinstance(file_id,str) or not file_id.startswith('file-'):
            raise SamError('Files API returned an invalid file ID',code='file_id',calls=self.calls[first_call:])
        request={'model':MODEL,'stream':True,'input':[{'type':'message','role':'user','content':[
            {'type':'input_text','text':self.concept},{'type':'input_video','file_id':file_id}]}]}
        if self.request_confidence: request['metadata']={'include_confidence':'true'}
        async def segment():
            stream=await self.api.responses.create(**request)
            async with stream:
                options = {'on_partial':self.on_partial} if self.on_partial is not None else {}
                return await parse_sam_events(stream,metadata,source=self.source,**options)
        run=await self._request('segmentation',segment,first_call=first_call)
        receipt=dict(run.receipt,upload_file_id=file_id,
            prompt=self.concept,
            request_sha256=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest(),
            video_sha256=metadata.video_sha256,calls=list(self.calls[first_call:]))
        return SamRun(run.masks,run.source,run.video_sha256,receipt)

    async def segment_image(self,path,metadata):
        """Documented input_image with a PNG data URL; no video upload or FPS."""
        from .video import file_sha256
        path = Path(path)
        if path.suffix.lower() != '.png' or file_sha256(path) != metadata.video_sha256:
            raise SamError('source PNG hash mismatch',code='input_changed')
        first_call = len(self.calls)
        request = {'model':MODEL,'stream':True,'metadata':{'include_confidence':'true'},
            'input':[{'type':'message','role':'user','content':[
                {'type':'input_text','text':self.concept},
                {'type':'input_image','image_url':'data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode('ascii')}]}]}
        async def segment():
            stream = await self.api.responses.create(**request)
            async with stream:
                return await parse_sam_events(stream,metadata,source=self.source,media_kind='image',on_partial=self.on_partial)
        run = await self._request('image_segmentation',segment,first_call=first_call)
        receipt = dict(run.receipt,prompt=self.concept,image_sha256=metadata.video_sha256,
            request_sha256=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest(),
            calls=list(self.calls[first_call:]))
        return SamRun(run.masks,run.source,run.video_sha256,receipt)

    async def close(self):
        await self.api.close()
