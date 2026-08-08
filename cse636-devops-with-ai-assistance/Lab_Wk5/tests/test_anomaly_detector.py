import numpy as np
import pandas as pd

from anomaly_detector import (
    ANOMALY_END,
    ANOMALY_START,
    evaluate,
    ground_truth,
    run_isolation_forest,
)
from generate_data import generate_metrics


def test_ground_truth_marks_exactly_the_injected_window():
    df = generate_metrics(n=500, seed=42)
    gt = ground_truth(df)
    assert gt.sum() == ANOMALY_END - ANOMALY_START + 1
    assert gt[ANOMALY_START] == 1
    assert gt[ANOMALY_END] == 1
    assert gt[ANOMALY_START - 1] == 0
    assert gt[ANOMALY_END + 1] == 0


def test_accuracy_trap_all_normal_predictions_score_zero_recall():
    """A detector that predicts 'normal' for everything scores ~98% accuracy
    on this ~98%-normal dataset but should show recall=0 for the Anomaly
    class -- the exact trap the lab doc calls out."""
    df = generate_metrics(n=500, seed=42)
    df["is_anomaly"] = False  # never flags anything

    metrics = evaluate(df)

    assert metrics["recall"] == 0.0
    assert metrics["precision"] == 0.0
    assert metrics["f1"] == 0.0
    assert metrics["n_flagged"] == 0

    accuracy = (df["is_anomaly"].astype(int).to_numpy() == ground_truth(df)).mean()
    assert accuracy > 0.95  # high accuracy, despite catching zero anomalies


def test_perfect_predictions_score_perfect_metrics():
    df = generate_metrics(n=500, seed=42)
    df["is_anomaly"] = ground_truth(df).astype(bool)

    metrics = evaluate(df)

    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0


def test_isolation_forest_recovers_the_injected_incident():
    df = generate_metrics(n=500, seed=42)
    result = run_isolation_forest(df, contamination=0.04, random_state=42)
    metrics = evaluate(result)

    # Not a tautology: the model must actually find the incident from the
    # raw metrics, not from the ground-truth labels.
    assert metrics["recall"] >= 0.9
    assert metrics["precision"] >= 0.5


def test_contamination_increases_number_flagged():
    df = generate_metrics(n=500, seed=42)
    counts = []
    for contamination in (0.01, 0.04, 0.10):
        result = run_isolation_forest(df, contamination=contamination, random_state=42)
        counts.append(int(result["is_anomaly"].sum()))

    assert counts == sorted(counts)
    assert counts[0] < counts[-1]
