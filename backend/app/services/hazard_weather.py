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
            "The latest five-day rainfall/ET₀ update uses Open-Meteo forecast-model history, not rain-gauge observations.",
            "Weather inputs are not a Kaavalal hazard probability or official warning.",
        ],
    }

    try:
        forecast = _fetch_json(OPEN_METEO_FORECAST_URL, {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "precipitation,precipitation_probability,soil_moisture_0_to_7cm,temperature_2m,relative_humidity_2m,et0_fao_evapotranspiration",
            # Five recent modelled days help repair the archive's known D-5 lag.
            "past_hours": 120,
            "forecast_hours": 72,
            "timezone": TIMEZONE,
        })
        hourly = forecast.get("hourly", {})
        times = hourly.get("time", [])
        # Forecast API contains 120 prior model hours followed by forecast hours.
        recent_rain = hourly.get("precipitation", [])[:120]
        recent_et0 = hourly.get("et0_fao_evapotranspiration", [])[:120]
        recent_surface_moisture = hourly.get("soil_moisture_0_to_7cm", [])[:120]
        recent_root_moisture = hourly.get("soil_moisture_7_to_28cm", [])[:120]
        recent_complete = len(recent_rain) == 120 and all(value is not None for value in recent_rain)
        base["forecast"] = {
            "hourly_time": times,
            "precipitation_mm": hourly.get("precipitation", []),
            "precipitation_probability_pct": hourly.get("precipitation_probability", []),
            "soil_moisture_0_to_7cm": hourly.get("soil_moisture_0_to_7cm", []),
            "temperature_2m_c": hourly.get("temperature_2m", []),
            "relative_humidity_2m_pct": hourly.get("relative_humidity_2m", []),
            "et0_fao_evapotranspiration_mm": hourly.get("et0_fao_evapotranspiration", []),
            "forecast_hours": 72,
            "recent_5d_precipitation_mm": _sum(recent_rain, 0, None) if recent_complete else None,
            "recent_5d_et0_mm": _sum(recent_et0, 0, None) if len(recent_et0) == 120 and all(value is not None for value in recent_et0) else None,
            "recent_5d_soil_moisture_0_7cm_mean": _mean(recent_surface_moisture, 0, None),
            "recent_5d_soil_moisture_7_28cm_mean": _mean(recent_root_moisture, 0, None),
            "note": "The previous 120 model hours provide recent weather context; they are model estimates, not local rain-gauge observations. The following 72 hours are forecast.",
        }
    except (requests.RequestException, ValueError) as exc:
        base["unavailable"].append({"feed": "forecast", "reason": str(exc)})

    try:
        archive = _fetch_json(OPEN_METEO_ARCHIVE_URL, {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": archive_start.isoformat(),
            "end_date": archive_end.isoformat(),
            "hourly": "precipitation,et0_fao_evapotranspiration,soil_moisture_0_to_7cm,soil_moisture_7_to_28cm,soil_moisture_28_to_100cm",
            "timezone": TIMEZONE,
        })
        hourly = archive.get("hourly", {})
        hourly_values = hourly.get("precipitation", [])
        # Archive is hourly. The requested window ends on the latest complete
        # reanalysis date, so these are explicitly dated historical summaries.
        history = {}
        for days in (1, 3, 5, 7, 14, 30, 90):
            count = days * 24
            history[f"rainfall_{days}d_mm"] = _sum(hourly_values, max(0, len(hourly_values) - count), len(hourly_values))
        recent_rain_5d = base.get("forecast", {}).get("recent_5d_precipitation_mm")
        if recent_rain_5d is not None:
            for days in (7, 30, 90):
                total = history.get(f"rainfall_{days}d_mm")
                start = max(0, len(hourly_values) - days * 24)
                oldest_stale = _sum(hourly_values, start, start + 5 * 24)
                if total is not None and oldest_stale is not None:
                    history[f"rainfall_{days}d_live_mm"] = round(max(0.0, total - oldest_stale) + recent_rain_5d, 2)
        history["rainfall_window_start"] = archive_start.isoformat()
        history["rainfall_window_end"] = archive_end.isoformat()
        history["soil_moisture_0_to_7cm_mean"] = _mean(hourly.get("soil_moisture_0_to_7cm", []), 0, None)
        history["soil_moisture_7_to_28cm_mean"] = _mean(hourly.get("soil_moisture_7_to_28cm", []), 0, None)
        history["soil_moisture_28_to_100cm_mean"] = _mean(hourly.get("soil_moisture_28_to_100cm", []), 0, None)
        history["et0_fao_evapotranspiration_90d_mm"] = _sum(hourly.get("et0_fao_evapotranspiration", []), 0, None)
        et0_values = hourly.get("et0_fao_evapotranspiration", [])
        history["et0_fao_evapotranspiration_30d_mm"] = _sum(et0_values, max(0, len(et0_values) - 30 * 24), len(et0_values))
        recent_et0_5d = base.get("forecast", {}).get("recent_5d_et0_mm")
        if recent_et0_5d is not None:
            for days in (30, 90):
                key = f"et0_fao_evapotranspiration_{days}d_mm"
                total = history.get(key)
                start = max(0, len(et0_values) - days * 24)
                oldest_stale = _sum(et0_values, start, start + 5 * 24)
                if total is not None and oldest_stale is not None:
                    history[f"et0_fao_evapotranspiration_{days}d_live_mm"] = round(max(0.0, total - oldest_stale) + recent_et0_5d, 2)
        # API-14 uses the declared k=0.85 decay on daily rainfall, newest day
        # weighted 1.0. It is a meteorological antecedent index, not a risk score.
        api = 0.0
        daily_rain = [sum(value for value in hourly_values[i:i + 24] if value is not None)
                      for i in range(max(0, len(hourly_values) - 14 * 24), len(hourly_values), 24)]
        for age, amount in enumerate(reversed(daily_rain)):
            api += amount * (0.85 ** age)
        history["api_14d_mm"] = round(api, 2) if daily_rain else None
        # Consecutive dry days use the IMD 2.5 mm daily criterion.
        daily_series = [sum(value for value in hourly_values[i:i + 24] if value is not None)
                        for i in range(0, len(hourly_values), 24)]
        cdd = 0
        for amount in reversed(daily_series):
            if amount >= 2.5:
                break
            cdd += 1
        history["cdd_count"] = cdd if daily_series else None
        recent_daily_rain = []
        if len(recent_rain) == 120 and all(value is not None for value in recent_rain):
            recent_daily_rain = [sum(recent_rain[i:i + 24]) for i in range(0, 120, 24)]
        if recent_daily_rain:
            recent_cdd = 0
            for amount in reversed(recent_daily_rain):
                if amount >= 2.5:
                    break
                recent_cdd += 1
            history["cdd_count_live"] = cdd + 5 if recent_cdd == 5 else recent_cdd
        history["note"] = "ERA5-Land archive ends five days before today; rolling 7/30/90-day rain and 30/90-day ET₀ totals replace the oldest five days with recent forecast-model history when available."
        if base.get("forecast"):
            latest_rain = base["forecast"].get("recent_5d_precipitation_mm")
            if latest_rain is not None:
                history["rainfall_5d_live_mm"] = latest_rain
            latest_et0 = base["forecast"].get("recent_5d_et0_mm")
            if latest_et0 is not None:
                history["et0_fao_evapotranspiration_5d_live_mm"] = latest_et0
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
