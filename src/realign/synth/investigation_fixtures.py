"""Trusted synthetic environment, OUTSIDE the isolated investigator/tool worker.

Only public observations/reference measurements cross the capability boundary.
Hidden parameters and expected outcomes are used by post-freeze reporting only.
"""
from dataclasses import replace
import numpy as np
from realign.contracts import Experiment, NoiseConfig
from realign.physics import PendulumParams, PegParams
from realign.audit.chain import digest
from .generator import generate_trial

NOMINAL=PendulumParams(.72,gamma_per_s=.06,quadratic_drag_per_m=.02)


def reference_measurements(seed, sigma, *, shift_px=0.):
    rng=np.random.default_rng(seed+900000)
    target=np.array([[100.,100.],[400.,100.],[400.,350.],[100.,350.]])
    observed=target+np.array([shift_px,0.])+rng.normal(0,.03,target.shape)
    stationary=rng.normal(0,sigma,(100,2))+[250.,300.]
    return {'source':'SYNTHETIC','reference_px':target.tolist(),'observed_px':observed.tolist(),
            'stationary_xy_px':stationary.tolist()}


class SyntheticEnvironment:
    def __init__(self, params, *, seed=51000, sigma=.5, measurement_shift_px=0., limited=False, insufficient=False):
        self._params=params; self.seed=seed; self.sigma=sigma
        self.shift=measurement_shift_px; self.limited=limited; self.insufficient=insufficient
        self.count=0; self.requests=[]
        self.checks=reference_measurements(seed,sigma,shift_px=self.shift)
        self.initial=[self._trial(a) for a in (.2,.32)]
        self.allowed_release_angles=(.3,) if limited else (.65,)

    def _trial(self, angle, *, duration=1.6, zone='exploration'):
        index=self.count; self.count+=1
        rate=8. if self.insufficient else 20.
        t,_=generate_trial(self._params,Experiment(float(angle),duration,rate),
            seed=self.seed+index,trial_id='obs-'+digest({'seed':self.seed,'index':index})[:16],
            noise=NoiseConfig(((self.sigma**2,0.),(0.,self.sigma**2))),zone=zone)
        if self.shift:
            t=replace(t,observation=replace(t.observation,xy_px=t.observation.xy_px+[self.shift,0.]))
        return t

    def perform(self, candidate):
        action=candidate['action']; kind=action['kind']
        self.requests.append(candidate['experiment_ref'])
        if kind=='RELEASE':
            angle=action['release_angle_rad']
            if angle not in self.allowed_release_angles:
                return None
            trials=[self._trial(angle,duration=action['duration_s']) for _ in range(action['repeats'])]
            return {'trials':trials,'checks':None,'receipt':{'kind':kind,'source':'SYNTHETIC_ENVIRONMENT','new_observations':len(trials)}}
        if kind=='REPEAT':
            trials=[self._trial(.2) for _ in range(action['repeats'])]
            return {'trials':trials,'checks':None,'receipt':{'kind':kind,'source':'SYNTHETIC_ENVIRONMENT','new_observations':len(trials)}}
        if kind in ('CAMERA_CALIBRATION','STATIONARY_REFERENCE'):
            fresh=reference_measurements(self.seed+100,self.sigma,shift_px=self.shift)
            checks=dict(self.checks)
            if kind=='CAMERA_CALIBRATION':
                checks.update(reference_px=fresh['reference_px'],observed_px=fresh['observed_px'])
            else:
                checks['stationary_xy_px']=fresh['stationary_xy_px']
            self.checks=checks
            return {'trials':[],'checks':checks,'receipt':{'kind':kind,'source':'SYNTHETIC_ENVIRONMENT','new_observations':0}}
        return None

    def development_after_freeze(self):
        return [self._trial(a,zone='development') for a in (.4,.56,.62)]


def case(label, *, seed=51000, sigma=.5):
    p=NOMINAL
    options={}
    if label=='parameter_mismatch':
        p=replace(p,length_m=.76,gamma_per_s=.11,quadratic_drag_per_m=.05)
    elif label=='vertical_peg':
        p=replace(p,peg=PegParams(.16))
    elif label in ('off_vertical_peg','two_round'):
        p=replace(p,peg=PegParams(.16,-.4))
    elif label=='unexcited_peg':
        p=replace(p,peg=PegParams(.16,-.8)); options['limited']=True
    elif label=='measurement_problem':
        options['measurement_shift_px']=8.
    elif label=='insufficient':
        options['insufficient']=True; options['limited']=True
    elif label!='no_fault':
        raise ValueError('unknown synthetic fixture')
    return SyntheticEnvironment(p,seed=seed,sigma=sigma,**options)
