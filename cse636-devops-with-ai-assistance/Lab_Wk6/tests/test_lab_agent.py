import json

import lab.react_agent as agent


def setup_function():
    # Each test gets a clean "no rollback executed yet" state.
    agent._ROLLED_BACK.clear()


def test_get_metrics_shows_elevated_error_rate_before_rollback():
    result = json.loads(agent.execute_tool("get_metrics", {"service": "payment-svc"}))
    assert result["error_rate"] == 0.08


def test_get_metrics_recovers_after_rollback():
    agent.execute_tool("execute_rollback", {"service": "payment-svc", "approved_by": "Salman"})
    result = json.loads(agent.execute_tool("get_metrics", {"service": "payment-svc"}))
    assert result["error_rate"] < 0.05


def test_dry_run_does_not_mutate_state():
    agent.execute_tool("dry_run_rollback", {"service": "payment-svc"})
    result = json.loads(agent.execute_tool("get_metrics", {"service": "payment-svc"}))
    assert result["error_rate"] == 0.08, "a dry run must never change what get_metrics reports"


def test_execute_rollback_requires_approved_by_in_result():
    result = agent.execute_tool(
        "execute_rollback", {"service": "payment-svc", "approved_by": "Salman"}
    )
    assert "Salman" in result
    assert "ROLLBACK EXECUTED" in result


def test_unrelated_service_is_unaffected_by_rollback():
    agent.execute_tool("execute_rollback", {"service": "payment-svc", "approved_by": "Salman"})
    result = json.loads(agent.execute_tool("get_metrics", {"service": "cart-svc"}))
    assert result["error_rate"] == 0.003


def test_unknown_tool_reports_itself_as_unknown():
    assert agent.execute_tool("delete_everything", {}) == "Unknown tool: delete_everything"
