"""wx - a high-quality CLI for weather forecasts.

Routes:
  - US (CONUS, AK, HI, PR, USVI, GU) -> NWS (api.weather.gov)
  - Europe                            -> DWD via Brightsky (api.brightsky.dev)
  - Global fallback                   -> met.no Locationforecast 2.0

Geocoding via Open-Meteo (free, no key).
"""
__version__ = "1.2.1"
