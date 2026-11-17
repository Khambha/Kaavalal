from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import case, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.admin_audit_log import AdminAuditLog
from app.models.admin_user import AdminUser
from app.models.alert import Alert
from app.models.help_request import HelpRequest
from app.models.help_request_message import HelpRequestMessage
from app.models.organization import Organization
from app.models.user import User
from app.models.responder_coverage import ResponderCoverage
from app.models.resource_item import ResourceItem
from app.models.resource_asset import ResourceAsset
from app.models.resource_asset_assignment import ResourceAssetAssignment
from app.models.resource_request import ResourceRequest
from app.models.resource_transaction import ResourceTransaction
from app.services.request_tracking import record_status
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
    is_returnable: bool = False
    inventory_mode: str = Field(default="Bulk", pattern="^(Bulk|Tracked Asset)$")

    @model_validator(mode="after")
    def strip_text(self):
        for field in ("name", "district", "category", "unit"):
            value = getattr(self, field).strip()
            if not value:
                raise ValueError(f"{field.replace('_', ' ').title()} cannot be blank.")
            setattr(self, field, value)
        if self.inventory_mode == "Tracked Asset" and not self.is_returnable:
            raise ValueError("Tracked assets must be classified as reusable so they can be returned.")
        return self


class ResourceStockAdjustment(BaseModel):
    direction: str = Field(pattern="^(add|remove)$")
    quantity: int = Field(gt=0, le=1000000)
    reason: str = Field(min_length=3, max_length=500)


class ResourceRequestDecision(BaseModel):
    status: str = Field(pattern="^(Granted|Rejected)$")
    quantity_granted: int | None = Field(default=None, ge=1, le=1000000)
    asset_ids: list[int] = Field(default_factory=list, max_length=1000)
    rejection_reason: str | None = Field(default=None, min_length=3, max_length=1000)


class ResourceAssetsCreate(BaseModel):
    identifiers: list[str] = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=3, max_length=500)


class ResourceAssetRetirement(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class ResourceMaintenanceUpdate(BaseModel):
    action: str = Field(pattern="^(repair|retire)$")
    quantity: int = Field(gt=0, le=1000000)
    reason: str = Field(min_length=3, max_length=500)


class ResourceThresholdUpdate(BaseModel):
    threshold: int = Field(ge=0, le=1000000)
    reason: str = Field(min_length=3, max_length=500)


class ResourceDistrictUpdate(BaseModel):
    district: str = Field(min_length=2, max_length=100)


STANDARD_DISTRICT_RESOURCE_CATALOG = (
    ("Drinking water", "Water", "litres", False, "Bulk"),
    ("Food packages", "Food", "packages", False, "Bulk"),
    ("Medicine kiosks", "Medical", "kiosks", True, "Bulk"),
    ("Ambulances", "Medical transport", "vehicles", True, "Tracked Asset"),
    ("Rescue boats", "Water rescue", "boats", True, "Tracked Asset"),
    ("Insect repellant kits", "Health", "kits", False, "Bulk"),
    ("Personal first-aid kits", "Medical", "kits", False, "Bulk"),
    ("Headlamps", "Equipment", "units", True, "Bulk"),
    ("Earthmovers (JCBs)", "Heavy equipment", "vehicles", True, "Tracked Asset"),
    ("Excavators", "Heavy equipment", "vehicles", True, "Tracked Asset"),
    ("KSRTC buses", "Transport", "vehicles", True, "Tracked Asset"),
    ("School buses", "Transport", "vehicles", True, "Tracked Asset"),
    ("Power backup units", "Power", "units", True, "Bulk"),
    ("Communication backup units", "Communications", "units", True, "Bulk"),
    ("Sanitation supplies", "Sanitation", "kits", False, "Bulk"),
    ("Camp supplies", "Camp", "kits", False, "Bulk"),
)


def resource_public(item: ResourceItem):
    return {
        "id": item.id,
        "name": item.name,
        "district": item.district,
        "category": item.category,
        "unit": item.unit,
        "quantity_available": item.quantity_available,
        "quantity_total": item.quantity_total,
        "quantity_issued": max(0, item.quantity_total - item.quantity_available - item.quantity_quarantined),
        "quantity_quarantined": item.quantity_quarantined,
        "inventory_mode": item.inventory_mode,
        "low_stock_threshold": item.low_stock_threshold,
        "is_returnable": item.is_returnable,
        "is_active": item.is_active,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def resource_request_public(item: ResourceRequest, responder_name=None, responder_email=None):
    granted = item.quantity_granted or 0
    return {
        "id": item.id,
        "resource_id": item.resource_id,
        "responder_id": item.responder_id,
        "responder_name": responder_name,
        "responder_email": responder_email,
        "help_request_id": item.help_request_id,
        "district": item.district,
        "resource_name": item.resource_name,
        "unit": item.unit,
        "inventory_mode": item.inventory_mode,
        "quantity_requested": item.quantity_requested,
        "quantity_granted": granted,
        "quantity_returned": item.quantity_returned,
        "quantity_quarantined": item.quantity_quarantined,
        "quantity_in_use": max(0, granted - item.quantity_returned) if item.is_returnable else 0,
        "is_returnable": item.is_returnable,
        "priority": item.priority,
        "rejection_reason": item.rejection_reason,
        "reason": item.reason,
        "status": item.status,
        "created_at": item.created_at,
        "reviewed_at": item.reviewed_at,
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
        "shelter_id": request.shelter_id,
        "eta_estimate_minutes": request.eta_estimate_minutes,
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
        "users": {
            "total": sum(role_counts.values()), "by_role": role_counts, "by_status": user_status_counts,
            "available_responders": db.query(func.count(User.id)).filter(
                User.role.in_(["rescuer", "responder"]),
                User.status == "active",
                User.is_available.is_(True),
            ).scalar(),
        },
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
                ResourceItem.quantity_available > 0,
                ResourceItem.quantity_available <= ResourceItem.low_stock_threshold,
            ).scalar(),
            "out_of_stock": db.query(func.count(ResourceItem.id)).filter(
                ResourceItem.is_active.is_(True),
                ResourceItem.quantity_available == 0,
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
    items = query.order_by(ResourceItem.category, ResourceItem.name).all()
    pending_counts = dict(db.query(ResourceRequest.resource_id, func.sum(ResourceRequest.quantity_requested))
        .filter(ResourceRequest.status == "Pending").group_by(ResourceRequest.resource_id).all())
    asset_counts = {(resource_id, status): count for resource_id, status, count in db.query(
        ResourceAsset.resource_id, ResourceAsset.status, func.count(ResourceAsset.id)
    ).group_by(ResourceAsset.resource_id, ResourceAsset.status).all()}
    resources = []
    for item in items:
        resources.append({**resource_public(item), "quantity_requested_pending": int(pending_counts.get(item.id, 0) or 0),
                          "assets_available": int(asset_counts.get((item.id, "Available"), 0)),
                          "assets_assigned": int(asset_counts.get((item.id, "Assigned"), 0))})
    return resources


@router.get("/resource-requests")
def list_resource_requests(status: str | None = Query(default=None, pattern="^(Pending|Granted|Partially Granted|Consumed|Rejected|Partially Returned|Returned)$"), limit: int = Query(default=100, ge=1, le=300), db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    query = db.query(ResourceRequest, User.full_name, User.email).join(User, ResourceRequest.responder_id == User.id)
    if status:
        query = query.filter(ResourceRequest.status == status)
    priority_order = case((ResourceRequest.priority == "Critical", 0), (ResourceRequest.priority == "Urgent", 1), else_=2)
    rows = query.order_by(case((ResourceRequest.status == "Pending", 0), else_=1),
                          priority_order, ResourceRequest.created_at.desc(), ResourceRequest.id.desc()).limit(limit).all()
    request_ids = [row.id for row, _, _ in rows]
    asset_rows = (db.query(ResourceAssetAssignment, ResourceAsset)
        .join(ResourceAsset, ResourceAsset.id == ResourceAssetAssignment.asset_id)
        .filter(ResourceAssetAssignment.request_id.in_(request_ids)).all()) if request_ids else []
    assets_by_request = {}
    for assignment, asset in asset_rows:
        assets_by_request.setdefault(assignment.request_id, []).append((assignment, asset))
    results = []
    for row, name, email in rows:
        result = resource_request_public(row, name, email)
        result["assets"] = [{"id": asset.id, "identifier": asset.asset_identifier, "status": asset.status,
                             "return_condition": assignment.return_condition, "return_note": assignment.return_note}
                            for assignment, asset in assets_by_request.get(row.id, [])]
        results.append(result)
    return results


@router.get("/resource-assets")
def list_resource_assets(district: str | None = Query(default=None, max_length=100), db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    query = db.query(ResourceAsset, ResourceItem).join(ResourceItem, ResourceItem.id == ResourceAsset.resource_id)
    if district:
        query = query.filter(func.lower(ResourceItem.district) == district.strip().lower())
    rows = query.order_by(ResourceItem.name, ResourceAsset.asset_identifier).all()
    result = []
    for asset, item in rows:
        request_row = db.get(ResourceRequest, asset.assigned_request_id) if asset.assigned_request_id else None
        responder = db.get(User, request_row.responder_id) if request_row else None
        result.append({"id": asset.id, "resource_id": item.id, "resource_name": item.name,
            "identifier": asset.asset_identifier, "status": asset.status,
            "assigned_request_id": asset.assigned_request_id,
            "assigned_to": responder.full_name if responder else None,
            "help_request_id": request_row.help_request_id if request_row else None,
            "maintenance_note": asset.maintenance_note})
    return result


@router.patch("/resource-requests/{request_id}/decision")
def decide_resource_request(request_id: int, data: ResourceRequestDecision, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    request_row = db.query(ResourceRequest).filter(ResourceRequest.id == request_id).with_for_update().first()
    if request_row is None:
        raise HTTPException(status_code=404, detail="Resource request not found.")
    if request_row.status != "Pending":
        raise HTTPException(status_code=409, detail="This resource request has already been reviewed.")
    if data.status == "Granted":
        item = db.query(ResourceItem).filter(ResourceItem.id == request_row.resource_id).with_for_update().first()
        if item is None or not item.is_active:
            raise HTTPException(status_code=409, detail="This inventory item is no longer active.")
        grant_quantity = data.quantity_granted if data.quantity_granted is not None else request_row.quantity_requested
        if grant_quantity > request_row.quantity_requested:
            raise HTTPException(status_code=422, detail="Granted quantity cannot exceed the requested amount.")
        if item.inventory_mode == "Tracked Asset":
            if not data.asset_ids or len(data.asset_ids) != grant_quantity:
                raise HTTPException(status_code=422, detail=f"Select exactly {grant_quantity} individually tracked assets.")
            assets = db.query(ResourceAsset).filter(ResourceAsset.id.in_(data.asset_ids), ResourceAsset.resource_id == item.id, ResourceAsset.status == "Available").with_for_update().all()
            if len(assets) != grant_quantity:
                available = db.query(func.count(ResourceAsset.id)).filter(ResourceAsset.resource_id == item.id, ResourceAsset.status == "Available").scalar() or 0
                raise HTTPException(status_code=409, detail=f"Only {available} tracked assets remain available. Refresh and adjust the approval.")
            for asset in assets:
                asset.status = "Assigned"
                asset.assigned_request_id = request_row.id
                db.add(ResourceAssetAssignment(request_id=request_row.id, asset_id=asset.id))
            item.quantity_available -= grant_quantity
        else:
            if data.asset_ids:
                raise HTTPException(status_code=422, detail="Asset IDs can only be assigned to tracked-asset requests.")
            if grant_quantity > item.quantity_available:
                raise HTTPException(status_code=409, detail=f"Only {item.quantity_available} {item.unit} remain in {item.district} stock. Adjust the grant quantity and try again.")
            item.quantity_available -= grant_quantity
        request_row.quantity_granted = grant_quantity
        request_row.status = ("Partially Granted" if grant_quantity < request_row.quantity_requested
                              else "Granted" if item.is_returnable else "Consumed")
        db.add(ResourceTransaction(
            resource_id=item.id,
            responder_id=request_row.responder_id,
            help_request_id=request_row.help_request_id,
            resource_name=item.name,
            district=item.district or request_row.district,
            unit=item.unit,
            quantity=grant_quantity,
            transaction_type="Issued" if item.is_returnable else "Consumed",
            reason=f"{request_row.status} resource request #{request_row.id}: {request_row.reason}",
        ))
    else:
        if not data.rejection_reason or not data.rejection_reason.strip():
            raise HTTPException(status_code=422, detail="A reason is required when rejecting a resource request.")
        request_row.status = "Rejected"
        request_row.rejection_reason = data.rejection_reason.strip()
    request_row.reviewer_admin_id = admin.id
    request_row.reviewed_at = datetime.now(timezone.utc)
    log_action(db, admin, "resource_request_reviewed", "resource_request", request_row.id,
               f"{request_row.status}: requested {request_row.quantity_requested}; granted {request_row.quantity_granted or 0} {request_row.unit} {request_row.resource_name} for {request_row.district}; {request_row.rejection_reason or ''}")
    db.commit()
    db.refresh(request_row)
    return resource_request_public(request_row)


@router.post("/resources/setup-standard-catalog")
def setup_standard_resource_catalog(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    """Create missing standard resource rows for every Kerala district, with unstocked balances."""
    districts = list(get_lac_mapping())
    existing_rows = db.query(ResourceItem).filter(ResourceItem.district.is_not(None)).all()
    existing = {(item.name.strip().casefold(), item.district.strip().casefold()): item for item in existing_rows}
    created = 0
    for district in districts:
        for name, category, unit, is_returnable, inventory_mode in STANDARD_DISTRICT_RESOURCE_CATALOG:
            key = (name.casefold(), district.casefold())
            if key in existing:
                existing[key].is_returnable = is_returnable
                if existing[key].quantity_total == 0 and existing[key].quantity_quarantined == 0:
                    existing[key].inventory_mode = inventory_mode
                continue
            item = ResourceItem(
                name=name,
                district=district,
                category=category,
                unit=unit,
                quantity_available=0,
                quantity_total=0,
                low_stock_threshold=0,
                is_returnable=is_returnable,
                inventory_mode=inventory_mode,
                is_active=True,
                created_by=admin.id,
            )
            db.add(item)
            existing[key] = item
            created += 1
    if created:
        log_action(db, admin, "resource_catalog_initialized", "resource_catalog", None,
                   f"Created {created} unstocked entries across {len(districts)} districts.")
    db.commit()
    return {
        "created": created,
        "districts": len(districts),
        "resources_per_district": len(STANDARD_DISTRICT_RESOURCE_CATALOG),
        "message": "Standard district resource catalog is ready. New items start with zero stock; add only confirmed quantities.",
    }


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
        "transaction_type": transaction.transaction_type,
        "reason": transaction.reason,
        "help_request_id": transaction.help_request_id,
        "responder_name": responder_name,
        "responder_email": responder_email,
        "created_at": transaction.created_at,
    } for transaction, responder_name, responder_email in rows]


@router.post("/resources", status_code=201)
def create_resource(data: ResourceCreate, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    if data.quantity_available != 0:
        raise HTTPException(status_code=422, detail="New inventory items start at zero. Add stock afterward with a reason so the change is audited.")
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
        quantity_available=data.quantity_available, quantity_total=data.quantity_available,
        low_stock_threshold=data.low_stock_threshold, is_returnable=data.is_returnable,
        inventory_mode=data.inventory_mode,
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
    if item.inventory_mode == "Tracked Asset":
        raise HTTPException(status_code=409, detail="Add or retire tracked units by asset identifier instead of changing a bulk quantity.")
    delta = data.quantity if data.direction == "add" else -data.quantity
    updated_quantity = item.quantity_available + delta
    if updated_quantity < 0:
        raise HTTPException(status_code=409, detail=f"Only {item.quantity_available} {item.unit} are currently available.")
    item.quantity_available = updated_quantity
    item.quantity_total += delta
    log_action(db, admin, "resource_stock_adjusted", "resource_item", item.id,
        f"{item.district or 'unassigned district'}: {data.direction.title()} {data.quantity} {item.unit}; {data.reason.strip()}; balance {updated_quantity}")
    db.commit()
    db.refresh(item)
    return resource_public(item)


@router.patch("/resources/{resource_id}/maintenance")
def update_bulk_resource_maintenance(resource_id: int, data: ResourceMaintenanceUpdate, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    item = db.query(ResourceItem).filter(ResourceItem.id == resource_id).with_for_update().first()
    if item is None or item.inventory_mode != "Bulk" or not item.is_returnable:
        raise HTTPException(status_code=404, detail="Reusable bulk inventory item not found.")
    if data.quantity > item.quantity_quarantined:
        raise HTTPException(status_code=409, detail=f"Only {item.quantity_quarantined} {item.unit} are currently in maintenance quarantine.")
    item.quantity_quarantined -= data.quantity
    if data.action == "repair":
        item.quantity_available += data.quantity
    else:
        item.quantity_total -= data.quantity
    log_action(db, admin, f"resource_bulk_{data.action}", "resource_item", item.id,
        f"{item.district}: {data.action.title()} {data.quantity} quarantined {item.unit}; {data.reason.strip()}")
    db.commit()
    db.refresh(item)
    return resource_public(item)


@router.get("/resources/{resource_id}/assets")
def list_resource_assets(resource_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    item = db.get(ResourceItem, resource_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found.")
    result = []
    for asset in db.query(ResourceAsset).filter(ResourceAsset.resource_id == item.id).order_by(ResourceAsset.asset_identifier).all():
        request_row = db.get(ResourceRequest, asset.assigned_request_id) if asset.assigned_request_id else None
        responder = db.get(User, request_row.responder_id) if request_row else None
        result.append({"id": asset.id, "identifier": asset.asset_identifier, "status": asset.status,
             "assigned_request_id": asset.assigned_request_id, "assigned_to": responder.full_name if responder else None,
             "help_request_id": request_row.help_request_id if request_row else None, "maintenance_note": asset.maintenance_note})
    return result


@router.post("/resources/{resource_id}/assets", status_code=201)
def add_resource_assets(resource_id: int, data: ResourceAssetsCreate, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    item = db.query(ResourceItem).filter(ResourceItem.id == resource_id).with_for_update().first()
    if item is None or item.inventory_mode != "Tracked Asset":
        raise HTTPException(status_code=404, detail="Tracked inventory item not found.")
    if not item.is_active:
        raise HTTPException(status_code=409, detail="Reactivate this item before adding assets.")
    identifiers = [identifier.strip() for identifier in data.identifiers]
    if any(not identifier for identifier in identifiers) or len({identifier.casefold() for identifier in identifiers}) != len(identifiers):
        raise HTTPException(status_code=422, detail="Asset identifiers must be non-empty and unique in this submission.")
    existing = {value.casefold() for (value,) in db.query(ResourceAsset.asset_identifier).all()}
    if any(identifier.casefold() in existing for identifier in identifiers):
        raise HTTPException(status_code=409, detail="An asset with one of those IDs already exists in the system.")
    db.add_all(ResourceAsset(resource_id=item.id, asset_identifier=value) for value in identifiers)
    item.quantity_available += len(identifiers)
    item.quantity_total += len(identifiers)
    log_action(db, admin, "resource_assets_added", "resource_item", item.id,
               f"Added tracked assets {', '.join(identifiers)} to {item.district}; reason: {data.reason.strip()}")
    db.commit()
    return {"added": len(identifiers), "item": resource_public(item)}


@router.patch("/resources/assets/{asset_id}/retire")
def retire_resource_asset(asset_id: int, data: ResourceAssetRetirement, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    asset = db.query(ResourceAsset).filter(ResourceAsset.id == asset_id).with_for_update().first()
    if asset is None:
        raise HTTPException(status_code=404, detail="Tracked asset not found.")
    if asset.status == "Assigned":
        raise HTTPException(status_code=409, detail="An assigned asset cannot be retired.")
    if asset.status == "Retired":
        raise HTTPException(status_code=409, detail="This asset is already retired.")
    item = db.query(ResourceItem).filter(ResourceItem.id == asset.resource_id).with_for_update().first()
    if asset.status == "Available":
        item.quantity_available = max(0, item.quantity_available - 1)
    elif asset.status == "Maintenance":
        item.quantity_quarantined = max(0, item.quantity_quarantined - 1)
    item.quantity_total = max(0, item.quantity_total - 1)
    asset.status = "Retired"
    asset.maintenance_note = data.reason.strip()
    log_action(db, admin, "resource_asset_retired", "resource_asset", asset.id,
               f"{asset.asset_identifier} from {item.district}; reason: {data.reason.strip()}")
    db.commit()
    return {"id": asset.id, "identifier": asset.asset_identifier, "status": asset.status}


@router.patch("/resources/assets/{asset_id}/maintenance")
def update_resource_asset_maintenance(asset_id: int, is_available: bool = Query(...), note: str = Query(default="", max_length=1000), db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    if not note.strip():
        raise HTTPException(status_code=422, detail="Add a repair or maintenance note for the audit record.")
    asset = db.query(ResourceAsset).filter(ResourceAsset.id == asset_id).with_for_update().first()
    if asset is None:
        raise HTTPException(status_code=404, detail="Tracked asset not found.")
    item = db.query(ResourceItem).filter(ResourceItem.id == asset.resource_id).with_for_update().first()
    if asset.status == "Assigned":
        raise HTTPException(status_code=409, detail="An assigned asset cannot be released from maintenance status.")
    if is_available and asset.status == "Maintenance":
        asset.status = "Available"
        item.quantity_available += 1
        item.quantity_quarantined = max(0, item.quantity_quarantined - 1)
    elif not is_available and asset.status == "Available":
        asset.status = "Maintenance"
        asset.maintenance_note = note.strip()
        item.quantity_available = max(0, item.quantity_available - 1)
        item.quantity_quarantined += 1
    elif (is_available and asset.status != "Maintenance") or (not is_available and asset.status != "Available"):
        raise HTTPException(status_code=409, detail=f"The asset is already {asset.status.lower()}.")
    if is_available:
        asset.maintenance_note = None
    log_action(db, admin, "resource_asset_maintenance_updated", "resource_asset", asset.id,
               f"{asset.asset_identifier}: {'available' if is_available else 'maintenance'}; {note.strip()}")
    db.commit()
    return {"id": asset.id, "identifier": asset.asset_identifier, "status": asset.status}


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


@router.patch("/resources/{resource_id}/threshold")
def update_resource_threshold(resource_id: int, data: ResourceThresholdUpdate, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    item = db.get(ResourceItem, resource_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found.")
    previous = item.low_stock_threshold
    item.low_stock_threshold = data.threshold
    log_action(db, admin, "resource_low_stock_threshold_updated", "resource_item", item.id,
               f"{item.district}: low-stock threshold {previous} -> {data.threshold} {item.unit}; {data.reason.strip()}")
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
        "is_available": bool(user.is_available and user.status == "active" and user.role in {"rescuer", "responder"}),
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
    if user.status != "active" or user.role not in {"rescuer", "responder"}:
        user.is_available = False
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


@router.get("/requests/{request_id}/messages")
def list_request_messages(request_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    request = db.get(HelpRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Help request not found.")
    rows = db.query(HelpRequestMessage).filter(
        HelpRequestMessage.help_request_id == request_id
    ).order_by(HelpRequestMessage.created_at.asc(), HelpRequestMessage.id.asc()).all()
    result = []
    for item in rows:
        sender = db.get(User, item.sender_user_id)
        result.append({
            "id": item.id,
            "help_request_id": item.help_request_id,
            "sender_user_id": item.sender_user_id,
            "sender_role": item.sender_role,
            "sender_name": sender.full_name if sender else "User",
            "message": item.message,
            "created_at": item.created_at,
        })
    return result


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
    if previous != data.status:
        record_status(db, help_request_id=request.id, status=data.status, actor_role="admin", note=data.reason or f"Administrator updated status to {data.status}.")
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
        if not any(district.casefold() == request.district.casefold()
                   for district, _ in responder_coverage):
            raise HTTPException(status_code=422, detail="The responder is not assigned to this request's district.")
        if request.status in {"Resolved", "Rejected"}:
            raise HTTPException(status_code=409, detail="A closed request cannot be assigned.")
    previous = request.assigned_responder_id
    previous_status = request.status
    request.assigned_responder_id = data.responder_id
    if data.responder_id is not None:
        request.status = "Assigned"
    detail = f"responder {previous} -> {data.responder_id}"
    if request.status != previous_status:
        record_status(db, help_request_id=request.id, status=request.status, actor_role="admin", note="Administrator assigned a responder.")
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
