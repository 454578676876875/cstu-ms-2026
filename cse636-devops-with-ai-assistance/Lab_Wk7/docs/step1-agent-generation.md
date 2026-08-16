# Step 1 — Generating the Terraform, and the bug it exposed in my policy

## The prompt

Verbatim from `week-07-lab.md`:

```
Generate a Terraform aws_s3_bucket resource named "capstone-artifacts".
It must have: versioning enabled, server-side encryption (AES256),
public access blocked, and tags: Environment=capstone, ManagedBy=terraform.
```

The output is `terraform/compliant/s3.tf`. It passes `terraform validate`, plans
to 4 resources, and clears all 9 policy rules.

## The experiment worth writing down

There are two ways to express those four requirements, and which one an agent
picks matters more than I expected.

Modern (provider v4+): the bucket is one resource, and versioning, encryption,
and the public-access block are separate resources that reference it.

Deprecated (pre-v4): versioning and encryption are inline blocks inside the
`aws_s3_bucket` resource itself.

A lot of Terraform material still shows the older style, so it's a realistic
thing for a model to emit. I wrote it out (`terraform/deprecated-inline/s3.tf`)
and ran it through every gate to see what would actually catch it.

### What each gate did

| Gate | Result |
|---|---|
| `terraform validate` | **Success** — deprecation *warnings* only, no error |
| `terraform plan` | Succeeds. Plan contains **1** resource instead of 4 |
| `conftest` (my first policy) | 3 denies — no encryption, no versioning, no public-access block |

My first reaction was that this was a great result: validate waves it through,
policy catches it. I nearly wrote that up as the finding.

### It was wrong

Before writing it up I checked what the plan JSON actually contained, and the
inline attributes are still there with real values:

```json
"versioning": [{"enabled": true, "mfa_delete": false}],
"server_side_encryption_configuration": [
  {"rule": [{"apply_server_side_encryption_by_default": [{"sse_algorithm": "AES256"}]}]}
]
```

Provider v5.100 still honors the deprecated blocks. The bucket really would be
encrypted, and really would be versioned. Two of my three denies were false
positives: the policy was reporting a missing security control that was in fact
present, purely because it was spelled the old way.

The third deny was legitimate:
`aws_s3_bucket_public_access_block` has no inline equivalent, so that bucket
really would not have had one.

### The fix

`policy/s3.rego` now accepts either spelling for the security question, and
raises a `warn` (non-blocking) for the deprecated syntax:

```
$ conftest test plans/tfplan-deprecated-inline.json --policy policy/
WARN - ... declares encryption with the deprecated inline block; use
       aws_s3_bucket_server_side_encryption_configuration.
WARN - ... declares versioning with the deprecated inline block; use
       aws_s3_bucket_versioning.
FAIL - ... has no public access block.

9 tests, 6 passed, 2 warnings, 1 failure, 0 exceptions
```

One deny, and it's the true one. Two warnings that say "fix your syntax" without
blocking the pipeline. `policy/s3_test.rego` has four regression tests pinning
this behaviour so it can't quietly come back.

## Why this is the part of the lab I'd defend in a review

The lab's thesis is that the agent proposes and the policy decides, which
quietly assumes the policy is right. This was a case where it wasn't, and the
failure mode is the bad kind: a false positive on a security control. Those are
worse than they look, because a policy that blocks correct configurations gets
exceptions carved into it, then gets ignored, and then the one time it fires on
something real nobody believes it.

The thing that caught it was not the policy or the tests. Both agreed with each
other, because I'd written both from the same wrong assumption. What caught it
was reading the raw plan JSON to check what the tool was actually reporting,
instead of trusting my own summary of it.
