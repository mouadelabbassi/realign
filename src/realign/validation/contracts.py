"""Closed G5 data contracts. Lengths are metres, time seconds, pixels explicit."""
from dataclasses import dataclass
import json
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator
from realign.audit.chain import digest


from realign.audit.public_validation import Closed,GeometryMeasurements


class EvaluationProtocol(Closed):
    """Fixed before investigation; thresholds are acceptance tolerances, not p-values."""
    schema_version: Literal["1.0"] = "1.0"
    max_trajectory_rmse_px: Annotated[FiniteFloat, Field(gt=0)] = 2.
    minimum_trials: Annotated[int, Field(ge=1, le=32)] = 2
    minimum_valid_samples_per_trial: Annotated[int, Field(ge=2, le=256)] = 12
    maximum_missing_fraction: Annotated[FiniteFloat, Field(ge=0, le=1)] = .25
    minimum_release_angle_rad: Annotated[FiniteFloat, Field(ge=0, lt=1.5)] = .3
    length_tolerance_m: Annotated[FiniteFloat, Field(gt=0)] = .01
    peg_position_tolerance_m: Annotated[FiniteFloat, Field(gt=0)] = .01
    negative_control: bool = False


class RealQualification(Closed):
    """Explicit external evidence prerequisites; declarations are not attestations."""
    independent_manual_review_verified: bool = False
    camera_calibration_verified: bool = False
    capture_timing_verified: bool = False
    release_conditions_measured: bool = False
    stationary_noise_measured: bool = False
    independent_geometry_measured: bool = False
    reference_ids: tuple[str, ...] = ()

    def blockers(self):
        fields = ("independent_manual_review_verified", "camera_calibration_verified", "capture_timing_verified",
                  "release_conditions_measured", "stationary_noise_measured", "independent_geometry_measured")
        return [name.upper() for name in fields if not getattr(self, name)] + ([] if self.reference_ids else ["INDEPENDENT_REFERENCE_IDS_REQUIRED"])


@dataclass(frozen=True)
class FrozenModel:
    """Deeply immutable canonical bytes; all dictionary views are independent copies."""
    canonical_payload: bytes

    @property
    def content_sha256(self):
        return digest(json.loads(self.canonical_payload))

    def to_dict(self):
        return json.loads(self.canonical_payload)

    def public_receipt(self):
        value = self.to_dict()
        return {"schema_version": "1.0", "challenge_id": value["challenge_id"],
                "content_sha256": self.content_sha256, "model_ref": value["investigation_freeze"]["model_ref"],
                "investigation_freeze_sha256": value["investigation_freeze"]["freeze_sha256"],
                "commitment_sha256": value["commitment_sha256"], "scope": "IMMUTABLE_PREDEFINED_PREDICTIVE_MODEL"}
