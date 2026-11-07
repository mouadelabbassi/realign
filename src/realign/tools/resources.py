"""Immutable memory store and explicit observation transfer. No filesystem I/O."""
from dataclasses import asdict, fields
import json
import numpy as np
from realign.audit.chain import canonical, digest
from realign.contracts import Trial, Observation, PlaneProjection, Experiment
from realign.contracts.video import VideoTrial, VideoObservation, VideoMetadata, NoiseEstimate, PlanarCalibration, ReleaseEstimate
from realign.contracts.external import ExternalVideoSource


class AccessDenied(ValueError):
    pass


def _clean(v):
    if isinstance(v, np.ndarray):
        return _clean(v.tolist())
    if isinstance(v, dict):
        return {k:_clean(x) for k,x in v.items()}
    if isinstance(v, (tuple,list)):
        return [_clean(x) for x in v]
    if isinstance(v, float) and not np.isfinite(v):
        if np.isnan(v):
            return None
        raise ValueError('nonfinite observation value')
    return v


def encode_trial(trial):
    if type(trial) not in (Trial, VideoTrial) or trial.zone != 'exploration':
        raise AccessDenied('only approved exploration observations may be transferred')
    if len(trial.observation.t_s)>256 or trial.experiment.duration_s>4:
        raise ValueError('runtime observation size/duration budget exceeded')
    value = {'kind':'VIDEO' if type(trial) is VideoTrial else 'DIRECT', 'trial':_clean(asdict(trial))}
    identity = digest({'t':value['trial']['observation'].get('t_s', value['trial']['observation'].get('metadata')),
                       'xy':value['trial']['observation']['xy_px']})[:16]
    value['trial']['trial_id'] = 'obs-'+identity
    if value['kind']=='VIDEO':
        value['trial']['observation']['recording_id'] = 'obs-'+identity
    return value


def _exact(value, cls):
    names={f.name for f in fields(cls)}
    if not isinstance(value,dict) or not set(value).issubset(names):
        raise AccessDenied('unknown observation contract fields')
    return dict(value)


def decode_trial(record):
    if set(record) != {'kind','trial'} or record['kind'] not in ('DIRECT','VIDEO'):
        raise AccessDenied('unsupported observation envelope')
    cls = VideoTrial if record['kind']=='VIDEO' else Trial
    d = _exact(record['trial'], cls)
    if d.get('zone') != 'exploration':
        raise AccessDenied('only exploration is accessible')
    exp = Experiment(**_exact(d.pop('experiment'), Experiment))
    projection = d.pop('projection')
    o = d.pop('observation')
    if cls is Trial:
        o = _exact(o, Observation)
        o.update(t_s=np.array(o['t_s']), xy_px=np.array(o['xy_px'],dtype=float), valid=np.array(o['valid'],dtype=bool))
        result = Trial(experiment=exp, projection=PlaneProjection(**_exact(projection,PlaneProjection)), observation=Observation(**o), **d)
    else:
        o = _exact(o, VideoObservation)
        metadata = _exact(o.pop('metadata'), VideoMetadata)
        if metadata.get('external_source') is not None:
            metadata['external_source']=ExternalVideoSource(**_exact(metadata['external_source'],ExternalVideoSource))
        o['metadata']=VideoMetadata(**metadata)
        o['noise']=NoiseEstimate(**_exact(o['noise'],NoiseEstimate))
        for key in ('xy_px','frame_covariance_px2'):
            o[key]=np.array(o[key],dtype=float)
        o['valid']=np.array(o['valid'],dtype=bool); o['flags']=np.array(o['flags'],dtype=np.uint32)
        release=ReleaseEstimate(**_exact(d.pop('release'),ReleaseEstimate))
        result=VideoTrial(experiment=exp,projection=PlanarCalibration(**_exact(projection,PlanarCalibration)),
                          observation=VideoObservation(**o),release=release,**d)
    if len(result.observation.t_s)>256 or result.experiment.duration_s>4:
        raise ValueError('runtime observation budget exceeded')
    return result


class ResourceStore:
    def __init__(self):
        self._values = {}
        self._allowed = set()

    def put(self, kind, value):
        encoded=canonical({'kind':kind,'value':value})
        ref=digest({'kind':kind,'value':value})
        if ref in self._values and self._values[ref]!=encoded:
            raise RuntimeError('content collision')
        self._values[ref]=encoded
        self._allowed.add(ref)
        return ref

    def get(self, ref, kind):
        if ref not in self._allowed:
            raise AccessDenied('resource is not allowed')
        item=json.loads(self._values[ref])
        if item['kind']!=kind or digest(item)!=ref:
            raise AccessDenied('resource type/integrity mismatch')
        return item['value']

    def has(self, ref, kind):
        try:
            self.get(ref,kind)
            return True
        except AccessDenied:
            return False
