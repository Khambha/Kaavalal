from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
import pytest
from fastapi import HTTPException
from types import SimpleNamespace

from app.services import hazard_weather
from app.routers import hazard_data


class FakeQuery:
    def __init__(self, result):
        self.result = result

    def filter(self, *_args):
        return self

    def first(self):
        return self.result


class FakeDatabase:
    def __init__(self, result):
        self.result = result

    def query(self, _model):
        return FakeQuery(self.result)


def test_aggregate_helpers_ignore_missing_values():
    assert hazard_weather._sum([1.0, None, 2.5], 0, None) == 3.5
    assert hazard_weather._mean([1.0, None, 3.0], 0, None) == 2.0
    assert hazard_weather._sum([None], 0, None) is None


def test_get_hazard_weather_builds_forecast_archive_and_seasonal_summaries(monkeypatch):
    now = datetime.now(ZoneInfo(hazard_weather.TIMEZONE))
    forecast_times = [
        (now - timedelta(hours=72) + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M")
        for i in range(145)
    ]
    forecast_payload = {
        "hourly": {
            "time": forecast_times,
            "precipitation": [1.0] * 145,
            "precipitation_probability": [50] * 145,
            "soil_moisture_0_to_7cm": [0.2] * 145,
            "temperature_2m": [28.0] * 145,
            "relative_humidity_2m": [80] * 145,
            "et0_fao_evapotranspiration": [0.1] * 145,
        }
    }
    archive_payload = {
        "hourly": {
            "time": ["hour"] * (90 * 24),
            "precipitation": [1.0] * (90 * 24),
            "et0_fao_evapotranspiration": [0.1] * (90 * 24),
            "soil_moisture_0_to_7cm": [0.2] * (90 * 24),
            "soil_moisture_7_to_28cm": [0.3] * (90 * 24),
        }
    }
    seasonal_payload = {
        "daily": {
            "time": [f"day-{i}" for i in range(120)],
            "precipitation_sum": [2.0] * 120,
            "temperature_2m_mean": [29.0] * 120,
            "et0_fao_evapotranspiration": [0.2] * 120,
            "soil_moisture_0_to_7cm_mean": [0.25] * 120,
        }
    }
    payloads = {
        hazard_weather.OPEN_METEO_FORECAST_URL: forecast_payload,
        hazard_weather.OPEN_METEO_ARCHIVE_URL: archive_payload,
        hazard_weather.OPEN_METEO_SEASONAL_URL: seasonal_payload,
    }
    calls = []

    def fake_fetch(url, params):
        calls.append((url, params))
        return payloads[url]

    monkeypatch.setattr(hazard_weather, "_fetch_json", fake_fetch)

    result = hazard_weather.get_hazard_weather(10.5, 76.2)

    assert len(calls) == 3
    assert result["forecast"]["forecast_hours"] == 72
    assert result["historical_reanalysis"]["rainfall_3d_mm"] == 72.0
    assert result["historical_reanalysis"]["rainfall_7d_mm"] == 168.0
    assert result["historical_reanalysis"]["rainfall_30d_mm"] == 720.0
    assert result["historical_reanalysis"]["rainfall_90d_mm"] == 2160.0
    assert result["seasonal_outlook"]["precipitation_sum"]["next_90d_sum"] == 180.0
    assert result["seasonal_outlook"]["soil_moisture_0_to_7cm_mean"]["next_90d_mean"] == 0.25
    assert result["unavailable"] == []


def test_get_hazard_weather_returns_partial_data_when_provider_fails(monkeypatch):
    def fail_fetch(url, params):
        raise requests.ConnectionError("provider offline")

    monkeypatch.setattr(hazard_weather, "_fetch_json", fail_fetch)

    result = hazard_weather.get_hazard_weather(10.5, 76.2)

    assert result["forecast"] is None
    assert result["historical_reanalysis"] is None
    assert result["seasonal_outlook"] is None
    assert {item["feed"] for item in result["unavailable"]} == {
        "forecast",
        "historical_reanalysis",
        "seasonal_outlook",
    }


def test_constituency_route_returns_weather_inputs_for_saved_coordinates(monkeypatch):
    location = SimpleNamespace(
        id=17,
        name="Thrissur",
        location_type="LAC",
        latitude=10.52,
        longitude=76.21,
    )
    monkeypatch.setattr(
        hazard_data,
        "get_hazard_weather",
        lambda latitude, longitude: {"latitude": latitude, "longitude": longitude},
    )

    result = hazard_data.get_constituency_hazard_inputs(17, FakeDatabase(location))

    assert result["location_name"] == "Thrissur"
    assert result["location_type"] == "LAC"
    assert result["latitude"] == 10.52
    assert result["longitude"] == 76.21


@pytest.mark.parametrize(
    ("location", "status_code"),
    [
        (None, 404),
        (SimpleNamespace(id=8, name="Palakkad", location_type="DISTRICT", latitude=10.8, longitude=76.6), 422),
        (SimpleNamespace(id=9, name="Wandoor", location_type="LAC", latitude=None, longitude=None), 400),
    ],
)
def test_constituency_route_rejects_missing_or_invalid_locations(location, status_code):
    with pytest.raises(HTTPException) as error:
        hazard_data.get_constituency_hazard_inputs(17, FakeDatabase(location))

    assert error.value.status_code == status_code
