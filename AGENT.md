# AGENT.md

Guidance for AI coding agents (Claude Code, Cursor, Aider, etc.) working in this
repo. Humans should read [README.md](README.md) first.

---

## What this project is

`wx` is a Python CLI that prints weather forecasts and aviation observations to
the terminal. It routes each location to the best regional API instead of using
a single global model.

- **Language**: Python 3.11+ (project pins `requires-python = ">=3.11"`)
- **Dependencies**: `requests` only (runtime); `pytest` for tests
- **Package manager**: `uv` (lockfile committed)
- **Entry point**: `wx.cli:main` → console script `wx`
- **Distribution**: single source tree, hatchling build backend

---

## Repository map

```
wx/
├── __init__.py              # exports __version__
├── cli.py                   # argparse + dispatch; the only place argv touches
├── model.py                 # canonical dataclasses (Forecast, CurrentConditions, …)
├── units.py                 # SI ↔ display unit conversions (single source of truth)
├── settings.py              # TOML config loader, default values, write template
├── geocode.py               # Open-Meteo name → (lat, lon)
├── router.py                # (lat, lon) → "nws" | "dwd" | "metno"
├── render.py                # forecast renderers: rich | table | plain | json
├── aviation_render.py       # METAR/TAF renderers: raw | decoded | json
└── providers/
    ├── nws.py               # api.weather.gov adapter
    ├── dwd.py               # Bright Sky (DWD) adapter
    ├── metno.py             # api.met.no adapter
    └── aviationweather.py   # aviationweather.gov METAR/TAF adapter

tests/
└── test_aviationweather.py  # pytest unit tests with mocked HTTP

test_integration.py          # script-style end-to-end with mocked HTTP
pyproject.toml
uv.lock
README.md
AGENT.md                     # this file
```

---

## Architecture invariants

These rules keep the codebase predictable. Follow them when adding features.

### 1. Providers return canonical SI units, renderers convert

Every forecast adapter in `wx/providers/` MUST normalize to the canonical types
in `wx/model.py`:

- temperature → °C
- wind speed → m/s
- pressure → hPa
- precipitation → mm
- visibility → meters
- direction → degrees (0=N, 90=E)
- percentages → 0–100

Display conversion happens **only** in `wx/render.py` via helpers in
`wx/units.py`. Never convert inside an adapter, and never inline a conversion
constant in a renderer — use `units.U.hpa_to(...)` etc.

**Aviation is the exception**: METAR/TAF are domain-specific, so
`aviationweather.py` keeps native aviation units (knots, statute miles, feet,
hPa for altimeter) and `aviation_render.py` formats them directly. This is
intentional — pilots expect aviation units.

### 2. The CLI is the only argv consumer

`wx/cli.py` owns all `argparse` definitions and all `print(...)` calls.
Providers and renderers must be pure: they take inputs, return values, raise
on errors. No `sys.argv`, no `print`, no `sys.exit` outside `cli.py`.

### 3. Errors propagate as typed exceptions; CLI translates to exit codes

- Adapters raise `requests.RequestException` for transport issues or a custom
  `*Error` (e.g. `AviationWeatherError`, `GeocodeError`) for semantic failures.
- `cli.py` catches them, prints `wx: <message>` to stderr, returns a non-zero
  exit code.
- Exit codes: `0` success, `1` runtime/data error, `2` usage error.
- `--debug` re-raises so the traceback prints.

### 4. URLs are built with `params=`, not f-strings

Always pass query parameters via `requests.get(url, params={...})`. Never
interpolate user input into a URL string — even ICAO codes that look safe.
See `wx/providers/aviationweather.py:_get_json` for the pattern.

### 5. The fallback chain is the routing safety net

If a regional provider fails, `cli._fetch_with_fallback` retries with met.no.
Don't add provider-specific retry logic inside adapters; raise and let the
fallback handle it. Aviation mode short-circuits this entirely (no fallback —
aviationweather.gov is the only source for METAR/TAF).

### 6. Settings are deep-merged with defaults

`settings.load()` returns a dict obtained by deep-merging the user's TOML
over `DEFAULTS`. Never read settings directly from disk elsewhere. When
adding a new setting:

1. Add it to `DEFAULTS` in `settings.py` with a sensible value
2. Add it to the `TEMPLATE` string (commented if optional)
3. Document it in the README's "Settings file" section

### 7. Output styles are a closed enum

`{rich, table, plain, json}`. If you add a new style, update:

- `argparse` choices in `cli.py`
- the dispatcher dict in `render.render`
- the README

Aviation mode also respects `--style=json`; non-json styles use the raw/decoded
distinction instead.

### 8. One canonical version string

`wx/__init__.py:__version__` is the source of truth. `pyproject.toml` mirrors
it. The example User-Agent in `README.md` and the `TEMPLATE` in `settings.py`
display the major.minor only. Bump all four together.

---

## Adding a new forecast provider

1. Create `wx/providers/<name>.py` with a `fetch(lat, lon, label, ua, timeout)
   -> Forecast` function.
2. Normalize all units to SI (see invariant #1).
3. Add the provider name to `router.Provider` literal and the `pick()` logic
   if it should be auto-selected.
4. Wire it into `cli._fetch_with_fallback` and the `--provider` argparse
   choices.
5. Add a row to the routing table in `README.md`.
6. Add fixtures + tests to `test_integration.py` (script-style) or a new
   `tests/test_<name>.py` (pytest-style).

---

## Conventions

- **Imports**: standard library, then third-party, then local (`from . import …`).
  No wildcard imports.
- **Types**: prefer modern syntax (`X | None`, not `Optional[X]`; `list[X]`,
  not `List[X]`). The project is 3.11+, so `from __future__ import annotations`
  is at the top of every module and `typing.Optional` should not be imported.
- **Dataclasses** for structured data; plain dicts only for config and raw API
  payloads.
- **Docstrings**: module-level docstring summarizing what the file does. Avoid
  function docstrings unless behavior is non-obvious. Never write Sphinx-style
  parameter lists.
- **Comments**: explain *why* when the *what* isn't obvious from naming. Don't
  narrate code.
- **Error messages**: lowercase, no trailing punctuation, prefixed with `wx:`
  when emitted from the CLI.
- **Naming**: snake_case for functions/variables, PascalCase for classes,
  SCREAMING_SNAKE for module-level constants.

---

## Testing

Two test layers, both with mocked HTTP — there must be **no network access**
in tests.

### Unit tests (pytest)

Location: `tests/`. Run with:

```bash
uv run pytest
```

Style: one file per module-under-test, `test_<feature>` functions, fixtures
inline at the top of the file. Use `unittest.mock.patch` to stub
`requests.get`. See `tests/test_aviationweather.py` for the pattern.

### Integration tests (script-style)

`test_integration.py` exercises the full CLI for every renderer + every
provider + every unit preset with canned HTTP responses. Run with:

```bash
uv run python test_integration.py
```

Both must pass before commits. When adding a new provider or major feature,
extend both layers.

### What to test

- Happy path: a realistic API response → expected Forecast/output.
- Edge cases: missing fields, `None` values, multi-record responses, unit
  variants ("F" vs "C", "10+" vs `6` for visibility).
- Error paths: 204, 404, malformed JSON, network failure.
- Renderer regressions: bugs found in code review should get a test that
  would have caught them (see commit history for examples).

---

## Code review checklist (when reviewing or self-reviewing)

- [ ] Adapter normalizes to SI; renderer handles display units
- [ ] URLs use `params=` dict, not f-string interpolation
- [ ] No `print` or `sys.exit` outside `cli.py`
- [ ] `None` handled explicitly with `is None`, not via falsy `or` chains
  (especially for numeric fields where `0` is valid — wind direction 0°,
  wind speed 0 kt, etc.)
- [ ] Modern typing (`X | None`, `list[X]`)
- [ ] Tests cover the new code path
- [ ] README updated if the public CLI surface changed
- [ ] Version bumped in both `pyproject.toml` and `wx/__init__.py` if shipping

---

## What NOT to do

- **Don't add async**. The CLI is synchronous and one-shot; aiohttp adds
  complexity without benefit.
- **Don't add a TUI**. `wx` is line-oriented, pipe-friendly, and CI-friendly.
- **Don't introduce a runtime dep** without strong justification. Every dep
  is a portability tax.
- **Don't add caching**. Users get a fresh forecast on every invocation by
  design. If a user wants caching, they can wrap `wx` in shell.
- **Don't add API keys** without making them optional and documenting the
  fallback. Current providers are all keyless on purpose.
- **Don't write to disk** outside of `settings.py`'s template creation.
- **Don't add new files without a clear reason**. Prefer editing an existing
  module. New features usually fit in `cli.py` + one provider/render module.

---

## Useful commands

```bash
# Run from source without installing
uv run wx Denver
uv run wx -mt KORD --decode

# Install as a global tool (isolated venv)
uv tool install .

# Upgrade after editing
uv tool upgrade wx

# Tests
uv run pytest                       # unit tests
uv run python test_integration.py   # end-to-end script

# Inspect config location
uv run wx --config-path
```

---

## Release process

1. Bump `version` in `pyproject.toml` and `__version__` in `wx/__init__.py`
   (keep in sync).
2. Update the example User-Agent in `README.md` and `settings.py:TEMPLATE`
   if major or minor changed.
3. **Update `CHANGELOG.md`**: add a new `## [X.Y.Z] — YYYY-MM-DD` section
   above the previous release. Group entries under the
   [Keep a Changelog](https://keepachangelog.com/) headings
   (`Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`,
   `Internal`). Add a matching link reference at the bottom of the file
   (`[X.Y.Z]: https://github.com/aeroperf/wx/releases/tag/vX.Y.Z`).
4. Run `uv run pytest` and `uv run python test_integration.py`.
5. Update README if any user-facing flag/behavior changed.
6. Commit with a clear message describing the change.
7. Push.

### What belongs in the changelog

- User-visible behavior changes (new flags, removed flags, changed defaults).
- Bug fixes that affect output or correctness.
- Architectural changes worth noting under `Internal` (new modules, typing
  migrations, dropped dependencies).

What doesn't: refactors with no behavior change, test-only changes,
formatting tweaks, doc typos. If you're unsure, err on the side of
including it under `Internal` rather than leaving it out.
