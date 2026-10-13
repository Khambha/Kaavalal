from typing import Optional

from sqlalchemy.orm import Session

from app.models.hazard import HazardData
from app.models.risk import RiskData


# Prototype-only values. Replace with validated, documented scoring
# rules before presenting results as real-world risk assessments.
HAZARD_LEVEL_SCORES = {
    "LOW": 25.0,
    "MODERATE": 50.0,
    "HIGH": 75.0,
    "VERY HIGH": 100.0,
}


def score_hazard_level(level: Optional[str]) -> Optional[float]:
    """Convert a known hazard label into a prototype score."""
    if not level:
        return None

    return HAZARD_LEVEL_SCORES.get(level.strip().upper())


def calculate_baseline_risk(db: Session, location_id: int) -> RiskData:
    """
    Calculate and save a prototype risk record from the latest
    available hazard-level record for a location.
    """
    hazards = (
        db.query(HazardData)
        .filter(HazardData.location_id == location_id)
        .order_by(HazardData.recorded_at.desc())
        .first()
    )

    if hazards is None:
        raise ValueError("No hazard data available for this location")

    flood_score = score_hazard_level(hazards.flood_level)
    landslide_score = score_hazard_level(hazards.landslide_level)
    drought_score = score_hazard_level(hazards.drought_level)

    available_scores = [
        score
        for score in (flood_score, landslide_score, drought_score)
        if score is not None
    ]

    if not available_scores:
        raise ValueError("No usable hazard levels available for scoring")

    overall_score = sum(available_scores) / len(available_scores)

    risk_record = RiskData(
        location_id=location_id,
        flood_risk=flood_score,
        landslide_risk=landslide_score,
        drought_risk=drought_score,
        overall_risk=round(overall_score, 2),
    )

    db.add(risk_record)
    db.commit()
    db.refresh(risk_record)

    return risk_record