# Historical susceptibility inputs

These user-supplied layers contribute a 20% context term to the experimental
preparedness index. Live weather scenarios contribute 80%. This composite is an
index out of 100, not a calibrated probability or an official warning.

## Source handling

- `source/` preserves the supplied inputs. The original drought workbook is
  preserved; `drought_village_susceptibility.csv` is its normalized runtime copy
  with merged district and taluk labels filled down.
- `flood_taluk_susceptibility.csv` and `landslide_taluk_susceptibility.csv`
  normalize column names from the supplied CSV files for the runtime loader.
- Flood susceptibility is a relative district percentile of the sum of the
  reported taluk floodplain areas. The input says the taluk assignment is
  approximate and marks every row unverified.
- Landslide uses the supplied `LS_INDEX` at district scale. The input says its
  district class is repeated across taluks; six rows are unmapped. It is not a
  taluk- or constituency-level prediction.
- Drought maps ordinal classes to equally spaced index values (No=0,
  Slight=33.3, Moderate=66.7, Severe=100), then averages village values by
  district. The workbook's publication date and method were not supplied.

All three sources are marked low quality by the application. Their values are
displayed with that caveat and never treated as event labels or probabilities.
If a district has no usable susceptibility value, that hazard remains weather-
only and the API marks the blend as unavailable for that district.
