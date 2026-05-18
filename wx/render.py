"""Output renderers for the four display styles."""
from __future__ import annotations

import json as jsonlib
import textwrap
from datetime import datetime
from typing import Any

from .model import DailyPeriod, Forecast, HourlyPeriod
from . import units as U

# ANSI colors (disabled if config.display.color is False)
class _Style:
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    YEL = "\033[33m"
    GRN = "\033[32m"
    CYN = "\033[36m"
    BLU = "\033[34m"
    MAG = "\033[35m"
    RST = "\033[0m"


class _NoStyle:
    BOLD = DIM = RED = YEL = GRN = CYN = BLU = MAG = RST = ""


def _style(color: bool):
    return _Style() if color else _NoStyle()


# tiny ASCII art per condition keyword
_ART = {
    "clear": [
        "    \\   /    ",
        "     .-.     ",
        "  ― (   ) ―  ",
        "     `-'     ",
        "    /   \\    ",
    ],
    "cloudy": [
        "             ",
        "    .--.     ",
        " .-(    ).   ",
        "(___.__)__)  ",
        "             ",
    ],
    "rain": [
        "    .-.      ",
        "   (   ).    ",
        "  (___(__)   ",
        "   ' ' ' '   ",
        "  ' ' ' '    ",
    ],
    "snow": [
        "    .-.      ",
        "   (   ).    ",
        "  (___(__)   ",
        "    *  *  *  ",
        "   *  *  *   ",
    ],
    "fog": [
        "             ",
        " _ - _ - _ - ",
        "  _ - _ - _  ",
        " _ - _ - _ - ",
        "             ",
    ],
    "thunderstorm": [
        "    .-.      ",
        "   (   ).    ",
        "  (___(__)   ",
        "   ⚡⚡⚡⚡   ",
        "  ' ' ' '    ",
    ],
}


def _art_for(condition: str, icon: str) -> list[str]:
    c = (condition + " " + icon).lower()
    if "thunder" in c:
        return _ART["thunderstorm"]
    if "snow" in c or "sleet" in c:
        return _ART["snow"]
    if "rain" in c or "drizzle" in c or "shower" in c:
        return _ART["rain"]
    if "fog" in c or "mist" in c or "haze" in c:
        return _ART["fog"]
    if "cloud" in c or "overcast" in c:
        return _ART["cloudy"]
    if "clear" in c or "sunny" in c or "fair" in c:
        return _ART["clear"]
    return [" " * 13] * 5


def _convert_temp(c: float | None, u: str) -> str:
    v = U.c_to(c, u)
    suffix = U.TEMP_SUFFIX.get(u.lower(), "°")
    return U.fmt(v, suffix)


def _convert_wind(mps: float | None, u: str) -> str:
    v = U.mps_to(mps, u)
    suffix = U.WIND_SUFFIX.get(u.lower(), u)
    return U.fmt(v, suffix)


def _convert_pressure(hpa: float | None, u: str) -> str:
    v = U.hpa_to(hpa, u)
    suffix = U.PRESSURE_SUFFIX.get(u.lower(), u)
    return U.fmt(v, suffix, decimals=2 if u.lower() == "inhg" else 0)


def _convert_precip(mm: float | None, u: str) -> str:
    v = U.mm_to(mm, u)
    suffix = U.PRECIP_SUFFIX.get(u.lower(), u)
    return U.fmt(v, suffix, decimals=2 if u.lower() == "in" else 1)


def _convert_vis(m: float | None, u: str) -> str:
    v = U.meters_to(m, u)
    suffix = U.VIS_SUFFIX.get(u.lower(), u)
    return U.fmt(v, suffix, decimals=0)


def _wind_dir_short(deg: float | None) -> str:
    if deg is None:
        return ""
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return dirs[int((deg + 11.25) // 22.5) % 16]


def _fmt_time(t: datetime | None, fmt: str = "%H:%M") -> str:
    if not t:
        return ""
    return t.strftime(fmt)


def _fmt_day(d: datetime | None) -> str:
    if not d:
        return ""
    return d.strftime("%a %b %d")


# ─── rich (default) ───────────────────────────────────────────────────────
def render_rich(fc: Forecast, cfg: dict, show_hourly: bool, show_daily: bool,
                show_alerts: bool, days: int, hourly_hours: int) -> str:
    s = _style(cfg["display"]["color"])
    u = cfg["units"]
    show_icons = cfg["display"]["icons"]
    out: list[str] = []

    # header
    out.append(f"{s.BOLD}{fc.location_label}{s.RST}  "
               f"{s.DIM}({fc.lat:.4f}, {fc.lon:.4f}) via {fc.provider.upper()}{s.RST}")
    out.append("")

    # current + art
    if fc.current:
        c = fc.current
        art = _art_for(c.condition, c.icon) if show_icons else [""] * 5
        lines = [
            f"{s.BOLD}{c.condition or '—'}{s.RST}",
            f"  {_convert_temp(c.temperature, u['temperature'])}"
            + (f"  feels {_convert_temp(c.apparent, u['temperature'])}" if c.apparent is not None else ""),
            f"  {_wind_dir_short(c.wind_direction)} {_convert_wind(c.wind_speed, u['wind'])}"
            + (f", gust {_convert_wind(c.wind_gust, u['wind'])}" if c.wind_gust else ""),
            f"  {U.fmt(c.humidity, '%')}  {_convert_pressure(c.pressure, u['pressure'])}",
            f"  vis {_convert_vis(c.visibility, u['visibility'])}"
            + (f"  cloud {U.fmt(c.cloud_cover, '%')}" if c.cloud_cover is not None else ""),
        ]
        for a, l in zip(art, lines):
            out.append(f"{s.CYN}{a}{s.RST}  {l}")
        out.append("")

    # alerts
    if show_alerts and fc.alerts:
        out.append(f"{s.BOLD}{s.RED}⚠ Active alerts:{s.RST}")
        for al in fc.alerts:
            sev_color = s.RED if al.severity in ("Extreme", "Severe") else s.YEL
            out.append(f"  {sev_color}{al.event}{s.RST} — {al.headline}")
            if al.expires:
                out.append(f"    {s.DIM}expires {al.expires.strftime('%Y-%m-%d %H:%M %Z')}{s.RST}")
        out.append("")

    # hourly
    if show_hourly and fc.hourly:
        out.append(f"{s.BOLD}Hourly (next {hourly_hours}h){s.RST}")
        out.append(f"  {s.DIM}{'time':<6} {'temp':>7} {'wind':>14} {'precip':>9} {'cond':<24}{s.RST}")
        for p in fc.hourly[:hourly_hours]:
            t = _fmt_time(p.time)
            temp = _convert_temp(p.temperature, u['temperature'])
            wind = f"{_wind_dir_short(p.wind_direction):>3} {_convert_wind(p.wind_speed, u['wind'])}"
            pop = f"{int(p.precip_probability)}%" if p.precip_probability is not None else ""
            precip = _convert_precip(p.precipitation, u['precipitation']) if p.precipitation else ""
            pp = f"{pop} {precip}".strip()
            out.append(f"  {t:<6} {temp:>7} {wind:>14} {pp:>9} {p.condition:<24}")
        out.append("")

    # daily
    if show_daily and fc.daily:
        out.append(f"{s.BOLD}Daily{s.RST}")
        for d in fc.daily[:days]:
            day = _fmt_day(d.date)
            lo = _convert_temp(d.temp_min, u['temperature'])
            hi = _convert_temp(d.temp_max, u['temperature'])
            pop = f" • {int(d.precip_probability)}% precip" if d.precip_probability is not None else ""
            precip = f" / {_convert_precip(d.precipitation, u['precipitation'])}" if d.precipitation else ""
            wind = ""
            if d.wind_speed_max:
                wind = f" • wind {_convert_wind(d.wind_speed_max, u['wind'])}"
            out.append(f"  {s.BOLD}{day:<14}{s.RST}{hi:>7} / {lo:<7}  {s.CYN}{d.condition}{s.RST}{pop}{precip}{wind}")
            if d.summary:
                # wrap NWS detail to 78 chars
                out.append(f"    {s.DIM}{_wrap(d.summary, 76)}{s.RST}")
        out.append("")

    out.append(f"{s.DIM}{fc.attribution}{s.RST}")
    return "\n".join(out)


def _wrap(text: str, width: int) -> str:
    return "\n    ".join(textwrap.wrap(text, width=width))


# ─── table ────────────────────────────────────────────────────────────────
def render_table(fc: Forecast, cfg: dict, show_hourly: bool, show_daily: bool,
                 show_alerts: bool, days: int, hourly_hours: int) -> str:
    u = cfg["units"]
    out = [f"{fc.location_label}  ({fc.lat:.4f}, {fc.lon:.4f})  via {fc.provider.upper()}", ""]

    if fc.current:
        c = fc.current
        rows = [
            ("condition", c.condition or "—"),
            ("temperature", _convert_temp(c.temperature, u['temperature'])),
            ("feels like", _convert_temp(c.apparent, u['temperature'])),
            ("humidity", f"{c.humidity:.0f}%" if c.humidity is not None else "—"),
            ("wind", f"{_wind_dir_short(c.wind_direction)} {_convert_wind(c.wind_speed, u['wind'])}"),
            ("gust", _convert_wind(c.wind_gust, u['wind']) if c.wind_gust else "—"),
            ("pressure", _convert_pressure(c.pressure, u['pressure'])),
            ("visibility", _convert_vis(c.visibility, u['visibility'])),
        ]
        out.append("CURRENT")
        for k, v in rows:
            out.append(f"  {k:<14} {v}")
        out.append("")

    if show_alerts and fc.alerts:
        out.append("ALERTS")
        for al in fc.alerts:
            out.append(f"  [{al.severity}] {al.event}: {al.headline}")
        out.append("")

    if show_hourly and fc.hourly:
        out.append(f"HOURLY (next {hourly_hours}h)")
        out.append(f"  {'time':<7}{'temp':>8}{'wind':>14}{'precip':>10}  condition")
        for p in fc.hourly[:hourly_hours]:
            t = _fmt_time(p.time)
            temp = _convert_temp(p.temperature, u['temperature'])
            wind = f"{_wind_dir_short(p.wind_direction)} {_convert_wind(p.wind_speed, u['wind'])}"
            pop = f"{int(p.precip_probability)}%" if p.precip_probability is not None else "—"
            out.append(f"  {t:<7}{temp:>8}{wind:>14}{pop:>10}  {p.condition}")
        out.append("")

    if show_daily and fc.daily:
        out.append("DAILY")
        out.append(f"  {'day':<14}{'high':>8}{'low':>8}{'precip':>10}  condition")
        for d in fc.daily[:days]:
            day = _fmt_day(d.date)
            hi = _convert_temp(d.temp_max, u['temperature'])
            lo = _convert_temp(d.temp_min, u['temperature'])
            pop = f"{int(d.precip_probability)}%" if d.precip_probability else "—"
            out.append(f"  {day:<14}{hi:>8}{lo:>8}{pop:>10}  {d.condition}")
        out.append("")

    out.append(fc.attribution)
    return "\n".join(out)


# ─── plain ────────────────────────────────────────────────────────────────
def render_plain(fc: Forecast, cfg: dict, show_hourly: bool, show_daily: bool,
                 show_alerts: bool, days: int, hourly_hours: int) -> str:
    u = cfg["units"]
    lines = [f"{fc.location_label} ({fc.lat:.4f},{fc.lon:.4f}) [{fc.provider}]"]
    if fc.current:
        c = fc.current
        lines.append(
            f"now: {c.condition or '?'} "
            f"{_convert_temp(c.temperature, u['temperature'])} "
            f"wind {_wind_dir_short(c.wind_direction)} {_convert_wind(c.wind_speed, u['wind'])} "
            f"rh {U.fmt(c.humidity, '%')} "
            f"p {_convert_pressure(c.pressure, u['pressure'])}"
        )
    if show_alerts:
        for al in fc.alerts:
            lines.append(f"alert: [{al.severity}] {al.event}: {al.headline}")
    if show_hourly:
        for p in fc.hourly[:hourly_hours]:
            pop = f" pop {int(p.precip_probability)}%" if p.precip_probability is not None else ""
            lines.append(
                f"{_fmt_time(p.time)}: {_convert_temp(p.temperature, u['temperature'])} "
                f"{_wind_dir_short(p.wind_direction)} {_convert_wind(p.wind_speed, u['wind'])}"
                f"{pop} {p.condition}"
            )
    if show_daily:
        for d in fc.daily[:days]:
            lines.append(
                f"{_fmt_day(d.date)}: hi {_convert_temp(d.temp_max, u['temperature'])} "
                f"lo {_convert_temp(d.temp_min, u['temperature'])} {d.condition}"
            )
    return "\n".join(lines)


# ─── json ─────────────────────────────────────────────────────────────────
def render_json(fc: Forecast, cfg: dict, show_hourly: bool, show_daily: bool,
                show_alerts: bool, days: int, hourly_hours: int) -> str:
    u = cfg["units"]

    def _cur(c) -> dict[str, Any] | None:
        if not c:
            return None
        return {
            "time": c.time.isoformat() if c.time else None,
            "condition": c.condition,
            "temperature": U.c_to(c.temperature, u['temperature']),
            "temperature_unit": u['temperature'],
            "apparent": U.c_to(c.apparent, u['temperature']),
            "humidity_pct": c.humidity,
            "wind_speed": U.mps_to(c.wind_speed, u['wind']),
            "wind_unit": u['wind'],
            "wind_direction_deg": c.wind_direction,
            "wind_gust": U.mps_to(c.wind_gust, u['wind']),
            "pressure": U.hpa_to(c.pressure, u['pressure']),
            "pressure_unit": u['pressure'],
            "visibility": U.meters_to(c.visibility, u['visibility']),
            "visibility_unit": u['visibility'],
            "cloud_cover_pct": c.cloud_cover,
        }

    def _h(p: HourlyPeriod) -> dict[str, Any]:
        return {
            "time": p.time.isoformat(),
            "temperature": U.c_to(p.temperature, u['temperature']),
            "wind_speed": U.mps_to(p.wind_speed, u['wind']),
            "wind_direction_deg": p.wind_direction,
            "precip": U.mm_to(p.precipitation, u['precipitation']),
            "precip_probability_pct": p.precip_probability,
            "humidity_pct": p.humidity,
            "condition": p.condition,
        }

    def _d(d: DailyPeriod) -> dict[str, Any]:
        return {
            "date": d.date.date().isoformat() if d.date else None,
            "temp_min": U.c_to(d.temp_min, u['temperature']),
            "temp_max": U.c_to(d.temp_max, u['temperature']),
            "precip": U.mm_to(d.precipitation, u['precipitation']),
            "precip_probability_pct": d.precip_probability,
            "wind_speed_max": U.mps_to(d.wind_speed_max, u['wind']),
            "condition": d.condition,
            "summary": d.summary,
        }

    payload = {
        "location": {"label": fc.location_label, "lat": fc.lat, "lon": fc.lon},
        "provider": fc.provider,
        "current": _cur(fc.current),
        "hourly": [_h(p) for p in fc.hourly[:hourly_hours]] if show_hourly else [],
        "daily": [_d(d) for d in fc.daily[:days]] if show_daily else [],
        "alerts": [
            {"event": a.event, "severity": a.severity, "headline": a.headline,
             "description": a.description, "instruction": a.instruction}
            for a in fc.alerts
        ] if show_alerts else [],
        "attribution": fc.attribution,
    }
    return jsonlib.dumps(payload, indent=2, default=str)


def render(fc: Forecast, cfg: dict, *, style: str, show_hourly: bool, show_daily: bool,
           show_alerts: bool, days: int, hourly_hours: int) -> str:
    fn = {
        "rich": render_rich,
        "table": render_table,
        "plain": render_plain,
        "json": render_json,
    }.get(style, render_rich)
    return fn(fc, cfg, show_hourly, show_daily, show_alerts, days, hourly_hours)
