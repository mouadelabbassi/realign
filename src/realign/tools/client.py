"""Trusted host-side capability provisioning. Model adapters never receive this object."""
from dataclasses import asdict
from realign.audit.chain import digest
from realign.contracts.investigation import Budget, ExperimentCandidate, Release, Repeat, Stationary, CameraCheck
from .resources import encode_trial


def candidate(action):
    return ExperimentCandidate(experiment_ref=digest({'kind':'EXPERIMENT','action':action.model_dump(mode='json')}),action=action)


class ScientificSession:
    def __init__(self, worker, trials, nominal, checks, *, budget=None, gate=None, release_angles=(.65,)):
        self.worker=worker; self.budget=budget or Budget()
        self.release_angles=tuple(release_angles)
        initial=worker.request({'command':'reset','records':[encode_trial(t) for t in trials],
            'nominal':asdict(nominal),'budget':self.budget.model_dump(mode='json'),'checks':checks,'gate':gate})
        self.nominal_model_ref=initial['nominal_model_ref']
        self.trial_refs=initial['trial_refs']; self.budget_ref=initial['budget_ref']
        self.protocol_ref=initial['protocol_ref']; self.checks_ref=initial['checks_ref']
        self.results=[]; self._round_clear()
        self._candidates()

    def _round_clear(self):
        self.fits={}; self.comparison=None; self.identifiability=None; self.discrepancy=None; self.scores={}

    def _candidates(self):
        actions=[Release(release_angle_rad=float(a)) for a in self.release_angles]
        actions += [Repeat(source_trial_ref=self.trial_refs[0]),Stationary(),CameraCheck(reference_ref=self.checks_ref)]
        self.candidates=[candidate(a).model_dump(mode='json') for a in actions]
        self.worker.request({'command':'candidates','candidates':self.candidates})

    def call(self, name, arguments):
        result=self.worker.call(name,arguments)
        self.results.append({'name':name,'arguments':arguments,'result':result})
        if result.get('code'):
            return result
        if name=='fit_candidate_model':
            if list(arguments['trial_refs'])==self.trial_refs:
                self.fits[arguments['candidate']]=result
                # A later model fit cannot inherit an earlier comparison/rank.
                self.comparison=None; self.identifiability=None
        elif name=='compare_candidate_models':
            self.comparison=result
        elif name=='inspect_identifiability':
            if (list(arguments['trial_refs'])==self.trial_refs and
                arguments['fitted_model_ref']==self.fits.get('PEG_ONE_SIDE',{}).get('fitted_model_ref')):
                self.identifiability=result
        elif name=='inspect_discrepancy':
            if list(arguments['trial_refs'])==self.trial_refs and arguments['model_ref']==self.nominal_model_ref:
                self.discrepancy=result
        elif name=='score_candidate_experiment':
            self.scores[result['experiment_ref']]=result
        return result

    def admit(self, trials=(), checks=None):
        result=self.worker.request({'command':'admit','records':[encode_trial(t) for t in trials],'checks':checks})
        self.trial_refs=result['trial_refs']; self.checks_ref=result['checks_ref']
        self._round_clear(); self._candidates()

    def fit(self, family):
        return self.call('fit_candidate_model',{'trial_refs':list(self.trial_refs),'candidate':family,
            'nominal_model_ref':self.nominal_model_ref,'budget_ref':self.budget_ref})

    def compare(self):
        return self.call('compare_candidate_models',{'trial_refs':list(self.trial_refs),
            'fitted_model_refs':[self.fits[f]['fitted_model_ref'] for f in ('FREE','PEG_ONE_SIDE')],
            'protocol_ref':self.protocol_ref})

    def audit(self):
        return self.worker.request({'command':'audit'})

    def freeze(self, model_ref=None):
        return self.worker.request({'command':'freeze','model_ref':model_ref})
