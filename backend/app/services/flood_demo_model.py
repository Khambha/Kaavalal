from functools import lru_cache
from pathlib import Path

import pandas as pd


MODEL_PATH = (
    Path(__file__).resolve().parents[1]
    / "ml_model"
    / "flood"
    / "flood_72h_demo_model.pkl"
)


@lru_cache(maxsize=1)
def load_flood_demo_bundle() -> dict:
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(
            "Flood demo model is not trained. Run "
            "python app/ml_model/flood/flood_risk_prediction.py from backend/."
        )

    # joblib uses pickle under the hood; only load the model artifact committed
    # with this trusted application, never a user-uploaded file.
    import joblib

    return joblib.load(MODEL_PATH)


def predict_flood_demo(features: dict) -> dict:
    bundle = load_flood_demo_bundle()
    feature_columns = bundle["feature_columns"]
    frame = pd.DataFrame(
        [{column: features[column] for column in feature_columns}],
        columns=feature_columns,
    )
    score = float(bundle["model"].predict_proba(frame)[0][1])
    return {
        "score_percent": round(score * 100, 2),
        "model_type": bundle["model_type"],
        "target_column": bundle["target_column"],
        "target_window_hours": bundle["target_window_hours"],
        "grid_size_km": bundle["grid_size_km"],
        "spatial_support": bundle["spatial_support"],
        "data_kind": bundle["data_kind"],
        "warning": bundle["warning"],
    }
