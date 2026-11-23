"""Validated weather features for district hazard analysis.

This module transforms Open-Meteo inputs into measured features. It deliberately
does not convert those inputs to a probability or operational warning.
"""

from datetime import datetime, timezone
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.services.hazard_weather import get_hazard_weather


class HazardFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: int | None = None
    location_name: str
    latitude: float
    longitude: float
    mean_elevation_m: float | None = None
    terrain_ruggedness: float | None = None
    western_ghats_susceptibility_tier: str | None = None
    coastal_backwater_exposure: bool | None = None
    major_river_basins: list[str] | None = None
    drainage_density_tier: str | None = None
    rain_24h_mm: float | None = None
    rain_72h_mm: float | None = None
    rain_3d_mm: float | None = None
    rain_7d_mm: float | None = None
    rain_14d_mm: float | None = None
    forecast_rain_24h_mm: float | None = None
    forecast_rain_72h_mm: float | None = None
    max_hourly_intensity_mm: float | None = None
    api_14d: float | None = None
    soil_moisture_0_7cm: float | None = None
    soil_moisture_7_28cm: float | None = None
    soil_moisture_28_100cm: float | None = None
    precip_30d_mm: float | None = None
    et0_30d_mm: float | None = None
    recent_precip_5d_mm: float | None = None
    recent_et0_5d_mm: float | None = None
    recent_soil_moisture_surface: float | None = None
    recent_soil_moisture_root: float | None = None
    water_balance_30d_mm: float | None = None
    precip_90d_mm: float | None = None
    et0_90d_mm: float | None = None
    seasonal_precip_30d_mm: float | None = None
    seasonal_et0_30d_mm: float | None = None
    seasonal_precip_90d_mm: float | None = None
    seasonal_et0_90d_mm: float | None = None
    cdd_count: int | None = None
    spi_30d: float | None = None
    spi_90d: float | None = None
    tmax_anomaly_14d: float | None = None
    feature_completeness_ratio: float = Field(ge=0, le=1)
    weather_fetched_at_utc: datetime
    source: str = "Open-Meteo ERA5-Land / forecast"
    unavailable_feeds: list[str] = Field(default_factory=list)


def _numbers(values: Any) -> list[float]:
    if not isinstance(values, list):
        return []
    return [float(value) for value in values if isinstance(value, (int, float))]


def _sum(values: list[float], count: int) -> float | None:
    if len(values) < count:
        return None
    return round(sum(values[-count:]), 2)


@lru_cache(maxsize=1)
def _district_static() -> dict[str, dict[str, Any]]:
    path = Path(__file__).resolve().parents[1] / "data" / "kerala_district_static.json"
    districts = json.loads(path.read_text(encoding="utf-8"))["districts"]
    return {item["district_id"]: item for item in districts}


def build_hazard_features(
    latitude: float,
    longitude: float,
    location_name: str,
    location_id: int | None = None,
) -> tuple[HazardFeatures, dict[str, Any]]:
    """Fetch current feeds, engineer dated features and validate the result."""
    raw = get_hazard_weather(latitude, longitude)
    district_key = "".join(character for character in location_name.lower().replace("district", "") if character.isalpha())
    district_key = {"trivandrum": "thiruvananthapuram", "trichur": "thrissur", "eranakulam": "ernakulam", "wynad": "wayanad"}.get(district_key, district_key)
    static = _district_static().get(district_key, {})
    history = raw.get("historical_reanalysis") or {}
    forecast = raw.get("forecast") or {}
    seasonal = raw.get("seasonal_outlook") or {}
    seasonal_precip = seasonal.get("precipitation_sum") or {}
    seasonal_et0 = seasonal.get("et0_fao_evapotranspiration") or {}
    precip = _numbers(forecast.get("precipitation_mm"))
    now = datetime.now(timezone.utc)
    past = precip[:120]
    # API response is the preceding 120 model hours followed by 72 forecast hours.
    future = precip[120:192]
    # Existing endpoint exposes only 90-day totals; calculate reliable shorter
    # windows from hourly archive data only when the raw feed supplies it.
    rain_3d = round(sum(past[-72:]), 2) if len(past) == 120 else None
    rain_7d = history.get("rainfall_7d_live_mm", history.get("rainfall_7d_mm"))
    rain_14d = history.get("rainfall_14d_mm")
    rain_24h = round(sum(past[-24:]), 2) if len(past) == 120 else None
    rain_72h = rain_3d
    forecast24 = _sum(future, 24)
    forecast72 = _sum(future, 72)
    et0_30 = history.get("et0_fao_evapotranspiration_30d_live_mm", history.get("et0_fao_evapotranspiration_30d_mm"))
    rain30 = history.get("rainfall_30d_live_mm", history.get("rainfall_30d_mm"))
    et0_90 = history.get("et0_fao_evapotranspiration_90d_live_mm", history.get("et0_fao_evapotranspiration_90d_mm"))
    rain90 = history.get("rainfall_90d_live_mm", history.get("rainfall_90d_mm"))
    seasonal_rain30 = seasonal_precip.get("next_30d_sum")
    seasonal_rain90 = seasonal_precip.get("next_90d_sum")
    seasonal_et030 = seasonal_et0.get("next_30d_sum")
    seasonal_et090 = seasonal_et0.get("next_90d_sum")
    moisture_surface = history.get("soil_moisture_0_7cm_mean")
    moisture_root = history.get("soil_moisture_7_28cm_mean")
    recent_moisture_surface = raw.get("forecast", {}).get("recent_5d_soil_moisture_0_7cm_mean")
    recent_moisture_root = raw.get("forecast", {}).get("recent_5d_soil_moisture_7_28cm_mean")
    required = [rain_3d, rain_7d, rain30, rain90, forecast24, forecast72, seasonal_rain30, seasonal_et030,
                seasonal_rain90, seasonal_et090, moisture_surface, moisture_root,
                static.get("mean_elevation_m"), static.get("terrain_ruggedness"),
                static.get("coastal_backwater_exposure"), static.get("major_river_basins")]
    completeness = sum(value is not None for value in required) / len(required)
    features = HazardFeatures(
        location_id=location_id,
        location_name=location_name,
        latitude=latitude,
        longitude=longitude,
        mean_elevation_m=static.get("mean_elevation_m"),
        terrain_ruggedness=static.get("terrain_ruggedness"),
        western_ghats_susceptibility_tier=static.get("western_ghats_susceptibility_tier"),
        coastal_backwater_exposure=static.get("coastal_backwater_exposure"),
        major_river_basins=static.get("major_river_basins"),
        drainage_density_tier=static.get("drainage_density_tier"),
        rain_24h_mm=rain_24h,
        rain_72h_mm=rain_72h,
        rain_3d_mm=rain_3d,
        rain_7d_mm=rain_7d,
        rain_14d_mm=rain_14d,
        forecast_rain_24h_mm=forecast24,
        forecast_rain_72h_mm=forecast72,
        max_hourly_intensity_mm=max(future) if future else None,
        soil_moisture_0_7cm=recent_moisture_surface if recent_moisture_surface is not None else moisture_surface,
        soil_moisture_7_28cm=recent_moisture_root if recent_moisture_root is not None else moisture_root,
        soil_moisture_28_100cm=history.get("soil_moisture_28_to_100cm_mean"),
        precip_30d_mm=rain30,
        et0_30d_mm=et0_30,
        recent_precip_5d_mm=history.get("rainfall_5d_live_mm"),
        recent_et0_5d_mm=history.get("et0_fao_evapotranspiration_5d_live_mm"),
        recent_soil_moisture_surface=recent_moisture_surface,
        recent_soil_moisture_root=recent_moisture_root,
        water_balance_30d_mm=round(rain30 - et0_30, 2) if rain30 is not None and et0_30 is not None else None,
        precip_90d_mm=rain90,
        et0_90d_mm=et0_90,
        seasonal_precip_30d_mm=seasonal_rain30,
        seasonal_et0_30d_mm=seasonal_et030,
        seasonal_precip_90d_mm=seasonal_rain90,
        seasonal_et0_90d_mm=seasonal_et090,
        api_14d=history.get("api_14d_mm"),
        cdd_count=history.get("cdd_count_live", history.get("cdd_count")),
        spi_30d=None,
        spi_90d=None,
        tmax_anomaly_14d=None,
        feature_completeness_ratio=completeness,
        weather_fetched_at_utc=now,
        unavailable_feeds=[item.get("feed", "unknown") for item in raw.get("unavailable", [])],
    )
    return features, raw
