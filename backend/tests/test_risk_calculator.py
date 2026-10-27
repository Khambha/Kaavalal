
import pytest

from app.services.risk_calculator import (
    HAZARD_LEVEL_SCORES,
    score_hazard_level,
)


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        ("LOW", 25.0),
        ("MODERATE", 50.0),
        ("HIGH", 75.0),
        ("VERY HIGH", 100.0),
        ("moderate", 50.0),
        ("  very   high  ", 100.0),
    ],
)
def test_score_hazard_level_recognized_values(level, expected):
    assert score_hazard_level(level) == expected


@pytest.mark.parametrize(
    "level",
    [
        None,
        "",
        " ",
        "UNKNOWN",
        "SEVERE",
        "LOW RISK",
    ],
)
def test_score_hazard_level_unknown_or_missing_values(level):
    assert score_hazard_level(level) is None


def test_score_mapping_contains_only_expected_prototype_levels():
    assert HAZARD_LEVEL_SCORES == {
        "LOW": 25.0,
        "MODERATE": 50.0,
        "HIGH": 75.0,
        "VERY HIGH": 100.0,
    }
