
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer
from app.core.database import Base


class RiskData(Base):
    __tablename__ = "risk_data"

    id = Column(Integer, primary_key=True, index=True)

    location_id = Column(
        Integer,
        ForeignKey("locations.id"),
        nullable=False,
        index=True,
    )

    flood_risk = Column(Float, nullable=True)
    landslide_risk = Column(Float, nullable=True)
    drought_risk = Column(Float, nullable=True)
    overall_risk = Column(Float, nullable=True)

    recorded_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    