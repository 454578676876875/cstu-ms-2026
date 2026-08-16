# Week 4 Lab Notes

## What MAPE did you achieve? Is it good enough for autoscaling decisions?

**MAE 2.51% CPU, MAPE 9.0%** on the held-out 24-hour test set (`output/forecast_summary.md`,
from an actual Prophet fit — `prophet==1.4.0` with the `cmdstanpy` backend installed and ran
cleanly on this machine, no fallback needed).

For an autoscaling decision specifically, I don't think MAPE is the number that matters most.
`recommend_replicas()` scales off `yhat_upper` (the top of the 80% CI band), not the point
forecast `yhat`, so a 9% average error doesn't directly translate into under-provisioning.
Looking at `output/cpu_eval.png`, the actual series stays inside the 80% CI band for nearly the
entire test window, and the recommendation logic already assumes the point forecast will
sometimes be a few points off. 9% MAPE is good enough to rank time windows as high/low load
reliably, which is what a 30-minute-ahead scaling decision actually needs. I wouldn't use the raw
`yhat` line alone to set a hard replica floor without that CI-band safety margin, though.

## What patterns did the Prophet components plot reveal?

`output/cpu_forecast_components.png` has three panels:

- **Trend:** a clean, near-linear rise from ~29% to ~42% over the 7-day training window.
  Prophet recovered the synthetic `0.005 * t` upward drift almost exactly as generated.
- **Weekly:** a smooth sinusoid troughing Sunday night into Monday (~-11%) and peaking
  Thursday-Friday (~+10%), matching the generator's `10 * sin(2*pi*t / (7*24*12))` term. The
  phase (low start-of-week, high mid-to-late-week) is a pattern a lot of production services
  actually show too (weekday traffic > weekend traffic), even though this one's synthetic.
- **Daily:** peaks around 05:00-06:00 (~+20%) and troughs around 17:00-18:00 (~-20%), recovering
  the `20 * sin(2*pi*t / (24*12))` daily term with the right amplitude and phase.

All three decompose cleanly with no visible leakage between them (the daily panel doesn't show a
weekly-shaped ripple, for instance), which makes sense since the synthetic data's components are
additive and independent by construction. A real production series with interacting daily/weekly
effects (weekday mornings spiking harder than weekend mornings, say) would probably show up
messier than this.

## If actual CPU hit 95% during a spike the model did not forecast, what would happen?

`recommend_replicas()` only looks at the forecast window `(now, now+30min]`, so it has no way to
react to what's happening right now if the live value diverges from what was predicted. An
unforecast spike to 95% would sit outside the 80% CI band entirely (the band tops out well below
95% in the test period plot), and the scaling recommendation would keep reporting whatever the
forecast said, not the actual 95% reading. That's basically the same reaction-lag problem this
course's notes describe for reactive HPA, just coming from the model's blind spot this time
instead of measurement lag.

To make it more robust, I wouldn't replace reactive HPA with predictive scaling, I'd run them
together. Keep a standard CPU-target HPA (or a simple "if live CPU > threshold, scale now" rule)
as a fast-acting floor underneath the predictive recommendation, so an unforecast spike still
gets caught by the reactive path within its normal reaction window, while the predictive layer
handles the known daily/weekly ramp ahead of time so the reactive path has less distance to
climb. Basically the same defense-in-depth idea this course keeps coming back to for other
guardrails (an approval gate doesn't replace scoped credentials, it sits on top of them), just
applied to capacity instead of safety.
