import json
import os
import uuid

from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
    Request,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.core.database import get_db
from app.models.help_request import HelpRequest
from app.models.user import User
from app.schemas.help_request import (
    HelpRequestCreate,
    HelpRequestResponse,
)

# IMPORTANT:
# Replace this import with your existing authentication dependency
# if your project uses a different module or function name.
from app.routers.auth import get_current_user


router = APIRouter(
    prefix="/api/help-requests",
    tags=["Help Requests"],
)


BASE_DIR = Path(__file__).resolve().parents[1]

MAPPING_FILE = (
    BASE_DIR.parent.parent
    / "frontend"
    / "src"
    / "lac_locations.json"
)

UPLOAD_DIR = BASE_DIR / "uploads" / "help_requests"
UPLOAD_DIR = BASE_DIR / "uploads" / "help_requests"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_BYTES = 5 * 1024 * 1024

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

ALLOWED_STATUSES = {
    "Under Review",
    "Assigned",
    "In Progress",
    "Resolved",
    "Rejected",
}


def get_lac_mapping():
    if not MAPPING_FILE.is_file():
        raise HTTPException(
            status_code=500,
            detail=f"LAC mapping file not found: {MAPPING_FILE}",
        )

    try:
        with MAPPING_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        constituencies = data.get("constituencies")

        if not isinstance(constituencies, list):
            raise HTTPException(
                status_code=500,
                detail="Invalid LAC mapping: 'constituencies' list is missing.",
            )

        mapping = {}

        for item in constituencies:
            district = item.get("district")
            lac_name = item.get("lac_name")

            if not district or not lac_name:
                continue

            district = district.strip().upper()
            lac_name = lac_name.strip()

            if district and lac_name:
                mapping.setdefault(district, [])

                if lac_name not in mapping[district]:
                    mapping[district].append(lac_name)

        if not mapping:
            raise HTTPException(
                status_code=500,
                detail="No district and LAC entries were found in the mapping file.",
            )

        return mapping

    except HTTPException:
        raise

    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"LAC mapping could not be loaded: {exc}",
        ) from exc


def validate_district_and_lac(district: str, lac: str):
    mapping = get_lac_mapping()

    district_options = {
        name.casefold(): name
        for name in mapping
    }

    actual_district = district_options.get(district.casefold())

    if not actual_district:
        raise HTTPException(
            status_code=422,
            detail="Invalid district.",
        )

    lac_options = mapping[actual_district]

    actual_lac = next(
        (
            item
            for item in lac_options
            if item.casefold() == lac.casefold()
        ),
        None,
    )

    if not actual_lac:
        raise HTTPException(
            status_code=422,
            detail="The selected LAC does not belong to the selected district.",
        )

    return actual_district, actual_lac


def require_responder(current_user: User):
    if current_user.role not in {"admin", "responder", "rescuer"}:
        raise HTTPException(
            status_code=403,
            detail="Only authorized response personnel can perform this action.",
        )


async def save_image(file: Optional[UploadFile]):
    if not file or not file.filename:
        return None

    extension = ALLOWED_IMAGE_TYPES.get(file.content_type)

    if extension is None:
        raise HTTPException(
            status_code=415,
            detail="Only JPEG, PNG, and WebP images are allowed.",
        )

    content = await file.read(MAX_UPLOAD_BYTES + 1)

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded image is empty.",
        )

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Image size must not exceed 5 MB.",
        )

    # Check common file signatures rather than trusting the MIME type alone.
    valid_signatures = {
        ".jpg": content.startswith(b"\xff\xd8\xff"),
        ".png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        ".webp": (
            len(content) >= 12
            and content.startswith(b"RIFF")
            and content[8:12] == b"WEBP"
        ),
    }

    if not valid_signatures[extension]:
        raise HTTPException(
            status_code=415,
            detail="The uploaded file does not match its image type.",
        )

    filename = f"{uuid.uuid4().hex}{extension}"
    destination = UPLOAD_DIR / filename

    destination.write_bytes(content)

    return filename


@router.get("/districts")
def get_districts():
    mapping = get_lac_mapping()

    return {
        "districts": list(mapping.keys())
    }
@router.get("/lacs/{district}")
def get_lacs(district: str):
    mapping = get_lac_mapping()

    requested_district = district.strip().casefold()

    actual_district = next(
        (
            name
            for name in mapping
            if name.strip().casefold() == requested_district
        ),
        None,
    )

    if actual_district is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "District not found.",
                "requested_district": district,
                "available_districts": list(mapping.keys()),
            },
        )

    return {
        "district": actual_district,
        "lacs": mapping[actual_district],
    }



@router.post("/", response_model=HelpRequestResponse, status_code=201)
async def create_help_request(
    request: Request,
    district: str = Form(...),
    lac: str = Form(...),
    location_description: str = Form(...),
    emergency_type: str = Form(...),
    people_affected: int = Form(...),
    special_assistance: Optional[str] = Form(None),
    urgency: str = Form(...),
    situation_description: str = Form(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = HelpRequestCreate(
            district=district,
            lac=lac,
            location_description=location_description,
            emergency_type=emergency_type,
            people_affected=people_affected,
            special_assistance=special_assistance,
            urgency=urgency,
            situation_description=situation_description,
            latitude=latitude,
            longitude=longitude,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(include_input=False),
        )

    actual_district, actual_lac = validate_district_and_lac(
        data.district,
        data.lac,
    )

    saved_image = await save_image(image)

    help_request = HelpRequest(
        user_id=current_user.id,
        district=actual_district,
        lac=actual_lac,
        location_description=data.location_description,
        latitude=data.latitude,
        longitude=data.longitude,
        emergency_type=data.emergency_type,
        people_affected=data.people_affected,
        special_assistance=data.special_assistance,
        urgency=data.urgency,
        situation_description=data.situation_description,
        image_path=saved_image,
        status="Submitted",
    )

    try:
        db.add(help_request)
        db.commit()
        db.refresh(help_request)
    except Exception:
        db.rollback()

        if saved_image:
            (UPLOAD_DIR / saved_image).unlink(missing_ok=True)

        raise HTTPException(
            status_code=500,
            detail="Could not save the help request.",
        )

    return help_request


@router.get("/my", response_model=list[HelpRequestResponse])
def get_my_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(HelpRequest)
        .filter(HelpRequest.user_id == current_user.id)
        .order_by(HelpRequest.created_at.desc())
        .all()
    )


@router.get("/{request_id}", response_model=HelpRequestResponse)
def get_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    help_request = db.query(HelpRequest).filter(
        HelpRequest.id == request_id
    ).first()

    if not help_request:
        raise HTTPException(
            status_code=404,
            detail="Help request not found.",
        )

    if (
        help_request.user_id != current_user.id
        and current_user.role not in {"admin", "responder", "rescuer"}
    ):
        raise HTTPException(
            status_code=403,
            detail="You cannot access this request.",
        )

    return help_request


@router.get("/files/{filename}")
def get_request_image(
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Only allow generated image names, never arbitrary filesystem paths.
    if (
        "/" in filename
        or "\\" in filename
        or filename in {".", ".."}
    ):
        raise HTTPException(status_code=400, detail="Invalid filename.")

    help_request = db.query(HelpRequest).filter(
        HelpRequest.image_path == filename
    ).first()

    if not help_request:
        raise HTTPException(status_code=404, detail="Image not found.")

    if (
        help_request.user_id != current_user.id
        and current_user.role not in {"admin", "responder", "rescuer"}
    ):
        raise HTTPException(status_code=403, detail="Access denied.")

    path = UPLOAD_DIR / filename

    if not path.is_file():
        raise HTTPException(status_code=404, detail="Image file not found.")

    return FileResponse(path)


@router.get("/", response_model=list[HelpRequestResponse])
def get_all_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_responder(current_user)

    return (
        db.query(HelpRequest)
        .order_by(HelpRequest.created_at.desc())
        .all()
    )


@router.patch("/{request_id}/status")
def update_request_status(
    request_id: int,
    status: str,
    responder_notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_responder(current_user)

    if status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=422,
            detail="Invalid status.",
        )

    help_request = db.query(HelpRequest).filter(
        HelpRequest.id == request_id
    ).first()

    if not help_request:
        raise HTTPException(
            status_code=404,
            detail="Help request not found.",
        )

    help_request.status = status
    help_request.responder_notes = responder_notes

    db.commit()
    db.refresh(help_request)

    return {
        "message": "Request status updated.",
        "request": HelpRequestResponse.model_validate(help_request),
    }