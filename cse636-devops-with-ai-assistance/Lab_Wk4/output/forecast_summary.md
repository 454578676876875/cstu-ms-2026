# Week 4 Forecast Summary

## Evaluation (held-out 24-hour test set)
- MAE:  2.51% CPU
- MAPE: 9.0%

## Autoscaling recommendation
- Current replicas:           4
- Max predicted CPU (30 min): 45.8% (upper 80% CI)
- Target CPU per replica:     60%
- Recommended replicas:       4
- Decision:                   No change
