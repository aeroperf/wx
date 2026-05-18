"""AviationWeather.gov adapter for METAR and TAF.

Endpoints (https://aviationweather.gov/data/api/):
  GET /api/data/metar?ids={ICAO}&hours={N}&format=json
  GET /api/data/taf?ids={ICAO}&format=json

The METAR endpoint returns 204 with no body if `hours` is not supplied and
no report exists within the default look-back. Always pass `hours`.

Field reference (subset, see schema link above):
  METAR: icaoId, rawOb, obsTime (epoch s), reportTime (ISO),
         temp/dewp (°C), wdir (deg | "VRB"), wspd/wgst (kt), visib (str|num),
         altim (hPa), slp (hPa), fltCat, clouds[], cover, wxString
  TAF:   icaoId, rawTAF, issueTime (ISO), validTimeFrom/To (epoch s), mostRecent,
         fcsts[]: timeFrom/To (epoch s), fcstChange (FM|BECMG|PROB|TEMPO|null),
                  probability (int), wdir, wspd, wgst, visib, wxString, clouds[]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

import requests

BASE = "https://aviationweather.gov/api/data"

WindDir = int | Literal["VRB"] | None
Visibility = str | float | None


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
    wind_dir: WindDir = None
    wind_speed_kt: float | None = None
    wind_gust_kt: float | None = None
    visibility: Visibility = None
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
    wind_dir: WindDir = None
    wind_speed_kt: float | None = None
    wind_gust_kt: float | None = None
    visibility: Visibility = None
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


def _epoch(v: Any) -> datetime | None:
    if v is None:
        return None
    try:
        return datetime.fromtimestamp(int(v), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _iso(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


def _get_json(path: str, params: dict[str, Any], ua: str, timeout: int) -> list[dict[str, Any]]:
    r = requests.get(
        f"{BASE}/{path}",
        params=params,
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


def _pick_most_recent(records: list[dict[str, Any]], time_key: str) -> dict[str, Any]:
    """Prefer records flagged mostRecent=1, otherwise newest by `time_key` (epoch s)."""
    recents = [r for r in records if r.get("mostRecent") == 1]
    if recents:
        return recents[0]
    return max(records, key=lambda r: r.get(time_key) or 0)


def _metar_from_dict(d: dict[str, Any], fallback_icao: str) -> MetarReport:
    return MetarReport(
        icao=d.get("icaoId", fallback_icao),
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
        visibility=d.get("visib"),
        altimeter_hpa=d.get("altim"),
        slp_hpa=d.get("slp"),
        flight_cat=d.get("fltCat", ""),
        clouds=d.get("clouds") or [],
        cover=d.get("cover", ""),
        wx_string=d.get("wxString") or "",
    )


def _taf_from_dict(d: dict[str, Any], fallback_icao: str) -> TafReport:
    forecasts = [
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
        for f in (d.get("fcsts") or [])
    ]
    return TafReport(
        icao=d.get("icaoId", fallback_icao),
        raw=d.get("rawTAF", ""),
        issued=_iso(d.get("issueTime")),
        valid_from=_epoch(d.get("validTimeFrom")),
        valid_to=_epoch(d.get("validTimeTo")),
        name=d.get("name", ""),
        lat=d.get("lat"),
        lon=d.get("lon"),
        elev_m=d.get("elev"),
        remarks=d.get("remarks") or "",
        forecasts=forecasts,
    )


def fetch_metar(icao: str, ua: str, timeout: int = 15, hours: int = 6) -> MetarReport:
    icao = icao.upper().strip()
    data = _get_json(
        "metar",
        {"ids": icao, "hours": hours, "format": "json"},
        ua,
        timeout,
    )
    if not data:
        raise AviationWeatherError(f"no METAR available for {icao} (last {hours}h)")
    return _metar_from_dict(_pick_most_recent(data, "obsTime"), icao)


def fetch_taf(icao: str, ua: str, timeout: int = 15) -> TafReport:
    icao = icao.upper().strip()
    data = _get_json(
        "taf",
        {"ids": icao, "format": "json"},
        ua,
        timeout,
    )
    if not data:
        raise AviationWeatherError(f"no TAF available for {icao}")
    # API may return current + amended; prefer mostRecent=1, else latest issue.
    return _taf_from_dict(_pick_most_recent(data, "validTimeFrom"), icao)
