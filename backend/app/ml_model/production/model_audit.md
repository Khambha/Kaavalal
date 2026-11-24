# Hazard model audit

Audited against repository artifacts and training data on 2026-11-20. None of
the current artifacts qualifies as a calibrated live district risk model.

| Artifact | Estimator / inputs | Target | Provenance and deployment status |
|---|---|---|---|
| `flood/flood_72h_demo_model.pkl` | RandomForestClassifier; 16 flood/weather fields | `flood_occurred_next_72h` | Synthetic demonstration target; the bundle itself warns scores are not validated probabilities. Not for inference in the live dashboard. |
| `flood/flood_risk_model.pkl` | RandomForestRegressor; 16 flood/weather fields | `flood_susc_score_adj_0_100` | Flood training rows are generated/modelled proxy records, not observed events. No probability interpretation. |
| `landslide/landslide_risk_model.pkl` | RandomForestRegressor; 90 weather/terrain/geology/soil fields | `risk_score_pct` | Mixed event inventory and simulated/synthetic-filled weather; no reliable event times or negative sample design. Random row split in the training script. |
| `drought/drought_risk_model.pkl` | RandomForestRegressor; 17 rainfall/deficit fields | `drought_risk_pct` | Demonstration training data include synthetic/SMOTE samples; training script uses random row split. |
| `synthetic_smote_report.json` | Dataset report, not estimator | N/A | Documents synthetic oversampling; not a deployable model. |

The repo contains small verification datasets for specific historical events,
but not a consistently labelled, time-indexed, district-wide training table for
all three hazards. Flood snapshots and positive-only landslide/drought
inventories cannot by themselves supply valid non-event labels or calibration.

## Release gate

Before creating production artifacts, curated event CSVs must have `district`,
`event_date`, and a binary `event` label with documented source and spatial
coverage. Training and calibration rows must be chronological, and evaluation
must include an unseen-district holdout. Proxy thresholds can support a clearly
labelled rule indicator, but are not training labels for a probability model.

## Static district context

`app/data/kerala_district_static.json` lists the 14 canonical district keys and
representative weather-grid coordinates. User-supplied susceptibility tables
are integrated separately in `app/ml_model/susceptibility/` as a 40% context
term in the experimental preparedness index. Their flood assignment is
approximate and unverified, landslide classes are district-level, and the
drought workbook's date/method are unknown. These inputs remain low-quality
susceptibility indices, not calibrated event probabilities. Official terrain,
coast/backwater, basin, and drainage fields remain null until proper spatial
layers are ingested and verified; do not replace them with guessed tiers.
