# react_agent.py
# Week 6 Assignment: self-healing agent for notify-svc's OOM crash loop.
# Author: Salman
#
# Same live/simulated split as lab/react_agent.py -- see that file for why.
#
# One thing I did differently from the lab: check_blast_radius() below gates
# dry_run_restart and restart_service in both modes, at the point where the
# tool actually runs, not just as a rule in the system prompt. My reasoning:
# if the only thing stopping the agent is a sentence in the prompt telling it
# not to, that's not really a guardrail -- the model could just not follow
# it. Checking it in code means it holds no matter what the model decides.

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.approval_gate import request_human_approval  # noqa: E402
from common.blast_radius import ErrorBudgetGate, KillSwitch, RemediationRateLimiter  # noqa: E402
from common.runbook import load_runbook_text  # noqa: E402

RUNBOOK_PATH = (
    Path(__file__).resolve().parents[2] / "runbooks" / "assignment-notify-svc-oom-crashloop.yaml"
)

# These live at module level on purpose -- they need to remember state
# across incidents in the same run, which is how the rate limiter can catch
# a second restart attempt if the crash loop comes back a few minutes later.
kill_switch = KillSwitch()
rate_limiter = RemediationRateLimiter(min_interval_seconds=600)
error_budget_gate = ErrorBudgetGate(min_budget_remaining=0.2)


def check_blast_radius(service: str, error_budget_remaining: float) -> tuple[bool, str]:
    """Everything here has to pass before dry_run_restart or restart_service can run."""
    if kill_switch.is_engaged():
        return False, (
            f"BLOCKED by kill switch ({KillSwitch.ENV_VAR} is set). "
            "All autonomous remediation is disabled."
        )

    if not error_budget_gate.allows(error_budget_remaining):
        return False, (
            f"BLOCKED by error-budget gate: error_budget_remaining="
            f"{error_budget_remaining} is below the {error_budget_gate.min_budget_remaining} "
            "floor. The service can't absorb any more risk right now."
        )

    allowed, remaining_seconds = rate_limiter.check(service)
    if not allowed:
        return False, (
            f"BLOCKED by rate limiter: {service} was already remediated within the last "
            f"{rate_limiter.min_interval_seconds:.0f}s cooldown window "
            f"({remaining_seconds:.0f}s remaining). A crash loop that resumes this fast is a "
            "real bug, not something a second restart will fix."
        )

    return True, ""


# --- Tool definitions (mirror the MCP server in incident_tools_server.py) ---
TOOLS = [
    {
        "name": "get_metrics",
        "description": "Get current error rate, latency, restart count, and error budget for a service",
        "input_schema": {
            "type": "object",
            "properties": {"service": {"type": "string"}},
            "required": ["service"],
        },
    },
    {
        "name": "get_pod_status",
        "description": "Get pod-level health: crash-loop state, restart count, memory usage, last OOM kill",
        "input_schema": {
            "type": "object",
            "properties": {"service": {"type": "string"}},
            "required": ["service"],
        },
    },
    {
        "name": "get_recent_logs",
        "description": "Get recent log lines for a service",
        "input_schema": {
            "type": "object",
            "properties": {"service": {"type": "string"}, "tail": {"type": "integer"}},
            "required": ["service"],
        },
    },
    {
        "name": "get_deployment_history",
        "description": "Get deployment history for a service",
        "input_schema": {
            "type": "object",
            "properties": {"service": {"type": "string"}},
            "required": ["service"],
        },
    },
    {
        "name": "dry_run_restart",
        "description": "Preview a rolling pod restart without executing it. Always run this before restart_service.",
        "input_schema": {
            "type": "object",
            "properties": {"service": {"type": "string"}},
            "required": ["service"],
        },
    },
    {
        "name": "restart_service",
        "description": "Execute a rolling restart of the service's pods. ONLY call this after human approval has been obtained.",
        "input_schema": {
            "type": "object",
            "properties": {"service": {"type": "string"}, "approved_by": {"type": "string"}},
            "required": ["service", "approved_by"],
        },
    },
]

# The leak is only mitigated, not fixed -- a restart clears the crash loop
# just long enough for the very next verify check to see a healthy pod, then
# the leak resumes. _VERIFY_PENDING models that one-call healthy window; it
# is set by restart_service and consumed by the next get_pod_status call.
# This is what lets a second incident minutes later legitimately re-diagnose
# a crash loop and reach the rate limiter, instead of short-circuiting on
# "already fixed."
_VERIFY_PENDING: set[str] = set()


def execute_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "get_metrics":
        s = tool_input["service"]
        if s == "notify-svc":
            return json.dumps(
                {
                    "error_rate": 0.061,
                    "p99_latency_ms": 2100,
                    "error_budget_remaining": 0.55,
                    "restart_count_15m": 4,
                }
            )
        return json.dumps(
            {"error_rate": 0.002, "p99_latency_ms": 90, "error_budget_remaining": 0.9, "restart_count_15m": 0}
        )

    elif tool_name == "get_pod_status":
        s = tool_input["service"]
        if s == "notify-svc" and s in _VERIFY_PENDING:
            _VERIFY_PENDING.discard(s)
            return json.dumps(
                {
                    "crash_loop_backoff": False,
                    "restarts_15m": 4,
                    "memory_usage_pct": 34,
                    "oom_killed_last": False,
                }
            )
        if s == "notify-svc":
            return json.dumps(
                {
                    "crash_loop_backoff": True,
                    "restarts_15m": 4,
                    "memory_usage_pct": 97,
                    "oom_killed_last": True,
                }
            )
        return json.dumps(
            {"crash_loop_backoff": False, "restarts_15m": 0, "memory_usage_pct": 41, "oom_killed_last": False}
        )

    elif tool_name == "get_recent_logs":
        s = tool_input["service"]
        if s == "notify-svc":
            return (
                "ERROR java.lang.OutOfMemoryError: Java heap space\n"
                "WARN  NotificationBatcher queue depth growing: 48000 pending\n"
                "ERROR java.lang.OutOfMemoryError: Java heap space\n"
                "INFO  Container OOMKilled, restarting pod notify-svc-7c9d4-x2p1q\n"
            )
        return "INFO  Batch sent: 214 notifications\nINFO  Healthcheck OK"

    elif tool_name == "get_deployment_history":
        s = tool_input["service"]
        if s == "notify-svc":
            return json.dumps(
                {
                    "current": "v3.7.0",
                    "previous": "v3.6.4",
                    "deployed_at": "6 hours ago",
                    "migration_pending": False,
                }
            )
        return json.dumps({"current": "v1.0.0", "deployed_at": "3 days ago"})

    elif tool_name == "dry_run_restart":
        s = tool_input["service"]
        return (
            f"DRY RUN: Would perform a rolling restart of all {s} pods. "
            "Estimated 3 pods, ~15s per pod, no traffic loss expected (rolling)."
        )

    elif tool_name == "restart_service":
        s = tool_input["service"]
        approver = tool_input.get("approved_by", "unknown")
        rate_limiter.record(s)
        _VERIFY_PENDING.add(s)
        return (
            f"RESTART EXECUTED: rolling restart of {s} pods completed. "
            f"Approved by: {approver}. ETA: 45 seconds."
        )

    return f"Unknown tool: {tool_name}"


SYSTEM_PROMPT_TEMPLATE = """You are an agentic SRE (Site Reliability Engineer) responsible for notify-svc.
Your job is to triage incidents using the available tools and resolve them by following
the structured runbook below, which is your source of truth for diagnosis and decision logic.

<runbook>
{runbook_text}
</runbook>

Follow the runbook's steps in order: check its trigger against the incident, work through
each diagnostic step using the matching tool, and use its on_result branches to decide
whether to proceed toward remediation or escalate.

Safety rules you MUST follow regardless of what the runbook says:
1. Always run dry_run_restart BEFORE restart_service.
2. NEVER call restart_service unless you have stated that you need human approval
   and the field approved_by has been provided to you by the orchestration layer.
3. Note that dry_run_restart and restart_service may be BLOCKED by a blast-radius
   control (kill switch, error-budget gate, or rate limiter) enforced outside your
   control. If a tool result says a call was blocked, do not retry it -- escalate,
   exactly as the runbook's blast_radius_checks step says.
4. Always explain your reasoning before each tool call.
5. If you are not confident (e.g., no matching pattern, crash loop without an OOM
   signature), escalate per the runbook rather than taking action.
6. After resolving an incident (or escalating), summarize what happened in 3-5 bullet
   points suitable for a postmortem draft.
"""


def _guarded_execute_tool(tool_name: str, tool_input: dict) -> str:
    """Wraps execute_tool so blast-radius controls apply in live mode too."""
    if tool_name in ("dry_run_restart", "restart_service"):
        metrics = json.loads(execute_tool("get_metrics", {"service": tool_input["service"]}))
        allowed, reason = check_blast_radius(tool_input["service"], metrics["error_budget_remaining"])
        if not allowed:
            return f"{reason} Escalate to human on-call for manual intervention."
    return execute_tool(tool_name, tool_input)


def run_agent_live(incident: str, service: str) -> None:
    """Live mode: real Claude tool-use loop, same shape as the lab's."""
    import anthropic

    client = anthropic.Anthropic()
    runbook_text = load_runbook_text(RUNBOOK_PATH)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(runbook_text=runbook_text)

    messages = [
        {
            "role": "user",
            "content": (
                f"Incident alert for service '{service}': {incident}\n\n"
                "Please triage this incident and determine the appropriate remediation."
            ),
        }
    ]

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        for block in response.content:
            if hasattr(block, "text"):
                print(f"[Agent Thought] {block.text}")

        if response.stop_reason == "end_turn":
            print("\n[Agent] Triage complete.")
            break

        if response.stop_reason != "tool_use":
            print(f"[Agent] Unexpected stop reason: {response.stop_reason}")
            break

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input

                print(f"\n[Agent Action] Calling tool: {tool_name}({json.dumps(tool_input)})")

                if tool_name == "restart_service":
                    # Check blast radius BEFORE asking a human to approve anything --
                    # otherwise an operator can be asked to approve a restart that's
                    # already guaranteed to be blocked (kill switch / rate limit /
                    # error budget), which just trains them to stop reading prompts.
                    metrics = json.loads(
                        execute_tool("get_metrics", {"service": tool_input["service"]})
                    )
                    allowed, block_reason = check_blast_radius(
                        tool_input["service"], metrics["error_budget_remaining"]
                    )
                    if not allowed:
                        tool_result = f"{block_reason} Escalate to human on-call for manual intervention."
                    else:
                        approved, approver = request_human_approval(
                            f"restart_service on {tool_input.get('service')}"
                        )
                        if not approved:
                            tool_result = (
                                "Restart DECLINED by operator. "
                                "Escalate to human on-call for manual intervention."
                            )
                        else:
                            # request_human_approval() blocks on a real, unbounded
                            # human input() -- guardrail state (kill switch, rate
                            # limiter, error budget) can change while we wait. Don't
                            # trust the pre-approval check; re-verify right before
                            # the destructive call actually fires.
                            recheck_metrics = json.loads(
                                execute_tool("get_metrics", {"service": tool_input["service"]})
                            )
                            still_allowed, recheck_reason = check_blast_radius(
                                tool_input["service"], recheck_metrics["error_budget_remaining"]
                            )
                            if not still_allowed:
                                tool_result = (
                                    f"{recheck_reason} Escalate to human on-call for manual "
                                    "intervention."
                                )
                            else:
                                tool_input["approved_by"] = approver
                                tool_result = execute_tool(tool_name, tool_input)
                else:
                    tool_result = _guarded_execute_tool(tool_name, tool_input)

                print(f"[Tool Result] {tool_result}")

                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": tool_result}
                )

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})


def run_agent_simulated(incident: str, service: str) -> None:
    from assignment.simulated_brain import triage

    triage(incident, service, execute_tool, request_human_approval, check_blast_radius)


def run_agent(incident: str, service: str = "notify-svc") -> None:
    print(f"\n[Agent] Starting triage for incident: {incident}\n")
    print(f"[Agent] Loaded runbook: {RUNBOOK_PATH}\n")

    if os.environ.get("ANTHROPIC_API_KEY"):
        print("[Agent] ANTHROPIC_API_KEY found -- running in live mode.\n")
        run_agent_live(incident, service)
    else:
        print("[Agent] No ANTHROPIC_API_KEY found -- running in simulation mode.\n")
        run_agent_simulated(incident, service)


if __name__ == "__main__":
    first_incident = (
        "ALERT: notify-svc has restarted 4 times in the last 15 minutes and error rate "
        "is at 6.1%, above the 3% threshold. p99 latency is elevated at 2100ms."
    )
    run_agent(first_incident)

    print(f"\n{'#' * 60}")
    print("# A second alert fires ~3 minutes later: the crash loop has resumed.")
    print(f"{'#' * 60}")

    second_incident = (
        "ALERT: notify-svc has restarted 4 times in the last 15 minutes and error rate "
        "is at 6.1%, above the 3% threshold. p99 latency is elevated at 2100ms. "
        "(Recurrence of the incident triaged moments ago.)"
    )
    run_agent(second_incident)
