from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint

from app.core.database import Base


class ResponderCoverage(Base):
    __tablename__ = "responder_lac_coverage"
    __table_args__ = (
        UniqueConstraint("responder_id", "district", "lac", name="uq_responder_lac_coverage"),
    )

    id = Column(Integer, primary_key=True, index=True)
    responder_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    district = Column(String(100), nullable=False)
    lac = Column(String(150), nullable=False)
