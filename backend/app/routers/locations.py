
import json
from urllib.error import URLError
from urllib.request import urlopen
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.location import Location
from app.schemas.location import LocationResponse


router = APIRouter(
    prefix="/api/districts",
    tags=["Districts"],
)


@router.get(
    "",
    response_model=list[LocationResponse],
)
def get_districts(
    db: Session = Depends(get_db),
):
    districts = (
        db.query(Location)
        .filter(Location.location_type == "DISTRICT")
        .order_by(Location.name)
        .all()
    )

    return districts


@router.get(
    "/{district_id}",
    response_model=LocationResponse,
)
def get_district(
    district_id: int,
    db: Session = Depends(get_db),
):
    district = (
        db.query(Location)
        .filter(
            Location.id == district_id,
            Location.location_type == "DISTRICT",
        )
        .first()
    )

    if district is None:
        raise HTTPException(
            status_code=404,
            detail="District not found",
        )

    return district


@router.get(
    "/{district_id}/lacs",
    response_model=list[LocationResponse],
)
def get_district_lacs(
    district_id: int,
    db: Session = Depends(get_db),
):
    district = (
        db.query(Location)
        .filter(
            Location.id == district_id,
            Location.location_type == "DISTRICT",
        )
        .first()
    )

    if district is None:
        raise HTTPException(
            status_code=404,
            detail="District not found",
        )

    lacs = (
        db.query(Location)
        .filter(
            Location.parent_id == district_id,
            Location.location_type == "LAC",
        )
        .order_by(Location.administrative_code)
        .all()
    )

    return lacs


# --------------------------------------------------
# GET LOCATIONS BELONGING TO A DISTRICT
# --------------------------------------------------
@router.get("/{district_id}/locations")
def get_district_locations(
    district_id: int,
    db: Session = Depends(get_db),
):
    district = (
        db.query(Location)
        .filter(
            Location.id == district_id,
            Location.location_type == "DISTRICT",
        )
        .first()
    )

    if district is None:
        raise HTTPException(
            status_code=404,
            detail="District not found",
        )

    locations = (
        db.query(Location)
        .filter(
            Location.parent_id == district_id
        )
        .order_by(Location.name)
        .all()
    )

    return {
        "district": district.name,
        "district_id": district.id,
        "locations": [
            {
                "id": location.id,
                "name": location.name,
                "location_type": location.location_type,
                "latitude": location.latitude,
                "longitude": location.longitude,
            }
            for location in locations
        ],
    }


# --------------------------------------------------
# GET CURRENT WEATHER FOR A DISTRICT
# --------------------------------------------------
DISTRICT_COORDS = {
    "THIRUVANANTHAPURAM": (8.5241, 76.9366),
    "TRIVANDRUM": (8.5241, 76.9366),
    "KOLLAM": (8.8932, 76.6141),
    "PATHANAMTHITTA": (9.2648, 76.7870),
    "ALAPPUZHA": (9.4981, 76.3388),
    "KOTTAYAM": (9.5916, 76.5222),
    "IDUKKI": (9.8500, 76.9667),
    "ERNAKULAM": (9.9816, 76.2999),
    "ERANAKULAM": (9.9816, 76.2999),
    "THRISSUR": (10.5276, 76.2144),
    "TRICHUR": (10.5276, 76.2144),
    "PALAKKAD": (10.7867, 76.6548),
    "MALAPPURAM": (11.0720, 76.0740),
    "KOZHIKODE": (11.2588, 75.7804),
    "WAYANAD": (11.6854, 76.1320),
    "WYNAD": (11.6854, 76.1320),
    "KANNUR": (11.8745, 75.3704),
    "KASARAGOD": (12.5102, 74.9852),
}


@router.get("/{district_id}/weather")
def get_district_weather(
    district_id: int,
    db: Session = Depends(get_db),
):
    district = (
        db.query(Location)
        .filter(
            Location.id == district_id,
            Location.location_type == "DISTRICT",
        )
        .first()
    )

    if district is None:
        raise HTTPException(
            status_code=404,
            detail="District not found",
        )

    lat = district.latitude
    lng = district.longitude

    if lat is None or lng is None:
        fallback = DISTRICT_COORDS.get(district.name.strip().upper(), (10.5, 76.2))
        lat, lng = fallback

    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}"
        f"&longitude={lng}"
        "&current=temperature_2m,relative_humidity_2m,"
        "precipitation,wind_speed_10m"
        "&timezone=Asia%2FKolkata"
    )

    try:
        with urlopen(url, timeout=10) as response:
            weather = json.loads(
                response.read().decode("utf-8")
            )
    except (URLError, TimeoutError):
        raise HTTPException(
            status_code=503,
            detail="Weather service is temporarily unavailable",
        )

    current = weather.get("current")

    if current is None:
        raise HTTPException(
            status_code=502,
            detail="Weather data is unavailable",
        )

    return {
        "district_id": district.id,
        "district": district.name,
        "temperature": current.get("temperature_2m"),
        "humidity": current.get("relative_humidity_2m"),
        "rainfall": current.get("precipitation"),
        "wind_speed": current.get("wind_speed_10m"),
        "time": current.get("time"),
    }

