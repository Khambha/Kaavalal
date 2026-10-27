import json
import re
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.admin_user import AdminUser
from app.models.help_request import HelpRequest
from app.models.responder_coverage import ResponderCoverage
from app.models.shelter import Shelter, ShelterRequest, RequestStatusEvent
from app.models.user import User
from app.routers.admin_auth import get_current_admin
from app.routers.auth import get_current_user
from app.routers.help_requests import responder_coverage_query, validate_district_and_lac
from app.services.request_tracking import record_status, event_public

router = APIRouter(prefix="/api/shelters", tags=["Shelters"])
admin_router = APIRouter(prefix="/api/admin/shelters", tags=["Shelters"])


class ShelterCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    building_type: str = Field(min_length=2, max_length=80)
    district: str
    lac: str
    address: str = Field(min_length=2, max_length=500)
    latitude: float = Field(ge=8.0, le=13.0)
    longitude: float = Field(ge=74.0, le=78.0)
    capacity: int = Field(gt=0, le=100000)


class ShelterLocationCheck(BaseModel):
    district: str = Field(min_length=2)
    lac: str = Field(min_length=2)
    latitude: float = Field(ge=8.0, le=13.0)
    longitude: float = Field(ge=74.0, le=78.0)


class ShelterRequestCreate(BaseModel):
    shelter_id: int
    client_request_id: str | None = Field(default=None, max_length=36)
    household_name: str = Field(min_length=2, max_length=150)
    aadhaar_last4: str = Field(pattern=r"^\d{4}$")
    phone: str = Field(min_length=7, max_length=20)
    people_count: int = Field(gt=0, le=1000)
    special_needs: str | None = Field(default=None, max_length=2000)


class RequestDecision(BaseModel):
    status: str = Field(pattern="^(Approved|Rejected)$")


class AssignShelter(BaseModel):
    shelter_id: int


DISTRICT_BOUNDARIES = Path(__file__).resolve().parents[3] / "frontend" / "public" / "Data" / "Kerala_districts.geojson"
DISTRICT_ALIASES = {
    "trivandrum": "thiruvananthapuram",
    "trichur": "thrissur",
    "eranakulam": "ernakulam",
    "wynad": "wayanad",
}


def _district_key(value):
    key = re.sub(r"[^a-z]", "", str(value or "").casefold().replace("district", ""))
    return DISTRICT_ALIASES.get(key, key)


@lru_cache(maxsize=1)
def _load_district_features():
    try:
        with DISTRICT_BOUNDARIES.open("r", encoding="utf-8") as stream:
            return json.load(stream).get("features", [])
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="District boundary data is unavailable; shelter coordinates cannot be verified.") from exc


def _point_in_ring(longitude, latitude, ring):
    inside = False
    previous = ring[-1]
    for current in ring:
        x1, y1 = float(previous[0]), float(previous[1])
        x2, y2 = float(current[0]), float(current[1])
        cross = (longitude - x1) * (y2 - y1) - (latitude - y1) * (x2 - x1)
        if abs(cross) < 1e-10 and min(x1, x2) - 1e-10 <= longitude <= max(x1, x2) + 1e-10 and min(y1, y2) - 1e-10 <= latitude <= max(y1, y2) + 1e-10:
            return True
        if (y1 > latitude) != (y2 > latitude):
            intersection = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
            if longitude < intersection:
                inside = not inside
        previous = current
    return inside


def _point_in_polygon(longitude, latitude, rings):
    return bool(rings) and _point_in_ring(longitude, latitude, rings[0]) and not any(
        _point_in_ring(longitude, latitude, hole) for hole in rings[1:]
    )


def _coordinate_in_district(latitude, longitude, district):
    feature = next(
        (item for item in _load_district_features()
         if _district_key(item.get("properties", {}).get("name")) == _district_key(district)),
        None,
    )
    if not feature:
        raise HTTPException(status_code=503, detail=f"No district boundary is available for {district}.")
    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinates") or []
    if geometry.get("type") == "Polygon":
        polygons = [coordinates]
    elif geometry.get("type") == "MultiPolygon":
        polygons = coordinates
    else:
        raise HTTPException(status_code=503, detail=f"Unsupported boundary data for {district}.")
    return any(_point_in_polygon(longitude, latitude, polygon) for polygon in polygons)


def _validate_shelter_coordinate(district, latitude, longitude):
    if not _coordinate_in_district(latitude, longitude, district):
        raise HTTPException(
            status_code=422,
            detail=f"These coordinates are outside {district}. Check the latitude/longitude order and the Google Maps pin before saving.",
        )


def shelter_public(shelter, can_assign=None):
    return {"id": shelter.id, "name": shelter.name, "building_type": shelter.building_type,
            "district": shelter.district, "lac": shelter.lac, "address": shelter.address,
            "latitude": shelter.latitude, "longitude": shelter.longitude,
            "capacity": shelter.capacity, "occupied": shelter.occupied,
            "available": shelter.capacity - shelter.occupied, "is_active": bool(shelter.is_active),
            **({"can_assign": can_assign} if can_assign is not None else {})}


def request_public(row, db):
    preferred = db.get(Shelter, row.preferred_shelter_id)
    assigned = db.get(Shelter, row.assigned_shelter_id) if row.assigned_shelter_id else None
    return {"id": row.id, "citizen_id": row.citizen_id, "district": row.district, "lac": row.lac,
            "household_name": row.household_name, "aadhaar_last4": row.aadhaar_last4,
            "phone": row.phone, "people_count": row.people_count, "special_needs": row.special_needs,
            "status": row.status, "preferred_shelter": shelter_public(preferred) if preferred else None,
            "assigned_shelter": shelter_public(assigned) if assigned else None,
            "created_at": row.created_at, "updated_at": row.updated_at,
            "eta_estimate_minutes": row.eta_estimate_minutes}


def require_responder(user):
    if user.role not in {"rescuer", "responder"}:
        raise HTTPException(status_code=403, detail="Only rescue personnel can access this action.")


def coverage_has(coverage, district, lac):
    return any(d.casefold() == district.casefold() and l.casefold() == lac.casefold() for d, l in coverage)


@admin_router.get("")
def admin_list(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    if admin.must_change_password:
        raise HTTPException(status_code=403, detail="Change your temporary password before using the admin console.")
    return [shelter_public(s) for s in db.query(Shelter).order_by(Shelter.district, Shelter.name).all()]


@admin_router.post("/validate-location")
def admin_validate_location(data: ShelterLocationCheck, admin: AdminUser = Depends(get_current_admin)):
    if admin.must_change_password:
        raise HTTPException(status_code=403, detail="Change your temporary password before using the admin console.")
    district, lac = validate_district_and_lac(data.district, data.lac)
    _validate_shelter_coordinate(district, data.latitude, data.longitude)
    return {"valid": True, "district": district, "lac": lac, "latitude": data.latitude, "longitude": data.longitude}


@admin_router.post("", status_code=201)
def admin_create(data: ShelterCreate, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    if admin.must_change_password:
        raise HTTPException(status_code=403, detail="Change your temporary password before using the admin console.")
    district, lac = validate_district_and_lac(data.district, data.lac)
    _validate_shelter_coordinate(district, data.latitude, data.longitude)
    shelter = Shelter(**data.model_dump(exclude={"district", "lac"}), district=district, lac=lac, created_by_admin_id=admin.id)
    db.add(shelter)
    db.commit()
    db.refresh(shelter)
    return shelter_public(shelter)


@admin_router.patch("/{shelter_id}")
def admin_update(shelter_id: int, data: ShelterCreate, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    if admin.must_change_password:
        raise HTTPException(status_code=403, detail="Change your temporary password before using the admin console.")
    shelter = db.get(Shelter, shelter_id)
    if not shelter:
        raise HTTPException(status_code=404, detail="Shelter not found.")
    district, lac = validate_district_and_lac(data.district, data.lac)
    _validate_shelter_coordinate(district, data.latitude, data.longitude)
    if data.capacity < shelter.occupied:
        raise HTTPException(status_code=409, detail=f"Capacity cannot be lower than current occupancy ({shelter.occupied}).")
    for field, value in data.model_dump(exclude={"district", "lac"}).items():
        setattr(shelter, field, value)
    shelter.district = district
    shelter.lac = lac
    db.commit()
    db.refresh(shelter)
    return shelter_public(shelter)


@admin_router.patch("/{shelter_id}/active")
def admin_active(shelter_id: int, is_active: bool, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    if admin.must_change_password:
        raise HTTPException(status_code=403, detail="Change your temporary password before using the admin console.")
    shelter = db.get(Shelter, shelter_id)
    if not shelter:
        raise HTTPException(status_code=404, detail="Shelter not found.")
    shelter.is_active = int(is_active)
    db.commit()
    return shelter_public(shelter)


@router.get("")
def public_shelters(db: Session = Depends(get_db)):
    shelters = db.query(Shelter).filter(Shelter.is_active == 1).order_by(Shelter.district, Shelter.name).all()
    # Do not publish stale or malformed coordinates on the citizen map. Admins
    # can still see and correct these rows in the console.
    return [shelter_public(s) for s in shelters if _coordinate_in_district(s.latitude, s.longitude, s.district)]


@router.post("/requests", status_code=201)
def create_request(data: ShelterRequestCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "citizen":
        raise HTTPException(status_code=403, detail="Only citizens can request shelter.")
    shelter = db.get(Shelter, data.shelter_id)
    if not shelter or not shelter.is_active:
        raise HTTPException(status_code=404, detail="The selected shelter is not available.")
    if data.client_request_id and (len(data.client_request_id) < 16 or len(data.client_request_id) > 36):
        raise HTTPException(status_code=422, detail="Invalid client request identifier.")
    if data.client_request_id:
        existing = db.query(ShelterRequest).filter(ShelterRequest.client_request_id == data.client_request_id).first()
        if existing:
            if existing.citizen_id != user.id:
                raise HTTPException(status_code=409, detail="This request identifier is already in use.")
            return request_public(existing, db)
    pending = db.query(ShelterRequest).filter(ShelterRequest.district.ilike(shelter.district), ShelterRequest.lac.ilike(shelter.lac), ShelterRequest.status == "Pending").count()
    row = ShelterRequest(citizen_id=user.id, preferred_shelter_id=shelter.id, district=shelter.district,
                         lac=shelter.lac, household_name=data.household_name.strip(), aadhaar_last4=data.aadhaar_last4,
                         phone=data.phone.strip(), people_count=data.people_count, special_needs=data.special_needs,
                         eta_estimate_minutes=min(360, 60 + pending * 15), client_request_id=data.client_request_id)
    db.add(row)
    db.flush()
    record_status(db, shelter_request_id=row.id, status="Pending", actor_role="system", note="Shelter request received and routed to the local rescue team.")
    db.commit()
    db.refresh(row)
    return request_public(row, db)


@router.get("/requests/my")
def my_requests(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [request_public(r, db) for r in db.query(ShelterRequest).filter(ShelterRequest.citizen_id == user.id).order_by(ShelterRequest.created_at.desc()).all()]


@router.get("/requests/my/{request_id}/history")
def my_shelter_request_history(request_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(ShelterRequest, request_id)
    if not row:
        raise HTTPException(status_code=404, detail="Shelter request not found.")
    if row.citizen_id != user.id:
        if user.role not in {"responder", "rescuer"} or not coverage_has(responder_coverage_query(db, user), row.district, row.lac):
            raise HTTPException(status_code=403, detail="You cannot access this request history.")
    events = db.query(RequestStatusEvent).filter(RequestStatusEvent.shelter_request_id == row.id).order_by(RequestStatusEvent.created_at.asc(), RequestStatusEvent.id.asc()).all()
    return [event_public(event) for event in events]


@router.get("/responder/requests")
def responder_requests(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_responder(user)
    coverage = responder_coverage_query(db, user)
    if not coverage:
        return []
    clauses = [((ShelterRequest.district.ilike(d)) & (ShelterRequest.lac.ilike(l))) for d, l in coverage]
    rows = db.query(ShelterRequest).filter(or_(*clauses)).order_by(ShelterRequest.created_at.desc()).all()
    return [request_public(r, db) for r in rows]


@router.get("/responder/all")
def responder_shelters(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_responder(user)
    coverage = responder_coverage_query(db, user)
    rows = db.query(Shelter).filter(Shelter.is_active == 1).order_by(Shelter.district, Shelter.name).all()
    return [shelter_public(s, coverage_has(coverage, s.district, s.lac)) for s in rows]


@router.post("/requests/{request_id}/decision")
def decide_request(request_id: int, data: RequestDecision, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_responder(user)
    row = db.query(ShelterRequest).filter(ShelterRequest.id == request_id).with_for_update().first()
    if not row:
        raise HTTPException(status_code=404, detail="Shelter request not found.")
    coverage = responder_coverage_query(db, user)
    if not coverage_has(coverage, row.district, row.lac):
        raise HTTPException(status_code=403, detail="This request is outside your assigned LAC coverage.")
    if row.status != "Pending":
        raise HTTPException(status_code=409, detail="This request has already been reviewed.")
    row.status = data.status
    row.responder_id = user.id
    record_status(db, shelter_request_id=row.id, status=row.status, actor_role=user.role,
                  note="Shelter request approved by the local rescue team." if row.status == "Approved" else "Shelter request declined by the local rescue team.")
    db.commit()
    db.refresh(row)
    return request_public(row, db)


@router.post("/requests/{request_id}/assign")
def assign_request(request_id: int, data: AssignShelter, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_responder(user)
    row = db.query(ShelterRequest).filter(ShelterRequest.id == request_id).with_for_update().first()
    shelter = db.query(Shelter).filter(Shelter.id == data.shelter_id, Shelter.is_active == 1).with_for_update().first()
    if not row or not shelter:
        raise HTTPException(status_code=404, detail="Request or shelter not found.")
    coverage = responder_coverage_query(db, user)
    if not coverage_has(coverage, shelter.district, shelter.lac):
        raise HTTPException(status_code=403, detail="You can only assign people to shelters in your LAC coverage.")
    if row.status not in {"Approved", "Assigned"}:
        raise HTTPException(status_code=409, detail="Approve this shelter request before assigning a shelter.")
    current_shelter = db.get(Shelter, row.assigned_shelter_id) if row.assigned_shelter_id else None
    reserved_here = row.people_count if current_shelter and current_shelter.id == shelter.id else 0
    if shelter.capacity - shelter.occupied + reserved_here < row.people_count:
        raise HTTPException(status_code=409, detail="There is not enough shelter capacity for this household.")
    if row.assigned_shelter_id:
        old = db.get(Shelter, row.assigned_shelter_id)
        if old:
            old.occupied = max(0, old.occupied - row.people_count)
    previous_shelter_id = row.assigned_shelter_id
    previous_status = row.status
    shelter.occupied += row.people_count
    row.assigned_shelter_id = shelter.id
    row.status = "Assigned"
    row.responder_id = user.id
    if previous_status != "Assigned" or previous_shelter_id != shelter.id:
        record_status(db, shelter_request_id=row.id, status="Assigned", actor_role=user.role, note=f"Household assigned to {shelter.name}.")
    db.commit()
    db.refresh(row)
    return request_public(row, db)


@router.post("/{shelter_id}/occupancy")
def change_occupancy(shelter_id: int, change: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_responder(user)
    shelter = db.get(Shelter, shelter_id)
    if not shelter:
        raise HTTPException(status_code=404, detail="Shelter not found.")
    coverage = responder_coverage_query(db, user)
    if not coverage_has(coverage, shelter.district, shelter.lac):
        raise HTTPException(status_code=403, detail="You can only update shelters in your LAC coverage.")
    if change == 0 or shelter.occupied + change < 0 or shelter.occupied + change > shelter.capacity:
        raise HTTPException(status_code=409, detail="Occupancy must stay between zero and capacity.")
    shelter.occupied += change
    db.commit()
    db.refresh(shelter)
    return shelter_public(shelter)


@router.post("/help-requests/{request_id}/assign")
def assign_emergency_shelter(request_id: int, data: AssignShelter, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_responder(user)
    help_request = db.query(HelpRequest).filter(HelpRequest.id == request_id).with_for_update().first()
    shelter = db.query(Shelter).filter(Shelter.id == data.shelter_id, Shelter.is_active == 1).with_for_update().first()
    if not help_request or not shelter:
        raise HTTPException(status_code=404, detail="Help request or shelter not found.")
    coverage = responder_coverage_query(db, user)
    if not coverage_has(coverage, help_request.district, help_request.lac):
        raise HTTPException(status_code=403, detail="This emergency is outside your assigned LAC coverage.")
    if not coverage_has(coverage, shelter.district, shelter.lac):
        raise HTTPException(status_code=403, detail="You can only assign people to shelters in your LAC coverage.")
    if help_request.status in {"Resolved", "Rejected"}:
        raise HTTPException(status_code=409, detail="A closed emergency cannot be assigned a shelter.")
    count = help_request.people_affected
    current_shelter = db.get(Shelter, help_request.shelter_id) if help_request.shelter_id else None
    reserved_here = count if current_shelter and current_shelter.id == shelter.id else 0
    if shelter.capacity - shelter.occupied + reserved_here < count:
        raise HTTPException(status_code=409, detail="There is not enough shelter capacity for this emergency.")
    if help_request.shelter_id:
        old = db.get(Shelter, help_request.shelter_id)
        if old:
            old.occupied = max(0, old.occupied - count)
    shelter.occupied += count
    help_request.shelter_id = shelter.id
    db.commit()
    return {"message": "Shelter assigned to emergency.", "shelter": shelter_public(shelter)}
