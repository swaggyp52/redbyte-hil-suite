import pytest

from hil_core.insights import Insight


def test_insight_to_dict_includes_canonical_and_legacy_aliases():
    insight = Insight(
        timestamp=12.5,
        event_type="thd",
        severity="warning",
        message="Elevated THD",
        metrics={"thd": 6.4},
        phase="A",
    )

    payload = insight.to_dict()

    assert payload["ts"] == pytest.approx(12.5)
    assert payload["timestamp"] == pytest.approx(12.5)
    assert payload["type"] == "thd"
    assert payload["description"] == "Elevated THD"
    assert payload["message"] == "Elevated THD"
    assert payload["metrics"] == {"thd": 6.4}
    assert payload["phase"] == "A"


@pytest.mark.parametrize(
    "payload, expected",
    [
        (
            {
                "ts": 1.25,
                "type": "thd",
                "severity": "warning",
                "description": "THD high",
                "metrics": {"thd": 7.1},
                "phase": "B",
            },
            (1.25, "thd", "warning", "THD high", {"thd": 7.1}, "B"),
        ),
        (
            {
                "timestamp": 2.5,
                "event_type": "frequency",
                "severity": "critical",
                "message": "Drift",
                "metrics": {"frequency": 61.3},
            },
            (2.5, "frequency", "critical", "Drift", {"frequency": 61.3}, None),
        ),
        (
            {
                "ts": None,
                "timestamp": 4.2,
                "type": "",
                "event_type": "thd",
                "description": "",
                "message": "Legacy message",
                "metrics": None,
            },
            (4.2, "thd", "info", "Legacy message", {}, None),
        ),
    ],
)
def test_insight_from_dict_supports_canonical_and_legacy_shapes(payload, expected):
    insight = Insight.from_dict(payload)

    assert insight.timestamp == pytest.approx(expected[0])
    assert insight.event_type == expected[1]
    assert insight.severity == expected[2]
    assert insight.message == expected[3]
    assert insight.metrics == expected[4]
    assert insight.phase == expected[5]


def test_insight_from_dict_handles_invalid_timestamp_and_metrics_gracefully():
    payload = {
        "timestamp": "not-a-number",
        "type": "thd",
        "message": "Malformed payload",
        "metrics": None,
    }

    insight = Insight.from_dict(payload)

    assert insight.timestamp == pytest.approx(0.0)
    assert insight.metrics == {}
    assert insight.message == "Malformed payload"


def test_insight_from_dict_parses_numeric_timestamp_strings():
    payload = {
        "timestamp": "123.4",
        "event_type": "unbalance",
        "message": "Phase mismatch",
        "metrics": {"unbalance": 12.0},
    }

    insight = Insight.from_dict(payload)

    assert insight.timestamp == pytest.approx(123.4)
    assert insight.event_type == "unbalance"
