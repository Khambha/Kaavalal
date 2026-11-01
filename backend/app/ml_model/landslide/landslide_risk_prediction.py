import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (mean_absolute_error,mean_squared_error,r2_score)

folder_path = Path(__file__).resolve().parent
data = pd.read_csv(folder_path / "landslide_training.csv")
print("Total number of records:", len(data))
print(data.head())

target_column = "risk_score_pct"

if target_column not in data.columns:
    raise ValueError("Target column is missing!")

print("\nTarget column:", target_column)

input_columns = [
    "rainfall_1h_mm",
    "rainfall_24h_mm",
    "rainfall_72h_mm",
    "rainfall_7d_mm",
    "rainfall_30d_mm",
    "max_rainfall_intensity_mm_h",
    "temperature_2m_c",
    "relative_humidity_2m_pct",
    "apparent_temperature_c",
    "surface_pressure_hpa",
    "cloud_cover_pct",
    "wind_speed_10m_kmh",
    "visibility_m",
    "slope_deg",
    "elevation_m",
    "distance_to_river_m",
    "distance_to_road_m",
    "soil_moisture",
    "soil_type",
    "groundwater_level_m",
    "pore_water_pressure",
    "land_use_land_cover",
    "land_use_code_2018",
    "geology_or_lithology",
    "vegetation_cover_pct",
    "historical_landslide_event_count"
]

for column in input_columns:

    if column not in data.columns:
        raise ValueError("Missing column: " + column)

print("\nAll input columns are available!")


data[target_column] = pd.to_numeric(data[target_column],errors="coerce")

data = data.dropna(subset=[target_column])

data = data[data[target_column].between(0, 100)]

print("Valid records:", len(data))

X = data[input_columns].copy()

Y = data[target_column].copy()


if "date" in data.columns:

    date = pd.to_datetime(data["date"], errors="coerce")

    X["date_year"] = date.dt.year
    X["date_month"] = date.dt.month

X = X.replace([np.inf, -np.inf], np.nan)

for column in X.columns:

    if column not in [
        "soil_type",
        "land_use_land_cover",
        "land_use_code_2018",
        "geology_or_lithology"
    ]:

        X[column] = pd.to_numeric(
            X[column],
            errors="coerce"
        )

X_train, X_test, y_train, y_test = train_test_split(X,Y,test_size=0.2,random_state=42)

print("\nTraining records:", len(X_train))
print("Testing records:", len(X_test))

X_train = pd.get_dummies(X_train, dtype=int)

X_test = pd.get_dummies(X_test, dtype=int)

X_test = X_test.reindex(
    columns=X_train.columns,
    fill_value=0
)

training_averages = X_train.mean()

X_train = X_train.fillna(training_averages)

X_test = X_test.fillna(training_averages)

X_train = X_train.fillna(0)

X_test = X_test.fillna(0)

model = RandomForestRegressor(n_estimators=100,random_state=42,n_jobs=-1)

model.fit(X_train, y_train)

print("\nLandslide model trained successfully!")

predictions = model.predict(X_test)

predictions = np.clip(predictions, 0, 100)

mae = mean_absolute_error(y_test, predictions)

mse = mean_squared_error(y_test, predictions)

rmse = np.sqrt(mse)

r2 = r2_score(y_test, predictions)

print("Mean Absolute Error:", round(mae, 2))

print("Mean Squared Error:", round(mse, 2))

print("Root Mean Squared Error:", round(rmse, 2))

print("R2 Score:", round(r2, 4))

model_path = folder_path / "landslide_risk_model.pkl"

model_data = {
    "model": model,
    "feature_columns": X_train.columns.tolist(),
    "training_averages": training_averages,
    "target_column": target_column
}

joblib.dump(model_data, model_path)

