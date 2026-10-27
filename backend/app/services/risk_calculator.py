import re
from typing import Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.hazard import HazardData
from app.models.risk import RiskData


# Prototype-only scoring values.
# These are illustrative labels, NOT validated disaster probabilities.
HAZARD_LEVEL_SCORES = {
    "LOW": 25.0,
    "MODERATE": 50.0,
    "HIGH": 75.0,
    "VERY HIGH": 100.0,
}

REQUIRED_HAZARDS = (
    "flood_level",
    "landslide_level",
    "drought_level",
)


def score_hazard_level(level: Optional[str]) -> Optional[float]:
    """Convert a recognized hazard label into an illustrative score."""

    if level is None or not level.strip():
        return None

    normalized_level = re.sub(r"\s+", " ", level).strip().upper()
    return HAZARD_LEVEL_SCORES.get(normalized_level)


def calculate_baseline_risk(
    db: Session,
    location_id: int,
) -> RiskData:
    """
    Calculate and save illustrative baseline risk from the latest
    hazard record.

    All three required hazard levels must be present and recognized.
    Missing or invalid levels are never silently treated as zero.
    """

    if location_id <= 0:
        raise ValueError("Location ID must be a positive integer")

    hazards = (
        db.query(HazardData)
        .filter(HazardData.location_id == location_id)
        .order_by(HazardData.recorded_at.desc())
        .first()
    )

    if hazards is None:
        raise ValueError(
            "No hazard data available for this location"
        )

    # Validate all required hazard levels before calculating.
    scores = {}

    for field in REQUIRED_HAZARDS:
        level = getattr(hazards, field)
        score = score_hazard_level(level)

        if score is None:
            raise ValueError(
                f"Missing or unsupported hazard level for {field}. "
                "Expected LOW, MODERATE, HIGH, or VERY HIGH."
            )

        if not 0 <= score <= 100:
            raise ValueError(
                f"Invalid score generated for {field}"
            )

        scores[field] = score

    flood_score = scores["flood_level"]
    landslide_score = scores["landslide_level"]
    drought_score = scores["drought_level"]

    # Equal-weight average for the prototype only.
    overall_score = round(
        (flood_score + landslide_score + drought_score) / 3,
        2,
    )

    if not 0 <= overall_score <= 100:
        raise ValueError(
            "Calculated overall risk is outside the valid 0–100 range"
        )

    risk_record = RiskData(
        location_id=location_id,
        flood_risk=flood_score,
        landslide_risk=landslide_score,
        drought_risk=drought_score,
        overall_risk=overall_score,
    )

    try:
        db.add(risk_record)
        db.commit()
        db.refresh(risk_record)
    except SQLAlchemyError:
        db.rollback()
        raise

    return risk_record
