"""Verified ideal hybrid peg pendulum.

Convention:
  Frame: x right, y up, gravity downward. Angles from downward vertical.
  Peg: P=(r*sin(phi), -r*cos(phi)) measured relative to the original pivot.
  'contact_side' chooses the half-plane in which the taut string is wrapped.
  -1: contact when angle is LESS than phi (traditional left-side wrap).
  +1: contact when angle is GREATER than phi (mirror image).
  Initial release MUST be on the free side of the peg, and not on the guard.

Within each mode the pivot and length are CONSTANT; a state-dependent
length would require a different Lagrangian. Do not generalize silently.

The ideal point peg introduces NO velocity loss and has no contact impulse.
At the straight-string guard, Cartesian velocity is continuous, while
angular rate rescales by the two radii. Kappa factors <= 1 provide an
explicitly non-ideal empirical option, not the ideal default.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import math
import numpy as np
from numpy.typing import NDArray
from scipy.integrate import solve_ivp


@dataclass(frozen=True)
class PegParams:
    distance_m: float
    angle_rad: float = 0.0
    contact_side: int = -1
    kappa_in: float = 1.0
    kappa_out: float = 1.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.distance_m) or self.distance_m <= 0:
            raise ValueError("peg distance must be positive")
        if not math.isfinite(self.angle_rad) or abs(self.angle_rad) >= math.pi / 2:
            raise ValueError("peg angle must be within (-pi/2, pi/2)")
        if self.contact_side not in (-1, 1):
            raise ValueError("contact_side must be -1 or 1")
        if not (0 < self.kappa_in <= 1 and 0 < self.kappa_out <= 1):
            raise ValueError("kappa must be in (0,1]; defaults are ideal lossless 1")


@dataclass(frozen=True)
class PendulumParams:
    length_m: float
    g: float = 9.80665
    gamma_per_s: float = 0.0
    quadratic_drag_per_m: float = 0.0
    peg: Optional[PegParams] = None

    def __post_init__(self) -> None:
        vals = (self.length_m, self.g, self.gamma_per_s, self.quadratic_drag_per_m)
        if not all(math.isfinite(v) for v in vals):
            raise ValueError("all physical parameters must be finite")
        if self.length_m <= 0 or self.g <= 0 or self.gamma_per_s < 0 or self.quadratic_drag_per_m < 0:
            raise ValueError("invalid length/gravity/drag")
        if self.peg and self.peg.distance_m >= self.length_m:
            raise ValueError("peg must be closer than the bob")
        if self.peg and self.length_m - self.peg.distance_m < 0.05 * self.length_m:
            raise ValueError("contact radius too short for this model")


@dataclass(frozen=True)
class SimEvent:
    time_s: float
    from_mode: str
    to_mode: str
    xy_pre_m: tuple[float, float]
    xy_post_m: tuple[float, float]
    speed_pre_mps: float
    speed_post_mps: float


@dataclass(frozen=True)
class SimResult:
    t_s: NDArray[np.float64]
    mode: NDArray[np.str_]
    q_rad: NDArray[np.float64]
    qd_rad_per_s: NDArray[np.float64]
    xy_m: NDArray[np.float64]
    events: tuple[SimEvent, ...]
    flags: tuple[str, ...]


def _geometry(p: PendulumParams, mode: str):
    if mode == "free" or p.peg is None:
        return np.zeros(2, dtype=float), p.length_m
    peg = p.peg
    pivot = np.array([peg.distance_m * math.sin(peg.angle_rad),
                      -peg.distance_m * math.cos(peg.angle_rad)], dtype=float)
    return pivot, p.length_m - peg.distance_m


def _xy(p: PendulumParams, mode: str, q: float) -> NDArray[np.float64]:
    pivot, ell = _geometry(p, mode)
    return pivot + ell * np.array([math.sin(q), -math.cos(q)], dtype=float)


def _speed(p: PendulumParams, mode: str, qd: float) -> float:
    return float(_geometry(p, mode)[1] * abs(qd))


def _rhs(p: PendulumParams, mode: str, x: NDArray[np.float64]) -> NDArray[np.float64]:
    ell = _geometry(p, mode)[1]
    q, qd = x
    return np.array([qd, -(p.g/ell)*math.sin(q) - p.gamma_per_s*qd
                     - p.quadratic_drag_per_m*ell*qd*abs(qd)], dtype=float)


def _tension_over_mass(p: PendulumParams, mode: str, x: NDArray[np.float64]) -> float:
    ell = _geometry(p, mode)[1]
    q, qd = x
    # Tangential drag has zero radial component in this approximation.
    return float(ell*qd*qd + p.g*math.cos(q))


def simulate(p: PendulumParams, theta0: float, omega0: float,
             t_eval: NDArray[np.float64], *, rtol: float = 1e-10,
             atol: float = 1e-12, max_events: int = 200) -> SimResult:
    """Integrate with exact terminal events, explicit modes, and speed-preserving resets.

    Returns a sample of continuous Cartesian positions and event metadata.
    Raises ValueError when the experiment is outside the model's validity
    envelope (initial contact side, slack string, invalid time grid).
    """
    t = np.asarray(t_eval, dtype=float)
    if t.ndim != 1 or len(t) < 2 or t[0] != 0 or not np.all(np.isfinite(t)) or np.any(np.diff(t) <= 0):
        raise ValueError("t_eval must be finite, strictly increasing and begin at 0")
    if not (math.isfinite(theta0) and math.isfinite(omega0)) or abs(theta0) >= math.pi:
        raise ValueError("invalid initial state")
    if max_events < 1:
        raise ValueError("max_events must be >= 1")
    if p.peg:
        # We support a known free-side release, not an ambiguous state already wrapped.
        if p.peg.contact_side * (theta0 - p.peg.angle_rad) >= -1e-9:
            raise ValueError("initial release must be strictly on the free side of the peg")
    mode = "free"
    x = np.array([theta0, omega0], dtype=float)
    if _tension_over_mass(p, mode, x) <= 0:
        raise ValueError("SLACK_VIOLATION: string not taut initially")

    cursor = 0.0
    last = float(t[-1]); segments = []; events = []
    flags: list[str] = []
    for iteration in range(max_events + 1):
        if cursor >= last:
            break
        target = "contact" if mode == "free" else "free"
        peg = p.peg
        event_functions = []
        if peg is not None:
            def crossing(time, state, *, phi=peg.angle_rad):
                return float(state[0] - phi)
            crossing.terminal = True
            crossing.direction = peg.contact_side if mode == "free" else -peg.contact_side
            event_functions.append(crossing)

        def slack(time, state, *, this_mode=mode):
            return _tension_over_mass(p, this_mode, state)
        slack.terminal = True
        slack.direction = -1
        event_functions.append(slack)
        sol = solve_ivp(lambda time, state: _rhs(p, mode, state), (cursor, last), x,
                        method="DOP853", dense_output=True, rtol=rtol, atol=atol,
                        events=event_functions)
        if not sol.success:
            raise RuntimeError(f"ODE solver failed: {sol.message}")
        end = float(sol.t[-1]); segments.append((cursor, end, mode, sol.sol))
        if sol.status == 0:
            cursor = last
            break
        # Since a guard can be at the initial time after reset, its derivative
        # direction prevents immediate re-firing in the next mode.
        if peg is not None and len(sol.t_events[0]) > 0:
            event_time = float(sol.t_events[0][0])
            state_before = np.asarray(sol.y_events[0][0], dtype=float)
            if event_time <= cursor + 1e-13:
                raise RuntimeError("ZERO_DWELL_EVENT: bad guard/chattering")
            pre_pos = _xy(p, mode, float(state_before[0]))
            pre_speed = _speed(p, mode, float(state_before[1]))
            ell_from = _geometry(p, mode)[1]
            ell_to = _geometry(p, target)[1]
            kappa = peg.kappa_in if mode == "free" else peg.kappa_out
            # At contact, both angular positions are phi. Tangent directions
            # coincide and Cartesian speed is preserved for kappa == 1.
            x = np.array([peg.angle_rad, kappa*ell_from/ell_to*state_before[1]], dtype=float)
            post_pos = _xy(p, target, float(x[0]))
            if np.linalg.norm(post_pos - pre_pos) > 1e-8:
                raise RuntimeError("GEOMETRY_DISCONTINUITY: invalid reset")
            events.append(SimEvent(event_time, mode, target, tuple(pre_pos), tuple(post_pos),
                                   pre_speed, _speed(p, target, float(x[1]))))
            mode = target
            cursor = event_time
            continue
        flags.append("SLACK_VIOLATION")
        raise ValueError(f"SLACK_VIOLATION at t={end:.8g} s; add a slack mode or choose a safer experiment")
    else:
        raise RuntimeError(f"MAX_EVENTS_EXCEEDED ({max_events})")

    modes = np.empty(t.shape, dtype="<U8")
    q = np.full_like(t, np.nan)
    qd = np.full_like(t, np.nan)
    xy = np.full((t.size, 2), np.nan)
    for i, (start, end, mode, interpolant) in enumerate(segments):
        # Assign the exact event time to the post-reset mode, except for final
        # endpoint. Floating samples away from guard use the segment as normal.
        final = i == len(segments) - 1
        indices = np.where((t >= start - 1e-14) & ((t < end - 1e-14) if not final else (t <= end + 1e-14)))[0]
        if not len(indices):
            continue
        sample = interpolant(t[indices])
        q[indices] = sample[0]; qd[indices] = sample[1]
        modes[indices] = mode
        pivot, ell = _geometry(p, mode)
        xy[indices] = pivot + ell * np.stack([np.sin(sample[0]), -np.cos(sample[0])], axis=1)
    if not np.all(np.isfinite(xy)):
        raise RuntimeError("UNASSIGNED_SAMPLES: integration segments do not cover t_eval")
    return SimResult(t, modes, q, qd, xy, tuple(events), tuple(flags))


def energy_per_mass(p: PendulumParams, result: SimResult) -> NDArray[np.float64]:
    lengths = np.where(result.mode == "free", p.length_m,
                       p.length_m - p.peg.distance_m if p.peg else p.length_m)
    return 0.5 * (lengths * result.qd_rad_per_s) ** 2 + p.g * result.xy_m[:, 1]
