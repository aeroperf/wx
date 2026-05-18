"""Settings file management.

Config lives at:
  - macOS/Linux: ~/.config/wx/config.toml
  - Windows: %APPDATA%\\wx\\config.toml

Falls back to ~/.wx.toml if neither dir is writable.
"""
from __future__ import annotations
import os
import sys
import tomllib
from pathlib import Path
from typing import Any


DEFAULTS: dict[str, Any] = {
    "units": {
        "temperature": "C",       # C | F | K
        "wind": "kt",             # kt | mph | kph | mps
        "pressure": "inHg",       # inHg | hPa | mb | mmHg
        "precipitation": "in",    # in | mm
        "visibility": "mi",       # mi | km
    },
    "display": {
        "style": "rich",          # rich | table | plain | json
        "color": True,
        "icons": True,
    },
    "forecast": {
        "days": 3,                # default number of forecast days
        "hourly_hours": 12,       # default hourly horizon
    },
    "api": {
        # NWS REQUIRES contact info in User-Agent. Edit this in your config.
        "user_agent": "wx/0.1 (https://example.com; you@example.com)",
        "timeout": 15,
    },
    "location": {
        "default": "",            # default city/coords if none provided
    },
    "locations": {},              # aliases: e.g. "home" = "lat,lon" -> wx home
}


def config_dir() -> Path:
    """Return platform-appropriate config directory (creating it if needed)."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        p = Path(base) / "wx"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        p = Path(xdg) / "wx" if xdg else Path.home() / ".config" / "wx"
    try:
        p.mkdir(parents=True, exist_ok=True)
        return p
    except OSError:
        return Path.home()


def config_path() -> Path:
    d = config_dir()
    primary = d / "config.toml"
    if primary.exists():
        return primary
    legacy = Path.home() / ".wx.toml"
    if legacy.exists():
        return legacy
    return primary


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Merge overlay into base recursively, returning a new dict."""
    out = dict(base)
    for k, v in overlay.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load() -> dict[str, Any]:
    """Load config, merging with defaults. Creates a template on first run."""
    path = config_path()
    if not path.exists():
        write_template(path)
        return dict(DEFAULTS)
    try:
        with open(path, "rb") as f:
            user = tomllib.load(f)
    except Exception as e:
        print(f"warning: could not parse {path}: {e}", file=sys.stderr)
        return dict(DEFAULTS)
    return _deep_merge(DEFAULTS, user)


TEMPLATE = """# wx CLI configuration
# Edit and save. Run `wx --config-path` to see this file's location.

[units]
temperature   = "C"      # C | F | K
wind          = "kt"     # kt | mph | kph | mps
pressure      = "inHg"   # inHg | hPa | mb | mmHg
precipitation = "in"     # in | mm
visibility    = "mi"     # mi | km

[display]
style  = "rich"          # rich | table | plain | json
color  = true
icons  = true

[forecast]
days         = 3
hourly_hours = 12

[api]
# NWS REQUIRES a descriptive User-Agent with contact info.
# met.no also requires a non-generic User-Agent.
user_agent = "wx/0.1 (https://example.com; you@example.com)"
timeout    = 15

[location]
default = ""             # e.g. "Denver" or "39.74,-105.0"

# Named location aliases. Call as `wx <name>`.
# Value can be a city name (geocoded) or "lat,lon" pair.
[locations]
# home = "39.74,-105.0"
# work = "Denver, CO"
"""


def write_template(path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(TEMPLATE)
    except OSError as e:
        print(f"warning: could not write template {path}: {e}", file=sys.stderr)
