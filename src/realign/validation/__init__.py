"""Independent, one-shot post-freeze validation; never an investigator tool.

The trusted application creates a challenge before starting a new investigation.
Only its public commitment/start receipt may enter the investigation. Private
heldouts, geometry and reveal nonce remain outside the isolated tool runtime.
"""
from .contracts import GeometryMeasurements, EvaluationProtocol, RealQualification, FrozenModel
from .vault import ValidationVault, ValidationError, verify_reveal

__all__ = ["GeometryMeasurements", "EvaluationProtocol", "RealQualification", "FrozenModel",
           "ValidationVault", "ValidationError", "verify_reveal"]
