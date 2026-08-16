#!/usr/bin/env python3
"""Minimal MCP server exposing simulated Jenkins build status to an AI agent.

Same tool contract (list_jobs, get_build_status) and the same list_tools()/call_tool() shape as
project/build-fixer/mcp_servers/jenkins_status.py, but backed by a local fixtures/jenkins_state.json
instead of a `requests` call to a real Jenkins REST API -- there's no Docker/Jenkins on this
machine (see README.md for why). The tool contract an agent sees is identical either way.

Install: pip install mcp
Env:
  JENKINS_STATE_PATH  Path to the fixture JSON. Defaults to fixtures/jenkins_state.json next to
                       this project's root.
"""
import json
import os
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

DEFAULT_STATE_PATH = Path(__file__).resolve().parent.parent.parent / "fixtures" / "jenkins_state.json"
STATE_PATH = Path(os.environ.get("JENKINS_STATE_PATH", DEFAULT_STATE_PATH))

app = Server("cse636-jenkins-mcp-sim")


def _load_state():
    with open(STATE_PATH, encoding="utf-8") as fh:
        return json.load(fh)


@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="get_build_status",
            description=(
                "Returns the status and number of the most recent build for a given job. Use "
                "this to check if a CI pipeline is currently passing or failing before making "
                "code changes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "job_name": {
                        "type": "string",
                        "description": "The Jenkins job name, e.g. 'ai-review-demo'",
                    }
                },
                "required": ["job_name"],
            },
        ),
        Tool(
            name="list_jobs",
            description="Returns a list of all Jenkins job names.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        state = _load_state()
    except (OSError, json.JSONDecodeError) as exc:
        return [TextContent(type="text", text=f"Could not read Jenkins state: {exc}")]

    if name == "list_jobs":
        jobs = list(state.get("jobs", {}).keys())
        return [TextContent(type="text", text=f"Jenkins jobs: {', '.join(jobs) or '(none)'}")]

    if name == "get_build_status":
        job = arguments.get("job_name")
        if not job:
            return [TextContent(type="text", text="Missing required argument: job_name")]
        job_data = state.get("jobs", {}).get(job)
        if job_data is None:
            return [TextContent(type="text", text=f"Job '{job}' not found (or it has no builds yet).")]
        builds = job_data.get("builds", [])
        if not builds:
            return [TextContent(type="text", text=f"Job '{job}' has no builds yet.")]
        latest = builds[0]
        result = latest.get("result") or "IN_PROGRESS"
        number = latest.get("number", "?")
        return [TextContent(type="text", text=f"Job '{job}': build #{number} -- {result}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _serve():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(_serve())
