"""Evaluation-only synthetic truth. This is not the future sealed evaluator/vault."""
from dataclasses import dataclass
import numpy as np
from realign.physics import PendulumParams


@dataclass(frozen=True)
class SyntheticTruth:
    params: PendulumParams
    xy_m: np.ndarray
    modes: np.ndarray
    events: tuple
    seed: int

    def __post_init__(self):
        for name in ('xy_m', 'modes'):
            value = np.array(getattr(self, name), copy=True)
            value.flags.writeable = False
            object.__setattr__(self, name, value)
