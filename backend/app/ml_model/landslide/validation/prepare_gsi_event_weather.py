"""Join strictly pre-event weather to GSI events with reported event hours."""

import csv
from datetime import datetime, timedelta
from pathlib import Path

import requests


ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
TIMEZONE = "Asia/Kolkata"
HERE = Path(__file__).resolve().parent
INPUT_PATH = HERE / "gsi_idukki_2018_event_labels.csv"
OUTPUT_PATH = HERE / "gsi_idukki_2018_events_with_weather.csv"


def _sum(values: list[float | None], end: int, hours: int) -> float | None:
    selected = [value for value in values[max(0, end - hours):end] if value is not None]
    return round(sum(selected), 2) if selected else None


def _mean(values: list[float | None], end: int, hours: int) -> float | None:
    selected = [value for value in values[max(0, end - hours):end] if value is not None]
    return round(sum(selected) / len(selected), 4) if selected else None


def fetch_pre_event_weather(event: dict[str, str]) -> dict:
    if event["event_time_precision"] != "hour" or not event["event_date"] or not event["event_time_ist"]:
        return {
            "weather_match_status": "not_matched_no_reported_event_hour",
            "weather_source": "",
        }

    event_time = datetime.fromisoformat(f"{event['event_date']}T{event['event_time_ist']}")
    start_date = (event_time - timedelta(days=7)).date().isoformat()
    response = requests.get(ARCHIVE_URL, params={
        "latitude": event["latitude"],
        "longitude": event["longitude"],
        "start_date": start_date,
        "end_date": event_time.date().isoformat(),
        "hourly": "precipitation,temperature_2m,relative_humidity_2m,soil_moisture_0_to_7cm,et0_fao_evapotranspiration",
        "timezone": TIMEZONE,
    }, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise ValueError(payload.get("reason", "Open-Meteo returned an error"))

    hourly = payload["hourly"]
    wanted = event_time.strftime("%Y-%m-%dT%H:%M")
    times = [value[:16] for value in hourly["time"]]
    try:
        event_index = times.index(wanted)
    except ValueError as exc:
        raise ValueError(f"Event hour {wanted} missing from archive response") from exc

    rainfall = hourly["precipitation"]
    window_72 = [value for value in rainfall[max(0, event_index - 72):event_index] if value is not None]
    return {
        "weather_match_status": "matched_pre_event_approximate_hour",
        "rainfall_1h_before_event_mm": rainfall[event_index - 1] if event_index else None,
        "rainfall_24h_before_event_mm": _sum(rainfall, event_index, 24),
        "rainfall_72h_before_event_mm": _sum(rainfall, event_index, 72),
        "rainfall_7d_before_event_mm": _sum(rainfall, event_index, 168),
        "max_hourly_rainfall_72h_mm": round(max(window_72, default=0.0), 2),
        "temperature_72h_mean_c": _mean(hourly["temperature_2m"], event_index, 72),
        "relative_humidity_72h_mean_pct": _mean(hourly["relative_humidity_2m"], event_index, 72),
        "soil_moisture_0_to_7cm_72h_mean": _mean(hourly["soil_moisture_0_to_7cm"], event_index, 72),
        "et0_72h_mm": _sum(hourly["et0_fao_evapotranspiration"], event_index, 72),
        "rainfall_window_start": (event_time - timedelta(days=7)).isoformat(sep=" "),
        "rainfall_window_end": (event_time - timedelta(hours=1)).isoformat(sep=" "),
        "weather_source": "Open-Meteo ERA5-Land archive at GSI event coordinates",
    }


def main() -> None:
    with INPUT_PATH.open(encoding="utf-8", newline="") as source:
        events = list(csv.DictReader(source))
    joined = [{**event, **fetch_pre_event_weather(event)} for event in events]
    columns = list(joined[0])
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=columns)
        writer.writeheader()
        writer.writerows(joined)
    print(f"Wrote {len(joined)} GSI event rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
