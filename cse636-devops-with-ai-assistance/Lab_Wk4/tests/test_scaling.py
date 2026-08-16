import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scaling import required_replicas, recommend_replicas, ScalingDecision


def test_required_replicas_scales_up():
    assert required_replicas(4, 85, target_cpu_per_replica=60) == 6


def test_required_replicas_clamps_to_min():
    assert required_replicas(4, 10, target_cpu_per_replica=60, min_replicas=2) == 2


def test_required_replicas_clamps_to_max():
    assert required_replicas(4, 500, target_cpu_per_replica=60, max_replicas=10) == 10


def test_required_replicas_rejects_bad_input():
    with pytest.raises(ValueError):
        required_replicas(0, 50)
    with pytest.raises(ValueError):
        required_replicas(4, -1)
    with pytest.raises(ValueError):
        required_replicas(4, 50, target_cpu_per_replica=0)
    with pytest.raises(ValueError):
        required_replicas(4, 50, min_replicas=10, max_replicas=5)


def test_scaling_decision_action_labels():
    assert ScalingDecision(4, 6, 80.0).action == "Scale UP by 2 replica(s)"
    assert ScalingDecision(4, 2, 20.0).action == "Scale DOWN by 2 replica(s)"
    assert ScalingDecision(4, 4, 60.0).action == "No change"


def test_recommend_replicas_uses_upper_ci_within_horizon():
    now = pd.Timestamp("2025-01-01T00:00:00")
    forecast_df = pd.DataFrame({
        "ds": pd.date_range(now, periods=12, freq="5min"),
        "yhat_upper": [50, 55, 90, 60, 58, 57, 56, 55, 200, 200, 200, 200],  # last 4 outside horizon
    })
    decision = recommend_replicas(forecast_df, current_replicas=4, horizon_minutes=30, now=now)
    # within (now, now+30min] are indices 1..6 -> max yhat_upper = 90
    assert decision.max_predicted_cpu == 90
    assert decision.recommended_replicas == required_replicas(4, 90)


def test_recommend_replicas_falls_back_to_tail_when_horizon_empty():
    now = pd.Timestamp("2030-01-01")  # far past every row in the forecast
    forecast_df = pd.DataFrame({
        "ds": pd.date_range("2025-01-01", periods=10, freq="5min"),
        "yhat_upper": [10] * 9 + [99],
    })
    decision = recommend_replicas(forecast_df, current_replicas=2, horizon_minutes=30, now=now)
    assert decision.max_predicted_cpu == 99
