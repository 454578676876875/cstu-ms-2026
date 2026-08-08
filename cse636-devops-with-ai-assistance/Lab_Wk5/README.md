# Week 5 — Anomaly Detection + Agent Instrumentation

Covers both the **Lab** (Part A: anomaly detection, Part B: OTel GenAI instrumentation) and the
**Assignment** (a small end-to-end anomaly → alert-grouping → agentic RCA system) from
`Lab_Wk5.md.txt`. Everything lives in this one project since the assignment builds directly on the
lab's detector and agent code.

## How to run

Dependency management is via [`uv`](https://docs.astral.sh/uv/) (no manual venv activation needed —
`uv run` resolves the project's `.venv` automatically).

```bash
cd cse636-devops-with-ai-assistance/Lab_Wk5

# 1. Generate the synthetic datasets (data/metrics_sample.csv, data/logs_sample.txt)
uv run python src/generate_data.py

# 2. Part A — anomaly detection + evaluation (contamination sweep + DBSCAN comparison)
uv run python src/anomaly_detector.py

# 3. Assignment — rule-based alert grouping (10+ alerts -> incident groups)
uv run python src/alert_grouper.py

# 4. Part B — OTel-instrumented log analyzer agent over 5 log windows
uv run python src/log_analyzer_agent.py
#    -> output/part_b_summary.md, output/part_b_spans.log

# 5. Assignment — agentic RCA (2 tools: get_metrics, get_logs) + OTel trace
uv run python src/rca_agent.py
#    -> output/rca_report.md, output/spans_sample.json

# 6. Full notebook (Part A/B + assignment visualizations, already executed and committed)
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/analysis.ipynb

# 7. Run the test suite
uv run pytest -v
```

## Project structure

```
data/
  metrics_sample.csv     500-min synthetic metrics, incident injected at indices 200-215
  logs_sample.txt        769 structured log lines, error/warn burst correlated with the incident

src/
  generate_data.py       builds both datasets above (deterministic, seeded)
  anomaly_detector.py    Isolation Forest (primary) + DBSCAN (bonus), precision/recall/F1 eval
  alert_grouper.py       expands flagged anomalies into per-metric alerts, groups by time-gap
  telemetry.py           OTel TracerProvider setup + GenAI-conventions span helpers (shared)
  log_analyzer_agent.py  Part B: simulated-LLM log analysis agent, OTel-instrumented
  rca_agent.py           Assignment: agentic RCA with get_metrics/get_logs tools + synthesis call

notebooks/
  analysis.ipynb         executed notebook: Part A/B walkthrough + assignment visualizations

output/
  rca_report.md          generated RCA report for the sample incident
  spans_sample.json      captured OTel spans (ConsoleSpanExporter) from the RCA agent run
  part_b_summary.md      Part B's window-size / tokens / latency / cost table
  part_b_spans.log       captured OTel spans from the Part B agent run

tests/
  test_anomaly_detector.py  ground truth, accuracy-trap case, IsoForest recall, contamination sweep
  test_alert_grouper.py     per-metric threshold logic, gap-based grouping (incl. edge cases)
  test_telemetry.py         token/cost estimation, span attributes, parent/child span nesting

WRITEUP.md               reflection questions (lab) + 1-page reflection (assignment)
```

## Key design decisions and trade-offs

**Why simulated LLM calls instead of real Anthropic API calls.** No `ANTHROPIC_API_KEY` is configured
in this environment, and the lab doc explicitly allows simulating the response ("or simulate a
response if you don't have API access"). `telemetry.simulated_llm_call()` fabricates *realistic*
token counts (via the standard ~4-chars/token heuristic) and latency (modeled on output length, since
that's what dominates real Claude latency), and `log_analyzer_agent.simulate_llm_analysis()` /
`rca_agent.synthesize_rca()` derive their response text from the actual input data (error counts,
service names, metric deltas) rather than returning canned text — so the numbers and the "analysis"
are grounded, even if no network call happens. Cost estimates use Anthropic's published per-token
pricing for the (simulated) model.

**Why Isolation Forest over DBSCAN as the primary detector.** Isolation Forest's `contamination`
parameter is a direct, interpretable knob on the expected anomaly rate, and it's built specifically to
isolate rare points via random partitioning. In this dataset the 16 incident points are close to
*each other* in feature space (a sustained spike, not scattered outliers), which is exactly the case
DBSCAN struggles with — density-based clustering tends to absorb a sustained anomaly into its own
small dense cluster rather than flagging it as noise. That's borne out in the numbers: Isolation
Forest reaches F1≈0.89 (contamination=0.04) vs. DBSCAN's F1≈0.48 (eps=1.0, min_samples=5). Full
detail and the contamination sweep are in `notebooks/analysis.ipynb`.

**Why alert grouping is rule-based (time-gap clustering), not LLM-based.** Grouping 48 per-metric
alerts into incidents is a well-defined, cheap, deterministic problem (sort by time, split when the
gap between consecutive alerts exceeds a threshold). Spending an LLM call on it would add cost and
latency for no accuracy benefit — a good example of *not* reaching for an agent when a simple rule
suffices.

**Why the RCA agent has exactly two tools.** `get_metrics` (baseline-vs-incident comparison) and
`get_logs` (matching log lines + error/warn counts) map directly to the two evidence sources named in
the assignment brief. Both are wrapped in `tool_span()` and nested under a single `rca_agent.run`
trace, so the resulting trace in `output/spans_sample.json` shows a realistic agent shape: one parent
span, two tool-call children, one synthesis-call child — verified explicitly in the notebook's last
cell.
