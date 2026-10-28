"""Load the KSDMA datasets into the chatbot's reference tables.

    cd backend
    python -m app.chatbot.import_ksdma --src ./ksdma_files

Put the original files (the .xlsx and the Taluk Directory .pdf) in one folder. Files are matched by
name fragment, so the upload prefixes do not matter. Safe to re-run: tables are replaced each time.
Writes import_report.txt listing everything that was cleaned, skipped or needs a human to check.

Deliberately NOT imported (personal data, or not meant for citizens):
  - camp 'Ownership' column (free text containing individuals' names and phone numbers)
  - private hospital nodal-person names/phones, ITI principals' mobiles, boat owners' names/addresses/phones,
    Aapda Mitra volunteer list (names, DOB, blood group, mobile, email, home address)
  - dam / SEOC satellite phone numbers (inter-department use only), ERV officer contacts
"""
import argparse
import glob
import os
import re
import sys
import warnings

import pandas as pd

from .config import normalize_district

warnings.filterwarnings("ignore")

# Sheet-name abbreviations used across the KSDMA workbooks
ABBR = {
    "tvm": "Thiruvananthapuram", "trm": "Thiruvananthapuram", "klm": "Kollam",
    "pta": "Pathanamthitta", "ptn": "Pathanamthitta",
    "alp": "Alappuzha", "apa": "Alappuzha", "apz": "Alappuzha", "ala": "Alappuzha",
    "ktm": "Kottayam", "kot": "Kottayam", "ktym": "Kottayam", "idk": "Idukki",
    "ekm": "Ernakulam", "erk": "Ernakulam", "enk": "Ernakulam", "ern": "Ernakulam",
    "tsr": "Thrissur", "thr": "Thrissur", "tcr": "Thrissur",
    "pkd": "Palakkad", "plk": "Palakkad", "mlp": "Malappuram", "mpm": "Malappuram",
    "kkd": "Kozhikode", "kzk": "Kozhikode", "kzkd": "Kozhikode",
    "wyd": "Wayanad", "wynd": "Wayanad", "knr": "Kannur", "knu": "Kannur",
    "ksd": "Kasaragod", "ksg": "Kasaragod", "ksgd": "Kasaragod", "ksr": "Kasaragod",
}


def district_of(text):
    t = str(text or "").strip().lower()
    return ABBR.get(t) or normalize_district(t)


def squash(s):
    return re.sub(r"\s+", " ", str(s)).strip() if s is not None and str(s) != "nan" else ""


def in_lat(v): return v is not None and 8.0 <= v <= 12.9
def in_lng(v): return v is not None and 74.7 <= v <= 77.6


def num(v):
    try:
        f = float(str(v).strip().replace(",", ""))
        return None if f != f else f
    except Exception:
        return None


def to_int(v):
    n = num(v)
    return int(n) if n is not None else None


def find(src, fragment, ext):
    hits = [p for p in glob.glob(os.path.join(src, f"*{fragment}*{ext}"))]
    return hits[0] if hits else None


# ------------------------------------------------------------------ camps
def load_camps(path, rep):
    df = pd.read_excel(path, sheet_name=0)
    df.columns = [str(c).strip() for c in df.columns]
    rows, seen = [], set()
    stats = dict(total=len(df), no_name=0, dup=0, swapped=0, no_coords=0, bad_capacity=0, no_district=0)
    for r in df.to_dict("records"):
        name = squash(r.get("Camp"))
        district = district_of(r.get("District"))
        if not district:
            stats["no_district"] += 1
            continue
        if not name:
            stats["no_name"] += 1
            continue
        lsg, village = squash(r.get("LSG")), squash(r.get("Village"))
        key = (district, name.lower(), lsg.lower(), village.lower())
        if key in seen:
            stats["dup"] += 1
            continue
        seen.add(key)
        lat, lng = num(r.get("Y")), num(r.get("X"))
        if not (in_lat(lat) and in_lng(lng)):
            if in_lat(lng) and in_lng(lat):
                lat, lng = lng, lat
                stats["swapped"] += 1
            else:
                lat = lng = None
                stats["no_coords"] += 1
        cap_raw = r.get("Capacity")
        cap = None
        if cap_raw is not None and str(cap_raw) != "nan":
            m = re.fullmatch(r"\s*(\d+)(\.0+)?\s*,?\s*", str(cap_raw))
            if m:
                cap = int(m.group(1))
            else:
                stats["bad_capacity"] += 1

        def yn(v):
            s = squash(v).lower()
            if s == "yes": return "yes"
            if s == "no": return "no"
            n = num(v)
            return "yes" if n and n > 0 else None

        letters = sorted(set(re.findall(r"[A-D]", str(r.get("Type", "")).upper().replace("TYPE", ""))))
        rows.append(dict(district=district, name=name[:200], lsg=lsg[:120], village=village[:120],
                         lat=lat, lng=lng, capacity=cap, toilets=yn(r.get("Toilets")),
                         disabled_friendly=yn(r.get("DisabledFriendly")),
                         camp_type=",".join(letters) or None))
    rep.append(f"CAMPS: {stats['total']} source rows -> {len(rows)} imported. "
               f"Dropped: {stats['dup']} duplicates, {stats['no_name']} without a name, {stats['no_district']} without a district. "
               f"Coordinates: {stats['swapped']} lat/lng swapped and fixed, {stats['no_coords']} missing/invalid (kept, but no map/distance). "
               f"Capacity: {stats['bad_capacity']} unreadable values (e.g. '1.50, 2.50', '2hall') stored as 'not recorded'.")
    return rows


# ------------------------------------------------------------------ water kiosks
def load_kiosks(path, rep):
    rows, seen, bad = [], set(), 0
    for sheet, df in pd.read_excel(path, sheet_name=None).items():
        df.columns = [str(c).strip().upper() for c in df.columns]
        for r in df.to_dict("records"):
            a, b = num(r.get("X")), num(r.get("Y"))
            # X/Y are swapped in some sheets: decide per row by valid Kerala ranges
            if in_lat(a) and in_lng(b): lat, lng = a, b
            elif in_lat(b) and in_lng(a): lat, lng = b, a
            else:
                bad += 1
                continue
            district = district_of(r.get("DISTRICT")) or district_of(sheet)
            taluk = squash(r.get("TALUK")).title()
            if not district:
                bad += 1
                continue
            key = (round(lat, 5), round(lng, 5))
            if key in seen:
                continue
            seen.add(key)
            rows.append(dict(district=district, taluk=taluk[:60], lat=lat, lng=lng))
    rep.append(f"WATER KIOSKS: {len(rows)} imported ({bad} rows unusable). Source has coordinates only (no names/addresses); "
               f"X/Y column order differs between sheets and was fixed per row.")
    return rows


def canonicalize_taluks(kiosks, taluk_rows, rep):
    """Map misspelt kiosk taluk names (Hosthu, Housdurg, Kasargoad...) onto the official taluk names."""
    import difflib
    official = {}
    for t in taluk_rows:
        official.setdefault(t["district"], []).append(t["taluk"])
    changed, unmatched = 0, {}
    for k in kiosks:
        names = official.get(k["district"], [])
        raw = k["taluk"]
        best = difflib.get_close_matches(raw.title(), names, n=1, cutoff=0.6)
        if best:
            if best[0] != raw:
                changed += 1
            k["taluk"] = best[0]
        elif raw:
            unmatched[(k["district"], raw)] = unmatched.get((k["district"], raw), 0) + 1
    rep.append(f"  Kiosk taluk names: {changed} misspelt entries mapped onto official taluk names from the Taluk Directory.")
    if unmatched:
        rep.append("  Kiosk taluk names that match no official taluk (kept as written; please check): "
                   + "; ".join(f"{d}/{n} ({c})" for (d, n), c in sorted(unmatched.items())))


# ------------------------------------------------------------------ hospitals
def load_hospitals(gov_path, priv_path, rep):
    rows = []
    if gov_path:
        xl = pd.ExcelFile(gov_path)
        for sh in xl.sheet_names:
            district = normalize_district(sh)
            if not district or sh.lower().startswith(("summary", "state", "directions")):
                continue
            df = xl.parse(sh, header=None)
            for r in df.itertuples(index=False):
                name, beds = squash(r[1]), num(r[2])
                if not name or beds is None or re.match(r"(total|grand|section|name of)", name, re.I):
                    continue
                if "SECTION" in str(r[2]).upper():
                    continue
                rows.append(dict(district=district, name=name[:200], kind="government", total_beds=int(beds),
                                 rooms=None, ward_beds=None, icu_beds=to_int(r[3]), ventilators=to_int(r[4]),
                                 ambulances=None, data_as_of="2020-06"))
        rep.append(f"GOVERNMENT HOSPITALS: {sum(1 for r in rows if r['kind']=='government')} imported "
                   f"(survey dated 29-06-2020; COVID-specific columns ignored). Per-district counts match the workbook's district summary; "
                   f"note the workbook's own state total (405) differs from the sum of its districts.")
    n0 = len(rows)
    if priv_path:
        xl = pd.ExcelFile(priv_path)
        for sh in xl.sheet_names:
            district = district_of(sh)
            if not district:
                continue
            df = xl.parse(sh, header=None)
            started = False
            for r in df.itertuples(index=False):
                first = squash(r[0])
                if first.lower().startswith("name of the private"):
                    started = True
                    continue
                if not started or not first or first.lower().startswith("total"):
                    continue
                def n(v):  # 'NIL' means a real zero
                    return 0 if squash(v).lower() in ("nil", "nill") else to_int(v)
                rows.append(dict(district=district, name=first[:200], kind="private", total_beds=None,
                                 rooms=n(r[1]), ward_beds=n(r[3]), icu_beds=n(r[4]), ventilators=n(r[5]),
                                 ambulances=n(r[6]), data_as_of="2020-06"))
        rep.append(f"PRIVATE HOSPITALS: {len(rows) - n0} imported (survey dated 23-06-2020). Nodal-person names and phone "
                   f"numbers deliberately NOT imported (personal contacts).")
    return rows


# ------------------------------------------------------------------ taluk emergency operations centres (PDF)
_STD = re.compile(r"^0\d{3,5}$")


def _split_phones(tokens):
    """Turn the raw tokens of one taluk block into (valid_numbers, problems)."""
    valid, problems, toks, i = [], [], [t.strip(",") for t in tokens if t.strip(",")], 0
    while i < len(toks):
        t = toks[i]
        if _STD.match(t) and i + 1 < len(toks) and re.fullmatch(r"\d{5,8}", toks[i + 1]):
            digits = t + toks[i + 1]
            i += 2
            (valid if len(digits) == 11 else problems).append(digits if len(digits) == 11 else f"{digits} (unexpected length)")
        elif re.fullmatch(r"[6-9]\d{9}", t):
            valid.append(t)
            i += 1
        else:
            problems.append(t + " (incomplete: missing STD code or a digit)")
            i += 1
    seen, out = set(), []
    for v in valid:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out, problems


def load_taluk_eoc(path, rep):
    import pdfplumber
    rows, problems, district = [], [], None
    for page in pdfplumber.open(path).pages:
        words = page.extract_words()
        by_y = {}
        for w in words:
            by_y.setdefault(round(w["top"]), []).append(w)
        heads = []
        for y, ws in by_y.items():
            if any(w["text"] == "DISTRICT" for w in ws):
                name = " ".join(w["text"] for w in sorted(ws, key=lambda w: w["x0"]) if w["text"] != "DISTRICT")
                heads.append((y, name))
        heads.sort()
        head_ys = {y for y, _ in heads}
        anchors = sorted([w for w in words if re.fullmatch(r"\d{1,2}\.?", w["text"]) and w["x0"] < 200], key=lambda w: w["top"])
        phones = [w for w in words if w["x0"] >= 330 and re.fullmatch(r"[\d,]+", w["text"]) and w["top"] < 740]
        names = [w for w in words if 200 <= w["x0"] < 330 and not re.fullmatch(r"[\d.,]+", w["text"])
                 and w["text"] != "Taluk" and w["top"] > 60 and round(w["top"]) not in head_ys and "DISTRICT" not in w["text"]]
        for i, a in enumerate(anchors):
            prev_y = anchors[i - 1]["top"] if i else a["top"] - 40
            next_y = anchors[i + 1]["top"] if i + 1 < len(anchors) else a["top"] + 40
            lo = (prev_y + a["top"]) / 2 if i else a["top"] - 20
            hi = (a["top"] + next_y) / 2 if i + 1 < len(anchors) else a["top"] + 20
            for hy, _ in heads:
                if prev_y < hy < a["top"]: lo = max(lo, hy)
                if a["top"] < hy < next_y: hi = min(hi, hy)
            d = district
            for hy, hn in heads:
                if hy <= a["top"]: d = hn
            ph = sorted([p for p in phones if lo <= p["top"] < hi], key=lambda p: (round(p["top"]), p["x0"]))
            nm = sorted([n for n in names if lo <= n["top"] < hi], key=lambda n: (round(n["top"]), n["x0"]))
            taluk = " ".join(n["text"] for n in nm)
            taluk = re.sub(r"taluk$", "", taluk, flags=re.I).strip()
            valid, probs = _split_phones([p["text"] for p in ph])
            dist = normalize_district(d or "")
            if not dist or not taluk:
                problems.append(f"page {page.page_number}: could not read district/taluk for a row near y={round(a['top'])}")
                continue
            for p in probs:
                problems.append(f"{dist} / {taluk}: {p}")
            rows.append(dict(district=dist, taluk=taluk.title()[:60], phones=",".join(valid),
                             source_note="Taluk Directory PDF"))
        if heads:
            district = heads[-1][1]
    # same number listed under two taluks in the source
    owner = {}
    for r in rows:
        for p in r["phones"].split(","):
            if p:
                owner.setdefault(p, []).append(f"{r['district']}/{r['taluk']}")
    dups = {p: o for p, o in owner.items() if len(o) > 1}
    rep.append(f"TALUK EMERGENCY OPERATIONS CENTRES: {len(rows)} taluks imported; "
               f"{sum(1 for r in rows if not r['phones'])} with no verified number.")
    if dups:
        rep.append("  Numbers listed under more than one taluk in the PDF (kept as printed; please confirm): "
                   + "; ".join(f"{p} -> {', '.join(o)}" for p, o in dups.items()))
    if problems:
        rep.append("  Numbers NOT imported because they look incomplete or malformed (please check against the official source):")
        rep.extend(f"    - {p}" for p in problems)
    rep.append("  NOTE: the PDF header says 'Updated on 25th May 2025' but its page footers say '13-05-2021'. "
               "Confirm these numbers are current before launch.")
    return rows


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="folder containing the KSDMA .xlsx files and Taluk Directory .pdf")
    ap.add_argument("--report", default="import_report.txt")
    ap.add_argument("--dry-run", action="store_true", help="parse and report without touching the database")
    args = ap.parse_args()

    rep, data = [], {}
    p = find(args.src, "Monsoon-Camp", ".xlsx")
    if p: data["camps"] = load_camps(p, rep)
    else: rep.append("CAMPS: file 'Monsoon-Camp-Details...xlsx' not found - skipped")
    p = find(args.src, "Water_Kiosk", ".xlsx")
    if p: data["kiosks"] = load_kiosks(p, rep)
    else: rep.append("WATER KIOSKS: file not found - skipped")
    gov, priv = find(args.src, "Government-health", ".xlsx"), find(args.src, "Private-Hospital", ".xlsx")
    if gov or priv: data["hospitals"] = load_hospitals(gov, priv, rep)
    else: rep.append("HOSPITALS: files not found - skipped")
    p = find(args.src, "TALUK-DIRECTORY", ".pdf")
    if p: data["taluk"] = load_taluk_eoc(p, rep)
    else: rep.append("TALUK DIRECTORY: pdf not found - skipped")
    if "kiosks" in data and "taluk" in data:
        canonicalize_taluks(data["kiosks"], data["taluk"], rep)

    if not args.dry_run:
        from app.core.database import Base, SessionLocal, engine
        from .ref_models import RefCamp, RefWaterKiosk, RefHospital, RefTalukEOC
        tables = {"camps": RefCamp, "kiosks": RefWaterKiosk, "hospitals": RefHospital, "taluk": RefTalukEOC}
        Base.metadata.create_all(bind=engine, tables=[m.__table__ for m in tables.values()])
        db = SessionLocal()
        try:
            for key, model in tables.items():
                if key in data:
                    db.query(model).delete()
                    db.bulk_insert_mappings(model, data[key])
            db.commit()
        finally:
            db.close()
        rep.append("Database updated.")
    text = "\n".join(rep)
    open(args.report, "w", encoding="utf-8").write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
