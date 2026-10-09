
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer
from app.core.database import Base


class RainfallData(Base):
    __tablename__ = "rainfall_data"

    id = Column(Integer, primary_key=True, index=True)

    location_id = Column(
        Integer,
        ForeignKey("locations.id"),
        nullable=False,
        index=True,
    )

    rainfall_24h = Column(Float, nullable=True)
    rainfall_72h = Column(Float, nullable=True)
    rainfall_7d = Column(Float, nullable=True)

    recorded_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )