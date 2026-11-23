# Live hazard pipeline status

## Data flow

1. The frontend loads district identities from `GET /api/districts` and asks
   `GET /api/dashboard/risk-map` for current district weather features and
   experimental scenario indices. The map no longer fills missing data with
   hard-coded illustrative district scores.
2. `GET /api/dashboard/risk/{district_id}` fetches a broader live weather feature bundle
   using the same Open-Meteo forecast/archive/seasonal helper used by
   `/api/hazard-data/{location_id}`. It does not read current weather from the
   separate weather card as a model input.
3. `feature_pipeline.py` validates the measured and derived values with
   Pydantic, records source freshness, and calculates feature completeness.
   Values that require multi-year baselines or official terrain layers remain
   null until those data are actually available.
   It combines the latest 120 hourly model steps with the delayed archive to
   refresh rolling 7/30/90-day rainfall and 30/90-day ET₀ totals. These recent
   values are Open-Meteo model estimates, not local rain-gauge observations.
4. `scenario_risk.py` compares weather features against district/season
   distributions read from the existing flood, drought, and landslide training
   CSVs. Scenario spread comes from each matched dataset's weather interquartile
   range where at least five rows exist; sparse groups fall back to broader
   district/state samples. The index combines forecast scenario conditions
   (65%) with recent ERA5-Land weather context (35%). Drought uses rainfall
   versus ET₀ water balance, recent soil moisture, five-day rainfall, and dry
   spell length; historical CSV distributions set sensitivity ranges rather
   than directly setting the drought severity. CSV event labels and
   target/susceptibility columns are not read. The weather fields themselves
   are modeled, proxy, or synthetically filled, so this is an experimental
   index out of 100, not a probability, calibrated ML output, or official warning.
   Each hazard also returns a confidence score equal to the percentage of its
   required input fields currently available. It is an input-coverage measure,
   not prediction accuracy; the map tooltip shows it beside the index. For the
   overall layer, the confidence score follows the hazard with the highest index.

## API examples

`GET /api/dashboard/risk/{district_id}` returns a result object with
`status: INSUFFICIENT_DATA`, null composite/hazard scores, weather feature
values when feeds succeed, and a metadata reason. Representative district
coordinates are used only if the district database row has no coordinates.

`GET /api/dashboard/risk-map` requests district weather in parallel and returns
`EXPERIMENTAL_INDEX` where required forecast and recent-weather inputs exist.
Per-district responses are cached for 20 minutes. Provider failures leave that
district without a score, and the map displays no-data styling instead of a
fabricated value. Flood, landslide, drought, and overall layers are historical-
weather-anchored scenario indices, not live ML predictions or disaster
probabilities. Historical anchor provenance and fallback scope are returned
for each hazard.

## Data and training

Run `python scripts/train_risk_models.py --mode proxy --years 5` from
`backend/` to cache Open-Meteo daily reanalysis and create explicitly labelled
IMD rainfall-category proxy indicator CSVs. Proxy categories are not disaster
events and do not become probabilities. Historical mode requires curated
hazard event tables and currently stops safely because the repository lacks
verified event/non-event coverage for all districts and hazards.

The script's published rainfall categories are from the India Meteorological
Department's [Heavy Rainfall Warning Services SOP](https://mausam.imd.gov.in/imd_latest/contents/pdf/forecasting_sop.pdf).
The weather provider describes archive results as reanalysis, which is a
model-based historical estimate rather than a district rain-gauge observation
([Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)).

No production model artifacts or calibrated probability scores should be
created until event timing, negative labels, spatial coverage, and independent
time/district holdouts are reviewed. Current artifact details are in
`app/ml_model/production/model_audit.md`. The earlier flood, drought, and
landslide demonstration artifacts are deliberately not used by this live index:
their synthetic/proxy targets do not support real-event probability claims.
Only weather fields from their CSV inputs are used as clearly tagged scenario
reference distributions; no target or event label contributes to the score.
