"""Read static district susceptibility layers for the experimental preparedness index.

These are coarse context layers, not event labels and not probabilities. Source
quality and spatial limitations travel with every district score.
"""

import csv
from functools import lru_cache
from pathlib import Path
from statistics import median
from typing import Any


DATA_DIR = Path(__file__).resolve().parents[1] / "ml_model" / "susceptibility"
DROUGHT_CLASS_SCORE = {
    "no drought": 0.0,
    "slight drought": 33.3,
    "moderate drought": 66.7,
    "severe drought": 100.0,
}


def _district_key(value: str) -> str:
    key = "".join(char for char in str(value or "").casefold() if char.isalpha())
    return {
        "kasargod": "kasaragod",
        "kozhekkode": "kozhikode",
        "kozhikkode": "kozhikode",
        "trivandrum": "thiruvananthapuram",
        "tvm": "thiruvananthapuram",
        "trichur": "thrissur",
        "eranakulam": "ernakulam",
        "wynad": "wayanad",
    }.get(key, key)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _number(row: dict[str, str], key: str) -> float | None:
    try:
        value = float(row.get(key, ""))
    except (TypeError, ValueError):
        return None
    return value if value == value and abs(value) != float("inf") else None


@lru_cache(maxsize=1)
def _load_layers() -> dict[str, dict[str, dict[str, Any]]]:
    result: dict[str, dict[str, dict[str, Any]]] = {name: {} for name in ("flood", "landslide", "drought")}

    try:
        rows = _read_csv(DATA_DIR / "flood_taluk_susceptibility.csv")
        district_areas: dict[str, float] = {}
        for row in rows:
            district = _district_key(row.get("district", ""))
            area = _number(row, "floodplain_area_sq_km")
            if district and area is not None:
                district_areas[district] = district_areas.get(district, 0.0) + max(0.0, area)
        sorted_areas = sorted(district_areas.values())
        for district, area in district_areas.items():
            less = sum(value < area for value in sorted_areas)
            equal = sum(value == area for value in sorted_areas)
            percentile = 100.0 * (less + 0.5 * equal) / len(sorted_areas) if sorted_areas else None
            result["flood"][district] = {
                "score": round(percentile, 1) if percentile is not None else None,
                "source_rows": sum(_district_key(row.get("district", "")) == district for row in rows),
                "quality": "LOW",
                "basis": "District percentile of reported taluk floodplain area; source taluk assignment is approximate and all rows are unverified.",
                "source": "Flood_Susceptibility.csv",
            }
    except OSError:
        pass

    try:
        rows = _read_csv(DATA_DIR / "landslide_taluk_susceptibility.csv")
        grouped: dict[str, list[float]] = {}
        for row in rows:
            district = _district_key(row.get("district", ""))
            score = _number(row, "ls_index")
            if district and score is not None and row.get("class", "").strip().casefold() != "not mapped":
                grouped.setdefault(district, []).append(max(0.0, min(100.0, score)))
        for district, scores in grouped.items():
            result["landslide"][district] = {
                "score": round(median(scores), 1),
                "source_rows": len(scores),
                "quality": "LOW",
                "basis": "Source LS_INDEX at district scale; district class is repeated across taluks and six source rows are not mapped.",
                "source": "landslide_susceptibility.csv",
            }
    except OSError:
        pass

    try:
        rows = _read_csv(DATA_DIR / "drought_village_susceptibility.csv")
        grouped: dict[str, list[float]] = {}
        for row in rows:
            district = _district_key(row.get("district", ""))
            score = DROUGHT_CLASS_SCORE.get(row.get("class", "").strip().casefold())
            if district and score is not None:
                grouped.setdefault(district, []).append(score)
        for district, scores in grouped.items():
            result["drought"][district] = {
                "score": round(sum(scores) / len(scores), 1),
                "source_rows": len(scores),
                "quality": "LOW",
                "basis": "Mean ordinal village class (No=0, Slight=33.3, Moderate=66.7, Severe=100); source date and method were not supplied.",
                "source": "drought_susceptibility.csv.xlsx",
            }
    except OSError:
        pass

    return result


def get_historical_susceptibility(hazard: str, district: str) -> dict[str, Any]:
    """Return one static index with clear provenance, or an explicit unavailable result."""
    record = _load_layers().get(hazard, {}).get(_district_key(district))
    if record is None:
        return {
            "score": None,
            "quality": "UNAVAILABLE",
            "source_rows": 0,
            "basis": "No usable historical susceptibility value is available for this district.",
            "source": None,
            "score_semantics": "SUSCEPTIBILITY_INDEX_NOT_PROBABILITY",
        }
    return {**record, "score_semantics": "SUSCEPTIBILITY_INDEX_NOT_PROBABILITY"}
