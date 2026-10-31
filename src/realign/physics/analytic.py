"""Analytic oracles for an ideal, planar, taut, frictionless pendulum.

ellipk takes parameter m=k**2, NOT the elliptic modulus k.
The classical vertical peg formula requires free arc on one side and
contact arc on the other, and release from rest on the free side.
"""
from __future__ import annotations
import math
from scipy.special import ellipk


def period_small(length_m: float, g: float = 9.80665) -> float:
    if length_m <= 0 or g <= 0:
        raise ValueError("length and gravity must be positive")
    return 2 * math.pi * math.sqrt(length_m / g)


def period_exact(length_m: float, amplitude_rad: float, g: float = 9.80665) -> float:
    if length_m <= 0 or g <= 0 or abs(amplitude_rad) >= math.pi:
        raise ValueError("invalid pendulum parameters")
    m = math.sin(amplitude_rad / 2.0) ** 2
    return 4.0 * math.sqrt(length_m / g) * float(ellipk(m))


def vertical_peg_period(length_m: float, peg_distance_m: float, amplitude_rad: float,
                        g: float = 9.80665) -> float:
    """Ideal full period: one free half-cycle and one contact half-cycle.

    The shorter pendulum's turning angle follows energy conservation,
    and this function is only valid for a taut, non-slack swing.
    """
    if not (0 < peg_distance_m < length_m):
        raise ValueError("peg must be strictly between pivot and bob")
    short = length_m - peg_distance_m
    cos_turn = (length_m * math.cos(amplitude_rad) - peg_distance_m) / short
    if not (-1.0 <= cos_turn <= 1.0):
        raise ValueError("no admissible contact-mode turning point")
    amplitude_short = math.acos(cos_turn)
    if amplitude_short >= math.pi / 2:
        raise ValueError("ideal taut model invalid at this amplitude (string may slacken)")
    return 0.5 * (period_exact(length_m, amplitude_rad, g) + period_exact(short, amplitude_short, g))
