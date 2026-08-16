"""Test-impact analysis: map changed source files to the tests relevant to them, so CI runs
only what a change could plausibly affect instead of the full suite every time.

Convention used: app/<name>.py's relevant test is tests/test_<name>.py (matches this repo's
naming). A change to a shared file (anything not matching app/<name>.py, e.g. conftest.py or
a future shared/ module) is treated conservatively: run the full suite, since we can't prove a
narrower scope is safe.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP_DIR = HERE / "app"
TESTS_DIR = HERE / "tests"


def select_tests_for_changed_files(changed_files):
    """Returns (test_paths, is_full_suite). changed_files are paths relative to HERE,
    e.g. "app/math_ops.py"."""
    selected = set()
    for f in changed_files:
        p = Path(f)
        if p.parent.name == "app" and p.suffix == ".py" and p.stem != "__init__":
            candidate = TESTS_DIR / f"test_{p.stem}.py"
            if candidate.exists():
                selected.add(candidate)
                continue
        # Unrecognized / shared file -- fall back to the full suite.
        return sorted(TESTS_DIR.glob("test_*.py")), True
    return sorted(selected), False


def run_selected(changed_files):
    tests, is_full = select_tests_for_changed_files(changed_files)
    label = "FULL SUITE (conservative fallback)" if is_full else "SELECTED"
    print(f"Changed files: {changed_files}")
    print(f"Test selection: {label} -- {[t.name for t in tests]}")

    all_tests = sorted(TESTS_DIR.glob("test_*.py"))
    print(f"\nBefore (full suite): {len(all_tests)} test files")
    print(f"After (selected):    {len(tests)} test files")

    args = [sys.executable, "-m", "pytest", "-v"] + [str(t) for t in tests]
    result = subprocess.run(args, cwd=HERE, capture_output=True, text=True)
    print(f"\n{result.stdout}")
    return result.returncode


if __name__ == "__main__":
    changed = sys.argv[1:] or ["app/math_ops.py"]
    sys.exit(run_selected(changed))
