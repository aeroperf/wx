"""Unit tests for the aviationweather.gov adapter and renderers."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from wx import aviation_render, cli
from wx.providers import aviationweather as aw


# ─── Fixtures: realistic API responses ───────────────────────────────────
METAR_KORD = [{
    "icaoId": "KORD",
    "rawOb": "METAR KORD 180351Z 19011G23KT 10SM FEW065 SCT250 26/16 A2982 RMK AO2",
    "obsTime": 1779076260,
    "reportTime": "2026-05-18T04:00:00.000Z",
    "name": "Chicago/O'Hare Intl, IL, US",
    "lat": 41.9602, "lon": -87.9316, "elev": 202,
    "temp": 25.6, "dewp": 16.1,
    "wdir": 190, "wspd": 11, "wgst": 23,
    "visib": "10+",
    "altim": 1009.9, "slp": 1009.2,
    "fltCat": "VFR",
    "clouds": [{"cover": "FEW", "base": 6500}, {"cover": "SCT", "base": 25000}],
    "cover": "SCT",
}]

# Tricky: variable winds, calm conditions, missing fields, numeric visibility
METAR_EDGE = [{
    "icaoId": "K1G3",  # FAA identifier with digits
    "rawOb": "METAR K1G3 180400Z VRB03KT 6SM BKN015 OVC025 02/M01 A2998",
    "obsTime": 1779076800,
    "wdir": "VRB", "wspd": 3, "wgst": None,
    "visib": 6,
    "temp": 2.0, "dewp": -1.0,
    "altim": 1015.0,
    "clouds": [{"cover": "BKN", "base": 1500}, {"cover": "OVC", "base": 2500, "type": "CB"}],
    "fltCat": "MVFR",
}]

# Wind from due north — must render "000°", not "VRB"
METAR_NORTH = [{
    "icaoId": "KSEA", "rawOb": "raw",
    "obsTime": 1779076800,
    "wdir": 0, "wspd": 0, "wgst": None,
    "visib": "10+",
}]

# Multiple records — picker should choose mostRecent=1
METAR_MULTI = [
    {"icaoId": "KORD", "rawOb": "older", "obsTime": 1779070000, "mostRecent": 0},
    {"icaoId": "KORD", "rawOb": "newer", "obsTime": 1779076800, "mostRecent": 1},
    {"icaoId": "KORD", "rawOb": "oldest", "obsTime": 1779000000, "mostRecent": 0},
]

TAF_KORD = [{
    "icaoId": "KORD",
    "rawTAF": "TAF KORD 180540Z 1806/1912 19014G24KT P6SM SCT060 BKN100 ...",
    "issueTime": "2026-05-18T05:40:00.000Z",
    "validTimeFrom": 1779084000,
    "validTimeTo": 1779192000,
    "name": "Chicago/O'Hare Intl",
    "mostRecent": 1,
    "fcsts": [
        {"timeFrom": 1779084000, "timeTo": 1779102000, "fcstChange": None,
         "wdir": 190, "wspd": 14, "wgst": 24, "visib": "6+",
         "clouds": [{"cover": "SCT", "base": 6000}, {"cover": "BKN", "base": 10000}]},
        {"timeFrom": 1779102000, "timeTo": 1779127200, "fcstChange": "FM",
         "wdir": 170, "wspd": 11, "wgst": None, "visib": 6, "wxString": "-SHRA",
         "clouds": [{"cover": "SCT", "base": 3500}, {"cover": "OVC", "base": 6000}]},
        {"timeFrom": 1779102000, "timeTo": 1779123600, "fcstChange": "PROB",
         "probability": 30,
         "wdir": "VRB", "wspd": 15, "wgst": 25, "visib": 4, "wxString": "-TSRA",
         "clouds": [{"cover": "BKN", "base": 3500, "type": "CB"}]},
        # Wind shear scenario
        {"timeFrom": 1779127200, "timeTo": 1779156000, "fcstChange": "BECMG",
         "wdir": 210, "wspd": 14, "wgst": 24, "visib": "6+",
         "wshearHgt": 2000, "wshearDir": 240, "wshearSpd": 45,
         "clouds": [{"cover": "SCT", "base": 5000}]},
    ],
}]


def _mock_response(body, status=200):
    r = MagicMock()
    r.status_code = status
    r.content = b"x" if body is not None else b""
    r.json = MagicMock(return_value=body)
    r.raise_for_status = MagicMock()
    return r


def _mock_204():
    r = MagicMock()
    r.status_code = 204
    r.content = b""
    return r


# ─── Parser tests ─────────────────────────────────────────────────────────
def test_fetch_metar_parses_normal_response():
    with patch("requests.get", return_value=_mock_response(METAR_KORD)) as g:
        m = aw.fetch_metar("KORD", "wx-test", timeout=10, hours=6)
    # URL was built with params= (not f-string injection)
    args, kwargs = g.call_args
    assert "params" in kwargs
    assert kwargs["params"] == {"ids": "KORD", "hours": 6, "format": "json"}
    assert m.icao == "KORD"
    assert m.wind_dir == 190
    assert m.wind_speed_kt == 11
    assert m.wind_gust_kt == 23
    assert m.visibility == "10+"
    assert m.altimeter_hpa == 1009.9
    assert m.flight_cat == "VFR"
    assert len(m.clouds) == 2
    assert m.observed is not None


def test_fetch_metar_204_raises():
    with patch("requests.get", return_value=_mock_204()):
        with pytest.raises(aw.AviationWeatherError, match="no METAR"):
            aw.fetch_metar("ZZZZ", "wx-test")


def test_fetch_metar_picks_most_recent():
    with patch("requests.get", return_value=_mock_response(METAR_MULTI)):
        m = aw.fetch_metar("KORD", "wx-test")
    assert m.raw == "newer"


def test_fetch_metar_falls_back_to_obstime_when_no_mostrecent_flag():
    records = [
        {"icaoId": "KX", "rawOb": "old", "obsTime": 100},
        {"icaoId": "KX", "rawOb": "new", "obsTime": 999},
    ]
    with patch("requests.get", return_value=_mock_response(records)):
        m = aw.fetch_metar("KX", "wx-test")
    assert m.raw == "new"


def test_fetch_metar_edge_case_fields():
    with patch("requests.get", return_value=_mock_response(METAR_EDGE)):
        m = aw.fetch_metar("K1G3", "wx-test")
    assert m.icao == "K1G3"
    assert m.wind_dir == "VRB"
    assert m.visibility == 6  # numeric preserved
    assert m.wind_gust_kt is None


def test_fetch_taf_parses_change_groups():
    with patch("requests.get", return_value=_mock_response(TAF_KORD)):
        t = aw.fetch_taf("KORD", "wx-test")
    assert len(t.forecasts) == 4
    assert t.forecasts[0].change == ""        # initial
    assert t.forecasts[1].change == "FM"
    assert t.forecasts[2].change == "PROB"
    assert t.forecasts[2].probability == 30
    assert t.forecasts[3].wind_shear_hgt_ft == 2000


def test_fetch_taf_204_raises():
    with patch("requests.get", return_value=_mock_204()):
        with pytest.raises(aw.AviationWeatherError, match="no TAF"):
            aw.fetch_taf("ZZZZ", "wx-test")


def test_fetch_metar_invalid_json():
    r = MagicMock()
    r.status_code = 200
    r.content = b"<html>oops</html>"
    r.json = MagicMock(side_effect=ValueError("bad"))
    with patch("requests.get", return_value=r):
        with pytest.raises(aw.AviationWeatherError, match="invalid JSON"):
            aw.fetch_metar("KORD", "wx-test")


def test_epoch_handles_invalid():
    assert aw._epoch(None) is None
    assert aw._epoch("not-a-number") is None
    assert aw._epoch(1779076260) is not None


def test_iso_handles_invalid():
    assert aw._iso(None) is None
    assert aw._iso("") is None
    assert aw._iso("garbage") is None
    assert aw._iso("2026-05-18T04:00:00Z") is not None


# ─── Renderer tests ───────────────────────────────────────────────────────
def test_render_metar_raw_returns_raw_string():
    m = aw._metar_from_dict(METAR_KORD[0], "KORD")
    assert aviation_render.render_metar_raw(m) == METAR_KORD[0]["rawOb"]


def test_render_metar_decoded_contains_expected_fields():
    m = aw._metar_from_dict(METAR_KORD[0], "KORD")
    out = aviation_render.render_metar_decoded(m)
    assert "190° @ 11 kt gust 23 kt" in out
    assert "10+ SM" in out
    assert "29.82 inHg" in out  # 1009.9 hPa via wx.units (matches old constant)
    assert "1010 hPa" in out
    assert "VFR" in out
    assert "FEW @ 6,500 ft" in out


def test_render_metar_decoded_wind_due_north():
    """Bug fix: wind from 0° must render as 000°, not VRB. Speed 0 also OK."""
    m = aw._metar_from_dict(METAR_NORTH[0], "KSEA")
    out = aviation_render.render_metar_decoded(m)
    assert "000° @ 0 kt" in out
    assert "VRB" not in out


def test_render_metar_decoded_variable_wind():
    m = aw._metar_from_dict(METAR_EDGE[0], "K1G3")
    out = aviation_render.render_metar_decoded(m)
    assert "VRB @ 3 kt" in out
    assert "gust" not in out  # no gust


def test_render_metar_decoded_cloud_type_appended():
    m = aw._metar_from_dict(METAR_EDGE[0], "K1G3")
    out = aviation_render.render_metar_decoded(m)
    assert "OVCCB" in out  # type concatenated to cover


def test_render_taf_decoded_handles_all_change_groups():
    t = aw._taf_from_dict(TAF_KORD[0], "KORD")
    out = aviation_render.render_taf_decoded(t)
    assert "INITIAL" in out
    assert "FM " in out
    assert "PROB30" in out
    assert "PROB0" not in out  # bug fix: no spurious "PROB0"
    assert "BECMG" in out
    assert "wind shear 240° @ 45 kt at 2,000 ft" in out


def test_render_taf_period_label_handles_prob_tempo_combo():
    """Some feeds return 'PROB30 TEMPO' as fcstChange."""
    p = aw.TafForecastPeriod(
        time_from=None, time_to=None, change="PROB30 TEMPO", probability=30,
    )
    label = aviation_render._period_label(p, is_first=False)
    assert "PROB30" in label
    assert "TEMPO" in label


def test_render_aviation_json_no_duplicate_raw():
    m = aw._metar_from_dict(METAR_KORD[0], "KORD")
    t = aw._taf_from_dict(TAF_KORD[0], "KORD")
    out = aviation_render.render_aviation_json("KORD", m, t)
    data = json.loads(out)
    # raw is at outer level only — not duplicated inside `decoded`
    assert data["metar"]["raw"] == m.raw
    assert "raw" not in data["metar"]["decoded"]
    assert data["taf"]["raw"] == t.raw
    assert "raw" not in data["taf"]["decoded"]


def test_render_aviation_json_omits_missing_products():
    m = aw._metar_from_dict(METAR_KORD[0], "KORD")
    out = aviation_render.render_aviation_json("KORD", m, None)
    data = json.loads(out)
    assert "metar" in data
    assert "taf" not in data


# ─── CLI integration ──────────────────────────────────────────────────────
def test_cli_accepts_alphanumeric_icao():
    """Bug fix: ICAO with digits (K1G3) must be accepted."""
    assert cli._is_icao("KORD") is True
    assert cli._is_icao("K1G3") is True
    assert cli._is_icao("EGLL") is True
    assert cli._is_icao("KOR") is False    # too short
    assert cli._is_icao("KORDS") is False  # too long
    assert cli._is_icao("KOR-") is False   # non-alnum


def test_cli_metar_raw_output(capsys):
    with patch("requests.get", return_value=_mock_response(METAR_KORD)):
        rc = cli.main(["-m", "KORD"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.strip() == METAR_KORD[0]["rawOb"]


def test_cli_metar_decoded(capsys):
    with patch("requests.get", return_value=_mock_response(METAR_KORD)):
        rc = cli.main(["-m", "KORD", "--decode"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "METAR  KORD" in out
    assert "190° @ 11 kt" in out


def test_cli_metar_and_taf(capsys):
    def router(url, **kwargs):
        if "/metar" in url:
            return _mock_response(METAR_KORD)
        if "/taf" in url:
            return _mock_response(TAF_KORD)
        raise AssertionError(url)
    with patch("requests.get", side_effect=router):
        rc = cli.main(["-mt", "KORD"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "METAR KORD" in out
    assert "TAF KORD" in out


def test_cli_missing_icao(capsys):
    rc = cli.main(["-m"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "requires an ICAO" in err


def test_cli_invalid_icao(capsys):
    rc = cli.main(["-m", "TOOLONG"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "not a valid" in err


def test_cli_extra_args_warns(capsys):
    with patch("requests.get", return_value=_mock_response(METAR_KORD)):
        rc = cli.main(["-m", "KORD", "KSFO"])
    assert rc == 0
    err = capsys.readouterr().err
    assert "ignoring extra" in err


def test_cli_json_output(capsys):
    with patch("requests.get", return_value=_mock_response(METAR_KORD)):
        rc = cli.main(["-m", "KORD", "--style", "json"])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["icao"] == "KORD"
    assert "raw" in data["metar"]
    assert "decoded" in data["metar"]


def test_cli_handles_aviationweather_error(capsys):
    with patch("requests.get", return_value=_mock_204()):
        rc = cli.main(["-m", "ZZZZ"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "no METAR" in err


def test_cli_handles_network_error(capsys):
    import requests
    with patch("requests.get", side_effect=requests.ConnectionError("boom")):
        rc = cli.main(["-m", "KORD"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "request failed" in err
