"""Canonical weather data structures.

All adapters return these. Units are SI / canonical:
  temperature       : Celsius
  apparent / dewpoint: Celsius
  wind_speed / gust : m/s
  wind_direction    : degrees (0=N, 90=E)
  pressure          : hPa
  precipitation     : mm (over the period)
  precip_probability: 0-100
  humidity          : 0-100
  visibility        : meters
  cloud_cover       : 0-100
  uv_index          : float
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class CurrentConditions:
    time: Optional[datetime] = None
    temperature: Optional[float] = None
    apparent: Optional[float] = None
    dewpoint: Optional[float] = None
    humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_gust: Optional[float] = None
    wind_direction: Optional[float] = None
    pressure: Optional[float] = None
    visibility: Optional[float] = None
    cloud_cover: Optional[float] = None
    condition: str = ""           # human-readable summary
    icon: str = ""                # provider's symbol code (best-effort)


@dataclass
class HourlyPeriod:
    time: datetime
    temperature: Optional[float] = None
    apparent: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_gust: Optional[float] = None
    wind_direction: Optional[float] = None
    precipitation: Optional[float] = None
    precip_probability: Optional[float] = None
    humidity: Optional[float] = None
    cloud_cover: Optional[float] = None
    condition: str = ""
    icon: str = ""


@dataclass
class DailyPeriod:
    date: datetime
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    precipitation: Optional[float] = None
    precip_probability: Optional[float] = None
    wind_speed_max: Optional[float] = None
    wind_direction: Optional[float] = None
    condition: str = ""
    icon: str = ""
    summary: str = ""             # NWS-style detailed forecast paragraph


@dataclass
class Alert:
    headline: str
    severity: str = ""
    event: str = ""
    description: str = ""
    instruction: str = ""
    onset: Optional[datetime] = None
    expires: Optional[datetime] = None


@dataclass
class Forecast:
    provider: str                  # 'nws' | 'dwd' | 'metno'
    location_label: str
    lat: float
    lon: float
    current: Optional[CurrentConditions] = None
    hourly: list[HourlyPeriod] = field(default_factory=list)
    daily: list[DailyPeriod] = field(default_factory=list)
    alerts: list[Alert] = field(default_factory=list)
    attribution: str = ""
