# Synthetic SMOTE training demo

Run from the backend directory:

```powershell
python -m pip install -r requirements.txt
python app/ml_model/generate_smote_demo_data.py
```

The script writes separate synthetic training and untouched holdout CSVs under
each supported hazard's `synthetic_training/` directory and records row counts
in `synthetic_smote_report.json`. It splits first, then applies SMOTE only to
the training side: flood uses the existing constituency-group holdout, and
drought holds out 2025–2026.

The generated rows are **SMOTE interpolations from the existing demo CSVs**.
They are marked `SMOTE_INTERPOLATED_SYNTHETIC`; source rows are also marked
synthetic proxies. They are not documented disaster observations, and the
holdout is also synthetic, so evaluation on it is only a software/demo check,
not evidence of real-world prediction accuracy.

Flood's training subset is already close to balanced, so it may add no rows.
Drought's binary `drought_occurred` target can be oversampled. The script
intentionally skips landslide: its current 5,011 positive vs 268 negative
labels are all synthetic-filled, and balancing them would invent thousands of
untrustworthy non-landslide examples. SMOTE does not apply to the landslide
regression target `risk_score_pct` either.

The synthetic training CSVs are not connected to the production model loaders;
they do not change the current models or prediction API. Use them only for
experiments after reviewing the report and warning above.
