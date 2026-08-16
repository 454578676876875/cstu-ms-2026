"""Runs the Week 2 Jenkinsfile's stage order (Checkout is a no-op here -- the sample app
already lives in src/sample_app/) locally: Lint -> Test -> AI Code Review.

Stands in for the real Jenkins pipeline (no Docker/Jenkins on this machine -- see README.md).
Each stage's real stdout is captured, same shape as archiveArtifacts/console output would be.
"""
import subprocess
import sys
from pathlib import Path

import ai_review

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "src" / "sample_app"
REPORT_PATH = ROOT / "output" / "ai_review_report.txt"


def run_stage(name, fn):
    print(f"\n=== stage: {name} ===")
    return fn()


def stage_lint():
    result = subprocess.run(
        [sys.executable, "-m", "flake8", ".", "--max-line-length=120"],
        cwd=APP_DIR,
        capture_output=True,
        text=True,
    )
    print(result.stdout or "(no lint findings)")
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    # Mirrors the Jenkinsfile's `flake8 ... || true` -- lint findings don't fail the build.
    return {"exit_code": result.returncode, "output": result.stdout}


def stage_test():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v"],
        cwd=APP_DIR,
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
    return {"exit_code": result.returncode, "output": result.stdout}


def stage_ai_review():
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report = ai_review.run(str(APP_DIR), str(REPORT_PATH))
    print(f"Report written to {REPORT_PATH}")
    return {"exit_code": 0, "output": report}


def main():
    results = {}
    results["lint"] = run_stage("Lint", stage_lint)
    results["test"] = run_stage("Test", stage_test)
    if results["test"]["exit_code"] != 0:
        print("\nTest stage failed -- pipeline would still run AI Review per the Jenkinsfile's "
              "stage ordering (no `when` guard on AI Code Review), but flagging here.")
    results["ai_review"] = run_stage("AI Code Review", stage_ai_review)

    print("\n=== pipeline summary ===")
    for stage, r in results.items():
        status = "PASS" if r["exit_code"] == 0 else "FAIL"
        print(f"{stage}: {status}")

    return 0 if results["test"]["exit_code"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
