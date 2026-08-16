# incident_tools_server.py
# Week 6 Assignment: MCP server exposing the operations toolbox for notify-svc's
# OOM-crash-loop self-healing agent.
# Author: Salman
#
# Same shape as the lab's incident_tools_server.py, but for a different failure
# mode: a memory leak that OOMKills notify-svc's pods in a loop, rather than a
# bad deploy causing a NullPointerException. Restarting is a mitigation here,
# not a fix -- see runbooks/assignment-notify-svc-oom-crashloop.yaml.
import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server("notify-svc-incident-tools")

DEPLOYMENTS = {
    "notify-svc": {
        "current_version": "v3.7.0",
        "previous_version": "v3.6.4",
        "deployed_at": "6 hours ago",
        "migration_pending": False,
    },
}


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="get_metrics",
            description="Get current error rate, latency, restart count, and error budget for a service",
            inputSchema={
                "type": "object",
                "properties": {"service": {"type": "string", "description": "Service name"}},
                "required": ["service"],
            },
        ),
        Tool(
            name="get_pod_status",
            description="Get pod-level health: crash-loop state, restart count, memory usage, last OOM kill",
            inputSchema={
                "type": "object",
                "properties": {"service": {"type": "string"}},
                "required": ["service"],
            },
        ),
        Tool(
            name="get_recent_logs",
            description="Get recent log lines for a service",
            inputSchema={
                "type": "object",
                "properties": {"service": {"type": "string"}, "tail": {"type": "integer", "default": 30}},
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
            name="dry_run_restart",
            description="Show what a rolling pod restart would do, without executing it",
            inputSchema={
                "type": "object",
                "properties": {"service": {"type": "string"}},
                "required": ["service"],
            },
        ),
        Tool(
            name="restart_service",
            description="Execute a rolling restart of the service's pods. REQUIRES prior human approval.",
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {"type": "string"},
                    "approved_by": {"type": "string", "description": "Name of approver"},
                },
                "required": ["service", "approved_by"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "get_metrics":
        service = arguments["service"]
        if service == "notify-svc":
            data = {
                "error_rate": 0.061,
                "p99_latency_ms": 2100,
                "error_budget_remaining": 0.55,
                "restart_count_15m": 4,
            }
        else:
            data = {
                "error_rate": 0.002,
                "p99_latency_ms": 90,
                "error_budget_remaining": 0.9,
                "restart_count_15m": 0,
            }
        return [TextContent(type="text", text=json.dumps(data))]

    elif name == "get_pod_status":
        service = arguments["service"]
        if service == "notify-svc":
            data = {
                "crash_loop_backoff": True,
                "restarts_15m": 4,
                "memory_usage_pct": 97,
                "oom_killed_last": True,
            }
        else:
            data = {
                "crash_loop_backoff": False,
                "restarts_15m": 0,
                "memory_usage_pct": 41,
                "oom_killed_last": False,
            }
        return [TextContent(type="text", text=json.dumps(data))]

    elif name == "get_recent_logs":
        service = arguments["service"]
        if service == "notify-svc":
            logs = [
                "ERROR java.lang.OutOfMemoryError: Java heap space",
                "WARN  NotificationBatcher queue depth growing: 48000 pending",
                "ERROR java.lang.OutOfMemoryError: Java heap space",
                "INFO  Container OOMKilled, restarting pod notify-svc-7c9d4-x2p1q",
            ]
        else:
            logs = ["INFO  Batch sent: 214 notifications", "INFO  Healthcheck OK"]
        return [TextContent(type="text", text="\n".join(logs))]

    elif name == "get_deployment_history":
        service = arguments["service"]
        info = DEPLOYMENTS.get(service, {})
        return [TextContent(type="text", text=json.dumps(info))]

    elif name == "dry_run_restart":
        service = arguments["service"]
        result = (
            f"DRY RUN: Would perform a rolling restart of all {service} pods. "
            f"Estimated 3 pods, ~15s per pod, no traffic loss expected (rolling)."
        )
        return [TextContent(type="text", text=result)]

    elif name == "restart_service":
        service = arguments["service"]
        approver = arguments["approved_by"]
        result = (
            f"RESTART EXECUTED: rolling restart of {service} pods completed. "
            f"Approved by: {approver}. ETA: 45 seconds."
        )
        return [TextContent(type="text", text=result)]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
