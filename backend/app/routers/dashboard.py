import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.location import Location
from app.models.weather import WeatherData
from app.models.rainfall import RainfallData
from app.models.hazard import HazardData
from app.models.risk import RiskData
from app.services.risk_engine import assess_location
from app.core.rate_limit import limiter


router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
)

_STATIC_DISTRICTS = {
    item["district_id"]: item
    for item in json.loads(
        (Path(__file__).resolve().parents[1] / "data" / "kerala_district_static.json").read_text(encoding="utf-8")
    )["districts"]
}


def _district_coordinates(district: Location):
    if district.latitude is not None and district.longitude is not None:
        return district.latitude, district.longitude
    key = "".join(character for character in district.name.lower() if character.isalpha())
    static = _STATIC_DISTRICTS.get(key)
    if static:
        return static["latitude"], static["longitude"]
    return None, None


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


def serialize_risk(risk: RiskData | None, hazards: HazardData | None = None):
    """Return legacy scores with explicit provenance; never infer from labels."""
    if risk is not None:
        return {
            "recorded_at": risk.recorded_at,
            "score_type": "stored_unverified",
            "scores_available": False,
        }
    return None


@router.get("/risk/{district_id}")
async def get_live_district_risk(district_id: int, db: Session = Depends(get_db)):
    """Fetch live weather features and return a provenance-safe risk contract."""
    district = (db.query(Location).filter(
        Location.id == district_id, Location.location_type == "DISTRICT"
    ).first())
    if district is None:
        raise HTTPException(status_code=404, detail="District not found")
    latitude, longitude = _district_coordinates(district)
    if latitude is None or longitude is None:
        raise HTTPException(status_code=422, detail="District coordinates are required")
    return await asyncio.to_thread(
        assess_location, district.id, district.name, latitude, longitude
    )


@router.get("/risk-map")
async def get_district_risk_map(db: Session = Depends(get_db)):
    """Fetch current Open-Meteo inputs and experimental indices for map districts."""
    try:
        districts = (
            db.query(Location)
            .filter(Location.location_type == "DISTRICT")
            .order_by(Location.name)
            .all()
        )
        semaphore = asyncio.Semaphore(5)

        async def evaluate(district: Location):
            latitude, longitude = _district_coordinates(district)
            if latitude is None or longitude is None:
                return district, None
            async with semaphore:
                result = await asyncio.to_thread(
                    assess_location, district.id, district.name, latitude, longitude
                )
            return district, result

        evaluations = await asyncio.gather(*(evaluate(district) for district in districts))
        results = []
        for district, result in evaluations:
            results.append({
                "district": district.name,
                "district_id": district.id,
                "risk": result,
                "status": result.get("status", "INSUFFICIENT_DATA") if result else "INSUFFICIENT_DATA",
                "source": result.get("metadata", {}).get("source") if result else None,
                "metadata": result.get("metadata") if result else None,
            })
        return results
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to retrieve district risk map data.")


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
        risk_output = serialize_risk(risk, hazards)

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
            "risk": risk_output,
            "data_status": {
                "weather_available": weather is not None,
                "rainfall_available": rainfall is not None,
                "hazards_available": hazards is not None,
                "risk_available": risk_output is not None,
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
@limiter.limit("10/minute")
async def calculate_location_risk(
    request: Request,
    location_id: int,
    db: Session = Depends(get_db),
):
    """Refresh live weather features; scores stay unavailable without a validated model."""

    try:
        get_location_or_404(db, location_id)

        location = get_location_or_404(db, location_id)
        latitude, longitude = _district_coordinates(location)
        if location.location_type.upper() not in {"DISTRICT", "LAC", "CONSTITUENCY"}:
            raise HTTPException(status_code=422, detail="Live risk inputs are unavailable for this location type")
        latitude = location.latitude if location.latitude is not None else latitude
        longitude = location.longitude if location.longitude is not None else longitude
        if latitude is None or longitude is None:
            raise HTTPException(status_code=422, detail="Location coordinates are required")
        return await asyncio.to_thread(assess_location, location.id, location.name, latitude, longitude)

    except HTTPException:
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to calculate risk because of a database error.",
        )
