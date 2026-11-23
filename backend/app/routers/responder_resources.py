import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.help_request import HelpRequest
from app.models.resource_item import ResourceItem
from app.models.resource_asset import ResourceAsset
from app.models.resource_asset_assignment import ResourceAssetAssignment
from app.models.resource_request import ResourceRequest
from app.models.resource_request_batch import ResourceRequestBatch
from app.services.resource_request_triage import process_resource_request_batch
from app.models.resource_transaction import ResourceTransaction
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.help_requests import require_request_coverage, require_responder, responder_coverage_query

router = APIRouter(prefix="/api/responder/resources", tags=["Responder resources"])


class ResourceRequestCreate(BaseModel):
    resource_id: int | None = None
    custom_item_name: str | None = Field(default=None, min_length=2, max_length=120)
    district: str | None = Field(default=None, min_length=2, max_length=100)
    category: str = Field(default="Additional", min_length=2, max_length=60)
    unit: str = Field(default="units", min_length=1, max_length=40)
    quantity: int = Field(gt=0, le=100000)
    reason: str = Field(min_length=3, max_length=1000)
    help_request_id: int = Field(gt=0)
    priority: str = Field(default="Standard", pattern="^(Standard|Urgent|Critical)$")


class ResourceRequestBatchLine(BaseModel):
    resource_id: int | None = None
    custom_item_name: str | None = Field(default=None, min_length=2, max_length=120)
    category: str = Field(default="Additional", min_length=2, max_length=60)
    unit: str = Field(default="units", min_length=1, max_length=40)
    quantity: int = Field(gt=0, le=100000)


class ResourceRequestBatchCreate(BaseModel):
    help_request_id: int = Field(gt=0)
    district: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=3, max_length=2000)
    priority: str = Field(default="Standard", pattern="^(Standard|Urgent|Critical)$")
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    items: list[ResourceRequestBatchLine] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def require_coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Provide both latitude and longitude, or leave both blank.")
        return self


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
        "category": row.category or "Additional",
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
        batch = db.get(ResourceRequestBatch, row.transaction_id) if row.transaction_id else None
        if batch:
            view.update({"transaction_id": batch.tx_id, "transaction_status": batch.status,
                         "triage_state": batch.triage_state, "ai_priority": batch.ai_priority,
                         "ai_summary": batch.ai_summary})
        view["assets"] = [{"id": asset.id, "identifier": asset.asset_identifier, "status": asset.status}
            for assignment, asset in db.query(ResourceAssetAssignment, ResourceAsset).join(ResourceAsset, ResourceAsset.id == ResourceAssetAssignment.asset_id).filter(ResourceAssetAssignment.request_id == row.id).all()]
        results.append(view)
    return results


def create_resource_request(data: ResourceRequestCreate, db: Session, current_user: User, path_resource_id: int | None = None, transaction_id: int | None = None, commit: bool = True):
    require_responder(current_user)
    selected_resource_id = path_resource_id if path_resource_id is not None else data.resource_id
    item = None
    if selected_resource_id is not None:
        item = db.query(ResourceItem).filter(ResourceItem.id == selected_resource_id).with_for_update().first()
        if item is None or not item.is_active:
            raise HTTPException(status_code=404, detail="Inventory item not found or inactive.")
        require_resource_district(db, current_user, item)
        district, resource_name, category, unit = item.district, item.name, item.category, item.unit
        inventory_mode, is_returnable = item.inventory_mode, item.is_returnable
    else:
        if not data.custom_item_name or not data.district:
            raise HTTPException(status_code=422, detail="Choose a catalog item or enter a custom item name and district.")
        available_areas = responder_coverage_query(db, current_user)
        district_match = next((district for district, _ in available_areas if district.casefold() == data.district.strip().casefold()), None)
        if district_match is None:
            raise HTTPException(status_code=403, detail="Custom item requests are limited to your assigned districts.")
        district = district_match
        resource_name = data.custom_item_name.strip()
        if not resource_name:
            raise HTTPException(status_code=422, detail="Enter a name for the additional resource.")
        item = db.query(ResourceItem).filter(
            func.lower(ResourceItem.name) == resource_name.casefold(),
            func.lower(ResourceItem.district) == district.casefold(),
        ).with_for_update().first()
        if item:
            if not item.is_active:
                raise HTTPException(status_code=409, detail="An item with that name exists in this district but is inactive. Ask the admin to reactivate it.")
            resource_name, category, unit = item.name, item.category, item.unit
            inventory_mode, is_returnable = item.inventory_mode, item.is_returnable
        else:
            category, unit = data.category.strip(), data.unit.strip()
            if not category or not unit:
                raise HTTPException(status_code=422, detail="Enter a category and unit for the additional resource.")
            inventory_mode, is_returnable = "Bulk", False

    linked_request = db.get(HelpRequest, data.help_request_id)
    if linked_request is None:
        raise HTTPException(status_code=404, detail="Help request not found.")
    require_request_coverage(db, current_user, linked_request)
    if linked_request.district.casefold() != district.casefold():
        raise HTTPException(status_code=422, detail="The selected incident must be in the same district as the resource request.")
    if linked_request.assigned_responder_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the responder assigned to this help request can request resources for it.")
    if linked_request.status in {"Resolved", "Rejected"}:
        raise HTTPException(status_code=409, detail="Resources cannot be requested for a closed help request.")

    reason = data.reason.strip()
    if not reason:
        raise HTTPException(status_code=422, detail="Add a reason for the resource request.")
    row = ResourceRequest(
        transaction_id=transaction_id,
        resource_id=item.id if item else None,
        responder_id=current_user.id,
        help_request_id=linked_request.id,
        district=district,
        resource_name=resource_name,
        category=category,
        unit=unit,
        inventory_mode=inventory_mode,
        quantity_requested=data.quantity,
        is_returnable=is_returnable,
        priority=data.priority,
        reason=reason,
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()
    return row


@router.post("/request-batches", status_code=201)
def create_resource_request_batch(data: ResourceRequestBatchCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_responder(current_user)
    linked_request = db.get(HelpRequest, data.help_request_id)
    if linked_request is None:
        raise HTTPException(status_code=404, detail="Help request not found.")
    require_request_coverage(db, current_user, linked_request)
    if linked_request.assigned_responder_id != current_user.id or linked_request.status in {"Resolved", "Rejected"}:
        raise HTTPException(status_code=403, detail="The linked incident must be active and assigned to you.")
    if linked_request.district.casefold() != data.district.strip().casefold():
        raise HTTPException(status_code=422, detail="The selected incident must be in the same district as the resource request.")
    if any((line.resource_id is None) == (not line.custom_item_name) for line in data.items):
        raise HTTPException(status_code=422, detail="Each line must select either a catalog item or a new item name.")

    district_code = "".join(character for character in data.district.upper() if character.isalnum())[:12]
    batch = ResourceRequestBatch(
        tx_id=f"REQ-KL-{district_code}-{secrets.token_hex(16).upper()}",
        responder_id=current_user.id,
        help_request_id=linked_request.id,
        district=linked_request.district,
        description=data.description.strip(),
        latitude=data.latitude if data.latitude is not None else linked_request.latitude,
        longitude=data.longitude if data.longitude is not None else linked_request.longitude,
        status="PENDING_AI_TRIAGE",
        triage_state="PENDING",
    )
    db.add(batch)
    try:
        db.flush()
        created_rows = []
        for line in data.items:
            line_data = ResourceRequestCreate(
                resource_id=line.resource_id,
                custom_item_name=line.custom_item_name,
                district=data.district,
                category=line.category,
                unit=line.unit,
                quantity=line.quantity,
                reason=data.description.strip(),
                help_request_id=data.help_request_id,
                priority=data.priority,
            )
            created_rows.append(create_resource_request(line_data, db, current_user, transaction_id=batch.id, commit=False))
        item_keys = [(row.resource_id or f"custom:{row.resource_name.strip().casefold()}", row.district.strip().casefold()) for row in created_rows]
        if len(item_keys) != len(set(item_keys)):
            raise HTTPException(status_code=422, detail="Each resource can appear only once in a transaction; combine its quantity on one line.")
        db.commit()
        db.refresh(batch)
        background_tasks.add_task(process_resource_request_batch, batch.id)
        return {"transaction_id": batch.tx_id, "status": batch.status, "triage_state": batch.triage_state,
                "items": [resource_request_view(row) for row in created_rows]}
    except Exception:
        db.rollback()
        raise


@router.post("/requests", status_code=201)
def request_catalog_or_custom_resource(data: ResourceRequestCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = create_resource_request(data, db, current_user)
    return {"message": f"Request for {row.quantity_requested} {row.unit} of {row.resource_name} sent to the administrator.", "request": resource_request_view(row)}


@router.post("/{resource_id}/requests", status_code=201)
def request_catalog_resource(resource_id: int, data: ResourceRequestCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = create_resource_request(data, db, current_user, path_resource_id=resource_id)
    return {"message": f"Request for {row.quantity_requested} {row.unit} of {row.resource_name} sent to the administrator.", "request": resource_request_view(row)}


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
