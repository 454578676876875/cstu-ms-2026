#!/usr/bin/env python3
"""Standalone MCP client smoke test for jenkins_status_sim.py.

Mirrors project/mcp_servers/test_jenkins_status.py: spawns the server as a subprocess over
stdio (exactly how Claude Code would), does the MCP handshake, lists advertised tools, then
calls list_jobs and get_build_status -- against the local fixture instead of a live Jenkins.

Run:
  python src/mcp_servers/test_jenkins_status_sim.py
"""
import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "jenkins_status_sim.py")


def _text(result):
    return "\n".join(getattr(block, "text", str(block)) for block in result.content)


async def main():
    params = StdioServerParameters(command=sys.executable, args=[SERVER], env=os.environ.copy())

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Tools advertised:", ", ".join(t.name for t in tools.tools))

            print("\n--- list_jobs ---")
            print(_text(await session.call_tool("list_jobs", {})))

            print("\n--- get_build_status (job=ai-review-demo) ---")
            print(_text(await session.call_tool("get_build_status", {"job_name": "ai-review-demo"})))

            print("\n--- get_build_status (job=nightly-integration, IN_PROGRESS case) ---")
            print(_text(await session.call_tool("get_build_status", {"job_name": "nightly-integration"})))

            print("\n--- get_build_status (job=does-not-exist, 404 case) ---")
            print(_text(await session.call_tool("get_build_status", {"job_name": "does-not-exist"})))

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
