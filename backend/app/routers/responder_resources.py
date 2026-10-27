from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.help_request import HelpRequest
from app.models.resource_item import ResourceItem
from app.models.resource_transaction import ResourceTransaction
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.help_requests import require_request_coverage, require_responder, responder_coverage_query

router = APIRouter(prefix="/api/responder/resources", tags=["Responder resources"])


class ResourceIssue(BaseModel):
    quantity: int = Field(gt=0, le=100000)
    reason: str = Field(min_length=3, max_length=1000)
    help_request_id: int | None = None


def resource_view(item: ResourceItem):
    return {
        "id": item.id,
        "name": item.name,
        "district": item.district,
        "category": item.category,
        "unit": item.unit,
        "quantity_available": item.quantity_available,
        "low_stock_threshold": item.low_stock_threshold,
    }


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
    return [resource_view(item) for item in items if item.district.casefold() in districts]


@router.post("/{resource_id}/issue")
def issue_resource(
    resource_id: int,
    data: ResourceIssue,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_responder(current_user)
    item = db.query(ResourceItem).filter(ResourceItem.id == resource_id).with_for_update().first()
    if item is None or not item.is_active:
        raise HTTPException(status_code=404, detail="Available inventory item not found.")

    coverage = responder_coverage_query(db, current_user)
    if not item.district or not any(district.casefold() == item.district.casefold() for district, _ in coverage):
        raise HTTPException(status_code=403, detail="This item is outside your assigned district coverage.")
    if data.quantity > item.quantity_available:
        raise HTTPException(status_code=409, detail=f"Only {item.quantity_available} {item.unit} are currently available in {item.district}.")

    linked_request = None
    if data.help_request_id is not None:
        linked_request = db.get(HelpRequest, data.help_request_id)
        if linked_request is None:
            raise HTTPException(status_code=404, detail="Help request not found.")
        require_request_coverage(db, current_user, linked_request)
        if linked_request.district.casefold() != item.district.casefold():
            raise HTTPException(status_code=422, detail="The selected help request is in a different district from this stock.")
        if linked_request.assigned_responder_id != current_user.id:
            raise HTTPException(status_code=403, detail="Only the responder assigned to this help request can issue resources for it.")
        if linked_request.status in {"Resolved", "Rejected"}:
            raise HTTPException(status_code=409, detail="Resources cannot be issued to a closed help request.")

    reason = data.reason.strip()
    if not reason:
        raise HTTPException(status_code=422, detail="Add a reason for issuing this resource.")

    item.quantity_available -= data.quantity
    db.add(ResourceTransaction(
        resource_id=item.id,
        responder_id=current_user.id,
        help_request_id=linked_request.id if linked_request else None,
        resource_name=item.name,
        district=item.district,
        unit=item.unit,
        quantity=data.quantity,
        reason=reason,
    ))
    db.commit()
    db.refresh(item)
    return {"message": f"Issued {data.quantity} {item.unit} of {item.name} from {item.district} stock.", "item": resource_view(item)}
