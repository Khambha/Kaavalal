"""Experimental district/season weather-scenario index; never a probability.

Historical training CSVs are read only for weather feature distributions. Their
event labels and risk targets are deliberately ignored. Static susceptibility
layers contribute 40% to a 60/40 experimental preparedness index; they are not
event labels and must not be described as probabilities.
"""

import csv
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.services.historical_susceptibility import get_historical_susceptibility


WEATHER_WEIGHT = 0.65
ANTECEDENT_WEIGHT = 0.35
LIVE_WEATHER_INDEX_WEIGHT = 0.60
HISTORICAL_SUSCEPTIBILITY_WEIGHT = 0.40
TIMEZONE = ZoneInfo("Asia/Kolkata")
MODEL_DIR = Path(__file__).resolve().parents[1] / "ml_model"

# Only meteorological fields are selected from the training CSVs. Targets,
# event labels, and their synthetic score fields are never used as event truth.
ANCHOR_FILES = {
    "flood": {
        "file": MODEL_DIR / "flood" / "flood_training.csv",
        "features": ("rainfall_24h_mm", "rainfall_72h_mm", "rainfall_7d_mm", "rainfall_1h_mm"),
        "quality": "MODELLED_NOT_OBSERVED weather anchors",
    },
    "landslide": {
        "file": MODEL_DIR / "landslide" / "landslide_training.csv",
        "features": ("rainfall_24h_mm", "rainfall_72h_mm", "rainfall_7d_mm", "max_rainfall_intensity_mm_h"),
        "quality": "weather fields are synthetically filled",
    },
    "drought": {
        "file": MODEL_DIR / "drought" / "drought_training.csv",
        "features": ("rainfall_30d_mm", "rainfall_90d_mm", "rainfall_60d_mm", "rainfall_180d_mm"),
        "quality": "proxy/demo weather records; target labels are not used",
    },
}

SCENARIO_NAMES = ("Lower weather case", "Baseline forecast", "Upper weather case")


def _district_key(value: str) -> str:
    key = "".join(char for char in str(value or "").lower() if char.isalpha())
    return {
        "trivandrum": "thiruvananthapuram", "tvm": "thiruvananthapuram",
        "trichur": "thrissur", "eranakulam": "ernakulam", "wynad": "wayanad",
    }.get(key, key)


def _season(month: int) -> str:
    if month in (6, 7, 8, 9):
        return "southwest_monsoon"
    if month in (10, 11):
        return "northeast_monsoon"
    if month in (3, 4, 5):
        return "premonsoon"
    return "dry_season"


def _parse_month(value: str) -> int | None:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:19], fmt).month
        except ValueError:
            continue
    return None


@lru_cache(maxsize=1)
def _load_weather_anchors() -> dict[str, dict[str, Any]]:
    """Read weather-only distributions, grouped by district and calendar season."""
    anchors: dict[str, dict[str, Any]] = {}
    for hazard, config in ANCHOR_FILES.items():
        buckets: dict[tuple[str, str], dict[str, list[float]]] = {}
        try:
            with config["file"].open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    district = _district_key(row.get("district", ""))
                    month = _parse_month(row.get("date", ""))
                    if month is None:
                        continue
                    season = _season(month)
                    for feature in config["features"]:
                        try:
                            value = float(row.get(feature, ""))
                        except (TypeError, ValueError):
                            continue
                        if not (value >= 0 and value < float("inf")):
                            continue
                        for key in ((district, season), (district, "all"), ("*", season), ("*", "all")):
                            buckets.setdefault(key, {}).setdefault(feature, []).append(value)
        except OSError:
            # Missing source files lower confidence; no guessed fallback rows are created.
            buckets = {}
        anchors[hazard] = {"buckets": buckets, "config": config}
    return anchors


def _quantile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _select_anchor(hazard: str, district: str, season: str) -> dict[str, Any]:
    loaded = _load_weather_anchors()[hazard]
    buckets = loaded["buckets"]
    for key, scope in (((district, season), "district + season"), ((district, "all"), "district, all seasons"),
                       (("*", season), "statewide season"), (("*", "all"), "statewide, all seasons")):
        distributions = buckets.get(key, {})
        counts = [len(values) for values in distributions.values() if values]
        count = max(counts, default=0)
        if count >= 5:
            return {
                "distributions": distributions,
                "metadata": {
                    "source_file": loaded["config"]["file"].name,
                    "source_quality": loaded["config"]["quality"],
                    "scope": scope,
                    "season": season,
                    "sample_count": count,
                    "weather_fields_only": True,
                    "event_labels_used": False,
                },
            }
    return {
        "distributions": {},
        "metadata": {
            "source_file": loaded["config"]["file"].name,
            "source_quality": loaded["config"]["quality"],
            "scope": "no usable historical anchor",
            "season": season,
            "sample_count": 0,
            "weather_fields_only": True,
            "event_labels_used": False,
        },
    }


def _percentile_rank(value: float | None, values: list[float] | None) -> float | None:
    if value is None or not values:
        return None
    less = sum(sample < value for sample in values)
    equal = sum(sample == value for sample in values)
    return round(100 * (less + 0.5 * equal) / len(values), 1)


def _historical_stats(values: list[float] | None) -> dict[str, float] | None:
    if not values:
        return None
    return {
        "p25": round(_quantile(values, 0.25) or 0, 2),
        "p50": round(_quantile(values, 0.50) or 0, 2),
        "p75": round(_quantile(values, 0.75) or 0, 2),
        "p90": round(_quantile(values, 0.90) or 0, 2),
    }


def _scenario_factors(anchor_values: list[float] | None) -> tuple[float, float, float]:
    """Set perturbation width from local historical spread, with conservative bounds."""
    if not anchor_values or len(anchor_values) < 5:
        spread = 0.20
    else:
        median = _quantile(anchor_values, 0.50) or 0
        iqr = (_quantile(anchor_values, 0.75) or 0) - (_quantile(anchor_values, 0.25) or 0)
        spread = max(0.10, min(0.35, iqr / max(median, 1.0) * 0.25))
    return (1.0 - spread, 1.0, 1.0 + spread)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _rain_severity(amount_mm: float | None, scale_days: float = 1.0) -> float | None:
    """Fallback weather intensity scale; IMD bands are not hazard-event thresholds."""
    if amount_mm is None:
        return None
    daily_equivalent = max(0.0, amount_mm) / max(scale_days, 1.0)
    if daily_equivalent < 64.5:
        return _clamp(daily_equivalent / 64.5 * 40)
    if daily_equivalent < 115.6:
        return 40 + (daily_equivalent - 64.5) / (115.6 - 64.5) * 30
    if daily_equivalent < 204.5:
        return 70 + (daily_equivalent - 115.6) / (204.5 - 115.6) * 30
    return 100.0


def _mean(values: list[float | None]) -> float | None:
    known = [float(value) for value in values if value is not None]
    return sum(known) / len(known) if known else None


def _weighted_mean(values: list[tuple[float | None, float]]) -> float | None:
    known = [(float(value), weight) for value, weight in values if value is not None]
    total_weight = sum(weight for _, weight in known)
    return sum(value * weight for value, weight in known) / total_weight if total_weight else None


def _input_coverage_score(values: list[Any]) -> int:
    """A transparent input-completeness measure, not predictive accuracy."""
    return round(100 * sum(value is not None for value in values) / len(values)) if values else 0


def _drought_deficit(rain_mm: float | None, et0_mm: float | None) -> float | None:
    if rain_mm is None or et0_mm is None or et0_mm <= 0:
        return None
    return _clamp(max(0.0, (et0_mm - rain_mm) / et0_mm) * 200.0)


def _soil_moisture_dryness(value: float | None) -> float | None:
    if value is None:
        return None
    # Transparent prototype range; not an official drought threshold.
    return _clamp((0.35 - value) / (0.35 - 0.15) * 100.0)


def _blend(weather_score: float | None, antecedent_score: float | None) -> float | None:
    if weather_score is None or antecedent_score is None:
        return None
    return round(_clamp(WEATHER_WEIGHT * weather_score + ANTECEDENT_WEIGHT * antecedent_score), 1)


def _apply_susceptibility_blend(hazard: str, result: dict[str, Any], district: str) -> dict[str, Any]:
    """Apply the requested 60/40 blend while preserving weather-only components."""
    weather_score = result.get("score")
    historical = get_historical_susceptibility(hazard, district)
    historical_score = historical.get("score")
    applied = weather_score is not None and historical_score is not None
    result["weather_scenario_score"] = weather_score
    result["historical_susceptibility"] = historical

    for scenario in result.get("scenarios", []):
        scenario_weather = scenario.get("index")
        scenario["weather_index"] = scenario_weather
        scenario["historical_susceptibility_index"] = historical_score
        if scenario_weather is not None and historical_score is not None:
            scenario["index"] = round(
                LIVE_WEATHER_INDEX_WEIGHT * scenario_weather
                + HISTORICAL_SUSCEPTIBILITY_WEIGHT * historical_score,
                1,
            )

    scenario_values = [item.get("index") for item in result.get("scenarios", [])]
    if applied and scenario_values and all(value is not None for value in scenario_values):
        result["score"] = round(0.25 * scenario_values[0] + 0.5 * scenario_values[1] + 0.25 * scenario_values[2], 1)
    elif weather_score is not None:
        result["score"] = weather_score

    result["blend"] = {
        "applied": applied,
        "weather_weight": LIVE_WEATHER_INDEX_WEIGHT if applied else 1.0,
        "historical_susceptibility_weight": HISTORICAL_SUSCEPTIBILITY_WEIGHT if applied else 0.0,
        "weather_scenario_score": weather_score,
        "historical_susceptibility_score": historical_score,
        "status": "BLENDED_80_20" if applied else "WEATHER_ONLY_SUSCEPTIBILITY_UNAVAILABLE",
        "semantics": "Preparedness index out of 100; not a disaster probability.",
    }
    if historical_score is not None:
        result.setdefault("component_breakdown", []).append({
            "label": "Historical susceptibility context",
            "score": historical_score,
            "weight": "40% of combined preparedness index",
            "quality": historical.get("quality"),
        })
    if historical.get("quality") == "LOW":
        result["confidence"] = "LOW"
        result.setdefault("data_gaps", []).append("Historical susceptibility layer has coarse or unverified source quality")
    elif historical_score is None:
        result["confidence"] = "LOW"
        result.setdefault("data_gaps", []).append("Historical susceptibility unavailable; score remains weather-only")
    return result


def _risk_component(value: float | None, values: list[float] | None, fallback_days: float = 1.0) -> float | None:
    rank = _percentile_rank(value, values)
    return rank if rank is not None else _rain_severity(value, fallback_days)


def _make_rain_scenarios(
    forecast24: float | None,
    forecast72: float | None,
    antecedent: float | None,
    distributions: dict[str, list[float]],
    hazard: str,
    terrain_missing: bool = False,
    forecast_window_hours: int = 72,
) -> dict[str, Any]:
    anchor_values = distributions.get("rainfall_24h_mm") or distributions.get("rainfall_72h_mm")
    factors = _scenario_factors(anchor_values)
    rows = []
    for name, factor in zip(SCENARIO_NAMES, factors):
        score24 = _risk_component(forecast24 * factor if forecast24 is not None else None,
                                  distributions.get("rainfall_24h_mm"))
        score72 = _risk_component(forecast72 * factor if forecast72 is not None else None,
                                  distributions.get("rainfall_72h_mm"), 3)
        weather = score24 if forecast_window_hours <= 24 else _mean([score24, score72])
        rows.append({"name": name, "precipitation_factor": round(factor, 2), "index": _blend(weather, antecedent)})
    values = [row["index"] for row in rows]
    score = round(0.25 * values[0] + 0.5 * values[1] + 0.25 * values[2], 1) if all(v is not None for v in values) else None
    baseline_24h = _risk_component(forecast24, distributions.get("rainfall_24h_mm"))
    baseline_72h = _risk_component(forecast72, distributions.get("rainfall_72h_mm"), 3)
    baseline_weather = baseline_24h if forecast_window_hours <= 24 else _mean([baseline_24h, baseline_72h])
    return {
        "score": score,
        "forecast_window_hours": forecast_window_hours,
        "weather_component": round(baseline_weather, 1) if baseline_weather is not None else None,
        "antecedent_weather_component": round(antecedent, 1) if antecedent is not None else None,
        "scenarios": rows,
        "confidence": "LOW" if terrain_missing or score is None else "LIMITED",
        "data_gaps": ["Official terrain susceptibility layer not integrated"] if terrain_missing else [],
        "scenario_spread_source": "district/season historical weather interquartile range" if anchor_values else "conservative default sensitivity range",
    }


def build_scenario_indices(features: Any) -> dict[str, Any]:
    """Return indices normalized to the district/season weather anchors."""
    today = datetime.now(TIMEZONE).date()
    season = _season(today.month)
    district = _district_key(features.location_name)
    hazards: dict[str, Any] = {}

    for hazard in ("flood", "landslide"):
        anchor = _select_anchor(hazard, district, season)
        distributions = anchor["distributions"]
        antecedent = _weighted_mean([
            (_risk_component(features.rain_7d_mm, distributions.get("rainfall_7d_mm"), 7), 0.7),
            (_rain_severity(features.api_14d, 14), 0.3),
        ])
        result = _make_rain_scenarios(
            features.forecast_rain_24h_mm,
            features.forecast_rain_72h_mm,
            antecedent,
            distributions,
            hazard,
            terrain_missing=hazard == "landslide" and features.terrain_ruggedness is None,
            forecast_window_hours=24 if hazard == "flood" else 72,
        )
        result["level"] = "EXPERIMENTAL_INDEX" if result["score"] is not None else "NOT_AVAILABLE"
        result["historical_anchor"] = anchor["metadata"]
        required_inputs = [
            features.forecast_rain_24h_mm,
            features.rain_7d_mm,
            features.api_14d,
            anchor["metadata"]["sample_count"] if anchor["metadata"]["sample_count"] >= 5 else None,
            features.terrain_ruggedness if hazard == "landslide" else True,
        ]
        if hazard != "flood":
            required_inputs.insert(1, features.forecast_rain_72h_mm)
        result["confidence_score"] = _input_coverage_score(required_inputs)
        result["confidence_score_basis"] = "Percentage of required weather/context inputs available; not prediction accuracy."
        if anchor["metadata"]["sample_count"] < 5:
            result["confidence"] = "LOW"
            result["data_gaps"].append("Fewer than five usable historical weather rows for this reference group")
        result["historical_reference"] = {
            "rainfall_24h_mm": _historical_stats(distributions.get("rainfall_24h_mm")),
            "rainfall_72h_mm": _historical_stats(distributions.get("rainfall_72h_mm")),
            "rainfall_7d_mm": _historical_stats(distributions.get("rainfall_7d_mm")),
        }
        hazards[hazard] = _apply_susceptibility_blend(hazard, result, features.location_name)

    anchor = _select_anchor("drought", district, season)
    distributions = anchor["distributions"]
    forecast_deficit_30 = _drought_deficit(features.seasonal_precip_30d_mm, features.seasonal_et0_30d_mm)
    forecast_deficit_90 = _drought_deficit(features.seasonal_precip_90d_mm, features.seasonal_et0_90d_mm)
    weather_component = _mean([forecast_deficit_30, forecast_deficit_90])
    recent_deficit_30 = _drought_deficit(features.precip_30d_mm, features.et0_30d_mm)
    recent_deficit_90 = _drought_deficit(features.precip_90d_mm, features.et0_90d_mm)
    recent_window_deficit = _mean([recent_deficit_30, recent_deficit_90])
    surface_moisture = features.recent_soil_moisture_surface if features.recent_soil_moisture_surface is not None else features.soil_moisture_0_7cm
    root_moisture = features.recent_soil_moisture_root if features.recent_soil_moisture_root is not None else features.soil_moisture_7_28cm
    surface_dryness = _soil_moisture_dryness(surface_moisture)
    root_dryness = _soil_moisture_dryness(root_moisture)
    recent_soil_dryness = _mean([surface_dryness, root_dryness])
    recent_5d_deficit = _drought_deficit(features.recent_precip_5d_mm, features.recent_et0_5d_mm)
    dry_spell = _clamp(features.cdd_count / 30 * 100) if features.cdd_count is not None else None
    recent_dry = _weighted_mean([
        (recent_window_deficit, 0.4),
        (recent_soil_dryness, 0.3),
        (recent_5d_deficit, 0.2),
        (dry_spell, 0.1),
    ])

    forecast_rain = (features.seasonal_precip_30d_mm, features.seasonal_precip_90d_mm)
    forecast_et0 = (features.seasonal_et0_30d_mm, features.seasonal_et0_90d_mm)
    long_anchor = distributions.get("rainfall_30d_mm") or distributions.get("rainfall_90d_mm")
    factors = _scenario_factors(long_anchor)
    scenarios = []
    for name, factor in zip(SCENARIO_NAMES, factors):
        weather = _mean([
            _drought_deficit(rain * factor if rain is not None else None, et0)
            for rain, et0 in zip(forecast_rain, forecast_et0)
        ])
        scenarios.append({"name": name, "precipitation_factor": round(factor, 2), "index": _blend(weather, recent_dry)})
    scenario_values = [row["index"] for row in scenarios]
    score = round(0.25 * scenario_values[0] + 0.5 * scenario_values[1] + 0.25 * scenario_values[2], 1) if all(v is not None for v in scenario_values) else None

    forecast_reasons = []
    for label, rain, et0, deficit in (
        ("30-day outlook", features.seasonal_precip_30d_mm, features.seasonal_et0_30d_mm, forecast_deficit_30),
        ("90-day outlook", features.seasonal_precip_90d_mm, features.seasonal_et0_90d_mm, forecast_deficit_90),
        ("Recent 30-day balance", features.precip_30d_mm, features.et0_30d_mm, recent_deficit_30),
        ("Recent 90-day balance", features.precip_90d_mm, features.et0_90d_mm, recent_deficit_90),
        ("Recent 5-day balance", features.recent_precip_5d_mm, features.recent_et0_5d_mm, recent_5d_deficit),
    ):
        if rain is None or et0 is None or et0 <= 0:
            forecast_reasons.append(f"{label}: unavailable")
        elif rain >= et0:
            forecast_reasons.append(f"{label}: rainfall {rain:.1f} mm meets/exceeds ET₀ {et0:.1f} mm; water-deficit component {deficit:.1f}/100")
        else:
            shortfall = (et0 - rain) / et0 * 100
            forecast_reasons.append(f"{label}: rainfall {rain:.1f} mm is {shortfall:.1f}% below ET₀ {et0:.1f} mm; water-deficit component {deficit:.1f}/100")

    drought_result = {
        "score": score,
        "level": "EXPERIMENTAL_INDEX" if score is not None else "NOT_AVAILABLE",
        "weather_component": round(weather_component, 1) if weather_component is not None else None,
        "antecedent_weather_component": round(recent_dry, 1) if recent_dry is not None else None,
        "reasons": forecast_reasons + [
            f"Surface soil-moisture dryness component: {surface_dryness:.1f}/100" if surface_dryness is not None else "Surface soil moisture: unavailable",
            f"Root-zone soil-moisture dryness component: {root_dryness:.1f}/100" if root_dryness is not None else "Root-zone soil moisture: unavailable",
            f"Consecutive dry days: {features.cdd_count}" if features.cdd_count is not None else "Consecutive dry days: unavailable",
            "Historical training CSV weather fields adjust scenario spread only; their proxy/synthetic targets are not used as event truth.",
        ],
        "component_breakdown": [
            {"label": "Forecast rainfall vs ET₀ (30/90 day)", "score": round(weather_component, 1) if weather_component is not None else None, "weight": "65% forecast component"},
            {"label": "Recent 30/90-day water balance", "score": round(recent_window_deficit, 1) if recent_window_deficit is not None else None, "weight": "40% of recent component"},
            {"label": "Recent soil-moisture dryness", "score": round(recent_soil_dryness, 1) if recent_soil_dryness is not None else None, "weight": "30% of recent component"},
            {"label": "Recent 5-day rainfall vs ET₀", "score": round(recent_5d_deficit, 1) if recent_5d_deficit is not None else None, "weight": "20% of recent component"},
            {"label": "Consecutive dry days", "score": round(dry_spell, 1) if dry_spell is not None else None, "weight": "10% of recent component"},
        ],
        "input_parameters": [
            {"label": "Forecast rainfall · 30 days", "value": features.seasonal_precip_30d_mm, "unit": "mm", "source": "Open-Meteo seasonal outlook"},
            {"label": "Forecast ET₀ · 30 days", "value": features.seasonal_et0_30d_mm, "unit": "mm", "source": "Open-Meteo seasonal outlook"},
            {"label": "Forecast rainfall · 90 days", "value": features.seasonal_precip_90d_mm, "unit": "mm", "source": "Open-Meteo seasonal outlook"},
            {"label": "Forecast ET₀ · 90 days", "value": features.seasonal_et0_90d_mm, "unit": "mm", "source": "Open-Meteo seasonal outlook"},
            {"label": "Recent rainfall · 30 days", "value": features.precip_30d_mm, "unit": "mm", "source": "ERA5-Land + recent model history"},
            {"label": "Recent ET₀ · 30 days", "value": features.et0_30d_mm, "unit": "mm", "source": "ERA5-Land + recent model history"},
            {"label": "Recent rainfall · 90 days", "value": features.precip_90d_mm, "unit": "mm", "source": "ERA5-Land + recent model history"},
            {"label": "Recent ET₀ · 90 days", "value": features.et0_90d_mm, "unit": "mm", "source": "ERA5-Land + recent model history"},
            {"label": "Rainfall · latest 5 days", "value": features.recent_precip_5d_mm, "unit": "mm", "source": "Open-Meteo recent model history"},
            {"label": "ET₀ · latest 5 days", "value": features.recent_et0_5d_mm, "unit": "mm", "source": "Open-Meteo recent model history"},
            {"label": "Surface soil moisture · 0–7 cm", "value": surface_moisture, "unit": "m³/m³", "source": "Open-Meteo recent model history or ERA5-Land"},
            {"label": "Root-zone soil moisture · 7–28 cm", "value": root_moisture, "unit": "m³/m³", "source": "Open-Meteo / ERA5-Land"},
            {"label": "Consecutive dry days", "value": features.cdd_count, "unit": "days", "source": "Daily rainfall below 2.5 mm"},
        ],
        "scenarios": scenarios,
        "confidence": "LIMITED" if score is not None and anchor["metadata"]["sample_count"] >= 5 else "LOW",
        "confidence_score": _input_coverage_score([
            features.seasonal_precip_30d_mm, features.seasonal_et0_30d_mm,
            features.seasonal_precip_90d_mm, features.seasonal_et0_90d_mm,
            features.precip_30d_mm, features.et0_30d_mm,
            features.precip_90d_mm, features.et0_90d_mm,
            features.recent_precip_5d_mm, features.recent_et0_5d_mm,
            surface_moisture, root_moisture, features.cdd_count,
            anchor["metadata"]["sample_count"] if anchor["metadata"]["sample_count"] >= 5 else None,
        ]),
        "confidence_score_basis": "Percentage of required weather/context inputs available; not prediction accuracy.",
        "data_gaps": [] if anchor["metadata"]["sample_count"] >= 5 else ["Historical drought weather reference is sparse or unavailable"],
        "scenario_spread_source": "district/season historical weather interquartile range" if long_anchor else "conservative default sensitivity range",
        "historical_anchor": anchor["metadata"],
        "historical_reference": {
            "rainfall_30d_mm": _historical_stats(distributions.get("rainfall_30d_mm")),
            "rainfall_90d_mm": _historical_stats(distributions.get("rainfall_90d_mm")),
        },
    }
    hazards["drought"] = _apply_susceptibility_blend("drought", drought_result, features.location_name)

    available = [item["score"] for item in hazards.values() if item["score"] is not None]
    composite = max(available) if available else None
    dominant = max((name for name, item in hazards.items() if item["score"] is not None), key=lambda name: hazards[name]["score"], default=None)
    complete = sum(item["score"] is not None for item in hazards.values())
    return {
        "score": round(composite, 1) if composite is not None else None,
        "dominant_hazard": dominant,
        "confidence_score": hazards[dominant]["confidence_score"] if dominant else None,
        "confidence_score_basis": "Percentage of required inputs available for the hazard that sets the overall index; not prediction accuracy.",
        "hazards": hazards,
        "confidence": "LOW" if any(item["confidence"] == "LOW" for item in hazards.values()) else "LIMITED",
        "hazards_available": complete,
        "formula": {
            "live_weather_scenario_weight": LIVE_WEATHER_INDEX_WEIGHT,
            "historical_susceptibility_weight": HISTORICAL_SUSCEPTIBILITY_WEIGHT,
            "weather_forecast_weight_within_live_scenario": WEATHER_WEIGHT,
            "recent_weather_context_weight_within_live_scenario": ANTECEDENT_WEIGHT,
        },
        "scenario_method": "Precipitation sensitivity cases use district/season historical weather spread where available. Each weather scenario is blended 60/40 with the static historical susceptibility index when that source has a district value. Scenarios are simulated, not observed hazard events.",
        "historical_data_note": "Static susceptibility layers contribute 40% to the preparedness index where available. Their source, spatial resolution, and quality are reported per hazard; source scores are not disaster probabilities. Training event labels and risk targets are not used.",
        "limitations": [
            "Index values are not percentages or probabilities of a disaster.",
            "Historical weather anchors include modeled, proxy, or synthetically filled values and are not observed hazard outcomes.",
            "Where available, scenarios compare against district/season empirical rainfall distributions; sparse seasons fall back to a broader district or statewide group.",
            "Historical susceptibility inputs are coarse and unverified; flood and landslide sources do not provide reliable taluk-scale boundaries, and the drought workbook has no supplied publication date or method.",
        ],
    }
