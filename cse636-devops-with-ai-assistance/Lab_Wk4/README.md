# Week 4 Lab and Assignment: Time-Series Forecasting for Autoscaling

Covers the Week 4 lab (Prophet CPU forecast -> autoscaling recommendation) and the assignment
(a 4-6 page cost-impact/effectiveness report), both described in `week-04-lab.md`.

Prophet is actually installed and fit here, not stubbed out. `prophet==1.4.0` (with the
`cmdstanpy` backend) built cleanly into this project's `uv` venv and fit without issue on this
Windows machine, so every number in this submission comes from a trained model, not a guess.

## How to run

Managed with [`uv`](https://docs.astral.sh/uv/). First run takes ~15s longer than later runs
(cmdstanpy compiles/caches the Stan model on first fit).

```bash
cd cse636-devops-with-ai-assistance/Lab_Wk4

# 1. Generate the synthetic dataset
uv run python src/generate_data.py

# 2. Train, evaluate, plot, and produce the scaling recommendation
uv run python src/forecast.py

# 3. Assignment: cost-impact comparison (static / reactive / predictive), real numbers
uv run python src/cost_analysis.py

# 4. Run the test suite
uv run pytest -v
```

## Project structure

```
src/
  generate_data.py       the lab's synthetic CPU/memory generator (seeded)
  scaling.py              recommend_replicas() / required_replicas() as tested pure functions,
                          same pattern as project/forecasting/scaling.py
  forecast.py              train/evaluate/plot (Steps 2-5): metrics_overview, cpu_forecast,
                          cpu_forecast_components, cpu_eval plots + forecast_summary.md
  cost_analysis.py         assignment's cost-impact comparison, computed from the trained
                          model and generated data
  prometheus_stretch.py    Step 6 stretch -- written for completeness, not run (no cluster
                          here; see WRITEUP.md)

data/
  synthetic_metrics.csv    generated dataset (2016 rows, 7 days at 5-min resolution)

output/
  metrics_overview.png, cpu_forecast.png, cpu_forecast_components.png, cpu_eval.png
  forecast_summary.md       MAE/MAPE + the scaling recommendation, from an actual run
  cost_analysis.md          static/reactive/predictive replica-count and cost comparison

tests/
  test_scaling.py           required_replicas()/recommend_replicas() -- clamping, validation,
                          horizon-window selection, fallback-to-tail behavior

WRITEUP.md               lab notes (MAPE, components-plot patterns, spike-robustness question)
ASSIGNMENT.md              cost-impact / effectiveness report
```

## Design decisions

I went in planning to try Prophet and fall back to statsmodels Holt-Winters if cmdstan didn't
build on Windows. `uv add prophet` and `model.fit()` both worked without a fight, though, so the
fallback never got used. Every MAE/MAPE/plot/cost number in this submission comes from that fit.

I also bumped `make_future_dataframe(periods=300, ...)` up from the lab snippet's `periods=12`.
The lab's Step 3 snippet uses `periods=12` (1 hour), but Step 4's evaluation needs a forecast row
for every point in the 24-hour (289-point) held-out test set. `periods=12` doesn't cover that and
`evaluate()` errors out with a length mismatch, so I bumped it to 300 (25 hours) — covers the
whole test window plus a bit of true future for the scaling recommendation.

One thing that tripped me up: `recommend_replicas`'s `now` parameter. The lab's original snippet
calls `pd.Timestamp.now()` directly, which lands years past this synthetic 2025-10 dataset, so
the horizon window `(now, now+30min]` would always be empty against 2025 data and silently fall
through to only the fallback path. `recommend_replicas()` takes an explicit `now` instead
(defaulting to `pd.Timestamp.now()` for normal use), and `forecast.py` anchors it to the data's
own last timestamp so the "predict the next 30 minutes" logic actually runs against in-range
forecast rows instead of always hitting its fallback.

Cost analysis uses computed numbers, not assumed ones — `cost_analysis.py` re-fits the same
Prophet model, merges the forecast against the generated data, and computes replica counts per
scenario from that. See `ASSIGNMENT.md` section 4 for the numbers and an honest read of what they
do (and don't) show.
