# Kerala flood 72-hour demo model

This folder's demo trainer predicts the synthetic target `flood_occurred_next_72h`.
It is intentionally separate from operational flood forecasting: the CSV marks
its records and generated fields as synthetic, and the coordinates are
approximate constituency/year points rather than measured 10 km grid cells.

## Train

From the `backend` directory, install `requirements.txt` and run:

```powershell
python app/ml_model/flood/flood_risk_prediction.py
```

The script trains a binary random forest, holds out whole constituencies for
its demo metrics, and writes `flood_72h_demo_model.pkl` beside this README.

## Demo prediction API

`POST /api/risk/flood/demo-predict`

The request supplies a grid identifier, coordinates, and all 16 model features.
The response labels the score as simulated and includes the model's warning.
This API does not fetch or derive the feature values from OpenWeather or another
weather provider; the caller must provide them.

The score is a model score trained against synthetic labels, not a calibrated
flood probability. Do not use it for real-world emergency decisions. A future
observed-data model needs separate verified event labels, feature collection,
and evaluation before deployment.
