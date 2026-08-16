# Capstone Integration: The Seven Labs as One Pipeline

This ties `Lab_Wk1` through `Lab_Wk7` together into the single end-to-end agentic DevOps
pipeline the course's [capstone rubric](../../code/CSE636/weeks/GROUP_PROJECT_GUIDE.md) asks
for: developer intent flows through CI/CD, IaC, deployment, observability, and remediation, with
a guardrail at every stage. Each lab in this repo is a real, independently runnable local
project (see each `Lab_WkN/README.md` for how to run it).

**This is the narrative walkthrough.** The actual runnable, wired-together capstone deliverable
— an orchestrator that invokes each stage as an actual subprocess, with data threaded between
Stage 4 and Stage 5, plus the 4-6 page report and the presentation script — lives in
[`capstone/`](capstone/). Run `python capstone/pipeline.py` or read
[`capstone/transcripts/pipeline_run.txt`](capstone/transcripts/pipeline_run.txt) for a captured,
end-to-end execution log. What follows here is the stage-by-stage explanation of *why* each
connection exists; `capstone/README.md` documents which connections are live data flow versus
independent-but-adjacent execution.

## The pipeline, stage by stage

### Stage 0 — Baseline environment (Week 1)

**What:** a real cloud/Docker lab environment (`cse636-lab-wk1` container) with a sample repo
(`dockersamples/example-voting-app`) cloned into it, plus collected CI-log and system-metrics
data.

**Feeds forward:** `Lab_Wk1/data/ci-build-log.txt` and `system-metrics.txt` are collected for
reuse "in later labs" (per the lab spec). Week 3's build-fixer agent is the direct continuation
of "here's what a real build log and a real failing/passing pipeline looks like."

**Guardrail:** none yet, this stage is entirely read-only exploration and observation. The
autonomy-level reflection in `Lab_Wk1/WRITEUP.md` argues *for* keeping read tasks unconstrained
(human-on-the-loop) while treating every write task from here on as needing a gate, which is the
shape the rest of the pipeline takes.

### Stage 1 — Agentic CI/CD (Weeks 2 and 3)

**What:** `Lab_Wk2`'s Lint -> Test -> AI Review pipeline plus MCP-exposed build status, and
`Lab_Wk3`'s build-fixer agent that turns a red build into a human-approved fix.

**Guardrail:** a blocking approval gate (`Lab_Wk3/src/common/approval_gate.py`) sits between
"agent proposes a fix" and "fix is written." Both outcomes (approved, declined) are captured
from actual runs in `Lab_Wk3/transcripts/`, and the agent structurally cannot touch more than
one file or merge/deploy anything (`Lab_Wk3/docs/guardrails.md`). Week 2's MCP server is
read-only by construction (`list_jobs`/`get_build_status` only, no write tool exists at all).

### Stage 2 — Agentic IaC (Week 7)

**What:** an agent generates a Terraform S3 bucket; an OPA policy run through `conftest`
decides whether the resulting plan is allowed, before anything is applied.

**Guardrail:** this is policy-as-code rather than code review. `Lab_Wk7/policy/s3.rego`'s 9
rules block a non-compliant plan (`Lab_Wk7/transcripts/03-policy-fail-step4.txt`) regardless of
whether a human or an agent (or a successfully-injected agent) produced it. No `terraform_apply`
tool exists anywhere in the toolchain, so even a fully compromised agent cannot act on what OPA
would have blocked anyway (`Lab_Wk7/docs/step5-prompt-injection.md`).

### Stage 3 — Predictive deploy (Week 4)

**What:** a Prophet forecast of CPU load translated into a replica-count recommendation and a
real cost-impact comparison against reactive HPA and static over-provisioning.

**Guardrail:** the recommendation scales off the upper 80% confidence bound instead of the
point forecast, a quantified safety margin against under-provisioning a spike the model got
wrong (`Lab_Wk4/WRITEUP.md`). `Lab_Wk4/ASSIGNMENT.md`'s finding that predictive costs run
*slightly more* than reactive here works as its own guardrail against over-trusting a forecast:
the recommendation is to layer predictive under reactive, never to replace it.

### Stage 4 — Observability (Week 5)

**What:** an Isolation Forest anomaly detector, rule-based alert grouping, and an
OTel-GenAI-instrumented RCA agent (`Lab_Wk5`).

**Guardrail:** every model and agent step carries an OpenTelemetry span (service *and* agent
telemetry, per the course's Week 5 requirement). The RCA agent's two tools (`get_metrics`,
`get_logs`) are both read-only, so this stage can diagnose but never act.

### Stage 5 — Auto-remediate (Week 6)

**What:** a ReAct incident-triage agent with a YAML runbook, gated at the one destructive
action (`execute_rollback` / `restart_service`) by an approval prompt, backed by three in-code
blast-radius controls (kill switch, error-budget gate, remediation rate limiter), from
`Lab_Wk6`.

**Guardrail:** the rate limiter is demonstrated blocking a *second* automated restart for the
same recurring failure in the same captured run (`Lab_Wk6/transcripts/assignment_transcript.txt`),
the restart-flapping scenario the course notes warn about, shown happening and getting stopped
in the transcript rather than just described.

## How the guardrail pattern compounds

Reading Weeks 1 through 7 in order, the same four guardrail primitives reappear and get
stricter each time a stage gets closer to something destructive:

1. **Read before write is unconstrained; write always gates.** Week 1's reflection states this
   as a principle; every later week's agent that can write something (Week 2's review is
   comment-only, Week 3/6's fixes are approval-gated, Week 7's apply doesn't exist at all)
   follows it in code, not just in a system prompt.
2. **Blast radius shrinks with proximity to production.** Week 3's agent can touch one file;
   Week 6's agent can call exactly one destructive tool, rate-limited and kill-switched; Week
   7's toolchain has no destructive tool at all. Each stage is strictly *more* constrained than
   the one before it, matching how much closer it sits to affecting a running system.
3. **Self-verification, not self-report.** Week 3's build-fixer re-runs the real test suite
   after applying a fix rather than trusting its own claim of success; Week 6's agent's
   `get_metrics`/`get_pod_status` reflect real post-action state; Week 7's OPA gate inspects the
   actual resulting plan, not the agent's description of what it did.
4. **A policy/logic layer decides, the agent only proposes.** This is Week 7's own stated
   thesis ("the agent proposes, the policy decides") but it's true of every stage: Week 3's
   `check_blast_radius()`, Week 6's blast-radius checks, and Week 7's Rego rules all live in
   code the agent cannot talk its way past. That's the same answer, repeated at every stage, to
   this course's recurring question: what stops a capable-but-wrong (or successfully injected)
   agent from mattering?

## What's wired together live, and what isn't

`capstone/pipeline.py` runs all five stages as actual subprocesses in one execution. One
connection is threaded data flow rather than narrative adjacency: **Stage 4 → Stage 5**.
`Lab_Wk5/src/capstone_signal.py` (a new, thin entry point; no detection logic changed) prints
the Isolation Forest result as JSON, and the orchestrator builds Stage 5's incident description
from that JSON before calling `Lab_Wk6/src/lab/capstone_entry.py` (also new and thin) to run
the unmodified Week 6 agent against it. Stage 5 only runs if Stage 4 reports an anomaly, which
is enforced in `pipeline.py`'s control flow and matches the pipeline diagram's decision diamond
in the actual code, not only in the write-up.

Each `Lab_WkN` still runs in its own `uv` project/process rather than one shared always-on
service. No Jenkins, Terraform backend, or OTel collector is actually standing up anywhere,
since this is a local, simulation-based submission environment (each week's own README states
which piece of infrastructure it substitutes for and why). Stage 2 (Wk7's OPA gate) now runs
fully live: `conftest 0.69.0` is installed, matching the exact version `Lab_Wk7/README.md`
documents building against. The code path that degrades gracefully (citing `Lab_Wk7`'s own
prior verified transcript instead of faking a pass) is still there for an environment without
`conftest`, it's just not the active path here. See `capstone/REPORT.md` §8 for that history,
and its suggestion for what a next iteration (Stage 3 → Stage 5 as a second live connection)
would add.
