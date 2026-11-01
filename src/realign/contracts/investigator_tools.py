"""Versioned, closed handoff schemas only. No tool dispatch or agent loop.

References are opaque content hashes resolved by a future exploration-only
allowlist. Schema validation is NOT a storage/permission security boundary.
"""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

Ref = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
Refs = Annotated[tuple[Ref, ...], Field(min_length=1, max_length=24)]
Positive = Annotated[FiniteFloat, Field(ge=0)]
Flag = Literal['LOW_EXCITATION', 'RANK_DEFICIENT', 'BOUND_ACTIVE', 'SOLVER_FAILURE',
               'QUALITY_FAILURE', 'EQUIVALENT', 'UNCALIBRATED', 'INSUFFICIENT_DATA']


class Closed(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False)
    schema_version: Literal['1.0'] = '1.0'


class ExplorationInput(Closed):
    trial_refs: Refs
    zone: Literal['exploration'] = 'exploration'


class EvidenceOutput(Closed):
    evidence_ref: Ref
    status: Literal['OK', 'FAILED', 'AMBIGUOUS', 'NOT_IMPLEMENTED']
    flags: tuple[Flag, ...] = ()


class InspectDiscrepancyInput(ExplorationInput):
    model_ref: Ref


class InspectDiscrepancyOutput(EvidenceOutput):
    valid_samples: Annotated[int, Field(ge=0)]
    trajectory_rmse_px: Positive | None = None
    innovation_mean_square: Positive | None = None
    lag1_x: Annotated[FiniteFloat, Field(ge=-1, le=1)] | None = None


class FitCandidateModelInput(ExplorationInput):
    candidate: Literal['FREE', 'PEG_ONE_SIDE']
    nominal_model_ref: Ref
    budget_ref: Ref
    wrap_side: Literal[-1, 1] = -1


class FitCandidateModelOutput(EvidenceOutput):
    fitted_model_ref: Ref | None = None
    robust_cost: Positive | None = None
    attempted_starts: Annotated[int, Field(ge=0, le=32)]
    converged_starts: Annotated[int, Field(ge=0, le=32)]
    residual_calls: Annotated[int, Field(ge=0)]


class CompareCandidateModelsInput(ExplorationInput):
    fitted_model_refs: Annotated[tuple[Ref, ...], Field(min_length=2, max_length=8)]
    protocol_ref: Ref


class CandidateScore(Closed):
    model_ref: Ref
    trial_cv_mse_px2: Positive | None = None
    geometric_radial_mse_m2: Positive | None = None


class CompareCandidateModelsOutput(EvidenceOutput):
    scores: Annotated[tuple[CandidateScore, ...], Field(max_length=8)]
    null_calibration_ref: Ref | None = None
    calibrated_support: Literal['NOT_ASSESSED', 'INDISTINGUISHABLE', 'PREDICTIVE_DIFFERENCE']


class InspectIdentifiabilityInput(ExplorationInput):
    fitted_model_ref: Ref


class InspectIdentifiabilityOutput(EvidenceOutput):
    scaled_singular_values: Annotated[tuple[Positive, ...], Field(max_length=8)]
    numerical_rank: Annotated[int, Field(ge=0, le=8)] | None = None
    locally_identifiable: bool
    globally_identified: Literal[False] = False
    uncertainty_ref: Ref | None = None


class CandidateExperiment(Closed):
    experiment_ref: Ref
    release_angle_rad: Annotated[FiniteFloat, Field(gt=-1.3, lt=1.3)]
    duration_s: Annotated[FiniteFloat, Field(gt=0, le=60)]
    repeats: Annotated[int, Field(ge=1, le=10)]


class ScoreCandidateExperimentInput(Closed):
    fitted_model_refs: Annotated[tuple[Ref, ...], Field(min_length=2, max_length=8)]
    candidate: CandidateExperiment
    feasibility_protocol_ref: Ref


class ScoreCandidateExperimentOutput(EvidenceOutput):
    experiment_ref: Ref
    feasible: bool | None = None
    expected_information_gain_nat: Positive | None = None
    prediction_separation_sigma: Positive | None = None
    numerical_uncertainty: Positive | None = None


SCHEMAS = {
    'inspect_discrepancy': (InspectDiscrepancyInput, InspectDiscrepancyOutput),
    'fit_candidate_model': (FitCandidateModelInput, FitCandidateModelOutput),
    'compare_candidate_models': (CompareCandidateModelsInput, CompareCandidateModelsOutput),
    'inspect_identifiability': (InspectIdentifiabilityInput, InspectIdentifiabilityOutput),
    'score_candidate_experiment': (ScoreCandidateExperimentInput, ScoreCandidateExperimentOutput),
}


def tool_json_schemas():
    return {name: {'input': i.model_json_schema(), 'output': o.model_json_schema(),
                   'implementation_status': 'SCHEMA_ONLY'} for name, (i, o) in SCHEMAS.items()}
