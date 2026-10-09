
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.location import Location
from app.models.risk import RiskData


router = APIRouter(
    prefix="/api/risk",
    tags=["Risk"],
)


@router.get("/{location_id}")
def get_risk(
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

    # Retrieve the latest risk record for this location
    risk = (
        db.query(RiskData)
        .filter(RiskData.location_id == location_id)
        .order_by(RiskData.recorded_at.desc())
        .first()
    )

    if risk is None:
        raise HTTPException(
            status_code=404,
            detail="Risk data not found for this location",
        )

    return {
        "location_id": location.id,
        "location_name": location.name,
        "flood_risk": risk.flood_risk,
        "landslide_risk": risk.landslide_risk,
        "drought_risk": risk.drought_risk,
        "overall_risk": risk.overall_risk,
        "recorded_at": risk.recorded_at,
    }
