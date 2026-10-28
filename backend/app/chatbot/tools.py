"""Agent tools: what Thunai can look up, each backed by a Kaavalal module.

EDIT THE `SCHEMA` MAPPING below to match your real MySQL tables/columns. It is the only place
you need to change. If a table is missing or a query fails, the tool says the data is
unavailable (it never invents anything).

Reference data from KSDMA files (see import_ksdma.py): relief camps, water kiosks, hospitals, taluk EOCs.

Module map:  alerts -> 16 | shelters -> 13,14,15 | incidents -> 6,7,8 (own reports only)
             risk -> 17,18 | weather -> 19 | history -> 21 | guidelines (RAG) -> 20,22
"""
from sqlalchemy import text
from langchain_core.tools import tool
from . import config
from .config import EMERGENCY_CONTACTS, normalize_district
from .rag import search as rag_search
import difflib
import re
from .request_context import current_user_id, current_location
from .geo import haversine_km, map_link


# ---- adjust to your project --------------------------------------------
def _session():
    from app.core.database import SessionLocal
    return SessionLocal()


SCHEMA = {
    # Module 16: Disaster Alerts and Notifications
    "alerts": {
        "table": "alerts",
        "cols": "title, severity, district, message, published_at",
        "district": "district",
        "active_filter": "status = 'published' AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)",
        "order": "published_at DESC",
    },
    # Modules 13-15: Shelter Management / Finder / Occupancy Tracking
    "shelters": {
        "table": "shelters",
        "cols": "name, district, lac, address, building_type, capacity, occupied",
        "district": "district",
        "active_filter": "is_active = 1",
        "order": "name ASC",
    },
    # Modules 6-8: Incident Reporting / Tracking / Management (citizen sees OWN reports only)
    "incidents": {
        "table": "help_requests",
        "cols": "id, emergency_type, urgency, status, district, created_at, updated_at",
        "id_col": "id",
        "owner_col": "user_id",
        "order": "created_at DESC",
    },
    # Modules 17-18: Risk Assessment / AI-ML Risk Prediction
    "risk": {
        "table": "risk_data rd JOIN locations l ON l.id = rd.location_id",
        "cols": "l.name AS district, rd.flood_risk, rd.landslide_risk, rd.drought_risk, rd.overall_risk, rd.recorded_at",
        "district": "l.name",
        "order": "rd.recorded_at DESC",
    },
    # Module 19: Weather and Rainfall Data
    "weather": {
        "table": "rainfall_data rd JOIN locations l ON l.id = rd.location_id",
        "cols": "l.name AS district, rd.rainfall_24h, rd.rainfall_72h, rd.rainfall_7d, rd.recorded_at",
        "district": "l.name",
        "order": "rd.recorded_at DESC",
    },
    # Module 21: Historical Disaster Data
    "history": {
        "table": "historical_disasters",
        "cols": "district, disaster_type, event_date, description",
        "district": "district",
        "order": "event_date DESC",
    },
}
# -------------------------------------------------------------------------

NOT_KERALA = ("That does not look like a Kerala district. Kaavalal covers Kerala's 14 districts only. "
              "Ask the user which Kerala district they mean.")


def _rows(sql: str, params: dict):
    db = _session()
    try:
        result = db.execute(text(sql), params)
        return [dict(r._mapping) for r in result]
    finally:
        db.close()


def _by_district(key: str, district: str, limit: int, extra_where: str = ""):
    """Shared query: rows of a SCHEMA table for one Kerala district. Returns (rows|None, error|None)."""
    s = SCHEMA[key]
    canonical = normalize_district(district)
    if not canonical:
        return None, NOT_KERALA
    where = f"{s['district']} LIKE :d"
    if extra_where:
        where = f"{extra_where} AND {where}"
    try:
        rows = _rows(f"SELECT {s['cols']} FROM {s['table']} WHERE {where} "
                     f"ORDER BY {s['order']} LIMIT {int(limit)}", {"d": f"%{canonical}%"})
    except Exception as e:
        return None, f"That data is not available right now ({type(e).__name__})."
    return rows, None


@tool
def get_active_alerts(district: str = "") -> str:
    """Get currently active disaster alerts (flood, landslide, rain warnings) published in Kaavalal.
    Optionally filter by Kerala district, in English or Malayalam, e.g. 'Wayanad' or 'വയനാട്'."""
    s = SCHEMA["alerts"]
    if district:
        rows, err = _by_district("alerts", district, 5, s["active_filter"])
        if err:
            return err
    else:
        try:
            rows = _rows(f"SELECT {s['cols']} FROM {s['table']} WHERE {s['active_filter']} "
                         f"ORDER BY {s['order']} LIMIT 5", {})
        except Exception as e:
            return f"Alerts are not available right now ({type(e).__name__}). Advise the user to check the KSDMA website."
    return str(rows) if rows else "No active alerts found."


@tool
def find_shelters(district: str) -> str:
    """Find open shelters / relief camps in a Kerala district (English or Malayalam name),
    with capacity and how many places are still available. A district is required."""
    s = SCHEMA["shelters"]
    rows, err = _by_district("shelters", district, 8, s["active_filter"])
    if err:
        return err
    for r in rows:
        try:
            r["available_places"] = max(int(r["capacity"]) - int(r["occupied"]), 0)
        except Exception:
            pass
    return str(rows) if rows else f"No open shelters found in {district}."


@tool
def get_district_risk(district: str) -> str:
    """Get the latest Kaavalal risk assessment (flood, landslide, drought) for a Kerala district.
    These are model/assessment outputs, not official forecasts. Mention the assessment time."""
    rows, err = _by_district("risk", district, 6)
    if err:
        return err
    return str(rows) if rows else "No risk assessment is available for that district yet."


@tool
def get_rainfall(district: str) -> str:
    """Get the latest recorded rainfall for a Kerala district."""
    rows, err = _by_district("weather", district, 5)
    if err:
        return err
    return str(rows) if rows else "No recent rainfall data is available for that district."


@tool
def get_past_disasters(district: str) -> str:
    """Get past recorded disasters (floods, landslides etc.) for a Kerala district."""
    rows, err = _by_district("history", district, 5)
    if err:
        return err
    return str(rows) if rows else "No historical disaster records found for that district."


@tool
def get_my_incident_status(incident_id: str = "") -> str:
    """Check the status of the logged-in user's OWN incident reports. Give an incident ID for one
    report, or leave empty to list their latest reports. Works only for logged-in users."""
    uid = current_user_id.get()
    if uid is None:
        return "The user is not logged in. Ask them to log in to Kaavalal to see their incident reports."
    s = SCHEMA["incidents"]
    where, params = f"{s['owner_col']} = :u", {"u": uid}
    if incident_id.strip():
        if not incident_id.strip().isdigit():
            return "The incident ID must be a number. Ask the user for it."
        where += f" AND {s['id_col']} = :i"
        params["i"] = int(incident_id)
    try:
        rows = _rows(f"SELECT {s['cols']} FROM {s['table']} WHERE {where} "
                     f"ORDER BY {s['order']} LIMIT 5", params)
    except Exception as e:
        return f"Incident status is not available right now ({type(e).__name__})."
    return str(rows) if rows else "No matching incident reports found for this user."


# ===================== KSDMA reference-data tools (tables filled by import_ksdma.py) =====================
CAMP_NOTE = ("These camps come from KSDMA's monsoon camp list. Being listed does NOT mean a camp is open now: "
             "tell the user to confirm with the district control room (1077) or taluk emergency centre.")
HOSPITAL_NOTE = ("Hospital figures are from a June 2020 KSDMA survey (COVID-era). Beds and ICU availability today may differ: "
                 "advise calling the hospital first, and 108 / 112 in an emergency.")


def _db_query(fn):
    db = _session()
    try:
        return fn(db)
    finally:
        db.close()


def _place_tokens(place: str):
    """Words of `place` that are not district names (used to match panchayat / village / camp names)."""
    words = re.findall(r"[A-Za-z]{3,}|[\u0D00-\u0D7F]+", place or "")
    stop = {"the", "near", "nearest", "camp", "camps", "relief", "shelter", "shelters", "in", "at", "for", "kiosk",
            "kiosks", "water", "hospital", "hospitals", "and", "any", "district", "taluk", "panchayat", "village"}
    out = []
    for w in words:
        if w.lower() in stop or normalize_district(w):
            continue
        out.append(w)
    return out


def _camp_row(c, user_loc=None):
    d = {"name": c.name, "district": c.district, "local_body": c.lsg, "village": c.village,
         "capacity": c.capacity if c.capacity is not None else "not recorded",
         "toilets": c.toilets or "unknown", "disabled_friendly": c.disabled_friendly or "unknown"}
    if c.lat is not None and c.lng is not None:
        d["map"] = map_link(c.lat, c.lng)
        if user_loc:
            d["distance_km"] = round(haversine_km(user_loc[0], user_loc[1], c.lat, c.lng), 1)
    return d


@tool
def find_relief_camps(place: str = "", near_me: bool = False) -> str:
    """Find relief camps / shelters from KSDMA's monsoon camp list. `place` can be a Kerala district, panchayat,
    municipality, village or camp name (English or Malayalam). Set near_me=true to list the camps nearest to the
    user's shared location (only works if the user shared their location)."""
    if not config.KSDMA_DATA_READY:
        return "KSDMA camp records have not been imported into this Kaavalal database yet. Do not infer that no camps exist; call the district emergency control room at 1077."
    from .ref_models import RefCamp
    loc = current_location.get()

    def run(db):
        if near_me:
            if not loc:
                return "The user has not shared their location. Ask them to press 'Use my location', or tell you a district or panchayat."
            lat, lng = loc
            for box in (0.15, 0.4, 1.0):
                cands = (db.query(RefCamp).filter(RefCamp.lat.isnot(None), RefCamp.lat.between(lat - box, lat + box),
                                                  RefCamp.lng.between(lng - box, lng + box)).all())
                if len(cands) >= 5:
                    break
            cands.sort(key=lambda c: haversine_km(lat, lng, c.lat, c.lng))
            if not cands:
                return "No camps with map coordinates were found near that location."
            return CAMP_NOTE + "\nNearest camps: " + str([_camp_row(c, loc) for c in cands[:5]])
        district = normalize_district(place)
        tokens = _place_tokens(place)
        q = db.query(RefCamp)
        if district:
            q = q.filter(RefCamp.district == district)
        if tokens:
            from sqlalchemy import or_
            conds = []
            for t in tokens:
                like = f"%{t}%"
                conds += [RefCamp.lsg.ilike(like), RefCamp.village.ilike(like), RefCamp.name.ilike(like)]
            matched = q.filter(or_(*conds)).order_by(RefCamp.capacity.desc()).limit(8).all()
            if matched:
                return CAMP_NOTE + "\nCamps matching '" + place + "': " + str([_camp_row(c) for c in matched])
            if not district:
                return f"No camps matched '{place}'. Ask the user for their district or panchayat name."
        if not district:
            return "A Kerala district, panchayat or village name is needed, or the user can share their location."
        total = q.count()
        top = q.order_by(RefCamp.capacity.desc()).limit(6).all()
        extra = f" (no match for '{' '.join(tokens)}', showing the largest camps in the district)" if tokens else ""
        return (CAMP_NOTE + f"\n{district} has {total} listed camps{extra}. Largest: " + str([_camp_row(c) for c in top])
                + "\nSuggest the user give a panchayat/village name or share their location for nearby camps.")
    try:
        return _db_query(run)
    except Exception as e:
        return f"The relief camp list is not available right now ({type(e).__name__}). Give the district control room number 1077."


@tool
def find_water_kiosks(place: str = "", near_me: bool = False) -> str:
    """Find emergency drinking-water kiosk locations. `place` can be a Kerala district or taluk name. Set near_me=true
    for the kiosks nearest to the user's shared location. Kiosks have map coordinates only (no names)."""
    if not config.KSDMA_DATA_READY:
        return "KSDMA water-kiosk records have not been imported into this Kaavalal database yet. Do not infer that no kiosks exist."
    from .ref_models import RefWaterKiosk
    loc = current_location.get()

    def run(db):
        if near_me:
            if not loc:
                return "The user has not shared their location. Ask them to press 'Use my location', or give a district or taluk."
            lat, lng = loc
            for box in (0.1, 0.3, 1.0):
                cands = db.query(RefWaterKiosk).filter(RefWaterKiosk.lat.between(lat - box, lat + box),
                                                       RefWaterKiosk.lng.between(lng - box, lng + box)).all()
                if len(cands) >= 3:
                    break
            cands.sort(key=lambda k: haversine_km(lat, lng, k.lat, k.lng))
            if not cands:
                return "No water kiosk locations were found near that location."
            return "Nearest water kiosks: " + str([{"taluk": k.taluk, "district": k.district,
                                                    "distance_km": round(haversine_km(lat, lng, k.lat, k.lng), 1),
                                                    "map": map_link(k.lat, k.lng)} for k in cands[:5]])
        district = normalize_district(place)
        if not district:
            return NOT_KERALA
        taluks = [r[0] for r in db.query(RefWaterKiosk.taluk).filter(RefWaterKiosk.district == district).distinct().all()]
        tokens = _place_tokens(place)
        match = difflib.get_close_matches(" ".join(tokens).title(), taluks, n=1, cutoff=0.6) if tokens else []
        q = db.query(RefWaterKiosk).filter(RefWaterKiosk.district == district)
        if match:
            q = q.filter(RefWaterKiosk.taluk == match[0])
            return f"{q.count()} water kiosk locations are listed in {match[0]} taluk, {district}. Ask the user to share their location for the nearest ones."
        counts = {t: db.query(RefWaterKiosk).filter(RefWaterKiosk.district == district, RefWaterKiosk.taluk == t).count() for t in taluks}
        return f"{q.count()} water kiosk locations are listed in {district} district, by taluk: {counts}. Ask for a taluk or the user's location for specifics."
    try:
        return _db_query(run)
    except Exception as e:
        return f"Water kiosk data is not available right now ({type(e).__name__})."


@tool
def find_hospitals(district: str, kind: str = "") -> str:
    """List hospitals in a Kerala district from the KSDMA health survey (government and private), with bed, ICU and
    ventilator counts. kind can be 'government' or 'private' (optional)."""
    if not config.KSDMA_DATA_READY:
        return "KSDMA hospital records have not been imported into this Kaavalal database yet. Call 108 or 112 in an emergency."
    from .ref_models import RefHospital
    canonical = normalize_district(district)
    if not canonical:
        return NOT_KERALA

    def run(db):
        q = db.query(RefHospital).filter(RefHospital.district == canonical)
        if kind.lower() in ("government", "private"):
            q = q.filter(RefHospital.kind == kind.lower())
        rows = q.all()
        if not rows:
            return f"No hospital records found for {canonical}."
        rows.sort(key=lambda h: ((h.icu_beds or 0), (h.total_beds or h.ward_beds or 0)), reverse=True)
        out = [{"name": h.name, "type": h.kind, "beds": h.total_beds if h.total_beds is not None else h.ward_beds,
                "private_rooms": h.rooms, "icu_beds": h.icu_beds, "ventilators": h.ventilators,
                "ambulances": h.ambulances} for h in rows[:8]]
        return HOSPITAL_NOTE + f"\n{len(rows)} hospitals listed in {canonical}; largest by ICU/beds: " + str(out)
    try:
        return _db_query(run)
    except Exception as e:
        return f"Hospital data is not available right now ({type(e).__name__})."


@tool
def get_taluk_emergency_contacts(district: str, taluk: str = "") -> str:
    """Get the 24x7 Taluk Emergency Operations Centre (TEOC) phone numbers for a Kerala district, or for one taluk.
    Use this when the user needs the local office to confirm a camp, report a problem or ask for help."""
    if not config.KSDMA_DATA_READY:
        return "KSDMA taluk contact records have not been imported into this Kaavalal database yet. Use the district control room number 1077."
    from .ref_models import RefTalukEOC
    canonical = normalize_district(district)
    if not canonical:
        return NOT_KERALA

    def run(db):
        rows = db.query(RefTalukEOC).filter(RefTalukEOC.district == canonical).all()
        if not rows:
            return f"No taluk contacts are available for {canonical}. Give the district control room number 1077."
        names = [r.taluk for r in rows]
        pick = difflib.get_close_matches(taluk.title(), names, n=1, cutoff=0.55) if taluk.strip() else []
        sel = [r for r in rows if r.taluk == pick[0]] if pick else rows
        out = [{"taluk": r.taluk, "phones": r.phones.split(",") if r.phones else "no verified number"} for r in sel]
        note = "Source: KSDMA Taluk Directory. Confirm numbers are current; district control room 1077 is always available."
        return note + "\n" + str(out)
    try:
        return _db_query(run)
    except Exception as e:
        return f"Taluk contact data is not available right now ({type(e).__name__}). Use district control room 1077."


@tool
def search_guidelines(query: str) -> str:
    """Search the disaster-safety knowledge base (flood, landslide, lightning,
    first aid, evacuation, preparedness) for official guidance."""
    docs = rag_search(query, k=4)
    if not docs:
        return "No relevant guidance found."
    return "\n\n---\n\n".join(f"[{d.metadata.get('source')}]\n{d.page_content}" for d in docs)


@tool
def get_emergency_contacts() -> str:
    """Get official emergency helpline numbers."""
    return "\n".join(f"{k}: {v}" for k, v in EMERGENCY_CONTACTS.items())


ALL_TOOLS = [get_active_alerts, find_shelters, find_relief_camps, find_water_kiosks, find_hospitals,
             get_taluk_emergency_contacts, get_district_risk, get_rainfall, get_past_disasters,
             get_my_incident_status, search_guidelines, get_emergency_contacts]
