
from pydantic import BaseModel, ConfigDict


class LocationResponse(BaseModel):
    id: int
    name: str
    location_type: str
    parent_id: int | None = None

    administrative_code: str | None = None

    latitude: float | None = None
    longitude: float | None = None

    area_sq_km: float | None = None
    population: int | None = None
    population_density: float | None = None
    elevation_m: float | None = None
    coastal_status: str | None = None

    model_config = ConfigDict(from_attributes=True)
