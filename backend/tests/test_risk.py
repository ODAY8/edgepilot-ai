"""Tests proving the risk-assessment service is fully deterministic.

assess_risk() must be a pure function of (event type, confidence): the
same inputs always produce the same RiskAssessment, with no randomness
anywhere in the calculation.
"""

from app.services.risk import _DEFAULT, _RISK_TABLE, assess_risk
from app.services.vision import Detection


def make_detection(event_type: str, confidence: float) -> Detection:
    return Detection(type=event_type, label=event_type, confidence=confidence, context="test context")


def test_repeated_identical_detection_produces_identical_risk():
    detection = make_detection("restricted_area_entry", 0.94)
    results = [assess_risk(detection) for _ in range(50)]

    first = results[0]
    for result in results:
        assert result.level == first.level
        assert result.score == first.score


def test_repeated_identical_detection_across_all_known_event_types():
    for event_type, (expected_level, _) in _RISK_TABLE.items():
        detection = make_detection(event_type, 0.87)
        results = [assess_risk(detection) for _ in range(20)]

        assert all(r.level == expected_level for r in results)
        scores = {r.score for r in results}
        assert len(scores) == 1, f"{event_type} produced varying scores: {scores}"


def test_known_event_types_map_to_expected_risk_levels():
    assert assess_risk(make_detection("restricted_area_entry", 0.9)).level == "HIGH"
    assert assess_risk(make_detection("forklift_near_miss", 0.9)).level == "HIGH"
    assert assess_risk(make_detection("ppe_violation", 0.9)).level == "MEDIUM"
    assert assess_risk(make_detection("unattended_object", 0.9)).level == "MEDIUM"
    assert assess_risk(make_detection("normal_activity", 0.9)).level == "LOW"


def test_score_stays_within_the_event_types_band():
    for event_type, (_, (low, high)) in _RISK_TABLE.items():
        for confidence in (0.0, 0.25, 0.5, 0.75, 1.0):
            result = assess_risk(make_detection(event_type, confidence))
            assert low <= result.score <= high, (
                f"{event_type} at confidence {confidence} scored {result.score}, "
                f"outside band [{low}, {high}]"
            )


def test_higher_confidence_never_produces_a_lower_score():
    for event_type in _RISK_TABLE:
        scores = [assess_risk(make_detection(event_type, c)).score for c in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)]
        assert scores == sorted(scores), f"{event_type} scores were not monotonic: {scores}"


def test_unknown_event_type_falls_back_to_default_band_deterministically():
    detection = make_detection("some_future_event_type_not_in_table", 0.7)
    results = [assess_risk(detection) for _ in range(20)]

    expected_level, (low, high) = _DEFAULT
    assert all(r.level == expected_level for r in results)
    assert len({r.score for r in results}) == 1
    assert low <= results[0].score <= high


def test_out_of_range_confidence_is_clamped_not_crashed():
    low_conf = assess_risk(make_detection("ppe_violation", -0.5))
    high_conf = assess_risk(make_detection("ppe_violation", 1.5))

    _, (low, high) = _RISK_TABLE["ppe_violation"]
    assert low_conf.score == low
    assert high_conf.score == high
