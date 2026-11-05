"""Safe application-only terminal telemetry. Never enable raw SDK logging."""
import json
import logging
import time

LOGGER = logging.getLogger('realign.live')
FIELDS = frozenset(('session','window_id','recording_id','source','mode','state','status','code','category',
    'model','operation','attempt','error_type','http_status','latency_s','queue_latency_s','end_to_end_latency_s',
    'new_observations','valid_frames','returned_mask_count','capture_sequence','frames','width','height',
    'total_requests','reserved_usd','ceiling_usd','reason','request_id','result_sha256','manifest_sha256',
    'video_sha256','image_sha256','audit_head','received_masks','parser_revision','source_frame_index',
    'completed_scientific_evidence','step','action','outcome','tool','evidence_ref','detected_count',
    'queued_frames','queued_windows','dropped_frames','dropped_windows','continuous','camera_index','backend_id'))


def configure_terminal(level='INFO'):
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s.%(msecs)03dZ %(levelname)s [%(threadName)s] %(message)s',datefmt='%Y-%m-%dT%H:%M:%S')
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    LOGGER.handlers[:] = [handler]
    LOGGER.setLevel(level)
    LOGGER.propagate = False


def emit(event_name, *, level=logging.INFO, **fields):
    safe = {k:v for k,v in fields.items() if k in FIELDS and (v is None or type(v) in (str,int,float,bool))}
    LOGGER.log(level,'%s %s',event_name,json.dumps(safe,ensure_ascii=True,allow_nan=False,sort_keys=True))
