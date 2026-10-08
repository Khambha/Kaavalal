from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.location import Location
from app.schemas.location import LocationResponse


router = APIRouter(
    prefix="/api/districts",
    tags=["Districts"],
)


@router.get(
    "",
    response_model=list[LocationResponse],
)
def get_districts(
    db: Session = Depends(get_db),
):
    districts = (
        db.query(Location)
        .filter(Location.location_type == "DISTRICT")
        .order_by(Location.name)
        .all()
    )

    return districts


@router.get(
    "/{district_id}",
    response_model=LocationResponse,
)
def get_district(
    district_id: int,
    db: Session = Depends(get_db),
):
    district = (
        db.query(Location)
        .filter(
            Location.id == district_id,
            Location.location_type == "DISTRICT",
        )
        .first()
    )

    if district is None:
        raise HTTPException(
            status_code=404,
            detail="District not found",
        )

    return district