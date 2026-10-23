import os

import requests
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.location import Location

load_dotenv()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

router = APIRouter(
    prefix="/api/weather",
    tags=["Weather"],
)


@router.get("/{location_id}")
def get_weather(
    location_id: int,
    db: Session = Depends(get_db),
):
    # Find the requested location in MySQL.
    location = (
        db.query(Location)
        .filter(Location.id == location_id)
        .first()
    )

    if location is None:
        raise HTTPException(
            status_code=404,
            detail="Location not found",
        )

    # Check the API key.
    if not OPENWEATHER_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="OpenWeather API key is not configured",
        )

    # Check whether the location has coordinates.
    if location.latitude is None or location.longitude is None:
        raise HTTPException(
            status_code=400,
            detail="Latitude and longitude are missing for this location",
        )

    # Request live weather from OpenWeather.
    url = "https://api.openweathermap.org/data/2.5/weather"

    params = {
        "lat": location.latitude,
        "lon": location.longitude,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10,
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=502,
            detail="Unable to connect to OpenWeather",
        )

    if response.status_code == 401:
        raise HTTPException(
            status_code=502,
            detail="OpenWeather rejected the API key. Check the key and its activation status.",
        )

    if response.status_code == 429:
        raise HTTPException(
            status_code=502,
            detail="OpenWeather API request limit reached",
        )

    if not response.ok:
        raise HTTPException(
            status_code=502,
            detail="OpenWeather could not provide weather data",
        )

    data = response.json()

    # Return live weather information.
    weather_items = data.get("weather", [])
    weather_condition = (
        weather_items[0].get("description")
        if weather_items
        else None
    )
    weather_icon = weather_items[0].get("icon") if weather_items else None

    rainfall = data.get("rain", {}).get("1h")

    return {
        "location_id": location.id,
        "location_name": location.name,
        "latitude": data.get("coord", {}).get("lat", location.latitude),
        "longitude": data.get("coord", {}).get("lon", location.longitude),
        "temperature": data.get("main", {}).get("temp"),
        "feels_like": data.get("main", {}).get("feels_like"),
        "humidity": data.get("main", {}).get("humidity"),
        "pressure": data.get("main", {}).get("pressure"),
        "wind_speed": data.get("wind", {}).get("speed"),
        "wind_direction": data.get("wind", {}).get("deg"),
        "cloudiness": data.get("clouds", {}).get("all"),
        "visibility": data.get("visibility"),
        "weather_condition": weather_condition,
        "weather_icon": weather_icon,
        "rainfall_1h": rainfall,
        "sunrise": data.get("sys", {}).get("sunrise"),
        "sunset": data.get("sys", {}).get("sunset"),
        "source": "OpenWeather",
        "recorded_at": data.get("dt"),
    }
