"""Capstone integration point: prints a JSON anomaly-detection signal for the pipeline
orchestrator (../capstone/pipeline.py) to consume as Stage 4 (Observability) -> Stage 5
(Auto-remediate) input. Reuses the real detector in anomaly_detector.py unchanged -- this is
just a JSON-shaped entry point, no new detection logic.
"""
import json

from anomaly_detector import ANOMALY_END, ANOMALY_START, evaluate, load_metrics, run_isolation_forest


def build_signal():
    df = load_metrics()
    result = run_isolation_forest(df, contamination=0.04)
    metrics = evaluate(result)
    flagged_idx = result.index[result["is_anomaly"]].tolist()
    return {
        "anomaly_detected": metrics["n_flagged"] > 0,
        "n_flagged": metrics["n_flagged"],
        "precision": round(metrics["precision"], 3),
        "recall": round(metrics["recall"], 3),
        "f1": round(metrics["f1"], 3),
        "first_flagged_index": flagged_idx[0] if flagged_idx else None,
        "ground_truth_incident_window": [ANOMALY_START, ANOMALY_END],
    }


if __name__ == "__main__":
    print(json.dumps(build_signal()))
