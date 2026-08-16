# Week 3 Lab and Assignment: Build-Fixer Agent with a Human Approval Gate

Covers the Week 3 lab (a build-fixer agent that detects a failing test, proposes a fix, and
stops at a human approval gate) and the assignment (test-impact analysis + single-failure-class
remediation), both described in `week-03-lab.md`.

Built on the lab document's own no-GitHub path: its "Running on Jenkins" J5 walkthrough runs
the agent, prints the proposed fix, and pauses at a blocking gate with no PR opened. This
project does the same thing locally, no Jenkins/GitHub Actions needed. The "apply" step writes
the fix to the local file (standing in for opening a PR), and only after a blocking approval.

## How to run

Managed with [`uv`](https://docs.astral.sh/uv/).

```bash
cd cse636-devops-with-ai-assistance/Lab_Wk3

# 1. Lab: build-fixer agent (approve when prompted; calculator.py is already fixed in this
#    submission from the captured run, so revert the "return a + b" line to the buggy version
#    first if you want to see it propose the fix again)
uv run python src/lab/build_fixer_agent.py

# 2. Assignment: test-impact analysis (select only the tests relevant to a changed file)
cd src/assignment && uv run python select_tests.py app/math_ops.py && cd ../..

# 3. Assignment: single-failure-class remediation (finds + proposes fixing an unused import)
uv run python src/assignment/remediation_agent.py

# 4. Run the test suite
uv run pytest -v
```

## Project structure

```
src/
  common/
    approval_gate.py         shared blocking input() approval gate (same pattern as Lab_Wk6)
  lab/
    calculator.py             the lab's buggy-then-fixed calculator (add() bug, per spec)
    tests/test_calculator.py
    build_fixer_agent.py      dual-mode (live/simulated) build-fixer: runs tests, proposes a
                              fix, blocks on approval, applies + re-verifies
  assignment/
    app/
      math_ops.py, string_ops.py, inventory_ops.py   3 small modules (inventory_ops.py had a
                              deliberate unused import, since fixed, see WRITEUP.md)
    tests/                    one test file per module
    select_tests.py            test-impact analysis: changed file -> relevant test file(s),
                              conservative full-suite fallback for anything outside app/
    remediation_agent.py       detects + gated-fixes one failure class: F401 unused imports

docs/
  guardrails.md                approval gate + blast-radius documentation the assignment rubric
                              asks for

transcripts/
  lab_declined.txt / lab_approved.txt                          real captured runs, both outcomes
  select_tests_demo.txt                                         real before/after test-count run
  assignment_remediation_declined.txt / _approved.txt           real captured runs, both outcomes

tests/
  test_build_fixer_agent.py    simulated_fix() root-cause/fix logic against synthetic input
  test_select_tests.py         selection mapping + fallback logic
  test_remediation_agent.py    F401 regex parsing, line-removal logic, real flake8 integration

WRITEUP.md               lab deliverable + assignment reflection
```

## Design decisions

Why does the file end up permanently fixed by the approved-run transcript? `lab_declined.txt`
was captured first (confirmed via `diff` that the file was untouched afterward), then
`lab_approved.txt` was captured against the same still-buggy file. So both transcripts are
back-to-back runs, not one edited after the fact. The final committed `calculator.py` and
`app/inventory_ops.py` reflect the last thing that happened to them (the approved fix), same as
a repo's actual history would.

Why does `simulated_fix()` pattern-match instead of trying to "understand" the bug? No
`ANTHROPIC_API_KEY` is set, so instead of faking general reasoning, `simulated_fix()` recognizes
this one specific known bug (matching on the actual failing assertion text) and falls back
honestly ("could not determine root cause... escalate to a human") for anything else. That's
documented as the main limitation in `WRITEUP.md`'s "one thing to change" section.

Why does `remediation_agent.py` only handle F401? The assignment asks for one well-defined
failure class, not a general fixer. Constraining `find_unused_imports()` to
`flake8 --select=F401` means the agent structurally can't "fix" anything it wasn't built to
recognize. That's a blast-radius limit, not just a design choice (see `docs/guardrails.md`).
