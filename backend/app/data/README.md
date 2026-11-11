# KSDMA camp shelter candidates

`ksdma_monsoon_shelter_candidates.json` is a prepared, review-only import derived from the user-provided `Monsoon-Camp-Details-ALL-Kerala.xlsx` workbook.

- 5,163 records are eligible for the shelter table after checking names, capacity, coordinates, duplicate rows, and whether each point falls inside its listed district boundary.
- Every record is imported inactive with `needs_review` set. It is hidden from citizen and responder shelter lists and cannot be activated until an admin confirms the details.
- LAC is assigned to the nearest LAC center in the same district. Every assignment is marked for review and includes the distance to the center; the assignment is approximate and is not a constituency-boundary lookup.
- Capacity values that are missing, non-integer, non-positive, or above the shelter form limit are excluded. Rows with missing/invalid coordinates or points outside their listed district are also excluded.
- Duplicate rows are identified by district, camp name, LSG, and village. Source worksheet row numbers are retained in `source_row` and `source_key` for traceability.

The admin Shelters screen has an explicit import action. Importing is idempotent by `source_key`. Admins can filter pending review candidates by district, inspect/edit a row, confirm the review, and then choose whether to activate it. Confirming a review does not activate the shelter.

## Verifying the other workbooks

The other source lists need per-facility checks before they can be treated as shelters:

1. Confirm with the district/local authority that the facility is currently available for evacuation use and identify an accountable contact or source record.
2. Confirm a usable address and location pin; verify that the pin falls inside the listed district, then assign/confirm the LAC.
3. Confirm a safe, current shelter capacity with the facility operator. Classroom counts, hotel rooms, and hospital beds are not shelter capacities by themselves.
4. Deduplicate across lists by name, locality, and coordinates. Keep the original workbook row as provenance.
5. Add verified facilities as inactive candidates, review them in the admin directory, and activate only after the admin confirms the details.

The private hospital workbook is dated June 2020, so its current status and capacity would need re-confirmation before reuse.

## Auditorium coordinate suggestions

`auditorium_geocoding_suggestions_review.csv` contains all 1,505 rows from the user-provided auditorium workbook. It was generated with the single-threaded script `backend/scripts/geocode_auditoriums.py` using OpenStreetMap Nominatim. The script waits at least 1.1 seconds between uncached requests and caches results for resumability. The earlier `auditorium_geocoding_suggestions.csv` file is a preliminary result; use the `_review.csv` file.

- 512 rows have a high-confidence facility-name and location-context match inside the listed district; 103 are medium facility-name matches without a full location-context match, 124 are low-confidence matches, and 766 had no result.
- 739 rows have suggested coordinates. Four low-confidence results fall outside the workbook-listed district; 120 are address/locality-only matches.
- Every row remains `Pending`. The workbook does not include shelter capacity, so capacity is blank and must be confirmed by the facility operator before a record can become a shelter.
- Review the returned OSM feature name/address and open its map link. A name match is still only a suggestion; verify the exact site with the facility or local authority.
- Attribution is included in every CSV row: © OpenStreetMap contributors (ODbL). Review the [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/) before running more geocoding.

`auditorium_demo_candidates.json` contains two distinct high-confidence suggestions from each of the 14 districts, excluding exact name overlaps with the camp candidates. The admin Shelters screen can add these 28 records to the separate review-only candidate table. They have no capacity and are not available to citizens or responders.
