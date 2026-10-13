from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.location import Location
from app.models.weather import WeatherData
from app.models.rainfall import RainfallData
from app.models.hazard import HazardData
from app.models.risk import RiskData
from app.services.risk_calculator import calculate_baseline_risk
from app.services.imd_mock_importer import import_imd_mock_data


router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
)


def get_location_or_404(db: Session, location_id: int) -> Location:
    """Return a location or raise 404 when it does not exist."""

    location = (
        db.query(Location)
        .filter(Location.id == location_id)
        .first()
    )

    if location is None:
        raise HTTPException(
            status_code=404,
            detail=f"Location with ID {location_id} not found",
        )

    return location


@router.get("/{location_id}")
def get_dashboard(
    location_id: int,
    db: Session = Depends(get_db),
):
    """Return location details and the latest available dashboard data."""

    try:
        location = get_location_or_404(db, location_id)

        weather = (
            db.query(WeatherData)
            .filter(WeatherData.location_id == location_id)
            .order_by(WeatherData.recorded_at.desc())
            .first()
        )

        rainfall = (
            db.query(RainfallData)
            .filter(RainfallData.location_id == location_id)
            .order_by(RainfallData.recorded_at.desc())
            .first()
        )

        hazards = (
            db.query(HazardData)
            .filter(HazardData.location_id == location_id)
            .order_by(HazardData.recorded_at.desc())
            .first()
        )

        risk = (
            db.query(RiskData)
            .filter(RiskData.location_id == location_id)
            .order_by(RiskData.recorded_at.desc())
            .first()
        )

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
                    "source": weather.source,
                }
                if weather else None
            ),
            "rainfall": (
                {
                    "rainfall_24h": rainfall.rainfall_24h,
                    "rainfall_72h": rainfall.rainfall_72h,
                    "rainfall_7d": rainfall.rainfall_7d,
                    "recorded_at": rainfall.recorded_at,
                    "source": rainfall.source,
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
            "data_status": {
                "weather_available": weather is not None,
                "rainfall_available": rainfall is not None,
                "hazards_available": hazards is not None,
                "risk_available": risk is not None,
                "is_sample_data": True,
            },
        }

    except HTTPException:
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve dashboard data. Check the database connection.",
        )


@router.post("/{location_id}/calculate-risk")
def calculate_location_risk(
    location_id: int,
    db: Session = Depends(get_db),
):
    """Calculate and return the illustrative baseline risk for a location."""

    try:
        get_location_or_404(db, location_id)

        risk = calculate_baseline_risk(db, location_id)

        return {
            "location_id": risk.location_id,
            "flood_risk": risk.flood_risk,
            "landslide_risk": risk.landslide_risk,
            "drought_risk": risk.drought_risk,
            "overall_risk": risk.overall_risk,
            "recorded_at": risk.recorded_at,
            "score_type": "illustrative_baseline",
        }

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to calculate risk because of a database error.",
        )


@router.post("/mock-weather/import")
def import_mock_weather(
    db: Session = Depends(get_db),
):
    """
    Development-only endpoint for importing mock weather data.
    Do not expose this endpoint in production.
    """

    try:
        result = import_imd_mock_data(db)

        return {
            "message": "Mock weather import completed",
            **result,
        }

    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="Mock weather data file was not found.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Mock import failed because of a database error.",
        )
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Mock import failed. Check the backend terminal logs.",
        )
