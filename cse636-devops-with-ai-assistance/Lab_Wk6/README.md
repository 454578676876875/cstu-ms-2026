# Week 6 Lab and Assignment: Gated Incident-Triage Agents

This covers the Week 6 lab (a ReAct incident-triage agent for `payment-svc` with a gated
rollback) and the assignment (a self-healing agent for `notify-svc` with blast-radius
controls), both described in `week-06-lab.md`. Same as Week 5, I kept both in one project
because the assignment reuses the lab's approval gate and runbook loader.

## How to run

Managed with [`uv`](https://docs.astral.sh/uv/). `uv run` finds the project's `.venv` on its
own; if `uv` isn't on your `PATH`, `python -m uv` works too.

```bash
cd cse636-devops-with-ai-assistance/Lab_Wk6

# 1. Lab: triage a payment-svc rollback incident (approve when prompted)
uv run python src/lab/react_agent.py

# 2. Sanity-check the lab's MCP server tool handlers directly
uv run python -c "
import asyncio, sys; sys.path.insert(0, 'src')
from lab.incident_tools_server import list_tools
print(asyncio.run(list_tools()))
"

# 3. Assignment: triage two notify-svc OOM-crash-loop incidents back to back
#    (the second one gets blocked by the rate limiter, see below)
uv run python src/assignment/react_agent.py

# 4. Assignment bonus: same incident with the kill switch engaged
AUTOHEAL_KILL_SWITCH=1 uv run python -c "
import sys; sys.path.insert(0, 'src')
from assignment.react_agent import run_agent
run_agent('ALERT: notify-svc has restarted 4 times in the last 15 minutes.', service='notify-svc')
"

# 5. Run the test suite
uv run pytest -v
```

I don't have `ANTHROPIC_API_KEY` set up on this machine, and week-06-lab.md's setup table
says that's okay ("an Anthropic API key, or the provided simulation mode"). So both agents run
in simulation mode by default: a small scripted "brain" in `simulated_brain.py` walks the same
runbook a live Claude call would, prints the same Thought → Action → Observation shape, and
stops at the same real approval gate (an actual `input()` prompt, not a mock). If you do set
`ANTHROPIC_API_KEY`, both agents switch over to `run_agent_live()` automatically, which is the
real Claude tool-use loop from Step 3 of the lab doc. Same tools, same approval gate, same
blast-radius checks either way.

## Project structure

```
runbooks/
  lab-payment-svc-high-error-rate.yaml       lab runbook (from week-06-lab.md, reproduced verbatim)
  assignment-notify-svc-oom-crashloop.yaml   assignment runbook (new failure mode, see below)

src/
  common/
    approval_gate.py     shared human-approval gate (real input(), blocks until answered)
    runbook.py            YAML runbook loading (raw text for prompts, parsed dict for the brain)
    blast_radius.py       KillSwitch, RemediationRateLimiter, ErrorBudgetGate (assignment only)
  lab/
    incident_tools_server.py   MCP server: get_metrics/get_recent_logs/get_deployment_history/
                                dry_run_rollback/execute_rollback for payment-svc
    react_agent.py              dual-mode (live/simulated) ReAct agent + gated rollback
    simulated_brain.py          scripted ReAct trace for simulation mode, grounded in real tool output
  assignment/
    incident_tools_server.py   MCP server: 6 tools for notify-svc (adds get_pod_status, renames
                                the remediation pair to dry_run_restart/restart_service)
    react_agent.py              dual-mode agent + gated restart + blast-radius enforcement
    simulated_brain.py          scripted ReAct trace for the OOM-crash-loop runbook

diagrams/
  architecture.svg      1-page self-healing architecture diagram (gates, autonomy levels, kill switch)

transcripts/
  lab_transcript_approved.txt           full lab run: rollback approved, incident resolved
  lab_transcript_declined.txt           stretch test: rollback declined, agent escalates
  assignment_transcript.txt             two notify-svc incidents back to back (see below)
  assignment_transcript_declined.txt    restart declined, agent escalates
  assignment_transcript_kill_switch.txt bonus: kill switch blocks remediation immediately

tests/
  test_runbook.py            YAML loading, both runbooks' structure
  test_blast_radius.py       KillSwitch / RemediationRateLimiter / ErrorBudgetGate in isolation
  test_lab_agent.py          execute_tool's simulated state (rollback recovery, dry-run purity)
  test_lab_brain.py          simulated_brain's migration-pending branch (faked, since the static
                              fixture data never exercises it on its own)
  test_assignment_agent.py   check_blast_radius, the verify-window state machine, guarded tool calls

WRITEUP.md               lab reflection (300-400 words) + assignment safety discussion (400-600 words)
```

## What the transcripts show

If you only read one, make it `assignment_transcript.txt`. It runs two incidents back to back
in the same process. The first is a real OOM crash loop, and the agent handles it the way
you'd hope: diagnoses it, passes all three blast-radius checks, gets a human to approve, and
restarts the pods. Three minutes later in the story (instantly in real time), a second alert
fires for the exact same symptom. That's on purpose. A restart only clears the leaked memory,
it doesn't fix the leak, so the crash loop comes right back. The agent diagnoses it the same
way as the first time, but now `check_blast_radius()` comes back `False` before it even
attempts a dry run, because `RemediationRateLimiter` remembers the last restart was under 10
minutes ago. So it escalates and never shows the approval prompt at all. I didn't hand-script
that second outcome separately, by the way — it's the exact same function call as the first
incident, just running against different state by the time it fires. Basically this is the
restart-loop scenario from the check-your-understanding box in week-06-notes.md's "Levels of
Autonomy & Blast-Radius Control" section, played out for real instead of just described.

`assignment_transcript_kill_switch.txt` shows the same incident with `AUTOHEAL_KILL_SWITCH=1`
set. The agent still diagnoses it normally, since read-only tools aren't gated, but gets
blocked before the dry run no matter what the error budget or rate-limit state look like. The
error-budget gate doesn't get its own transcript, but it's exercised directly in
`tests/test_assignment_agent.py::test_check_blast_radius_blocks_on_low_error_budget`.

## Design decisions

Blast-radius checks live in the tool-execution code, not in the system prompt. The lab's
given `react_agent.py` just tells Claude "always run dry_run_rollback before
execute_rollback" as a plain instruction, which is fine for what the lab is asking. But for
the assignment I didn't want to trust the model to keep following a rule like that on its own,
so the kill switch, error-budget, and rate-limiter checks all happen in `check_blast_radius()`,
called by the code itself before `dry_run_restart` or `restart_service` can run — in both live
mode and simulation mode. In live mode this check specifically runs before the approval prompt
even shows up. An earlier version of this had that backwards (asked for approval, then checked
blast-radius), which meant an operator could get asked to approve a restart that was already
going to be blocked anyway. Caught that in a review pass and fixed the ordering. The model
still gets told why a check failed, since the block reason comes back as the tool result, but
it can't just talk its way past the rule.

`execute_tool` also keeps a little bit of state, which the lab's starter code doesn't do. In
the given `react_agent.py`, `execute_tool("get_metrics", ...)` always returns the same
elevated numbers for `payment-svc` no matter what happens, so the runbook's own `verify` step
could never actually see things improve. I added `_ROLLED_BACK` in the lab agent and
`_VERIFY_PENDING` in the assignment agent so `get_metrics`/`get_pod_status` actually reflect
what the agent just did. For the assignment this is also what makes the two-incident
rate-limiter demo work: the pod looks healthy for exactly one check right after the restart,
then goes back to looking sick, which matches the "leak resumes" story the runbook tells.

I also had to pin `mcp` below 2.0. `uv sync` resolves it to 2.0.0 by default, and that version
dropped the `@server.list_tools()` / `@server.call_tool()` decorator style the lab's template
code is written against, in favor of a different API. `pyproject.toml` pins `mcp>=1.2,<2.0`,
which resolves to 1.29.0 and still has the old decorators, so both `incident_tools_server.py`
files actually run instead of throwing an AttributeError on import.

The MCP server files aren't just there for show, either. The lab's own starter code admits in
a comment that `execute_tool()` doesn't really talk to the MCP server at runtime ("in a real
system, these call the MCP server"), and I kept that same split because it's what the lab asks
for: one file with the tool schema, one file with the agent. Both `incident_tools_server.py`
files still work if you call `list_tools()`/`call_tool()` on them directly, which is what the
`uv run python -c "..."` command above checks.

As for why I didn't just reuse payment-svc/rollback for the assignment: the assignment wants
its own runbook with its own decision logic, and reusing the lab's exact scenario would've
made the remediation and verification sections basically the same thing twice. Restarting pods
for a memory leak felt like a genuinely different situation than rolling back a bad deploy,
since a restart only buys time instead of fixing anything. That gap is basically what the rate
limiter and the runbook's "second crash loop means a code fix, not another restart" note are
built around.

## Rubric coverage

Here's how each thing `week-06-lab.md` grades against maps to where it actually shows up in
this repo.

### Lab -- "Check your understanding: prove the gate and the loop"

| What it asks for | Where it's shown |
|---|---|
| A ReAct trace -- a Thought before each tool call, not just actions | `simulated_brain.py` prints `[Agent Thought]` before every `[Agent Action]`; see `transcripts/lab_transcript_approved.txt` |
| A real pause at the approval gate -- "no" must abort, not silently proceed | `common/approval_gate.py`'s blocking `input()`; the decline path is captured end to end in `transcripts/lab_transcript_declined.txt` |
| Least privilege -- reaches remediation only through `execute_rollback`, only after approval, with `dry_run_rollback` called first | `react_agent.py`'s 5-tool `TOOLS` list + system-prompt rule 1; `tests/test_lab_agent.py::test_dry_run_does_not_mutate_state` checks the dry run can't sneak in a side effect |
| Stretch test: decline and confirm escalation + a postmortem still gets printed | `transcripts/lab_transcript_declined.txt` -- ends in an escalation and a postmortem noting the operator declined |

### Assignment -- "Rubric Hints"

| Criterion | What earns full marks | Where it's met |
|---|---|---|
| Architecture diagram | Clear, correctly labelled, shows approval gates and autonomy levels | `diagrams/architecture.svg` -- labels the blast-radius gate, the Level 2 approval gate, the Level 1 escalation path, and the kill switch |
| Runbook definition | Covers trigger, diagnostics, decision logic, remediation, verification | `runbooks/assignment-notify-svc-oom-crashloop.yaml` -- `triggers`, four diagnostic steps, `on_result`/`blast_radius_checks` for decision logic, `dry_run_then_restart` for remediation, `verify` for verification |
| Agent code -- ReAct loop | Thought text logged before each action; loop terminates correctly | `react_agent.py` (live mode) + `simulated_brain.py` (simulation mode); every captured run in `transcripts/` ends at "Triage complete" or an escalation, never hangs |
| Agent code -- approval gate | Destructive action blocked until approval; escalation path if declined | `restart_service` is gated in both run modes; the decline path is captured in `transcripts/assignment_transcript_declined.txt` |
| Agent code -- blast-radius controls | At least 2 controls implemented and demonstrated | 3 implemented in `common/blast_radius.py`. Rate limiter: `transcripts/assignment_transcript.txt` (blocks the second incident's restart). Kill switch: `transcripts/assignment_transcript_kill_switch.txt`. Error-budget gate: `tests/test_assignment_agent.py::test_check_blast_radius_blocks_on_low_error_budget` |
| Safety discussion | Identifies real failure modes; proposes concrete mitigations; not generic | `WRITEUP.md`, "Assignment: Safety Discussion" |
| Code quality | Readable, commented, handles edge cases (migration pending, budget low) | migration-pending handled in the lab's runbook and exercised in `tests/test_lab_brain.py` (the fixture data never actually hits this branch on its own, so I added a test that fakes it); low budget handled by `ErrorBudgetGate` and covered in `tests/test_blast_radius.py` and `tests/test_assignment_agent.py` |

