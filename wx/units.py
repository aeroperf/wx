"""Unit conversions.

All adapters normalize to a canonical internal representation:
  - temperature: Celsius
  - wind speed: m/s
  - pressure: hPa
  - precipitation: mm
  - visibility: meters

Then this module converts to user preferences.
"""
from __future__ import annotations


def c_to(value: float | None, unit: str) -> float | None:
    if value is None:
        return None
    u = unit.upper()
    if u == "C":
        return value
    if u == "F":
        return value * 9 / 5 + 32
    if u == "K":
        return value + 273.15
    return value


def mps_to(value: float | None, unit: str) -> float | None:
    if value is None:
        return None
    u = unit.lower()
    if u in ("mps", "m/s"):
        return value
    if u == "kt" or u == "knots" or u == "knot":
        return value * 1.943844
    if u == "mph":
        return value * 2.236936
    if u == "kph" or u == "km/h" or u == "kmh":
        return value * 3.6
    return value


def hpa_to(value: float | None, unit: str) -> float | None:
    if value is None:
        return None
    u = unit.lower()
    if u in ("hpa", "mb", "mbar"):
        return value
    if u == "inhg":
        return value * 0.02953
    if u == "mmhg":
        return value * 0.750062
    return value


def mm_to(value: float | None, unit: str) -> float | None:
    if value is None:
        return None
    u = unit.lower()
    if u == "mm":
        return value
    if u == "in" or u == "inch" or u == "inches":
        return value / 25.4
    return value


def meters_to(value: float | None, unit: str) -> float | None:
    if value is None:
        return None
    u = unit.lower()
    if u == "m":
        return value
    if u == "km":
        return value / 1000
    if u in ("mi", "miles"):
        return value / 1609.344
    if u in ("ft", "feet"):
        return value * 3.28084
    return value


# Display suffixes (keys are lowercase; look up via .lower())
TEMP_SUFFIX = {"c": "°C", "f": "°F", "k": "K"}
WIND_SUFFIX = {"kt": "kt", "mph": "mph", "kph": "km/h", "mps": "m/s"}
PRESSURE_SUFFIX = {"inhg": "inHg", "hpa": "hPa", "mb": "mb", "mmhg": "mmHg"}
PRECIP_SUFFIX = {"in": "in", "mm": "mm"}
VIS_SUFFIX = {"mi": "mi", "km": "km", "m": "m", "ft": "ft"}


def fmt(value: float | None, suffix: str, decimals: int = 0) -> str:
    if value is None:
        return "—"
    if decimals == 0:
        return f"{value:.0f} {suffix}"
    return f"{value:{'.' + str(decimals) + 'f'}} {suffix}"
