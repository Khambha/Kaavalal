
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.location import Location
from app.models.weather import WeatherData


router = APIRouter(
    prefix="/api/weather",
    tags=["Weather"],
)


@router.get("/{location_id}")
def get_weather(
    location_id: int,
    db: Session = Depends(get_db),
):
    # Confirm that the requested location exists.
    location = (
        db.query(Location)
        .filter(Location.id == location_id)
        .first()
    )

    if location is None:
        raise HTTPException(
            status_code=404,
            detail="Location not found",
        )

    # Retrieve the latest weather record for that location.
    weather = (
        db.query(WeatherData)
        .filter(WeatherData.location_id == location_id)
        .order_by(WeatherData.recorded_at.desc())
        .first()
    )

    if weather is None:
        raise HTTPException(
            status_code=404,
            detail="Weather data not found for this location",
        )

    return {
        "location_id": location.id,
        "location_name": location.name,
        "temperature": weather.temperature,
        "humidity": weather.humidity,
        "wind_speed": weather.wind_speed,
        "recorded_at": weather.recorded_at,
    }