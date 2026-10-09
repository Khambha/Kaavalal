
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.location import Location
from app.models.weather import WeatherData
from app.models.rainfall import RainfallData
from app.models.hazard import HazardData
from app.models.risk import RiskData


router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
)


@router.get("/{location_id}")
def get_dashboard(
    location_id: int,
    db: Session = Depends(get_db),
):
    # 1. Find the requested location
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

    # 2. Get the latest weather record
    weather = (
        db.query(WeatherData)
        .filter(WeatherData.location_id == location_id)
        .order_by(WeatherData.recorded_at.desc())
        .first()
    )

    # 3. Get the latest rainfall record
    rainfall = (
        db.query(RainfallData)
        .filter(RainfallData.location_id == location_id)
        .order_by(RainfallData.recorded_at.desc())
        .first()
    )

    # 4. Get the latest hazard record
    hazards = (
        db.query(HazardData)
        .filter(HazardData.location_id == location_id)
        .order_by(HazardData.recorded_at.desc())
        .first()
    )

    # 5. Get the latest risk record
    risk = (
        db.query(RiskData)
        .filter(RiskData.location_id == location_id)
        .order_by(RiskData.recorded_at.desc())
        .first()
    )

    # 6. Return all dashboard information together
    return {
        "location": {
            "id": location.id,
            "name": location.name,
            "location_type": location.location_type,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "population": location.population,
            "area_sq_km": location.area_sq_km,
            "elevation_m": location.elevation_m,
            "coastal_status": location.coastal_status,
        },
        "weather": (
            {
                "temperature": weather.temperature,
                "humidity": weather.humidity,
                "wind_speed": weather.wind_speed,
                "recorded_at": weather.recorded_at,
            }
            if weather else None
        ),
        "rainfall": (
            {
                "rainfall_24h": rainfall.rainfall_24h,
                "rainfall_72h": rainfall.rainfall_72h,
                "rainfall_7d": rainfall.rainfall_7d,
                "recorded_at": rainfall.recorded_at,
            }
            if rainfall else None
        ),
        "hazards": (
            {
                "flood_level": hazards.flood_level,
                "landslide_level": hazards.landslide_level,
                "drought_level": hazards.drought_level,
                "earthquake_level": hazards.earthquake_level,
                "coastal_level": hazards.coastal_level,
                "recorded_at": hazards.recorded_at,
            }
            if hazards else None
        ),
        "risk": (
            {
                "flood_risk": risk.flood_risk,
                "landslide_risk": risk.landslide_risk,
                "drought_risk": risk.drought_risk,
                "overall_risk": risk.overall_risk,
                "recorded_at": risk.recorded_at,
            }
            if risk else None
        ),
    }

