# Verified landslide event inventory

`landslide_inventory_2018.csv` is derived from the published 2018 Kerala monsoon landslide point inventory. The preparation script downloads the public DANS shapefile attribute table and preserves source flags, event coordinates, landslide type, impact attributes, and land-cover fields:

```powershell
cd backend
.\venv\Scripts\python.exe app/ml_model/landslide/prepare_verified_inventory.py
```

## Provenance

- Dataset DOI: <https://doi.org/10.17026/dans-x6c-y7x2>
- Article: Hao et al. (2020), *Earth System Science Data*, <https://doi.org/10.5194/essd-12-2899-2020>
- The published inventory contains 4,728 mapped landslides and combines NRSC mapping, GSI field surveys, and additional visual interpretation. The article reports that 73% were confirmed by at least two independent sources and cautions that completeness cannot be quantified.

## Validation limits

- The inventory is positive-only and does not include sampled non-landslide locations.
- It identifies the 2018 monsoon event, but does not provide a date for each point. `event_date` is intentionally blank. Do not use these rows to score a 72-hour landslide forecast.
- Constituencies are assigned to the nearest constituency centroid **within the source district**. The distance is retained as `nearest_lac_centroid_km`; it is an approximate crosswalk, not a polygon membership test. Exact constituency boundaries are not currently in the repository.
- `source_raster_value` is preserved as supplied; interpret it only after consulting the dataset metadata.
- This inventory is separate from `landslide_training.csv`. Do not merge its observed event labels with synthetic weather, dates, or risk scores.

This supports spatial checks of the 2018 event inventory. A proper event-window backtest still needs point-level dates and comparable negative observations from the same periods.

## Date-aligned GSI event subset

`gsi_idukki_2018_event_labels.csv` transcribes the ten site records in the [GSI/KSDMA post-disaster report](https://sdma.kerala.gov.in/wp-content/uploads/2020/08/Landslide-Study.pdf). The report provides coordinates and event dates; two events have approximate initiation hours. `prepare_gsi_event_weather.py` joins pre-event Open-Meteo reanalysis only for those two hour-level cases and leaves date-only cases unmatched. One reported subsidence case is retained for traceability but has `landslide_confirmed=0` and is excluded from landslide positives because it is not described as a landslide event.

The resulting `gsi_idukki_2018_events_with_weather.csv` is a small event case series (two date-and-hour weather matches, no negative windows). It can support a case review, but cannot establish 72-hour model accuracy.
