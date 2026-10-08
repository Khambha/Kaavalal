from sqlalchemy import Column, Float, Integer, String

from app.core.database import Base


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(100), nullable=False, index=True)

    location_type = Column(
        String(30),
        nullable=False,
        index=True,
    )

    parent_id = Column(
        Integer,
        nullable=True,
        index=True,
    )

    latitude = Column(Float, nullable=True)

    longitude = Column(Float, nullable=True)

    area_sq_km = Column(Float, nullable=True)

    population = Column(Integer, nullable=True)

    population_density = Column(Float, nullable=True)

    elevation_m = Column(Float, nullable=True)

    coastal_status = Column(
        String(30),
        nullable=True,
    )