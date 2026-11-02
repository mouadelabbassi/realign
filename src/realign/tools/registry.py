"""Five bounded numerical handlers. All data enter through immutable capabilities.

No file loading, generator imports, development observations or arbitrary code.
This module runs inside the isolated worker, not in the model adapter process.
"""
from dataclasses import asdict
import math
import numpy as np
from pydantic import ValidationError
from realign.audit.chain import AuditChain, digest, canonical
from realign.contracts import Experiment, Trial, Observation, PlaneProjection
from realign.contracts.video import VideoTrial
from realign.contracts.investigation import Budget, TOOLS, ToolFailure, ExperimentCandidate
from realign.physics import PendulumParams, PegParams
from realign.fit.robust_fit import FitOptions, FitError, fit_free, predict_free, residuals_free
from realign.fit.peg_fit import PegFitOptions, fit_peg, predict_peg, residuals_peg, score_peg
from realign.fit.baselines import score_free, observation_fingerprint
from .resources import ResourceStore, AccessDenied, decode_trial


PROTOCOL = {
    'version':'task04-pilot-1', 'alpha':.05, 'minimum_null_replicates':20,
    'duration_s':1.6, 'sample_rate_hz':20., 'angles_rad':[.2,.32,.65,.65],
    'localization_sd_px':[.5,1.5], 'folds':2, 'formal_comparisons':1,
    'maximum_cv_noise_ratio':4., 'minimum_coverage_rad':.6,
    'length_bounds_m':[.6,.85], 'gamma_bounds_per_s':[0.,.3],
    'quadratic_bounds_per_m':[0.,.2], 'peg_fraction_bounds':[.04,.4],
    'peg_angle_bounds_rad':[-.9,.1], 'wrap_side':-1,
    'scope':'SYNTHETIC_REGISTERED_PREDICTIVE_MODEL_COMPARISON',
}


class Exhausted(RuntimeError):
    pass


def empirical_tail(scores, statistic):
    # An unavailable null fit is a worst-case exceedance, never evidence that
    # the observed mechanism is unusual. Missing replicates cannot lower p.
    return (1+sum(x is None or x>=statistic for x in scores))/(len(scores)+1)


def parameters(value):
    d=dict(value)
    if d.get('peg') is not None:
        d['peg']=PegParams(**d['peg'])
    return PendulumParams(**d)


def predict(params, trial):
    return predict_peg(params,trial) if params.peg else predict_free(params,trial)


def _floor(trials):
    return float(np.mean([np.trace(t.observation.covariance_px2) for t in trials]))


def _mse(params, trials):
    return float(np.mean([np.mean(np.sum((predict(params,t)[t.observation.valid]-t.observation.xy_px[t.observation.valid])**2,axis=1))
                          for t in trials]))


class ToolRegistry:
    def __init__(self, records, nominal, *, budget=None, checks=None, gate=None):
        self.store=ResourceStore(); self.audit=AuditChain()
        self.budget=budget or Budget()
        self.budget_ref=self.store.put('BUDGET',self.budget.model_dump(mode='json'))
        self.protocol_ref=self.store.put('PROTOCOL',PROTOCOL)
        self.used={'tool_calls':0,'fit_jobs':0}
        self.trial_refs=[]; self.fit_cache={}; self.comparison_cache={}
        self.candidates={}
        self.checks_ref=self.store.put('CHECKS',checks or {})
        self.checks=self._check_quality(checks or {})
        self.nominal=parameters(nominal)
        if self.nominal.peg is not None:
            raise ValueError('nominal model must be FREE')
        self.nominal_ref=self.store.put('MODEL',{'family':'FREE','params':asdict(self.nominal),
            'training_refs':[],'budget_ref':self.budget_ref,'role':'NOMINAL'})
        self.gate_ref=None
        if gate is not None:
            self._validate_gate(gate)
            self.gate_ref=self.store.put('GATE',gate)
        self.admit(records)
        self.frozen=False

    def _validate_gate(self, gate):
        if set(gate)!={'protocol_ref','budget_ref','scores','sample_count','failed_comparisons','scope'}:
            raise ValueError('invalid calibration fields')
        scores=gate['scores']
        if gate['protocol_ref']!=self.protocol_ref or gate['budget_ref']!=self.budget_ref:
            raise ValueError('calibration protocol/budget mismatch')
        if len(scores)!=gate['sample_count'] or len(scores)<20 or len(scores)>64:
            raise ValueError('insufficient registered null replicates')
        if any(x is not None and (type(x) not in (float,int) or not math.isfinite(x)) for x in scores):
            raise ValueError('invalid calibration statistic')
        if sum(x is not None for x in scores)<16:
            raise ValueError('too many failed null comparisons')
        if gate['failed_comparisons']!=sum(x is None for x in scores) or gate['scope']!=PROTOCOL['scope']:
            raise ValueError('calibration provenance mismatch')

    @staticmethod
    def _check_quality(checks):
        if not isinstance(checks,dict) or set(checks)-{'reference_px','observed_px','stationary_xy_px','source'}:
            raise ValueError('only approved reference measurements allowed')
        if checks and checks.get('source') not in ('SYNTHETIC','REAL_MEASURED'):
            raise ValueError('explicit reference provenance required')
        rms=sd=None
        if checks.get('reference_px') is not None:
            a=np.asarray(checks['reference_px'],float); b=np.asarray(checks.get('observed_px'),float)
            if a.shape!=b.shape or a.ndim!=2 or a.shape[1]!=2 or not 4<=len(a)<=32 or not np.isfinite([a,b]).all():
                raise ValueError('invalid independent reference pairs')
            rms=float(np.sqrt(np.mean(np.sum((a-b)**2,axis=1))))
        if checks.get('stationary_xy_px') is not None:
            a=np.asarray(checks['stationary_xy_px'],float)
            if a.ndim!=2 or a.shape[1]!=2 or not 16<=len(a)<=256 or not np.isfinite(a).all():
                raise ValueError('invalid stationary observations')
            sd=float(np.sqrt(np.linalg.eigvalsh(np.cov(a.T,ddof=1)).max()))
        return {'reference_reprojection_rms_px':rms,'stationary_sd_px':sd,
                'quality_ok':rms is not None and sd is not None and rms<=1. and sd<=3.}

    def admit(self, records, checks=None):
        if getattr(self,'frozen',False):
            raise AccessDenied('investigation is frozen')
        if len(self.trial_refs)+len(records)>6:
            raise ValueError('too many exploration observations')
        old={observation_fingerprint(self.trial(r)) for r in self.trial_refs}
        staged=[]
        for record in records:
            t=decode_trial(record)
            fingerprint=observation_fingerprint(t)
            if fingerprint in old:
                raise AccessDenied('duplicate exploration observations')
            old.add(fingerprint)
            previous=self.trial(self.trial_refs[0]) if self.trial_refs else staged[0][1] if staged else None
            if previous is not None and t.observation.provenance!=previous.observation.provenance:
                raise AccessDenied('cannot mix observation provenance')
            staged.append((record,t))
        effective_checks=checks if checks is not None else self.store.get(self.checks_ref,'CHECKS')
        quality=self._check_quality(effective_checks)
        first=staged[0][1] if staged else self.trial(self.trial_refs[0]) if self.trial_refs else None
        if first is not None and effective_checks:
            expected='SYNTHETIC' if first.observation.provenance=='SYNTHETIC' else 'REAL_MEASURED'
            if effective_checks.get('source')!=expected:
                raise AccessDenied('reference/observation provenance mismatch')
        for record,_ in staged:
            self.trial_refs.append(self.store.put('TRIAL',record))
        if checks is not None:
            self.checks=quality
            self.checks_ref=self.store.put('CHECKS',checks)

    def register_candidates(self, candidates):
        for raw in candidates:
            c=ExperimentCandidate.model_validate_json(json_bytes(raw))
            if c.experiment_ref!=digest({'kind':'EXPERIMENT','action':c.action.model_dump(mode='json')}):
                raise AccessDenied('experiment content reference mismatch')
            self.candidates[c.experiment_ref]=c

    def trial(self, ref):
        return decode_trial(self.store.get(ref,'TRIAL'))

    def _trials(self, refs):
        if len(set(refs))!=len(refs):
            raise AccessDenied('duplicate references')
        return tuple(self.trial(r) for r in refs)

    def model(self, ref):
        return self.store.get(ref,'MODEL')

    def _charge(self, count):
        if self.used['fit_jobs']+count>self.budget.max_fit_jobs:
            raise Exhausted('fit budget')
        self.used['fit_jobs']+=count

    def _fit(self, family, refs):
        self._charge(1)
        key=(family,tuple(refs))
        if key in self.fit_cache:
            return self.fit_cache[key]
        trials=self._trials(refs)
        common=dict(n_starts=8,max_nfev=self.budget.max_nfev,
            length_bounds_m=tuple(PROTOCOL['length_bounds_m']),
            gamma_bounds_per_s=tuple(PROTOCOL['gamma_bounds_per_s']),
            quadratic_bounds_per_m=tuple(PROTOCOL['quadratic_bounds_per_m']))
        if family=='FREE':
            f=fit_free(trials,self.nominal,FitOptions(**common))
        else:
            init=self.fit_cache.get(('FREE',tuple(refs)))
            f=fit_peg(trials,self.nominal,PegFitOptions(**common,
                peg_fraction_bounds=tuple(PROTOCOL['peg_fraction_bounds']),
                peg_angle_bounds_rad=tuple(PROTOCOL['peg_angle_bounds_rad'])),
                initializer=parameters(init['params']) if init else None)
        data=asdict(f)
        result={'family':family,'params':asdict(f.params),'fit':data,'training_refs':list(refs),'budget_ref':self.budget_ref,'role':'FITTED'}
        self.fit_cache[key]=result
        return result

    def _emit(self,name,args,data,*,failure=False):
        ref=self.store.put('EVIDENCE',{'tool':name,'input_sha256':digest(args),'output':data})
        cls=ToolFailure if failure else TOOLS[name][1]
        result=cls(evidence_ref=ref,**data).model_dump(mode='json')
        self.audit.append('TOOL',{'name':name,'input_sha256':digest(args),'output':result,'used':dict(self.used)})
        return result

    def dispatch(self, name, raw):
        if self.frozen:
            raise AccessDenied('investigation is frozen')
        safe_name=name if name in TOOLS else 'REJECTED'
        try:
            if name not in TOOLS:
                raise AccessDenied('unknown tool')
            if self.used['tool_calls']>=self.budget.max_tool_calls:
                raise Exhausted('tool budget')
            self.used['tool_calls']+=1
            args=TOOLS[name][0].model_validate_json(json_bytes(raw))
            data=getattr(self,'_'+name)(args)
            return self._emit(name,args.model_dump(mode='json'),data)
        except AccessDenied:
            code='ACCESS_DENIED'
        except Exhausted:
            code='BUDGET'
        except (ValidationError,ValueError,TypeError,KeyError):
            code='INVALID_INPUT'
        except (FitError,RuntimeError,FloatingPointError,np.linalg.LinAlgError):
            code='SOLVER_FAILURE'
        return self._emit(safe_name,{'request_hash':digest(raw)}, {'status':'FAILED','code':code},failure=True)

    def _inspect_discrepancy(self, a):
        model=self.model(a.model_ref); p=parameters(model['params'])
        ts=self._trials(a.trial_refs); floor=_floor(ts)
        n=sum(int(t.observation.valid.sum()) for t in ts)
        if n==0:
            raise ValueError('missing observations')
        mse=_mse(p,ts)
        residuals=(residuals_peg if p.peg else residuals_free)(p,ts)
        missing=1-n/sum(len(t.observation.t_s) for t in ts)
        lag=None
        if p.peg is None:
            lag=score_free(p,ts,p.length_m)['lag1_x']
        flags=[]
        if not self.checks['quality_ok']:
            flags.append('QUALITY_FAILURE' if self.checks['reference_reprojection_rms_px'] is not None else 'MISSING_REFERENCE')
        if missing>.15:
            flags.append('QUALITY_FAILURE')
        adequate=bool(n>=48 and missing<=.15 and mse<=2.5*floor and np.mean(residuals**2)<=2.5)
        return {'status':'OK','flags':tuple(flags),'valid_samples':n,'trajectory_rmse_px':math.sqrt(mse),
            'innovation_mean_square':float(np.mean(residuals**2)),'lag1_x':lag,
            'localization_floor_mse_px2':floor,'missing_fraction':missing,
            **self.checks,'predictively_adequate':adequate}

    def _fit_candidate_model(self, a):
        if a.budget_ref!=self.budget_ref or a.nominal_model_ref!=self.nominal_ref:
            raise AccessDenied('unapproved fit configuration')
        try:
            f=self._fit(a.candidate,a.trial_refs)
        except FitError as exc:
            ref=self.store.put('DIAGNOSTICS',{'starts':list(exc.starts),'failure':'SOLVER_OR_EXCITATION_FAILURE'})
            flag='INSUFFICIENT_DATA' if 'insufficient' in str(exc) else 'UNEXCITED' if 'unexcited' in str(exc) else 'SOLVER_FAILURE'
            return {'status':'FAILED','flags':(flag,),'candidate':a.candidate,
                'fitted_model_ref':None,'diagnostics_ref':ref,'robust_cost':None,
                'attempted_starts':len(exc.starts),'converged_starts':0,'fit_jobs_charged':1,'residual_calls':None}
        ref=self.store.put('MODEL',f)
        diag=self.store.put('DIAGNOSTICS',f['fit'])
        starts=f['fit']['starts']
        return {'status':'OK','flags':(),'candidate':a.candidate,'fitted_model_ref':ref,
            'diagnostics_ref':diag,'robust_cost':f['fit']['robust_cost'],
            'attempted_starts':len(starts),'converged_starts':sum(s['success'] for s in starts),
            'fit_jobs_charged':1,
            'residual_calls':sum(s['residual_calls'] for s in starts) if a.candidate=='PEG_ONE_SIDE' else None}

    def _registered_design(self, ts):
        if len(ts)!=4 or not all(type(t) is Trial for t in ts):
            return False
        if asdict(self.nominal)!={'length_m':.72,'g':9.80665,'gamma_per_s':.06,'quadratic_drag_per_m':.02,'peg':None}:
            return False
        angles=[t.experiment.release_angle_rad for t in ts]
        if not np.allclose(angles,PROTOCOL['angles_rad'],atol=1e-10,rtol=0):
            return False
        for t in ts:
            e=t.experiment; o=t.observation
            sd=math.sqrt(o.covariance_px2[0][0])
            if e.duration_s!=1.6 or e.sample_rate_hz!=20. or e.release_velocity_rad_per_s!=0 or len(o.t_s)!=33:
                return False
            if o.ar1_phi!=0 or not o.valid.all() or not any(abs(sd-x)<1e-10 for x in (.5,1.5)):
                return False
            if not np.allclose(o.covariance_px2,np.eye(2)*sd**2,atol=1e-12) or t.projection!=PlaneProjection():
                return False
        return all(np.allclose(t.observation.covariance_px2,ts[0].observation.covariance_px2) for t in ts)

    def _compare_candidate_models(self, a):
        if a.protocol_ref!=self.protocol_ref:
            raise AccessDenied('unapproved comparison')
        if list(a.trial_refs)!=self.trial_refs:
            raise AccessDenied('comparison must use every current observation in registered order')
        ts=self._trials(a.trial_refs)
        models=[self.model(r) for r in a.fitted_model_refs]
        if {m['family'] for m in models}!={'FREE','PEG_ONE_SIDE'}:
            raise AccessDenied('exactly FREE and PEG_ONE_SIDE required')
        if any(m['role']!='FITTED' or m['training_refs']!=list(a.trial_refs) for m in models):
            raise AccessDenied('models must use exactly the current exploration records')
        refs={m['family']:r for m,r in zip(models,a.fitted_model_refs)}
        floor=_floor(ts)
        folds=[]; scores={'FREE':[],'PEG_ONE_SIDE':[]}; count=0
        if len(ts)>=4:
            for parity in (0,1):
                train=tuple(r for i,r in enumerate(a.trial_refs) if i%2!=parity)
                held=tuple(t for i,t in enumerate(ts) if i%2==parity)
                row={'training_refs':list(train),'validation_refs':[r for i,r in enumerate(a.trial_refs) if i%2==parity]}
                for family in ('FREE','PEG_ONE_SIDE'):
                    count+=1
                    try:
                        f=self._fit(family,train)
                        row[family]={'mse_px2':_mse(parameters(f['params']),held),
                                     'fit_diagnostics':f['fit']}
                        scores[family].append(row[family]['mse_px2'])
                    except (FitError,ValueError,RuntimeError,FloatingPointError) as exc:
                        if isinstance(exc,Exhausted):
                            raise
                        row[family]={'failure':type(exc).__name__,'starts':list(getattr(exc,'starts',()))}
                folds.append(row)
        statistic=None
        if all(len(scores[f])==2 for f in scores):
            statistic=float(min((x-y)/floor for x,y in zip(scores['FREE'],scores['PEG_ONE_SIDE'])))
        valid=self._registered_design(ts) and self.gate_ref is not None
        p=threshold=None; support='NOT_ASSESSED'; n=0
        if valid and statistic is not None:
            gate=self.store.get(self.gate_ref,'GATE'); n=len(gate['scores'])
            threshold=max(0.,max(x for x in gate['scores'] if x is not None))
            p=empirical_tail(gate['scores'],statistic)
            support='INDISTINGUISHABLE'
            peg_ratio=float(np.mean(scores['PEG_ONE_SIDE']))/floor
            if p<=.05 and statistic>threshold and peg_ratio<=4.:
                support='PEG_PREDICTIVE_DIFFERENCE'
        flags=() if valid and statistic is not None else ('UNCALIBRATED',)
        if len(ts)<4:
            flags+=('INSUFFICIENT_DATA',)
        rows=[{'model_ref':refs[f],'candidate':f,
               'trial_cv_mse_px2':float(np.mean(scores[f])) if len(scores[f])==2 else None,
               'noise_ratio':float(np.mean(scores[f]))/floor if len(scores[f])==2 else None} for f in ('FREE','PEG_ONE_SIDE')]
        detail={'folds':folds,'trial_refs':list(a.trial_refs),'statistic':statistic,'scores':rows,
                'protocol_ref':self.protocol_ref,'scope':PROTOCOL['scope'],'single_formal_look':True}
        cref=self.store.put('COMPARISON',detail)
        self.comparison_cache[cref]=detail
        return {'status':'OK' if valid and statistic is not None else 'AMBIGUOUS','flags':flags,'scores':tuple(rows),
            'comparison_ref':cref,'statistic':statistic,'empirical_tail_probability':p,
            'calibrated_threshold':threshold,'null_calibration_ref':self.gate_ref if valid else None,
            'null_replicates':n,'calibrated_support':support,'fit_jobs_charged':count}

    def _inspect_identifiability(self, a):
        f=self.model(a.fitted_model_ref)
        if f['role']!='FITTED' or f['training_refs']!=list(a.trial_refs):
            raise AccessDenied('identifiability requires matching exploration fit')
        self._trials(a.trial_refs)
        info=f['fit'].get('identifiability',{})
        sv=info.get('scaled_singular_values',f['fit'].get('jacobian_singular_values',[]))
        rank=info.get('numerical_rank')
        if rank is None and f['family']=='FREE' and sv:
            rank=sum(x>max(sv)*1e-5 for x in sv)
        local=bool(info.get('locally_identifiable',rank==3))
        return {'status':'OK' if local else 'AMBIGUOUS','flags':() if local else ('RANK_DEFICIENT',),
            'scaled_singular_values':tuple(sv),'numerical_rank':rank,'locally_identifiable':local,
            'near_bound':info.get('near_bound'),'uncertainty_ref':self.store.put('UNCERTAINTY',info),
            'globally_identified':False}

    def _score_candidate_experiment(self, a):
        if a.feasibility_protocol_ref!=self.protocol_ref:
            raise AccessDenied('unapproved feasibility protocol')
        c=self.candidates.get(a.candidate.experiment_ref)
        if c is None or c!=a.candidate:
            raise AccessDenied('experiment is not allowlisted')
        action=c.action
        base={'experiment_ref':c.experiment_ref,'expected_information_gain_nat':None}
        if action.kind in ('CAMERA_CALIBRATION','STATIONARY_REFERENCE'):
            if action.kind=='CAMERA_CALIBRATION' and action.reference_ref!=self.checks_ref:
                raise AccessDenied('unapproved reference check')
            missing=(self.checks['reference_reprojection_rms_px'] is None if action.kind=='CAMERA_CALIBRATION'
                     else self.checks['stationary_sd_px'] is None)
            bad=(self.checks['reference_reprojection_rms_px'] or 0)>1. if action.kind=='CAMERA_CALIBRATION' else (self.checks['stationary_sd_px'] or 0)>3.
            return {**base,'status':'OK','flags':(),'feasible':True,'predictive_discrimination_sigma':None,
                'ensemble_spread_sigma':None,'diagnostic_priority':100 if missing or bad else 0,
                'valid_ensemble_members':0,'method':'REFERENCE_CHECK_PRIORITY'}
        if len(a.fitted_model_refs)!=2:
            return {**base,'status':'AMBIGUOUS','flags':('NO_MODEL_UNCERTAINTY',),'feasible':None,
                'predictive_discrimination_sigma':None,'ensemble_spread_sigma':None,'diagnostic_priority':0,
                'valid_ensemble_members':0,'method':'UNAVAILABLE'}
        models=[self.model(r) for r in a.fitted_model_refs]
        if {m['family'] for m in models}!={'FREE','PEG_ONE_SIDE'}:
            raise AccessDenied('matched candidate families required')
        source=self.trial(models[0]['training_refs'][0])
        if isinstance(source,VideoTrial):
            return {**base,'status':'AMBIGUOUS','flags':('OUTSIDE_PROTOCOL',),'feasible':None,
                'predictive_discrimination_sigma':None,'ensemble_spread_sigma':None,'diagnostic_priority':0,
                'valid_ensemble_members':0,'method':'UNAVAILABLE'}
        if action.kind=='REPEAT':
            source=self.trial(action.source_trial_ref)
            exp=source.experiment
        else:
            exp=Experiment(action.release_angle_rad,action.duration_s,20.)
        t=exp.times()
        dummy=Trial('planning',exp,Observation(t,np.zeros((len(t),2)),np.ones(len(t),bool),
                    covariance_px2=source.observation.covariance_px2),source.projection)
        floor=_floor([source])
        free=next(m for m in models if m['family']=='FREE')
        peg=next(m for m in models if m['family']=='PEG_ONE_SIDE')
        ensemble=[peg['params']]
        for s in peg['fit']['starts']:
            if s.get('success') and s.get('cost') is not None and s['cost']<=peg['fit']['robust_cost']+2.3:
                if s['fitted_params'] not in ensemble:
                    ensemble.append(s['fitted_params'])
        values=[]; valid=0; failed=False
        try:
            y0=predict(parameters(free['params']),dummy); valid=1
            for p in ensemble[:8]:
                try:
                    y=predict(parameters(p),dummy)
                    values.append(float(np.sqrt(np.mean(np.sum((y-y0)**2,axis=1))/floor)))
                    valid+=1
                except (ValueError,RuntimeError,FloatingPointError):
                    failed=True
        except (ValueError,RuntimeError,FloatingPointError):
            failed=True
        if failed or not values:
            return {**base,'status':'AMBIGUOUS','flags':('INFEASIBLE',),'feasible':False,
                'predictive_discrimination_sigma':None,'ensemble_spread_sigma':None,'diagnostic_priority':0,
                'valid_ensemble_members':valid,'method':'UNAVAILABLE'}
        return {**base,'status':'OK','flags':(),'feasible':True,
            'predictive_discrimination_sigma':float(np.quantile(values,.75)),
            'ensemble_spread_sigma':float((np.quantile(values,.75)-np.quantile(values,.25))/2),
            'diagnostic_priority':0,'valid_ensemble_members':valid,'method':'ENSEMBLE_Q75_PREDICTIVE_SEPARATION'}


def json_bytes(value):
    return canonical(value)
