from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.admin_audit_log import AdminAuditLog
from app.models.admin_user import AdminUser
from app.models.alert import Alert
from app.models.help_request import HelpRequest
from app.models.organization import Organization
from app.models.user import User
from app.models.responder_coverage import ResponderCoverage
from app.models.resource_item import ResourceItem
from app.models.resource_transaction import ResourceTransaction
from app.routers.admin_auth import get_current_admin, password_hash, admin_public
from app.routers.help_requests import get_lac_mapping, responder_coverage_query, validate_district_and_lac

def require_ready_admin(admin: AdminUser = Depends(get_current_admin)):
    if admin.must_change_password:
        raise HTTPException(status_code=403, detail="Change your temporary password before using the admin console.")
    return admin


router = APIRouter(prefix="/api/admin", tags=["Admin"], dependencies=[Depends(require_ready_admin)])


class UserUpdate(BaseModel):
    role: str | None = Field(default=None, pattern="^(citizen|rescuer|responder)$")
    status: str | None = Field(default=None, pattern="^(active|inactive|suspended|pending|rejected)$")

    @model_validator(mode="after")
    def require_change(self):
        if self.role is None and self.status is None:
            raise ValueError("Provide a role or status to update.")
        return self


class NewAdmin(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    temporary_password: str = Field(min_length=12, max_length=128)


class RequestStatusUpdate(BaseModel):
    status: str = Field(pattern="^(Submitted|Under Review|Assigned|In Progress|Resolved|Rejected)$")
    reason: str | None = Field(default=None, min_length=3, max_length=1000)

    @model_validator(mode="after")
    def require_terminal_reason(self):
        if self.status in {"Resolved", "Rejected"} and (not self.reason or not self.reason.strip()):
            raise ValueError("A reason is required to resolve or reject a request.")
        return self


class AssignmentUpdate(BaseModel):
    responder_id: int | None


class CoverageArea(BaseModel):
    district: str = Field(min_length=2, max_length=100)
    lac: str = Field(min_length=2, max_length=150)


class CoverageUpdate(BaseModel):
    coverage: list[CoverageArea] = Field(min_length=1, max_length=2)


class OrganizationCreate(BaseModel):
    organization_code: str = Field(min_length=3, max_length=50, pattern="^[A-Za-z0-9][A-Za-z0-9_-]*$")
    organization_name: str = Field(min_length=2, max_length=150)
    organization_type: str = Field(min_length=2, max_length=50)
    district: str | None = Field(default=None, max_length=100)


class AlertCreate(BaseModel):
    title: str = Field(min_length=4, max_length=180)
    message: str = Field(min_length=10, max_length=10000)
    severity: str = Field(pattern="^(info|advisory|warning|emergency)$")
    district: str | None = Field(default=None, max_length=100)
    expires_at: datetime | None = None


class AlertEdit(BaseModel):
    title: str | None = Field(default=None, min_length=4, max_length=180)
    message: str | None = Field(default=None, min_length=10, max_length=10000)
    severity: str | None = Field(default=None, pattern="^(info|advisory|warning|emergency)$")
    district: str | None = Field(default=None, max_length=100)
    expires_at: datetime | None = None


class ResourceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    district: str = Field(min_length=2, max_length=100)
    category: str = Field(default="General", min_length=2, max_length=60)
    unit: str = Field(min_length=1, max_length=40)
    quantity_available: int = Field(default=0, ge=0)
    low_stock_threshold: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def strip_text(self):
        for field in ("name", "district", "category", "unit"):
            value = getattr(self, field).strip()
            if not value:
                raise ValueError(f"{field.replace('_', ' ').title()} cannot be blank.")
            setattr(self, field, value)
        return self


class ResourceStockAdjustment(BaseModel):
    direction: str = Field(pattern="^(add|remove)$")
    quantity: int = Field(gt=0, le=1000000)
    reason: str = Field(min_length=3, max_length=500)


class ResourceDistrictUpdate(BaseModel):
    district: str = Field(min_length=2, max_length=100)


def resource_public(item: ResourceItem):
    return {
        "id": item.id,
        "name": item.name,
        "district": item.district,
        "category": item.category,
        "unit": item.unit,
        "quantity_available": item.quantity_available,
        "low_stock_threshold": item.low_stock_threshold,
        "is_active": item.is_active,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def log_action(db: Session, admin: AdminUser, action: str, target_type: str, target_id: int | None, details: str | None = None):
    db.add(AdminAuditLog(
        admin_user_id=admin.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    ))


def request_public(request: HelpRequest):
    return {
        "id": request.id,
        "user_id": request.user_id,
        "district": request.district,
        "lac": request.lac,
        "location_description": request.location_description,
        "latitude": request.latitude,
        "longitude": request.longitude,
        "emergency_type": request.emergency_type,
        "people_affected": request.people_affected,
        "special_assistance": request.special_assistance,
        "urgency": request.urgency,
        "situation_description": request.situation_description,
        "image_path": request.image_path,
        "status": request.status,
        "assigned_responder_id": request.assigned_responder_id,
        "responder_notes": request.responder_notes,
        "created_at": request.created_at,
        "updated_at": request.updated_at,
    }


def alert_public(alert: Alert):
    return {
        "id": alert.id,
        "title": alert.title,
        "message": alert.message,
        "severity": alert.severity,
        "district": alert.district,
        "status": alert.status,
        "expires_at": alert.expires_at,
        "created_by": alert.created_by,
        "reviewed_by": alert.reviewed_by,
        "published_at": alert.published_at,
        "created_at": alert.created_at,
        "updated_at": alert.updated_at,
    }


def alert_has_expired(alert: Alert) -> bool:
    if alert.expires_at is None:
        return False
    expires_at = alert.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    role_counts = dict(db.query(User.role, func.count(User.id)).group_by(User.role).all())
    user_status_counts = dict(db.query(User.status, func.count(User.id)).group_by(User.status).all())
    request_counts = dict(db.query(HelpRequest.status, func.count(HelpRequest.id)).group_by(HelpRequest.status).all())
    active_statuses = {"Submitted", "Under Review", "Assigned", "In Progress"}
    logs = (db.query(AdminAuditLog, AdminUser.full_name)
        .outerjoin(AdminUser, AdminAuditLog.admin_user_id == AdminUser.id)
        .order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc()).limit(10).all())
    return {
        "users": {"total": sum(role_counts.values()), "by_role": role_counts, "by_status": user_status_counts},
        "administrators": {
            "total": db.query(func.count(AdminUser.id)).scalar(),
            "active": db.query(func.count(AdminUser.id)).filter(AdminUser.is_active.is_(True)).scalar(),
        },
        "help_requests": {
            "total": sum(request_counts.values()), "by_status": request_counts,
            "active_or_unresolved": sum(count for status, count in request_counts.items() if status in active_statuses),
            "pending": request_counts.get("Submitted", 0),
        },
        "alerts": {
            "draft": db.query(func.count(Alert.id)).filter(Alert.status == "draft").scalar(),
            "in_review": db.query(func.count(Alert.id)).filter(Alert.status == "review").scalar(),
            "published": db.query(func.count(Alert.id)).filter(Alert.status == "published").scalar(),
        },
        "resources": {
            "active": db.query(func.count(ResourceItem.id)).filter(ResourceItem.is_active.is_(True)).scalar(),
            "low_stock": db.query(func.count(ResourceItem.id)).filter(
                ResourceItem.is_active.is_(True),
                ResourceItem.quantity_available <= ResourceItem.low_stock_threshold,
            ).scalar(),
        },
        "recent_activity": [{
            "id": row.id, "admin_user_id": row.admin_user_id, "action": row.action,
            "target_type": row.target_type, "target_id": row.target_id,
            "details": row.details, "created_at": row.created_at,
            "admin_name": admin_name,
        } for row, admin_name in logs],
        "not_yet_modeled": ["shelters", "incident_assignments"],
    }


@router.get("/organizations")
def list_organizations(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    organizations = db.query(Organization).order_by(Organization.organization_name).all()
    return [{
        "id": organization.id,
        "organization_code": organization.organization_code,
        "organization_name": organization.organization_name,
        "organization_type": organization.organization_type,
        "district": organization.district,
        "is_active": organization.is_active,
        "responder_count": db.query(func.count(User.id)).filter(User.organization_id == organization.id).scalar(),
    } for organization in organizations]


@router.post("/organizations", status_code=201)
def create_organization(data: OrganizationCreate, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    code = data.organization_code.strip().upper()
    if db.query(Organization).filter(func.upper(Organization.organization_code) == code).first():
        raise HTTPException(status_code=409, detail="An organization with that code already exists.")
    organization = Organization(
        organization_code=code,
        organization_name=data.organization_name.strip(),
        organization_type=data.organization_type.strip(),
        district=data.district.strip() if data.district and data.district.strip() else None,
        is_active=True,
    )
    db.add(organization)
    db.flush()
    log_action(db, admin, "organization_created", "organization", organization.id,
        f"{organization.organization_name} ({code})")
    db.commit()
    db.refresh(organization)
    return {
        "id": organization.id,
        "organization_code": organization.organization_code,
        "organization_name": organization.organization_name,
        "organization_type": organization.organization_type,
        "district": organization.district,
        "is_active": organization.is_active,
    }


@router.patch("/organizations/{organization_id}/active")
def set_organization_active(organization_id: int, is_active: bool, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    organization = db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found.")
    organization.is_active = is_active
    log_action(db, admin, "organization_access_changed", "organization", organization.id,
        f"is_active -> {is_active}")
    db.commit()
    db.refresh(organization)
    return {"id": organization.id, "organization_code": organization.organization_code,
        "organization_name": organization.organization_name, "is_active": organization.is_active}


@router.get("/resources")
def list_resources(include_inactive: bool = False, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    query = db.query(ResourceItem)
    if not include_inactive:
        query = query.filter(ResourceItem.is_active.is_(True))
    return [resource_public(item) for item in query.order_by(ResourceItem.category, ResourceItem.name).all()]


@router.get("/resource-transactions")
def list_resource_transactions(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    rows = (db.query(ResourceTransaction, User.full_name, User.email)
        .join(User, ResourceTransaction.responder_id == User.id)
        .order_by(ResourceTransaction.created_at.desc(), ResourceTransaction.id.desc())
        .limit(limit).all())
    return [{
        "id": transaction.id,
        "resource_name": transaction.resource_name,
        "district": transaction.district,
        "unit": transaction.unit,
        "quantity": transaction.quantity,
        "reason": transaction.reason,
        "help_request_id": transaction.help_request_id,
        "responder_name": responder_name,
        "responder_email": responder_email,
        "created_at": transaction.created_at,
    } for transaction, responder_name, responder_email in rows]


@router.post("/resources", status_code=201)
def create_resource(data: ResourceCreate, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    name = data.name.strip()
    districts = get_lac_mapping()
    actual_district = next((value for value in districts if value.casefold() == data.district.casefold()), None)
    if not actual_district:
        raise HTTPException(status_code=422, detail="Choose a valid district.")
    existing = db.query(ResourceItem).filter(
        func.lower(ResourceItem.name) == name.lower(),
        func.lower(ResourceItem.district) == actual_district.lower(),
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="An item with that name already exists in this district. Adjust its stock instead.")
    item = ResourceItem(name=name, district=actual_district, category=data.category.strip(), unit=data.unit.strip(),
        quantity_available=data.quantity_available, low_stock_threshold=data.low_stock_threshold,
        created_by=admin.id)
    db.add(item)
    db.flush()
    log_action(db, admin, "resource_created", "resource_item", item.id,
        f"Created {name}: {item.quantity_available} {item.unit} in stock")
    db.commit()
    db.refresh(item)
    return resource_public(item)


@router.patch("/resources/{resource_id}/district")
def set_resource_district(resource_id: int, data: ResourceDistrictUpdate, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    item = db.get(ResourceItem, resource_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found.")
    districts = get_lac_mapping()
    actual_district = next((value for value in districts if value.casefold() == data.district.strip().casefold()), None)
    if not actual_district:
        raise HTTPException(status_code=422, detail="Choose a valid district.")
    duplicate = db.query(ResourceItem).filter(
        ResourceItem.id != item.id,
        func.lower(ResourceItem.name) == item.name.lower(),
        func.lower(ResourceItem.district) == actual_district.lower(),
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="An item with that name already exists in this district.")
    previous = item.district or "unassigned"
    item.district = actual_district
    log_action(db, admin, "resource_district_changed", "resource_item", item.id,
        f"{previous} -> {actual_district}")
    db.commit()
    db.refresh(item)
    return resource_public(item)


@router.patch("/resources/{resource_id}/stock")
def adjust_resource_stock(resource_id: int, data: ResourceStockAdjustment, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    item = db.query(ResourceItem).filter(ResourceItem.id == resource_id).with_for_update().first()
    if item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found.")
    if not item.is_active:
        raise HTTPException(status_code=409, detail="Reactivate this inventory item before changing its stock.")
    delta = data.quantity if data.direction == "add" else -data.quantity
    updated_quantity = item.quantity_available + delta
    if updated_quantity < 0:
        raise HTTPException(status_code=409, detail=f"Only {item.quantity_available} {item.unit} are currently available.")
    item.quantity_available = updated_quantity
    log_action(db, admin, "resource_stock_adjusted", "resource_item", item.id,
        f"{item.district or 'unassigned district'}: {data.direction.title()} {data.quantity} {item.unit}; {data.reason.strip()}; balance {updated_quantity}")
    db.commit()
    db.refresh(item)
    return resource_public(item)


@router.patch("/resources/{resource_id}/active")
def set_resource_active(resource_id: int, is_active: bool, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    item = db.get(ResourceItem, resource_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found.")
    item.is_active = is_active
    log_action(db, admin, "resource_access_changed", "resource_item", item.id, f"is_active -> {is_active}")
    db.commit()
    db.refresh(item)
    return resource_public(item)


@router.get("/users")
def list_users(
    search: str | None = Query(default=None, max_length=255),
    role: str | None = Query(default=None, pattern="^(citizen|rescuer|responder)$"),
    status: str | None = Query(default=None, pattern="^(active|pending|rejected|inactive|suspended)$"),
    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin),
):
    query = db.query(User)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(User.full_name.ilike(term), User.email.ilike(term)))
    if role:
        query = query.filter(User.role == ("rescuer" if role == "responder" else role))
    if status:
        query = query.filter(User.status == status)
    total = query.count()
    users = query.order_by(User.created_at.desc(), User.id.desc()).offset(offset).limit(limit).all()
    return {"total": total, "limit": limit, "offset": offset, "users": [{
        "id": user.id, "full_name": user.full_name, "email": user.email, "role": user.role,
        "status": user.status, "district": user.district, "nearest_lac": user.nearest_lac,
        "organization_id": user.organization_id, "rescuer_id": user.rescuer_id,
        "coverage": [{"district": district, "lac": lac} for district, lac in responder_coverage_query(db, user)]
            if user.role in {"rescuer", "responder"} else [],
        "created_at": user.created_at,
    } for user in users]}


@router.get("/users/{user_id}/coverage")
def get_responder_coverage(user_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    user = db.get(User, user_id)
    if not user or user.role not in {"rescuer", "responder"}:
        raise HTTPException(status_code=404, detail="Responder account not found.")
    return {"user_id": user.id, "coverage": [{"district": district, "lac": lac} for district, lac in responder_coverage_query(db, user)]}


@router.put("/users/{user_id}/coverage")
def set_responder_coverage(user_id: int, data: CoverageUpdate, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    user = db.get(User, user_id)
    if not user or user.role not in {"rescuer", "responder"}:
        raise HTTPException(status_code=404, detail="Responder account not found.")
    canonical = []
    seen = set()
    for area in data.coverage:
        district, lac = validate_district_and_lac(area.district.strip(), area.lac.strip())
        key = (district.casefold(), lac.casefold())
        if key in seen:
            raise HTTPException(status_code=422, detail="Coverage LACs must be unique.")
        seen.add(key)
        canonical.append((district, lac))

    active_assignments = db.query(HelpRequest).filter(
        HelpRequest.assigned_responder_id == user.id,
        HelpRequest.status.notin_(["Resolved", "Rejected"]),
    ).all()
    if any(not any(
        district.casefold() == request.district.casefold()
        and lac.casefold() == request.lac.casefold()
        for district, lac in canonical
    ) for request in active_assignments):
        raise HTTPException(status_code=409, detail="Reassign or close this responder's active requests before removing their LAC coverage.")

    db.query(ResponderCoverage).filter(ResponderCoverage.responder_id == user.id).delete()
    for district, lac in canonical:
        db.add(ResponderCoverage(responder_id=user.id, district=district, lac=lac))
    log_action(db, admin, "responder_coverage_updated", "user", user.id,
        "; ".join(f"{district} / {lac}" for district, lac in canonical))
    db.commit()
    return {"user_id": user.id, "coverage": [{"district": district, "lac": lac} for district, lac in canonical]}


@router.patch("/users/{user_id}")
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    changes = []
    if data.role is not None:
        new_role = "rescuer" if data.role == "responder" else data.role
        if user.role != new_role:
            changes.append(f"role {user.role} -> {new_role}")
            user.role = new_role
            if new_role == "rescuer" and user.status == "active":
                user.status = "pending"
                changes.append("status active -> pending for responder review")
    if data.status is not None:
        if data.status == "active" and user.role == "rescuer" and user.status == "pending":
            changes.append("responder approved")
        if user.status != data.status:
            changes.append(f"status {user.status} -> {data.status}")
            user.status = data.status
    if changes:
        log_action(db, admin, "user_updated", "user", user.id, "; ".join(changes))
        db.commit()
        db.refresh(user)
    return {"id": user.id, "full_name": user.full_name, "email": user.email, "role": user.role, "status": user.status, "district": user.district}


@router.get("/admins")
def list_admins(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    admins = db.query(AdminUser).order_by(AdminUser.created_at.desc()).all()
    return [admin_public(item) for item in admins]


@router.post("/admins", status_code=201)
def create_admin(data: NewAdmin, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    email = str(data.email).strip().lower()
    if db.query(AdminUser).filter(AdminUser.email == email).first():
        raise HTTPException(status_code=409, detail="An admin account with that email already exists.")
    new_admin = AdminUser(full_name=data.full_name.strip(), email=email,
        hashed_password=password_hash.hash(data.temporary_password), is_active=True, must_change_password=True)
    db.add(new_admin)
    try:
        db.flush()
        log_action(db, admin, "admin_created", "admin_user", new_admin.id, f"Created admin account for {email}")
        db.commit()
        db.refresh(new_admin)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An admin account with that email already exists.")
    return admin_public(new_admin)


@router.patch("/admins/{admin_id}/active")
def set_admin_active(admin_id: int, is_active: bool, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    target = db.get(AdminUser, admin_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Admin account not found.")
    if target.id == admin.id and not is_active:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own admin account.")
    if target.is_active and not is_active:
        count = db.query(func.count(AdminUser.id)).filter(AdminUser.is_active.is_(True)).scalar()
        if count <= 1:
            raise HTTPException(status_code=409, detail="Cannot deactivate the last active admin.")
    target.is_active = is_active
    log_action(db, admin, "admin_access_changed", "admin_user", target.id, f"is_active -> {is_active}")
    db.commit()
    return admin_public(target)


@router.get("/requests")
def list_requests(status: str | None = None, district: str | None = None, limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    query = db.query(HelpRequest)
    if status:
        query = query.filter(HelpRequest.status == status)
    if district:
        query = query.filter(HelpRequest.district.ilike(district))
    total = query.count()
    rows = query.order_by(HelpRequest.created_at.desc()).offset(offset).limit(limit).all()
    return {"total": total, "limit": limit, "offset": offset, "items": [request_public(item) for item in rows]}


@router.patch("/requests/{request_id}/status")
def update_request_status(request_id: int, data: RequestStatusUpdate, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    request = db.query(HelpRequest).filter(HelpRequest.id == request_id).with_for_update().first()
    if request is None:
        raise HTTPException(status_code=404, detail="Help request not found.")
    previous = request.status
    request.status = data.status
    detail = f"{previous} -> {data.status}"
    if data.reason:
        detail += f"; reason: {data.reason.strip()}"
    log_action(db, admin, "help_request_status_changed", "help_request", request.id, detail)
    db.commit()
    db.refresh(request)
    return request_public(request)


@router.patch("/requests/{request_id}/assignment")
def assign_request(request_id: int, data: AssignmentUpdate, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    request = db.query(HelpRequest).filter(HelpRequest.id == request_id).with_for_update().first()
    if request is None:
        raise HTTPException(status_code=404, detail="Help request not found.")
    if data.responder_id is not None:
        responder = db.get(User, data.responder_id)
        if not responder or responder.role not in {"rescuer", "responder"} or responder.status != "active":
            raise HTTPException(status_code=422, detail="Choose an active responder account.")
        responder_coverage = responder_coverage_query(db, responder)
        if not any(district.casefold() == request.district.casefold() and lac.casefold() == request.lac.casefold()
                   for district, lac in responder_coverage):
            raise HTTPException(status_code=422, detail="The responder is not assigned to this request's LAC.")
        if request.status in {"Resolved", "Rejected"}:
            raise HTTPException(status_code=409, detail="A closed request cannot be assigned.")
    previous = request.assigned_responder_id
    request.assigned_responder_id = data.responder_id
    if data.responder_id is not None:
        request.status = "Assigned"
    detail = f"responder {previous} -> {data.responder_id}"
    log_action(db, admin, "help_request_assigned", "help_request", request.id, detail)
    db.commit()
    db.refresh(request)
    return request_public(request)


@router.get("/requests/{request_id}/attachment")
def get_request_attachment(request_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    from app.routers.help_requests import UPLOAD_DIR

    request = db.get(HelpRequest, request_id)
    if not request or not request.image_path:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    path = UPLOAD_DIR / request.image_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Attachment file not found.")
    return FileResponse(path)


@router.get("/alerts")
def list_admin_alerts(status: str | None = None, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    query = db.query(Alert)
    if status:
        query = query.filter(Alert.status == status)
    return [alert_public(item) for item in query.order_by(Alert.created_at.desc()).all()]


@router.post("/alerts", status_code=201)
def create_alert(data: AlertCreate, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    alert = Alert(**data.model_dump(), created_by=admin.id, status="draft")
    db.add(alert)
    db.flush()
    log_action(db, admin, "alert_created", "alert", alert.id, "Alert created as draft")
    db.commit()
    db.refresh(alert)
    return alert_public(alert)


@router.patch("/alerts/{alert_id}")
def edit_alert(alert_id: int, data: AlertEdit, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")
    if alert.status not in {"draft", "review"}:
        raise HTTPException(status_code=409, detail="Only draft or in-review alerts can be edited.")
    changes = data.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(alert, key, value)
    log_action(db, admin, "alert_edited", "alert", alert.id, ", ".join(changes.keys()))
    db.commit()
    db.refresh(alert)
    return alert_public(alert)


@router.post("/alerts/{alert_id}/submit-review")
def submit_alert_for_review(alert_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")
    if alert.status != "draft":
        raise HTTPException(status_code=409, detail="Only a draft can be submitted for review.")
    alert.status = "review"
    log_action(db, admin, "alert_submitted_for_review", "alert", alert.id)
    db.commit()
    db.refresh(alert)
    return alert_public(alert)


@router.post("/alerts/{alert_id}/publish")
def publish_alert(alert_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")
    if alert.status != "review":
        raise HTTPException(status_code=409, detail="Only an alert in review can be published.")
    if alert_has_expired(alert):
        raise HTTPException(status_code=422, detail="An expired alert cannot be published.")
    alert.status = "published"
    alert.reviewed_by = admin.id
    alert.published_at = datetime.now(timezone.utc)
    log_action(db, admin, "alert_published", "alert", alert.id)
    db.commit()
    db.refresh(alert)
    return alert_public(alert)


@router.post("/alerts/{alert_id}/withdraw")
def withdraw_alert(alert_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")
    if alert.status != "published":
        raise HTTPException(status_code=409, detail="Only a published alert can be withdrawn.")
    alert.status = "withdrawn"
    log_action(db, admin, "alert_withdrawn", "alert", alert.id)
    db.commit()
    db.refresh(alert)
    return alert_public(alert)


@router.post("/alerts/{alert_id}/expire")
def expire_alert(alert_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")
    if alert.status != "published":
        raise HTTPException(status_code=409, detail="Only a published alert can expire.")
    if not alert_has_expired(alert):
        raise HTTPException(status_code=422, detail="The alert expiration time has not been reached.")
    alert.status = "expired"
    log_action(db, admin, "alert_expired", "alert", alert.id)
    db.commit()
    db.refresh(alert)
    return alert_public(alert)


@router.get("/audit-logs")
def audit_logs(limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    query = db.query(AdminAuditLog)
    total = query.count()
    rows = (query.with_entities(AdminAuditLog, AdminUser.full_name)
        .outerjoin(AdminUser, AdminAuditLog.admin_user_id == AdminUser.id)
        .order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc()).offset(offset).limit(limit).all())
    return {"total": total, "limit": limit, "offset": offset, "items": [{
        "id": row.id, "admin_user_id": row.admin_user_id, "action": row.action,
        "target_type": row.target_type, "target_id": row.target_id,
        "details": row.details, "created_at": row.created_at, "admin_name": admin_name,
    } for row, admin_name in rows]}
