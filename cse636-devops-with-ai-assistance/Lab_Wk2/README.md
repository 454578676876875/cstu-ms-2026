# Week 2 Lab and Assignment: AI Code Review Pipeline + MCP Server

Covers the Week 2 lab (Part 1: Lint -> Test -> AI Code Review pipeline; Part 2: an MCP server
exposing build status) and the assignment (a governance-focused agent framework comparison),
both described in `week-02-lab.md`.

No Docker Desktop / Rancher Desktop is running on this machine, so both halves of Part 1 and
Part 2 are **local simulations** (this was agreed beforehand), same pattern as `Lab_Wk5`-`Lab_Wk7`.
The code is real, the tests are real, and the runs in `transcripts/` are real captured output.
It's just standing in for a live Jenkins container and a live Jenkins REST API instead of faking
output by hand.

## How to run

Managed with [`uv`](https://docs.astral.sh/uv/).

```bash
cd cse636-devops-with-ai-assistance/Lab_Wk2

# 1. Run the full pipeline: Lint -> Test -> AI Code Review (stands in for the Jenkins run)
uv run python src/pipeline_sim.py

# 2. Sanity-check the MCP server end-to-end (real stdio handshake, real subprocess)
uv run python src/mcp_servers/test_jenkins_status_sim.py

# 3. Run the test suite
uv run pytest -v
```

## Project structure

```
src/
  sample_app/
    app.py                 tiny inventory-reorder helper -- the repo the pipeline lints/tests/
                            reviews; one deliberate gap (apply_discount has no bounds check)
                            for the AI Review stage to find
    conftest.py             empty -- puts the repo root on sys.path (same as the lab's
                            given sample-python-app layout)
    tests/test_app.py
  ai_review.py               dual-mode AI review step: live Claude call if ANTHROPIC_API_KEY is
                              set, else a simulated review grounded in real static analysis of
                              the file (not canned text) -- same pattern as Lab_Wk5's
                              simulated_llm_call
  pipeline_sim.py             runs Lint -> Test -> AI Code Review locally, in the Jenkinsfile's
                              stage order, writing output/ai_review_report.txt
  mcp_servers/
    jenkins_status_sim.py     MCP server: list_jobs / get_build_status, same tool contract as
                              project/mcp_servers/jenkins_status.py, backed by
                              fixtures/jenkins_state.json instead of a live Jenkins REST call
    test_jenkins_status_sim.py  standalone MCP client smoke test (spawns the server, does the
                              real handshake, calls both tools) -- mirrors
                              project/mcp_servers/test_jenkins_status.py

fixtures/
  jenkins_state.json          3 builds across 2 jobs: a SUCCESS/FAILURE history for
                              ai-review-demo, and one job with a null `result` to exercise the
                              IN_PROGRESS path

transcripts/
  pipeline_run.txt            real run of pipeline_sim.py -- all 3 stages PASS
  mcp_client_smoke_test.txt   real run of the MCP client smoke test against the live subprocess

output/
  ai_review_report.txt        the actual generated review report

tests/
  test_ai_review.py           simulated-review static-analysis findings, live/simulated branch
  test_jenkins_mcp_server.py  the MCP server's tool handlers, called directly (no subprocess)

WRITEUP.md               permissions reflection the lab asks for + design notes
ASSIGNMENT.md              agent/framework comparison + integration & governance plan
```

## Design decisions

Why is the pipeline simulated instead of a real Jenkins container? No Docker Desktop / Rancher
Desktop running here. `pipeline_sim.py` runs the exact same three stages the lab's Jenkinsfile
defines, in the same order, with the same "lint findings don't fail the build, test failures are
surfaced but don't block AI Review" behavior, just as a local Python script instead of inside
`cstu-jenkins`. Every stage's output in `transcripts/pipeline_run.txt` comes from an actual
subprocess run (`flake8`, `pytest`, the review step), nothing hand-written.

The MCP server is fixture-backed for the same reason, instead of hitting a real Jenkins REST
API. `jenkins_status_sim.py` keeps the exact tool contract (`list_tools`/`call_tool`,
`get_build_status`/`list_jobs`) as `project/mcp_servers/jenkins_status.py`, so an agent talking
to either server sees an identical interface, and swaps the `requests.get(JENKINS_URL + ...)`
call for reading `fixtures/jenkins_state.json`. `test_jenkins_status_sim.py` is there to prove
this is an actual MCP server and not just a plain function: it spawns the file as a subprocess
and does the JSON-RPC handshake over stdio, the same way Claude Code would.

One more thing worth explaining: why the AI review step is grounded static analysis rather than
free-form text when it's running simulated. No `ANTHROPIC_API_KEY` is set here, and rather than
return a fixed canned string, `ai_review.simulated_review()` walks the file's AST for missing
docstrings and greps for the `NOTE:` comment flagging the one deliberate bug
(`apply_discount`'s missing bounds check on `percent_off`). So the report comes out of the actual
file content and would change if the file changed. Same idea as Lab_Wk5's `simulated_llm_call`.
