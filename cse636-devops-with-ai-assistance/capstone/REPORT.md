# Capstone Technical Report: An End-to-End Agentic DevOps Pipeline

Salman, CSE636, Week 7 Capstone

## 1. Overview

This capstone integrates the seven weekly labs in this repository (`Lab_Wk1`–`Lab_Wk7`) into the
pipeline the course diagrams: Agentic CI/CD, Agentic IaC, Predictive Deploy, Observability,
Auto-remediate, with a guardrail at every stage. `capstone/pipeline.py` orchestrates an
end-to-end run by invoking each week's lab project as a subprocess in its own `uv` environment.
The full captured output is in `capstone/transcripts/pipeline_run.txt` (a real run, exit code 0,
not edited by hand).

I added two small, clearly-marked integration files to make Stage 4 → Stage 5 an actual data
dependency instead of just two labs described as adjacent: `Lab_Wk5/src/capstone_signal.py`
(prints the Isolation Forest detector's result as JSON) and `Lab_Wk6/src/lab/capstone_entry.py`
(runs the Week 6 agent against an incident description built from that JSON, instead of the
hardcoded string in the original lab file). Neither the agent logic nor the detection logic
changed; both files are thin entry points around existing, unmodified code.

## 2. Architecture

```
Developer intent ("deploy checkout v2.3.1")
        │
        ▼
Stage 1 — Agentic CI/CD (Wk 2 + 3)
  Lint → Test → AI Review (Wk2) ── code review comment, non-blocking
  Single-failure-class remediation check (Wk3) ── F401 unused-import gate
  Guardrail: approval gate before any write; MCP server is read-only
        │  pipeline_passed
        ▼
Stage 2 — Agentic IaC (Wk 7)
  Terraform generation → OPA policy (conftest) → apply gate
  Guardrail: no apply tool exists; policy blocks before any apply
        │  opa_passed
        ▼
Stage 3 — Predictive Deploy (Wk 4)
  Prophet forecast → replica recommendation → cost-impact comparison
  Guardrail: scales off the upper 80% CI, not the point forecast
        │  forecast_ok
        ▼
Stage 4 — Observability (Wk 5)
  Isolation Forest anomaly detector over service metrics
  Guardrail: read-only; produces a signal, takes no action
        │  anomaly_detected? ──── NO ──→ deployment complete
        │ YES
        ▼
Stage 5 — Auto-remediate (Wk 6)
  ReAct triage agent: get_metrics → get_logs → get_deploy_history →
  dry_run_rollback → [human approval gate] → execute_rollback → verify
  Guardrail: blast-radius-limited tools, blocking approval, self-verification
        │
        └──→ loop back to re-observe (Stage 4)
```

Every arrow in this diagram that crosses a Lab_WkN boundary is either (a) a subprocess call with
data actually threaded through (Stage 4 → Stage 5, the anomaly signal), or (b) an independent
execution of that stage's own project, captured in the same pipeline run (Stages 1, 3, 4 always;
Stage 2 falls back to a cached but real, previously-captured result, see §4). Everything here has
a corresponding line in `capstone/transcripts/pipeline_run.txt`.

## 3. Levels of Autonomy Per Stage (Week 1 thread)

| Stage | Autonomy level | Where the human sits |
|---|---|---|
| CI/CD — AI review (Wk2) | Assistant / human-on-the-loop | Comment posted, no block; human reads whenever they choose |
| CI/CD — remediation (Wk3) | Human-in-the-loop | Agent proposes a fix, blocking approval gate before write (see `Lab_Wk3/transcripts`) |
| IaC — OPA gate (Wk7) | Not agent autonomy at all — a deterministic policy layer | Policy, not a human, makes the block/allow call; a human approves the *plan* separately per the lab's Step 4 flow |
| Predictive deploy (Wk4) | Assistant | Produces a recommendation; nothing in this repo auto-applies a scaling decision |
| Observability (Wk5) | Human-on-the-loop | Detector runs continuously and reports; a human (or Stage 5's gated agent) decides what to do with a flag |
| Auto-remediate (Wk6) | Human-in-the-loop for the one destructive action | `execute_rollback` blocks on `request_human_approval()` — a real terminal prompt, not a timeout-based auto-approve (`Lab_Wk6/src/common/approval_gate.py`) |

The pattern across all seven weeks, stated once here and demonstrated stage-by-stage in
`cse636-devops-with-ai-assistance/CAPSTONE_INTEGRATION.md`, is that read access is unconstrained,
write access always gates, and blast radius shrinks the closer a stage sits to production. Week
3's agent can write one file. Week 6's agent can call exactly one destructive tool, rate-limited
and kill-switched in `Lab_Wk6/src/common/blast_radius.py`. Week 7's toolchain has no destructive
tool at all.

## 4. Agent Security and Guardrails (at least two, demonstrated)

1. **Blocking human approval gate**, not a timeout-based default-approve. Demonstrated twice in
   this pipeline run: implicitly in Stage 1 (Wk3's remediation agent would have gated a real
   finding, it found none this run, which is itself a "clean" result, see §6) and explicitly in
   Stage 5 (`transcripts/pipeline_run.txt` lines ~141-146: the pipeline's stdin answers "yes" and
   "Capstone-Pipeline-Operator", and that name appears in the tool call and the postmortem, which
   is how I can tell the approval was actually consumed and not bypassed).
2. **Least-privilege tools / no destructive capability at all** for Stage 2. `Lab_Wk7`'s
   toolchain has no `terraform_apply` or `destroy` tool anywhere, demonstrated in
   `Lab_Wk7/docs/step5-prompt-injection.md`: even when the agent was shown a prompt-injection
   payload, OPA independently blocks the resulting bad config, and there's no tool path from
   agent output to a real `apply` regardless of what the agent decides.
3. **Self-verification over self-report**, a third guardrail worth calling out: Stage 5's agent
   re-checks `get_metrics` after `execute_rollback` and only declares the incident resolved
   because the tool result shows `error_rate=0.006`, not because it assumes the rollback worked
   (`transcripts/pipeline_run.txt` lines 149-151).

## 5. Observability (service + agent telemetry)

- **Service-level:** Stage 4's Isolation Forest evaluates against a labeled ground-truth window
  (`Lab_Wk5/src/anomaly_detector.py`), producing precision/recall/F1. This run: precision 0.8,
  recall 1.0, f1 0.889, 20 points flagged, first flag at index 188, which is 4 minutes before the
  labeled incident starts at index 200. The interesting part is that the detector flagged early,
  not late (see §7).
- **Agent-level:** `Lab_Wk5`'s RCA agent and `Lab_Wk6`'s ReAct agent both produce a full
  Thought → Action → Observation trace (`Lab_Wk5/output/spans_sample.json` uses OTel
  GenAI-convention spans; `Lab_Wk6`'s trace is printed inline, same shape, captured per-run in
  `transcripts/`). This capstone run's Stage 5 output is that trace, end to end, from incident to
  postmortem.

## 6. Auto-Remediation with Blast-Radius Control

Stage 5 only runs if Stage 4 actually reports `anomaly_detected: true`. The pipeline's own
`main()` checks `obs.get("signal")` before calling `stage5_auto_remediate`, so "the agent cannot
act until an alert has actually fired" (the course's own Stage 4 guardrail line) is enforced in
code, not just narrated. Within Stage 5, `execute_rollback` is scoped to exactly one service,
requires a prior `dry_run_rollback`, and cannot run without `approved_by`. See
`Lab_Wk6/src/lab/react_agent.py`'s tool definitions and `Lab_Wk6/WRITEUP.md` /
`docs/guardrails.md` for the assignment's additional kill-switch and rate-limiter controls (not
exercised by this particular capstone run, but demonstrated in
`Lab_Wk6/transcripts/assignment_transcript.txt`, where the rate limiter blocks a second automated
restart of the same recurring failure).

An ITSM-equivalent record is the postmortem draft printed at the end of Stage 5
(`transcripts/pipeline_run.txt` lines 155-162), a structured summary generated from the actual
tool calls made during this run, not a template filled with placeholders.

## 7. Audit Trail and Governance

- **Structured, per-action logging:** every tool call in Stage 5 prints its name, its input, and
  its result before the agent reasons about it, visible verbatim in
  `transcripts/pipeline_run.txt`.
- **Timestamped human approval:** the approver's name (`Capstone-Pipeline-Operator`, supplied via
  the orchestrator's stdin, standing in for a real operator's name in an interactive run) is
  threaded through the tool call and the final postmortem, so there's a durable link between who
  approved this and what happened as a result.
- **SLSA-adjacent provenance for the IaC artifact:** `Lab_Wk7`'s committed `plans/*.json` (the
  `terraform show -json` output for every variant) is the auditable record of what was actually
  evaluated by the policy gate, not what the agent claims it generated.

## 8. Lessons Learned

**What worked better than expected:** wiring Stage 4 into Stage 5 with actual data, instead of
just describing two labs as adjacent, surfaced a result I didn't expect going in. The detector's
`first_flagged_index` (188) comes before the labeled incident window starts (200-215). This isn't
a bug. Isolation Forest scores every point by how unusual its feature combination is relative to
the whole dataset, and the metrics apparently started drifting a few minutes before crossing
whatever threshold the ground-truth label used. It's a small "leading indicator" result, and you'd
only see it by actually running the detector against real data and checking the index, not by
describing the two labs as connected in a paragraph.

**What didn't work as cleanly at first:** the first version of this report was written before
`conftest` was installed in this environment, so Stage 2 (Wk7's OPA gate) fell back to citing
`Lab_Wk7`'s own previously-captured transcript instead of running live. The orchestrator said so
in its output rather than crashing or silently faking a pass. `conftest 0.69.0` (matching the
exact version `Lab_Wk7/README.md` was built against) has since been installed
(`C:\Users\salma\bin\conftest.exe`), so the current `transcripts/pipeline_run.txt` has Stage 2
running live now (`source: "live_conftest"`, 9/9 passes), and all four of `Lab_Wk7`'s policy
variants plus its 19 Rego unit tests were independently re-verified live and matched the
previously-captured/hand-traced results exactly. I left the fallback code path in `stage2_iac()`
in place regardless, since a fresh environment without `conftest` should still degrade cleanly
instead of breaking.

**What I'd do differently:** connect Stage 3 (predictive deploy)'s replica recommendation into
Stage 5 as well. Right now Stage 5 gets Stage 4's anomaly signal but has no visibility into Stage
3's "no change, 4 replicas" decision from the same run, even though an actual incident response
would want to know whether the service had just been scaled up right before the alert fired.
That's a natural next integration point I ran out of scope for in this pass.

## 9. Concrete Suggestion for Improvement

Add a **shared incident-context object**: a small JSON schema (service name, current deploy
version, recent scaling decisions, recent anomaly signals) that every stage writes to and every
later stage reads from, instead of the current ad-hoc "Stage N's stdout, parsed by Stage N+1's
orchestrator code" pattern. This capstone's Stage 4 → 5 wiring shows the concept works, but
hand-building a bespoke JSON contract per pair of stages doesn't scale past the two I actually
connected. A shared schema would let Stage 3's forecast, Stage 4's anomaly, and Stage 5's
remediation all reason about the same incident without three separate ad-hoc parsers.
