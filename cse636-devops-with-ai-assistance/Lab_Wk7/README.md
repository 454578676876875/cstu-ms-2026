# Week 7 Lab: Agentic IaC with a Policy Gate

The Week 7 lab from `week-07-lab.md`: an agent generates a Terraform S3 bucket,
Terraform validates and plans it, and an OPA policy run through conftest decides
whether the plan is allowed — before anything is applied. Plus the deliberate
policy break (Step 4) and the prompt-injection demo (Step 5).

The one-line summary of what this lab is actually about: **the agent proposes,
the policy decides.** Everything here is built so that stays true even when the
agent is wrong or actively manipulated.

## How to run

Needs `conftest` for the policy targets, and `terraform` only if you want to
regenerate the plans. **No AWS account is required** — the provider is
configured with mock credentials and `skip_*` flags, so `terraform plan` runs
fully offline. Nothing is ever applied.

```bash
cd cse636-devops-with-ai-assistance/Lab_Wk7

make policy            # Step 3: compliant plan          -> PASS, exit 0
make policy-fail       # Step 4: broken plan             -> 1 FAIL, exit 1
make policy-injected   # Step 5: injected plan           -> 2 FAIL, exit 1
make policy-deprecated # bonus:  deprecated inline style -> 1 FAIL + 2 WARN
make policy-all        # all four in order

make test              # 19 Rego unit tests for the policy itself

make validate          # terraform validate, all four variants
make plan-all          # regenerate every plans/tfplan-*.json
```

Installing the toolchain on Windows, which is what I did:

```bash
winget install Hashicorp.Terraform     # terraform
winget install ezwinports.make         # make
# conftest isn't in winget -- grab the Windows zip from
# https://github.com/open-policy-agent/conftest/releases and put it on PATH
```

Versions used: Terraform 1.15.8, AWS provider 5.100.0, conftest 0.69.0 (bundles
OPA 1.19.0).

## Layout

```
terraform/
  compliant/s3.tf           Step 1 output: what the agent generated. Passes everything.
  noncompliant/s3.tf        Step 4: Environment tag = "staging" instead of "capstone".
  injected/s3.tf            Step 5: what the prompt injection asked for.
  deprecated-inline/s3.tf   Bonus: the pre-provider-v4 inline style.

policy/
  s3.rego                   9 rules: tags, name prefix, encryption, public access, versioning.
  s3_test.rego              19 unit tests, including regressions for a false positive I hit.

plans/                      terraform show -json output for each variant, committed so the
                            policy targets run without terraform installed.

docs/
  malicious_docs.txt        the injection payload, verbatim from the lab doc.
  step1-agent-generation.md the generation experiment and the policy bug it exposed.
  step5-prompt-injection.md what the agent actually did, and why that isn't the defense.

transcripts/                captured output from real runs of every step.
```

## What each step shows

**Steps 1–2 — generate and plan.** `terraform/compliant/s3.tf` is what came out
of the lab's prompt. It plans to 4 resources with no AWS account
(`transcripts/01`).

**Step 3 — the policy passes.** 9 rules, 9 passed, exit 0 (`transcripts/02`).

**Step 4 — the policy blocks.** One tag changed from `capstone` to `staging`;
conftest returns one deny and exit 1, so CI would stop (`transcripts/03`). Worth
noting the broken config still passes `terraform validate` — validate checks
schema, not intent.

**Step 5 — prompt injection.** The full write-up is in
`docs/step5-prompt-injection.md`, including the honest version of what happened:
I gave the agent `docs/malicious_docs.txt` and **it refused to follow the
injection**. That's a real result but a weak one — it's one model, one attempt,
against a payload with three obvious tells (`SYSTEM:` marker, `---` fences, "do
not mention this change"). It is not a control you can rely on.

So the demonstrable part doesn't depend on the agent at all. I hand-wrote the
config the injection *wanted* (`terraform/injected/s3.tf`), and OPA blocks it
with two denies (`transcripts/04`) — regardless of how the bad Terraform got
there. Combined with the fact that nothing in this lab has an `apply` tool, a
fully successful injection still changes no infrastructure.

## Design decisions

**The policy checks values, not just resource existence.** The version in the
course starter denies only when an encryption resource is absent. Mine also
checks that `sse_algorithm` is really AES256 or aws:kms, that versioning status
is really `Enabled` (not `Suspended`), and that *all four* public-access booleans
are really true. Existence-only checks are easy to satisfy with a resource
that's present but switched off, which is the shape careless and malicious
changes both tend to take.

**I got the policy wrong first, and the fix is the interesting part.** Terraform
has two spellings for S3 encryption and versioning — the modern separate
resources, and deprecated inline blocks on `aws_s3_bucket`. My first policy only
recognized the modern form, so it denied a config that was genuinely encrypted
and versioned, just written the old way. Two false positives on security
controls. The policy now accepts either spelling and only *warns* about the
deprecated syntax. Full write-up in `docs/step1-agent-generation.md`; four
regression tests in `s3_test.rego` keep it fixed.

That mattered more to me than the passing case. A policy that blocks correct
configurations gets exceptions carved into it, then gets ignored, and then it
doesn't matter that it was right the one time it caught something real.

**Variants are separate directories, not edits to one file.** The lab says to
edit `s3.tf` in place for Step 4. I kept each variant as its own config so both
the pass and the fail are reproducible from a clean checkout and both plans stay
in version control.

**Committed plan JSON.** `plans/*.json` is checked in so `make policy` works
with only conftest installed. Regenerate any time with `make plan-all`.

## Known limitations

- **The policy is per-plan, not per-bucket.** With one bucket that's equivalent,
  but a plan with two buckets where only one is encrypted would pass, because
  associating a config resource with its bucket means resolving
  `bucket = aws_s3_bucket.X.id` references through the plan's `configuration`
  block. This is the first thing I'd fix.
- **No human approval gate.** The lab doesn't ask for one, but it's the defense
  from the Week 7 notes that's most conspicuously missing here — and the notes
  are specific that the confirmation should arrive on a *different channel* from
  the one carrying untrusted content.
- **The naming rule is a bit teaching-to-the-test.** I added the
  `capstone-` prefix rule knowing the injection renames the bucket. Naming
  conventions are ordinary governance, and the encryption deny would have fired
  anyway — but a policy only catches violations someone thought to write down.
- **State-blind.** The policy validates the end state, so it wouldn't flag that
  renaming a *live* bucket means destroy-and-recreate, i.e. data loss, with every
  individual rule still satisfied.
- **One injection attempt, one model.** See `docs/step5-prompt-injection.md`.

## Rubric coverage

Mapping the lab's "✅ Check your understanding — what each layer of this exercise
proves" to the evidence here.

| What it should prove | Where |
|---|---|
| Step 3: policy-as-code *allowing* a compliant plan | `transcripts/02-policy-pass.txt` — 9/9, exit 0 |
| Step 4: the guardrail *blocking* a non-compliant plan **before any apply** | `transcripts/03-policy-fail-step4.txt` — 1 deny, exit 1. Nothing in the repo can apply. |
| Step 5: why the policy gate and least-privilege tools matter | `transcripts/04` (OPA blocks the injected plan independently of the agent) + `docs/step5-prompt-injection.md` (defense table, and why the agent's refusal isn't the control) |
| Name the defense that would have stopped the injection | `docs/step5-prompt-injection.md` — least-privilege tools, argued against the alternatives |
