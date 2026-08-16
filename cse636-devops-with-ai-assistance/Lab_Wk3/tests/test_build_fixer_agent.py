import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "lab"))

import build_fixer_agent as bfa

BUGGY_SOURCE = (
    "def add(a, b):\n"
    "    # Bug: subtraction instead of addition\n"
    "    return a - b\n"
    "\n"
    "\n"
    "def multiply(a, b):\n"
    "    return a * b\n"
)

BUILD_LOG = (
    "tests/test_calculator.py::test_add FAILED\n"
    "    assert add(2, 3) == 5\n"
    "E   assert -1 == 5\n"
)


def test_simulated_fix_identifies_root_cause():
    fix = bfa.simulated_fix(BUILD_LOG, BUGGY_SOURCE)
    assert "a - b" in fix["root_cause"] or "subtraction" in fix["root_cause"]
    assert "return a + b" in fix["fixed_file_content"]
    assert "return a - b" not in fix["fixed_file_content"]


def test_simulated_fix_only_changes_the_buggy_line():
    fix = bfa.simulated_fix(BUILD_LOG, BUGGY_SOURCE)
    assert "def multiply(a, b):\n    return a * b" in fix["fixed_file_content"]


def test_simulated_fix_falls_back_when_unrecognized():
    fix = bfa.simulated_fix("some other failure", BUGGY_SOURCE)
    assert fix["fixed_file_content"] == BUGGY_SOURCE
    assert "escalate" in fix["fix_description"].lower()


def test_propose_fix_dispatches_to_simulated_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    fix = bfa.propose_fix(BUILD_LOG, BUGGY_SOURCE)
    assert "return a + b" in fix["fixed_file_content"]
