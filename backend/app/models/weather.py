
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer
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

    recorded_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    