# Capstone Presentation Script (15 minutes)

Format: live demo preferred, run `python capstone/pipeline.py` from a terminal and narrate —
`transcripts/pipeline_run.txt` is the fallback recording if the live run isn't practical that day.

---

## 1. Problem statement (3 min)

"So if you did this whole pipeline by hand, here's what it looks like. An engineer watches CI.
Someone reviews a Terraform PR by eye. Someone else is eyeballing a dashboard trying to pick the
right moment to scale. And somebody notices an alert and has to decide whether to roll back.
That's four or five different people, on their own schedules, and each one of them is a
bottleneck — if they're asleep, in a meeting, whatever, the whole thing just waits on them.

What I built is the agentic version of that same five-stage pipeline: CI/CD, IaC, deploy,
observability, remediation. It uses the seven weekly labs from this course, actually wired
together instead of just described as connected. The one-line thesis, which I'm borrowing from
Week 7's own lab doc, is: the agent proposes, the guardrail decides. Everywhere an agent could
act, there's a non-agent layer sitting in front of it — a policy engine, a blocking approval
gate, a rate limiter — and that's the thing that actually authorizes the action."

## 2. Live demo (8 min)

Run `python capstone/pipeline.py` and narrate as it executes:

- **Stage 1 (CI/CD):** "Okay, Week 2's Lint→Test→AI-Review pipeline is running against an actual
  sample app, watch it pass all three stages. Then Week 3's remediation agent checks for one
  specific bug class — this run it doesn't find anything, but that's a real result too, not a
  pass I scripted in ahead of time."
- **Stage 2 (IaC):** "Week 7's OPA policy gate runs here against a real Terraform plan, with
  `conftest` actually installed and doing the check live. 9 tests, 9 passed, same result you'd
  see running it by hand in Lab_Wk7. The pipeline also has a fallback path for an environment
  without `conftest` — it would say so out loud and show you a previously-captured result instead
  of crashing or faking a pass — but that's not the path you're watching right now."
- **Stage 3 (predictive deploy):** "This is a real Prophet model forecasting CPU load and
  recommending a replica count. Watch the MAPE and the recommendation print live, not pulled
  from a cached file."
- **Stage 4 (observability):** "This one's interesting. An Isolation Forest model scores the
  metrics dataset and flags an anomaly. Watch the JSON print: `anomaly_detected: true`, first
  flagged at index 188."
- **Stage 5 (auto-remediate), the payoff:** "That JSON from Stage 4 — not a hardcoded string —
  is what builds the incident description the Week 6 agent is about to triage. Watch it reason:
  check metrics, check logs, check deploy history, dry-run the rollback, and stop, right here,
  for an actual approval prompt." *(Type `yes` and your name live if doing this interactively —
  that pause is the point, nothing proceeds without it.)* "And now it verifies its own fix worked
  by re-checking metrics instead of just declaring victory."

## 3. Lessons learned (3 min)

"One thing, not the polished-demo version:

Wiring Stage 4 into Stage 5 for real, instead of just describing them as adjacent, surfaced
something I didn't expect going in: the anomaly detector flagged the incident before the labeled
ground-truth window even starts. That's a leading-indicator result you only get by actually
running the pipeline, not by drawing an arrow between two boxes in a diagram. And when I first
built this, `conftest` wasn't installed here, so Stage 2 was running off a cached, previously-
captured result instead of live — the pipeline said so out loud rather than hiding it or faking
a pass. I'd rather show a partial pipeline that's telling the truth than a complete one that
isn't. `conftest` is installed now, so that particular gap is closed, but the honest-fallback
path is still there in case it isn't next time."

*What I'd do differently:* connect Stage 3's deploy decision into Stage 5's incident context too.
Right now the remediation agent doesn't know "we just scaled 30 seconds ago" when it triages an
alert, and an on-call engineer would probably want that correlation.

## 4. Questions (1 min)

Anticipated: *"Why doesn't the agent just fix things automatically end to end?"* My answer: the
whole point of every stage's guardrail — approval gate, policy engine, rate limiter, no
apply-tool at all — is that "the agent is capable" and "the agent can be trusted" are different
claims. This pipeline only relies on the second claim where it's actually been verified, never
where it's just assumed.
