import json
import re
import uuid
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.core.rate_limit import limiter
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
    is_active: bool = True


class ShelterLocationCheck(BaseModel):
    district: str = Field(min_length=2)
    lac: str = Field(min_length=2)
    latitude: float = Field(ge=8.0, le=13.0)
    longitude: float = Field(ge=74.0, le=78.0)


class ShelterLocationSearch(BaseModel):
    query: str = Field(min_length=3, max_length=300)
    district: str = Field(min_length=2, max_length=100)


class ShelterRequestCreate(BaseModel):
    shelter_id: int
    client_request_id: str | None = Field(default=None, max_length=36)
    household_name: str = Field(min_length=2, max_length=150)
    aadhaar_last4: str = Field(pattern=r"^\d{4}$")
    phone: str = Field(min_length=7, max_length=20)
    people_count: int = Field(gt=0, le=1000)
    citizen_location: str | None = Field(default=None, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    reason: str | None = Field(default=None, max_length=2000)
    special_needs: str | None = Field(default=None, max_length=2000)


class RequestDecision(BaseModel):
    status: str = Field(pattern="^(Approved|Rejected)$")
    shelter_id: int | None = None


class AssignShelter(BaseModel):
    shelter_id: int


DISTRICT_BOUNDARIES = Path(__file__).resolve().parents[3] / "frontend" / "public" / "Data" / "Kerala_districts.geojson"
SHELTER_REQUEST_UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads" / "shelter_requests"
SHELTER_REQUEST_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_ID_PHOTO_BYTES = 5 * 1024 * 1024
ALLOWED_ID_PHOTO_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
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


@admin_router.post("/geocode")
@limiter.limit("12/minute")
def admin_geocode_shelter_location(
    request: Request,
    data: ShelterLocationSearch,
    admin: AdminUser = Depends(get_current_admin),
):
    """Search a place name and return Kerala map points; the key stays server-side."""
    if admin.must_change_password:
        raise HTTPException(status_code=403, detail="Change your temporary password before using the admin console.")
    if not settings.GOOGLE_MAPS_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Google Maps location search is not configured. Add GOOGLE_MAPS_API_KEY to the backend environment.",
        )

    address = f"{data.query.strip()}, {data.district.strip()}, Kerala, India"
    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={
                "address": address,
                "components": "country:IN",
                "region": "in",
                "key": settings.GOOGLE_MAPS_API_KEY,
            },
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        raise HTTPException(status_code=502, detail="Google Maps location search is temporarily unavailable.") from None

    if payload.get("status") == "OVER_QUERY_LIMIT":
        raise HTTPException(status_code=429, detail="Google Maps location search has reached its current quota.")
    if payload.get("status") not in {"OK", "ZERO_RESULTS"}:
        raise HTTPException(status_code=502, detail="Google Maps could not complete this location search.")

    results = []
    for item in payload.get("results", []):
        point = (item.get("geometry") or {}).get("location") or {}
        latitude, longitude = point.get("lat"), point.get("lng")
        if latitude is None or longitude is None or not (8 <= latitude <= 13 and 74 <= longitude <= 78):
            continue
        if not _coordinate_in_district(latitude, longitude, data.district):
            continue
        place_id = item.get("place_id")
        maps_params = {"api": "1", "query": f"{latitude},{longitude}"}
        if place_id:
            maps_params["query_place_id"] = place_id
        results.append({
            "formatted_address": item.get("formatted_address") or data.query.strip(),
            "latitude": latitude,
            "longitude": longitude,
            "place_id": place_id,
            "map_url": "https://www.google.com/maps/search/?" + urlencode(maps_params),
        })
        if len(results) == 5:
            break
    if not results:
        raise HTTPException(status_code=404, detail="No matching location was found in Kerala. Try a nearby landmark or local-body name.")
    return {"results": results}


def shelter_public(shelter, can_assign=None):
    return {"id": shelter.id, "name": shelter.name, "building_type": shelter.building_type,
            "district": shelter.district, "lac": shelter.lac, "address": shelter.address,
            "latitude": shelter.latitude, "longitude": shelter.longitude,
            "capacity": shelter.capacity, "occupied": shelter.occupied,
            "available": shelter.capacity - shelter.occupied, "is_active": bool(shelter.is_active),
            "source_key": shelter.source_key, "source_name": shelter.source_name,
            "source_row": shelter.source_row, "needs_review": bool(shelter.needs_review),
            "lac_assignment_method": shelter.lac_assignment_method,
            "lac_distance_km": shelter.lac_distance_km,
            **({"can_assign": can_assign} if can_assign is not None else {})}


def request_public(row, db):
    preferred = db.get(Shelter, row.preferred_shelter_id)
    assigned = db.get(Shelter, row.assigned_shelter_id) if row.assigned_shelter_id else None
    acceptance_id = f"KSL-{row.id:08d}" if assigned and row.status in {"Approved", "Assigned"} else None
    result = {"id": row.id, "citizen_id": row.citizen_id, "district": row.district, "lac": row.lac,
            "acceptance_id": acceptance_id,
            "household_name": row.household_name, "aadhaar_last4": row.aadhaar_last4,
            "phone": row.phone, "people_count": row.people_count, "special_needs": row.special_needs,
            "citizen_location": row.citizen_location, "latitude": row.latitude, "longitude": row.longitude,
            "reason": row.reason, "id_photo_available": bool(row.id_photo_path),
            "status": row.status, "preferred_shelter": shelter_public(preferred) if preferred else None,
            "assigned_shelter": shelter_public(assigned) if assigned else None,
            "created_at": row.created_at, "updated_at": row.updated_at,
            "eta_estimate_minutes": row.eta_estimate_minutes}
    return result


def require_responder(user):
    if user.role not in {"rescuer", "responder"}:
        raise HTTPException(status_code=403, detail="Only rescue personnel can access this action.")


def coverage_has(coverage, district, lac):
    return any(d.casefold() == district.casefold() and l.casefold() == lac.casefold() for d, l in coverage)


def coverage_has_district(coverage, district):
    return any(d.strip().casefold() == str(district or "").strip().casefold() for d, _ in coverage)


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
    if is_active and shelter.needs_review:
        raise HTTPException(status_code=409, detail="Review and confirm this shelter's location, LAC, and capacity before activating it.")
    shelter.is_active = int(is_active)
    db.commit()
    return shelter_public(shelter)


@admin_router.patch("/{shelter_id}/review")
def admin_review(shelter_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    if admin.must_change_password:
        raise HTTPException(status_code=403, detail="Change your temporary password before using the admin console.")
    shelter = db.get(Shelter, shelter_id)
    if not shelter:
        raise HTTPException(status_code=404, detail="Shelter not found.")
    shelter.needs_review = False
    db.commit()
    db.refresh(shelter)
    return shelter_public(shelter)


@router.get("")
def public_shelters(db: Session = Depends(get_db)):
    shelters = db.query(Shelter).filter(Shelter.is_active == 1, Shelter.needs_review.is_(False)).order_by(Shelter.district, Shelter.name).all()
    # Do not publish stale or malformed coordinates on the citizen map. Admins
    # can still see and correct these rows in the console.
    return [shelter_public(s) for s in shelters if _coordinate_in_district(s.latitude, s.longitude, s.district)]


@router.get("/reference-camps")
@limiter.limit("60/minute")
def public_reference_camps(
    request: Request,
    district: str | None = Query(default=None, max_length=100),
    search: str | None = Query(default=None, max_length=160),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Expose the static KSDMA directory without treating its camps as live shelters."""
    from app.chatbot.ref_models import RefCamp

    query = db.query(RefCamp)
    if district and district.strip():
        query = query.filter(func.lower(RefCamp.district) == _district_key(district))
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(
            RefCamp.name.ilike(pattern),
            RefCamp.lsg.ilike(pattern),
            RefCamp.village.ilike(pattern),
        ))

    total = query.count()
    camps = (query.order_by(RefCamp.district, RefCamp.name)
             .offset((page - 1) * page_size).limit(page_size).all())
    items = []
    for camp in camps:
        location_query = ", ".join(part for part in (camp.name, camp.village, camp.lsg, camp.district, "Kerala", "India") if part)
        map_query = f"{camp.lat},{camp.lng}" if camp.lat is not None and camp.lng is not None else location_query
        items.append({
            "id": camp.id,
            "name": camp.name,
            "district": camp.district,
            "local_body": camp.lsg,
            "village": camp.village,
            "latitude": camp.lat,
            "longitude": camp.lng,
            "listed_capacity": camp.capacity,
            "toilets": camp.toilets,
            "disabled_friendly": camp.disabled_friendly,
            "map_url": "https://www.google.com/maps/search/?" + urlencode({"api": "1", "query": map_query}),
            "status": "KSDMA listed; current operating status unverified",
        })
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "source": "KSDMA monsoon relief-camp inventory",
        "notice": "This static list does not confirm that a camp is open or has space today. Confirm with the district control room at 1077 before travelling.",
    }


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
                         citizen_location=data.citizen_location.strip() if data.citizen_location else None,
                         latitude=data.latitude, longitude=data.longitude,
                         reason=data.reason.strip() if data.reason else None,
                         eta_estimate_minutes=min(360, 60 + pending * 15), client_request_id=data.client_request_id)
    db.add(row)
    db.flush()
    record_status(db, shelter_request_id=row.id, status="Pending", actor_role="system", note="Shelter request received and routed to the local rescue team.")
    db.commit()
    db.refresh(row)
    return request_public(row, db)


def require_shelter_request_access(row, db, user):
    if row.citizen_id == user.id:
        return
    if user.role in {"responder", "rescuer"} and coverage_has_district(responder_coverage_query(db, user), row.district):
        return
    raise HTTPException(status_code=403, detail="You cannot access this shelter request.")


@router.post("/requests/{request_id}/id-photo")
async def upload_shelter_request_id_photo(request_id: int, image: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(ShelterRequest, request_id)
    if not row:
        raise HTTPException(status_code=404, detail="Shelter request not found.")
    if row.citizen_id != user.id:
        raise HTTPException(status_code=403, detail="Only the requesting citizen can upload an identification photo.")
    extension = ALLOWED_ID_PHOTO_TYPES.get(image.content_type or "")
    if extension is None:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, or WebP image.")
    content = await image.read(MAX_ID_PHOTO_BYTES + 1)
    signatures = {".jpg": content.startswith(b"\xff\xd8\xff"), ".png": content.startswith(b"\x89PNG\r\n\x1a\n"), ".webp": len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP"}
    if not content or len(content) > MAX_ID_PHOTO_BYTES or not signatures[extension]:
        raise HTTPException(status_code=415, detail="The photo must be a valid image no larger than 5 MB.")
    filename = f"{uuid.uuid4().hex}{extension}"
    destination = SHELTER_REQUEST_UPLOAD_DIR / filename
    destination.write_bytes(content)
    old_path = SHELTER_REQUEST_UPLOAD_DIR / row.id_photo_path if row.id_photo_path else None
    row.id_photo_path = filename
    try:
        db.commit()
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Could not save the identification photo.")
    if old_path:
        old_path.unlink(missing_ok=True)
    return {"id_photo_available": True}


@router.get("/requests/{request_id}/id-photo")
def get_shelter_request_id_photo(request_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(ShelterRequest, request_id)
    if not row:
        raise HTTPException(status_code=404, detail="Shelter request not found.")
    require_shelter_request_access(row, db, user)
    if not row.id_photo_path:
        raise HTTPException(status_code=404, detail="No identification photo was provided.")
    path = SHELTER_REQUEST_UPLOAD_DIR / Path(row.id_photo_path).name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Identification photo file not found.")
    return FileResponse(path)


@router.get("/requests/my")
def my_requests(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [request_public(r, db) for r in db.query(ShelterRequest).filter(ShelterRequest.citizen_id == user.id).order_by(ShelterRequest.created_at.desc()).all()]


@router.get("/requests/my/{request_id}/history")
def my_shelter_request_history(request_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(ShelterRequest, request_id)
    if not row:
        raise HTTPException(status_code=404, detail="Shelter request not found.")
    if row.citizen_id != user.id:
        if user.role not in {"responder", "rescuer"} or not coverage_has_district(responder_coverage_query(db, user), row.district):
            raise HTTPException(status_code=403, detail="You cannot access this request history.")
    events = db.query(RequestStatusEvent).filter(RequestStatusEvent.shelter_request_id == row.id).order_by(RequestStatusEvent.created_at.asc(), RequestStatusEvent.id.asc()).all()
    return [event_public(event) for event in events]


@router.get("/responder/requests")
def responder_requests(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_responder(user)
    coverage = responder_coverage_query(db, user)
    if not coverage:
        return []
    districts = sorted({district.strip() for district, _ in coverage if district and district.strip()})
    if not districts:
        return []
    clauses = [ShelterRequest.district.ilike(district) for district in districts]
    rows = db.query(ShelterRequest).filter(or_(*clauses)).order_by(ShelterRequest.created_at.desc()).all()
    return [request_public(r, db) for r in rows]


@router.get("/responder/all")
def responder_shelters(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_responder(user)
    coverage = responder_coverage_query(db, user)
    rows = db.query(Shelter).order_by(Shelter.district, Shelter.name).all()
    return [shelter_public(s, coverage_has_district(coverage, s.district)) for s in rows]


@router.post("/requests/{request_id}/decision")
def decide_request(request_id: int, data: RequestDecision, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_responder(user)
    row = db.query(ShelterRequest).filter(ShelterRequest.id == request_id).with_for_update().first()
    if not row:
        raise HTTPException(status_code=404, detail="Shelter request not found.")
    coverage = responder_coverage_query(db, user)
    if not coverage_has_district(coverage, row.district):
        raise HTTPException(status_code=403, detail="This request is outside your assigned district coverage.")
    if row.status != "Pending":
        raise HTTPException(status_code=409, detail="This request has already been reviewed.")
    assigned_shelter = None
    if data.status == "Approved":
        shelter_id = data.shelter_id or row.preferred_shelter_id
        assigned_shelter = db.query(Shelter).filter(Shelter.id == shelter_id, Shelter.is_active == 1).with_for_update().first()
        if not assigned_shelter:
            raise HTTPException(status_code=409, detail="Choose an active shelter for this household.")
        if not coverage_has_district(coverage, assigned_shelter.district) or assigned_shelter.district.strip().casefold() != row.district.strip().casefold():
            raise HTTPException(status_code=403, detail="Choose a shelter in the request's district.")
        if assigned_shelter.capacity - assigned_shelter.occupied < row.people_count:
            raise HTTPException(status_code=409, detail="This shelter no longer has enough space. Choose another in-coverage shelter.")
        assigned_shelter.occupied += row.people_count
        row.assigned_shelter_id = assigned_shelter.id
        row.status = "Assigned"
    else:
        row.status = "Rejected"
    row.responder_id = user.id
    record_status(db, shelter_request_id=row.id, status=row.status, actor_role=user.role,
                  note=f"Request accepted and household assigned to {assigned_shelter.name}." if assigned_shelter else "Shelter request declined by the local rescue team.")
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
    if not coverage_has_district(coverage, row.district):
        raise HTTPException(status_code=403, detail="This request is outside your assigned district coverage.")
    if shelter.district.strip().casefold() != row.district.strip().casefold():
        raise HTTPException(status_code=403, detail="Choose a shelter in the request's district.")
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
    if not coverage_has_district(coverage, shelter.district):
        raise HTTPException(status_code=403, detail="You can only update shelters in your assigned districts.")
    if change > 0 and not shelter.is_active:
        raise HTTPException(status_code=409, detail="This shelter is inactive and cannot accept more people.")
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
