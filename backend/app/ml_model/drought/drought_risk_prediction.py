import pandas as pd
import numpy as np
import joblib

from pathlib import Path

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (mean_absolute_error,mean_squared_error,r2_score)

folder_path = Path(__file__).resolve().parent

dataset_path = folder_path / "drought_training.csv"
model_path = folder_path / "drought_risk_model.pkl"

data = pd.read_csv(dataset_path)
print("Total rows:", len(data))
print(data.head())


feature_columns = [
    "rainfall_1h_mm",
    "rainfall_7d_mm",
    "rainfall_30d_mm",
    "rainfall_60d_mm",
    "rainfall_90d_mm",
    "rainfall_180d_mm",
    "rainfall_deficit_pct",

    "temperature_2m_c",
    "temp_anomaly_c",
    "avg_max_temp_c",

    "relative_humidity_2m_pct",
    "evapotranspiration_mm",
    "soil_moisture",

    "vegetation_health_index",

    "groundwater_level_m",
    "reservoir_storage_pct",

    "historical_drought_event_count"
]


target_column = "drought_risk_pct"


required_columns = feature_columns + [target_column]

for column in required_columns:
    if column not in data.columns:
        raise ValueError("Missing column: " + column)

data = data.dropna(subset=[target_column])

for column in feature_columns:
    data[column] = pd.to_numeric(data[column], errors="coerce")
    
    
print("\nTotal rows:", len(data))


data = data.replace([np.inf, -np.inf], np.nan)

data = data.dropna(subset=feature_columns)

data = data[data[target_column].between(0, 100)]

data = data.reset_index(drop=True)

print("Rows after cleaning:", len(data))

if len(data) < 2:
    raise ValueError("Not enough valid data to train the model.")


X = data[feature_columns].copy()

Y = data[target_column].copy()

print("\nNumber of input features:", X.shape[1])


X_train, X_test, y_train, y_test = train_test_split(X,Y,test_size=0.20,random_state=42)

print("\nTraining rows:", len(X_train))
print("Testing rows:", len(X_test))


model = RandomForestRegressor(n_estimators=100,random_state=42)

model.fit(X_train, y_train)

y_pred = model.predict(X_test)

y_pred = np.clip(y_pred, 0, 100)

mae = mean_absolute_error(y_test, y_pred)

mse = mean_squared_error(y_test, y_pred)

rmse = np.sqrt(mse)

r2 = r2_score(y_test, y_pred)

print("MAE:", round(mae, 2))
print("MSE:", round(mse, 2))
print("RMSE:", round(rmse, 2))
print("R2 Score:", round(r2, 4))

model_information = {

    "model": model,

    "feature_columns": feature_columns,

    "target_column": target_column,

    "model_type": "RandomForestRegressor"

}

joblib.dump(model_information, "drought_risk_model.pkl")


