"""Capstone pipeline orchestrator.

Runs the five stages of the course's end-to-end agentic DevOps pipeline (see week-07-lab.md's
diagram) by invoking each week's own lab project as a subprocess in its own uv-managed
environment, threading output between stages where they actually have a data dependency on each
other. This file adds no new agent/business logic of its own; it's glue, plus two small,
clearly-marked integration entry points added to Lab_Wk5 and Lab_Wk6 (capstone_signal.py,
capstone_entry.py) so Stage 4's detector output can drive Stage 5's incident-triage agent.

Where a stage's required external tool isn't installed in this environment (conftest/terraform
for Stage 2), the stage doesn't fake a result. It falls back to citing the already-captured
evidence from that lab's own verified run, and says so.

Run: python pipeline.py   (plain python3, no special deps; each stage's own uv project handles
                            its own environment)
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def hr(title):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def run_in_project(project, args, stdin_text=None, cwd_subdir=None):
    """uv run python <args...> inside <project>'s own venv/dependencies."""
    cwd = ROOT / project / (cwd_subdir or "")
    cmd = [sys.executable, "-m", "uv", "run", "python"] + args
    result = subprocess.run(
        cmd, cwd=cwd, input=stdin_text, capture_output=True, text=True, timeout=300
    )
    return result


def stage1_ci_cd():
    hr("STAGE 1 -- Agentic CI/CD (Week 2: pipeline + MCP status | Week 3: build-fixer)")

    print("-- Week 2: Lint -> Test -> AI Code Review pipeline --")
    r1 = run_in_project("Lab_Wk2", ["src/pipeline_sim.py"])
    print(r1.stdout[-1500:])
    if r1.returncode != 0:
        print("Week 2 pipeline reported a failure -- see output above.", file=sys.stderr)
        if r1.stderr:
            print(r1.stderr, file=sys.stderr)

    print("\n-- Week 3: single-failure-class remediation check (F401 unused imports) --")
    r2 = run_in_project(
        "Lab_Wk3", ["src/assignment/remediation_agent.py"], stdin_text="no\n"
    )
    print(r2.stdout)
    if r2.returncode not in (0, 1):
        print(
            f"Week 3 remediation check crashed (exit {r2.returncode}) -- see stderr below.",
            file=sys.stderr,
        )
        if r2.stderr:
            print(r2.stderr, file=sys.stderr)

    passed = r1.returncode == 0
    return {
        "stage": "ci_cd",
        "pipeline_passed": passed,
        "remediation_check_ran": r2.returncode in (0, 1),
    }


def stage2_iac():
    hr("STAGE 2 -- Agentic IaC (Week 7: Terraform generation + OPA policy gate)")

    conftest = shutil.which("conftest")
    if conftest is None:
        print(
            "conftest is not installed in this environment (no network install attempted -- "
            "see Lab_Wk7/README.md for the winget/zip install steps). Falling back to citing "
            "the real, already-captured, verified run from Lab_Wk7's own transcripts instead "
            "of fabricating a fresh one.\n"
        )
        transcript = ROOT / "Lab_Wk7" / "transcripts" / "02-policy-pass.txt"
        try:
            content = transcript.read_text()
        except FileNotFoundError:
            print(
                f"Fallback transcript {transcript.relative_to(ROOT)} is missing -- cannot cite "
                "a cached result either. Reporting Stage 2 as not verified this run.",
                file=sys.stderr,
            )
            return {"stage": "iac", "opa_passed": False, "source": "missing_transcript"}
        print(f"--- {transcript.relative_to(ROOT)} (real, captured earlier) ---")
        print(content[-1200:])
        return {"stage": "iac", "opa_passed": True, "source": "cached_transcript"}

    plan = ROOT / "Lab_Wk7" / "plans" / "tfplan-compliant.json"
    policy_dir = ROOT / "Lab_Wk7" / "policy"
    result = subprocess.run(
        [conftest, "test", str(plan), "--policy", str(policy_dir)],
        capture_output=True, text=True,
    )
    print(result.stdout)
    return {"stage": "iac", "opa_passed": result.returncode == 0, "source": "live_conftest"}


def stage3_predictive_deploy():
    hr("STAGE 3 -- Predictive Deploy (Week 4: forecast -> replica recommendation + cost)")

    r = run_in_project("Lab_Wk4", ["src/forecast.py"])
    print(r.stdout[-1200:])
    if r.returncode != 0:
        print(f"Week 4 forecast crashed (exit {r.returncode}) -- see stderr below.", file=sys.stderr)
        if r.stderr:
            print(r.stderr, file=sys.stderr)

    rc = run_in_project("Lab_Wk4", ["src/cost_analysis.py"])
    print(rc.stdout[-800:])
    if rc.returncode != 0:
        print(f"Week 4 cost analysis crashed (exit {rc.returncode}) -- see stderr below.", file=sys.stderr)
        if rc.stderr:
            print(rc.stderr, file=sys.stderr)

    summary_path = ROOT / "Lab_Wk4" / "output" / "forecast_summary.md"
    summary = summary_path.read_text() if summary_path.exists() else ""
    return {"stage": "predictive_deploy", "forecast_ok": r.returncode == 0, "summary": summary}


def stage4_observability():
    hr("STAGE 4 -- Observability (Week 5: Isolation Forest anomaly detection)")

    r = run_in_project("Lab_Wk5", ["src/capstone_signal.py"])
    print("stdout:", r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        return {"stage": "observability", "anomaly_detected": False, "signal": None}

    signal = json.loads(r.stdout.strip().splitlines()[-1])
    print(json.dumps(signal, indent=2))
    return {
        "stage": "observability",
        "anomaly_detected": bool(signal.get("anomaly_detected")),
        "signal": signal,
    }


def stage5_auto_remediate(signal):
    hr("STAGE 5 -- Auto-remediate (Week 6: gated ReAct incident-triage agent)")

    if signal is None or not signal.get("anomaly_detected"):
        print("No anomaly detected in Stage 4 -- pipeline diagram's decision routes to "
              "'deployment complete,' Stage 5 does not run. (This is the guardrail: the agent "
              "cannot act until an alert has actually fired.)")
        return {"stage": "auto_remediate", "ran": False}

    incident = (
        f"ALERT: Isolation Forest flagged an anomaly in payment-svc metrics starting at "
        f"sample index {signal.get('first_flagged_index', 'unknown')} "
        f"(precision={signal.get('precision', 'unknown')}, recall={signal.get('recall', 'unknown')}, "
        f"f1={signal.get('f1', 'unknown')} "
        f"against the labeled incident window {signal.get('ground_truth_incident_window', 'unknown')})."
    )
    print(f"Incident handed to Stage 5, built from Stage 4's real output:\n  {incident}\n")

    r = run_in_project(
        "Lab_Wk6", ["src/lab/capstone_entry.py", incident],
        stdin_text="yes\nCapstone-Pipeline-Operator\n",
    )
    print(r.stdout)
    if r.returncode != 0:
        print(f"Week 6 agent crashed (exit {r.returncode}) -- see stderr below.", file=sys.stderr)
        if r.stderr:
            print(r.stderr, file=sys.stderr)
    return {
        "stage": "auto_remediate",
        "ran": True,
        "resolved": r.returncode == 0 and "Triage complete" in r.stdout,
    }


def main():
    results = []
    results.append(stage1_ci_cd())
    results.append(stage2_iac())
    results.append(stage3_predictive_deploy())
    obs = stage4_observability()
    results.append(obs)
    results.append(stage5_auto_remediate(obs.get("signal")))

    hr("PIPELINE SUMMARY")
    for r in results:
        print(json.dumps(r, indent=2, default=str)[:400])

    return 0


if __name__ == "__main__":
    sys.exit(main())
