from types import SimpleNamespace

from app.routers.dashboard import serialize_risk


def test_dashboard_calculates_baseline_from_complete_hazard_labels():
    hazards = SimpleNamespace(
        flood_level="HIGH",
        landslide_level="LOW",
        drought_level="MODERATE",
        recorded_at=None,
    )

    result = serialize_risk(None, hazards)

    assert result["flood_risk"] == 75
    assert result["landslide_risk"] == 25
    assert result["drought_risk"] == 50
    assert result["overall_risk"] == 50
    assert result["score_type"] == "illustrative_baseline"


def test_dashboard_does_not_calculate_when_a_required_hazard_is_missing():
    hazards = SimpleNamespace(
        flood_level="HIGH",
        landslide_level=None,
        drought_level="MODERATE",
        recorded_at=None,
    )

    assert serialize_risk(None, hazards) is None
