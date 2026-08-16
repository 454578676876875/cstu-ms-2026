"""Auto-remediation for one well-defined failure class: an unused import (flake8 code F401).
Detects it, proposes the minimal fix (delete that one line), and stops at the same blocking
approval gate the lab's build_fixer_agent.py uses. Never applies a fix unattended.
"""
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.approval_gate import request_human_approval

HERE = Path(__file__).resolve().parent
APP_DIR = HERE / "app"

F401_PATTERN = re.compile(r"^(?P<path>.+):(?P<line>\d+):\d+: F401 '(?P<module>.+)' imported but unused$")


def find_unused_imports():
    result = subprocess.run(
        [sys.executable, "-m", "flake8", "--select=F401", str(APP_DIR)],
        capture_output=True,
        text=True,
    )
    findings = []
    for line in result.stdout.splitlines():
        m = F401_PATTERN.match(line)
        if m:
            findings.append((Path(m.group("path")), int(m.group("line")), m.group("module")))
    return findings


def propose_fix(path, line_no):
    lines = path.read_text().splitlines(keepends=True)
    removed = lines[line_no - 1]
    fixed_lines = lines[: line_no - 1] + lines[line_no:]
    return removed, "".join(fixed_lines)


def run():
    findings = find_unused_imports()
    if not findings:
        print("No unused imports found (F401). Nothing to remediate.")
        return 0

    exit_code = 0
    for path, line_no, module in findings:
        print(f"\n=== F401: '{module}' imported but unused in {path.name}:{line_no} ===")
        removed_line, fixed_content = propose_fix(path, line_no)
        print(f"Proposed removal: {removed_line.rstrip()}")

        approved, approver = request_human_approval(
            f"remove the unused import '{module}' from {path.name}:{line_no}"
        )
        if not approved:
            print("=== DECLINED -- escalating to human, no changes made ===")
            exit_code = 1
            continue

        path.write_text(fixed_content)
        print(f"=== APPROVED by {approver} -- import removed ===")

        recheck = subprocess.run(
            [sys.executable, "-m", "flake8", "--select=F401", str(path)],
            capture_output=True,
            text=True,
        )
        if recheck.stdout.strip():
            print(f"=== Fix did NOT clear F401 -- escalate: {recheck.stdout}")
            exit_code = 1
        else:
            print("=== Confirmed: F401 cleared for this file ===")

    return exit_code


if __name__ == "__main__":
    sys.exit(run())
