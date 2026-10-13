
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.weather import WeatherData
from app.models.rainfall import RainfallData


MOCK_DATA_FILE = (
    Path(__file__).resolve().parents[1]
    / "mock_data"
    / "imd_current_weather.json"
)


def import_imd_mock_data(db: Session) -> dict:
    """Import normalized mock observations into MySQL for development."""

    if not MOCK_DATA_FILE.exists():
        raise FileNotFoundError(
            f"Mock data file not found: {MOCK_DATA_FILE}"
        )

    with MOCK_DATA_FILE.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    if payload.get("is_mock_data") is not True:
        raise ValueError("Import stopped: data is not marked as mock.")

    imported_weather = 0
    skipped_weather = 0
    imported_rainfall = 0
    skipped_rainfall = 0

    try:
        for item in payload.get("data", []):
            location_id = int(item["location_id"])

            recorded_at = datetime.strptime(
                f'{item["observation_date"]} '
                f'{item["observation_time"]}',
                "%Y-%m-%d %H:%M:%S",
            )

            location_exists = db.execute(
                text(
                    "SELECT id FROM locations "
                    "WHERE id = :location_id"
                ),
                {"location_id": location_id},
            ).first()

            if location_exists is None:
                raise ValueError(
                    f"Location ID {location_id} does not exist."
                )

            existing_weather = (
                db.query(WeatherData)
                .filter(
                    WeatherData.location_id == location_id,
                    WeatherData.recorded_at == recorded_at,
                )
                .first()
            )

            if existing_weather:
                skipped_weather += 1
            else:
                db.add(
                    WeatherData(
                        location_id=location_id,
                        temperature=item.get("temperature"),
                        humidity=item.get("humidity"),
                        wind_speed=item.get("wind_speed"),
                        source="MOCK",
                        recorded_at=recorded_at,
                    )
                )
                imported_weather += 1

            existing_rainfall = (
                db.query(RainfallData)
                .filter(
                    RainfallData.location_id == location_id,
                    RainfallData.recorded_at == recorded_at,
                )
                .first()
            )

            if existing_rainfall:
                skipped_rainfall += 1
            else:
                db.add(
                    RainfallData(
                        location_id=location_id,
                        rainfall_24h=item.get("rainfall_24h"),
                        rainfall_72h=item.get("rainfall_72h"),
                        rainfall_7d=item.get("rainfall_7d"),
                        source="MOCK",
                        recorded_at=recorded_at,
                    )
                )
                imported_rainfall += 1

        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "provider": payload.get("provider", "UNKNOWN"),
        "is_mock_data": True,
        "weather_imported": imported_weather,
        "weather_skipped": skipped_weather,
        "rainfall_imported": imported_rainfall,
        "rainfall_skipped": skipped_rainfall,
    }
