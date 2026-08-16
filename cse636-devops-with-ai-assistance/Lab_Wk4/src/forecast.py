"""Train a Prophet model on the synthetic CPU series, evaluate on a held-out 24h split,
produce the lab's required plots, and turn the forecast into a scaling recommendation.
"""
import matplotlib

matplotlib.use("Agg")  # no display in this environment -- write PNGs directly

import matplotlib.pyplot as plt
import pandas as pd
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error

from scaling import recommend_replicas

DATA_PATH = "data/synthetic_metrics.csv"
OUTPUT_DIR = "output"


def load_data():
    return pd.read_csv(DATA_PATH, parse_dates=["ds"])


def explore(df):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 6), sharex=True)
    ax1.plot(df["ds"], df["cpu"], linewidth=0.8, color="steelblue")
    ax1.set_ylabel("CPU %")
    ax1.set_title("CPU Utilization")
    ax1.axhline(70, color="orange", linestyle="--", alpha=0.5, label="Scale-up threshold")
    ax1.legend()

    ax2.plot(df["ds"], df["memory"], linewidth=0.8, color="coral")
    ax2.set_ylabel("Memory %")
    ax2.set_title("Memory Utilization")
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/metrics_overview.png", dpi=120)
    plt.close(fig)


def train_and_forecast(df):
    cpu_df = df[["ds", "cpu"]].rename(columns={"cpu": "y"})

    split_time = cpu_df["ds"].max() - pd.Timedelta("24h")
    train = cpu_df[cpu_df["ds"] < split_time].copy()
    test = cpu_df[cpu_df["ds"] >= split_time].copy()
    print(f"Training on {len(train)} points, evaluating on {len(test)} points")

    model = Prophet(
        daily_seasonality=True, weekly_seasonality=True, yearly_seasonality=False, interval_width=0.80
    )
    model.fit(train)

    # periods must cover the full 24h held-out test window (288 5-min steps) plus a bit of
    # true future beyond it for the scaling recommendation -- 12 periods (1h) isn't enough.
    future = model.make_future_dataframe(periods=300, freq="5min")
    forecast = model.predict(future)

    fig = model.plot(forecast)
    plt.title("CPU Forecast")
    plt.savefig(f"{OUTPUT_DIR}/cpu_forecast.png", dpi=120)
    plt.close(fig)

    fig2 = model.plot_components(forecast)
    plt.savefig(f"{OUTPUT_DIR}/cpu_forecast_components.png", dpi=120)
    plt.close(fig2)

    return model, forecast, train, test


def evaluate(forecast, test):
    # Explicit merge on 'ds' (rather than isin + positional indexing) guarantees actual/predicted
    # line up row-for-row regardless of forecast's internal ordering -- isin only happened to work
    # here because both frames were already sorted ascending by ds with no duplicate timestamps.
    test_forecast = test.merge(forecast, on="ds", how="left", suffixes=("", "_forecast"))
    actual = test_forecast["y"].values
    predicted = test_forecast["yhat"].values

    mae = mean_absolute_error(actual, predicted)
    mape = mean_absolute_percentage_error(actual, predicted) * 100

    fig, ax = plt.subplots(figsize=(14, 4))
    ax.plot(test["ds"], actual, label="Actual", color="steelblue")
    ax.plot(test_forecast["ds"], predicted, label="Predicted", color="orange", linestyle="--")
    ax.fill_between(
        test_forecast["ds"], test_forecast["yhat_lower"], test_forecast["yhat_upper"],
        alpha=0.2, color="orange", label="80% CI",
    )
    ax.axhline(70, color="red", linestyle=":", alpha=0.5, label="Scale-up threshold")
    ax.set_title("CPU Forecast vs. Actual (Test Period)")
    ax.legend()
    plt.savefig(f"{OUTPUT_DIR}/cpu_eval.png", dpi=120)
    plt.close(fig)

    return mae, mape


def main():
    df = load_data()
    explore(df)
    model, forecast, train, test = train_and_forecast(df)
    mae, mape = evaluate(forecast, test)

    current = 4
    # Anchor "now" to the data's own last timestamp. pd.Timestamp.now() would be years past
    # this synthetic 2025-10 series, so recommend_replicas's horizon window would always be
    # empty and silently fall back to forecast_df.tail(...) instead of actual future rows.
    now = df["ds"].max() - pd.Timedelta(minutes=30)
    decision = recommend_replicas(forecast, current_replicas=current, now=now)

    summary = f"""# Week 4 Forecast Summary

## Evaluation (held-out 24-hour test set)
- MAE:  {mae:.2f}% CPU
- MAPE: {mape:.1f}%

## Autoscaling recommendation
- Current replicas:           {current}
- Max predicted CPU (30 min): {decision.max_predicted_cpu:.1f}% (upper 80% CI)
- Target CPU per replica:     60%
- Recommended replicas:       {decision.recommended_replicas}
- Decision:                   {decision.action}
"""
    with open(f"{OUTPUT_DIR}/forecast_summary.md", "w") as fh:
        fh.write(summary)
    print(summary)


if __name__ == "__main__":
    main()
