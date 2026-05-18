# wx

A terminal weather tool that gets you the *best* regional forecast instead of
defaulting to one global model:

| Region | API | Quality notes |
|---|---|---|
| CONUS, AK, HI, PR, USVI, Guam, Samoa | **NWS** (`api.weather.gov`) | Direct from US forecasters; includes detailed text forecasts and active alerts. |
| Europe & nearby | **DWD** via Bright Sky (`api.brightsky.dev`) | DWD's MOSMIX is excellent for Europe; Bright Sky surfaces it cleanly. |
| Everywhere else | **met.no** (`api.met.no/locationforecast`) | Norway's MET, also used as fallback if a regional API fails. |
| Airports (worldwide) | **aviationweather.gov** | Official US NWS Aviation Weather Center. METAR + TAF by ICAO code. |

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
wx --afd Denver         # include NWS Area Forecast Discussion (US only)

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

### Example output

US location — routed to NWS, includes active alerts when present:

```
$ wx -c Denver
Denver, Colorado, United States  (39.7392, -104.9847) via NWS

    .-.        Light Rain and Fog/Mist
   (   ).        6 °C  feels 5 °C
  (___(__)       E 4 kt
   ' ' ' '       94 %  29.82 inHg
  ' ' ' '        vis 8 mi

⚠ Active alerts:
  Freeze Watch — Freeze Watch issued May 17 at 10:59PM MDT
    until May 19 at 8:00AM MDT by NWS Denver CO
    expires 2026-05-18 14:00 UTC-06:00

data: US NOAA/NWS (api.weather.gov)
```

NWS multi-day forecast — daily highs/lows plus the NWS forecaster's
written narrative for each period:

```
$ wx -d 5 Denver
Denver, Colorado, United States  (39.7392, -104.9847) via NWS

    .-.        Light Rain and Fog/Mist
   (   ).        6 °C  feels 5 °C
  (___(__)       E 4 kt
   ' ' ' '       94 %  29.82 inHg
  ' ' ' '        vis 8 mi

⚠ Active alerts:
  Freeze Watch — Freeze Watch issued May 17 at 10:59PM MDT
    until May 19 at 8:00AM MDT by NWS Denver CO
    expires 2026-05-18 14:00 UTC-06:00

Daily
  Mon May 18       8 °C / 2 °C     Rain Showers • 97% precip • wind 13 kt
    Rain showers before noon, then showers and thunderstorms. Cloudy.
    High near 46, with temperatures falling to around 42 in the
    afternoon. North northeast wind 8 to 15 mph, with gusts as high as
    28 mph. Chance of precipitation is 100%. New rainfall amounts
    between a half and three quarters of an inch possible.
  Tue May 19      10 °C / 4 °C     Mostly Cloudy then Rain Showers Likely • 75% precip • wind 6 kt
    Rain showers likely after noon. Mostly cloudy, with a high near 50.
    Northeast wind 2 to 7 mph, with gusts as high as 16 mph. Chance of
    precipitation is 60%.
  Wed May 20      17 °C / 5 °C     Partly Sunny then Showers And Thunderstorms Likely • 73% precip • wind 6 kt
    Showers and thunderstorms likely after noon. Partly sunny, with a
    high near 62. Chance of precipitation is 70%.
  Thu May 21      21 °C / 7 °C     Mostly Sunny then Chance Showers And Thunderstorms • 44% precip • wind 7 kt
    A chance of showers and thunderstorms after noon. Mostly sunny, with
    a high near 69.
  Fri May 22      22 °C / 8 °C     Mostly Sunny then Slight Chance Showers And Thunderstorms • 22% precip • wind 6 kt
    A slight chance of showers and thunderstorms after noon. Mostly
    sunny, with a high near 71.

data: US NOAA/NWS (api.weather.gov)
```

European location — routed to DWD via Bright Sky:

```
$ wx -c Berlin
Berlin, State of Berlin, Germany  (52.5244, 13.4105) via DWD

    \   /      dry
     .-.         18 °C
  ― (   ) ―      ESE 8 kt, gust 13 kt
     `-'         48 %  29.99 inHg
    /   \        vis 23 mi  cloud 88 %

data: Deutscher Wetterdienst via Bright Sky (brightsky.dev)
```

Anywhere else — routed to met.no (Norwegian Meteorological Institute):

```
$ wx -c "Phuket, Thailand"
Phuket, Phuket, Thailand  (7.8906, 98.3981) via METNO

    .-.        Light rain
   (   ).        28 °C
  (___(__)       WNW 17 kt
   ' ' ' '       79 %  29.72 inHg
  ' ' ' '        vis —  cloud 100 %

data: MET Norway (api.met.no, CC BY 4.0)
```

Table style — same data, no ASCII art, easy to scan or pipe:

```
$ wx --style table -d 5 Denver
Denver, Colorado, United States  (39.7392, -104.9847)  via NWS

CURRENT
  condition      Light Rain and Fog/Mist
  temperature    6 °C
  feels like     5 °C
  humidity       94%
  wind           E 4 kt
  pressure       29.82 inHg
  visibility     8 mi

DAILY
  day               high     low    precip  condition
  Mon May 18        8 °C    2 °C       97%  Rain Showers
  Tue May 19       10 °C    4 °C       75%  Mostly Cloudy then Rain Showers Likely
  Wed May 20       17 °C    5 °C       73%  Partly Sunny then Showers And Thunderstorms Likely
  Thu May 21       21 °C    7 °C       44%  Mostly Sunny then Chance Showers And Thunderstorms
  Fri May 22       22 °C    8 °C       22%  Mostly Sunny then Slight Chance Showers And Thunderstorms

data: US NOAA/NWS (api.weather.gov)
```

Raw METAR — the form pilots and dispatchers expect:

```
$ wx -m KORD
METAR KORD 180951Z 19014G25KT 10SM FEW050 BKN070 BKN180 BKN250 24/15
  A2981 RMK AO2 PK WND 19027/0934 SLP089 T02390150 $
```

Raw TAF:

```
$ wx -t KORD
TAF KORD 180909Z 1809/1912 19014G24KT P6SM SCT060 BKN100
  FM181100 17011KT 6SM -SHRA SCT035 OVC060
  TEMPO 1811/1814 27018G28KT 3SM -TSRA BKN035CB
  FM181400 16015G26KT 6SM -SHRA VCTS BKN040CB OVC080
  FM181800 21014G24KT P6SM SCT050 BKN100
  FM190200 19011G20KT P6SM FEW060 BKN200
  FM191000 22013G22KT P6SM SCT040 OVC060
  PROB30 1910/1912 4SM -SHRA BKN035
```

(The actual METAR/TAF is emitted as a single line; line breaks above are
for readability. Use `--decode` for a pretty-printed multi-line form.)

### METAR & TAF for airports

Aviation observations and forecasts by 4-character station identifier,
sourced from [aviationweather.gov](https://aviationweather.gov/data/api/).
Works worldwide with ICAO codes (KORD, EGLL, RJTT, SBGR, …) as well as
FAA identifiers that include digits (e.g. K1G3, 0R0).

```bash
wx -m KORD              # raw METAR
wx -t KORD              # raw TAF
wx -mt KORD             # raw METAR + TAF
wx -mt KORD --decode    # decoded / pretty-printed
wx -m KORD --metar-hours 12   # widen METAR look-back window
wx -mt KORD --style json      # structured JSON (raw + decoded fields)
```

Default output is the raw, standard-format METAR/TAF string — the form
pilots and dispatchers expect. `--decode` formats winds, clouds, change
groups (FM/BECMG/PROB/TEMPO), and validity windows as a readable block.

The aviation mode short-circuits forecast routing — flags like `-H`, `-d`,
`-A`, `--provider`, etc. are ignored when `-m` or `-t` is set.

> **Not for operational use.** METAR/TAF data is sourced from
> `aviationweather.gov` and re-displayed as-is, but this tool is not an
> approved aviation weather briefing source. Pilots and dispatchers
> must consult an official briefing service (e.g. 1800wxbrief.com,
> ForeFlight, or your national AIS) before flight. No warranty is
> made as to accuracy, completeness, or timeliness.

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
user_agent = "wx/1.2 (https://example.com; you@example.com)"
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

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release notes.

## Development

```bash
# install deps including dev group (pytest)
uv sync

# run the unit tests (pytest)
uv run pytest

# run the end-to-end integration script
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
- NWS Aviation Weather Center (`aviationweather.gov`) — public domain.
- Geocoding by [Open-Meteo](https://open-meteo.com) (CC BY 4.0).

The attribution line is printed at the bottom of each forecast.
