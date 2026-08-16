# Capstone: The End-to-End Pipeline

This is the Week 7 capstone deliverable (not the same thing as the Week 7 *lab*, which is just
`Lab_Wk7`). It integrates all seven weekly labs into one working pipeline, per `week-07-lab.md`'s
Capstone Project Rubric (`C:\Users\salma\code\CSE636\weeks\week-07\week-07-lab.md`, outside this
repo).

## Deliverables

1. **Code repository**: this folder plus `Lab_Wk1`–`Lab_Wk7`. `pipeline.py` is the orchestrator;
   see `../CAPSTONE_INTEGRATION.md` for the stage-by-stage narrative.
2. **`REPORT.md`**: the 4-6 page technical report (architecture, guardrails, lessons learned,
   a concrete improvement suggestion).
3. **`PRESENTATION.md`**: a 15-minute demo script (3 min problem, 8 min demo, 3 min lessons,
   1 min questions), matching the lab doc's presentation guidance.

## Run it

```bash
cd cse636-devops-with-ai-assistance/capstone
python pipeline.py
```

`pipeline.py` itself has no special dependencies, just `subprocess` and `json`. It calls into
each `Lab_WkN`'s own `uv` project for that stage's work. You need `uv` on `PATH` (same as every
other lab in this repo) and, for a live Stage 2, `conftest`. `conftest 0.69.0` (the exact version
`Lab_Wk7/README.md` was built against) is installed at `C:\Users\salma\bin\conftest.exe` in this
environment, so Stage 2 runs live by default now. Without `conftest` on `PATH`, Stage 2 falls back
to citing `Lab_Wk7`'s own already-captured, verified result instead of crashing or faking a pass
(see `REPORT.md` §8).

`transcripts/pipeline_run.txt` is a real captured run (exit code 0, all 5 stages live, including
Stage 2's real `conftest test` invocation — `source: "live_conftest"`).

## What's actually wired vs. narrated

- **Stage 4 → Stage 5 is real data flow.** `Lab_Wk5/src/capstone_signal.py` (new, thin) prints
  the Isolation Forest detector's result as JSON. `pipeline.py` builds an incident description
  from that JSON and passes it to `Lab_Wk6/src/lab/capstone_entry.py` (new, thin), which runs the
  unmodified Week 6 agent against it. Stage 5 doesn't run at all if Stage 4 reports no anomaly.
  The "agent cannot act until an alert has actually fired" guardrail is enforced in `pipeline.py`'s
  control flow, not just asserted in prose.
- **All 5 stages run live** in the current captured run, each the corresponding week's own
  unmodified project (Stage 2 included, now that `conftest` is installed, see above; its
  cached-transcript fallback still exists in code for an environment without `conftest`, but
  isn't the active path here).
- What's **not** wired: each stage still runs in its own process/venv rather than one shared
  service, and Stage 3's forecast doesn't yet feed Stage 5 (see `REPORT.md` §8, a named next step,
  not a hidden gap).
