"""Runtime contracts v1.1. Task 03's schema-only v1.0 remains reproducible."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

Ref = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
Refs = Annotated[tuple[Ref, ...], Field(min_length=1, max_length=8)]
Nonnegative = Annotated[FiniteFloat, Field(ge=0)]
Family = Literal['FREE', 'PEG_ONE_SIDE']
Outcome = Literal['KEEP_UNCHANGED', 'CALIBRATE_PARAMETERS', 'CORRECT_MEASUREMENT', 'REPAIR_STRUCTURE', 'ABSTAIN']
Stage = Literal['OBSERVE', 'HYPOTHESIZE', 'TEST', 'REQUEST_EVIDENCE', 'DECIDE', 'FREEZE']
Flag = Literal['QUALITY_FAILURE', 'MISSING_REFERENCE', 'INSUFFICIENT_DATA', 'UNEXCITED',
               'RANK_DEFICIENT', 'BOUND_ACTIVE', 'SOLVER_FAILURE', 'UNCALIBRATED',
               'OUTSIDE_PROTOCOL', 'NO_MODEL_UNCERTAINTY', 'INFEASIBLE', 'BUDGET',
               'ACCESS_DENIED', 'INVALID_INPUT', 'API_ERROR', 'UNSUPPORTED_PROPOSAL',
               'NO_NEW_EVIDENCE', 'OPERATING_ENVELOPE_ONLY']
CANONICAL_OUTCOME = {'KEEP_UNCHANGED':'KEEP', 'CALIBRATE_PARAMETERS':'RECALIBRATE',
    'CORRECT_MEASUREMENT':'CORRECT_MEASUREMENT', 'REPAIR_STRUCTURE':'REPAIR_STRUCTURE', 'ABSTAIN':'ABSTAIN'}


class Closed(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False, strict=True)
    schema_version: Literal['1.1'] = '1.1'


class Budget(Closed):
    max_rounds: Annotated[int, Field(ge=1, le=2)] = 2
    max_steps: Annotated[int, Field(ge=1, le=40)] = 32
    max_tool_calls: Annotated[int, Field(ge=1, le=32)] = 24
    max_fit_jobs: Annotated[int, Field(ge=1, le=16)] = 10
    max_experiments: Annotated[int, Field(ge=0, le=1)] = 1
    n_starts: Literal[8] = 8
    max_nfev: Annotated[int, Field(ge=1, le=80)] = 40
    max_api_requests: Annotated[int, Field(ge=1, le=32)] = 24
    worker_timeout_s: Annotated[int, Field(ge=1, le=1800)] = 600


class Release(Closed):
    kind: Literal['RELEASE'] = 'RELEASE'
    release_angle_rad: Annotated[FiniteFloat, Field(ge=.1, le=.7)]
    duration_s: Annotated[FiniteFloat, Field(ge=1, le=4)] = 1.6
    repeats: Literal[2] = 2


class Repeat(Closed):
    kind: Literal['REPEAT'] = 'REPEAT'
    source_trial_ref: Ref
    repeats: Annotated[int, Field(ge=2, le=3)] = 2


class Stationary(Closed):
    kind: Literal['STATIONARY_REFERENCE'] = 'STATIONARY_REFERENCE'
    duration_s: Annotated[FiniteFloat, Field(ge=1, le=4)] = 2.


class CameraCheck(Closed):
    kind: Literal['CAMERA_CALIBRATION'] = 'CAMERA_CALIBRATION'
    reference_ref: Ref


ExperimentAction = Annotated[Release | Repeat | Stationary | CameraCheck, Field(discriminator='kind')]


class ExperimentCandidate(Closed):
    experiment_ref: Ref
    action: ExperimentAction


class ExplorationInput(Closed):
    trial_refs: Refs
    zone: Literal['exploration'] = 'exploration'


class InspectInput(ExplorationInput):
    model_ref: Ref


class FitInput(ExplorationInput):
    candidate: Family
    nominal_model_ref: Ref
    budget_ref: Ref
    wrap_side: Literal[-1] = -1


class CompareInput(ExplorationInput):
    fitted_model_refs: Annotated[tuple[Ref, ...], Field(min_length=2, max_length=2)]
    protocol_ref: Ref


class IdentifiabilityInput(ExplorationInput):
    fitted_model_ref: Ref


class ScoreInput(Closed):
    fitted_model_refs: Annotated[tuple[Ref, ...], Field(max_length=2)]
    candidate: ExperimentCandidate
    feasibility_protocol_ref: Ref


class EvidenceOutput(Closed):
    evidence_ref: Ref
    status: Literal['OK', 'FAILED', 'AMBIGUOUS']
    flags: tuple[Flag, ...] = ()


class ToolFailure(Closed):
    evidence_ref: Ref
    status: Literal['FAILED'] = 'FAILED'
    code: Flag


class DiscrepancyOutput(EvidenceOutput):
    valid_samples: Annotated[int, Field(ge=0)]
    trajectory_rmse_px: Nonnegative | None
    innovation_mean_square: Nonnegative | None
    lag1_x: Annotated[FiniteFloat, Field(ge=-1, le=1)] | None
    localization_floor_mse_px2: Nonnegative | None
    missing_fraction: Annotated[FiniteFloat, Field(ge=0, le=1)]
    reference_reprojection_rms_px: Nonnegative | None
    stationary_sd_px: Nonnegative | None
    quality_ok: bool
    predictively_adequate: bool


class FitOutput(EvidenceOutput):
    candidate: Family
    fitted_model_ref: Ref | None
    diagnostics_ref: Ref | None
    robust_cost: Nonnegative | None
    attempted_starts: Annotated[int, Field(ge=0, le=8)]
    converged_starts: Annotated[int, Field(ge=0, le=8)]
    fit_jobs_charged: Annotated[int, Field(ge=0)]
    residual_calls: Annotated[int, Field(ge=0)] | None


class ModelScore(Closed):
    model_ref: Ref
    candidate: Family
    trial_cv_mse_px2: Nonnegative | None
    noise_ratio: Nonnegative | None


class ComparisonOutput(EvidenceOutput):
    scores: tuple[ModelScore, ...]
    comparison_ref: Ref
    statistic: FiniteFloat | None
    empirical_tail_probability: Annotated[FiniteFloat, Field(gt=0, le=1)] | None
    calibrated_threshold: FiniteFloat | None
    null_calibration_ref: Ref | None
    null_replicates: Annotated[int, Field(ge=0)]
    calibrated_support: Literal['NOT_ASSESSED', 'INDISTINGUISHABLE', 'PEG_PREDICTIVE_DIFFERENCE']
    method: Literal['WHOLE_TRIAL_TWO_FOLD_CV'] = 'WHOLE_TRIAL_TWO_FOLD_CV'
    fit_jobs_charged: Annotated[int, Field(ge=0)]


class IdentifiabilityOutput(EvidenceOutput):
    scaled_singular_values: tuple[Nonnegative, ...]
    numerical_rank: Annotated[int, Field(ge=0, le=5)] | None
    locally_identifiable: bool
    near_bound: bool | None
    globally_identified: Literal[False] = False
    uncertainty_ref: Ref | None


class ExperimentScore(EvidenceOutput):
    experiment_ref: Ref
    feasible: bool | None
    predictive_discrimination_sigma: Nonnegative | None
    ensemble_spread_sigma: Nonnegative | None
    diagnostic_priority: Annotated[int, Field(ge=0, le=100)]
    valid_ensemble_members: Annotated[int, Field(ge=0, le=9)]
    expected_information_gain_nat: None = None
    method: Literal['ENSEMBLE_Q75_PREDICTIVE_SEPARATION', 'REFERENCE_CHECK_PRIORITY', 'UNAVAILABLE']


class Hypothesis(Closed):
    family: Literal['NOMINAL_FREE', 'PARAMETER_FREE', 'PEG_ONE_SIDE', 'MEASUREMENT']
    status: Literal['UNRESOLVED', 'PREDICTIVELY_SUPPORTED', 'NOT_SELECTED']
    evidence_refs: tuple[Ref, ...]


class AgentTurn(Closed):
    action: Literal['HYPOTHESIZE', 'REQUEST_EVIDENCE', 'DECIDE']
    hypotheses: Annotated[tuple[Hypothesis, ...], Field(min_length=1, max_length=4)]
    experiment_ref: Ref | None
    outcome: Outcome | None
    model_ref: Ref | None
    evidence_refs: Annotated[tuple[Ref, ...], Field(min_length=1, max_length=24)]
    reasons: tuple[Flag, ...]

    @model_validator(mode='after')
    def coherent(self):
        if self.action == 'HYPOTHESIZE' and any(v is not None for v in (self.experiment_ref, self.outcome, self.model_ref)):
            raise ValueError('hypotheses cannot execute an experiment or decision')
        if self.action == 'REQUEST_EVIDENCE' and (self.experiment_ref is None or self.outcome is not None or self.model_ref is not None):
            raise ValueError('request requires only an approved experiment reference')
        if self.action == 'DECIDE' and (self.outcome is None or self.experiment_ref is not None):
            raise ValueError('decision outcome required')
        return self


class ToolCall(Closed):
    call_id: Annotated[str, Field(pattern=r'^[a-zA-Z0-9_-]{1,128}$')]
    name: Literal['inspect_discrepancy', 'fit_candidate_model', 'compare_candidate_models',
                  'inspect_identifiability', 'score_candidate_experiment']
    arguments: Annotated[str, Field(min_length=2, max_length=16000)]


class AdapterReply(Closed):
    calls: Annotated[tuple[ToolCall, ...], Field(max_length=2)] = ()
    turn: AgentTurn | None = None

    @model_validator(mode='after')
    def one_mode(self):
        if bool(self.calls) == (self.turn is not None):
            raise ValueError('exactly one of tool calls or structured turn required')
        return self


class EvidenceReceipt(Closed):
    kind: Literal['RELEASE','REPEAT','STATIONARY_REFERENCE','CAMERA_CALIBRATION']
    source: Literal['SYNTHETIC_ENVIRONMENT','APPROVED_RECORDING_LIBRARY']
    new_observations: Annotated[int, Field(ge=0, le=3)]


TOOLS = {
    'inspect_discrepancy': (InspectInput, DiscrepancyOutput),
    'fit_candidate_model': (FitInput, FitOutput),
    'compare_candidate_models': (CompareInput, ComparisonOutput),
    'inspect_identifiability': (IdentifiabilityInput, IdentifiabilityOutput),
    'score_candidate_experiment': (ScoreInput, ExperimentScore),
}


def tool_definitions():
    return [{'type':'function','function':{'name':name,
        'description':'Bounded exploration-only numerical evidence; missing metrics remain null.',
        'parameters':inp.model_json_schema()}} for name,(inp,_) in TOOLS.items()]
