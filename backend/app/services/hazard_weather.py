"""Open-Meteo inputs for the constituency-level drought and landslide pipeline.

These are weather observations/reanalysis and forecasts, not trained model
predictions. Keep that distinction in API responses and downstream UI.
"""

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import requests


OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_SEASONAL_URL = "https://seasonal-api.open-meteo.com/v1/seasonal"
TIMEZONE = "Asia/Kolkata"


def _fetch_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise ValueError(payload.get("reason", "Provider returned an error"))
    return payload


def _sum(values: list[float | None], start: int, end: int | None) -> float | None:
    window = [value for value in values[start:end] if value is not None]
    return round(sum(window), 2) if window else None


def _mean(values: list[float | None], start: int, end: int | None) -> float | None:
    window = [value for value in values[start:end] if value is not None]
    return round(sum(window) / len(window), 4) if window else None


def _daily_windows(payload: dict[str, Any], days: int = 90) -> dict[str, Any]:
    daily = payload.get("daily", {})
    times = daily.get("time", [])
    result: dict[str, Any] = {"dates": times}
    for key in ("precipitation_sum", "et0_fao_evapotranspiration"):
        values = daily.get(key, [])
        result[key] = {
            f"next_{period}d_sum": _sum(values, 0, period)
            for period in (30, 60, 90)
        }
    moisture = daily.get("soil_moisture_0_to_7cm_mean", [])
    result["soil_moisture_0_to_7cm_mean"] = {
        f"next_{period}d_mean": _mean(moisture, 0, period)
        for period in (30, 60, 90)
    }
    temperature = daily.get("temperature_2m_mean", [])
    result["temperature_2m_mean_c"] = {
        f"next_{period}d_mean": _mean(temperature, 0, period)
        for period in (30, 60, 90)
    }
    return result


def get_hazard_weather(latitude: float, longitude: float) -> dict[str, Any]:
    """Fetch forecast, recent reanalysis and seasonal outlook for one point."""
    today = datetime.now(ZoneInfo(TIMEZONE)).date()
    # Reanalysis is delayed; end at D-5 to avoid silently presenting missing
    # latest days as zero rainfall.
    archive_end = today - timedelta(days=5)
    archive_start = archive_end - timedelta(days=89)
    base = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": TIMEZONE,
        "source": "Open-Meteo",
        "forecast": None,
        "historical_reanalysis": None,
        "seasonal_outlook": None,
        "unavailable": [],
        "limitations": [
            "Constituency coordinates are represented by a weather grid cell, not an area-wide station average.",
            "Weather inputs are not a Kaavalal hazard probability or official warning.",
        ],
    }

    try:
        forecast = _fetch_json(OPEN_METEO_FORECAST_URL, {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "precipitation,precipitation_probability,soil_moisture_0_to_7cm,temperature_2m,relative_humidity_2m,et0_fao_evapotranspiration",
            "past_hours": 72,
            "forecast_hours": 72,
            "timezone": TIMEZONE,
        })
        hourly = forecast.get("hourly", {})
        times = hourly.get("time", [])
        # Forecast API contains 72 prior model hours followed by forecast hours.
        base["forecast"] = {
            "hourly_time": times,
            "precipitation_mm": hourly.get("precipitation", []),
            "precipitation_probability_pct": hourly.get("precipitation_probability", []),
            "soil_moisture_0_to_7cm": hourly.get("soil_moisture_0_to_7cm", []),
            "temperature_2m_c": hourly.get("temperature_2m", []),
            "relative_humidity_2m_pct": hourly.get("relative_humidity_2m", []),
            "et0_fao_evapotranspiration_mm": hourly.get("et0_fao_evapotranspiration", []),
            "forecast_hours": 72,
            "note": "Use future timestamps for the 72-hour landslide trigger window; earlier hours are model history, not station observations.",
        }
    except (requests.RequestException, ValueError) as exc:
        base["unavailable"].append({"feed": "forecast", "reason": str(exc)})

    try:
        archive = _fetch_json(OPEN_METEO_ARCHIVE_URL, {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": archive_start.isoformat(),
            "end_date": archive_end.isoformat(),
            "hourly": "precipitation,et0_fao_evapotranspiration,soil_moisture_0_to_7cm,soil_moisture_7_to_28cm",
            "timezone": TIMEZONE,
        })
        hourly = archive.get("hourly", {})
        hourly_values = hourly.get("precipitation", [])
        # Archive is hourly. The requested window ends on the latest complete
        # reanalysis date, so these are explicitly dated historical summaries.
        history = {}
        for days in (3, 7, 30, 90):
            count = days * 24
            history[f"rainfall_{days}d_mm"] = _sum(hourly_values, max(0, len(hourly_values) - count), len(hourly_values))
        history["rainfall_window_start"] = archive_start.isoformat()
        history["rainfall_window_end"] = archive_end.isoformat()
        history["soil_moisture_0_to_7cm_mean"] = _mean(hourly.get("soil_moisture_0_to_7cm", []), 0, None)
        history["soil_moisture_7_to_28cm_mean"] = _mean(hourly.get("soil_moisture_7_to_28cm", []), 0, None)
        history["et0_fao_evapotranspiration_90d_mm"] = _sum(hourly.get("et0_fao_evapotranspiration", []), 0, None)
        history["note"] = "ERA5-Land reanalysis; latest five days are omitted because archive data can be delayed."
        base["historical_reanalysis"] = history
    except (requests.RequestException, ValueError) as exc:
        base["unavailable"].append({"feed": "historical_reanalysis", "reason": str(exc)})

    try:
        seasonal = _fetch_json(OPEN_METEO_SEASONAL_URL, {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "precipitation_sum,temperature_2m_mean,et0_fao_evapotranspiration,soil_moisture_0_to_7cm_mean",
            "forecast_days": 120,
            "timezone": TIMEZONE,
        })
        base["seasonal_outlook"] = _daily_windows(seasonal)
        base["limitations"].append(
            "Seasonal outlook is a coarse ECMWF ensemble indication and is not bias corrected; interpret as regional tendency."
        )
    except (requests.RequestException, ValueError) as exc:
        base["unavailable"].append({"feed": "seasonal_outlook", "reason": str(exc)})

    return base
