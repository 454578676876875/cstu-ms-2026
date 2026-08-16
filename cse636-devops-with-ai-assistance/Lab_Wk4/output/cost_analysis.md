# Cost-Impact Analysis (computed from the trained model + generated data)

Assumptions: $0.04/hour/replica (illustrative AWS t3.medium on-demand rate),
target 60% CPU per replica, 1 minimum replica, over the full 7-day
(168-hour) synthetic dataset (2016 5-minute samples).

| Scenario | Avg replicas | 7-day cost |
|---|---|---|
| Static (peak-provisioned, 24/7) | 2 | $13.44 |
| Reactive HPA (immediate up, 15-min stabilized down) | 1.06 | $7.14 |
| Predictive (Prophet, 30-min horizon, upper 80% CI) | 1.08 | $7.28 |

Peak actual CPU over the 7 days: 69.7%.
