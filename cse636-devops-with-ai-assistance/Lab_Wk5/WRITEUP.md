# Week 5 — Write-up

## Lab Part B — Reflection Questions

**1. How did input token count correlate with log window size? Was the relationship linear?**

Yes, essentially perfectly linear — `telemetry.estimate_tokens()` uses the standard ~4-chars-per-token
heuristic, so `input_tokens ≈ chars / 4` by construction (see the summary table in
`output/part_b_summary.md`: 862 chars → 260 tokens, 32,914 chars → 8,273 tokens, both ratios ≈3.3-4).
With a real tokenizer on plain-text logs I'd expect the relationship to still be close to linear, with
a slight sub-linear bend from repeated tokens (timestamps, `service=`, `ERROR`) compressing better than
average English prose as the window grows.

**2. At what rate would your agent's LLM cost accumulate at 10 log windows/minute, 24/7, for a month?**

Using the `large (200 lines, incident+recovery)` window as representative (~4,176 input / 75 output
tokens, ≈$0.0137/call):

```
10 calls/min * 60 min * 24 hr * 30 days = 432,000 calls/month
432,000 * $0.0137/call ≈ $5,918/month
```

That's a substantial recurring bill for a single log-analysis agent, and it scales linearly and
automatically with log volume and window size — a noisier month costs more with no approval gate.

**3. What guardrail would you add to prevent runaway costs?**

A per-window **token budget with pre-flight truncation/dedup** (aggregate repeated log lines before
sending), a **rate limiter** on calls/minute, and a **monthly spend cap** enforced client-side that
degrades to a cheaper rule-based fallback once hit — with an alert at ~80% of the cap so a human can
intervene before the hard stop.

**4. What would a production-grade dashboard for this agent look like? List five metrics.**

1. Calls per minute (throughput, and to catch runaway loops)
2. p50/p99 latency per call
3. Cost per hour/day, cumulative against the monthly budget
4. LLM call error/failure rate (timeouts, rate limits, malformed responses)
5. "No anomalies detected" rate over time (a proxy for silent quality drift — an agent that suddenly
   stops flagging anything is a red flag, not a green one)

(Full working versions of the above, generated from the actual run, are also embedded in
`notebooks/analysis.ipynb`.)

---

## Assignment — 1-Page Reflection

**What I built.** A small but complete pipeline: `generate_data.py` produces labelled synthetic
metrics and correlated structured logs; `anomaly_detector.py` runs Isolation Forest (and DBSCAN as a
comparison) with precision/recall/F1 against the known ground truth; `alert_grouper.py` expands the
16 anomalous rows into 48 per-metric alerts and groups them by time-gap into a single incident;
`rca_agent.py` runs an agentic RCA over that incident using two tools (`get_metrics`, `get_logs`) and
a synthesis step, all instrumented with OTel spans following the GenAI semantic conventions.

**Key decisions.** I chose Isolation Forest as the primary detector because `contamination` is a
direct, interpretable prior on the anomaly rate, and I chose rule-based (time-gap) grouping over
LLM-based grouping because it's a deterministic problem that doesn't benefit from an LLM call — using
an agent where a five-line rule suffices would be wasted cost and latency, the opposite lesson of
the guardrails discussion above. Both choices and their trade-offs are detailed in `README.md`.

**What didn't work as expected — honestly.** A few concrete failures during the build:

- `uv` wasn't installed on this machine at all; I had to `pip install --user uv` first, and even then
  the resulting `uv.exe` wasn't on `PATH`, so every invocation went through `python -m uv` instead of a
  bare `uv` command. Minor, but it meant the "just run `uv run ...`" instructions in the assignment
  prompt didn't work out of the box.
- `uv init` defaults to a *packaged* project layout (`src/lab_wk5/__init__.py` + a `[project.scripts]`
  entry point + a build backend). That's wrong for a collection of standalone scripts like this one,
  so I had to delete the generated package and set `[tool.uv] package = false` in `pyproject.toml`
  before `uv sync` would stop trying to build/install the project itself as a wheel.
- The notebook's cells that shell out to `log_analyzer_agent.py` and `rca_agent.py` (via
  `subprocess.run(["python", ...])`) failed on first execution with `ModuleNotFoundError:
  No module named 'opentelemetry'` — even though `uv run jupyter nbconvert --execute` was clearly using
  the project's venv for the *notebook kernel itself*. The bug was that a bare `"python"` string
  resolves to whatever `python` is first on `PATH`, which on this machine is **not** the venv's
  interpreter. Swapping to `sys.executable` (the interpreter actually running the kernel) fixed it
  immediately. This is a good example of an assumption ("the subprocess inherits my environment")
  that's true in a plain shell but silently false inside a Jupyter kernel launched by `uv run`.
- DBSCAN's default-ish parameters (`eps=1.0`, `min_samples=5`, on standardized features) badly
  underperformed Isolation Forest (F1 0.48 vs 0.89) — not a bug, but a genuine, slightly surprising
  result: I expected DBSCAN to do reasonably well since the incident is a dense 16-point cluster, which
  is exactly what DBSCAN is supposed to find. The failure mode is that a dense *anomalous* cluster looks
  identical to a dense *normal* cluster from DBSCAN's point of view — density alone doesn't encode
  "this is far from normal," only "this is close to its neighbors." Isolation Forest's isolation-based
  scoring, by contrast, only cares about typicality relative to the *entire* dataset, which is the right
  inductive bias for this task.

**What I'd do differently with more time.** Tune DBSCAN's `eps`/`min_samples` properly (e.g. via a
k-distance plot) instead of using one fixed guess, to see how close it can get to Isolation Forest;
and wire the RCA agent's `get_logs`/`get_metrics` tools to a real Claude call behind a feature flag, so
switching from simulated to live is a one-line config change rather than a rewrite.
