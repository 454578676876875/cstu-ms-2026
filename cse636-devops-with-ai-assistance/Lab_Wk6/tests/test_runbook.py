from pathlib import Path

from common.runbook import load_runbook_dict, load_runbook_text

REPO_ROOT = Path(__file__).resolve().parents[1]
LAB_RUNBOOK = REPO_ROOT / "runbooks" / "lab-payment-svc-high-error-rate.yaml"
ASSIGNMENT_RUNBOOK = REPO_ROOT / "runbooks" / "assignment-notify-svc-oom-crashloop.yaml"


def test_load_runbook_text_returns_full_yaml():
    text = load_runbook_text(LAB_RUNBOOK)
    assert "payment-svc: high error rate" in text
    assert "execute_rollback" in text


def test_load_runbook_dict_parses_trigger_and_steps():
    runbook = load_runbook_dict(LAB_RUNBOOK)
    assert runbook["triggers"][0]["service"] == "payment-svc"
    assert runbook["triggers"][0]["threshold"] == 0.05
    step_ids = [step["id"] for step in runbook["steps"]]
    assert step_ids == [
        "check_metrics",
        "check_logs",
        "check_recent_deploy",
        "dry_run_then_rollback",
        "verify",
    ]
    assert runbook["escalation"]["page"] == "on-call-primary"


def test_assignment_runbook_covers_required_sections():
    runbook = load_runbook_dict(ASSIGNMENT_RUNBOOK)
    assert runbook["triggers"][0]["service"] == "notify-svc"
    step_ids = [step["id"] for step in runbook["steps"]]
    assert "blast_radius_checks" in step_ids
    assert "verify" in step_ids
    assert runbook["steps"][-1]["on_result"]["still_crash_looping"]["escalate"] is True
