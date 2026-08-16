"""Unit tests against the MCP server's tool handlers directly (no subprocess), same style as
project/mcp_servers doesn't ship, but matches the pattern used for the lab's other MCP servers.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "mcp_servers"))

import jenkins_status_sim as server


def test_list_jobs_returns_fixture_jobs():
    result = asyncio.run(server.call_tool("list_jobs", {}))
    text = result[0].text
    assert "ai-review-demo" in text
    assert "nightly-integration" in text


def test_get_build_status_success():
    result = asyncio.run(server.call_tool("get_build_status", {"job_name": "ai-review-demo"}))
    text = result[0].text
    assert "#41" in text
    assert "SUCCESS" in text


def test_get_build_status_in_progress_when_result_null():
    result = asyncio.run(
        server.call_tool("get_build_status", {"job_name": "nightly-integration"})
    )
    assert "IN_PROGRESS" in result[0].text


def test_get_build_status_job_not_found():
    result = asyncio.run(server.call_tool("get_build_status", {"job_name": "nope"}))
    assert "not found" in result[0].text


def test_list_tools_advertises_both_tools():
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert names == {"get_build_status", "list_jobs"}


def test_fixture_state_is_valid_json():
    with open(server.STATE_PATH, encoding="utf-8") as fh:
        state = json.load(fh)
    assert "jobs" in state


def test_get_build_status_missing_job_name_argument():
    result = asyncio.run(server.call_tool("get_build_status", {}))
    assert "Missing required argument" in result[0].text


def test_get_build_status_empty_builds_list():
    async def _run():
        job_data = {"jobs": {"empty-job": {"builds": []}}}
        original = server._load_state
        server._load_state = lambda: job_data
        try:
            return await server.call_tool("get_build_status", {"job_name": "empty-job"})
        finally:
            server._load_state = original

    result = asyncio.run(_run())
    assert "no builds yet" in result[0].text
