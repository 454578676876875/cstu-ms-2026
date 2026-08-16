# Week 6 Write-up

## Lab: Reflection (payment-svc gated rollback)

**At what level of autonomy did your agent operate? Was that the right choice?**

For the only destructive action (`execute_rollback`), the agent operates at Level 2, "Draft &
confirm": it stages the action (`dry_run_rollback`) and blocks on a named human approval before
executing. Read-only tools run unrestricted -- there's nothing to gate about reading data. That
split is right for this case: a `NullPointerException` eight minutes after a deploy is about as
textbook a rollback as incident response gets, but "textbook" is exactly the confidence that
makes an agent over-trust one signal. A human typing their name into the audit log costs a few
seconds and catches what the runbook's static branches can't, like whether on-call is already
mid-firefight on something related.

**What guardrails did you implement beyond the approval gate?**

Least privilege: exactly five tools, and `dry_run_rollback` is required before
`execute_rollback` by both the runbook's step order and an explicit system-prompt rule.
`approved_by` only ever comes from the terminal prompt, never synthesized by the agent.
Honestly, that's the extent of it for the lab -- no rate limiter or kill switch here, since the
lab doesn't ask for them (built for the assignment instead). Real gap worth naming: this agent
alone would happily re-process a declined rollback a second time with no cooldown, the exact
flapping risk the assignment's guardrails close.

**What would you need to add to deploy this against a real Kubernetes cluster safely?**

A rate limiter and kill switch (ported from the assignment), an RBAC-scoped service account
instead of a trusted in-process dict, idempotency protection against duplicate alerts,
structured audit logging instead of stdout prints, and timeouts around every tool call -- right
now a hung `kubectl` call would leave the loop stuck indefinitely with no fallback.

**What surprised you about the agent's reasoning?**

Two things. First, the lab's given template's `execute_tool` always returns the same elevated
`error_rate` for `payment-svc`, even after a rollback, so a literal read of the runbook's
`verify` step would escalate every successful rollback as a failure. I only caught this by
tracing what the agent would actually observe, which is why `react_agent.py` here tracks
rollback state so verification means something. Second: writing the simulated brain made "the
ReAct loop" feel less like a vague pattern and more like a literal state machine -- almost the
whole agent turned out to be re-reading the runbook's `on_result` branches in order, grounded in
the previous tool's real output.

---

## Assignment: Safety Discussion (notify-svc self-healing agent)

Where the other pieces of this assignment live: [`diagrams/architecture.svg`](diagrams/architecture.svg)
(architecture, gates, autonomy levels), [`runbooks/assignment-notify-svc-oom-crashloop.yaml`](runbooks/assignment-notify-svc-oom-crashloop.yaml)
(runbook), [`src/assignment/`](src/assignment/) (agent code), [`transcripts/assignment_transcript.txt`](transcripts/assignment_transcript.txt)
(two-incident transcript). More on why I made the choices I did is in `README.md`.

**What failure modes exist in this agent?** The log-signature match (`"OutOfMemoryError" in
logs`) is a naive substring check -- a log line that mentions the string incidentally, in a
comment or a deeper unrelated stack frame, would trip the same branch and burn the rate
limiter's one restart attempt on something a restart can't fix. `get_metrics` and
`get_pod_status` are point-in-time snapshots with no staleness check; a live version pulling
from Prometheus could act on numbers that were already stale by the time the tool call
returned during a fast-moving incident. There's approval fatigue risk too: if this crash loop
pages every ten minutes because the rate limiter's cooldown is short, an on-call could start
rubber-stamping "yes" without reading the dry-run output, which quietly defeats the gate's
purpose. And `approved_by` is just a free-text field -- nothing actually checks that the name
typed at the terminal is who it says it is.

**How would the blast-radius controls limit damage from a wrong decision?** The rate limiter
caps the worst case at one automated restart per service per ten-minute window -- demonstrated
live in `assignment_transcript.txt`, where the exact restart-flapping scenario from
week-06-notes.md's "Levels of Autonomy & Blast-Radius Control" check-your-understanding gets
blocked on the second incident, before a dry run is even attempted. The error-budget gate
refuses to spend a service's remaining reliability margin on a guess: if `error_budget_remaining`
is already low from an unrelated cause, automated restarts are refused even with a perfect
OOM signature match, forcing a human into the loop instead of a static rule deciding alone.
The kill switch is there for whatever I didn't think of -- it's just one environment variable,
checked first, and it doesn't care whether the rest of the reasoning was right or wrong.

**How would I test this before pointing it at a real system?** Replay a corpus of real
(redacted) incident logs against the signature matcher to measure its false-positive rate
before trusting it live. Specifically chaos-test the guardrails under duplicate/concurrent
alert delivery, since a race condition in shared rate-limiter state is exactly where a control
silently stops working without anyone noticing. Run the agent in Level-1-only "recommend"
mode for a probation period -- log what it would have restarted without ever calling
`restart_service` -- and compare its calls against what the on-call actually did. And unit-test
every blast-radius control against its exact boundary condition, the way `tests/test_blast_radius.py`
does here, but against the real Prometheus/Kubernetes client rather than simulated data.

**What additional guardrails would I add before production?** Idempotency keys so a duplicate
alert can't fire two concurrent restarts of the same rollout; a canary restart (one pod, watch
60 seconds, then the rest) instead of an all-at-once rolling restart; a structured, queryable
audit log of every gate decision instead of stdout prints; and a system-wide daily cap on
total automated actions, not just a per-service one, so a bug that fires across many services
at once can't slip past a control that only looks at one service at a time.
