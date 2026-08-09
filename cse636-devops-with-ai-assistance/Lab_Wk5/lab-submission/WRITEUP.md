# Week 5 Write-up

## Lab Part B: Reflection Questions

**1. How did input token count correlate with log window size? Was the relationship linear?**

Pretty much perfectly linear. `telemetry.estimate_tokens()` just uses the usual ~4 characters per
token rule, so `input_tokens` is roughly `chars / 4` by definition (see `output/part_b_summary.md`:
862 chars gave 260 tokens, 32,914 chars gave 8,273 tokens, both around that same ratio). With a real
tokenizer I'd expect it to still be close to linear, maybe slightly less than linear as the window
grows, since repeated stuff like timestamps and `service=` and `ERROR` compresses a bit better than
normal English text.

**2. At what rate would your agent's LLM cost accumulate at 10 log windows/minute, 24/7, for a month?**

Using the "large (200 lines)" window as a typical case (about 4,176 input tokens, 75 output tokens,
roughly $0.0137 per call):

```
10 calls/min * 60 min * 24 hr * 30 days = 432,000 calls/month
432,000 * $0.0137/call = about $5,918/month
```

That's a lot of money for just one log-analysis agent, and it scales up automatically with log
volume. No one has to approve a bigger bill, it just happens.

**3. What guardrail would you add to prevent runaway costs?**

I'd add a token budget per window (truncate or dedupe repeated log lines before sending), a rate
limit on calls per minute, and a monthly spend cap that falls back to a cheaper rule-based check once
it's hit. I'd also alert at around 80% of the cap so someone can step in before it's a hard stop.

**4. What would a production-grade dashboard for this agent look like? List five metrics.**

1. Calls per minute (to catch runaway loops and see load)
2. p50/p99 latency per call
3. Cost per hour or day, tracked against the monthly budget
4. Error rate on LLM calls (timeouts, rate limits, bad responses)
5. Rate of "no anomalies detected" over time, since an agent that suddenly stops flagging anything is
   probably broken, not doing great

(The actual numbers behind these answers are also shown in `analysis.ipynb`.)

---

## Assignment: 1-Page Reflection

**What I built.** A small pipeline: `generate_data.py` makes labelled synthetic metrics and matching
structured logs. `anomaly_detector.py` runs Isolation Forest (and DBSCAN for comparison) and checks
precision/recall/F1 against the known ground truth. `alert_grouper.py` turns the 16 anomalous rows
into 48 per-metric alerts and groups them by time gap into one incident. `rca_agent.py` runs an
agentic RCA on that incident using two tools (`get_metrics`, `get_logs`) plus a synthesis step, all
instrumented with OTel spans following the GenAI conventions.

**Key decisions.** I picked Isolation Forest as the main detector because `contamination` is an easy
parameter to reason about for the expected anomaly rate. I used rule-based (time-gap) grouping
instead of an LLM for alerts because it's a simple, deterministic problem that doesn't need an LLM
call. Using an agent where a five-line rule works fine would just waste money and time, which is kind
of the opposite lesson from the guardrails discussion above. More detail on both is in `README.md`.

**What didn't work as expected, honestly.** A few real problems came up while building this:

- `uv` wasn't installed on my machine at all. I had to `pip install --user uv`, and even then the
  installed `uv.exe` wasn't on `PATH`, so I ended up running `python -m uv` instead of a plain `uv`
  command the whole time.
- `uv init` sets up a packaged project by default (a `src/lab_wk5/__init__.py` package plus a script
  entry point and a build backend). That's the wrong shape for a folder of plain scripts, so I had to
  delete the generated package and add `[tool.uv] package = false` before `uv sync` would stop trying
  to build the project as a wheel.
- The notebook cells that call `log_analyzer_agent.py` and `rca_agent.py` through
  `subprocess.run(["python", ...])` failed the first time with `ModuleNotFoundError: No module named
  'opentelemetry'`, even though the notebook itself was clearly running inside the project's venv.
  Turned out a plain `"python"` string just grabs whatever `python` is first on `PATH`, which wasn't
  the venv's interpreter. Switching to `sys.executable` fixed it right away. I hadn't realized a
  subprocess launched from a Jupyter kernel doesn't automatically use the same interpreter.
- DBSCAN did much worse than Isolation Forest (F1 about 0.48 vs. 0.89) with `eps=1.0, min_samples=5`.
  This one actually surprised me. I expected DBSCAN to do fine since the incident is basically one
  dense cluster of 16 points, which sounds like exactly what DBSCAN should find. The problem is that a
  dense cluster of anomalies looks the same to DBSCAN as a dense cluster of normal points. Density
  alone doesn't tell you "this is far from normal," just "this is close to its neighbors." Isolation
  Forest looks at how typical a point is compared to the whole dataset, which fits this problem
  better.

**What I'd do differently with more time.** I'd actually tune DBSCAN's `eps` and `min_samples`
properly instead of guessing one value, maybe using a k-distance plot, to see how close it can get to
Isolation Forest. I'd also connect the RCA agent's tools to a real Claude call behind a flag, so
switching from simulated to live would just be a config change instead of a rewrite.
