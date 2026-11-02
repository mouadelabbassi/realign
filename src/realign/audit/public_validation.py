"""Public v1 geometry/reveal verification. No vault, file IO, fitting or evaluation.

The canonical commitment encoding is unchanged from Task06.
"""
import hmac,re
from typing import Annotated,Literal
from pydantic import BaseModel,ConfigDict,Field,FiniteFloat,model_validator
from .chain import canonical,digest

class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


class GeometryMeasurements(Closed):
    """Independent geometry, not a generator parameter dump or mode/event labels."""
    schema_version: Literal["1.0"] = "1.0"
    length_unit: Literal["m"] = "m"
    coordinate_frame: Literal["pivot_relative_x_right_y_up"] = "pivot_relative_x_right_y_up"
    string_length_m: Annotated[FiniteFloat, Field(gt=0)]
    string_length_sigma_m: Annotated[FiniteFloat, Field(ge=0)]
    peg_xy_m: tuple[FiniteFloat, FiniteFloat] | None = None
    peg_sigma_m: tuple[Annotated[FiniteFloat, Field(ge=0)], Annotated[FiniteFloat, Field(ge=0)]] | None = None
    method: Literal["SYNTHETIC_FIXTURE", "INDEPENDENT_PHYSICAL_MEASUREMENT"]
    reference_ids: Annotated[tuple[str, ...], Field(min_length=1, max_length=16)]

    @model_validator(mode="after")
    def paired(self):
        if (self.peg_xy_m is None) != (self.peg_sigma_m is None):
            raise ValueError("peg coordinates and their uncertainty must be supplied together")
        if any(not x or len(x)>120 for x in self.reference_ids):
            raise ValueError("bounded independent reference identities required")
        if self.method == "INDEPENDENT_PHYSICAL_MEASUREMENT" and (
                self.string_length_sigma_m <= 0 or self.peg_sigma_m is not None and min(self.peg_sigma_m) <= 0):
            raise ValueError("physical geometry requires positive measurement uncertainty")
        return self


def _commitment(challenge_id, domain, dataset, protocol, geometry, nonce):
    return digest({"schema_version":"1.0","challenge_id":challenge_id,"domain":domain,
                   "heldout_dataset_sha256":dataset,"protocol":protocol,"geometry":geometry,"nonce_hex":nonce})


def verify_reveal(commitment, reveal):
    """Verify an already released reveal. It never reads any private vault file."""
    try:
        nonce=reveal["nonce_hex"]
        if (not isinstance(nonce,str) or not re.fullmatch(r"[0-9a-f]{64,256}",nonce) or len(nonce)%2 or
                len(bytes.fromhex(nonce))<32): return False
        geometry=GeometryMeasurements.model_validate_json(canonical(reveal["geometry"])).model_dump(mode="json")
        if reveal["challenge_id"]!=commitment["challenge_id"] or reveal["domain"]!=commitment["domain"]: return False
        expected=_commitment(commitment["challenge_id"],commitment["domain"],commitment["heldout_dataset_sha256"],
                             commitment["protocol"],geometry,nonce)
        return hmac.compare_digest(expected,commitment["commitment_sha256"])
    except (KeyError,TypeError,ValueError):
        return False


