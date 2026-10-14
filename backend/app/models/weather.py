
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String

from app.core.database import Base


class WeatherData(Base):
    __tablename__ = "weather_data"

    id = Column(Integer, primary_key=True, index=True)

    location_id = Column(
        Integer,
        ForeignKey("locations.id"),
        nullable=False,
        index=True,
    )

    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    wind_speed = Column(Float, nullable=True)

    # MOCK, IMD, or another identified provider
    source = Column(
        String(30),
        nullable=False,
        default="MOCK",
    )

    recorded_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
