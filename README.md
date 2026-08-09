# CSE636: DevOps with AI Assistance

This repository contains coursework for CSE636, DevOps with AI Assistance. Each week's lab and
assignment work is organized under `cse636-devops-with-ai-assistance/`, with a dedicated folder per
week.

## Repository Structure

```
cse636-devops-with-ai-assistance/
  Lab_Wk5/    Week 5: Anomaly Detection and AI-Generated Root Cause Analysis
```

## Week 5: Anomaly Detection and Agent Instrumentation

Located in [`cse636-devops-with-ai-assistance/Lab_Wk5`](cse636-devops-with-ai-assistance/Lab_Wk5).

This submission implements both the Week 5 lab and the accompanying assignment as a single project:

- **Anomaly detection**: an Isolation Forest detector (with a DBSCAN comparison) evaluated against
  labelled synthetic metrics, including a precision/recall/F1 analysis and a `contamination`
  parameter sweep.
- **Alert grouping**: a rule-based, time-gap clustering approach that consolidates per-metric alerts
  into incident groups.
- **Agentic root cause analysis**: an RCA agent that uses two tools, `get_metrics` and `get_logs`, to
  gather evidence and synthesize a structured incident report.
- **Observability**: every model and agent step is instrumented with OpenTelemetry, following the
  GenAI semantic conventions for spans, tokens, latency, and cost.

The project is managed with [`uv`](https://docs.astral.sh/uv/) and includes an executed Jupyter
notebook, a pytest suite, generated incident reports, and captured trace data. See
[`Lab_Wk5/README.md`](cse636-devops-with-ai-assistance/Lab_Wk5/README.md) for setup instructions,
project layout, and the design decisions behind the implementation, and
[`Lab_Wk5/WRITEUP.md`](cse636-devops-with-ai-assistance/Lab_Wk5/WRITEUP.md) for the written
reflection.

**Note:** No Anthropic API key is configured in this environment, so LLM calls in the log-analysis
and RCA agents are simulated. The simulated responses are derived from real detector and log output
rather than fixed text, so the token counts, costs, and generated reports remain representative of
what a live call would produce.
