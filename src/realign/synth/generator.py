"""Generate a public observation record and a SEPARATE evaluation-only truth record."""
import numpy as np
from realign.contracts import Experiment, NoiseConfig, Observation, PlaneProjection, Trial
from realign.observation.camera import project
from realign.observation.noise import sample_noise
from realign.physics import PendulumParams, simulate
from .truth import SyntheticTruth


def generate_trial(params: PendulumParams, experiment: Experiment, *, seed: int,
                   trial_id: str, noise: NoiseConfig = NoiseConfig(),
                   projection: PlaneProjection = PlaneProjection(), zone='exploration'):
    t = experiment.times()
    out = simulate(params, experiment.release_angle_rad, experiment.release_velocity_rad_per_s, t)
    rng = np.random.default_rng(seed)
    xy_px = project(out.xy_m, projection) + sample_noise(len(t), noise, rng)
    valid = rng.random(len(t)) >= noise.dropout_probability
    observation = Observation(t, xy_px, valid, noise.covariance_px2, noise.ar1_phi)
    public = Trial(trial_id, experiment, observation, projection, zone)
    private = SyntheticTruth(params, out.xy_m, out.mode, out.events, seed)
    return public, private
