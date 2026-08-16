# Week 1 Lab and Assignment: Cloud DevOps Setup and First Agent Run

Covers the Week 1 lab (cloud/Docker lab environment + four observed agent tasks against a real
sample repo) and the assignment (three real-world agentic-DevOps deployments, researched and
cited), both described in `week-01-lab.md`.

This week is different in shape from Weeks 5-7. The lab itself is "run an AI agent against a
repo and watch what it does," so instead of building a separate simulated project I ran the
four tasks with Claude Code (this session) against a real cloned repository inside the course's
Step 1b local Docker lab environment and kept the transcripts.

## What's here

```
sample repo used:  dockersamples/example-voting-app, cloned into the Step 1b Docker
                    container's workspace (not copied into this repo -- see below)

transcripts/
  task1-exploration.txt              "explain what this app does" -- read-only
  task2-security-analysis.txt        grep + read for hardcoded credentials -- found a real one
  task3-ci-workflow-generation.txt   generate a GitHub Actions CI workflow
  task4-dockerfile-iteration.txt     find + propose fixing an outdated base image

data/
  ci-build-log.txt                   real local run of the generated ci.yml (1615 lines,
                                      full build + e2e vote-flow test, exit=0)
  docker-image-build-raw.txt         raw docker build log for the Step 1b lab image itself
  system-metrics.txt                 top/free/df/docker ps captured inside the lab container

output/
  generated-ci.yml                   the actual CI workflow reviewed in Task 3
  assignment_reflection.pdf          the assignment essay, rendered to PDF (submission format)

WRITEUP.md          lab report (environment, per-task summary table, autonomy reflection,
                     confirmation of collected data)
ASSIGNMENT.md        "Real-World Agentic DevOps Deployments" essay (three deployments,
                      web-researched and cited, one involving a real production failure)
```

## Why the sample repo isn't copied into this folder

`example-voting-app` lives in the Step 1b Docker lab environment's persistent workspace
(`cse636-lab-wk1` container, host-mounted at `C:\Users\salma\lab-data`), which is the environment
the lab actually asks you to set up and run the agent inside. Copying a 200+ file third-party
clone into this submission repo would just be duplication. The transcripts already capture what
the agent found and did there, and that's the actual lab deliverable.

## Design decisions

Task 3 found existing untracked work and didn't overwrite it. `.github/workflows/ci.yml` in the
cloned repo was already present (`git status` shows it as `??`, meaning never committed to the
upstream repo; it was generated in an earlier session against this same lab environment) and
already validated by a real green run (`data/ci-build-log.txt`). The correct move was to check
before writing, confirm the existing file actually satisfies the task, and document that instead
of silently regenerating a second, possibly worse version. `WRITEUP.md`'s autonomy reflection
calls this out as the most important thing this lab surfaced.

Task 4 turned up two outdated base images, not the one the prompt assumes. The lab's phrasing
("the Dockerfile") assumes a single Dockerfile, but this repo has three, one per service. I
checked all three instead of guessing which one the prompt meant and found `result/Dockerfile`
on an EOL'd Node 18 and `worker/Dockerfile` on an EOL'd .NET 7. I scoped the actual fix to the
lower-risk single-line bump (Node 18 -> 22) and flagged the .NET bump separately instead of
bundling a riskier change into the same pass.

The assignment essay is grounded in cited sources, researched via web search rather than written
from memory: a documented production-database-deletion incident (Replit, July 2025), the 2025
DORA State of AI-Assisted Software Development report (aggregate, industry-wide), and a named
practitioner account of Anthropic's own internal SRE use of Claude. See `ASSIGNMENT.md`'s
References section for full citations.
