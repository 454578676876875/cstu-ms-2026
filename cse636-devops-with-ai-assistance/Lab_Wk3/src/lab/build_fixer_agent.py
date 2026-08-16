"""Build-fixer agent, lab version.

Reads a failing build log, identifies the root cause and a minimal fix, and stops at a blocking
human approval gate before touching the source file. Mirrors the lab's own no-GitHub path (the
"Running on Jenkins" J5 walkthrough: agent prints root cause + fix, pipeline pauses at `input`,
no PR opened). Here the "apply" step is writing the fixed file locally (standing in for opening
a PR) instead of calling the GitHub API, since this is a local simulation with no GitHub push
involved. Same guarantee either way: nothing gets written without a human saying yes.

Dual-mode like Lab_Wk6's agents: a live structured-output Claude call if ANTHROPIC_API_KEY is
set, otherwise a simulated fix derived from the build log and source file.
"""
import difflib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.approval_gate import request_human_approval

HERE = Path(__file__).resolve().parent
SOURCE_PATH = HERE / "calculator.py"
TEST_CMD = [sys.executable, "-m", "pytest", "tests/", "--tb=short"]

FIX_SCHEMA = {
    "type": "object",
    "properties": {
        "root_cause": {"type": "string"},
        "fix_description": {"type": "string"},
        "fixed_file_content": {"type": "string"},
    },
    "required": ["root_cause", "fix_description", "fixed_file_content"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are a build-fixer agent. Your only job is to identify
the root cause of a failing Python test and propose the minimal fix to the
source file. Change exactly one file: the source file under test, never the
test file. fixed_file_content must be the complete corrected file. Do not add
tests or make stylistic changes unrelated to the bug."""


def run_tests():
    result = subprocess.run(TEST_CMD, cwd=HERE, capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def simulated_fix(build_log, source_code):
    """Derived from the actual build log/source, not canned. Same principle as Lab_Wk6's
    simulated_brain.py: a scripted stand-in for the LLM call that reasons over real input."""
    if "test_add" in build_log and "assert add(2, 3) == 5" in build_log:
        fixed = source_code.replace(
            "    # Bug: subtraction instead of addition\n    return a - b",
            "    return a + b",
        )
        return {
            "root_cause": (
                "add(a, b) returns a - b instead of a + b -- test_add expects add(2, 3) == 5 "
                "but the current implementation returns -1."
            ),
            "fix_description": "Change the return statement in add() from `a - b` to `a + b`.",
            "fixed_file_content": fixed,
        }
    return {
        "root_cause": "Could not determine root cause from the build log with the simulated brain.",
        "fix_description": "No fix proposed -- escalate to a human.",
        "fixed_file_content": source_code,
    }


def live_fix(build_log, source_code):
    import anthropic
    import os

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": FIX_SCHEMA}},
        messages=[{
            "role": "user",
            "content": (
                f"Build log:\n```\n{build_log}\n```\n\n"
                f"Source file (calculator.py):\n```python\n{source_code}\n```"
            ),
        }],
    )
    return json.loads(next(b.text for b in response.content if b.type == "text"))


def propose_fix(build_log, source_code):
    import os

    if os.environ.get("ANTHROPIC_API_KEY"):
        return live_fix(build_log, source_code)
    return simulated_fix(build_log, source_code)


def run():
    print("=== Build-fixer agent: running tests ===")
    rc, build_log = run_tests()
    print(build_log)

    if rc == 0:
        print("Tests already pass -- nothing to fix.")
        return 0

    print("\n=== Build-fixer agent: proposing a fix ===")
    source_code = SOURCE_PATH.read_text()
    fix = propose_fix(build_log, source_code)

    print(f"Root cause:       {fix['root_cause']}")
    print(f"Fix description:  {fix['fix_description']}")

    diff = "\n".join(
        difflib.unified_diff(
            source_code.splitlines(),
            fix["fixed_file_content"].splitlines(),
            fromfile="calculator.py (before)",
            tofile="calculator.py (proposed)",
            lineterm="",
        )
    )
    print(f"\nProposed diff:\n{diff}")

    if fix["fixed_file_content"] == source_code:
        print(
            "\n=== No-op fix (fixed_file_content is identical to the original) -- "
            "nothing to apply, escalating to a human ==="
        )
        return 1

    approved, approver = request_human_approval(
        f"apply this fix to {SOURCE_PATH.name} (see diff above)"
    )
    if not approved:
        print("\n=== DECLINED -- escalating to human, no changes made ===")
        return 1

    SOURCE_PATH.write_text(fix["fixed_file_content"])
    print(f"\n=== APPROVED by {approver} -- fix applied ===")

    print("\n=== Re-running tests to confirm the fix ===")
    rc2, retest_log = run_tests()
    print(retest_log)
    if rc2 == 0:
        print("=== Fix confirmed: tests pass ===")
        return 0
    print("=== Fix did NOT resolve the failure -- escalate to a human ===")
    return 1


if __name__ == "__main__":
    sys.exit(run())
