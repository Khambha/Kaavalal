import csv
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]


def read_csv(relative_path):
    with (BACKEND_DIR / relative_path).open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def test_verified_2018_landslide_inventory_keeps_dates_unknown_and_lac_assignment_approximate():
    rows = read_csv("app/ml_model/landslide/validation/landslide_inventory_2018.csv")

    assert len(rows) == 4728
    assert len({row["source_record_id"] for row in rows}) == 4728
    assert all(row["event_date"] == "" for row in rows)
    assert all(row["lac_assignment_method"].startswith("nearest constituency centroid") for row in rows)
    assert all(row["source_doi"] == "doi:10.17026/dans-x6c-y7x2" for row in rows)


def test_gsi_event_series_marks_only_hour_level_confirmed_landslides_as_weather_matched():
    labels = read_csv("app/ml_model/landslide/validation/gsi_idukki_2018_event_labels.csv")
    joined = read_csv("app/ml_model/landslide/validation/gsi_idukki_2018_events_with_weather.csv")
    matched = [row for row in joined if row["weather_match_status"].startswith("matched")]

    assert len(labels) == 11
    assert len(joined) == len(labels)
    assert {row["event_id"] for row in matched} == {"GSI-2018-IDK-01", "GSI-2018-IDK-02"}
    assert all(float(row["rainfall_72h_before_event_mm"]) >= 0 for row in matched)
    subsidence = next(row for row in labels if row["event_type"] == "subsidence")
    assert subsidence["landslide_confirmed"] == "0"


def test_official_flood_snapshot_is_positive_only_and_joined_to_pre_event_weather():
    labels = read_csv("app/ml_model/flood/validation/flood_inundation_2018-07-16_district_labels.csv")
    joined = read_csv("app/ml_model/flood/validation/flood_inundation_2018-07-16_with_weather.csv")

    assert len(labels) == 7
    assert sum(int(row["inundated_area_ha"]) for row in labels) == 55007
    assert all(row["flood_observed"] == "1" for row in labels)
    assert len(joined) == 7
    assert all(float(row["rainfall_72h_before_observation_mm"]) >= 0 for row in joined)


def test_official_drought_declarations_remain_positive_district_season_labels():
    rows = read_csv("app/ml_model/drought/validation/drought_official_district_seasons.csv")
    kharif_rabi = [row for row in rows if row["season"] == "Kharif and Rabi 2016-17"]
    rabi = [row for row in rows if row["season"] == "Rabi 2017-18"]

    assert len(rows) == 23
    assert len(kharif_rabi) == 14
    assert len(rabi) == 9
    assert all(row["drought_declared"] == "1" for row in rows)
    assert all(row["label_status"] == "official_positive" for row in rows)
