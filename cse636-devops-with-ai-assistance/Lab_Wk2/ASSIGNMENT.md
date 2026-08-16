# Agent Integration and Governance Plan: Claude Code vs. GitHub Copilot

Salman, CSE636, Week 2 Assignment

## 1. Introduction

**Comparing:** Claude Code (Anthropic) and GitHub Copilot (agent mode, GitHub/Microsoft).
Chosen because they represent the two dominant deployment models in this space. Claude Code is a
terminal-first, tool-calling agent you compose into arbitrary pipelines (exactly what this
course's Lab_Wk5-Wk7 do), while Copilot is IDE-and-platform-native, tightly integrated into
GitHub's own PR/Actions/Issues surface. A team choosing between them is choosing between an
agent as a general-purpose tool-using process, versus an agent as a feature of the platform
they're already living in.

**Team context:** 25 engineers, ~150 repositories, production on AWS. Mid-DevOps-maturity:
CI exists per-repo (mostly GitHub Actions), but no centralized platform team, no existing
MCP-style tool layer, and code review norms vary by team.

## 2. Technical Comparison

| Dimension | Claude Code | GitHub Copilot (agent mode) |
|---|---|---|
| **Capabilities** | Full agentic loop: reads/writes files, runs shell commands, calls MCP tools, can drive multi-step tasks (refactors, test generation, CI triage) with minimal scaffolding. Requires explicit permission grants per tool/command class. | Autocomplete and chat are fully autonomous within the editor; "Agent mode" / Copilot Workspace can plan and execute multi-file changes and open PRs, but is more scoped to code-change tasks than open-ended shell/tool use. |
| **Integration** | CLI-native; drives any tool it's given a command for (git, docker, kubectl, arbitrary scripts) plus first-class MCP support for structured tool access (the exact pattern this course's Week 2 lab builds). Fits into CI as a pipeline step (see this repo's `Lab_Wk3`). | Deepest integration is inside VS Code / GitHub.com and GitHub Actions; MCP support exists but is newer and less central to the product's identity. Strongest where the workflow is already "open a PR on GitHub." |
| **Cost model** | Per-token API pricing (Anthropic) or a Claude subscription tier bundling Claude Code usage; self-hostable orchestration since it's just a CLI calling an API. | Flat per-seat subscription (Copilot Business/Enterprise); usage-based agent-mode/premium-request pricing on top for heavier agentic tasks. |
| **Autonomy level for common tasks** | Ranges from assistant (autocomplete-equivalent) to human-in-the-loop (approval-gated PR/tool-call flows, as built in this repo's Lab_Wk3/Wk6) depending entirely on how the integrator wires approval gates — the tool doesn't impose a ceiling. | Similar range, but the product nudges toward human-in-the-loop by default via the PR review flow GitHub already has; going further (e.g., autonomous merges) requires deliberately loosening branch protection rather than the tool doing it implicitly. |
| **Strengths** | Terminal/CLI fluency, strong at multi-step reasoning across a repo, first-class scriptability (this entire submission repo's Lab_Wk5-7 are built by driving it non-interactively), works uniformly across any Git host, not just GitHub. | Zero-setup IDE experience for individual engineers; tightest fit for "review this PR" / "fix this Copilot-flagged issue" workflows already inside GitHub's UI; strong autocomplete quality engineers already trust. |
| **Weaknesses / risks** | Requires the team to build its own guardrail layer (approval gates, tool scoping). Nothing stops a mis-scoped tool grant from being too broad, since the framework hands you the primitives, not a governance policy. | Less flexible outside the GitHub/VS Code ecosystem; agent-mode task scope is narrower than a general tool-calling loop, so it's a worse fit for cross-cutting tasks (infra changes, multi-repo coordination) than code-local changes. |

## 3. Integration Plan

**Phase 1 — pilot (weeks 1-4), one team, lowest-risk task first.** Start with AI code review as
an advisory comment, not a merge-blocking gate (mirrors this course's Week 2 lab). Claude Code
runs in CI on every PR, posts a review comment, blocks nothing. Blast radius is essentially zero:
worst case is a useless comment, not a bad merge. Copilot's PR review feature is a natural
parallel pilot in the same phase since it needs no separate setup on GitHub-hosted repos, which
gives an actual side-by-side comparison instead of a paper one.

**Phase 2 — build-fixer / triage agents (weeks 5-10), pilot team + 1 more.** Extend to the
build-fixer pattern this repo's `Lab_Wk3` and `Lab_Wk6` implement: agent proposes a fix as a PR
behind a required-reviewer gate, never merges itself. This is the first phase where an MCP
server (build status, deploy status) is worth standing up, since by now there's a genuine
cross-repo need for it.

**Phase 3 — broader rollout (weeks 11-16), all 25 engineers, opt-in per repo.** Only repos whose
owning team has completed a short guardrails checklist (branch protection confirmed, required
reviewers set, no agent token with merge rights) get access. This is a technical gate, not a
policy request — the MCP/CI wiring simply isn't provisioned until the checklist is verified.

**Tools needing MCP servers or API integrations:** a build-status server (Jenkins/Actions, per
this course's Week 2 lab), a deploy-status/risk-score server (Week 4 pattern), and a
scoped-read-only ticketing integration (for the triage/postmortem flow in Week 6). Each is a
separate credential with its own minimum scope — no single "do everything" service account.

**Measuring success:** PR review turnaround time (target: -20% by end of Phase 2), fraction of
CI failures auto-triaged with a correct root-cause proposal (tracked manually for the first 50
incidents, since "correct" needs a human judgment call), and a near-miss log: every case where a
human caught something the agent got wrong before it caused damage. This last one matters most.
A near-miss count going up over time as usage grows isn't automatically bad; a near-miss rate
that doesn't fall as guardrails mature is the actual red flag.

## 4. Governance Plan

### Permissions and credentials

- **Read-only by default everywhere.** Every agent identity starts with repo-read + PR-comment
  scopes only. Write scope (opening a branch/PR) is a separate, explicitly requested grant per
  repo, reviewed by that repo's owning team lead.
- **No agent identity ever gets merge rights.** Concretely: a GitHub App / fine-grained PAT with
  `contents: read`, `pull_requests: write` (to open, not merge), and **no** `contents: write` on
  protected branches. This is enforced by GitHub branch protection (required reviewers), not by
  asking the agent nicely, the same principle this repo's `Lab_Wk3`/`Lab_Wk6` enforce in code
  (`check_blast_radius()` gates the destructive call; it isn't just a system-prompt instruction).
- **Credential storage:** GitHub App private keys and any Anthropic API keys live in the org's
  secret manager (AWS Secrets Manager, since the team's on AWS), injected into CI as short-lived
  environment variables, never checked into a repo or a `.env` a human might commit by accident.
- **Rotation:** GitHub App keys rotated quarterly or immediately on any suspected leak; API keys
  on a 90-day schedule with automated expiry (key stops working, not just "should be rotated").

### Human oversight

| Action type | Oversight level | Approver |
|---|---|---|
| Read-only analysis / PR comment | None required (human-on-the-loop) | N/A — reviewed only if a human chooses to |
| Open a PR with a proposed fix | Required human approval before merge (human-in-the-loop) | The repo's on-call or a designated reviewer, never the requester who triggered the agent |
| Trigger a deploy or infra change | Required approval + a second reviewer for anything touching production | Team lead or on-call SRE |
| Anything the agent flags low-confidence | Escalate to a human immediately, no retry-and-guess | Same reviewer as the action type above |

When uncertain, the agent must say so explicitly in its output and stop rather than pick a
plausible-sounding default. This is a system-prompt requirement, enforced by treating any PR
whose description contains a hedge ("might," "unsure," "couldn't verify") as automatically
needing a second reviewer, not just the usual one.

### Auditability

- Every agent-initiated action (API call, PR opened, tool invocation) is logged with: which
  agent identity, which repo, what tool, what input, what output, and a timestamp. This mirrors
  the OTel GenAI span pattern this course's Week 5 lab implements, extended to write actions.
- Logs ship to the same centralized logging the rest of CI/CD already uses (so there's one
  place to search, not a separate agent-only silo).
- **Incident tracing:** every agent-authored commit carries a trailer (`Agent-Run-Id: <uuid>`)
  linking back to the full tool-call log for that run, so a production incident can be traced to
  "which specific agent invocation, with which inputs" in one lookup, not a guess.
- **Retention:** 1 year for agent action logs (matches the org's general audit-log retention),
  longer if a log is attached to an open incident or postmortem.

### Failure modes and incident response

1. **Agent proposes a plausible-but-wrong fix that a rushed reviewer approves.** Mitigation:
   require the PR description to include the agent's stated confidence and evidence (which log
   lines / test failures it based the fix on), so a reviewer has something concrete to check
   against, not just a diff to skim.
2. **Over-scoped credential gets exploited via prompt injection** (an agent reading untrusted
   content, e.g. an issue comment or a file it was asked to review, that contains hidden
   instructions). Mitigation: the tool-scoping described above means even a fully "hijacked"
   agent has no destructive tool to call; this is the same defense this course's Week 7 lab
   demonstrates directly (OPA + least-privilege tools stop a successful injection from mattering).
3. **Cost/usage runaway.** A mis-triggered workflow (e.g. an infinite retry loop) burns API
   budget or floods a repo with agent-opened PRs. Mitigation: a hard per-repo, per-day rate limit
   on agent-triggered runs, enforced in the CI wrapper script, not just monitored after the fact.

**Conditions to disable the agent entirely for a repo:** two or more near-misses in a 30-day
window where a human had to catch a proposed change that would have broken production if merged
as-is; or any confirmed case of the agent acting outside its granted tool scope (which should be
technically impossible, so if it happens, that's a bug in the scoping, not just a policy
violation, and rollout pauses org-wide until fixed).

### Policy and acceptable use

- The agent may **never**: merge to a protected branch, delete a resource, modify IAM/security
  group configuration, or access a production database directly.
- Enforced technically, not just by policy: branch protection blocks direct merges regardless of
  who/what pushes; the agent's tool set simply has no `terraform apply`, `kubectl delete`, or
  direct DB-write tool defined anywhere in its MCP server configuration — the same "no tool, no
  action" principle Week 7's lab demonstrates for `terraform_apply`.

## 5. Conclusion

**Recommendation:** deploy Claude Code first, for the CLI-native pipeline integrations (code
review, build-fixer, IaC generation) this team needs across 150 heterogeneous repos that aren't
all hosted identically. Layer in Copilot for individual-engineer IDE assistance where its
GitHub-native PR flow is strongest, rather than picking one exclusively. **First 90-day goal:**
Phase 1 (advisory code review, zero merge risk) live on 10 pilot repos, with a near-miss log
showing the guardrails actually catch what they're supposed to before Phase 2 begins.
