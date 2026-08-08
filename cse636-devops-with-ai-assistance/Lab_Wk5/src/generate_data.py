"""Generate the synthetic datasets used by the Week 5 lab and assignment:

- data/metrics_sample.csv  : 500 one-minute samples of cpu/error_rate/latency,
                              with an injected incident at indices 200-215.
- data/logs_sample.txt     : 200+ structured log lines covering the same
                              time range, with correlated ERROR/WARN bursts
                              during the incident window.

Run with: uv run python src/generate_data.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

ANOMALY_START, ANOMALY_END = 200, 215  # inclusive, matches lab doc


def generate_metrics(n: int = 500, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    timestamps = pd.date_range("2025-10-01 08:00", periods=n, freq="1min")
    cpu = rng.normal(35, 5, n)
    error_rate = rng.exponential(0.002, n)
    latency_p99 = rng.normal(150, 20, n)

    cpu[ANOMALY_START : ANOMALY_END + 1] = rng.normal(85, 5, ANOMALY_END - ANOMALY_START + 1)
    error_rate[ANOMALY_START : ANOMALY_END + 1] = rng.uniform(
        0.05, 0.15, ANOMALY_END - ANOMALY_START + 1
    )
    latency_p99[ANOMALY_START : ANOMALY_END + 1] = rng.normal(
        3500, 200, ANOMALY_END - ANOMALY_START + 1
    )

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "cpu_pct": np.clip(cpu, 0, 100),
            "error_rate": np.clip(error_rate, 0, 1),
            "latency_p99_ms": np.clip(latency_p99, 0, None),
        }
    )
    return df


SERVICES = ["checkout-api", "payments-svc", "inventory-svc", "auth-svc"]

NORMAL_MESSAGES = [
    ("INFO", "request completed status=200 path=/api/v1/health"),
    ("INFO", "request completed status=200 path=/api/v1/cart"),
    ("INFO", "cache hit key=session:{sid}"),
    ("INFO", "db query completed rows=1 duration_ms={dur}"),
    ("DEBUG", "heartbeat ok"),
]

INCIDENT_MESSAGES = [
    ("ERROR", "db connection pool exhausted: waited {dur}ms for connection"),
    ("ERROR", "upstream timeout calling payments-svc after {dur}ms"),
    ("WARN", "circuit breaker OPEN for downstream=payments-svc"),
    ("ERROR", "request failed status=503 path=/api/v1/checkout"),
    ("ERROR", "connection reset by peer during db query"),
    ("WARN", "retrying request attempt=3 backoff_ms={dur}"),
]


def generate_logs(n_minutes: int = 500, seed: int = 7) -> list[str]:
    rng = np.random.default_rng(seed)
    lines: list[str] = []
    base_ts = pd.Timestamp("2025-10-01 08:00")

    for minute in range(n_minutes):
        ts = base_ts + pd.Timedelta(minutes=minute)
        in_incident = ANOMALY_START <= minute <= ANOMALY_END
        # more log volume per minute during the incident (retries, errors)
        n_lines = rng.integers(3, 7) if in_incident else rng.integers(1, 3)

        for _ in range(n_lines):
            service = rng.choice(SERVICES)
            if in_incident and rng.random() < 0.75:
                level, template = INCIDENT_MESSAGES[rng.integers(0, len(INCIDENT_MESSAGES))]
                dur = int(rng.integers(1500, 5000))
            else:
                level, template = NORMAL_MESSAGES[rng.integers(0, len(NORMAL_MESSAGES))]
                dur = int(rng.integers(5, 120))
            sid = f"{rng.integers(10000, 99999)}"
            msg = template.format(dur=dur, sid=sid)
            offset_s = int(rng.integers(0, 60))
            line_ts = ts + pd.Timedelta(seconds=offset_s)
            lines.append(
                f"{line_ts.isoformat()} {level:<5} service={service} {msg}"
            )

    lines.sort()  # interleave by timestamp across services
    return lines


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    metrics_df = generate_metrics()
    metrics_path = DATA_DIR / "metrics_sample.csv"
    metrics_df.to_csv(metrics_path, index=False)
    print(f"wrote {metrics_path} ({len(metrics_df)} rows)")

    logs = generate_logs()
    logs_path = DATA_DIR / "logs_sample.txt"
    logs_path.write_text("\n".join(logs) + "\n", encoding="utf-8")
    print(f"wrote {logs_path} ({len(logs)} lines)")


if __name__ == "__main__":
    main()
