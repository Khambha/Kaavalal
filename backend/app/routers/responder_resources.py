from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.help_request import HelpRequest
from app.models.resource_item import ResourceItem
from app.models.resource_asset import ResourceAsset
from app.models.resource_asset_assignment import ResourceAssetAssignment
from app.models.resource_request import ResourceRequest
from app.models.resource_transaction import ResourceTransaction
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.help_requests import require_request_coverage, require_responder, responder_coverage_query

router = APIRouter(prefix="/api/responder/resources", tags=["Responder resources"])


class ResourceRequestCreate(BaseModel):
    quantity: int = Field(gt=0, le=100000)
    reason: str = Field(min_length=3, max_length=1000)
    help_request_id: int = Field(gt=0)
    priority: str = Field(default="Standard", pattern="^(Standard|Urgent|Critical)$")


class ResourceReturn(BaseModel):
    quantity: int = Field(default=1, gt=0, le=100000)
    asset_ids: list[int] = Field(default_factory=list, max_length=1000)
    condition: str = Field(default="Good", pattern="^(Good|Damaged)$")
    note: str | None = Field(default=None, max_length=1000)


def resource_view(item: ResourceItem):
    return {
        "id": item.id,
        "name": item.name,
        "district": item.district,
        "category": item.category,
        "unit": item.unit,
        "quantity_available": item.quantity_available,
        "low_stock_threshold": item.low_stock_threshold,
        "is_returnable": item.is_returnable,
        "inventory_mode": item.inventory_mode,
        "is_active": item.is_active,
    }


def resource_request_view(row: ResourceRequest):
    granted = row.quantity_granted or 0
    return {
        "id": row.id,
        "resource_id": row.resource_id,
        "help_request_id": row.help_request_id,
        "district": row.district,
        "resource_name": row.resource_name,
        "unit": row.unit,
        "inventory_mode": row.inventory_mode,
        "quantity_requested": row.quantity_requested,
        "quantity_granted": granted,
        "quantity_returned": row.quantity_returned,
        "quantity_quarantined": row.quantity_quarantined,
        "quantity_in_use": max(0, granted - row.quantity_returned) if row.is_returnable else 0,
        "is_returnable": row.is_returnable,
        "priority": row.priority,
        "rejection_reason": row.rejection_reason,
        "reason": row.reason,
        "status": row.status,
        "created_at": row.created_at,
        "reviewed_at": row.reviewed_at,
    }


def require_resource_district(db: Session, user: User, item: ResourceItem):
    coverage = responder_coverage_query(db, user)
    if not item.district or not any(district.casefold() == item.district.casefold() for district, _ in coverage):
        raise HTTPException(status_code=403, detail="This item is outside your assigned district coverage.")


@router.get("")
def list_covered_resources(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_responder(current_user)
    coverage = responder_coverage_query(db, current_user)
    districts = {district.casefold() for district, _ in coverage}
    if not districts:
        return []
    items = db.query(ResourceItem).filter(
        ResourceItem.is_active.is_(True),
        ResourceItem.district.is_not(None),
    ).order_by(ResourceItem.district, ResourceItem.category, ResourceItem.name).all()
    results = []
    for item in items:
        if item.district.casefold() not in districts:
            continue
        view = resource_view(item)
        if item.inventory_mode == "Tracked Asset":
            view["available_assets"] = [{"id": asset.id, "identifier": asset.asset_identifier}
                for asset in db.query(ResourceAsset).filter(ResourceAsset.resource_id == item.id, ResourceAsset.status == "Available").order_by(ResourceAsset.asset_identifier).all()]
        results.append(view)
    return results


@router.get("/requests")
def list_my_resource_requests(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_responder(current_user)
    rows = db.query(ResourceRequest).filter(
        ResourceRequest.responder_id == current_user.id,
    ).order_by(ResourceRequest.created_at.desc(), ResourceRequest.id.desc()).limit(200).all()
    results = []
    for row in rows:
        view = resource_request_view(row)
        view["assets"] = [{"id": asset.id, "identifier": asset.asset_identifier, "status": asset.status}
            for assignment, asset in db.query(ResourceAssetAssignment, ResourceAsset).join(ResourceAsset, ResourceAsset.id == ResourceAssetAssignment.asset_id).filter(ResourceAssetAssignment.request_id == row.id).all()]
        results.append(view)
    return results


@router.post("/{resource_id}/requests", status_code=201)
def request_resource(
    resource_id: int,
    data: ResourceRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_responder(current_user)
    item = db.query(ResourceItem).filter(ResourceItem.id == resource_id).with_for_update().first()
    if item is None or not item.is_active:
        raise HTTPException(status_code=404, detail="Available inventory item not found.")
    require_resource_district(db, current_user, item)
    if data.quantity > item.quantity_available:
        raise HTTPException(status_code=409, detail=f"Only {item.quantity_available} {item.unit} are currently available in {item.district}.")

    linked_request = db.get(HelpRequest, data.help_request_id)
    if linked_request is None:
        raise HTTPException(status_code=404, detail="Help request not found.")
    require_request_coverage(db, current_user, linked_request)
    if linked_request.district.casefold() != item.district.casefold():
        raise HTTPException(status_code=422, detail="The selected help request is in a different district from this stock.")
    if linked_request.assigned_responder_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the responder assigned to this help request can request resources for it.")
    if linked_request.status in {"Resolved", "Rejected"}:
        raise HTTPException(status_code=409, detail="Resources cannot be requested for a closed help request.")

    reason = data.reason.strip()
    if not reason:
        raise HTTPException(status_code=422, detail="Add a reason for the resource request.")
    row = ResourceRequest(
        resource_id=item.id,
        responder_id=current_user.id,
        help_request_id=linked_request.id,
        district=item.district,
        resource_name=item.name,
        unit=item.unit,
        inventory_mode=item.inventory_mode,
        quantity_requested=data.quantity,
        is_returnable=item.is_returnable,
        priority=data.priority,
        reason=reason,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"message": f"Request for {data.quantity} {item.unit} of {item.name} sent to the administrator.", "request": resource_request_view(row)}


@router.post("/requests/{request_id}/return")
def return_resource(
    request_id: int,
    data: ResourceReturn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_responder(current_user)
    row = db.query(ResourceRequest).filter(ResourceRequest.id == request_id).with_for_update().first()
    if row is None or row.responder_id != current_user.id:
        raise HTTPException(status_code=404, detail="Resource allocation not found.")
    if not row.is_returnable:
        raise HTTPException(status_code=409, detail="This resource is consumable and cannot be returned to stock.")
    if row.status not in {"Granted", "Partially Granted", "Partially Returned"}:
        raise HTTPException(status_code=409, detail="Only granted resource allocations can be returned.")
    outstanding = (row.quantity_granted or 0) - row.quantity_returned
    item = db.query(ResourceItem).filter(ResourceItem.id == row.resource_id).with_for_update().first()
    if item is None:
        raise HTTPException(status_code=404, detail="The inventory item for this allocation no longer exists.")
    if data.condition == "Damaged" and not (data.note or "").strip():
        raise HTTPException(status_code=422, detail="Describe the damage or maintenance needed.")
    if item.inventory_mode == "Tracked Asset":
        if not data.asset_ids:
            raise HTTPException(status_code=422, detail="Select the tracked asset IDs being returned.")
        assignments = db.query(ResourceAssetAssignment, ResourceAsset).join(
            ResourceAsset, ResourceAsset.id == ResourceAssetAssignment.asset_id
        ).filter(ResourceAssetAssignment.request_id == row.id,
                 ResourceAssetAssignment.asset_id.in_(data.asset_ids),
                 ResourceAssetAssignment.returned_at.is_(None)).with_for_update().all()
        if len(assignments) != len(set(data.asset_ids)):
            raise HTTPException(status_code=409, detail="One or more selected assets are not currently assigned to this request.")
        returned_quantity = len(assignments)
        if returned_quantity > outstanding:
            raise HTTPException(status_code=409, detail=f"Only {outstanding} assets remain assigned to you.")
        for assignment, asset in assignments:
            assignment.returned_at = datetime.now(timezone.utc)
            assignment.return_condition = data.condition
            assignment.return_note = (data.note or "").strip() or None
            asset.assigned_request_id = None
            if data.condition == "Damaged":
                asset.status = "Maintenance"
                asset.maintenance_note = (data.note or "").strip()
            else:
                asset.status = "Available"
        if data.condition == "Good":
            item.quantity_available += returned_quantity
        else:
            item.quantity_quarantined += returned_quantity
            row.quantity_quarantined += returned_quantity
    else:
        if data.asset_ids:
            raise HTTPException(status_code=422, detail="Choose individual assets only for tracked-asset inventory.")
        if data.quantity > outstanding:
            raise HTTPException(status_code=409, detail=f"Only {outstanding} {row.unit} remain assigned to you.")
        returned_quantity = data.quantity
        if data.condition == "Good":
            item.quantity_available += returned_quantity
        else:
            item.quantity_quarantined += returned_quantity
            row.quantity_quarantined += returned_quantity
    row.quantity_returned += returned_quantity
    row.status = "Returned" if row.quantity_returned == row.quantity_granted else "Partially Returned"
    db.add(ResourceTransaction(
        resource_id=item.id,
        responder_id=current_user.id,
        help_request_id=row.help_request_id,
        resource_name=row.resource_name,
        district=row.district,
        unit=row.unit,
        quantity=returned_quantity,
        transaction_type="Returned" if data.condition == "Good" else "Quarantined",
        reason=f"Resource request #{row.id}; {data.condition.lower()} return{': ' + data.note.strip() if data.note and data.note.strip() else ''}",
    ))
    db.commit()
    db.refresh(row)
    location = "available stock" if data.condition == "Good" else "maintenance quarantine"
    return {"message": f"Returned {returned_quantity} {row.unit} of {row.resource_name} to {location}.", "request": resource_request_view(row), "item": resource_view(item)}
