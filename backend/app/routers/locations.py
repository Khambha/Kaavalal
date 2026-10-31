
import json
from urllib.error import URLError
from urllib.request import urlopen
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.location import Location
from app.schemas.location import LocationResponse


router = APIRouter(
    prefix="/api/districts",
    tags=["Districts"],
)

WMO_WEATHER_DESCRIPTIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Heavy rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def serialize_current_weather(current: dict):
    weather_code = current.get("weather_code")
    return {
        "temperature": current.get("temperature_2m"),
        "feels_like": current.get("apparent_temperature"),
        "humidity": current.get("relative_humidity_2m"),
        "pressure": current.get("pressure_msl"),
        "cloudiness": current.get("cloud_cover"),
        "visibility": current.get("visibility"),
        "wind_speed": current.get("wind_speed_10m"),
        "wind_direction": current.get("wind_direction_10m"),
        "rainfall": current.get("precipitation"),
        "rainfall_1h": current.get("precipitation"),
        "weather_code": weather_code,
        "weather_condition": WMO_WEATHER_DESCRIPTIONS.get(weather_code, "Conditions unavailable"),
        "time": current.get("time"),
        "source": "Open-Meteo",
    }


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


def fetch_open_meteo_current(lat: float, lng: float):
    """Fetch current conditions for a WGS84 point from Open-Meteo."""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}"
        f"&longitude={lng}"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
        "pressure_msl,cloud_cover,visibility,weather_code,precipitation,"
        "wind_speed_10m,wind_direction_10m"
        "&timezone=Asia%2FKolkata"
    )
    try:
        with urlopen(url, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError):
        raise HTTPException(status_code=503, detail="Weather service is temporarily unavailable")

    current = payload.get("current")
    if current is None:
        raise HTTPException(status_code=502, detail="Weather data is unavailable")
    return current


@router.get("/{district_id}/lacs/{lac_code}/weather")
def get_lac_weather(
    district_id: int,
    lac_code: str,
    latitude: float | None = Query(default=None, ge=8.0, le=13.0),
    longitude: float | None = Query(default=None, ge=74.0, le=78.0),
    db: Session = Depends(get_db),
):
    """Return live weather for a LAC coordinate, falling back to its map coordinate."""
    district = (
        db.query(Location)
        .filter(Location.id == district_id, Location.location_type == "DISTRICT")
        .first()
    )
    if district is None:
        raise HTTPException(status_code=404, detail="District not found")

    lac = (
        db.query(Location)
        .filter(
            Location.parent_id == district_id,
            Location.location_type == "LAC",
            Location.administrative_code == lac_code,
        )
        .first()
    )

    # Prefer coordinates maintained by the backend. The frontend supplies its
    # public LAC centroid only when the local database has no coordinates yet.
    lat = lac.latitude if lac and lac.latitude is not None else latitude
    lng = lac.longitude if lac and lac.longitude is not None else longitude
    if lat is None or lng is None:
        raise HTTPException(status_code=400, detail="LAC latitude and longitude are required")
    if not (8.0 <= lat <= 13.0 and 74.0 <= lng <= 78.0):
        raise HTTPException(status_code=422, detail="LAC coordinates must be within Kerala")

    current = fetch_open_meteo_current(lat, lng)
    return {
        "district_id": district.id,
        "district": district.name,
        "lac_code": lac_code,
        "lac": lac.name if lac else None,
        "latitude": lat,
        "longitude": lng,
        **serialize_current_weather(current),
        "scope": "LAC coordinates",
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

    current = fetch_open_meteo_current(lat, lng)

    return {
        "district_id": district.id,
        "district": district.name,
        **serialize_current_weather(current),
    }

