"""Reference tables loaded from KSDMA datasets (see import_ksdma.py).

These are owned by the chatbot module, so they never clash with your Shelter Management /
Resource Inventory tables. Later you can merge them into those modules if you wish.
No personal data is stored here (no owner names, phone numbers of individuals, addresses).
"""
from sqlalchemy import Column, Integer, String, Float, Text, Index
from app.core.database import Base


class RefCamp(Base):
    __tablename__ = "ref_camps"
    id = Column(Integer, primary_key=True, autoincrement=True)
    district = Column(String(30), index=True)
    name = Column(String(200))
    lsg = Column(String(120), index=True)        # local self-government body (panchayat / municipality)
    village = Column(String(120), index=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    capacity = Column(Integer, nullable=True)    # None = not recorded / unreadable in source
    toilets = Column(String(5), nullable=True)   # yes / no / None
    disabled_friendly = Column(String(5), nullable=True)
    camp_type = Column(String(10), nullable=True)  # source codes A-D; meaning not documented, never shown to users
    __table_args__ = (Index("ix_ref_camps_latlng", "lat", "lng"),)


class RefWaterKiosk(Base):
    __tablename__ = "ref_water_kiosks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    district = Column(String(30), index=True)
    taluk = Column(String(60), index=True)
    lat = Column(Float)
    lng = Column(Float)
    __table_args__ = (Index("ix_ref_kiosks_latlng", "lat", "lng"),)


class RefHospital(Base):
    __tablename__ = "ref_hospitals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    district = Column(String(30), index=True)
    name = Column(String(200))
    kind = Column(String(12))                    # government | private
    total_beds = Column(Integer, nullable=True)  # government sheets
    rooms = Column(Integer, nullable=True)       # private sheets: private rooms
    ward_beds = Column(Integer, nullable=True)   # private sheets: beds in wards
    icu_beds = Column(Integer, nullable=True)
    ventilators = Column(Integer, nullable=True)
    ambulances = Column(Integer, nullable=True)
    data_as_of = Column(String(10))              # survey date, e.g. 2020-06


class RefTalukEOC(Base):
    __tablename__ = "ref_taluk_eoc"
    id = Column(Integer, primary_key=True, autoincrement=True)
    district = Column(String(30), index=True)
    taluk = Column(String(60), index=True)
    phones = Column(Text)                        # comma separated, validated numbers only
    source_note = Column(String(120))
