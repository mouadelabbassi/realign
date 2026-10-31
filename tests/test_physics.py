import math
import numpy as np
import pytest
from scipy.signal import find_peaks
from realign.physics import (PendulumParams, PegParams, simulate, energy_per_mass,
                             period_exact, period_small, vertical_peg_period)


def trajectory(p, th0=0.65, duration=6.0, n=2001):
    return simulate(p, th0, 0.0, np.linspace(0, duration, n))


def test_small_amplitude_limit():
    assert abs(period_exact(.75, 1e-4) / period_small(.75) - 1) < 1e-9


def test_exact_period_from_numerical_integration():
    p = PendulumParams(.68)
    out = trajectory(p, .78, 10, 5001)
    peak = find_peaks(out.q_rad, distance=300, prominence=.15)[0][0]
    # Sampled peak location is only accurate to the sampling interval.
    assert abs(out.t_s[peak] - period_exact(.68, .78)) < .004


def test_energy_free():
    p = PendulumParams(.62)
    out = trajectory(p, .6, 18, 2401)
    E = energy_per_mass(p, out)
    assert np.max(np.abs(E-E[0])) < 3e-9


def test_peg_events_and_energy():
    p = PendulumParams(.75, peg=PegParams(.20))
    out = trajectory(p, .55, 8, 4001)
    assert len(out.events) >= 4
    assert {e.to_mode for e in out.events} == {"contact", "free"}
    for e in out.events:
        assert np.linalg.norm(np.array(e.xy_pre_m)-e.xy_post_m) < 1e-10
        assert abs(e.speed_pre_mps-e.speed_post_mps) < 1e-9
    E = energy_per_mass(p, out)
    assert np.max(np.abs(E - E[0])) < 1e-8


def test_vertical_peg_period():
    p = PendulumParams(.75, peg=PegParams(.15))
    out = trajectory(p, .45, 12, 12001)
    # Each free->contact event repeats once per full period.
    tt = [e.time_s for e in out.events if e.to_mode == "contact"]
    assert len(tt) >= 3
    np.testing.assert_allclose(np.diff(tt), vertical_peg_period(.75, .15, .45), atol=2e-7)


def test_mirror_symmetry():
    t = np.linspace(0, 5, 1301)
    left = simulate(PendulumParams(.80,peg=PegParams(.2, -.12, -1)), .62, 0, t)
    right = simulate(PendulumParams(.80,peg=PegParams(.2, +.12, +1)), -.62, 0, t)
    np.testing.assert_allclose(left.xy_m[:, 0], -right.xy_m[:, 0], atol=2e-9)
    np.testing.assert_allclose(left.xy_m[:, 1], right.xy_m[:, 1], atol=2e-9)
    assert len(left.events)==len(right.events)


def test_loss_accounting():
    p = PendulumParams(.7, peg=PegParams(.2, kappa_in=.98, kappa_out=1))
    out = trajectory(p, .5, 4, 4001)
    assert len(out.events) >= 1
    E = energy_per_mass(p, out)
    assert E[-1] < E[0]
    assert all(e.speed_post_mps <= e.speed_pre_mps + 1e-10 for e in out.events)


def test_peg_out_of_reach():
    p = PendulumParams(.7,peg=PegParams(.12, -.85))
    out = trajectory(p,.4,8,1001)
    assert len(out.events) == 0
    assert np.all(out.mode=="free")


def test_initial_side_rejected():
    with pytest.raises(ValueError,match="free side"):
        trajectory(PendulumParams(.7,peg=PegParams(.2)), -.2)


def test_slack_is_not_silently_simulated():
    with pytest.raises(ValueError,match="SLACK"):
        trajectory(PendulumParams(.65),2.2)


def test_drag_dissipates_energy():
    p = PendulumParams(.7,gamma_per_s=.12, quadratic_drag_per_m=.03)
    out=trajectory(p, .6, 5, 1501)
    E=energy_per_mass(p,out)
    assert np.max(np.diff(E)) < 1e-9
    assert E[-1] < E[0]


def test_invalid_parameters():
    with pytest.raises(ValueError): PendulumParams(.2,peg=PegParams(.22))
    with pytest.raises(ValueError): PendulumParams(-1)
    with pytest.raises(ValueError): PegParams(.1,kappa_in=1.2)
