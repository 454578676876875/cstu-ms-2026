# react_agent.py
# Week 6 Lab: ReAct agent that triages a payment-svc incident using the
# runbook, with a human-approval gate before the destructive action.
# Author: Salman
#
# I don't have an ANTHROPIC_API_KEY set up on this machine, and the lab doc
# says that's fine ("an API key, or the provided simulation mode"), so I
# built two run modes:
#   - run_agent_live(): the real Claude tool-use loop from Step 3, used if
#     you do have a key set.
#   - run_agent_simulated(): a small scripted "brain" (simulated_brain.py)
#     that walks the same runbook and prints the same
#     Thought -> Action -> Observation shape a live run would.
#
# Both modes call the same execute_tool() and the same real approval_gate,
# so the actual safety behavior (dry-run first, no execute without an
# approver, etc.) doesn't depend on which one is reasoning.

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.approval_gate import request_human_approval  # noqa: E402
from common.runbook import load_runbook_text  # noqa: E402

RUNBOOK_PATH = (
    Path(__file__).resolve().parents[2] / "runbooks" / "lab-payment-svc-high-error-rate.yaml"
)

# --- Tool definitions (mirror the MCP server in incident_tools_server.py) ---
TOOLS = [
    {
        "name": "get_metrics",
        "description": "Get current error rate and latency for a service",
        "input_schema": {
            "type": "object",
            "properties": {"service": {"type": "string", "description": "Service name"}},
            "required": ["service"],
        },
    },
    {
        "name": "get_recent_logs",
        "description": "Get recent error log lines for a service (last N lines)",
        "input_schema": {
            "type": "object",
            "properties": {"service": {"type": "string"}, "tail": {"type": "integer"}},
            "required": ["service"],
        },
    },
    {
        "name": "get_deployment_history",
        "description": "Get recent deployment history for a service",
        "input_schema": {
            "type": "object",
            "properties": {"service": {"type": "string"}},
            "required": ["service"],
        },
    },
    {
        "name": "dry_run_rollback",
        "description": "Preview a rollback without executing it. Always run this before execute_rollback.",
        "input_schema": {
            "type": "object",
            "properties": {"service": {"type": "string"}},
            "required": ["service"],
        },
    },
    {
        "name": "execute_rollback",
        "description": "Execute a rollback. ONLY call this after human approval has been obtained.",
        "input_schema": {
            "type": "object",
            "properties": {"service": {"type": "string"}, "approved_by": {"type": "string"}},
            "required": ["service", "approved_by"],
        },
    },
]

# The lab's starter code always returns the same elevated error_rate for
# payment-svc, even after a rollback -- so the runbook's own verify step
# could never actually pass. I added this set so get_metrics reflects a
# rollback that already happened.
_ROLLED_BACK: set[str] = set()


# --- Simulated tool execution (in a real system, these call the MCP server) ---
def execute_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "get_metrics":
        s = tool_input["service"]
        if s == "payment-svc" and s not in _ROLLED_BACK:
            return json.dumps(
                {"error_rate": 0.08, "p99_latency_ms": 450, "error_budget_remaining": 0.42}
            )
        if s == "payment-svc":
            return json.dumps(
                {"error_rate": 0.006, "p99_latency_ms": 135, "error_budget_remaining": 0.42}
            )
        return json.dumps(
            {"error_rate": 0.003, "p99_latency_ms": 120, "error_budget_remaining": 0.85}
        )

    elif tool_name == "get_recent_logs":
        s = tool_input["service"]
        if s == "payment-svc":
            return (
                "ERROR NullPointerException in PaymentProcessor.process() line 142\n"
                "ERROR NullPointerException in PaymentProcessor.process() line 142\n"
                "WARN  Cart total $12,450.00 exceeded expected range\n"
            )
        return "INFO  Request processed in 115ms\nINFO  Healthcheck OK"

    elif tool_name == "get_deployment_history":
        s = tool_input["service"]
        if s == "payment-svc":
            return json.dumps(
                {
                    "current": "v1.4.2",
                    "previous": "v1.4.1",
                    "deployed_at": "8 minutes ago",
                    "migration_pending": False,
                }
            )
        return json.dumps({"current": "v2.1.0", "deployed_at": "2 hours ago"})

    elif tool_name == "dry_run_rollback":
        s = tool_input["service"]
        return f"DRY RUN: Would revert {s} v1.4.2 -> v1.4.1. No migration pending. Safe to proceed."

    elif tool_name == "execute_rollback":
        s = tool_input["service"]
        approver = tool_input.get("approved_by", "unknown")
        _ROLLED_BACK.add(s)
        return f"ROLLBACK EXECUTED: {s} reverted to v1.4.1. Approved by {approver}. ETA 45s."

    return f"Unknown tool: {tool_name}"


SYSTEM_PROMPT_TEMPLATE = """You are an agentic SRE (Site Reliability Engineer).
Your job is to triage incidents using the available tools and resolve them by following
the structured runbook below, which is your source of truth for diagnosis and decision logic.

<runbook>
{runbook_text}
</runbook>

Follow the runbook's steps in order: check its trigger against the incident, work through
each diagnostic step using the matching tool, and use its on_result branches to decide
whether to proceed toward remediation or escalate. If the incident doesn't match any
branch in the runbook, escalate per the runbook's `escalation` block.

Safety rules you MUST follow regardless of what the runbook says:
1. Always run dry_run_rollback BEFORE execute_rollback.
2. NEVER call execute_rollback unless you have stated that you need human approval
   and the field approved_by has been provided to you by the orchestration layer.
3. Always explain your reasoning before each tool call.
4. If you are not confident (e.g., no matching pattern, migration pending), escalate
   per the runbook rather than taking action.
5. After resolving an incident (or escalating), summarize what happened in 3-5 bullet points
   suitable for a postmortem draft.
"""


def run_agent_live(incident: str) -> None:
    """Live mode: real Claude tool-use loop, as in week-06-lab.md Step 3."""
    import anthropic

    client = anthropic.Anthropic()
    runbook_text = load_runbook_text(RUNBOOK_PATH)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(runbook_text=runbook_text)

    messages = [
        {
            "role": "user",
            "content": f"Incident alert: {incident}\n\nPlease triage this incident and determine the appropriate remediation.",
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

                if tool_name == "execute_rollback":
                    approved, approver = request_human_approval(
                        f"execute_rollback on {tool_input.get('service')}"
                    )
                    if not approved:
                        tool_result = (
                            "Rollback DECLINED by operator. "
                            "Escalate to human on-call for manual intervention."
                        )
                    else:
                        tool_input["approved_by"] = approver
                        tool_result = execute_tool(tool_name, tool_input)
                else:
                    tool_result = execute_tool(tool_name, tool_input)

                print(f"[Tool Result] {tool_result}")

                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": tool_result}
                )

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})


def run_agent_simulated(incident: str) -> None:
    """Simulation mode: scripted brain, same runbook, same approval gate."""
    from lab.simulated_brain import triage

    triage(incident, execute_tool, request_human_approval)


def run_agent(incident: str) -> None:
    print(f"\n[Agent] Starting triage for incident: {incident}\n")
    print(f"[Agent] Loaded runbook: {RUNBOOK_PATH}\n")

    if os.environ.get("ANTHROPIC_API_KEY"):
        print("[Agent] ANTHROPIC_API_KEY found -- running in live mode.\n")
        run_agent_live(incident)
    else:
        print("[Agent] No ANTHROPIC_API_KEY found -- running in simulation mode.\n")
        run_agent_simulated(incident)


if __name__ == "__main__":
    incident_description = (
        "ALERT: payment-svc error rate has been above 5% for the past 4 minutes. "
        "This started approximately 8 minutes after a deployment. "
        "Cart-svc latency is also slightly elevated. "
        "Please investigate and remediate."
    )
    run_agent(incident_description)
