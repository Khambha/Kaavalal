from pydantic import BaseModel, ConfigDict


class LocationBase(BaseModel):
    name: str
    location_type: str
    parent_id: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    area_sq_km: float | None = None
    population: int | None = None
    population_density: float | None = None
    elevation_m: float | None = None
    coastal_status: str | None = None


class LocationResponse(LocationBase):
    id: int

    model_config = ConfigDict(
        from_attributes=True
    )