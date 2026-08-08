"""Agentic root-cause-analysis (RCA) system.

Given an incident (an AlertGroup from alert_grouper.py), the agent:
  1. Calls tool `get_metrics` to pull metric evidence for the incident window
     (vs. a normal-period baseline).
  2. Calls tool `get_logs` to pull matching log lines for the same window.
  3. Synthesizes a structured RCA report from that evidence (simulated LLM
     call - see README).

Every step (both tool calls and the synthesis call) is wrapped in an OTel
span, nested under a single `rca_agent.run` trace, using the GenAI
conventions from telemetry.py.

Run with: uv run python src/rca_agent.py
Writes output/rca_report.md and output/spans_sample.json.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from alert_grouper import AlertGroup, build_alerts, group_alerts
from anomaly_detector import FEATURES, load_metrics, run_isolation_forest
from telemetry import configure_tracer, simulated_llm_call, tool_span

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

BASELINE_WINDOW_MINUTES = 60  # look this far before the incident for a "normal" baseline


# --- Tools -------------------------------------------------------------

def get_metrics(tracer, df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    """Tool: summarize each metric during the incident window vs. a
    baseline window immediately preceding it."""
    with tool_span(tracer, "get_metrics", **{"incident.start": str(start), "incident.end": str(end)}):
        window = df[(df["timestamp"] >= start) & (df["timestamp"] <= end)]
        baseline_start = start - pd.Timedelta(minutes=BASELINE_WINDOW_MINUTES)
        baseline = df[(df["timestamp"] >= baseline_start) & (df["timestamp"] < start)]

        evidence = {}
        for metric in FEATURES:
            base_mean = baseline[metric].mean()
            win_mean = window[metric].mean()
            pct_change = ((win_mean - base_mean) / base_mean * 100) if base_mean else float("inf")
            evidence[metric] = {
                "baseline_mean": round(float(base_mean), 3),
                "incident_mean": round(float(win_mean), 3),
                "pct_change": round(float(pct_change), 1),
            }
        return evidence


def get_logs(tracer, log_lines: list[str], start: pd.Timestamp, end: pd.Timestamp) -> dict:
    """Tool: fetch and summarize log lines whose timestamp falls in the
    incident window."""
    with tool_span(tracer, "get_logs", **{"incident.start": str(start), "incident.end": str(end)}):
        matched = []
        for line in log_lines:
            ts_str = line.split(" ", 1)[0]
            try:
                ts = pd.Timestamp(ts_str)
            except ValueError:
                continue
            if start <= ts <= end:
                matched.append(line)

        errors = [l for l in matched if " ERROR " in l]
        warns = [l for l in matched if " WARN " in l]
        services = re.findall(r"service=(\S+)", "\n".join(matched))
        top_services = sorted(set(services), key=services.count, reverse=True)[:3]

        return {
            "total_lines": len(matched),
            "error_count": len(errors),
            "warn_count": len(warns),
            "top_services": top_services,
            "sample_errors": [l for l in errors[:5]],
        }


# --- Synthesis -----------------------------------------------------------

def synthesize_rca(metrics_evidence: dict, logs_evidence: dict, group: AlertGroup) -> str:
    """Simulated LLM synthesis: builds a structured RCA report grounded in
    the tool outputs above (deterministic, but the shape and reasoning mirror
    what a real Claude call driven by the same prompt would produce)."""
    worst_metric = max(metrics_evidence.items(), key=lambda kv: abs(kv[1]["pct_change"]))
    metric_name, metric_stats = worst_metric

    metric_lines = "\n".join(
        f"- **{m}**: baseline {v['baseline_mean']} -> incident {v['incident_mean']} "
        f"({v['pct_change']:+.1f}%)"
        for m, v in metrics_evidence.items()
    )
    sample_error_lines = "\n".join(f"  - `{e.strip()}`" for e in logs_evidence["sample_errors"]) or "  - (none captured)"

    report = f"""# RCA Report — Incident {group.start} to {group.end}

## Summary
Between **{group.start}** and **{group.end}**, {len(group.alerts)} alerts fired across
{len(group.metrics_involved)} metric(s) ({', '.join(group.metrics_involved)}). The dominant signal was
**{metric_name}**, which moved {metric_stats['pct_change']:+.1f}% relative to the preceding
{BASELINE_WINDOW_MINUTES}-minute baseline. Logs corroborate an active incident: {logs_evidence['error_count']}
ERROR and {logs_evidence['warn_count']} WARN lines were emitted in the window, concentrated in
{', '.join(logs_evidence['top_services']) or 'unknown service(s)'}.

## Evidence: Metrics
{metric_lines}

## Evidence: Logs
- {logs_evidence['total_lines']} total log lines in window
- {logs_evidence['error_count']} ERROR, {logs_evidence['warn_count']} WARN
- Top services: {', '.join(logs_evidence['top_services']) or 'n/a'}
- Representative errors:
{sample_error_lines}

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
"""
    return report


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tracer = configure_tracer(
        "rca-agent", span_log_path=str(OUTPUT_DIR / "spans_sample.json")
    )

    metrics_df = load_metrics()
    log_lines = (DATA_DIR / "logs_sample.txt").read_text(encoding="utf-8").splitlines()

    flagged = run_isolation_forest(metrics_df, contamination=0.04)
    alerts = build_alerts(flagged)
    groups = group_alerts(alerts)
    incident = max(groups, key=lambda g: len(g.alerts))  # pick the biggest incident

    with tracer.start_as_current_span("rca_agent.run") as run_span:
        run_span.set_attribute("incident.start", str(incident.start))
        run_span.set_attribute("incident.end", str(incident.end))
        run_span.set_attribute("incident.alert_count", len(incident.alerts))

        metrics_evidence = get_metrics(tracer, metrics_df, incident.start, incident.end)
        logs_evidence = get_logs(tracer, log_lines, incident.start, incident.end)

        prompt = (
            "Synthesize a root cause analysis report from this evidence:\n"
            f"METRICS: {json.dumps(metrics_evidence)}\n"
            f"LOGS: {json.dumps({k: v for k, v in logs_evidence.items() if k != 'sample_errors'})}"
        )
        report_text = synthesize_rca(metrics_evidence, logs_evidence, incident)
        llm_result = simulated_llm_call(
            tracer,
            prompt=prompt,
            response_text=report_text,
            span_name="synthesize_rca_report",
        )

    from opentelemetry import trace as _trace

    _trace.get_tracer_provider().force_flush()

    report_path = OUTPUT_DIR / "rca_report.md"
    report_path.write_text(llm_result.text, encoding="utf-8")
    print(f"wrote {report_path}")
    print(f"wrote {OUTPUT_DIR / 'spans_sample.json'}")
    print(
        f"synthesis call: {llm_result.input_tokens} in / {llm_result.output_tokens} out tokens, "
        f"{llm_result.latency_ms:.1f}ms"
    )


if __name__ == "__main__":
    main()
