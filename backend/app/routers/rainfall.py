
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.location import Location
from app.models.rainfall import RainfallData


router = APIRouter(
    prefix="/api/rainfall",
    tags=["Rainfall"],
)


@router.get("/{location_id}")
def get_rainfall(
    location_id: int,
    db: Session = Depends(get_db),
):
    # Check whether the requested location exists.
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

    # Retrieve the latest rainfall record for this location.
    rainfall = (
        db.query(RainfallData)
        .filter(RainfallData.location_id == location_id)
        .order_by(RainfallData.recorded_at.desc())
        .first()
    )

    if rainfall is None:
        raise HTTPException(
            status_code=404,
            detail="Rainfall data not found for this location",
        )

    return {
        "location_id": location.id,
        "location_name": location.name,
        "rainfall_24h": rainfall.rainfall_24h,
        "rainfall_72h": rainfall.rainfall_72h,
        "rainfall_7d": rainfall.rainfall_7d,
        "recorded_at": rainfall.recorded_at,
    }