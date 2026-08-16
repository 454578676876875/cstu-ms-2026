# Week 2 Lab Reflection

## What to Submit, mapped to what's here

1. **"Screenshot of a successful Jenkins build showing the artifact."** No Jenkins running on
   this machine (agreed substitution, see `README.md`). Substituted with
   `transcripts/pipeline_run.txt`, a real captured run of all three stages showing `PASS` for
   lint, test, and AI review, plus `output/ai_review_report.txt` as the actual artifact the
   Jenkinsfile's `archiveArtifacts` step would have captured.
2. **`ai_review_report.txt`**: `output/ai_review_report.txt`, from one real run.
3. **MCP server code**: `src/mcp_servers/jenkins_status_sim.py`, commented per-section like the
   lab asks, plus `test_jenkins_status_sim.py` as proof it actually speaks MCP correctly.
4. **Permissions reflection**: below.

## What the AI review caught vs. what a linter missed

`flake8` on `sample_app/app.py` came back completely clean (`(no lint findings)` in
`transcripts/pipeline_run.txt`), so the file is PEP8-compliant. The AI review stage still found
two things a style linter structurally can't catch. First, `apply_discount` accepts
`percent_off` with no bounds check, so `apply_discount(100, 150)` silently returns `-50` instead
of erroring, which is a semantic bug rather than a style violation. Second, two public functions
have no docstring, and a linter without a docstring plugin (`flake8-docstrings` isn't installed
here) won't flag that by default. That's basically the value proposition the lab is testing for:
lint catches whether the code follows the style guide, AI review catches whether a function's
contract actually makes sense given what it accepts.

One thing it likely would have missed even running live: it only reviewed `app.py` in isolation,
so it has no visibility into how `apply_discount` gets called elsewhere. It can't tell you
whether the missing bounds check is reachable with attacker-controlled input or only ever gets a
hardcoded, safe discount from a config file. A real review needs call-site context, and this
single-file review step just doesn't give it that.

## Permissions granted, and how I'd scope them

The MCP server here is read-only by construction: its only two tools are `list_jobs` and
`get_build_status`, both reads. Even in the real (non-simulated) version, the credential it
would need is a Jenkins API token scoped to "read build status," not the full admin token the
lab's example config implies (`JENKINS_USER=admin`). Concretely I'd:

- Create a dedicated Jenkins service account (not `admin`) with the **Job/Read** and
  **Overall/Read** permissions only — no Job/Build, Job/Configure, or Job/Delete.
- Scope that account to the specific jobs an agent actually needs (Jenkins' Role Strategy
  plugin supports per-job role grants), rather than every job in the instance.
- Rotate the API token on a fixed schedule and store it as a Jenkins credential /
  environment secret, never in the MCP server's source.

Tightening further: the current tool set already can't mutate anything (no `trigger_build`,
`create_job`, or `execute` tool exists at all; the lab's optional write-path extensions aren't
implemented here), which is a stronger guarantee than a read-scoped-but-technically-writable
token, since there's no code path to abuse even if the token were over-privileged. The
fixture-backed version in this submission goes one step further for the local demo: no network
access and no real credential at all. Honestly, "what this server can do to anything outside
this repo" is just nothing.
