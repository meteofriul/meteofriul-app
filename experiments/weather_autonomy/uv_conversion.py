"""Offline CAMS UV conversion; no retrieval or production integration.

Only accepts biologically effective irradiance (W/m²), not accumulated
energy, broadband solar radiation, or clear-sky values relabelled all-sky.
Reference: ECMWF CAMS global forecast data documentation, UV index.
"""
import math


def uv_index(irradiance, *, unit):
    if unit != "W m-2":
        raise ValueError("Expected biologically effective irradiance in W m-2")
    if irradiance is None:
        return None
    if isinstance(irradiance, bool) or not isinstance(irradiance, (int, float)):
        raise ValueError("Expected a numeric irradiance")
    if not math.isfinite(irradiance) or irradiance < 0:
        raise ValueError("Expected finite nonnegative irradiance")
    result = irradiance * 40
    if not math.isfinite(result):
        raise ValueError("UV index overflow")
    return result
