from pydantic import BaseModel, ConfigDict, Field


class FloodDemoFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rainfall_1h_mm: float = Field(ge=0, le=1000)
    rainfall_24h_mm: float = Field(ge=0, le=2000)
    rainfall_72h_mm: float = Field(ge=0, le=4000)
    rainfall_7d_mm: float = Field(ge=0, le=8000)
    rainfall_30d_mm: float = Field(ge=0, le=12000)
    temperature_2m_c: float = Field(ge=-10, le=60)
    relative_humidity_2m_pct: float = Field(ge=0, le=100)
    surface_pressure_hpa: float = Field(ge=800, le=1100)
    cloud_cover_pct: float = Field(ge=0, le=100)
    wind_speed_10m_kmh: float = Field(ge=0, le=400)
    elevation_m: float = Field(ge=-500, le=9000)
    slope_deg: float = Field(ge=0, le=90)
    distance_to_river_m: float = Field(ge=0, le=1_000_000)
    soil_moisture: float = Field(ge=0, le=1)
    river_water_level_m: float = Field(ge=-20, le=100)
    historical_flood_event_count: int = Field(ge=0, le=10000)


class FloodDemoPredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grid_id: str = Field(min_length=1, max_length=80)
    latitude: float = Field(ge=8.0, le=13.0)
    longitude: float = Field(ge=74.0, le=78.0)
    features: FloodDemoFeatures
