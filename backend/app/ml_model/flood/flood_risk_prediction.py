"""Train the explicitly synthetic Kerala flood demo classifier.

This script is for the Kaavalal demo only. Its labels and several predictors
are synthetic/proxy values; the saved model is not an operational forecast.
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    balanced_accuracy_score,
    classification_report,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit


FOLDER_PATH = Path(__file__).resolve().parent
DATASET_PATH = FOLDER_PATH / "flood_training.csv"
MODEL_PATH = FOLDER_PATH / "flood_72h_demo_model.pkl"

FEATURE_COLUMNS = [
    "rainfall_1h_mm",
    "rainfall_24h_mm",
    "rainfall_72h_mm",
    "rainfall_7d_mm",
    "rainfall_30d_mm",
    "temperature_2m_c",
    "relative_humidity_2m_pct",
    "surface_pressure_hpa",
    "cloud_cover_pct",
    "wind_speed_10m_kmh",
    "elevation_m",
    "slope_deg",
    "distance_to_river_m",
    "soil_moisture",
    "river_water_level_m",
    "historical_flood_event_count",
]
TARGET_COLUMN = "flood_occurred_next_72h"


def load_demo_data() -> pd.DataFrame:
    data = pd.read_csv(DATASET_PATH)
    required = FEATURE_COLUMNS + [TARGET_COLUMN, "constituency"]
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise ValueError(f"Training CSV is missing required columns: {missing}")

    # Keep the demo visibly segregated from future observed data. Do not
    # silently train this demo script on an unlabeled or real-world dataset.
    if "generated_columns_basis" not in data.columns or not data[
        "generated_columns_basis"
    ].astype(str).str.contains("SYNTHETIC", case=False).all():
        raise ValueError(
            "This demo trainer only accepts rows explicitly marked SYNTHETIC."
        )
    if "record_type" in data.columns and not data["record_type"].astype(str).str.contains(
        "MODELLED_NOT_OBSERVED", case=False
    ).all():
        raise ValueError("Unexpected record type; refusing to mix demo and observed rows.")

    for column in FEATURE_COLUMNS + [TARGET_COLUMN]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.replace([np.inf, -np.inf], np.nan)
    data = data.dropna(subset=FEATURE_COLUMNS + [TARGET_COLUMN, "constituency"])
    data = data[data[TARGET_COLUMN].isin([0, 1])].copy()
    data[TARGET_COLUMN] = data[TARGET_COLUMN].astype(int)

    if data[TARGET_COLUMN].nunique() != 2:
        raise ValueError("The synthetic 72-hour target must contain both 0 and 1 labels.")
    if data["constituency"].nunique() < 2:
        raise ValueError("At least two constituencies are required for grouped evaluation.")
    return data.reset_index(drop=True)


def main() -> None:
    data = load_demo_data()
    x = data[FEATURE_COLUMNS]
    y = data[TARGET_COLUMN]
    groups = data["constituency"]

    # Keep each constituency entirely on one side of the split so repeated
    # annual samples for the same area do not leak into both sets.
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)
    train_indices, test_indices = next(splitter.split(x, y, groups))
    x_train, x_test = x.iloc[train_indices], x.iloc[test_indices]
    y_train, y_test = y.iloc[train_indices], y.iloc[test_indices]
    if y_train.nunique() != 2 or y_test.nunique() != 2:
        raise ValueError(
            "Grouped split did not include both classes in train and test. "
            "Review the synthetic labels before training."
        )

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=10,
        min_samples_leaf=4,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(x_train, y_train)

    predicted = model.predict(x_test)
    score = model.predict_proba(x_test)[:, 1]
    metrics = {
        "balanced_accuracy": float(balanced_accuracy_score(y_test, predicted)),
        "f1": float(f1_score(y_test, predicted, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, score)),
        "train_rows": int(len(train_indices)),
        "test_rows": int(len(test_indices)),
        "train_constituencies": int(groups.iloc[train_indices].nunique()),
        "test_constituencies": int(groups.iloc[test_indices].nunique()),
    }

    model_bundle = {
        "model": model,
        "feature_columns": FEATURE_COLUMNS,
        "target_column": TARGET_COLUMN,
        "target_window_hours": 72,
        "grid_size_km": 10,
        "spatial_support": (
            "Approximate 10 km demo grid proxy. Source samples are synthetic "
            "constituency/year points with approximate coordinates, not observed grid cells."
        ),
        "model_type": "RandomForestClassifier",
        "data_kind": "synthetic_demo",
        "metrics": metrics,
        "warning": (
            "Synthetic demonstration only. Scores are not validated flood probabilities "
            "and must not be used for real-world emergency decisions."
        ),
    }
    joblib.dump(model_bundle, MODEL_PATH)

    print(f"Synthetic demo rows used: {len(data)}")
    print(f"Target: {TARGET_COLUMN} (flood observed within 72 hours)")
    print(f"Features: {len(FEATURE_COLUMNS)}")
    print("Grouped holdout metrics (constituencies kept separate):")
    print(classification_report(y_test, predicted, zero_division=0))
    print(metrics)
    print(f"Saved demo model: {MODEL_PATH}")


if __name__ == "__main__":
    main()
