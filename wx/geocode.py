"""Location resolution.

Accepts:
  - "lat,lon" (e.g. "39.74,-105.0")  -> parsed directly
  - city name                         -> Open-Meteo geocoding API

Open-Meteo geocoding: https://geocoding-api.open-meteo.com/v1/search
No API key needed.
"""
from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass

import requests

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

_COORD_RE = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$"
)


@dataclass
class Location:
    name: str
    lat: float
    lon: float
    country: str = ""
    admin: str = ""        # state/region
    timezone: str = ""

    @property
    def display(self) -> str:
        parts = [self.name]
        if self.admin:
            parts.append(self.admin)
        if self.country and self.country != self.admin:
            parts.append(self.country)
        return ", ".join(parts)


class GeocodeError(Exception):
    pass


def parse_coords(s: str) -> tuple[float, float] | None:
    m = _COORD_RE.match(s)
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def resolve(query: str, user_agent: str, timeout: int = 15) -> Location:
    """Resolve a query string to a Location.

    Accepts 'lat,lon' or a place name.
    """
    query = query.strip()
    if not query:
        raise GeocodeError("empty location query")

    coords = parse_coords(query)
    if coords is not None:
        lat, lon = coords
        return Location(name=f"{lat:.4f},{lon:.4f}", lat=lat, lon=lon)

    params = {"name": query, "count": 1, "language": "en", "format": "json"}
    url = f"{GEOCODE_URL}?{urllib.parse.urlencode(params)}"
    try:
        r = requests.get(url, headers={"User-Agent": user_agent}, timeout=timeout)
        r.raise_for_status()
    except requests.RequestException as e:
        raise GeocodeError(f"geocoding request failed: {e}") from e

    data = r.json()
    results = data.get("results") or []
    if not results:
        raise GeocodeError(f"no location found for '{query}'")
    top = results[0]
    return Location(
        name=top.get("name", query),
        lat=float(top["latitude"]),
        lon=float(top["longitude"]),
        country=top.get("country", ""),
        admin=top.get("admin1", ""),
        timezone=top.get("timezone", ""),
    )
