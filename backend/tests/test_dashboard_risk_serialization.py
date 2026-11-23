from types import SimpleNamespace

from app.routers.dashboard import serialize_risk


def test_dashboard_does_not_infer_numeric_scores_from_hazard_labels():
    hazards = SimpleNamespace(
        flood_level="HIGH",
        landslide_level="LOW",
        drought_level="MODERATE",
        recorded_at=None,
    )

    result = serialize_risk(None, hazards)

    # Hazard labels describe categories; they are not calibrated numeric risks.
    assert result is None


def test_dashboard_does_not_calculate_when_a_required_hazard_is_missing():
    hazards = SimpleNamespace(
        flood_level="HIGH",
        landslide_level=None,
        drought_level="MODERATE",
        recorded_at=None,
    )

    assert serialize_risk(None, hazards) is None
