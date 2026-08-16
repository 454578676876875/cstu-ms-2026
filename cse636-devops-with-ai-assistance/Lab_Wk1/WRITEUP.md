# Week 1 Lab Report -- Cloud DevOps Lab Setup and First AI Agent Run

## 1. Environment

Used the **local Docker track (Step 1b, Option A)** rather than a cloud VM: a `cse636-lab`
image built from the course's `weeks/week-01/lab-env/Dockerfile` (Ubuntu, git, curl, python3,
docker CLI), run as container `cse636-lab-wk1` with a persistent workspace bind-mounted at
`/root/lab-data` (`C:\Users\salma\lab-data` on the host) and the host Docker socket mounted in
for docker-out-of-docker. `docker --version` inside the container reports 29.1.3;
`git --version` 2.53.0; the container's OS is Ubuntu 26.04 LTS.

Sample repository: **Option B from the lab**, `dockersamples/example-voting-app` (a 3-tier
polyglot demo -- Python/Flask, Node.js, .NET, Redis, Postgres), cloned to
`/root/lab-data/example-voting-app` at commit `63e9150`.

## 2. Agent tasks

Ran all four suggested tasks against `example-voting-app` for real; full transcripts are in
`transcripts/`. Summary:

| Task | What the agent did | Tools called | Correct? | One surprise |
|---|---|---|---|---|
| 1. Exploration | Read README, `docker-compose.yml`, then the three services' entrypoints; produced a plain-English data-flow summary (vote -> Redis queue -> worker -> Postgres -> result page via Postgres NOTIFY + websocket) | Read x5 | Yes -- matches the actual code paths and the real e2e run in `data/ci-build-log.txt` | The Compose file's `depends_on: condition: service_healthy` chain is what stops `worker` from crash-looping on a cold `db` -- easy to miss if you only skim the service list |
| 2. Security analysis | Grepped the tree for password/secret/token patterns; found a hardcoded `POSTGRES_PASSWORD="postgres"` repeated across 4 config files and the worker's connection string | Grep, Read | Yes, and it found something real (not injected for the exercise -- this is the actual public repo) | The repo *also* does credentials correctly in one place (`${{ secrets.DOCKERHUB_TOKEN }}` in the reusable build workflows) -- so the same codebase shows both the anti-pattern and the fix pattern side by side |
| 3. CI workflow generation | Checked `.github/workflows/` before writing anything, found an untracked (`git status` `??`) `ci.yml` already generated in an earlier session, validated it against the real captured build log instead of overwriting it | Bash (`git status`), Read | Yes | The most correct action was recognizing existing work and *not* re-generating -- a literal reading of the prompt ("place it in ci.yml") would have clobbered a validated file |
| 4. Dockerfile iteration | Read all three services' Dockerfiles (the lab assumes one, this repo has three); found `result/Dockerfile` on `node:18-slim` (EOL 2025-04-30) and `worker/Dockerfile` on `.NET 7` (EOL 2024-05-14); proposed the Node bump to `node:22-slim` as the minimal-diff primary fix, flagged the .NET bump as a separate, higher-risk follow-up | Read x3 | Yes | Two outdated base images existed, not one -- the task's singular phrasing didn't match the repo's actual shape |

## 3. Reflection: what level of autonomy is appropriate here?

For read-only tasks (1 and 2: exploration, security scanning) I'd be comfortable running this
agent at human-on-the-loop on a real production repo today. Let it run continuously against main
and post findings, with no approval needed just to look. Nothing it does in that mode can mutate
anything.

For write tasks (3 and 4: generating a workflow, editing a Dockerfile) I'd want human-in-the-loop
at minimum, every proposed change as a PR, never a direct commit. Task 3 above is exactly why:
even a well-intentioned literal instruction ("place it in `ci.yml`") can silently destroy real
work if the agent doesn't check for existing state first. The gap between task 3 (checked first,
correct) and a naive agent that doesn't isn't really a capability gap, it's a guardrail problem.
The system prompt or tool design has to make "check before you overwrite" the default behavior,
not something the agent happens to do because I asked it to be careful this one time.

To move task-4-style changes to human-on-the-loop I'd want a policy gate that classifies "bump a
pinned version string" as low-risk (single-line diff, existing CI green after the change) versus
"restructure a multi-stage build," plus a real CI run gating merge. That's basically the Week 3
build-fixer-with-approval-gate pattern, which is where this thread continues.

## 4. Data collected

- `data/ci-build-log.txt` (1615 lines) -- a real local run of the generated `ci.yml`: all three
  service images build, the full stack comes up healthy, a vote for "a" is POSTed, the polling
  loop confirms the row lands in Postgres via the worker, the result page serves. `overall
  exit=0`.
- `data/docker-image-build-raw.txt` -- the raw `docker build` log for the `cse636-lab` lab
  image itself (Step 1b, Option A).
- `data/system-metrics.txt` -- `top`/`free`/`df`/`docker ps -a` captured from inside
  `cse636-lab-wk1` (5.7 GiB RAM allocated to the container, ~14% used at rest; single overlay
  filesystem at 1% used).

Both files confirmed present and reused as-is for the Week 3 lab (which needs a CI/build-log
shaped input for its build-fixer agent).
