"""Rule-based alert grouping.

Real alerting systems (PagerDuty, Opsgenie, Alertmanager) fire one alert per
metric/threshold breach, which means a single incident often produces a
flood of individual alerts. This module expands anomalous rows from the
anomaly detector into per-metric alerts, then groups them with simple
time-proximity (gap) clustering so an on-call engineer sees "one incident"
instead of dozens of unrelated pings.

Run with: uv run python src/alert_grouper.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from anomaly_detector import FEATURES, load_metrics, run_isolation_forest

# Per-metric alert thresholds (domain knowledge, not learned) - a metric only
# generates its own alert if it individually looks unhealthy, even within a
# row IsolationForest already flagged as anomalous.
METRIC_THRESHOLDS = {
    "cpu_pct": 70.0,
    "error_rate": 0.02,
    "latency_p99_ms": 500.0,
}

GROUP_GAP = pd.Timedelta(minutes=3)


@dataclass
class Alert:
    timestamp: pd.Timestamp
    metric: str
    value: float
    threshold: float

    def __str__(self) -> str:
        return f"[{self.timestamp}] {self.metric}={self.value:.2f} (threshold={self.threshold})"


@dataclass
class AlertGroup:
    alerts: list[Alert] = field(default_factory=list)

    @property
    def start(self) -> pd.Timestamp:
        return min(a.timestamp for a in self.alerts)

    @property
    def end(self) -> pd.Timestamp:
        return max(a.timestamp for a in self.alerts)

    @property
    def metrics_involved(self) -> list[str]:
        return sorted({a.metric for a in self.alerts})

    def summary(self) -> str:
        return (
            f"{self.start} -> {self.end} | {len(self.alerts)} alerts | "
            f"metrics={self.metrics_involved}"
        )


def build_alerts(df_flagged: pd.DataFrame) -> list[Alert]:
    """One alert per (anomalous row, breached metric)."""
    alerts: list[Alert] = []
    anomalous = df_flagged[df_flagged["is_anomaly"]]
    for _, row in anomalous.iterrows():
        for metric in FEATURES:
            threshold = METRIC_THRESHOLDS[metric]
            if row[metric] > threshold:
                alerts.append(Alert(row["timestamp"], metric, row[metric], threshold))
    return alerts


def group_alerts(alerts: list[Alert], gap: pd.Timedelta = GROUP_GAP) -> list[AlertGroup]:
    """Gap-based temporal clustering: sort by time, start a new group
    whenever the time since the previous alert exceeds `gap`."""
    if not alerts:
        return []

    ordered = sorted(alerts, key=lambda a: a.timestamp)
    groups: list[AlertGroup] = [AlertGroup(alerts=[ordered[0]])]

    for alert in ordered[1:]:
        current_group = groups[-1]
        if alert.timestamp - current_group.end <= gap:
            current_group.alerts.append(alert)
        else:
            groups.append(AlertGroup(alerts=[alert]))

    return groups


def main() -> None:
    df = load_metrics()
    flagged = run_isolation_forest(df, contamination=0.04)

    alerts = build_alerts(flagged)
    print(f"Generated {len(alerts)} raw per-metric alerts from {flagged['is_anomaly'].sum()} anomalous rows")
    for a in alerts[:10]:
        print(" ", a)
    if len(alerts) > 10:
        print(f"  ... and {len(alerts) - 10} more")

    groups = group_alerts(alerts)
    print(f"\nGrouped into {len(groups)} incident group(s):")
    for i, g in enumerate(groups, 1):
        print(f"  Group {i}: {g.summary()}")


if __name__ == "__main__":
    main()
