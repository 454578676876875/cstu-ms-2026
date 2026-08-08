# RCA Report — Incident 2025-10-01 11:20:00 to 2025-10-01 11:35:00

## Summary
Between **2025-10-01 11:20:00** and **2025-10-01 11:35:00**, 48 alerts fired across
3 metric(s) (cpu_pct, error_rate, latency_p99_ms). The dominant signal was
**error_rate**, which moved +5207.2% relative to the preceding
60-minute baseline. Logs corroborate an active incident: 30
ERROR and 23 WARN lines were emitted in the window, concentrated in
checkout-api, inventory-svc, payments-svc.

## Evidence: Metrics
- **cpu_pct**: baseline 34.858 -> incident 83.387 (+139.2%)
- **error_rate**: baseline 0.002 -> incident 0.11 (+5207.2%)
- **latency_p99_ms**: baseline 146.358 -> incident 3431.727 (+2244.8%)

## Evidence: Logs
- 64 total log lines in window
- 30 ERROR, 23 WARN
- Top services: checkout-api, inventory-svc, payments-svc
- Representative errors:
  - `2025-10-01T11:21:18 ERROR service=checkout-api request failed status=503 path=/api/v1/checkout`
  - `2025-10-01T11:21:18 ERROR service=inventory-svc connection reset by peer during db query`
  - `2025-10-01T11:21:39 ERROR service=checkout-api connection reset by peer during db query`
  - `2025-10-01T11:21:41 ERROR service=inventory-svc upstream timeout calling payments-svc after 1872ms`
  - `2025-10-01T11:22:09 ERROR service=payments-svc connection reset by peer during db query`

## Root Cause Hypothesis
The simultaneous spike in `latency_p99_ms` and `error_rate` alongside `cpu_pct`, combined with log
evidence of **connection pool exhaustion** and **upstream timeouts**, points to a downstream
dependency (most likely `payments-svc`, per log volume) becoming slow or unavailable. Elevated CPU is
consistent with request threads blocking/retrying while waiting on that dependency rather than being
the primary trigger — i.e. CPU is a symptom of backed-up retries, not the root cause.

## Recommended Preventive Measures
1. Add a circuit breaker with a tighter timeout on calls to the implicated downstream service so
   failures fail fast instead of exhausting the connection pool.
2. Set an autoscaling policy or connection-pool alarm keyed on pool-wait-time, not just CPU, since CPU
   lagged the actual trigger in this incident.
3. Add a synthetic health check against the downstream dependency so degradation is caught before it
   cascades into client-facing errors.
