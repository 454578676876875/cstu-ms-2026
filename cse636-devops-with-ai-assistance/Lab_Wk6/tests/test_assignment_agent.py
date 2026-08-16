import json

import assignment.react_agent as agent
from common.blast_radius import ErrorBudgetGate, KillSwitch, RemediationRateLimiter


def setup_function():
    agent._VERIFY_PENDING.clear()
    # Fresh guardrail instances per test so tests can't leak state into each other.
    agent.kill_switch = KillSwitch()
    agent.rate_limiter = RemediationRateLimiter(min_interval_seconds=600)
    agent.error_budget_gate = ErrorBudgetGate(min_budget_remaining=0.2)


def test_pod_status_shows_crash_loop_before_restart():
    result = json.loads(agent.execute_tool("get_pod_status", {"service": "notify-svc"}))
    assert result["crash_loop_backoff"] is True


def test_pod_status_clears_for_one_call_after_restart_then_resumes():
    agent.execute_tool("restart_service", {"service": "notify-svc", "approved_by": "Salman"})

    verify = json.loads(agent.execute_tool("get_pod_status", {"service": "notify-svc"}))
    assert verify["crash_loop_backoff"] is False, "the verify step must see a healthy pod"

    recheck = json.loads(agent.execute_tool("get_pod_status", {"service": "notify-svc"}))
    assert recheck["crash_loop_backoff"] is True, "the leak resumes on the next check"


def test_check_blast_radius_allows_by_default():
    allowed, reason = agent.check_blast_radius("notify-svc", error_budget_remaining=0.55)
    assert allowed is True
    assert reason == ""


def test_check_blast_radius_blocks_on_kill_switch(monkeypatch):
    monkeypatch.setenv(KillSwitch.ENV_VAR, "1")
    allowed, reason = agent.check_blast_radius("notify-svc", error_budget_remaining=0.55)
    assert allowed is False
    assert "kill switch" in reason.lower()


def test_check_blast_radius_blocks_on_low_error_budget():
    allowed, reason = agent.check_blast_radius("notify-svc", error_budget_remaining=0.05)
    assert allowed is False
    assert "error-budget" in reason.lower()


def test_check_blast_radius_blocks_second_remediation_within_cooldown():
    agent.execute_tool("restart_service", {"service": "notify-svc", "approved_by": "Salman"})
    allowed, reason = agent.check_blast_radius("notify-svc", error_budget_remaining=0.55)
    assert allowed is False
    assert "rate limiter" in reason.lower()


def test_check_blast_radius_rate_limit_is_per_service():
    agent.execute_tool("restart_service", {"service": "notify-svc", "approved_by": "Salman"})
    allowed, _ = agent.check_blast_radius("other-svc", error_budget_remaining=0.55)
    assert allowed is True


def test_guarded_execute_tool_blocks_dry_run_when_kill_switch_engaged(monkeypatch):
    monkeypatch.setenv(KillSwitch.ENV_VAR, "1")
    result = agent._guarded_execute_tool("dry_run_restart", {"service": "notify-svc"})
    assert "BLOCKED by kill switch" in result
    assert "DRY RUN" not in result
