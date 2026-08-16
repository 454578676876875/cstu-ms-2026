# Guardrails: Approval Gates and Blast-Radius Limits

## Approval gate (both lab and assignment)

`src/common/approval_gate.py`'s `request_human_approval()` is a blocking `input()` call, not a
timeout-based auto-approve, not a "confirm" flag that defaults to yes. Every agent in this
project (`build_fixer_agent.py`, `remediation_agent.py`) calls it before the one line that
writes to a source file, and both the approved and declined paths are exercised for real in
`transcripts/` (not hand-written):

- `transcripts/lab_declined.txt`: agent proposes the fix, human says no, `calculator.py` is
  confirmed byte-for-byte unchanged (checked with `diff` at capture time).
- `transcripts/lab_approved.txt`: agent proposes the same fix, human approves, the file gets
  written, and the agent re-runs the test suite itself to confirm the fix worked instead of
  just assuming it did.
- `transcripts/assignment_remediation_declined.txt` / `_approved.txt`: same two-path proof for
  the assignment's remediation agent.

What makes this a gate and not theater: if you deleted every call site of
`request_human_approval()`, the agents would still propose fixes identically. The gate is a
separate step wrapping the one destructive action (`Path.write_text`), not baked into the
fix-generation logic. Removing the human changes nothing about what the agent can compute, only
whether anything gets written to disk.

## Blast-radius limits

1. **Single-file scope.** Both agents' fix schema has no field for touching more than one file.
   `build_fixer_agent.py`'s system prompt states this outright ("Change exactly one file...
   never the test file"), and `remediation_agent.py` structurally can't touch anything but the
   one file `flake8` flagged, since `propose_fix()` takes a single `path` argument.
2. **Single failure class per remediation agent.** `remediation_agent.py` only recognizes F401
   (unused import). `find_unused_imports()` calls flake8 with `--select=F401`, so a different
   violation class (a real bug, say, or a security issue) is invisible to this agent and can't
   trigger a fix it wasn't built to reason about.
3. No merge/deploy capability at all. Neither agent has a tool for pushing to a remote, opening
   a PR against a shared branch, or triggering a deploy. The "apply" step is a local file write
   plus a local test re-run, the same no-GitHub scope as the lab document's own J5 dry-run
   walkthrough. There's no code path from either agent to a shared/production system.
4. Self-verification before declaring success. Neither agent's final "PASS" is just its own
   claim; both re-run the actual test/lint tool after applying a fix and report that tool's
   exit code, not their own judgment. `build_fixer_agent.py` distinguishes "fix applied" from
   "fix confirmed" as two separate log lines.

## What isn't covered here

These agents don't rate-limit repeated invocations (Lab_Wk6's `RemediationRateLimiter` pattern)
or check an error budget before proposing a fix. Both would be reasonable additions for a
same-failure-flapping scenario, but that's out of scope here since Week 3's task is a one-shot
build fix, not a recurring incident-response loop (that's Week 6's territory, already built in
this repo's `Lab_Wk6`).
