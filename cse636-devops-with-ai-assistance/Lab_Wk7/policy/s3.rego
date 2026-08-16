# S3 guardrails, evaluated by conftest against `terraform show -json` output.
# Every deny that matches prints a message and fails the build, which is what
# stops a non-compliant plan from reaching `terraform apply`.
#
#   conftest test plans/tfplan-compliant.json --policy policy/
#
# Design note 1: the version of this policy in the course starter checks only
# that an encryption resource *exists*. I check the values too (sse_algorithm is
# actually AES256, versioning status is actually "Enabled", every one of the
# four public-access booleans is actually true). Existence checks are easy to
# satisfy with a resource that is present but switched off, which is exactly the
# kind of thing a prompt-injected or careless change produces.
#
# Design note 2: encryption and versioning each have TWO valid spellings -- the
# modern separate resource, and the deprecated inline block on aws_s3_bucket.
# I check for both. I did not do this originally, and testing caught it: an
# agent that emits the old inline style (which a lot of Terraform training data
# still shows) produced a plan that genuinely IS encrypted and versioned, but my
# first policy denied it because it only looked for the separate resources.
# That is a false positive, and a policy that cries wolf gets switched off. The
# deprecated form now raises a `warn` instead -- visible, but not blocking.
# See docs/step1-agent-generation.md for the full experiment.
#
# Known limitation: the encryption/versioning/public-access rules are evaluated
# per PLAN, not per BUCKET. With one bucket in the plan (this lab) that is
# equivalent. A plan with two buckets where only one is encrypted would pass,
# because associating a config resource with its bucket means resolving
# `bucket = aws_s3_bucket.X.id` references through the plan's `configuration`
# block. Called out in the README as the top thing I would fix next.

package main

import rego.v1

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

buckets contains r if {
	r := input.resource_changes[_]
	r.type == "aws_s3_bucket"
	"create" in r.change.actions
}

resources_of_type(t) := [r |
	r := input.resource_changes[_]
	r.type == t
	"create" in r.change.actions
]

valid_sse_algorithms := {"AES256", "aws:kms"}

# ---------------------------------------------------------------------------
# Rule 1 + 2: required tags must be present
# ---------------------------------------------------------------------------

required_tags := ["Environment", "ManagedBy"]

deny contains msg if {
	r := buckets[_]
	tag := required_tags[_]
	not r.change.after.tags[tag]
	msg := sprintf("S3 bucket '%s' is missing the required '%s' tag.", [r.address, tag])
}

# ---------------------------------------------------------------------------
# Rule 3: Environment must be exactly "capstone" for this exercise
# ---------------------------------------------------------------------------

deny contains msg if {
	r := buckets[_]
	env := r.change.after.tags.Environment
	env != "capstone"
	msg := sprintf(
		"S3 bucket '%s' has Environment='%s', expected 'capstone'.",
		[r.address, env],
	)
}

# ---------------------------------------------------------------------------
# Rule 4: bucket names must use the approved prefix
#
# A naming convention is ordinary S3 governance, but it earns its place here for
# a specific reason: it is the rule that catches the Step 5 injection, which
# renamed the bucket while leaving the tags untouched to look normal.
# ---------------------------------------------------------------------------

approved_bucket_prefix := "capstone-"

deny contains msg if {
	r := buckets[_]
	name := r.change.after.bucket
	not startswith(name, approved_bucket_prefix)
	msg := sprintf(
		"S3 bucket '%s' has name '%s', which does not start with the approved prefix '%s'.",
		[r.address, name, approved_bucket_prefix],
	)
}

# ---------------------------------------------------------------------------
# Rule 5: server-side encryption, in either the modern or the deprecated form
# ---------------------------------------------------------------------------

# modern: a dedicated aws_s3_bucket_server_side_encryption_configuration
encryption_ok if {
	enc := resources_of_type("aws_s3_bucket_server_side_encryption_configuration")[_]
	algo := enc.change.after.rule[_].apply_server_side_encryption_by_default[_].sse_algorithm
	algo in valid_sse_algorithms
}

# deprecated: an inline server_side_encryption_configuration block on the bucket
encryption_ok if {
	b := buckets[_]
	algo := b.change.after.server_side_encryption_configuration[_].rule[_].apply_server_side_encryption_by_default[_].sse_algorithm
	algo in valid_sse_algorithms
}

deny contains msg if {
	r := buckets[_]
	not encryption_ok
	msg := sprintf("S3 bucket '%s' has no server-side encryption with an approved algorithm.", [r.address])
}

warn contains msg if {
	b := buckets[_]
	b.change.after.server_side_encryption_configuration
	msg := sprintf(
		"S3 bucket '%s' declares encryption with the deprecated inline block; use aws_s3_bucket_server_side_encryption_configuration.",
		[b.address],
	)
}

# ---------------------------------------------------------------------------
# Rule 6: a public-access block must exist AND have all four flags on
#
# All four matter. Leaving one false is the classic way a bucket ends up
# publicly readable while still appearing to have a public-access block.
# ---------------------------------------------------------------------------

public_access_flags := [
	"block_public_acls",
	"block_public_policy",
	"ignore_public_acls",
	"restrict_public_buckets",
]

deny contains msg if {
	r := buckets[_]
	count(resources_of_type("aws_s3_bucket_public_access_block")) == 0
	msg := sprintf("S3 bucket '%s' has no public access block.", [r.address])
}

deny contains msg if {
	pab := resources_of_type("aws_s3_bucket_public_access_block")[_]
	flag := public_access_flags[_]
	pab.change.after[flag] != true
	msg := sprintf(
		"Public access block '%s' has %s=false; all four public-access flags must be true.",
		[pab.address, flag],
	)
}

# ---------------------------------------------------------------------------
# Rule 7: versioning must be on, in either the modern or the deprecated form
#
# "Suspended" is a real and easy-to-miss state -- the resource is present, so an
# existence-only check passes, but the bucket is not actually versioned.
# ---------------------------------------------------------------------------

# modern: a dedicated aws_s3_bucket_versioning with status Enabled
versioning_ok if {
	v := resources_of_type("aws_s3_bucket_versioning")[_]
	v.change.after.versioning_configuration[_].status == "Enabled"
}

# deprecated: an inline versioning { enabled = true } block on the bucket
versioning_ok if {
	b := buckets[_]
	b.change.after.versioning[_].enabled == true
}

deny contains msg if {
	r := buckets[_]
	not versioning_ok
	msg := sprintf("S3 bucket '%s' does not have versioning enabled.", [r.address])
}

warn contains msg if {
	b := buckets[_]
	b.change.after.versioning
	msg := sprintf(
		"S3 bucket '%s' declares versioning with the deprecated inline block; use aws_s3_bucket_versioning.",
		[b.address],
	)
}
