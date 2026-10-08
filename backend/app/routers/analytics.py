from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.location import Location


router = APIRouter(
    prefix="/api/analytics",
    tags=["Analytics"],
)


def get_location_statistics(db: Session):
    total_locations = (
        db.query(func.count(Location.id))
        .scalar()
    )

    total_districts = (
        db.query(func.count(Location.id))
        .filter(
            Location.location_type == "DISTRICT"
        )
        .scalar()
    )

    coastal_districts = (
        db.query(func.count(Location.id))
        .filter(
            Location.location_type == "DISTRICT",
            Location.coastal_status == "COASTAL",
        )
        .scalar()
    )

    inland_districts = (
        db.query(func.count(Location.id))
        .filter(
            Location.location_type == "DISTRICT",
            Location.coastal_status == "INLAND",
        )
        .scalar()
    )

    return {
        "total_locations": total_locations,
        "total_districts": total_districts,
        "coastal_districts": coastal_districts,
        "inland_districts": inland_districts,
    }


def get_geographic_statistics(db: Session):
    total_districts = (
        db.query(func.count(Location.id))
        .filter(
            Location.location_type == "DISTRICT"
        )
        .scalar()
    )

    coastal_districts = (
        db.query(func.count(Location.id))
        .filter(
            Location.location_type == "DISTRICT",
            Location.coastal_status == "COASTAL",
        )
        .scalar()
    )

    inland_districts = (
        db.query(func.count(Location.id))
        .filter(
            Location.location_type == "DISTRICT",
            Location.coastal_status == "INLAND",
        )
        .scalar()
    )

    districts_with_coordinates = (
        db.query(func.count(Location.id))
        .filter(
            Location.location_type == "DISTRICT",
            Location.latitude.is_not(None),
            Location.longitude.is_not(None),
        )
        .scalar()
    )

    return {
        "total_districts": total_districts,
        "coastal_districts": coastal_districts,
        "inland_districts": inland_districts,
        "districts_with_coordinates": districts_with_coordinates,
    }


def get_district_breakdown(db: Session):
    districts = (
        db.query(Location)
        .filter(
            Location.location_type == "DISTRICT"
        )
        .order_by(Location.name)
        .all()
    )

    return [
        {
            "id": district.id,
            "name": district.name,
            "latitude": district.latitude,
            "longitude": district.longitude,
            "coastal_status": district.coastal_status,
            "population": district.population,
            "population_density": district.population_density,
            "elevation_m": district.elevation_m,
            "area_sq_km": district.area_sq_km,
        }
        for district in districts
    ]


@router.get("/overview")
def get_analytics_overview(
    db: Session = Depends(get_db),
):
    statistics = get_location_statistics(db)

    return {
        "module": "Kerala Disaster Management Analytics",
        "status": "active",
        "locations": statistics,
    }


@router.get("/incidents")
def get_incident_analytics():
    return {
        "message": "Incident analytics will be connected when incident data is available"
    }


@router.get("/resources")
def get_resource_analytics():
    return {
        "message": "Resource analytics will be connected when resource data is available"
    }


@router.get("/risk")
def get_risk_analytics():
    return {
        "message": "Risk analytics will be connected when risk data is available"
    }


@router.get("/districts")
def get_district_analytics(
    db: Session = Depends(get_db),
):
    statistics = get_location_statistics(db)
    districts = get_district_breakdown(db)

    return {
        "summary": statistics,
        "districts": districts,
    }


@router.get("/geography")
def get_geographic_analytics(
    db: Session = Depends(get_db),
):
    return get_geographic_statistics(db)