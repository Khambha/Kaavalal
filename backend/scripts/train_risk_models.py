"""Prepare auditable district weather/label datasets for hazard model work.

This command intentionally does not emit production classifiers: the current
repository lacks label coverage that supports probability calibration. Proxy
mode writes threshold indicators, never probabilities or model artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests


BACKEND_DIR = Path(__file__).resolve().parents[1]
STATIC_FILE = BACKEND_DIR / "app" / "data" / "kerala_district_static.json"
CACHE_DIR = BACKEND_DIR / "data" / "cache"
PROXY_DIR = BACKEND_DIR / "data" / "proxy_datasets"
EVENT_DIR = BACKEND_DIR / "data" / "historical_events"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def load_districts() -> list[dict[str, Any]]:
    return json.loads(STATIC_FILE.read_text(encoding="utf-8"))["districts"]


def fetch_daily(district: dict[str, Any], start: date, end: date) -> list[dict[str, Any]]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{district['district_id']}_{start}_{end}_daily.csv"
    if path.exists():
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    response = requests.get(ARCHIVE_URL, params={
        "latitude": district["latitude"], "longitude": district["longitude"],
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "daily": "precipitation_sum,temperature_2m_max,et0_fao_evapotranspiration,soil_moisture_0_to_7cm_mean",
        "timezone": "Asia/Kolkata",
    }, timeout=60)
    response.raise_for_status()
    body = response.json()
    if body.get("error") or not body.get("daily", {}).get("time"):
        raise RuntimeError(body.get("reason", "Archive returned no daily observations"))
    daily = body["daily"]
    fields = [key for key in daily if key != "time"]
    rows = [{"date": stamp, **{field: daily[field][i] for field in fields}}
            for i, stamp in enumerate(daily["time"])]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", *fields])
        writer.writeheader()
        writer.writerows(rows)
    time.sleep(0.25)
    return rows


def write_proxy_dataset(district: dict[str, Any], rows: list[dict[str, Any]]) -> Path:
    """Write IMD rainfall category indicators; these are not hazard labels."""
    PROXY_DIR.mkdir(parents=True, exist_ok=True)
    path = PROXY_DIR / f"{district['district_id']}_rainfall_proxy.csv"
    fields = ["district_id", "district_name", "date", "precipitation_sum", "temperature_2m_max",
              "et0_fao_evapotranspiration", "soil_moisture_0_to_7cm_mean", "imd_heavy_rain_day_proxy",
              "imd_very_heavy_rain_day_proxy", "imd_extremely_heavy_rain_day_proxy", "provenance"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            raw = row.get("precipitation_sum")
            rain = float(raw) if raw not in (None, "") else None
            writer.writerow({
                "district_id": district["district_id"], "district_name": district["district_name"],
                "date": row["date"], "precipitation_sum": raw,
                "temperature_2m_max": row.get("temperature_2m_max"),
                "et0_fao_evapotranspiration": row.get("et0_fao_evapotranspiration"),
                "soil_moisture_0_to_7cm_mean": row.get("soil_moisture_0_to_7cm_mean"),
                "imd_heavy_rain_day_proxy": int(rain is not None and rain >= 64.5),
                "imd_very_heavy_rain_day_proxy": int(rain is not None and rain >= 115.6),
                "imd_extremely_heavy_rain_day_proxy": int(rain is not None and rain >= 204.5),
                "provenance": "METEOROLOGICAL_PROXY_NOT_HAZARD_EVENT",
            })
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("historical", "proxy"), required=True)
    parser.add_argument("--years", type=int, default=5)
    args = parser.parse_args()
    if args.years < 2 or args.years > 30:
        parser.error("--years must be between 2 and 30")
    end = date.today() - timedelta(days=6)  # archive data can be delayed
    start = end - timedelta(days=365 * args.years)
    districts = load_districts()
    if args.mode == "historical":
        required = [EVENT_DIR / f"{hazard}_events.csv" for hazard in ("flood", "landslide", "drought")]
        missing = [path.name for path in required if not path.exists()]
        if missing:
            print("Cannot train VERIFIED_HISTORICAL models. Missing event tables:", ", ".join(missing), file=sys.stderr)
            print("Provide documented event and non-event coverage with district, date, event label, source, and coverage window.", file=sys.stderr)
            print("No production artifacts were written.", file=sys.stderr)
            return 2
        print("Event files found, but training is blocked until label coverage and negative-sample design are reviewed.", file=sys.stderr)
        print("No production artifacts were written.", file=sys.stderr)
        return 2

    print("WARNING: proxy mode creates IMD rainfall-category indicators, not flood/landslide/drought event labels or risk probabilities.")
    for district in districts:
        rows = fetch_daily(district, start, end)
        output = write_proxy_dataset(district, rows)
        print(f"Prepared {len(rows)} daily rows: {output}")
    registry = {
        "status": "DATASET_ONLY_NO_PRODUCTION_MODELS",
        "provenance": "METEOROLOGICAL_PROXY",
        "threshold_source": "IMD Heavy Rainfall Warning Services SOP, Table 5.2",
        "threshold_source_url": "https://mausam.imd.gov.in/imd_latest/contents/pdf/forecasting_sop.pdf",
        "training_window": {"start": start.isoformat(), "end": end.isoformat()},
        "district_count": len(districts),
        "validation": "Not run: proxy indicators are not observed hazard event labels.",
        "probabilities_calibrated": False,
        "production_artifacts_written": False,
    }
    PROXY_DIR.mkdir(parents=True, exist_ok=True)
    (PROXY_DIR / "proxy_dataset_manifest.json").write_text(json.dumps(registry, indent=2), encoding="utf-8")
    print("Dataset manifest written. No model or calibrated probability was produced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
