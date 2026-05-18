"""NWS (US National Weather Service) adapter.

Flow:
  1. GET /points/{lat},{lon}           -> grid + forecast URLs + station list
  2. GET .../stations                  -> nearest observation station
  3. GET /stations/{id}/observations/latest  -> current conditions
  4. GET forecastHourly                -> hourly periods
  5. GET forecast                      -> twice-daily detailed periods
  6. GET /alerts/active?point=lat,lon  -> active alerts

NWS units in responses can vary; we parse them rather than assume.
Coordinate values are truncated to 4 decimal places.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import requests

from ..model import (
    Alert,
    CurrentConditions,
    DailyPeriod,
    Forecast,
    HourlyPeriod,
)

BASE = "https://api.weather.gov"


def _round(v: float) -> float:
    return round(v, 4)


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        # NWS uses ISO-8601 with offset
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _value(obj: Any) -> float | None:
    """Extract numeric `value` from an NWS quantitative-value object, converting to SI."""
    if not isinstance(obj, dict):
        return None
    v = obj.get("value")
    if v is None:
        return None
    unit = (obj.get("unitCode") or "").lower()
    # Common NWS unit codes
    if unit.endswith(":degc"):
        return float(v)
    if unit.endswith(":degf"):
        return (float(v) - 32) * 5 / 9
    if unit.endswith(":km_h-1") or unit.endswith(":km_h"):
        return float(v) / 3.6
    if unit.endswith(":m_s-1") or unit.endswith(":m_s"):
        return float(v)
    if unit.endswith(":mi_h-1"):
        return float(v) * 0.44704
    if unit.endswith(":mm"):
        return float(v)
    if unit.endswith(":m"):
        return float(v)
    if unit.endswith(":pa"):
        return float(v) / 100  # Pa -> hPa
    if unit.endswith(":percent"):
        return float(v)
    return float(v)


def _get(url: str, ua: str, timeout: int) -> dict[str, Any]:
    r = requests.get(
        url,
        headers={"User-Agent": ua, "Accept": "application/geo+json"},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()


def fetch(lat: float, lon: float, location_label: str, ua: str, timeout: int = 15) -> Forecast:
    lat, lon = _round(lat), _round(lon)
    fc = Forecast(
        provider="nws",
        location_label=location_label,
        lat=lat,
        lon=lon,
        attribution="data: US NOAA/NWS (api.weather.gov)",
    )

    points = _get(f"{BASE}/points/{lat},{lon}", ua, timeout)
    pprops = points["properties"]
    forecast_url = pprops.get("forecast")
    hourly_url = pprops.get("forecastHourly")
    stations_url = pprops.get("observationStations")

    # current conditions from nearest station
    if stations_url:
        try:
            stations = _get(stations_url, ua, timeout)
            feats = stations.get("features") or []
            if feats:
                station_id = feats[0]["properties"]["stationIdentifier"]
                obs = _get(
                    f"{BASE}/stations/{station_id}/observations/latest",
                    ua,
                    timeout,
                )
                op = obs["properties"]
                apparent = _value(op.get("heatIndex"))
                if apparent is None:
                    apparent = _value(op.get("windChill"))
                if apparent is None:
                    apparent = _value(op.get("temperature"))
                fc.current = CurrentConditions(
                    time=_parse_dt(op.get("timestamp")),
                    temperature=_value(op.get("temperature")),
                    apparent=apparent,
                    dewpoint=_value(op.get("dewpoint")),
                    humidity=_value(op.get("relativeHumidity")),
                    wind_speed=_value(op.get("windSpeed")),
                    wind_gust=_value(op.get("windGust")),
                    wind_direction=_value(op.get("windDirection")),
                    pressure=_value(op.get("barometricPressure")),
                    visibility=_value(op.get("visibility")),
                    cloud_cover=None,
                    condition=op.get("textDescription") or "",
                    icon=op.get("icon") or "",
                )
        except requests.RequestException:
            pass  # leave current as None

    # hourly
    if hourly_url:
        try:
            h = _get(hourly_url, ua, timeout)
            for p in h["properties"]["periods"]:
                # NWS hourly is in F or C depending on unit attribute
                t = p.get("temperature")
                t_unit = (p.get("temperatureUnit") or "F").upper()
                t_c = None if t is None else (float(t) if t_unit == "C" else (float(t) - 32) * 5 / 9)
                # windSpeed is a string like "10 mph"
                ws_mps = _parse_wind_string(p.get("windSpeed"))
                wd = p.get("windDirection")
                fc.hourly.append(
                    HourlyPeriod(
                        time=_parse_dt(p.get("startTime")) or datetime.now(),
                        temperature=t_c,
                        wind_speed=ws_mps,
                        wind_direction=_dir_to_deg(wd),
                        precip_probability=(p.get("probabilityOfPrecipitation") or {}).get("value"),
                        humidity=(p.get("relativeHumidity") or {}).get("value"),
                        condition=p.get("shortForecast") or "",
                        icon=p.get("icon") or "",
                    )
                )
        except requests.RequestException:
            pass

    # daily (NWS returns twice-daily periods - day/night pairs)
    if forecast_url:
        try:
            f = _get(forecast_url, ua, timeout)
            periods = f["properties"]["periods"]
            # pair day/night into daily entries
            day_buckets: dict[str, dict[str, Any]] = {}
            order: list[str] = []
            for p in periods:
                start = _parse_dt(p.get("startTime"))
                if not start:
                    continue
                key = start.date().isoformat()
                bucket = day_buckets.setdefault(key, {})
                if key not in order:
                    order.append(key)
                t = p.get("temperature")
                t_unit = (p.get("temperatureUnit") or "F").upper()
                t_c = None if t is None else (float(t) if t_unit == "C" else (float(t) - 32) * 5 / 9)
                if p.get("isDaytime"):
                    bucket["max"] = t_c
                    bucket["day_summary"] = p.get("detailedForecast") or ""
                    bucket["day_short"] = p.get("shortForecast") or ""
                    bucket["icon"] = p.get("icon") or bucket.get("icon", "")
                    bucket["wind_dir"] = _dir_to_deg(p.get("windDirection"))
                    bucket["wind_max"] = _parse_wind_string(p.get("windSpeed"))
                else:
                    bucket["min"] = t_c
                    if "day_short" not in bucket:
                        bucket["day_short"] = p.get("shortForecast") or ""
                        bucket["day_summary"] = p.get("detailedForecast") or ""
                bucket.setdefault("date", start)
                pop = (p.get("probabilityOfPrecipitation") or {}).get("value")
                if pop is not None:
                    bucket["pop"] = max(bucket.get("pop") or 0, pop)
            for key in order:
                b = day_buckets[key]
                fc.daily.append(
                    DailyPeriod(
                        date=b["date"],
                        temp_min=b.get("min"),
                        temp_max=b.get("max"),
                        precip_probability=b.get("pop"),
                        wind_speed_max=b.get("wind_max"),
                        wind_direction=b.get("wind_dir"),
                        condition=b.get("day_short", ""),
                        icon=b.get("icon", ""),
                        summary=b.get("day_summary", ""),
                    )
                )
        except requests.RequestException:
            pass

    # alerts
    try:
        a = _get(f"{BASE}/alerts/active?point={lat},{lon}", ua, timeout)
        for feat in a.get("features") or []:
            ap = feat.get("properties", {})
            fc.alerts.append(
                Alert(
                    headline=ap.get("headline", ""),
                    severity=ap.get("severity", ""),
                    event=ap.get("event", ""),
                    description=ap.get("description", ""),
                    instruction=ap.get("instruction") or "",
                    onset=_parse_dt(ap.get("onset")),
                    expires=_parse_dt(ap.get("expires")),
                )
            )
    except requests.RequestException:
        pass

    return fc


_CARDINAL = {
    "N": 0, "NNE": 22.5, "NE": 45, "ENE": 67.5,
    "E": 90, "ESE": 112.5, "SE": 135, "SSE": 157.5,
    "S": 180, "SSW": 202.5, "SW": 225, "WSW": 247.5,
    "W": 270, "WNW": 292.5, "NW": 315, "NNW": 337.5,
}


def _dir_to_deg(d) -> float | None:
    if d is None:
        return None
    if isinstance(d, (int, float)):
        return float(d)
    return _CARDINAL.get(str(d).upper().strip())


def _parse_wind_string(s) -> float | None:
    """NWS daily/hourly windSpeed is a string like '10 mph' or '5 to 10 mph'."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s) * 0.44704  # assume mph
    parts = str(s).split()
    # take last numeric token, convert mph -> m/s
    nums = [float(p) for p in parts if p.replace(".", "", 1).isdigit()]
    if not nums:
        return None
    mph = max(nums)  # for "5 to 10", use the upper
    if "kph" in s.lower() or "km/h" in s.lower():
        return mph / 3.6
    return mph * 0.44704
