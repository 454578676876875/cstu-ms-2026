import pandas as pd
import pytest

from alert_grouper import Alert, METRIC_THRESHOLDS, build_alerts, group_alerts


def _row(ts, cpu, error_rate, latency, is_anomaly=True):
    return {
        "timestamp": pd.Timestamp(ts),
        "cpu_pct": cpu,
        "error_rate": error_rate,
        "latency_p99_ms": latency,
        "is_anomaly": is_anomaly,
    }


def test_build_alerts_only_fires_for_breached_metrics():
    # cpu breaches, error_rate and latency stay under threshold
    df = pd.DataFrame([_row("2025-01-01 00:00", cpu=90.0, error_rate=0.001, latency=100.0)])
    alerts = build_alerts(df)

    assert len(alerts) == 1
    assert alerts[0].metric == "cpu_pct"


def test_build_alerts_ignores_non_anomalous_rows():
    df = pd.DataFrame(
        [_row("2025-01-01 00:00", cpu=90.0, error_rate=0.5, latency=9000.0, is_anomaly=False)]
    )
    alerts = build_alerts(df)
    assert alerts == []


def test_build_alerts_can_fire_multiple_metrics_per_row():
    df = pd.DataFrame([_row("2025-01-01 00:00", cpu=90.0, error_rate=0.5, latency=9000.0)])
    alerts = build_alerts(df)
    assert {a.metric for a in alerts} == set(METRIC_THRESHOLDS.keys())


def test_group_alerts_empty_input():
    assert group_alerts([]) == []


def test_group_alerts_splits_on_gap():
    # two alerts 1 minute apart (same group), then one 10 minutes later (new group)
    alerts = [
        Alert(pd.Timestamp("2025-01-01 00:00"), "cpu_pct", 90.0, 70.0),
        Alert(pd.Timestamp("2025-01-01 00:01"), "error_rate", 0.5, 0.02),
        Alert(pd.Timestamp("2025-01-01 00:20"), "latency_p99_ms", 9000.0, 500.0),
    ]

    groups = group_alerts(alerts, gap=pd.Timedelta(minutes=3))

    assert len(groups) == 2
    assert len(groups[0].alerts) == 2
    assert len(groups[1].alerts) == 1
    assert groups[1].metrics_involved == ["latency_p99_ms"]


def test_group_alerts_merges_within_gap_regardless_of_order():
    alerts = [
        Alert(pd.Timestamp("2025-01-01 00:05"), "cpu_pct", 90.0, 70.0),
        Alert(pd.Timestamp("2025-01-01 00:00"), "error_rate", 0.5, 0.02),
    ]
    groups = group_alerts(alerts, gap=pd.Timedelta(minutes=10))
    assert len(groups) == 1
    assert groups[0].start == pd.Timestamp("2025-01-01 00:00")
    assert groups[0].end == pd.Timestamp("2025-01-01 00:05")
