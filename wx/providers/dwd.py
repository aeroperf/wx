"""Brightsky (DWD) adapter.

Brightsky exposes DWD's MOSMIX forecast and station observations.
Endpoints:
  GET https://api.brightsky.dev/current_weather?lat=&lon=
  GET https://api.brightsky.dev/weather?lat=&lon=&date=YYYY-MM-DD&last_date=YYYY-MM-DD

Brightsky returns SI units (Celsius, m/s, hPa, mm, meters) and ISO timestamps.
No API key required, but include a User-Agent for politeness.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import requests

from ..model import (
    CurrentConditions,
    DailyPeriod,
    Forecast,
    HourlyPeriod,
)

BASE = "https://api.brightsky.dev"


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _get(url: str, ua: str, timeout: int) -> dict[str, Any]:
    r = requests.get(url, headers={"User-Agent": ua}, timeout=timeout)
    r.raise_for_status()
    return r.json()


# Brightsky condition strings -> rough icon hint we'll reuse
_ICON_HINT = {
    "dry": "clear",
    "fog": "fog",
    "rain": "rain",
    "sleet": "sleet",
    "snow": "snow",
    "hail": "hail",
    "thunderstorm": "thunderstorm",
}


def fetch(lat: float, lon: float, location_label: str, ua: str, timeout: int = 15,
          days: int = 7) -> Forecast:
    fc = Forecast(
        provider="dwd",
        location_label=location_label,
        lat=lat,
        lon=lon,
        attribution="data: Deutscher Wetterdienst via Bright Sky (brightsky.dev)",
    )

    # Current
    try:
        cw = _get(f"{BASE}/current_weather?lat={lat}&lon={lon}", ua, timeout)
        w = cw.get("weather") or {}
        fc.current = CurrentConditions(
            time=_parse_dt(w.get("timestamp")),
            temperature=w.get("temperature"),
            dewpoint=w.get("dew_point"),
            humidity=w.get("relative_humidity"),
            wind_speed=_kmh_to_mps(w.get("wind_speed_10")),
            wind_gust=_kmh_to_mps(w.get("wind_gust_speed_10")),
            wind_direction=w.get("wind_direction_10"),
            pressure=w.get("pressure_msl"),
            visibility=w.get("visibility"),
            cloud_cover=w.get("cloud_cover"),
            condition=w.get("condition") or "",
            icon=_ICON_HINT.get((w.get("condition") or "").lower(), ""),
        )
    except requests.RequestException:
        pass

    # Hourly + daily over the next `days`
    today = date.today()
    last = today + timedelta(days=max(1, days))
    try:
        url = (
            f"{BASE}/weather?lat={lat}&lon={lon}"
            f"&date={today.isoformat()}&last_date={last.isoformat()}"
        )
        wf = _get(url, ua, timeout)
        records = wf.get("weather") or []
        # hourly
        for r in records:
            fc.hourly.append(
                HourlyPeriod(
                    time=_parse_dt(r.get("timestamp")) or datetime.now(),
                    temperature=r.get("temperature"),
                    wind_speed=_kmh_to_mps(r.get("wind_speed")),
                    wind_gust=_kmh_to_mps(r.get("wind_gust_speed")),
                    wind_direction=r.get("wind_direction"),
                    precipitation=r.get("precipitation"),
                    precip_probability=r.get("precipitation_probability"),
                    humidity=r.get("relative_humidity"),
                    cloud_cover=r.get("cloud_cover"),
                    condition=r.get("condition") or "",
                    icon=_ICON_HINT.get((r.get("condition") or "").lower(), ""),
                )
            )
        # roll up daily
        by_day: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for r in records:
            ts = _parse_dt(r.get("timestamp"))
            if not ts:
                continue
            k = ts.date().isoformat()
            if k not in by_day:
                by_day[k] = {"date": ts, "temps": [], "precip": 0.0,
                             "pops": [], "winds": [], "conditions": []}
                order.append(k)
            b = by_day[k]
            if r.get("temperature") is not None:
                b["temps"].append(r["temperature"])
            if r.get("precipitation"):
                b["precip"] += r["precipitation"]
            if r.get("precipitation_probability") is not None:
                b["pops"].append(r["precipitation_probability"])
            ws = _kmh_to_mps(r.get("wind_speed"))
            if ws is not None:
                b["winds"].append(ws)
            if r.get("condition"):
                b["conditions"].append(r["condition"])
        for k in order:
            b = by_day[k]
            temps = b["temps"]
            cond = _dominant(b["conditions"])
            fc.daily.append(
                DailyPeriod(
                    date=b["date"],
                    temp_min=min(temps) if temps else None,
                    temp_max=max(temps) if temps else None,
                    precipitation=b["precip"] or None,
                    precip_probability=max(b["pops"]) if b["pops"] else None,
                    wind_speed_max=max(b["winds"]) if b["winds"] else None,
                    condition=cond,
                    icon=_ICON_HINT.get(cond.lower(), ""),
                )
            )
    except requests.RequestException:
        pass

    return fc


def _kmh_to_mps(v):
    if v is None:
        return None
    try:
        return float(v) / 3.6
    except (TypeError, ValueError):
        return None


def _dominant(items: list[str]) -> str:
    if not items:
        return ""
    counts: dict[str, int] = {}
    for it in items:
        counts[it] = counts.get(it, 0) + 1
    return max(counts, key=counts.get)
