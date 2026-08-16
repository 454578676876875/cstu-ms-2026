"""Translate a CPU forecast into a Kubernetes scaling recommendation.

Dependency-free and pure, same shape as project/forecasting/scaling.py, so it's easy to test in
isolation from the Prophet model that feeds it (forecast.py).
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class ScalingDecision:
    current_replicas: int
    recommended_replicas: int
    max_predicted_cpu: float

    @property
    def delta(self) -> int:
        return self.recommended_replicas - self.current_replicas

    @property
    def action(self) -> str:
        if self.delta > 0:
            return f"Scale UP by {self.delta} replica(s)"
        if self.delta < 0:
            return f"Scale DOWN by {-self.delta} replica(s)"
        return "No change"


def required_replicas(
    current_replicas: int,
    predicted_cpu: float,
    target_cpu_per_replica: float = 60.0,
    min_replicas: int = 2,
    max_replicas: int = 50,
) -> int:
    """Replica count needed to keep CPU near the target.

    >>> required_replicas(4, 85, target_cpu_per_replica=60)
    6
    >>> required_replicas(4, 10, target_cpu_per_replica=60)  # clamps to min
    2
    """
    if current_replicas < 1:
        raise ValueError("current_replicas must be >= 1")
    if predicted_cpu < 0:
        raise ValueError("predicted_cpu must be >= 0")
    if target_cpu_per_replica <= 0:
        raise ValueError("target_cpu_per_replica must be > 0")
    if min_replicas > max_replicas:
        raise ValueError("min_replicas must be <= max_replicas")

    raw = math.ceil(current_replicas * predicted_cpu / target_cpu_per_replica)
    return max(min_replicas, min(max_replicas, raw))


def recommend_replicas(
    forecast_df,
    current_replicas: int,
    target_cpu_pct: float = 60.0,
    horizon_minutes: int = 30,
    min_replicas: int = 2,
    max_replicas: int = 50,
    now=None,
) -> ScalingDecision:
    """Given a Prophet forecast DataFrame (columns ds, yhat_upper), recommend a replica
    count for the max predicted CPU (upper 80% CI, per the lab's rationale: a safety margin
    for scale-up beats an under-provisioned spike) within the next horizon_minutes."""
    import pandas as pd

    now = now or pd.Timestamp.now()
    cutoff = now + pd.Timedelta(minutes=horizon_minutes)
    upcoming = forecast_df[(forecast_df["ds"] > now) & (forecast_df["ds"] <= cutoff)]

    if upcoming.empty:
        upcoming = forecast_df.tail(max(1, horizon_minutes // 5))

    max_cpu = float(upcoming["yhat_upper"].max())
    rec = required_replicas(current_replicas, max_cpu, target_cpu_pct, min_replicas, max_replicas)
    return ScalingDecision(
        current_replicas=current_replicas, recommended_replicas=rec, max_predicted_cpu=max_cpu
    )
