"""Renderers for METAR/TAF output (raw and decoded)."""
from __future__ import annotations

import json as jsonlib
from dataclasses import asdict
from datetime import datetime

from .providers.aviationweather import MetarReport, TafForecastPeriod, TafReport


def _fmt_dt(t: datetime | None) -> str:
    return t.strftime("%Y-%m-%d %H:%MZ") if t else "—"


def _wind_str(d, spd, gust) -> str:
    if spd is None and d is None:
        return "—"
    direction = "VRB" if d == "VRB" or d is None else f"{int(d):03d}°"
    base = f"{direction} @ {spd or 0:.0f} kt"
    if gust:
        base += f" gust {gust:.0f} kt"
    return base


def _clouds_str(clouds: list[dict]) -> str:
    if not clouds:
        return "—"
    parts = []
    for c in clouds:
        cover = c.get("cover", "?")
        base = c.get("base")
        typ = c.get("type") or ""
        suffix = typ if typ else ""
        if base is None:
            parts.append(f"{cover}{suffix}")
        else:
            parts.append(f"{cover}{suffix} @ {int(base):,} ft")
    return ", ".join(parts)


def _vis_str(v) -> str:
    if v is None or v == "":
        return "—"
    if isinstance(v, (int, float)):
        return f"{v} SM"
    s = str(v)
    if s.endswith("+"):
        return f"{s[:-1]}+ SM"
    return f"{s} SM"


# ─── METAR ────────────────────────────────────────────────────────────────
def render_metar_raw(m: MetarReport) -> str:
    return m.raw


def render_metar_decoded(m: MetarReport) -> str:
    out = [
        f"METAR  {m.icao}" + (f"  {m.name}" if m.name else ""),
        f"  observed   {_fmt_dt(m.observed)}",
    ]
    if m.flight_cat:
        out.append(f"  category   {m.flight_cat}")
    out.append(f"  wind       {_wind_str(m.wind_dir, m.wind_speed_kt, m.wind_gust_kt)}")
    out.append(f"  visibility {_vis_str(m.visibility)}")
    if m.wx_string:
        out.append(f"  weather    {m.wx_string}")
    out.append(f"  clouds     {_clouds_str(m.clouds)}")
    if m.temp_c is not None or m.dewp_c is not None:
        t = f"{m.temp_c:.0f}°C" if m.temp_c is not None else "—"
        d = f"{m.dewp_c:.0f}°C" if m.dewp_c is not None else "—"
        out.append(f"  temp/dewp  {t} / {d}")
    if m.altimeter_hpa is not None:
        inhg = m.altimeter_hpa * 0.02953
        out.append(f"  altimeter  {inhg:.2f} inHg  ({m.altimeter_hpa:.0f} hPa)")
    if m.slp_hpa is not None:
        out.append(f"  SLP        {m.slp_hpa:.1f} hPa")
    out.append("")
    out.append(f"  raw  {m.raw}")
    return "\n".join(out)


# ─── TAF ──────────────────────────────────────────────────────────────────
def render_taf_raw(t: TafReport) -> str:
    return t.raw


def _period_label(p: TafForecastPeriod, is_first: bool) -> str:
    if p.change == "FM":
        return f"FM {_fmt_dt(p.time_from)}"
    if p.change == "BECMG":
        return f"BECMG {_fmt_dt(p.time_from)} → {_fmt_dt(p.time_to)}"
    if p.change == "PROB":
        return f"PROB{p.probability or 0} {_fmt_dt(p.time_from)} → {_fmt_dt(p.time_to)}"
    if p.change == "TEMPO":
        return f"TEMPO {_fmt_dt(p.time_from)} → {_fmt_dt(p.time_to)}"
    return f"{'INITIAL' if is_first else 'PERIOD'} {_fmt_dt(p.time_from)} → {_fmt_dt(p.time_to)}"


def render_taf_decoded(t: TafReport) -> str:
    out = [
        f"TAF  {t.icao}" + (f"  {t.name}" if t.name else ""),
        f"  issued     {_fmt_dt(t.issued)}",
        f"  valid      {_fmt_dt(t.valid_from)} → {_fmt_dt(t.valid_to)}",
    ]
    if t.remarks:
        out.append(f"  remarks    {t.remarks}")
    out.append("")
    for i, p in enumerate(t.forecasts):
        out.append(f"  {_period_label(p, i == 0)}")
        out.append(f"    wind       {_wind_str(p.wind_dir, p.wind_speed_kt, p.wind_gust_kt)}")
        out.append(f"    visibility {_vis_str(p.visibility)}")
        if p.wx_string:
            out.append(f"    weather    {p.wx_string}")
        out.append(f"    clouds     {_clouds_str(p.clouds)}")
        if p.wind_shear_hgt_ft is not None:
            out.append(
                f"    wind shear {p.wind_shear_dir or 0:03d}° @ "
                f"{p.wind_shear_spd_kt or 0:.0f} kt at {p.wind_shear_hgt_ft:,} ft"
            )
        out.append("")
    out.append(f"  raw  {t.raw}")
    return "\n".join(out)


# ─── JSON wrapper (only when --style=json) ────────────────────────────────
def _metar_to_dict(m: MetarReport) -> dict:
    d = asdict(m)
    for k in ("observed", "report_time"):
        if d.get(k):
            d[k] = d[k].isoformat()
    return d


def _taf_to_dict(t: TafReport) -> dict:
    d = asdict(t)
    for k in ("issued", "valid_from", "valid_to"):
        if d.get(k):
            d[k] = d[k].isoformat()
    for f in d.get("forecasts", []):
        for k in ("time_from", "time_to"):
            if f.get(k):
                f[k] = f[k].isoformat()
    return d


def render_aviation_json(icao: str, m: MetarReport | None, t: TafReport | None) -> str:
    payload: dict = {"icao": icao}
    if m is not None:
        payload["metar"] = {"raw": m.raw, "decoded": _metar_to_dict(m)}
    if t is not None:
        payload["taf"] = {"raw": t.raw, "decoded": _taf_to_dict(t)}
    return jsonlib.dumps(payload, indent=2, default=str)
