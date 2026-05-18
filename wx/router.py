"""Decide which weather API to use for a given coordinate.

NWS covers: CONUS, Alaska, Hawaii, Puerto Rico, US Virgin Islands, Guam,
American Samoa, Northern Marianas.

Brightsky (DWD) covers Europe well. The DWD MOSMIX model is global, but
station observations cluster in central Europe. We route Europe + nearby
to DWD and let met.no catch everything else.
"""
from __future__ import annotations
from typing import Literal

Provider = Literal["nws", "dwd", "metno"]


def _in_box(lat: float, lon: float, *, lat_min, lat_max, lon_min, lon_max) -> bool:
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def is_us(lat: float, lon: float) -> bool:
    """Rough bounding boxes for NWS coverage."""
    # CONUS
    if _in_box(lat, lon, lat_min=24.5, lat_max=49.5, lon_min=-125.0, lon_max=-66.5):
        return True
    # Alaska (including Aleutians wrapping date line)
    if _in_box(lat, lon, lat_min=51.0, lat_max=71.5, lon_min=-179.5, lon_max=-129.5):
        return True
    if _in_box(lat, lon, lat_min=51.0, lat_max=55.0, lon_min=172.0, lon_max=180.0):
        return True
    # Hawaii
    if _in_box(lat, lon, lat_min=18.5, lat_max=22.5, lon_min=-160.5, lon_max=-154.5):
        return True
    # Puerto Rico + US Virgin Islands
    if _in_box(lat, lon, lat_min=17.6, lat_max=18.6, lon_min=-67.5, lon_max=-64.5):
        return True
    # Guam + Northern Marianas
    if _in_box(lat, lon, lat_min=13.0, lat_max=20.7, lon_min=144.5, lon_max=146.2):
        return True
    # American Samoa
    if _in_box(lat, lon, lat_min=-14.6, lat_max=-14.1, lon_min=-171.0, lon_max=-169.4):
        return True
    return False


def is_europe(lat: float, lon: float) -> bool:
    """Rough bounding box covering Europe (incl. UK, Iceland, west Russia).

    Intentionally generous; this is the secondary fallback before met.no.
    """
    # Mainland Europe + UK + Iceland + west Russia
    if _in_box(lat, lon, lat_min=34.0, lat_max=72.0, lon_min=-25.0, lon_max=45.0):
        return True
    # Canary Islands (Spanish territory, off Morocco coast)
    if _in_box(lat, lon, lat_min=27.5, lat_max=29.5, lon_min=-18.2, lon_max=-13.4):
        return True
    return False


def pick(lat: float, lon: float) -> Provider:
    if is_us(lat, lon):
        return "nws"
    if is_europe(lat, lon):
        return "dwd"
    return "metno"
