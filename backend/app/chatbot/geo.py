"""Small geo helpers (no external dependency)."""
from math import radians, sin, cos, asin, sqrt


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    p1, p2 = radians(lat1), radians(lat2)
    dphi, dl = p2 - p1, radians(lng2 - lng1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(a))


def in_kerala_box(lat, lng) -> bool:
    return 8.0 <= lat <= 12.9 and 74.7 <= lng <= 77.6


def map_link(lat, lng) -> str:
    return f"https://www.google.com/maps?q={lat:.5f},{lng:.5f}"
