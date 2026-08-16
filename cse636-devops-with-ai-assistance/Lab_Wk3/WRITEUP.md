# Week 3 Lab Deliverable

## Screenshot/log evidence

No GitHub Actions/Jenkins involved (local, no-GitHub path, same as the lab document's own J5
"Running on Jenkins" dry-run walkthrough). Evidence is the captured terminal output:

- Test failure: `transcripts/lab_declined.txt` (top), `assert -1 == 5`, `1 failed, 1 passed`.
- Agent's proposed fix: same file, "Proposed diff" section.
- Approval gate pause: `[APPROVAL GATE] apply this fix to calculator.py`, both outcomes
  (`transcripts/lab_declined.txt`, `transcripts/lab_approved.txt`).

## Root cause and fix description: was it accurate?

```
root_cause:      "add(a, b) returns a - b instead of a + b -- test_add expects
                   add(2, 3) == 5 but the current implementation returns -1."
fix_description: "Change the return statement in add() from `a - b` to `a + b`."
```

Yes, and it's verifiable, not just asserted, since the fix was re-tested by the agent itself
(`transcripts/lab_approved.txt`'s "Re-running tests to confirm the fix" section shows
`2 passed`). This ran in simulated-brain mode (no `ANTHROPIC_API_KEY` set), and
`simulated_fix()` is a pattern match against the specific known bug, not a general bug-fixer.
See "one thing to change" below for what that costs.

## One thing I'd change about the agent's prompt or the guardrail setup

The guardrail held up fine (blocking approval gate, single-file scope, self-verification via
re-test), and I wouldn't loosen or tighten it for this lab's scope. What I'd change is the
prompt. The weak part is `simulated_fix()`'s string-matching approach to "understanding" the
bug: it only recognizes this exact bug (`assert add(2, 3) == 5` plus the literal comment text),
so it's a stand-in for reasoning, not reasoning itself. In live mode (with a real
`ANTHROPIC_API_KEY`), `SYSTEM_PROMPT` would need one more constraint I didn't add: an
instruction to include, in `fix_description`, why the fix is minimal and doesn't touch anything
else. Right now the schema captures what changed but not why the reviewer should trust that
nothing else needed to change, and that's the information a human approver at the gate actually
needs to make a fast yes/no call instead of re-deriving it from the diff themselves.

---

## Assignment: Test-Impact Analysis + Single-Failure-Class Remediation

### Test selection evidence

`transcripts/select_tests_demo.txt`: changing `app/math_ops.py` selects only
`test_math_ops.py` (2 tests) instead of the full 3-file, 7-test suite. That's an actual
before/after count (`tests/test_select_tests.py` covers the selection logic itself, including
the conservative "unrecognized file -> run everything" fallback).

### Remediation accuracy

`remediation_agent.py` targets exactly one failure class (F401, unused import) and only that
class, confirmed via `tests/test_remediation_agent.py`'s regex-parsing and file-editing tests,
plus the end-to-end runs in `transcripts/assignment_remediation_declined.txt` and
`_approved.txt`, which found and fixed the actual (not synthetic) `import os` left in
`app/inventory_ops.py`. `flake8 --select=F401` re-run after the fix confirms the violation is
gone, so the agent isn't just claiming success.

### Guardrails

See `docs/guardrails.md`: approval gate that actually blocks (both outcomes captured for real),
single-file / single-failure-class blast radius, no merge/deploy capability, self-verification
via the actual linter/test tool rather than the agent's own say-so.

### Reflection: how the agent failed or surprised me

Building `select_tests.py`'s fallback rule surfaced a trade-off I hadn't fully thought through
going in: the naming-convention mapping (`app/foo.py` -> `tests/test_foo.py`) is too optimistic
for anything beyond this toy app. A change to `app/math_ops.py` that altered a function
`string_ops.py` imports from it (cross-module coupling) would still only select
`test_math_ops.py` and silently skip `test_string_ops.py`. The fallback only catches changes to
files outside `app/` entirely (like `conftest.py`), not cross-module blast radius within
`app/`. A correct version would need import-graph analysis, not filename matching. I left the
simpler version in because doing it properly would've meant admitting the current
implementation's limit instead of quietly working around it with a fake "it handles everything"
claim, which is exactly the kind of thing this course keeps warning agents (and the humans
deploying them) not to do.
