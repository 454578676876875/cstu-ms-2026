"""Synthetic CPU/memory metrics, per the Week 4 lab's Step 1 snippet (seeded, repeatable)."""
import numpy as np
import pandas as pd


def generate(n_points=2016, seed=42):
    np.random.seed(seed)
    timestamps = pd.date_range(start="2025-10-01", periods=n_points, freq="5min")

    t = np.arange(n_points)
    daily_cycle = 20 * np.sin(2 * np.pi * t / (24 * 12))
    weekly_cycle = 10 * np.sin(2 * np.pi * t / (7 * 24 * 12))
    noise = np.random.normal(0, 3, n_points)
    trend = 0.005 * t

    cpu = np.clip(30 + daily_cycle + weekly_cycle + noise + trend, 5, 95)
    memory = np.clip(45 + 0.5 * daily_cycle + noise * 0.5, 20, 90)

    return pd.DataFrame({"ds": timestamps, "cpu": cpu, "memory": memory})


if __name__ == "__main__":
    df = generate()
    df.to_csv("data/synthetic_metrics.csv", index=False)
    print(f"Generated data/synthetic_metrics.csv with {len(df)} rows")
