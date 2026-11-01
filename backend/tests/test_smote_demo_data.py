import json
from pathlib import Path

import pandas as pd


BACKEND_DIR = Path(__file__).resolve().parents[1]
MODEL_DIR = BACKEND_DIR / "app" / "ml_model"


def test_smote_outputs_are_tagged_and_holdouts_are_unmodified():
    report = json.loads((MODEL_DIR / "synthetic_smote_report.json").read_text(encoding="utf-8"))

    drought_train = pd.read_csv(
        MODEL_DIR / "drought" / "synthetic_training" / "drought_smote_train.csv"
    )
    drought_holdout = pd.read_csv(
        MODEL_DIR / "drought" / "synthetic_training" / "drought_holdout_untouched.csv"
    )
    synthetic = drought_train[drought_train["row_origin"] == "SMOTE_INTERPOLATED_SYNTHETIC"]

    assert report["drought"]["smote_rows_added"] == len(synthetic) == 596
    assert len(drought_holdout) == report["drought"]["untouched_holdout_rows"] == 280
    assert set(drought_holdout["row_origin"]) == {"UNTOUCHED_SYNTHETIC_PROXY_HOLDOUT"}
    assert report["drought"]["class_counts_after_smote"]["0"] == report["drought"]["class_counts_after_smote"]["1"]
    assert report["flood"]["smote_rows_added"] == 0
    assert report["landslide_skipped"]["smote_rows_added"] == 0
