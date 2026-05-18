"""AviationWeather.gov adapter for METAR and TAF.

Endpoints (https://aviationweather.gov/data/api/):
  GET /api/data/metar?ids={ICAO}&hours={N}&format=json
  GET /api/data/taf?ids={ICAO}&format=json

The METAR endpoint returns 204 with no body if `hours` is not supplied and
no report exists within the default look-back. Always pass `hours`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import requests

BASE = "https://aviationweather.gov/api/data"


class AviationWeatherError(RuntimeError):
    pass


@dataclass
class MetarReport:
    icao: str
    raw: str
    observed: datetime | None = None
    report_time: datetime | None = None
    name: str = ""
    lat: float | None = None
    lon: float | None = None
    elev_m: float | None = None
    temp_c: float | None = None
    dewp_c: float | None = None
    wind_dir: Any = None        # int deg or "VRB"
    wind_speed_kt: float | None = None
    wind_gust_kt: float | None = None
    visibility: str = ""        # raw string (e.g. "10+", "6")
    altimeter_hpa: float | None = None
    slp_hpa: float | None = None
    flight_cat: str = ""
    clouds: list[dict[str, Any]] = field(default_factory=list)
    cover: str = ""
    wx_string: str = ""


@dataclass
class TafForecastPeriod:
    time_from: datetime | None
    time_to: datetime | None
    change: str = ""            # FM, BECMG, PROB, TEMPO, ""
    probability: int | None = None
    wind_dir: Any = None
    wind_speed_kt: float | None = None
    wind_gust_kt: float | None = None
    visibility: Any = None      # str or number
    wx_string: str = ""
    clouds: list[dict[str, Any]] = field(default_factory=list)
    wind_shear_hgt_ft: int | None = None
    wind_shear_dir: int | None = None
    wind_shear_spd_kt: float | None = None


@dataclass
class TafReport:
    icao: str
    raw: str
    issued: datetime | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    name: str = ""
    lat: float | None = None
    lon: float | None = None
    elev_m: float | None = None
    remarks: str = ""
    forecasts: list[TafForecastPeriod] = field(default_factory=list)


def _epoch(v) -> datetime | None:
    if v is None:
        return None
    try:
        return datetime.fromtimestamp(int(v), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _iso(v) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


def _get_json(url: str, ua: str, timeout: int) -> list[dict[str, Any]]:
    r = requests.get(
        url,
        headers={"User-Agent": ua, "Accept": "application/json"},
        timeout=timeout,
    )
    if r.status_code == 204 or not r.content:
        return []
    r.raise_for_status()
    try:
        data = r.json()
    except ValueError as e:
        raise AviationWeatherError(f"invalid JSON from aviationweather.gov: {e}") from e
    if not isinstance(data, list):
        raise AviationWeatherError("unexpected response shape")
    return data


def fetch_metar(icao: str, ua: str, timeout: int = 15, hours: int = 6) -> MetarReport:
    icao = icao.upper().strip()
    url = f"{BASE}/metar?ids={icao}&hours={hours}&format=json"
    data = _get_json(url, ua, timeout)
    if not data:
        raise AviationWeatherError(f"no METAR available for {icao} (last {hours}h)")
    d = data[0]  # most recent
    return MetarReport(
        icao=d.get("icaoId", icao),
        raw=d.get("rawOb", ""),
        observed=_epoch(d.get("obsTime")),
        report_time=_iso(d.get("reportTime")),
        name=d.get("name", ""),
        lat=d.get("lat"),
        lon=d.get("lon"),
        elev_m=d.get("elev"),
        temp_c=d.get("temp"),
        dewp_c=d.get("dewp"),
        wind_dir=d.get("wdir"),
        wind_speed_kt=d.get("wspd"),
        wind_gust_kt=d.get("wgst"),
        visibility=str(d.get("visib", "")),
        altimeter_hpa=d.get("altim"),
        slp_hpa=d.get("slp"),
        flight_cat=d.get("fltCat", ""),
        clouds=d.get("clouds") or [],
        cover=d.get("cover", ""),
        wx_string=d.get("wxString", "") or "",
    )


def fetch_taf(icao: str, ua: str, timeout: int = 15) -> TafReport:
    icao = icao.upper().strip()
    url = f"{BASE}/taf?ids={icao}&format=json"
    data = _get_json(url, ua, timeout)
    if not data:
        raise AviationWeatherError(f"no TAF available for {icao}")
    d = data[0]
    forecasts: list[TafForecastPeriod] = []
    for f in d.get("fcsts") or []:
        forecasts.append(
            TafForecastPeriod(
                time_from=_epoch(f.get("timeFrom")),
                time_to=_epoch(f.get("timeTo")),
                change=f.get("fcstChange") or "",
                probability=f.get("probability"),
                wind_dir=f.get("wdir"),
                wind_speed_kt=f.get("wspd"),
                wind_gust_kt=f.get("wgst"),
                visibility=f.get("visib"),
                wx_string=f.get("wxString") or "",
                clouds=f.get("clouds") or [],
                wind_shear_hgt_ft=f.get("wshearHgt"),
                wind_shear_dir=f.get("wshearDir"),
                wind_shear_spd_kt=f.get("wshearSpd"),
            )
        )
    return TafReport(
        icao=d.get("icaoId", icao),
        raw=d.get("rawTAF", ""),
        issued=_iso(d.get("issueTime")),
        valid_from=_epoch(d.get("validTimeFrom")),
        valid_to=_epoch(d.get("validTimeTo")),
        name=d.get("name", ""),
        lat=d.get("lat"),
        lon=d.get("lon"),
        elev_m=d.get("elev"),
        remarks=d.get("remarks", "") or "",
        forecasts=forecasts,
    )
