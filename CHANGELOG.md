# Changelog

All notable changes to `wx` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] — 2026-05-18

Quality pass on the 1.1.0 aviation feature: bug fixes, hardening, and a
real test suite. No public CLI surface changed beyond the broadened
station-ID validator.

### Added
- Pytest suite under [tests/](tests/) (29 tests) covering parser, renderers,
  and CLI integration for METAR/TAF, with mocked HTTP fixtures.
- [AGENT.md](AGENT.md) — architecture invariants and conventions for AI
  coding agents.
- TAF rendering now handles combined change codes like `PROB30 TEMPO`.
- TAF wind-shear groups are now rendered when present.

### Changed
- Station-ID validator accepts alphanumeric identifiers (e.g. `K1G3`, `0R0`)
  instead of alpha-only, matching FAA conventions.
- Multi-record responses now prefer `mostRecent=1`, falling back to the
  newest observation/issue time, instead of positional `[0]`.
- HTTP requests use `params={...}` dicts instead of f-string URL building —
  defense in depth against injection.
- Wind-direction `0°` and wind-speed `0 kt` are no longer treated as missing
  (explicit `is not None` checks instead of falsy `or` chains).
- `wx.units` is the single source for the inHg conversion factor; the
  hardcoded `0.02953` constant was removed from the aviation renderer.
- Location-alias lookups in `[locations]` are now case-insensitive.
- `--days 0` and `--hours 0` are respected instead of falling through to
  config defaults.
- JSON output: `raw` no longer duplicated inside the `decoded` block.

### Fixed
- `PROB` change groups with `None` probability no longer render as `PROB0`.
- Visibility renderer: removed dead code that stripped and re-appended `+`.
- Wind shear with `None` direction no longer prints a misleading `000°`.
- Extra positional arguments after the ICAO code now produce a warning
  instead of being silently ignored.

### Internal
- Dropped `typing.Optional` in favor of `X | None`.
- Added `WindDir = int | Literal["VRB"] | None` type alias.
- Inlined the trivial `_round` helper in the NWS provider.
- Documented aviationweather.gov field semantics in the provider docstring.

## [1.1.0] — 2026-05-18

### Added
- METAR and TAF for airports via [aviationweather.gov](https://aviationweather.gov/data/api/).
- New flags: `-m`/`--metar`, `-t`/`--taf`, `--decode`, `--metar-hours`.
- New module [wx/providers/aviationweather.py](wx/providers/aviationweather.py)
  with `MetarReport`, `TafReport`, `TafForecastPeriod` dataclasses.
- New module [wx/aviation_render.py](wx/aviation_render.py) for raw/decoded
  output and JSON wrapping.
- Aviation mode short-circuits forecast routing — flags like `-H`, `-d`,
  `-A`, `--provider` are ignored when `-m`/`-t` is set.

### Changed
- Default aviation output is the raw, standard-format METAR/TAF string —
  the form pilots and dispatchers expect. `--decode` formats winds, clouds,
  change groups (FM/BECMG/PROB/TEMPO), and validity windows.

## [1.0.1] — 2026-05-18

### Fixed
- NWS station observations frequently omit `textDescription` and `icon`,
  leaving the rich view with no condition label and blank ASCII art. The
  current-conditions block now backfills from the first hourly forecast
  period so users see the actual condition (e.g. "Light Rain") and matching
  art.

## [1.0.0] — 2026-05-18

First stable release. Correctness pass plus expanded routing.

### Added
- Canary Islands sub-box routed to DWD/Bright Sky (Spanish territory off the
  Moroccan coast).
- `[locations]` alias table documented in the README — users can define
  `home = "39.74,-105.0"` and call `wx home`.

### Fixed
- `XDG_CONFIG_HOME=""` (empty string) no longer produces a relative config
  path.
- `0%` precipitation probability and `0.0` apparent temperature are no
  longer dropped via truthiness checks.
- Unit suffix dict keys are normalized to lowercase to match `.lower()`
  lookups.
- Self-caught `SystemExit` in the provider fallback chain replaced with
  `RuntimeError`.

## [0.x] — 2026-05-18

Initial commit. Three forecast providers (NWS, DWD via Bright Sky, met.no)
with auto-routing by coordinate bounding box, four output styles (rich,
table, plain, json), four unit presets, Open-Meteo geocoding, TOML config.

[1.2.0]: https://github.com/aeroperf/wx/releases/tag/v1.2.0
[1.1.0]: https://github.com/aeroperf/wx/releases/tag/v1.1.0
[1.0.1]: https://github.com/aeroperf/wx/releases/tag/v1.0.1
[1.0.0]: https://github.com/aeroperf/wx/releases/tag/v1.0.0
