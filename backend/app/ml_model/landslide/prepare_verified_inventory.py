"""Download and normalize the published 2018 Kerala landslide inventory.

This produces a separate event inventory for spatial validation. The source
does not provide point-level event dates, so the result must not be used as a
72-hour warning target.
"""

import csv
import json
import math
import struct
from pathlib import Path

import requests


DATASET_DOI = "doi:10.17026/dans-x6c-y7x2"
DATASET_API = "https://phys-techsciences.datastations.nl/api/datasets/:persistentId/"
OUTPUT_PATH = Path(__file__).resolve().parent / "validation" / "landslide_inventory_2018.csv"
LAC_COORDS_PATH = Path(__file__).resolve().parents[4] / "frontend" / "src" / "lac_locations.json"


def _read_dbf(content: bytes) -> list[dict[str, str]]:
    row_count = struct.unpack("<I", content[4:8])[0]
    header_length, record_length = struct.unpack("<HH", content[8:12])
    fields = []
    for offset in range(32, header_length - 1, 32):
        descriptor = content[offset:offset + 32]
        if descriptor[0] == 0x0D:
            break
        name = descriptor[:11].split(b"\0", 1)[0].decode("ascii")
        fields.append((name, descriptor[16]))

    records = []
    for index in range(row_count):
        start = header_length + index * record_length
        record = content[start:start + record_length]
        if not record or record[0:1] == b"*":
            continue
        cursor = 1
        values = {}
        for name, width in fields:
            values[name] = record[cursor:cursor + width].decode("utf-8", "replace").strip()
            cursor += width
        records.append(values)
    return records


def _number(value: str) -> float | None:
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _normalize_name(value: str) -> str:
    return " ".join(value.strip().casefold().replace("district", "").split())


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius_km * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _nearest_constituency(
    lat: float,
    lon: float,
    source_district: str,
    constituencies: list[dict],
) -> tuple[str, str, float, bool]:
    aliases = {
        "alleppey": "alappuzha",
        "kasargod": "kasaragod",
        "pathanamthita": "pathanamthitta",
        "trivandrum": "thiruvananthapuram",
        "eranakulam": "ernakulam",
        "trichur": "thrissur",
        "wynad": "wayanad",
    }
    normalized_source = aliases.get(_normalize_name(source_district), _normalize_name(source_district))
    district_candidates = []
    for item in constituencies:
        normalized_district = aliases.get(_normalize_name(item.get("district", "")), _normalize_name(item.get("district", "")))
        if normalized_district == normalized_source:
            district_candidates.append(item)
    candidates = district_candidates or constituencies
    nearest = min(
        candidates,
        key=lambda item: _distance_km(lat, lon, item["latitude"], item["longitude"]),
    )
    return (
        nearest["lac_code"],
        nearest["lac_name"],
        _distance_km(lat, lon, nearest["latitude"], nearest["longitude"]),
        bool(district_candidates),
    )


def main() -> None:
    response = requests.get(DATASET_API, params={"persistentId": DATASET_DOI}, timeout=30)
    response.raise_for_status()
    dataset = response.json()["data"]
    files = dataset["latestVersion"]["files"]
    dbf_entry = next(
        entry for entry in files
        if entry["dataFile"]["filename"].casefold().endswith(".dbf")
    )
    dbf_id = dbf_entry["dataFile"]["id"]

    download = requests.get(
        f"https://phys-techsciences.datastations.nl/api/access/datafile/{dbf_id}",
        timeout=90,
    )
    download.raise_for_status()
    source_rows = _read_dbf(download.content)

    with LAC_COORDS_PATH.open(encoding="utf-8") as source:
        constituencies = json.load(source)["constituencies"]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "source_record_id", "source_inventory_no", "event_year", "event_period", "event_date",
        "district", "longitude", "latitude", "landslide_type", "length_m",
        "width_m", "area_m2", "building_impact_count", "road_impact",
        "agriculture_impact_landcover", "land_use_2010", "land_use_2018",
        "source_nrsc", "source_gsi", "source_new_visual_mapping",
        "source_slope_class", "source_raster_value", "approx_lac_code",
        "approx_lac_name", "nearest_lac_centroid_km", "lac_district_matches",
        "lac_assignment_method", "label", "source_doi",
    ]

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        normalized_record_id = 0
        for row in source_rows:
            lon = _number(row.get("POINT_X", ""))
            lat = _number(row.get("POINT_Y", ""))
            if lon is None or lat is None or not (74 <= lon <= 78 and 8 <= lat <= 13):
                continue
            lac_code, lac_name, centroid_distance, district_has_candidates = _nearest_constituency(
                lat, lon, row.get("District", ""), constituencies
            )
            lac = next(item for item in constituencies if item["lac_code"] == lac_code)
            source_district = _normalize_name(row.get("District", ""))
            lac_district = _normalize_name(lac.get("district", ""))
            aliases = {
                "alleppey": "alappuzha",
                "kasargod": "kasaragod",
                "pathanamthita": "pathanamthitta",
                "trivandrum": "thiruvananthapuram",
                "eranakulam": "ernakulam",
                "trichur": "thrissur",
                "wynad": "wayanad",
            }
            source_district = aliases.get(source_district, source_district)
            lac_district = aliases.get(lac_district, lac_district)
            normalized_record_id += 1
            writer.writerow({
                "source_record_id": normalized_record_id,
                "source_inventory_no": row.get("No", ""),
                "event_year": 2018,
                "event_period": "2018 monsoon; source does not provide point-level dates",
                "event_date": "",
                "district": row.get("District", ""),
                "longitude": lon,
                "latitude": lat,
                "landslide_type": row.get("Type_of_sl", ""),
                "length_m": row.get("Length", ""),
                "width_m": row.get("Width", ""),
                "area_m2": row.get("Area", ""),
                "building_impact_count": row.get("Building_I", ""),
                "road_impact": row.get("Road_impac", ""),
                "agriculture_impact_landcover": row.get("Impact_Agr", ""),
                "land_use_2010": row.get("LU_2010", ""),
                "land_use_2018": row.get("LU_2018", ""),
                "source_nrsc": row.get("NRSC", ""),
                "source_gsi": row.get("GSI", ""),
                "source_new_visual_mapping": row.get("New", ""),
                "source_slope_class": row.get("Reclass_Sl", ""),
                "source_raster_value": row.get("RASTERVALU", ""),
                "approx_lac_code": lac_code,
                "approx_lac_name": lac_name,
                "nearest_lac_centroid_km": round(centroid_distance, 3),
                "lac_district_matches": source_district == lac_district,
                "lac_assignment_method": (
                    "nearest constituency centroid within source district; approximate until polygon boundaries are sourced"
                    if district_has_candidates else
                    "nearest constituency centroid statewide; no matching district boundary candidate available"
                ),
                "label": 1,
                "source_doi": DATASET_DOI,
            })

    print(f"Wrote {OUTPUT_PATH} from {len(source_rows)} source records")


if __name__ == "__main__":
    main()
