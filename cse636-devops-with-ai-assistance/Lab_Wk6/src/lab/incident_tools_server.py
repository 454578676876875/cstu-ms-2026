# incident_tools_server.py
# Week 6 Lab: MCP server for payment-svc triage tools.
# Author: Salman
#
# This is basically week-06-lab.md's Step 2 as given -- metrics, logs,
# deployment history, dry-run rollback, and the gated rollback itself. I
# dropped the unused `random` import from the starter code and everything
# else is the same.
import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server("incident-tools")

# --- Simulated data store ---
DEPLOYMENTS = {
    "payment-svc": {
        "current_version": "v1.4.2",
        "previous_version": "v1.4.1",
        "deployed_at": "8 minutes ago",
        "migration_pending": False,
    },
    "cart-svc": {
        "current_version": "v2.1.0",
        "previous_version": "v2.0.9",
        "deployed_at": "2 hours ago",
        "migration_pending": False,
    },
}


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="get_metrics",
            description="Get current error rate and latency for a service",
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Service name"}
                },
                "required": ["service"],
            },
        ),
        Tool(
            name="get_recent_logs",
            description="Get recent error log lines for a service",
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {"type": "string"},
                    "tail": {"type": "integer", "default": 20},
                },
                "required": ["service"],
            },
        ),
        Tool(
            name="get_deployment_history",
            description="Get deployment history for a service",
            inputSchema={
                "type": "object",
                "properties": {"service": {"type": "string"}},
                "required": ["service"],
            },
        ),
        Tool(
            name="dry_run_rollback",
            description="Show what a rollback would do, without executing it",
            inputSchema={
                "type": "object",
                "properties": {"service": {"type": "string"}},
                "required": ["service"],
            },
        ),
        Tool(
            name="execute_rollback",
            description="Execute a rollback. REQUIRES prior human approval.",
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {"type": "string"},
                    "approved_by": {
                        "type": "string",
                        "description": "Name of approver",
                    },
                },
                "required": ["service", "approved_by"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "get_metrics":
        service = arguments["service"]
        # Simulate elevated metrics for payment-svc
        if service == "payment-svc":
            data = {
                "error_rate": 0.08,
                "p99_latency_ms": 450,
                "error_budget_remaining": 0.42,
            }
        else:
            data = {
                "error_rate": 0.003,
                "p99_latency_ms": 120,
                "error_budget_remaining": 0.85,
            }
        return [TextContent(type="text", text=json.dumps(data))]

    elif name == "get_recent_logs":
        service = arguments["service"]
        if service == "payment-svc":
            logs = [
                "ERROR NullPointerException in PaymentProcessor.process() line 142",
                "ERROR NullPointerException in PaymentProcessor.process() line 142",
                "WARN  Cart total $12,450.00 exceeded expected range",
                "ERROR NullPointerException in PaymentProcessor.process() line 142",
            ]
        else:
            logs = ["INFO  Request processed in 115ms", "INFO  Healthcheck OK"]
        return [TextContent(type="text", text="\n".join(logs))]

    elif name == "get_deployment_history":
        service = arguments["service"]
        info = DEPLOYMENTS.get(service, {})
        return [TextContent(type="text", text=json.dumps(info))]

    elif name == "dry_run_rollback":
        service = arguments["service"]
        info = DEPLOYMENTS.get(service, {})
        result = (
            f"DRY RUN: Would revert {service} from "
            f"{info.get('current_version')} -> "
            f"{info.get('previous_version')}. "
            f"Migration pending: {info.get('migration_pending')}"
        )
        return [TextContent(type="text", text=result)]

    elif name == "execute_rollback":
        service = arguments["service"]
        approver = arguments["approved_by"]
        info = DEPLOYMENTS.get(service, {})
        result = (
            f"ROLLBACK EXECUTED: {service} reverted from "
            f"{info.get('current_version')} -> "
            f"{info.get('previous_version')}. "
            f"Approved by: {approver}. ETA: 45 seconds."
        )
        return [TextContent(type="text", text=result)]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
