"""Create training-only SMOTE demo sets for the binary hazard targets.

All source rows in these demo CSVs are synthetic/proxy records. This script
keeps a natural holdout untouched and applies SMOTE only after the split.
It deliberately skips landslide: its current binary labels are heavily
positive and all rows are synthetic-filled, so balancing would invent a huge
number of unreliable negative cases.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.model_selection import GroupShuffleSplit


ROOT = Path(__file__).resolve().parent
SEED = 42
HAZARDS = {
    "flood": {
        "target": "flood_occurred_next_72h",
        "features": [
            "rainfall_1h_mm", "rainfall_24h_mm", "rainfall_72h_mm",
            "rainfall_7d_mm", "rainfall_30d_mm", "temperature_2m_c",
            "relative_humidity_2m_pct", "surface_pressure_hpa",
            "cloud_cover_pct", "wind_speed_10m_kmh", "elevation_m",
            "slope_deg", "distance_to_river_m", "soil_moisture",
            "river_water_level_m", "historical_flood_event_count",
        ],
        "split": "constituency_group_holdout",
    },
    "drought": {
        "target": "drought_occurred",
        "features": [
            "rainfall_1h_mm", "rainfall_7d_mm", "rainfall_30d_mm",
            "rainfall_60d_mm", "rainfall_90d_mm", "rainfall_180d_mm",
            "rainfall_deficit_pct", "temperature_2m_c", "temp_anomaly_c",
            "avg_max_temp_c", "relative_humidity_2m_pct",
            "evapotranspiration_mm", "soil_moisture",
            "vegetation_health_index", "groundwater_level_m",
            "reservoir_storage_pct", "historical_drought_event_count",
        ],
        "split": "holdout_years_2025_2026",
    },
}


def split_rows(hazard: str, frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if hazard == "flood":
        splitter = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=SEED)
        train_idx, test_idx = next(
            splitter.split(frame, frame[HAZARDS[hazard]["target"]], frame["constituency"])
        )
        return frame.iloc[train_idx].copy(), frame.iloc[test_idx].copy()

    years = pd.to_datetime(frame["date"], errors="coerce").dt.year
    training = frame.loc[years < 2025].copy()
    holdout = frame.loc[years >= 2025].copy()
    if training.empty or holdout.empty:
        raise ValueError("Drought dataset needs both pre-2025 training rows and 2025+ holdout rows.")
    return training, holdout


def clean_frame(hazard: str, frame: pd.DataFrame) -> pd.DataFrame:
    cfg = HAZARDS[hazard]
    missing = sorted(set(cfg["features"] + [cfg["target"]]) - set(frame.columns))
    if missing:
        raise ValueError(f"{hazard} source CSV is missing columns: {missing}")
    result = frame[cfg["features"] + [cfg["target"]]].copy()
    for col in result.columns:
        result[col] = pd.to_numeric(result[col], errors="coerce")
    result = result.replace([float("inf"), -float("inf")], pd.NA).dropna()
    result[cfg["target"]] = result[cfg["target"]].astype(int)
    if set(result[cfg["target"]].unique()) != {0, 1}:
        raise ValueError(f"{hazard} training split must contain both binary classes")
    return result


def main() -> None:
    reports = {}
    for hazard, cfg in HAZARDS.items():
        source = pd.read_csv(ROOT / hazard / f"{hazard}_training.csv")
        train_source, holdout_source = split_rows(hazard, source)
        train = clean_frame(hazard, train_source)
        holdout = clean_frame(hazard, holdout_source)
        counts_before = train[cfg["target"]].value_counts().sort_index().to_dict()

        # Do not fabricate a larger class where the source is already balanced.
        if abs(counts_before[0] - counts_before[1]) <= max(25, int(0.10 * len(train))):
            x_resampled, y_resampled = train[cfg["features"]], train[cfg["target"]]
            synthetic_count = 0
        else:
            minority_count = min(counts_before.values())
            smote = SMOTE(k_neighbors=min(5, minority_count - 1), random_state=SEED)
            x_resampled, y_resampled = smote.fit_resample(
                train[cfg["features"]], train[cfg["target"]]
            )
            synthetic_count = len(x_resampled) - len(train)

        augmented = pd.DataFrame(x_resampled, columns=cfg["features"])
        augmented[cfg["target"]] = y_resampled.astype(int)
        augmented.insert(0, "row_origin", "SOURCE_SYNTHETIC_PROXY")
        if synthetic_count:
            augmented.loc[augmented.index[-synthetic_count:], "row_origin"] = "SMOTE_INTERPOLATED_SYNTHETIC"

        output_dir = ROOT / hazard / "synthetic_training"
        output_dir.mkdir(exist_ok=True)
        augmented.to_csv(output_dir / f"{hazard}_smote_train.csv", index=False)
        holdout.assign(row_origin="UNTOUCHED_SYNTHETIC_PROXY_HOLDOUT").to_csv(
            output_dir / f"{hazard}_holdout_untouched.csv", index=False
        )
        reports[hazard] = {
            "source_rows": int(len(source)),
            "train_rows_before_smote": int(len(train)),
            "untouched_holdout_rows": int(len(holdout)),
            "class_counts_before_smote": {str(k): int(v) for k, v in counts_before.items()},
            "class_counts_after_smote": {
                str(k): int(v) for k, v in augmented[cfg["target"]].value_counts().sort_index().items()
            },
            "smote_rows_added": int(synthetic_count),
            "split_method": cfg["split"],
            "warning": "Synthetic demo data only; these rows are not documented events or real observations.",
        }

    reports["landslide_skipped"] = {
        "reason": "Current binary labels are synthetic-filled and strongly positive-skewed; SMOTE would fabricate unreliable negative examples.",
        "class_counts": {"0": 268, "1": 5011},
        "smote_rows_added": 0,
    }
    (ROOT / "synthetic_smote_report.json").write_text(
        json.dumps(reports, indent=2), encoding="utf-8"
    )
    for hazard in HAZARDS:
        report = reports[hazard]
        print(f"{hazard}: added {report['smote_rows_added']} SMOTE rows; "
              f"class counts {report['class_counts_before_smote']} -> {report['class_counts_after_smote']}")
    print("Landslide skipped: existing labels are synthetic-filled and 5,011:268 imbalanced; SMOTE would invent unreliable negatives.")


if __name__ == "__main__":
    main()
