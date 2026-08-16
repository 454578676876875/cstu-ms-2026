# AI Forecasting for Kubernetes Autoscaling — Effectiveness Analysis

Salman, CSE636, Week 4 Assignment

## 1. Executive Summary

On this lab's data, predictive autoscaling did **not** beat reactive HPA on cost. It came in about
2% more expensive (\$7.27 vs. \$7.14 over a simulated week, `output/cost_analysis.md`), because it
trades a small amount of extra headroom for lower spike risk (it scales off the upper 80%
confidence bound, not the point forecast). The value predictive forecasting offers here is mostly
about timing: it can act before a load ramp starts rather than after crossing a threshold, which
matters for workloads with slow-starting containers or sharp, regular (daily/weekly) ramps. It
matters less for a workload whose load is already close to flat, which is roughly what this
synthetic dataset's low peak (69.7% CPU, never near saturation) turned out to be. The headline
finding: predictive autoscaling's value is conditional on the workload having a reaction-lag cost
worth avoiding in the first place. On a mild, well-behaved load profile it mostly just adds a
small, honest insurance premium.

## 2. Baseline: Reactive HPA vs. Predictive Autoscaling

Standard Kubernetes HPA polls a metric (default: CPU utilization) on a fixed interval
(`--horizontal-pod-autoscaler-sync-period`, default 15s) and scales replicas toward a target
utilization. Its key limitation is reaction lag: it can only respond to load that has already
happened by the time the metric is scraped, aggregated, and acted on, and it further defers
scale-down decisions by a stabilization window (default 300s) to avoid flapping. Scale-up is
comparatively fast, but a new pod still needs to schedule, pull an image, and pass its readiness
probe before it can absorb traffic. For a slow-starting container (a JVM warming up, a large ML
model loading into memory), that startup time alone can exceed the entire useful window of a
sharp, short traffic spike.

This lag does the most damage on sharp, short-duration spikes (a flash-sale traffic burst, a
batch job's initial fan-out) and on workloads with slow container startup, since in both cases
the load has already passed its worst point by the time reactive scaling finishes responding. A
predictive approach sidesteps this failure mode by scaling ahead of a load pattern it has already
learned to expect (this lab's daily/weekly seasonality), so new capacity comes online before the
load arrives instead of in response to it, at the cost of being wrong whenever the future doesn't
look like the learned pattern.

## 3. Our Forecasting Experiment

**Dataset:** the lab's synthetic generator (`src/generate_data.py`), 2,016 points at 5-minute
resolution (7 days). CPU is built from a 24-hour cycle (±20%), a 7-day cycle (±10%), a slow
upward trend, and Gaussian noise (σ=3), clipped to [5, 95]. Exploration
(`output/metrics_overview.png`) confirmed the intended daily/weekly pattern with no missing
timestamps and no injected anomaly outside the generator's own noise.

**Model performance:** Prophet (`daily_seasonality=True, weekly_seasonality=True,
interval_width=0.80`) trained on the first 6 days (1,727 points), evaluated on the held-out
final 24 hours (289 points). **MAE 2.51% CPU, MAPE 9.0%** (`output/forecast_summary.md`, an
actual run — `prophet==1.4.0` with the `cmdstanpy` backend installed and fit without issue on
this Windows machine, no fallback model needed). `output/cpu_eval.png` shows actual CPU tracking
inside the 80% CI band for nearly the entire test window.

**Where the model was most/least accurate:** the components decomposition
(`output/cpu_forecast_components.png`) recovered all three synthetic components cleanly: trend
rising ~29%→42% over the week, weekly cycle troughing Sun/Mon and peaking Thu/Fri (~±10%), daily
cycle peaking ~05:00-06:00 and troughing ~17:00-18:00 (~±20%), matching the generator's
parameters closely. Error is dominated by the injected Gaussian noise (σ=3), which Prophet
correctly treats as irreducible rather than trying to fit. The shape of the forecast never
seriously deviates from actual, but any individual 5-minute reading can be off by a few points
simply because the noise term is unpredictable by construction. There's no real "failure region"
in this data (no unmodeled anomaly, no regime change between train and test), which makes sense
given it's synthetic and stationary. A harder test would need a dataset where the pattern itself
changes over time (a new feature launch shifting the daily curve's shape, an actual incident, a
holiday).

**Alternative approach considered:** a seasonal-naive baseline (predict `y[t] = y[t - 1 week]`)
would probably perform comparably on this specific dataset, since the synthetic seasonality is
clean and stationary. Prophet's advantage over a moving average or naive seasonal baseline
usually shows up on data with trend plus multiple overlapping seasonalities plus irregular gaps,
which is exactly what this dataset has (trend, daily, and weekly together). For a single clean
seasonal pattern alone, a much cheaper seasonal-naive model might be good enough, and I'd want to
see that comparison run before recommending Prophet's extra operational complexity (its
`cmdstanpy` compiled-backend dependency is nontrivial to deploy compared to
`pandas.Series.shift()`) for a workload this well-behaved.

## 4. Cost-Impact Analysis

Numbers below are from the trained model and the generated dataset
(`src/cost_analysis.py`, `output/cost_analysis.md`), not assumed:

| Scenario | Avg replicas | 7-day cost |
|---|---|---|
| Static (peak-provisioned, 24/7) | 2 | \$13.44 |
| Reactive HPA (immediate scale-up, 15-min stabilized scale-down) | 1.06 | \$7.14 |
| Predictive (Prophet, 30-min horizon, upper 80% CI) | 1.08 | \$7.27 |

**Assumptions:** \$0.04/hour/replica (an illustrative AWS `t3.medium` on-demand rate, not the
exact current AWS price), target 60% CPU per replica, 1 minimum replica, over the full simulated
7-day/168-hour dataset. Reactive HPA is modeled as scaling up immediately but delaying scale-down
for 3 samples (15 minutes), to mimic Kubernetes HPA's default `stabilizationWindowSeconds=300`
behavior.

**Reading the result honestly:** static over-provisioning costs ~88% more than either dynamic
approach here, which is the expected result and not particularly surprising. The more interesting
number is that predictive cost slightly more than reactive (+1.8%) on this data, because the
predictive recommendation scales to the upper confidence bound rather than the raw actual value.
It's paying a small, quantifiable insurance premium for lead time that a purely reactive approach
doesn't have. Whether that premium is worth it depends on whether the workload actually has
spikes sharp enough, or startup times slow enough, that reactive HPA's lag would cost more than
1.8% in over-provisioned recovery time or under-provisioned request failures. This particular
synthetic workload, with its mild 69.7% peak and no sharp transients, doesn't clearly demonstrate
that either way.

## 5. Limitations and Failure Modes

- **Cold starts:** predictive scaling can pre-provision capacity, but it can't make a container
  start faster. If a pod takes 90 seconds to become ready, scaling the decision 30 minutes ahead
  only helps if that decision happens with at least that much lead time before the predicted
  spike, which means the forecast horizon needs to be tuned to the workload's actual startup
  time, not left at a fixed default.
- **Unpredictable/bursty traffic:** this experiment's dataset is, by construction, a clean
  seasonal signal. A workload driven by external events (a marketing campaign, a viral post) has
  no learnable seasonality for Prophet to find, and the model would degrade toward predicting the
  seasonal average, providing no better lead time than reactive scaling.
- **Model drift:** a model trained once and left running will silently degrade as the workload's
  actual pattern shifts (new features, changed usage hours, seasonal business cycles beyond what
  a week of training data can show). Mitigation: scheduled retraining (nightly, say, on a rolling
  training window) with automated MAPE monitoring against a held-out recent window, and an alert
  if MAPE crosses a threshold that would have changed the scaling recommendation.

## 6. Recommendations

Deploy predictive autoscaling for workloads with well-established, regular daily/weekly demand
cycles and either slow-starting containers or business-visible cost from brief
under-provisioning (a customer-facing service with a strong 9am ramp, for example). Skip it for
workloads whose load is either already flat (little to gain) or genuinely event-driven/bursty
(nothing to learn). For this specific lab's workload profile — mild peak, no sharp transients —
reactive HPA alone is arguably sufficient, and the honest recommendation based on the numbers
above is to layer predictive scaling in as a pre-emptive floor under reactive HPA rather than
replace it, matching the defense-in-depth reasoning in `WRITEUP.md`.

**Monitoring and governance:** track realized MAPE against a rolling recent window (not just the
one-time held-out test), alert when it degrades past a threshold tied to how much scaling error
the business can tolerate, and keep a reactive fallback active underneath at all times. A
predictive system with no reactive floor and no monitored accuracy has no safety net once its own
assumptions (seasonality is stable, the workload hasn't changed) stop holding.
