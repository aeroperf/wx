"""End-to-end integration test with mocked HTTP responses.

This validates:
  - geocoding -> coordinates
  - router picks the right provider per region
  - each adapter parses its API response correctly
  - units convert correctly
  - all 4 render styles produce output without errors
"""
import sys
import json
from unittest.mock import patch, MagicMock

sys.path.insert(0, '/home/claude/wx')

# ---- Sample API responses (trimmed real-world shapes) -------------------

GEOCODE_DENVER = {
    "results": [{
        "name": "Denver", "latitude": 39.7392, "longitude": -104.9903,
        "country": "United States", "admin1": "Colorado",
        "timezone": "America/Denver",
    }]
}

GEOCODE_BERLIN = {
    "results": [{
        "name": "Berlin", "latitude": 52.52, "longitude": 13.405,
        "country": "Germany", "admin1": "Berlin",
        "timezone": "Europe/Berlin",
    }]
}

GEOCODE_TOKYO = {
    "results": [{
        "name": "Tokyo", "latitude": 35.6762, "longitude": 139.6503,
        "country": "Japan", "admin1": "Tokyo",
    }]
}

NWS_POINTS = {
    "properties": {
        "forecast": "https://api.weather.gov/gridpoints/BOU/62,61/forecast",
        "forecastHourly": "https://api.weather.gov/gridpoints/BOU/62,61/forecast/hourly",
        "observationStations": "https://api.weather.gov/gridpoints/BOU/62,61/stations",
    }
}

NWS_STATIONS = {
    "features": [{"properties": {"stationIdentifier": "KDEN"}}]
}

NWS_OBS = {
    "properties": {
        "timestamp": "2025-01-15T18:53:00+00:00",
        "textDescription": "Mostly Cloudy",
        "icon": "https://api.weather.gov/icons/land/day/bkn?size=medium",
        "temperature": {"value": 5.0, "unitCode": "wmoUnit:degC"},
        "dewpoint": {"value": -3.0, "unitCode": "wmoUnit:degC"},
        "windDirection": {"value": 270, "unitCode": "wmoUnit:degree_(angle)"},
        "windSpeed": {"value": 18.4, "unitCode": "wmoUnit:km_h-1"},
        "windGust": {"value": 32.4, "unitCode": "wmoUnit:km_h-1"},
        "barometricPressure": {"value": 83000, "unitCode": "wmoUnit:Pa"},
        "visibility": {"value": 16093, "unitCode": "wmoUnit:m"},
        "relativeHumidity": {"value": 55.0, "unitCode": "wmoUnit:percent"},
        "heatIndex": {"value": None, "unitCode": "wmoUnit:degC"},
        "windChill": {"value": 2.0, "unitCode": "wmoUnit:degC"},
    }
}

NWS_HOURLY = {
    "properties": {
        "periods": [
            {
                "startTime": f"2025-01-15T{h:02d}:00:00-07:00",
                "temperature": 40 + h % 5,
                "temperatureUnit": "F",
                "windSpeed": "10 mph",
                "windDirection": "W",
                "probabilityOfPrecipitation": {"value": 20 if h % 3 == 0 else 5},
                "relativeHumidity": {"value": 50},
                "shortForecast": "Partly Cloudy",
                "icon": "https://api.weather.gov/icons/land/day/sct?size=small",
            } for h in range(12, 24)
        ]
    }
}

NWS_FORECAST = {
    "properties": {
        "periods": [
            {"startTime": "2025-01-15T12:00:00-07:00", "isDaytime": True,
             "temperature": 45, "temperatureUnit": "F", "windSpeed": "10 to 15 mph",
             "windDirection": "W", "shortForecast": "Partly Cloudy",
             "detailedForecast": "Partly cloudy with a high near 45. West wind 10 to 15 mph.",
             "probabilityOfPrecipitation": {"value": 20},
             "icon": "https://api.weather.gov/icons/land/day/sct"},
            {"startTime": "2025-01-15T18:00:00-07:00", "isDaytime": False,
             "temperature": 28, "temperatureUnit": "F", "windSpeed": "5 mph",
             "windDirection": "W", "shortForecast": "Clear",
             "detailedForecast": "Mostly clear with a low around 28.",
             "probabilityOfPrecipitation": {"value": 5}},
            {"startTime": "2025-01-16T06:00:00-07:00", "isDaytime": True,
             "temperature": 50, "temperatureUnit": "F", "windSpeed": "5 to 10 mph",
             "windDirection": "SW", "shortForecast": "Sunny",
             "detailedForecast": "Sunny with a high near 50.",
             "probabilityOfPrecipitation": {"value": 0}},
        ]
    }
}

NWS_ALERTS = {
    "features": [
        {"properties": {
            "headline": "Winter Weather Advisory until Jan 15 6 PM MST",
            "severity": "Moderate",
            "event": "Winter Weather Advisory",
            "description": "Snow expected. Travel could be difficult.",
            "instruction": "Slow down and use caution.",
            "onset": "2025-01-15T12:00:00-07:00",
            "expires": "2025-01-15T18:00:00-07:00",
        }}
    ]
}

BS_CURRENT = {
    "weather": {
        "timestamp": "2025-01-15T18:00:00+00:00",
        "temperature": 3.5,
        "dew_point": -1.2,
        "relative_humidity": 72,
        "wind_speed_10": 18.7,        # km/h
        "wind_direction_10": 250,
        "pressure_msl": 1013.2,
        "visibility": 25000,
        "cloud_cover": 80,
        "condition": "rain",
    }
}

BS_WEATHER = {
    "weather": [
        {"timestamp": f"2025-01-15T{h:02d}:00:00+00:00",
         "temperature": 2 + h * 0.5,
         "wind_speed": 15 + h, "wind_direction": 240,
         "precipitation": 0.5 if h % 4 == 0 else 0,
         "precipitation_probability": 60 if h % 4 == 0 else 10,
         "relative_humidity": 75, "cloud_cover": 70,
         "condition": "rain" if h % 4 == 0 else "cloudy",
         } for h in range(0, 24)
    ] + [
        {"timestamp": f"2025-01-16T{h:02d}:00:00+00:00",
         "temperature": 1 + h * 0.4,
         "wind_speed": 12, "wind_direction": 220,
         "precipitation": 0, "precipitation_probability": 5,
         "relative_humidity": 65, "cloud_cover": 30,
         "condition": "dry"} for h in range(0, 24)
    ]
}

METNO_RESPONSE = {
    "properties": {
        "meta": {"units": {"air_temperature": "celsius"}},
        "timeseries": [
            {
                "time": "2025-01-15T18:00:00Z",
                "data": {
                    "instant": {"details": {
                        "air_temperature": 22.4,
                        "dew_point_temperature": 18.0,
                        "relative_humidity": 78,
                        "wind_speed": 4.2,
                        "wind_from_direction": 145,
                        "air_pressure_at_sea_level": 1010.5,
                        "cloud_area_fraction": 50,
                    }},
                    "next_1_hours": {
                        "summary": {"symbol_code": "partlycloudy_day"},
                        "details": {"precipitation_amount": 0.0},
                    },
                    "next_6_hours": {
                        "summary": {"symbol_code": "partlycloudy_day"},
                        "details": {"precipitation_amount": 0.0},
                    },
                },
            },
            *[{
                "time": f"2025-01-15T{h:02d}:00:00Z",
                "data": {
                    "instant": {"details": {
                        "air_temperature": 20 + h * 0.2,
                        "wind_speed": 3 + (h % 5),
                        "wind_from_direction": 140 + h,
                        "relative_humidity": 75,
                        "cloud_area_fraction": 40,
                    }},
                    "next_1_hours": {
                        "summary": {"symbol_code": "rain"},
                        "details": {"precipitation_amount": 0.3 if h % 3 == 0 else 0},
                    },
                },
            } for h in range(19, 24)],
        ],
    }
}


def mock_get(url, **kwargs):
    """Return the right canned response based on URL."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    if "geocoding-api.open-meteo.com" in url:
        if "Denver" in url:
            resp.json.return_value = GEOCODE_DENVER
        elif "Berlin" in url:
            resp.json.return_value = GEOCODE_BERLIN
        elif "Tokyo" in url:
            resp.json.return_value = GEOCODE_TOKYO
        else:
            resp.json.return_value = {"results": []}
    elif "api.weather.gov/points/" in url:
        resp.json.return_value = NWS_POINTS
    elif "api.weather.gov/gridpoints/BOU/62,61/stations" in url:
        resp.json.return_value = NWS_STATIONS
    elif "stations/KDEN/observations/latest" in url:
        resp.json.return_value = NWS_OBS
    elif "/forecast/hourly" in url:
        resp.json.return_value = NWS_HOURLY
    elif "/forecast" in url and "api.weather.gov" in url:
        resp.json.return_value = NWS_FORECAST
    elif "api.weather.gov/alerts/active" in url:
        resp.json.return_value = NWS_ALERTS
    elif "api.brightsky.dev/current_weather" in url:
        resp.json.return_value = BS_CURRENT
    elif "api.brightsky.dev/weather" in url:
        resp.json.return_value = BS_WEATHER
    elif "api.met.no" in url:
        resp.json.return_value = METNO_RESPONSE
    else:
        raise AssertionError(f"Unexpected URL: {url}")
    return resp


# ---- Tests --------------------------------------------------------------

def run(argv):
    """Invoke the CLI with given args, return (rc, captured stdout)."""
    from io import StringIO
    from wx import cli
    buf = StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        rc = cli.main(argv)
    finally:
        sys.stdout = old
    return rc, buf.getvalue()


def main():
    with patch("requests.get", side_effect=mock_get):
        # 1. US -> NWS, default style
        print("=" * 70)
        print("TEST 1: wx Denver  (US, default rich style)")
        print("=" * 70)
        rc, out = run(["Denver"])
        assert rc == 0, f"rc={rc}"
        assert "Denver" in out
        assert "NWS" in out
        print(out)

        # 2. Europe -> DWD, table style, metric
        print("=" * 70)
        print("TEST 2: wx Berlin --style table -u metric --hourly")
        print("=" * 70)
        rc, out = run(["Berlin", "--style", "table", "-u", "metric", "--hourly"])
        assert rc == 0
        assert "Berlin" in out
        assert "DWD" in out
        print(out)

        # 3. Global -> met.no, plain, imperial
        print("=" * 70)
        print("TEST 3: wx Tokyo --style plain -u imperial -d 2")
        print("=" * 70)
        rc, out = run(["Tokyo", "--style", "plain", "-u", "imperial", "-d", "2"])
        assert rc == 0
        assert "Tokyo" in out
        assert "metno" in out.lower()
        print(out)

        # 4. JSON output
        print("=" * 70)
        print("TEST 4: wx Denver --style json --hourly")
        print("=" * 70)
        rc, out = run(["Denver", "--style", "json", "--hourly"])
        assert rc == 0
        data = json.loads(out)
        assert data["provider"] == "nws"
        assert data["location"]["label"].startswith("Denver")
        assert data["current"]["temperature_unit"] == "C"
        assert data["current"]["wind_unit"] == "kt"
        # Verify unit conversion: NWS gave 18.4 km/h -> ~9.93 kt
        assert abs(data["current"]["wind_speed"] - 9.93) < 0.1, data["current"]["wind_speed"]
        # Pressure: 83000 Pa = 830 hPa -> ~24.51 inHg (Denver is high altitude!)
        assert abs(data["current"]["pressure"] - 24.51) < 0.05, data["current"]["pressure"]
        print(json.dumps(data, indent=2)[:1500])
        print("...")

        # 5. Coordinate input
        print("=" * 70)
        print("TEST 5: wx 39.74,-105.0 (raw coords -> US route)")
        print("=" * 70)
        rc, out = run(["39.74,-105.0", "-c"])
        assert rc == 0
        assert "39.7400" in out
        print(out)

        # 6. Alerts only
        print("=" * 70)
        print("TEST 6: wx Denver -A (alerts only)")
        print("=" * 70)
        rc, out = run(["Denver", "-A"])
        assert rc == 0
        assert "Winter Weather" in out
        print(out)

        # 7. Provider override
        print("=" * 70)
        print("TEST 7: wx Denver --provider metno (force met.no)")
        print("=" * 70)
        rc, out = run(["Denver", "--provider", "metno", "--no-color"])
        assert rc == 0
        assert "METNO" in out
        print(out)

        # 8. Settings: changing units via flags
        print("=" * 70)
        print("TEST 8: --temp F --wind mph --pressure hPa --precip mm")
        print("=" * 70)
        rc, out = run(["Berlin", "--temp", "F", "--wind", "mph",
                       "--pressure", "hPa", "--precip", "mm",
                       "--style", "table"])
        assert rc == 0
        assert "°F" in out
        assert "mph" in out
        assert "hPa" in out
        print(out)

    print("=" * 70)
    print("ALL TESTS PASSED ✓")
    print("=" * 70)


if __name__ == "__main__":
    main()
