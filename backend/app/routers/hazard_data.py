from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.location import Location
from app.services.hazard_weather import get_hazard_weather


router = APIRouter(prefix="/api/hazard-data", tags=["Hazard Data"])


@router.get("/{location_id}")
def get_constituency_hazard_inputs(location_id: int, db: Session = Depends(get_db)):
    """Fetch weather inputs for drought and landslide work at one constituency."""
    location = db.query(Location).filter(Location.id == location_id).first()
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")
    if location.location_type.upper() not in {"LAC", "CONSTITUENCY"}:
        raise HTTPException(status_code=422, detail="Hazard inputs are currently served for constituency locations")
    if location.latitude is None or location.longitude is None:
        raise HTTPException(status_code=400, detail="Constituency latitude and longitude are required")

    data = get_hazard_weather(location.latitude, location.longitude)
    return {
        "location_id": location.id,
        "location_name": location.name,
        "location_type": location.location_type,
        **data,
    }
