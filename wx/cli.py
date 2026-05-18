"""CLI entry point for `wx`."""
from __future__ import annotations

import argparse
import sys

import requests

from . import __version__, aviation_render, geocode, render, router, settings
from .model import Forecast
from .providers import aviationweather, dwd, metno, nws


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wx",
        description="High-quality weather for your terminal. "
                    "Routes US to NWS, Europe to DWD, elsewhere to met.no.",
        epilog="Examples:\n"
               "  wx Denver\n"
               "  wx 39.74,-105.0\n"
               "  wx Berlin --hourly\n"
               "  wx Reykjavik -d 7 --no-current\n"
               "  wx -m KORD                  # raw METAR\n"
               "  wx -t KORD                  # raw TAF\n"
               "  wx -mt KORD --decode        # decoded METAR + TAF\n"
               "  wx --config-path",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("location", nargs="*", help="city name or 'lat,lon'")

    # forecast scope
    p.add_argument("-c", "--current", action="store_true",
                   help="show current conditions only (default: current + daily)")
    p.add_argument("-H", "--hourly", action="store_true",
                   help="include hourly forecast")
    p.add_argument("-d", "--days", type=int, default=None,
                   help="number of forecast days (default from config)")
    p.add_argument("--hours", type=int, default=None,
                   help="hourly horizon (default from config)")
    p.add_argument("--no-current", action="store_true",
                   help="hide current conditions block")
    p.add_argument("--no-daily", action="store_true",
                   help="hide daily forecast")
    p.add_argument("--no-alerts", action="store_true",
                   help="hide alerts (NWS only)")
    p.add_argument("-A", "--alerts-only", action="store_true",
                   help="show only active alerts")

    # output
    p.add_argument("--style", choices=["rich", "table", "plain", "json"],
                   default=None, help="output style (default from config)")
    p.add_argument("--no-color", action="store_true", help="disable colors")
    p.add_argument("--no-icons", action="store_true", help="disable ASCII art")

    # units overrides (one-shot)
    p.add_argument("-u", "--units",
                   choices=["metric", "imperial", "scientific"],
                   help="quick unit preset (overrides config)")
    p.add_argument("--temp", choices=["C", "F", "K"], help="temperature unit")
    p.add_argument("--wind", choices=["kt", "mph", "kph", "mps"], help="wind unit")
    p.add_argument("--pressure", choices=["inHg", "hPa", "mb", "mmHg"], help="pressure unit")
    p.add_argument("--precip", choices=["in", "mm"], help="precipitation unit")

    # provider override
    p.add_argument("--provider", choices=["auto", "nws", "dwd", "metno"],
                   default="auto", help="force a specific provider")

    # aviation (METAR/TAF for airports by ICAO code)
    p.add_argument("-m", "--metar", action="store_true",
                   help="fetch METAR for ICAO code (e.g. `wx -m KORD`)")
    p.add_argument("-t", "--taf", action="store_true",
                   help="fetch TAF for ICAO code (e.g. `wx -t KORD`)")
    p.add_argument("--decode", action="store_true",
                   help="decode METAR/TAF instead of printing raw text")
    p.add_argument("--metar-hours", type=int, default=6,
                   help="METAR look-back window in hours (default 6)")

    # diagnostics
    p.add_argument("--config-path", action="store_true",
                   help="print path to the config file and exit")
    p.add_argument("--debug", action="store_true", help="print tracebacks on error")
    p.add_argument("-V", "--version", action="version", version=f"wx {__version__}")
    return p


_PRESETS = {
    "metric":     {"temperature": "C", "wind": "kph",  "pressure": "hPa",  "precipitation": "mm", "visibility": "km"},
    "imperial":   {"temperature": "F", "wind": "mph",  "pressure": "inHg", "precipitation": "in", "visibility": "mi"},
    "scientific": {"temperature": "K", "wind": "mps",  "pressure": "hPa",  "precipitation": "mm", "visibility": "km"},
}


def _apply_overrides(cfg: dict, args: argparse.Namespace) -> dict:
    if args.units:
        cfg["units"].update(_PRESETS[args.units])
    if args.temp:
        cfg["units"]["temperature"] = args.temp
    if args.wind:
        cfg["units"]["wind"] = args.wind
    if args.pressure:
        cfg["units"]["pressure"] = args.pressure
    if args.precip:
        cfg["units"]["precipitation"] = args.precip
    if args.style:
        cfg["display"]["style"] = args.style
    if args.no_color:
        cfg["display"]["color"] = False
    if args.no_icons:
        cfg["display"]["icons"] = False
    return cfg


def _fetch_with_fallback(provider: str, lat: float, lon: float, label: str,
                        ua: str, timeout: int, debug: bool) -> Forecast:
    """Try the chosen provider; on failure fall back to met.no."""
    attempts = []
    if provider == "auto":
        attempts = [router.pick(lat, lon), "metno"]
    else:
        attempts = [provider]
        if provider != "metno":
            attempts.append("metno")
    seen = set()
    last_err: Exception | None = None
    for p in attempts:
        if p in seen:
            continue
        seen.add(p)
        try:
            if p == "nws":
                return nws.fetch(lat, lon, label, ua, timeout)
            if p == "dwd":
                return dwd.fetch(lat, lon, label, ua, timeout)
            return metno.fetch(lat, lon, label, ua, timeout)
        except requests.HTTPError as e:
            last_err = e
            if debug:
                print(f"[debug] {p} HTTP error: {e}", file=sys.stderr)
            # NWS returns 404 for non-US coords - silently fall through
            continue
        except requests.RequestException as e:
            last_err = e
            if debug:
                print(f"[debug] {p} request error: {e}", file=sys.stderr)
            continue
    raise RuntimeError(f"all providers failed ({last_err})")


def _is_icao(s: str) -> bool:
    """ICAO/FAA station identifiers are 4 alphanumeric characters."""
    return len(s) == 4 and s.isalnum()


def _run_aviation(args: argparse.Namespace, ua: str, timeout: int, cfg: dict) -> int:
    if not args.location:
        print("wx: -m/-t requires an ICAO code (e.g. `wx -m KORD`).", file=sys.stderr)
        return 2
    if len(args.location) > 1:
        extras = " ".join(args.location[1:])
        print(f"wx: ignoring extra arguments after ICAO: {extras!r}", file=sys.stderr)
    icao = args.location[0].upper()
    if not _is_icao(icao):
        print(f"wx: '{icao}' is not a valid 4-character station ID.", file=sys.stderr)
        return 2

    metar = taf = None
    try:
        if args.metar:
            metar = aviationweather.fetch_metar(icao, ua, timeout, hours=args.metar_hours)
        if args.taf:
            taf = aviationweather.fetch_taf(icao, ua, timeout)
    except aviationweather.AviationWeatherError as e:
        print(f"wx: {e}", file=sys.stderr)
        return 1
    except requests.RequestException as e:
        if args.debug:
            raise
        print(f"wx: aviationweather.gov request failed: {e}", file=sys.stderr)
        return 1

    if cfg["display"]["style"] == "json":
        print(aviation_render.render_aviation_json(icao, metar, taf))
        return 0

    parts: list[str] = []
    if metar is not None:
        parts.append(
            aviation_render.render_metar_decoded(metar) if args.decode
            else aviation_render.render_metar_raw(metar)
        )
    if taf is not None:
        parts.append(
            aviation_render.render_taf_decoded(taf) if args.decode
            else aviation_render.render_taf_raw(taf)
        )
    parts.append(
        "Not for operational use. Consult an official aviation weather "
        "briefing source (e.g. 1800wxbrief.com, ForeFlight, or your "
        "national AIS) before flight."
    )
    print("\n\n".join(parts))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = settings.load()

    if args.config_path:
        print(settings.config_path())
        return 0

    cfg = _apply_overrides(cfg, args)
    ua = cfg["api"]["user_agent"]
    timeout = cfg["api"]["timeout"]

    if settings.is_placeholder_user_agent(ua):
        print(
            "warning: api.user_agent still contains the example.com placeholder. "
            "NWS and met.no require a real contact (website or email) and will "
            "throttle or 403 requests otherwise. Edit "
            f"{settings.config_path()} before heavy use.",
            file=sys.stderr,
        )

    # METAR/TAF short-circuit: positional must be an ICAO code (4 alpha chars)
    if args.metar or args.taf:
        return _run_aviation(args, ua, timeout, cfg)

    if args.location:
        query = " ".join(args.location)
    else:
        query = cfg["location"]["default"]
    if not query:
        print("wx: no location given. Try `wx Denver` or set "
              "[location] default in your config.", file=sys.stderr)
        print(f"config: {settings.config_path()}", file=sys.stderr)
        return 2

    # resolve location alias from [locations] table (e.g. wx home; case-insensitive)
    aliases = {k.lower(): v for k, v in (cfg.get("locations") or {}).items()}
    alias = aliases.get(query.lower())
    if alias:
        query = alias

    try:
        loc = geocode.resolve(query, ua, timeout)
    except geocode.GeocodeError as e:
        print(f"wx: {e}", file=sys.stderr)
        return 1

    try:
        fc = _fetch_with_fallback(args.provider, loc.lat, loc.lon, loc.display,
                                  ua, timeout, args.debug)
    except Exception as e:
        if args.debug:
            raise
        print(f"wx: {e}", file=sys.stderr)
        return 1

    # decide what to show
    if args.alerts_only:
        show_current = show_hourly = show_daily = False
        show_alerts = True
    else:
        show_current = not args.no_current
        show_hourly = args.hourly
        show_daily = not args.no_daily and not args.current
        show_alerts = not args.no_alerts

    days = args.days if args.days is not None else cfg["forecast"]["days"]
    hours = args.hours if args.hours is not None else cfg["forecast"]["hourly_hours"]

    if not show_current and fc.current:
        fc.current = None  # suppress in render

    out = render.render(
        fc, cfg,
        style=cfg["display"]["style"],
        show_hourly=show_hourly,
        show_daily=show_daily,
        show_alerts=show_alerts,
        days=days,
        hourly_hours=hours,
    )
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
