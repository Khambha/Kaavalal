# Official flood snapshot labels

`flood_inundation_2018-07-16_district_labels.csv` records the seven district inundation totals published by KSDMA/NRSC for the Sentinel-1A observation of 16 July 2018. The source memorandum gives 55,007 hectares in total across those districts.

Run `prepare_event_weather.py` to query Open-Meteo's historical archive and create `flood_inundation_2018-07-16_with_weather.csv`. Rainfall windows end at 00:00 IST on the observation date, so the 24-hour, 72-hour, and 7-day predictors precede the observed inundation snapshot. Weather is sampled at the district representative coordinates already used by Kaavalal.

Sources:

- [KSDMA/NRSC flood map memorandum](https://sdma.kerala.gov.in/wp-content/uploads/2019/08/Memorandum1-Floods-2018.pdf)
- [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
- [KSDMA Flood 2018 maps and reports](https://sdma.kerala.gov.in/floods_2018/)

The labels are a **single-date, district-level satellite snapshot**. Districts absent from this map are unknown, not flood-free. The data cannot test a constituency-level 72-hour model or provide negative samples; it is a date-aligned event case study only. Do not merge it with the synthetic flood training CSV.
