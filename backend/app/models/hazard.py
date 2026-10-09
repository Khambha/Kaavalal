
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from app.core.database import Base


class HazardData(Base):
    __tablename__ = "hazard_data"

    id = Column(Integer, primary_key=True, index=True)

    location_id = Column(
        Integer,
        ForeignKey("locations.id"),
        nullable=False,
        index=True,
    )

    flood_level = Column(String(20), nullable=True)
    landslide_level = Column(String(20), nullable=True)
    drought_level = Column(String(20), nullable=True)
    earthquake_level = Column(String(20), nullable=True)
    coastal_level = Column(String(20), nullable=True)

    recorded_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )