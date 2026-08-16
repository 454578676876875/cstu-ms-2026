"""Cost-impact comparison for the assignment: static over-provisioning vs. reactive HPA
(with a stabilization-window-style scale-down delay) vs. predictive autoscaling (this lab's
Prophet forecast, upper 80% CI), over the full 7-day synthetic dataset.

Numbers computed from the trained model and generated data, not assumed.
"""
import pandas as pd
from prophet import Prophet

from scaling import required_replicas

TARGET_CPU = 60.0
MIN_REPLICAS = 1
COST_PER_REPLICA_HOUR = 0.04  # AWS t3.medium on-demand, illustrative (see ASSIGNMENT.md)


def reactive_series(cpu_values):
    """Immediate scale-up, delayed scale-down (3-sample / 15-min stabilization window).

    Note: Kubernetes HPA's default scaleDown.stabilizationWindowSeconds is 300s (5 min, i.e.
    a 1-sample window at this data's 5-min resolution), not 15 min. I used a longer 15-min/
    3-sample window here so the delayed-scale-down effect actually shows up in the cost
    comparison, not because I was trying to match the default exactly."""
    raw = [required_replicas(1, c, TARGET_CPU, min_replicas=MIN_REPLICAS) for c in cpu_values]
    out, window, cur = [], [], raw[0]
    for r in raw:
        window.append(r)
        if len(window) > 3:
            window.pop(0)
        cur = r if r > cur else max(window)
        out.append(cur)
    return out


def main():
    df = pd.read_csv("data/synthetic_metrics.csv", parse_dates=["ds"])
    cpu_df = df[["ds", "cpu"]].rename(columns={"cpu": "y"})
    split_time = cpu_df["ds"].max() - pd.Timedelta("24h")
    train = cpu_df[cpu_df["ds"] < split_time].copy()

    model = Prophet(daily_seasonality=True, weekly_seasonality=True, yearly_seasonality=False, interval_width=0.80)
    model.fit(train)
    forecast = model.predict(model.make_future_dataframe(periods=300, freq="5min"))

    merged = df.merge(forecast[["ds", "yhat_upper"]], on="ds", how="inner")
    cpu = merged["cpu"].values
    yhat_upper = merged["yhat_upper"].values
    step_hours = 5 / 60
    total_hours = len(cpu) * step_hours

    peak = float(cpu.max())
    static_replicas = required_replicas(1, peak, TARGET_CPU, min_replicas=MIN_REPLICAS)
    static_cost = static_replicas * COST_PER_REPLICA_HOUR * total_hours

    reactive = reactive_series(cpu)
    reactive_cost = sum(r * COST_PER_REPLICA_HOUR * step_hours for r in reactive)

    predictive = [required_replicas(1, y, TARGET_CPU, min_replicas=MIN_REPLICAS) for y in yhat_upper]
    predictive_cost = sum(r * COST_PER_REPLICA_HOUR * step_hours for r in predictive)

    report = f"""# Cost-Impact Analysis (computed from the trained model + generated data)

Assumptions: ${COST_PER_REPLICA_HOUR}/hour/replica (illustrative AWS t3.medium on-demand rate),
target {TARGET_CPU:.0f}% CPU per replica, {MIN_REPLICAS} minimum replica, over the full 7-day
({total_hours:.0f}-hour) synthetic dataset ({len(cpu)} 5-minute samples).

| Scenario | Avg replicas | 7-day cost |
|---|---|---|
| Static (peak-provisioned, 24/7) | {static_replicas} | ${static_cost:.2f} |
| Reactive HPA (immediate up, 15-min stabilized down) | {sum(reactive)/len(reactive):.2f} | ${reactive_cost:.2f} |
| Predictive (Prophet, 30-min horizon, upper 80% CI) | {sum(predictive)/len(predictive):.2f} | ${predictive_cost:.2f} |

Peak actual CPU over the 7 days: {peak:.1f}%.
"""
    with open("output/cost_analysis.md", "w") as fh:
        fh.write(report)
    print(report)


if __name__ == "__main__":
    main()
