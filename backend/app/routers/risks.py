
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.location import Location
from app.schemas.flood import FloodDemoPredictionRequest
from app.services.flood_demo_model import predict_flood_demo
from app.services.risk_engine import assess_location
from app.core.rate_limit import limiter
from app.core.config import settings


router = APIRouter(
    prefix="/api/risk",
    tags=["Risk"],
)


if settings.ENABLE_DEMO_MODELS:
    @router.post("/flood/demo-predict")
    def predict_flood_for_demo(data: FloodDemoPredictionRequest):
        """Return a clearly labeled synthetic demo score for one ~10 km grid cell."""
        try:
            prediction = predict_flood_demo(data.features.model_dump())
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        return {
            "grid_id": data.grid_id,
            "latitude": data.latitude,
            "longitude": data.longitude,
            "target": "flood_occurred_next_72h",
            "demo_score_percent": prediction.pop("score_percent"),
            "simulated": True,
            "prediction": prediction,
        }


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

    return {
        "location_id": location.id,
        "location_name": location.name,
        "status": "INSUFFICIENT_DATA",
        "score": None,
        "reason": "Legacy scores are not exposed as validated risk. Use /api/dashboard/risk/{district_id} for live weather features.",
    }

@router.post("/{location_id}/calculate")
@limiter.limit("10/minute")
async def calculate_risk(
    request: Request,
    location_id: int,
    db: Session = Depends(get_db),
):
    # Verify that the location exists
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

    if location.latitude is None or location.longitude is None:
        raise HTTPException(status_code=422, detail="Location coordinates are required")
    return await asyncio.to_thread(
        assess_location, location.id, location.name, location.latitude, location.longitude
    )
