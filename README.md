# CSE636: DevOps with AI Assistance

This repository contains coursework for CSE636, DevOps with AI Assistance. Each week's lab and
assignment work is organized under `cse636-devops-with-ai-assistance/`, with a dedicated folder per
week.

## Repository Structure

```
cse636-devops-with-ai-assistance/
  Lab_Wk5/    Week 5: Anomaly Detection and AI-Generated Root Cause Analysis
  Lab_Wk6/    Week 6: Gated Incident-Triage and Self-Healing Agents
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

## Week 6: Gated Incident-Triage and Self-Healing Agents

Located in [`cse636-devops-with-ai-assistance/Lab_Wk6`](cse636-devops-with-ai-assistance/Lab_Wk6).

Covers the Week 6 lab and the assignment:

- **Lab**: a ReAct agent that triages a `payment-svc` error-rate spike using a YAML runbook and
  5 tools, and stops for a human approval before the one destructive action
  (`execute_rollback`).
- **Assignment**: a self-healing agent for a different failure mode -- `notify-svc` stuck
  restarting in an OOM crash loop -- with its own runbook, 6 tools, a gated `restart_service`,
  and three blast-radius controls (kill switch, error-budget check, a rate limiter on
  remediation). These are checked in code, not just written into the prompt. The captured
  transcript runs two incidents back to back so the rate limiter actually blocks the second
  automated restart when the crash loop comes back -- the restart-flapping scenario the course
  notes warn about.
- **Architecture diagram**: [`diagrams/architecture.svg`](cse636-devops-with-ai-assistance/Lab_Wk6/diagrams/architecture.svg),
  labeled with the gates and autonomy level for each step.

Managed with [`uv`](https://docs.astral.sh/uv/). Includes both agents' MCP server + agent code,
both runbooks, captured terminal transcripts, and a pytest suite. See
[`Lab_Wk6/README.md`](cse636-devops-with-ai-assistance/Lab_Wk6/README.md) for how to run it and
the design decisions, and
[`Lab_Wk6/WRITEUP.md`](cse636-devops-with-ai-assistance/Lab_Wk6/WRITEUP.md) for the lab
reflection and the assignment's safety discussion.

**Note:** No Anthropic API key is configured in this environment, so both agents run in
simulation mode, which is an option the lab doc itself allows. A scripted stand-in "brain"
walks the same runbook a live Claude call would and stops at the same real, blocking
`input()` approval prompt, so the transcripts are from actual runs, not written by hand.
