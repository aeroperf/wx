"""met.no Locationforecast 2.0 adapter (global fallback).

GET https://api.met.no/weatherapi/locationforecast/2.0/compact?lat=&lon=

Returns SI units in JSON (celsius, m/s, hPa, mm, percent).
Coordinates MUST be rounded to <= 4 decimals or request returns 403.
User-Agent MUST be descriptive (not generic), or request returns 403.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import requests

from ..model import (
    CurrentConditions,
    DailyPeriod,
    Forecast,
    HourlyPeriod,
)

BASE = "https://api.met.no/weatherapi/locationforecast/2.0/compact"


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch(lat: float, lon: float, location_label: str, ua: str, timeout: int = 15) -> Forecast:
    lat4 = round(lat, 4)
    lon4 = round(lon, 4)
    fc = Forecast(
        provider="metno",
        location_label=location_label,
        lat=lat4,
        lon=lon4,
        attribution="data: MET Norway (api.met.no, CC BY 4.0)",
    )

    r = requests.get(
        f"{BASE}?lat={lat4}&lon={lon4}",
        headers={"User-Agent": ua, "Accept": "application/json"},
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    ts = data.get("properties", {}).get("timeseries") or []

    if not ts:
        return fc

    # current = first timeseries entry
    first = ts[0]
    inst = (first.get("data", {}).get("instant", {}).get("details") or {})
    next1 = (
        first.get("data", {}).get("next_1_hours", {}).get("summary", {}).get("symbol_code")
        or first.get("data", {}).get("next_6_hours", {}).get("summary", {}).get("symbol_code")
        or ""
    )
    fc.current = CurrentConditions(
        time=_parse_dt(first.get("time")),
        temperature=inst.get("air_temperature"),
        dewpoint=inst.get("dew_point_temperature"),
        humidity=inst.get("relative_humidity"),
        wind_speed=inst.get("wind_speed"),
        wind_gust=inst.get("wind_speed_of_gust"),
        wind_direction=inst.get("wind_from_direction"),
        pressure=inst.get("air_pressure_at_sea_level"),
        cloud_cover=inst.get("cloud_area_fraction"),
        condition=_humanize_symbol(next1),
        icon=next1,
    )

    # hourly: each entry has an instant; many have next_1_hours
    by_day: dict[str, dict[str, Any]] = {}
    day_order: list[str] = []
    for entry in ts:
        t = _parse_dt(entry.get("time"))
        if not t:
            continue
        det = entry.get("data", {}).get("instant", {}).get("details") or {}
        n1 = entry.get("data", {}).get("next_1_hours", {}) or {}
        n1s = n1.get("summary", {}) or {}
        n1d = n1.get("details", {}) or {}
        n6 = entry.get("data", {}).get("next_6_hours", {}) or {}
        n6s = n6.get("summary", {}) or {}
        n6d = n6.get("details", {}) or {}

        symbol = n1s.get("symbol_code") or n6s.get("symbol_code") or ""
        precip = n1d.get("precipitation_amount") or n6d.get("precipitation_amount")

        # only keep "hourly" entries from next_1_hours (first ~48h)
        if n1:
            fc.hourly.append(
                HourlyPeriod(
                    time=t,
                    temperature=det.get("air_temperature"),
                    wind_speed=det.get("wind_speed"),
                    wind_gust=det.get("wind_speed_of_gust"),
                    wind_direction=det.get("wind_from_direction"),
                    precipitation=precip,
                    humidity=det.get("relative_humidity"),
                    cloud_cover=det.get("cloud_area_fraction"),
                    condition=_humanize_symbol(symbol),
                    icon=symbol,
                )
            )

        # roll up daily
        k = t.date().isoformat()
        if k not in by_day:
            by_day[k] = {"date": t, "temps": [], "precip": 0.0,
                         "winds": [], "symbols": []}
            day_order.append(k)
        b = by_day[k]
        if det.get("air_temperature") is not None:
            b["temps"].append(det["air_temperature"])
        if precip:
            b["precip"] += precip
        if det.get("wind_speed") is not None:
            b["winds"].append(det["wind_speed"])
        if symbol:
            b["symbols"].append(symbol)

    for k in day_order:
        b = by_day[k]
        temps = b["temps"]
        sym = _dominant(b["symbols"])
        fc.daily.append(
            DailyPeriod(
                date=b["date"],
                temp_min=min(temps) if temps else None,
                temp_max=max(temps) if temps else None,
                precipitation=b["precip"] or None,
                wind_speed_max=max(b["winds"]) if b["winds"] else None,
                condition=_humanize_symbol(sym),
                icon=sym,
            )
        )

    return fc


def _dominant(items: list[str]) -> str:
    if not items:
        return ""
    counts: dict[str, int] = {}
    for it in items:
        # collapse day/night/polartwilight suffixes
        base = it.split("_")[0]
        counts[base] = counts.get(base, 0) + 1
    return max(counts, key=counts.get)


_SYMBOL_HUMAN = {
    "clearsky": "Clear sky",
    "fair": "Fair",
    "partlycloudy": "Partly cloudy",
    "cloudy": "Cloudy",
    "fog": "Fog",
    "rainshowers": "Rain showers",
    "rainshowersandthunder": "Rain showers with thunder",
    "sleetshowers": "Sleet showers",
    "snowshowers": "Snow showers",
    "rain": "Rain",
    "heavyrain": "Heavy rain",
    "heavyrainandthunder": "Heavy rain with thunder",
    "sleet": "Sleet",
    "snow": "Snow",
    "snowandthunder": "Snow with thunder",
    "lightrainshowers": "Light rain showers",
    "heavyrainshowers": "Heavy rain showers",
    "lightrain": "Light rain",
    "lightsleet": "Light sleet",
    "heavysleet": "Heavy sleet",
    "lightsnow": "Light snow",
    "heavysnow": "Heavy snow",
}


def _humanize_symbol(symbol: str) -> str:
    if not symbol:
        return ""
    base = symbol.split("_")[0]
    return _SYMBOL_HUMAN.get(base, base.replace("_", " ").capitalize())
