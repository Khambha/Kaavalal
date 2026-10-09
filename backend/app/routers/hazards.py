
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.location import Location
from app.models.hazard import HazardData


router = APIRouter(
    prefix="/api/hazards",
    tags=["Hazards"],
)


@router.get("/{location_id}")
def get_hazards(
    location_id: int,
    db: Session = Depends(get_db),
):
    # Check whether the location exists
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

    # Retrieve the latest hazard record for this location
    hazards = (
        db.query(HazardData)
        .filter(HazardData.location_id == location_id)
        .order_by(HazardData.recorded_at.desc())
        .first()
    )

    if hazards is None:
        raise HTTPException(
            status_code=404,
            detail="Hazard data not found for this location",
        )

    return {
        "location_id": location.id,
        "location_name": location.name,
        "flood_level": hazards.flood_level,
        "landslide_level": hazards.landslide_level,
        "drought_level": hazards.drought_level,
        "earthquake_level": hazards.earthquake_level,
        "coastal_level": hazards.coastal_level,
        "recorded_at": hazards.recorded_at,
    }

