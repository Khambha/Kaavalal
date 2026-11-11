"""Prepare one-time, review-only Nominatim coordinate suggestions for auditoriums.

This script is deliberately single-threaded, waits at least 1.1 seconds between
uncached requests, and caches each query so reruns do not repeat lookups.
"""
import argparse
import csv
import json
import math
import re
import time
from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[2]
GEOJSON = ROOT / "frontend" / "public" / "Data" / "Kerala_districts.geojson"
DATA_DIR = ROOT / "backend" / "app" / "data"
CACHE_PATH = DATA_DIR / "auditorium_geocode_cache.json"
OUTPUT_PATH = DATA_DIR / "auditorium_geocoding_suggestions_review.csv"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "KaavalalShelterDataReview/1.0 (one-time user-authorized facility geocoding; Kaavalal project)"
ATTRIBUTION = "© OpenStreetMap contributors (ODbL)"
GENERIC_NAME_WORDS = {"auditorium", "convention", "centre", "center", "hall", "mahal", "mandapam", "ground", "grounds", "the", "and"}
LOCATION_STOPWORDS = GENERIC_NAME_WORDS | {"road", "rd", "street", "st", "near", "opp", "opposite", "junction", "kerala", "india", "district", "taluk", "panchayat", "municipality", "village", "post", "po", "p", "o"}


def clean(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize(value):
    return re.sub(r"[^a-z0-9]", "", clean(value).casefold())


def words(value):
    return {word for word in re.findall(r"[a-z0-9]+", clean(value).casefold()) if word not in GENERIC_NAME_WORDS}


def point_in_ring(longitude, latitude, ring):
    inside = False
    previous = ring[-1]
    for current in ring:
        x1, y1 = float(previous[0]), float(previous[1])
        x2, y2 = float(current[0]), float(current[1])
        if (y1 > latitude) != (y2 > latitude):
            intersection = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
            if longitude < intersection:
                inside = not inside
        previous = current
    return inside


def point_in_district(longitude, latitude, district, features):
    district_key = normalize(district.removesuffix(" district"))
    feature = next((item for item in features if normalize(item.get("properties", {}).get("name", "").removesuffix(" district")) == district_key), None)
    if not feature:
        return False
    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinates") or []
    polygons = [coordinates] if geometry.get("type") == "Polygon" else coordinates if geometry.get("type") == "MultiPolygon" else []
    return any(
        point_in_ring(longitude, latitude, polygon[0])
        and not any(point_in_ring(longitude, latitude, hole) for hole in polygon[1:])
        for polygon in polygons
    )


def queries_for(row):
    primary = ", ".join(part for part in [row["name"], row["district"], "Kerala", "India"] if part)
    fallback = ", ".join(part for part in [row["address"], row["lsg"], row["district"], "Kerala", "India"] if part)
    return [primary] + ([fallback] if fallback and fallback != primary else [])


def fetch(query, cache, session):
    if query in cache:
        return cache[query]
    response = session.get(
        NOMINATIM,
        params={"q": query, "format": "jsonv2", "addressdetails": 1, "limit": 5, "countrycodes": "in"},
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en"},
        timeout=30,
    )
    if response.status_code == 429:
        raise RuntimeError(f"Nominatim returned HTTP 429; stopping to respect its usage policy. Retry-After={response.headers.get('Retry-After', 'unspecified')}")
    response.raise_for_status()
    results = response.json()
    cache[query] = results
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    time.sleep(1.1)
    return results


def suggest(row, results, features):
    ranked = []
    wanted = words(row["name"])
    for result in results:
        try:
            latitude, longitude = float(result["lat"]), float(result["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        display = clean(result.get("display_name"))
        result_name = clean(result.get("name"))
        display_words = words(display)
        name_words = words(result_name)
        location_words = words(f"{row['address']} {row['lsg']}") - LOCATION_STOPWORDS
        wanted_identity = wanted - location_words
        overlap = wanted_identity & name_words
        location_overlap = location_words & display_words
        exact = bool(wanted_identity and normalize(row["name"]) in normalize(result_name))
        enough_name = exact or len(overlap) >= 2 or (len(wanted_identity) == 1 and bool(overlap))
        in_district = point_in_district(longitude, latitude, row["district"], features)
        score = (100 if exact else 40 * len(overlap)) + (25 if in_district else -60)
        score += min(25, len(location_overlap) * 8)
        score += min(10, int(float(result.get("importance", 0) or 0) * 10))
        ranked.append((score, result, latitude, longitude, in_district, enough_name, len(overlap), bool(location_overlap)))
    if not ranked:
        return {
            "suggested_latitude": "", "suggested_longitude": "", "geocode_confidence": "no_match",
            "geocode_match_type": "none", "geocode_result_name": "", "geocode_result_address": "",
            "geocode_result_class": "", "geocode_result_type": "", "geocode_result_osm_url": "",
            "geocode_note": "No matching OSM search result; obtain a pin from the operator or local authority.",
        }
    score, result, latitude, longitude, in_district, enough_name, overlap, location_match = max(ranked, key=lambda item: item[0])
    if not in_district:
        confidence, match_type = "low", "outside_listed_district"
        note = "Search result falls outside the workbook-listed district boundary. Do not use without correction."
    elif enough_name:
        confidence, match_type = ("high" if location_match else "medium"), "facility_name_match"
        note = "Facility name and location context match the workbook; still verify the exact pin with the operator." if location_match else "Facility name matches within the listed district, but address/locality context did not also match; verify carefully."
    else:
        confidence, match_type = "low", "address_or_locality_only"
        note = "Result matches location context but not the facility name; likely a locality/address point, not a verified venue pin."
    osm_type = clean(result.get("osm_type"))
    osm_id = clean(result.get("osm_id"))
    osm_url = f"https://www.openstreetmap.org/{osm_type}/{osm_id}" if osm_type and osm_id else ""
    return {
        "suggested_latitude": latitude, "suggested_longitude": longitude,
        "geocode_confidence": confidence, "geocode_match_type": match_type,
        "geocode_result_name": clean(result.get("name")), "geocode_result_address": clean(result.get("display_name")),
        "geocode_result_class": clean(result.get("class")), "geocode_result_type": clean(result.get("type")),
        "geocode_result_osm_url": osm_url, "geocode_note": note,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to Auditorium-List.xlsx")
    parser.add_argument("--limit", type=int, default=0, help="Optional pilot limit; zero processes all records")
    args = parser.parse_args()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    features = json.loads(GEOJSON.read_text(encoding="utf-8"))["features"]
    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}
    workbook = pd.ExcelFile(args.input)
    rows = []
    for sheet in workbook.sheet_names:
        df = pd.read_excel(args.input, sheet_name=sheet)
        columns = {clean(column).casefold(): column for column in df.columns}
        name_col = columns.get("name")
        if not name_col:
            continue
        for index, record in df.iterrows():
            row = {
                "source_sheet": clean(sheet), "source_row": int(index + 2),
                "name": clean(record.get(name_col)), "address": clean(record.get(columns.get("address"))),
                "district": clean(record.get(columns.get("district"))), "lsg": clean(record.get(columns.get("lsg"))),
            }
            if row["name"]:
                rows.append(row)
    rows = rows[:args.limit] if args.limit else rows
    session = requests.Session()
    output = []
    counts = {"high": 0, "medium": 0, "low": 0, "no_match": 0, "uncached_requests": 0}
    for position, row in enumerate(rows, start=1):
        try:
            query_list = queries_for(row)
            results = []
            for query in query_list:
                if query not in cache:
                    counts["uncached_requests"] += 1
                query_results = fetch(query, cache, session)
                results.extend(query_results)
                if suggest(row, results, features)["geocode_confidence"] in {"high", "medium"}:
                    break
            suggestion = suggest(row, results, features)
        except Exception as exc:
            suggestion = {
                "suggested_latitude": "", "suggested_longitude": "", "geocode_confidence": "no_match",
                "geocode_match_type": "error", "geocode_result_name": "", "geocode_result_address": "",
                "geocode_result_class": "", "geocode_result_type": "", "geocode_result_osm_url": "",
                "geocode_note": f"Lookup stopped/failed: {type(exc).__name__}: {exc}",
            }
            output.append({**row, **suggestion, "capacity": "", "capacity_status": "Needs operator confirmation", "review_status": "Pending", "geocoder_attribution": ATTRIBUTION})
            write_csv(output)
            raise
        confidence = suggestion["geocode_confidence"]
        counts[confidence] += 1
        output.append({**row, **suggestion, "capacity": "", "capacity_status": "Not provided in source; confirm safe shelter capacity with operator", "review_status": "Pending", "geocoder_attribution": ATTRIBUTION})
        if position % 25 == 0 or position == len(rows):
            write_csv(output)
            print(f"Progress {position}/{len(rows)}; high={counts['high']}, medium={counts['medium']}, low={counts['low']}, no_match={counts['no_match']}; new lookups={counts['uncached_requests']}", flush=True)
    write_csv(output)
    print(f"Wrote {len(output)} rows to {OUTPUT_PATH}", flush=True)


def write_csv(rows):
    if not rows:
        return
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
