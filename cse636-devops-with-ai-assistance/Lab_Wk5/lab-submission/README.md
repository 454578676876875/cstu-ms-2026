# Week 5 Lab and Assignment: Anomaly Detection + Agent Instrumentation

This covers the Lab (Part A: anomaly detection, Part B: OTel GenAI instrumentation) and the
Assignment (a small anomaly detection to alert grouping to agentic RCA pipeline) described in
`Lab_Wk5.md.txt`. I put everything in one project because the assignment builds directly on the
lab's detector and agent code.

This folder is a self-contained copy meant for submission. It has its own `src/`, `data/`, and
`analysis.ipynb`, so it can run on its own without the rest of the repo.

## How to run

I used [`uv`](https://docs.astral.sh/uv/) for dependency management, so there's no manual venv
setup. `uv run` finds the project's `.venv` automatically.

```bash
cd lab-submission

# 1. Generate the synthetic data (data/metrics_sample.csv, data/logs_sample.txt)
uv run python src/generate_data.py

# 2. Part A: anomaly detection + evaluation (contamination sweep + DBSCAN comparison)
uv run python src/anomaly_detector.py

# 3. Assignment: rule-based alert grouping (10+ alerts into incident groups)
uv run python src/alert_grouper.py

# 4. Part B: OTel-instrumented log analyzer agent over 5 log windows
uv run python src/log_analyzer_agent.py
#    writes output/part_b_summary.md, output/part_b_spans.log

# 5. Assignment: agentic RCA (2 tools: get_metrics, get_logs) + OTel trace
uv run python src/rca_agent.py
#    writes output/rca_report.md, output/spans_sample.json

# 6. Full notebook (already executed and included as-is)
uv run jupyter nbconvert --to notebook --execute --inplace analysis.ipynb
```

## Project structure

```
data/
  metrics_sample.csv     500-minute synthetic metrics, incident injected at rows 200-215
  logs_sample.txt        structured log lines, with an error/warning burst during the incident

src/
  generate_data.py       builds both datasets above (seeded, so it's repeatable)
  anomaly_detector.py    Isolation Forest (main detector) + DBSCAN (bonus), precision/recall/F1
  alert_grouper.py       turns flagged anomalies into per-metric alerts, groups them by time gap
  telemetry.py           OTel setup + GenAI span helpers, used by both agents
  log_analyzer_agent.py  Part B: simulated-LLM log analysis agent, OTel-instrumented
  rca_agent.py           Assignment: agentic RCA using get_metrics/get_logs tools + a synthesis step

analysis.ipynb           executed notebook: Part A/B walkthrough + assignment visualizations

output/
  rca_report.md          the generated RCA report for the sample incident
  spans_sample.json      captured OTel spans from the RCA agent run
  part_b_summary.md      Part B's window size vs. tokens vs. latency vs. cost table
  part_b_spans.log       captured OTel spans from the Part B agent run

WRITEUP.md               reflection questions (lab) + 1-page reflection (assignment)
```

## Design decisions and trade-offs

**Why the LLM calls are simulated.** I don't have an `ANTHROPIC_API_KEY` set up, and the lab doc
says it's fine to simulate a response if you don't have API access. `telemetry.simulated_llm_call()`
makes up token counts (using the usual ~4 characters per token rule of thumb) and a latency number
based on output length, since that's mostly what drives real Claude response time. The "analysis"
text itself isn't canned. `log_analyzer_agent.simulate_llm_analysis()` and `rca_agent.synthesize_rca()`
build their response from the real input data (error counts, service names, metric changes), so the
numbers and the write-up are still grounded in something real, even without a network call.

**Why Isolation Forest instead of DBSCAN.** Isolation Forest's `contamination` parameter is a
direct, easy-to-reason-about setting for the expected anomaly rate. In this data, the 16 incident
points sit close together (one sustained spike, not scattered outliers), which is the case DBSCAN
tends to struggle with: it can treat a sustained anomaly as its own small dense cluster instead of
noise. The numbers back this up. Isolation Forest gets F1 around 0.89 (contamination=0.04) while
DBSCAN only gets about 0.48 (eps=1.0, min_samples=5). The full contamination sweep is in
`analysis.ipynb`.

**Why alert grouping is rule-based, not LLM-based.** Grouping 48 per-metric alerts into incidents is
a simple, deterministic problem: sort by time, start a new group when the gap since the last alert
gets too big. Using an LLM call here would just add cost and latency without improving accuracy.

**Why the RCA agent only has two tools.** `get_metrics` (baseline vs. incident comparison) and
`get_logs` (matching log lines plus error/warning counts) cover the two evidence sources the
assignment asks for. Both are wrapped as OTel tool spans nested under one `rca_agent.run` trace, so
`output/spans_sample.json` shows a realistic agent trace shape: one parent span, two tool-call
children, one synthesis-call child. This is checked directly in the notebook's last cell.
