"""Anomaly detection over the metrics dataset: Isolation Forest (primary) and
DBSCAN (bonus comparison), plus precision/recall/F1 evaluation against the
known ground-truth incident window.

Run with: uv run python src/anomaly_detector.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report, f1_score, precision_score, recall_score
from sklearn.preprocessing import StandardScaler

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FEATURES = ["cpu_pct", "error_rate", "latency_p99_ms"]
ANOMALY_START, ANOMALY_END = 200, 215  # inclusive


def load_metrics(path: Path | None = None) -> pd.DataFrame:
    path = path or DATA_DIR / "metrics_sample.csv"
    return pd.read_csv(path, parse_dates=["timestamp"])


def ground_truth(df: pd.DataFrame) -> np.ndarray:
    idx = np.arange(len(df))
    return ((idx >= ANOMALY_START) & (idx <= ANOMALY_END)).astype(int)


def scale_features(df: pd.DataFrame) -> np.ndarray:
    scaler = StandardScaler()
    return scaler.fit_transform(df[FEATURES])


def run_isolation_forest(
    df: pd.DataFrame, contamination: float = 0.04, random_state: int = 42
) -> pd.DataFrame:
    X = scale_features(df)
    model = IsolationForest(
        n_estimators=200, contamination=contamination, random_state=random_state
    )
    model.fit(X)
    out = df.copy()
    out["anomaly_score"] = model.decision_function(X)
    out["is_anomaly"] = model.predict(X) == -1
    return out


def run_dbscan(df: pd.DataFrame, eps: float = 1.0, min_samples: int = 5) -> pd.DataFrame:
    X = scale_features(df)
    model = DBSCAN(eps=eps, min_samples=min_samples)
    labels = model.fit_predict(X)
    out = df.copy()
    out["cluster"] = labels
    out["is_anomaly"] = labels == -1  # DBSCAN's noise points are the "anomalies"
    return out


def evaluate(df_with_predictions: pd.DataFrame) -> dict:
    y_true = ground_truth(df_with_predictions)
    y_pred = df_with_predictions["is_anomaly"].astype(int).to_numpy()
    return {
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "n_flagged": int(y_pred.sum()),
        "report": classification_report(
            y_true, y_pred, target_names=["Normal", "Anomaly"], zero_division=0
        ),
    }


def main() -> None:
    df = load_metrics()

    print("=== Isolation Forest: contamination sweep ===")
    for contamination in (0.01, 0.04, 0.10):
        result = run_isolation_forest(df, contamination=contamination)
        metrics = evaluate(result)
        print(
            f"contamination={contamination:<5} "
            f"flagged={metrics['n_flagged']:<4} "
            f"precision={metrics['precision']:.3f} "
            f"recall={metrics['recall']:.3f} "
            f"f1={metrics['f1']:.3f}"
        )

    print("\n=== Isolation Forest (contamination=0.04) full report ===")
    if_result = run_isolation_forest(df, contamination=0.04)
    print(evaluate(if_result)["report"])

    print("=== DBSCAN comparison (eps=1.0, min_samples=5) ===")
    db_result = run_dbscan(df, eps=1.0, min_samples=5)
    db_metrics = evaluate(db_result)
    print(db_metrics["report"])


if __name__ == "__main__":
    main()
