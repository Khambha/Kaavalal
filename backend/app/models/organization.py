from sqlalchemy import Column, Integer, String, Boolean, DateTime

from app.core.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)

    organization_code = Column(
        String(50),
        unique=True,
        nullable=False,
    )

    organization_name = Column(
        String(150),
        nullable=False,
    )

    organization_type = Column(
        String(50),
        nullable=False,
    )

    district = Column(
        String(100),
        nullable=True,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at = Column(
        DateTime,
        nullable=True,
    )