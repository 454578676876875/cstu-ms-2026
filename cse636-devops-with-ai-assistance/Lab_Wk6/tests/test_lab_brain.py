"""Exercises simulated_brain.triage()'s decision branches directly.

react_agent.execute_tool() always returns migration_pending=False (it's a
static fixture), so that branch of the runbook never actually runs in the
captured transcripts. These tests fake out execute_tool to prove the brain
still does the right thing when a deploy IS a migration risk, instead of
leaving that branch as dead code nobody ever checked.
"""

import json

from lab.simulated_brain import triage


def _make_fake_execute_tool(migration_pending: bool):
    calls = {"get_metrics": 0}

    def fake_execute_tool(tool_name: str, tool_input: dict) -> str:
        if tool_name == "get_metrics":
            calls["get_metrics"] += 1
            # first call (trigger check) is elevated; second call (post-rollback
            # verify) has recovered, same as react_agent.execute_tool's real behavior
            if calls["get_metrics"] == 1:
                return json.dumps(
                    {"error_rate": 0.08, "p99_latency_ms": 450, "error_budget_remaining": 0.42}
                )
            return json.dumps(
                {"error_rate": 0.006, "p99_latency_ms": 135, "error_budget_remaining": 0.42}
            )
        if tool_name == "get_recent_logs":
            return "ERROR NullPointerException in PaymentProcessor.process() line 142\n"
        if tool_name == "get_deployment_history":
            return json.dumps(
                {
                    "current": "v1.4.2",
                    "previous": "v1.4.1",
                    "deployed_at": "8 minutes ago",
                    "migration_pending": migration_pending,
                }
            )
        if tool_name == "dry_run_rollback":
            return "DRY RUN: Would revert payment-svc v1.4.2 -> v1.4.1. Safe to proceed."
        if tool_name == "execute_rollback":
            return f"ROLLBACK EXECUTED: payment-svc reverted to v1.4.1. Approved by {tool_input.get('approved_by')}."
        raise AssertionError(f"unexpected tool call in this test: {tool_name}")

    return fake_execute_tool


def test_migration_pending_escalates_without_touching_the_approval_gate(capsys):
    approval_calls = []

    def fake_approval(action: str):
        approval_calls.append(action)
        return True, "should-not-be-called"

    triage(
        "incident",
        _make_fake_execute_tool(migration_pending=True),
        fake_approval,
    )

    assert approval_calls == [], (
        "a pending migration must escalate before ever requesting approval, "
        "let alone calling dry_run_rollback or execute_rollback"
    )
    out = capsys.readouterr().out
    assert "migration" in out.lower()
    assert "Escalating to on-call-primary" in out


def test_no_migration_pending_proceeds_to_approval_gate(capsys):
    approval_calls = []

    def fake_approval(action: str):
        approval_calls.append(action)
        return True, "Salman"

    triage(
        "incident",
        _make_fake_execute_tool(migration_pending=False),
        fake_approval,
    )

    assert len(approval_calls) == 1
    assert "execute_rollback" in approval_calls[0]
    out = capsys.readouterr().out
    assert "Triage complete" in out
