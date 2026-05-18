# wx

A terminal weather tool that gets you the *best* regional forecast instead of
defaulting to one global model:

| Region | API | Quality notes |
|---|---|---|
| CONUS, AK, HI, PR, USVI, Guam, Samoa | **NWS** (`api.weather.gov`) | Direct from US forecasters; includes detailed text forecasts and active alerts. |
| Europe & nearby | **DWD** via Bright Sky (`api.brightsky.dev`) | DWD's MOSMIX is excellent for Europe; Bright Sky surfaces it cleanly. |
| Everywhere else | **met.no** (`api.met.no/locationforecast`) | Norway's MET, also used as fallback if a regional API fails. |

No API keys required. Pure Python; runs on macOS, Windows, Linux.

## Install with uv (recommended)

[uv](https://docs.astral.sh/uv/) is the fastest install path. It handles Python
versions, virtualenvs, and PATH setup automatically — no system Python required.

**Mac (with Homebrew):**
```bash
brew install uv
```

**Mac/Linux (universal):**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then from inside this directory:

```bash
uv tool install .
```

That puts `wx` on your PATH in an isolated environment with its own pinned
Python. To upgrade later after editing the code:

```bash
uv tool upgrade wx
```

To uninstall:

```bash
uv tool uninstall wx
```

### Alternative: run without installing

```bash
uv run wx Denver
```

This resolves dependencies and runs the tool in one step using the locked
versions from `uv.lock`. Useful for trying it out, or for one-off use from a
checkout you don't want to install globally.

### Alternative: traditional pip

If you'd rather not use uv:

```bash
pip install .
# or for an isolated install:
pipx install .
```

Requires Python 3.11+.

## Usage

```bash
wx Denver               # city name (geocoded via Open-Meteo)
wx "Berlin"             # quotes optional unless there are spaces
wx "New York, NY"
wx 39.74,-105.0         # raw coordinates (south & west are negative)

wx --hourly Denver      # add an hourly block
wx -d 7 Reykjavik       # 7-day forecast
wx -c Tokyo             # current only
wx -A Miami             # active alerts only

wx --style table Paris
wx --style json Berlin  # machine-readable
wx --no-color Denver    # for pipes/CI

wx -u imperial Boston
wx --temp F --wind mph Boston

wx --provider metno Denver   # force a specific source

wx --config-path        # show the config file location
wx -V                   # version
wx -h                   # full help
```

### Settings file

On first run, a TOML config is created:

- **macOS / Linux**: `~/.config/wx/config.toml` (or `$XDG_CONFIG_HOME/wx/config.toml`)
- **Windows**: `%APPDATA%\wx\config.toml`

Defaults match the brief: °C, knots, inHg, inches.

```toml
[units]
temperature   = "C"
wind          = "kt"
pressure      = "inHg"
precipitation = "in"
visibility    = "mi"

[display]
style  = "rich"      # rich | table | plain | json
color  = true
icons  = true

[forecast]
days         = 3
hourly_hours = 12

[api]
# NWS and met.no both require a descriptive User-Agent with contact info.
# Edit this to your own site/email.
user_agent = "wx/1.0 (https://example.com; you@example.com)"
timeout    = 15

[location]
default = ""        # optional; e.g. "Denver" — used when no location given
```

### Location aliases

Define named shortcuts in the `[locations]` table and call them by name:

```toml
[locations]
home = "39.74,-105.0"
work = "Denver, CO"
mom  = "Reykjavik"
```

```bash
wx home          # uses the coords above
wx work          # geocodes "Denver, CO"
```

Values can be either `"lat,lon"` pairs (skip geocoding) or place names.

### Important: edit the User-Agent

NWS and met.no will throttle or 403 requests with a generic User-Agent. Open
the config file (`wx --config-path` shows where it is) and put a real
contact (website or email) in `api.user_agent` before heavy use.

## Routing logic

By default, the provider is chosen by coordinate bounding boxes:

- US NWS coverage: CONUS, Alaska (incl. Aleutian wrap), Hawaii, Puerto Rico,
  USVI, Guam, Northern Marianas, American Samoa.
- Europe: rough box from −25°W to 45°E, 34°N to 72°N, plus a sub-box for
  the Canary Islands (Spanish territory off the Moroccan coast).
- Everything else: met.no.

If a regional API fails (network error, 404, etc.), the tool transparently
falls back to met.no.

Override with `--provider {nws,dwd,metno,auto}`.

## Development

```bash
# install deps including dev group (pytest)
uv sync

# run the test suite
uv run python test_integration.py

# run the CLI from source without installing
uv run wx Denver
```

The `uv.lock` file pins exact versions of all transitive dependencies for
reproducible installs across Mac and Windows.

## Data attribution

This tool re-displays public data from:

- US NOAA / National Weather Service — public domain.
- Deutscher Wetterdienst, served via Bright Sky — DWD terms of use apply.
- MET Norway — Norwegian Licence for Open Government Data (NLOD) / CC BY 4.0.

The attribution line is printed at the bottom of each forecast.
