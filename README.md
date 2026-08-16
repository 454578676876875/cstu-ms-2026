# CSE636: DevOps with AI Assistance

This repository contains coursework for CSE636, DevOps with AI Assistance. Each week's lab and
assignment work is organized under `cse636-devops-with-ai-assistance/`, with a dedicated folder per
week.

## Repository Structure

```
cse636-devops-with-ai-assistance/
  Lab_Wk1/    Week 1: Cloud DevOps Setup and First Agent Run
  Lab_Wk2/    Week 2: AI Code Review Pipeline + MCP Server
  Lab_Wk3/    Week 3: Build-Fixer Agent with a Human Approval Gate
  Lab_Wk4/    Week 4: Time-Series Forecasting for Autoscaling
  Lab_Wk5/    Week 5: Anomaly Detection and AI-Generated Root Cause Analysis
  Lab_Wk6/    Week 6: Gated Incident-Triage and Self-Healing Agents
  Lab_Wk7/    Week 7: Agentic IaC with an OPA Policy Gate
  CAPSTONE_INTEGRATION.md   narrative: how the seven weeks compose into one end-to-end pipeline
  capstone/                 the actual Capstone deliverable: a wired orchestrator that runs all
                             five pipeline stages for real, + REPORT.md + PRESENTATION.md
```

See [`cse636-devops-with-ai-assistance/capstone/`](cse636-devops-with-ai-assistance/capstone/)
for the Capstone deliverable (distinct from the Week 7 *lab*, `Lab_Wk7`) — a real,
subprocess-orchestrated pipeline run across all seven weeks (`python capstone/pipeline.py`),
the 4-6 page technical report, and the presentation script. See
[`cse636-devops-with-ai-assistance/CAPSTONE_INTEGRATION.md`](cse636-devops-with-ai-assistance/CAPSTONE_INTEGRATION.md)
for the stage-by-stage narrative explaining why each connection exists.

## Week 1: Cloud DevOps Setup and First Agent Run

Located in [`cse636-devops-with-ai-assistance/Lab_Wk1`](cse636-devops-with-ai-assistance/Lab_Wk1).

Different in shape from the other weeks: the lab itself is "run an AI agent against a real repo
and observe it," so rather than a simulated project, this ran the four suggested tasks for real
with Claude Code against `dockersamples/example-voting-app`, cloned inside the course's Step 1b
local Docker lab environment (`cse636-lab-wk1` container).

- **Four agent tasks, run for real**: repo exploration, a security scan that found a hardcoded
  Postgres password repeated across 5 files, reviewing an already-generated CI workflow (and
  recognizing it shouldn't be overwritten), and finding two outdated base images across the
  repo's three Dockerfiles.
- **Collected data**: a 1,615-line CI build log from an actual local run (image builds +
  a full vote -> Redis -> worker -> Postgres -> results e2e check, `exit=0`), plus system
  metrics from inside the lab container.
- **Assignment**: three researched, cited real-world agentic-DevOps deployments (a documented
  production database-deletion incident, the 2025 DORA report, and a named practitioner's
  account of Anthropic's own internal SRE use of Claude), rendered to PDF.

See [`Lab_Wk1/README.md`](cse636-devops-with-ai-assistance/Lab_Wk1/README.md) and
[`Lab_Wk1/WRITEUP.md`](cse636-devops-with-ai-assistance/Lab_Wk1/WRITEUP.md).

## Week 2: AI Code Review Pipeline + MCP Server

Located in [`cse636-devops-with-ai-assistance/Lab_Wk2`](cse636-devops-with-ai-assistance/Lab_Wk2).

No Docker/Jenkins running on this machine, so this is a local simulation of the lab's pipeline
(same substitution pattern as Weeks 5-7): Lint -> Test -> AI Review stages run against a
sample app, and an MCP server (stdio JSON-RPC, verified with a client handshake) exposes
build status backed by a local fixture instead of a live Jenkins REST API.

- **Pipeline**: `flake8` + `pytest` + a dual-mode AI review step that found a gap (a
  missing bounds check) via static analysis when no `ANTHROPIC_API_KEY` was set.
- **MCP server**: `list_jobs`/`get_build_status`, same tool contract as the course's
  `project/mcp_servers/jenkins_status.py`, confirmed with a subprocess client test.
- **Assignment**: a Claude Code vs. GitHub Copilot integration + governance plan for a
  25-engineer, 150-repo team.

See [`Lab_Wk2/README.md`](cse636-devops-with-ai-assistance/Lab_Wk2/README.md) and
[`Lab_Wk2/WRITEUP.md`](cse636-devops-with-ai-assistance/Lab_Wk2/WRITEUP.md).

## Week 3: Build-Fixer Agent with a Human Approval Gate

Located in [`cse636-devops-with-ai-assistance/Lab_Wk3`](cse636-devops-with-ai-assistance/Lab_Wk3).

Builds the lab document's own official no-GitHub path (its J5 dry-run walkthrough): an agent
detects a failing test, proposes a fix, and stops at a blocking approval gate before anything
is written. Both the approved and declined outcomes are captured from actual runs, not scripted
by hand.

- **Lab**: the buggy calculator from the spec, fixed after a captured approval, re-verified by
  re-running the actual test suite.
- **Assignment**: test-impact analysis (`select_tests.py`, a before/after test-count demo)
  and a single-failure-class remediation agent (detects and gate-fixes unused imports, F401).
- **Guardrails**: documented in `docs/guardrails.md`: single-file scope, single failure
  class, no merge/deploy capability, self-verification via the tool's actual exit code.

See [`Lab_Wk3/README.md`](cse636-devops-with-ai-assistance/Lab_Wk3/README.md) and
[`Lab_Wk3/WRITEUP.md`](cse636-devops-with-ai-assistance/Lab_Wk3/WRITEUP.md).

## Week 4: Time-Series Forecasting for Autoscaling

Located in [`cse636-devops-with-ai-assistance/Lab_Wk4`](cse636-devops-with-ai-assistance/Lab_Wk4).

The Prophet model (`prophet==1.4.0`, `cmdstanpy` backend) installed and fit cleanly on this
machine rather than falling back to a stub, so every number here comes from an actual trained
model.

- **Forecast**: MAE 2.51% CPU / MAPE 9.0% on a held-out 24-hour split; the components plot
  recovers the synthetic trend/weekly/daily signal cleanly.
- **Scaling**: `recommend_replicas()` as a tested pure function, scaling off the upper 80% CI
  band rather than the point forecast (a safety margin against under-forecasting).
- **Assignment**: a cost-impact comparison (static vs. reactive HPA vs. predictive, computed
  from the actual trained model and dataset) showing predictive costs come out slightly *more*
  than reactive here. That's not the flattering "AI saves money" result, but the write-up
  covers when the trade-off is worth it anyway.

See [`Lab_Wk4/README.md`](cse636-devops-with-ai-assistance/Lab_Wk4/README.md) and
[`Lab_Wk4/WRITEUP.md`](cse636-devops-with-ai-assistance/Lab_Wk4/WRITEUP.md).

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
and RCA agents are simulated. The simulated responses are derived from the actual detector and log
output rather than fixed text, so the token counts, costs, and generated reports stay representative
of what a live call would produce.

## Week 6: Gated Incident-Triage and Self-Healing Agents

Located in [`cse636-devops-with-ai-assistance/Lab_Wk6`](cse636-devops-with-ai-assistance/Lab_Wk6).

Covers the Week 6 lab and the assignment:

- **Lab**: a ReAct agent that triages a `payment-svc` error-rate spike using a YAML runbook and
  5 tools, and stops for a human approval before the one destructive action
  (`execute_rollback`).
- **Assignment**: a self-healing agent for a different failure mode: `notify-svc` stuck
  restarting in an OOM crash loop, with its own runbook, 6 tools, a gated `restart_service`,
  and three blast-radius controls (kill switch, error-budget check, a rate limiter on
  remediation). These are checked in code, not just written into the prompt. The captured
  transcript runs two incidents back to back, so the rate limiter blocks the second automated
  restart when the crash loop comes back — the restart-flapping scenario the course notes warn
  about.
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
walks the same runbook a live Claude call would and stops at the same blocking `input()`
approval prompt, so the transcripts come from actual runs rather than being written up after
the fact.

## Week 7: Agentic IaC with an OPA Policy Gate

Located in [`cse636-devops-with-ai-assistance/Lab_Wk7`](cse636-devops-with-ai-assistance/Lab_Wk7).

The Week 7 lab: an agent generates a Terraform S3 bucket, Terraform plans it, and an OPA
policy run through conftest decides whether that plan is allowed — before anything is
applied.

- **The policy gate**, `policy/s3.rego`: 9 rules covering tags, bucket naming, encryption,
  public access, and versioning. It checks *values*, not just that a resource exists, since
  a resource that is present but switched off is exactly what careless and malicious changes
  both look like. 19 Rego unit tests back it.
- **Four Terraform variants**, each with a committed plan: compliant (passes), the Step 4
  break (1 deny), the prompt-injected config (2 denies), and the deprecated inline style.
  All four pass `terraform validate` — only the policy separates them.
- **Prompt-injection demo**: the agent declined the injection, but the write-up argues at
  length why that is an anecdote rather than a control, and shows the parts that don't depend
  on the agent's judgement — OPA blocking the injected plan, and there being no `apply`
  capability anywhere in the toolchain.

Runs offline with mock AWS credentials; no cloud account and no cost. See
[`Lab_Wk7/README.md`](cse636-devops-with-ai-assistance/Lab_Wk7/README.md) for setup and
design decisions, and [`Lab_Wk7/WRITEUP.md`](cse636-devops-with-ai-assistance/Lab_Wk7/WRITEUP.md)
for the Step 5 discussion — including a false positive I shipped into the policy, how it was
caught, and why that failure mode worries me more than the injection did.
