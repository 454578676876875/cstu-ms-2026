"""Step 6 (stretch): emit the forecast as a Prometheus metric for a KEDA ScaledObject.

Written for completeness (matches the lab's "if you have a cluster" framing) but NOT run live
here -- there's no Prometheus/Minikube cluster on this machine. See WRITEUP.md for why this is
left as an unexercised script rather than faked output.
"""
import time

from prometheus_client import Gauge, start_http_server


def serve(model, recommend_replicas_fn, current_replicas=4, port=8000, interval_s=300):
    start_http_server(port)
    predicted_cpu_gauge = Gauge(
        "predicted_cpu_next_30m",
        "Prophet-predicted max CPU % for next 30 minutes",
        ["service"],
    )
    print(f"Emitting Prometheus metrics on :{port}/metrics ...")
    while True:
        future = model.make_future_dataframe(periods=6, freq="5min")
        fresh_forecast = model.predict(future)
        decision = recommend_replicas_fn(fresh_forecast, current_replicas=current_replicas)
        predicted_cpu_gauge.labels(service="my-app").set(decision.max_predicted_cpu)
        print(f"Emitted predicted_cpu_next_30m = {decision.max_predicted_cpu:.1f}%")
        time.sleep(interval_s)


if __name__ == "__main__":
    raise SystemExit(
        "Not run automatically -- requires a live model + a Prometheus/KEDA cluster. "
        "See WRITEUP.md."
    )
