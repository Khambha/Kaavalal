"""Join Open-Meteo historical weather to the official 2018 flood snapshot.

The output is district-centroid weather matched to the satellite observation
date. The event inventory contains positives only; it is not a classifier
training set or a 72-hour forecast benchmark.
"""

import csv
from datetime import datetime, timedelta
from pathlib import Path

import requests


ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
TIMEZONE = "Asia/Kolkata"
INPUT_PATH = Path(__file__).resolve().parent / "flood_inundation_2018-07-16_district_labels.csv"
OUTPUT_PATH = Path(__file__).resolve().parent / "flood_inundation_2018-07-16_with_weather.csv"

# Same district representative points already used by Kaavalal's weather router.
DISTRICT_COORDINATES = {
    "Alappuzha": (9.4981, 76.3388),
    "Ernakulam": (9.9816, 76.2999),
    "Kottayam": (9.5916, 76.5222),
    "Pathanamthitta": (9.2648, 76.7870),
    "Malappuram": (11.0720, 76.0740),
    "Kollam": (8.8932, 76.6141),
    "Thrissur": (10.5276, 76.2144),
}


def _sum(values: list[float | None], end: int, hours: int) -> float | None:
    window = [value for value in values[max(0, end - hours):end] if value is not None]
    return round(sum(window), 2) if window else None


def _mean(values: list[float | None], end: int, hours: int) -> float | None:
    window = [value for value in values[max(0, end - hours):end] if value is not None]
    return round(sum(window) / len(window), 4) if window else None


def fetch_weather(district: str, observation_date: str) -> dict:
    latitude, longitude = DISTRICT_COORDINATES[district]
    observation_midnight = datetime.fromisoformat(observation_date)
    start_date = (observation_midnight - timedelta(days=7)).date().isoformat()
    end_date = observation_midnight.date().isoformat()
    response = requests.get(ARCHIVE_URL, params={
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "precipitation,temperature_2m,relative_humidity_2m,soil_moisture_0_to_7cm,et0_fao_evapotranspiration",
        "timezone": TIMEZONE,
    }, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise ValueError(payload.get("reason", "Open-Meteo returned an error"))

    hourly = payload["hourly"]
    times = [time[:16] for time in hourly["time"]]
    cutoff = observation_midnight.strftime("%Y-%m-%dT%H:%M")
    try:
        end_index = times.index(cutoff)
    except ValueError as exc:
        raise ValueError(f"Observation cutoff {cutoff} is missing from archive response") from exc

    rainfall = hourly["precipitation"]
    precipitation_24h = _sum(rainfall, end_index, 24)
    precipitation_72h = _sum(rainfall, end_index, 72)
    return {
        "latitude": latitude,
        "longitude": longitude,
        "rainfall_1h_before_observation_mm": rainfall[end_index - 1] if end_index else None,
        "rainfall_24h_before_observation_mm": precipitation_24h,
        "rainfall_72h_before_observation_mm": precipitation_72h,
        "rainfall_7d_before_observation_mm": _sum(rainfall, end_index, 168),
        "max_hourly_rainfall_72h_mm": round(max(
            (value for value in rainfall[max(0, end_index - 72):end_index] if value is not None),
            default=0.0,
        ), 2),
        "temperature_72h_mean_c": _mean(hourly["temperature_2m"], end_index, 72),
        "relative_humidity_72h_mean_pct": _mean(hourly["relative_humidity_2m"], end_index, 72),
        "soil_moisture_0_to_7cm_72h_mean": _mean(hourly["soil_moisture_0_to_7cm"], end_index, 72),
        "et0_72h_mm": _sum(hourly["et0_fao_evapotranspiration"], end_index, 72),
        "rainfall_window_start": (observation_midnight - timedelta(days=7)).isoformat(sep=" "),
        "rainfall_window_end": (observation_midnight - timedelta(hours=1)).isoformat(sep=" "),
        "weather_source": "Open-Meteo ERA5-Land archive at district representative point",
    }


def main() -> None:
    with INPUT_PATH.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    weather_rows = [fetch_weather(row["district"], row["observation_date"]) for row in rows]
    columns = list(rows[0]) + list(weather_rows[0])
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=columns)
        writer.writeheader()
        for label, weather in zip(rows, weather_rows):
            writer.writerow({**label, **weather})
    print(f"Wrote {len(rows)} date-aligned district rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
