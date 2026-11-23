"""Conservative inference contract for live district hazard features.

No production-calibrated artifacts currently exist. The service therefore
reports inputs and model availability without inventing probabilities.
"""

from datetime import datetime, timedelta, timezone
import logging
import json
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any

import joblib

from app.services.feature_pipeline import build_hazard_features
from app.services.scenario_risk import build_scenario_indices

_CACHE: dict[str, tuple[datetime, dict[str, Any]]] = {}
_CACHE_LOCK = Lock()
_CACHE_TTL = timedelta(minutes=20)
logger = logging.getLogger(__name__)
PRODUCTION_DIR = Path(__file__).resolve().parents[1] / "ml_model" / "production"


@lru_cache(maxsize=1)
def _load_approved_registry() -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Load only an explicitly reviewed registry and its three model bundles."""
    registry_path = PRODUCTION_DIR / "model_registry.json"
    if not registry_path.is_file():
        return None
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        if registry.get("status") != "PRODUCTION_APPROVED" or registry.get("probabilities_calibrated") is not True:
            return None
        if registry.get("provenance") not in {"VERIFIED_HISTORICAL", "PROXY_CALIBRATED"}:
            return None
        if not isinstance(registry.get("composite_thresholds"), dict):
            return None
        loaded = {}
        for hazard in ("flood", "landslide", "drought"):
            item = registry.get("hazards", {}).get(hazard, {})
            artifact = (PRODUCTION_DIR / item.get("artifact", "")).resolve()
            if PRODUCTION_DIR.resolve() not in artifact.parents or not artifact.is_file():
                return None
            if not item.get("feature_names") or not isinstance(item.get("feature_names"), list):
                return None
            loaded[hazard] = {"bundle": joblib.load(artifact), "metadata": item}
        return registry, loaded
    except Exception:
        logger.exception("Unable to load the approved risk model registry")
        return None


def _predict_approved(features: Any, registry_data: tuple[dict[str, Any], dict[str, Any]]) -> dict[str, Any] | None:
    registry, models = registry_data
    if features.feature_completeness_ratio < 0.70:
        return None
    feature_values = features.model_dump()
    predictions: dict[str, float] = {}
    for hazard, item in models.items():
        columns = item["metadata"]["feature_names"]
        values = [feature_values.get(name) for name in columns]
        if any(value is None for value in values):
            return None
        estimator = item["bundle"]
        if isinstance(estimator, dict):
            estimator = estimator.get("model") or estimator.get("estimator")
        if estimator is None or not hasattr(estimator, "predict_proba"):
            return None
        classes = list(getattr(estimator, "classes_", []))
        positive_label = item["metadata"].get("positive_label", 1)
        if positive_label not in classes:
            return None
        probability = float(estimator.predict_proba([values])[0][classes.index(positive_label)])
        if not 0 <= probability <= 1:
            return None
        predictions[hazard] = probability
    scores = list(predictions.values())
    composite = 100 * (0.65 * max(scores) + 0.35 * (sum(scores) / len(scores)))
    dominant = max(predictions, key=predictions.get)
    score = round(composite, 1)
    thresholds = registry["composite_thresholds"]
    required_thresholds = ("moderate", "high", "critical")
    if any(not isinstance(thresholds.get(key), (int, float)) for key in required_thresholds):
        return None
    level = "CRITICAL" if score >= thresholds["critical"] else "HIGH" if score >= thresholds["high"] else "MODERATE" if score >= thresholds["moderate"] else "LOW"
    calibration = registry.get("calibration_reliability", "LOW")
    completeness_band = "LOW" if features.feature_completeness_ratio < 0.85 else "MEDIUM" if features.feature_completeness_ratio < 0.95 else "HIGH"
    confidence = "LOW" if "LOW" in {calibration, completeness_band} else "MEDIUM" if "MEDIUM" in {calibration, completeness_band} else "HIGH"
    return {
        "status": "OK",
        "composite_score": score,
        "risk_level": level,
        "dominant_hazard": dominant,
        "hazards": {
            name: {"probability": round(value, 4), "score": round(value * 100, 1), "level": "MODEL_OUTPUT", "top_drivers": []}
            for name, value in predictions.items()
        },
        "model_provenance": registry["provenance"],
        "model_version": registry.get("model_version"),
        "confidence": confidence,
    }


def assess_location(location_id: int, name: str, latitude: float, longitude: float) -> dict[str, Any]:
    key = f"district:{location_id}"
    now = datetime.now(timezone.utc)
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and now - cached[0] < _CACHE_TTL:
            return cached[1]
    try:
        features, feeds = build_hazard_features(latitude, longitude, name, location_id)
        approved_registry = _load_approved_registry()
        inference = _predict_approved(features, approved_registry) if approved_registry else None
        experimental = build_scenario_indices(features)
        ready = inference is not None
        has_experimental = experimental["score"] is not None
        hazard_values = inference["hazards"] if ready else {
            name: {
                **item,
                "probability": None,
                "top_drivers": [],
            }
            for name, item in experimental["hazards"].items()
        }
        payload = {
            "district_id": location_id,
            "district_name": name,
            "status": inference["status"] if ready else "EXPERIMENTAL_INDEX" if has_experimental else "INSUFFICIENT_DATA",
            "composite_score": inference["composite_score"] if ready else experimental["score"],
            "preparedness_index": None if ready else experimental,
            "score_semantics": "CALIBRATED_PROBABILITY" if ready else "EXPERIMENTAL_INDEX_NOT_PROBABILITY",
            "risk_level": inference["risk_level"] if ready else "EXPERIMENTAL" if has_experimental else "NO_DATA",
            "dominant_hazard": inference["dominant_hazard"] if ready else experimental["dominant_hazard"],
            "hazards": hazard_values,
            "uncertainty": {
                "confidence": inference["confidence"] if ready else experimental["confidence"],
                "confidence_score": inference.get("confidence_score") if ready else experimental["confidence_score"],
                "confidence_score_basis": None if ready else experimental["confidence_score_basis"],
                "feature_completeness": features.feature_completeness_ratio,
                "forecast_window_hours": 72,
            },
            "weather_features": features.model_dump(mode="json"),
            "metadata": {
                "source": "LIVE_ML_ENGINE" if ready else "OPEN_METEO_EXPERIMENTAL_SCENARIOS" if has_experimental else "LIVE_WEATHER_FEATURES",
                "model_provenance": inference["model_provenance"] if ready else "UNAVAILABLE",
                "model_version": inference["model_version"] if ready else None,
                "weather_updated_at": features.weather_fetched_at_utc.isoformat(),
                "reason": None if ready else "Experimental scenario index only; a calibrated production probability is not available.",
                "weather_feeds_unavailable": features.unavailable_feeds,
                "weather_provider_limitations": feeds.get("limitations", []),
                "index_limitations": experimental["limitations"],
            },
        }
    except Exception as exc:
        logger.exception("Live risk feature collection failed for location %s", location_id)
        payload = {
            "district_id": location_id,
            "district_name": name,
            "status": "INSUFFICIENT_DATA",
            "composite_score": None,
            "risk_level": "NO_DATA",
            "dominant_hazard": None,
            "hazards": {h: {"probability": None, "score": None, "level": "NOT_AVAILABLE", "top_drivers": []}
                        for h in ("flood", "landslide", "drought")},
            "uncertainty": {"confidence": "LOW", "feature_completeness": 0.0, "forecast_window_hours": 72},
            "weather_features": None,
            "metadata": {"source": "LIVE_WEATHER_FEATURES", "model_provenance": "UNAVAILABLE",
                         "model_version": None, "weather_updated_at": None,
                         "reason": f"Weather feature retrieval failed: {type(exc).__name__}"},
        }
    if payload["weather_features"] is not None:
        with _CACHE_LOCK:
            _CACHE[key] = (now, payload)
    return payload
