
import pandas as pd
import numpy as np
import joblib

from pathlib import Path

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)

folder_path = Path(__file__).resolve().parent

dataset_path = folder_path / "flood_training.csv"
model_path = folder_path / "flood_risk_model.pkl"

data = pd.read_csv(dataset_path)

print("Total rows:", len(data))
print("Total columns:", len(data.columns))


feature_columns = [
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

target_column = "flood_susc_score_adj_0_100"

required_columns = feature_columns + [target_column]

missing_columns = []

for column in required_columns:
    if column not in data.columns:
        missing_columns.append(column)

if missing_columns:
    raise ValueError(
        "Missing columns in the dataset: "
        + str(missing_columns)
    )

data = data.dropna(subset=[target_column])

for column in feature_columns:
    data[column] = pd.to_numeric(data[column], errors="coerce")

data = data.replace([np.inf, -np.inf], np.nan)

data = data[data[target_column].between(0, 100)]

data = data.dropna(subset=feature_columns)

data = data.reset_index(drop=True)

print("Rows after cleaning:", len(data))

if len(data) < 2:
    raise ValueError("Not enough valid rows to train and test the model.")

X = data[feature_columns].copy()

Y = data[target_column].copy()

print("\nInput features:", X.shape[1])
print("Target column:", target_column)

X_train, X_test, y_train, y_test = train_test_split(
    X,
    Y,
    test_size=0.20,
    random_state=42
)

print("\nTraining rows:", len(X_train))
print("Testing rows:", len(X_test))

model = RandomForestRegressor(
    n_estimators=100,
    max_depth=10,
    min_samples_leaf=3,
    random_state=42,
    n_jobs=-1
)

model.fit(X_train, y_train)

predicted_scores = model.predict(X_test)

predicted_scores = np.clip(predicted_scores, 0, 100)

mae = mean_absolute_error(y_test, predicted_scores)

mse = mean_squared_error(y_test, predicted_scores)

rmse = np.sqrt(mse)

r2 = r2_score(y_test, predicted_scores)


print("MAE:", round(mae, 2))
print("MSE:", round(mse, 2))
print("RMSE:", round(rmse, 2))
print("R2 Score:", round(r2, 4))


model_information = {
    "model": model,
    "feature_columns": feature_columns,
    "target_column": target_column,
    "model_type": "RandomForestRegressor",
}

joblib.dump(model_information, model_path)

