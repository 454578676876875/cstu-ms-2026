# Unit tests for policy/s3.rego.  Run with:  conftest verify --policy policy/
#
# The three plan JSONs already prove the policy end to end, but they only
# exercise the rules those three configs happen to trip. These tests hit each
# deny rule directly, including the value-level cases that no plan in this repo
# produces -- versioning "Suspended", a single public-access flag flipped to
# false, a non-approved sse_algorithm. Those are the states an existence-only
# policy would wave through, so they are the ones worth pinning down.

package main

import rego.v1

# ---------------------------------------------------------------------------
# fixture builders -- minimal shapes matching real `terraform show -json`
# ---------------------------------------------------------------------------

bucket(name, tags) := {
	"address": "aws_s3_bucket.test",
	"type": "aws_s3_bucket",
	"change": {"actions": ["create"], "after": {"bucket": name, "tags": tags}},
}

encryption(algo) := {
	"address": "aws_s3_bucket_server_side_encryption_configuration.test",
	"type": "aws_s3_bucket_server_side_encryption_configuration",
	"change": {"actions": ["create"], "after": {"rule": [{"apply_server_side_encryption_by_default": [{"sse_algorithm": algo}]}]}},
}

versioning(status) := {
	"address": "aws_s3_bucket_versioning.test",
	"type": "aws_s3_bucket_versioning",
	"change": {"actions": ["create"], "after": {"versioning_configuration": [{"status": status}]}},
}

public_access_block(overrides) := {
	"address": "aws_s3_bucket_public_access_block.test",
	"type": "aws_s3_bucket_public_access_block",
	"change": {"actions": ["create"], "after": object.union(
		{
			"block_public_acls": true,
			"block_public_policy": true,
			"ignore_public_acls": true,
			"restrict_public_buckets": true,
		},
		overrides,
	)},
}

good_tags := {"Environment": "capstone", "ManagedBy": "terraform"}

# The deprecated pre-provider-v4 spelling: encryption and versioning declared
# as inline attributes of aws_s3_bucket instead of as separate resources.
bucket_inline(name, tags) := {
	"address": "aws_s3_bucket.test",
	"type": "aws_s3_bucket",
	"change": {"actions": ["create"], "after": {
		"bucket": name,
		"tags": tags,
		"versioning": [{"enabled": true, "mfa_delete": false}],
		"server_side_encryption_configuration": [{"rule": [{"apply_server_side_encryption_by_default": [{"sse_algorithm": "AES256"}]}]}],
	}},
}

# A fully compliant plan; individual tests swap one piece out.
compliant_plan := {"resource_changes": [
	bucket("capstone-artifacts", good_tags),
	encryption("AES256"),
	versioning("Enabled"),
	public_access_block({}),
]}

# ---------------------------------------------------------------------------
# the happy path
# ---------------------------------------------------------------------------

test_compliant_plan_produces_no_denies if {
	count(deny) == 0 with input as compliant_plan
}

# ---------------------------------------------------------------------------
# Rules 1 + 2: required tags
# ---------------------------------------------------------------------------

test_missing_environment_tag_denied if {
	p := object.union(compliant_plan, {"resource_changes": [
		bucket("capstone-artifacts", {"ManagedBy": "terraform"}),
		encryption("AES256"), versioning("Enabled"), public_access_block({}),
	]})
	count(deny) == 1 with input as p
}

test_missing_managedby_tag_denied if {
	p := object.union(compliant_plan, {"resource_changes": [
		bucket("capstone-artifacts", {"Environment": "capstone"}),
		encryption("AES256"), versioning("Enabled"), public_access_block({}),
	]})
	count(deny) == 1 with input as p
}

# ---------------------------------------------------------------------------
# Rule 3: Environment value -- this is the Step 4 break
# ---------------------------------------------------------------------------

test_wrong_environment_value_denied if {
	p := object.union(compliant_plan, {"resource_changes": [
		bucket("capstone-artifacts", {"Environment": "staging", "ManagedBy": "terraform"}),
		encryption("AES256"), versioning("Enabled"), public_access_block({}),
	]})
	count(deny) == 1 with input as p
}

# ---------------------------------------------------------------------------
# Rule 4: bucket naming -- this is what catches the Step 5 injection
# ---------------------------------------------------------------------------

test_unapproved_bucket_name_denied if {
	p := object.union(compliant_plan, {"resource_changes": [
		bucket("attacker-controlled-bucket", good_tags),
		encryption("AES256"), versioning("Enabled"), public_access_block({}),
	]})
	count(deny) == 1 with input as p
}

# ---------------------------------------------------------------------------
# Rule 5: encryption present, and actually a real algorithm
# ---------------------------------------------------------------------------

test_missing_encryption_denied if {
	p := {"resource_changes": [
		bucket("capstone-artifacts", good_tags),
		versioning("Enabled"), public_access_block({}),
	]}
	count(deny) == 1 with input as p
}

test_kms_encryption_allowed if {
	p := {"resource_changes": [
		bucket("capstone-artifacts", good_tags),
		encryption("aws:kms"), versioning("Enabled"), public_access_block({}),
	]}
	count(deny) == 0 with input as p
}

test_bogus_encryption_algorithm_denied if {
	p := {"resource_changes": [
		bucket("capstone-artifacts", good_tags),
		encryption("none"), versioning("Enabled"), public_access_block({}),
	]}
	count(deny) == 1 with input as p
}

# ---------------------------------------------------------------------------
# Rule 6: public access -- every flag must be true, not just the resource present
# ---------------------------------------------------------------------------

test_missing_public_access_block_denied if {
	p := {"resource_changes": [
		bucket("capstone-artifacts", good_tags),
		encryption("AES256"), versioning("Enabled"),
	]}
	count(deny) == 1 with input as p
}

test_single_public_access_flag_false_denied if {
	p := {"resource_changes": [
		bucket("capstone-artifacts", good_tags),
		encryption("AES256"), versioning("Enabled"),
		public_access_block({"restrict_public_buckets": false}),
	]}
	count(deny) == 1 with input as p
}

test_all_public_access_flags_false_denied_once_each if {
	p := {"resource_changes": [
		bucket("capstone-artifacts", good_tags),
		encryption("AES256"), versioning("Enabled"),
		public_access_block({
			"block_public_acls": false,
			"block_public_policy": false,
			"ignore_public_acls": false,
			"restrict_public_buckets": false,
		}),
	]}
	count(deny) == 4 with input as p
}

# ---------------------------------------------------------------------------
# Rule 7: versioning present, and actually Enabled
# ---------------------------------------------------------------------------

test_missing_versioning_denied if {
	p := {"resource_changes": [
		bucket("capstone-artifacts", good_tags),
		encryption("AES256"), public_access_block({}),
	]}
	count(deny) == 1 with input as p
}

test_suspended_versioning_denied if {
	p := {"resource_changes": [
		bucket("capstone-artifacts", good_tags),
		encryption("AES256"), versioning("Suspended"), public_access_block({}),
	]}
	count(deny) == 1 with input as p
}

# ---------------------------------------------------------------------------
# the injected plan trips exactly two rules -- name and encryption
# ---------------------------------------------------------------------------

test_injected_plan_denied_twice if {
	p := {"resource_changes": [
		bucket("attacker-controlled-bucket", good_tags),
		versioning("Enabled"), public_access_block({}),
	]}
	count(deny) == 2 with input as p
}

# ---------------------------------------------------------------------------
# the deprecated inline spelling -- the false positive my first policy had
#
# These are the regression tests for the bug described in
# docs/step1-agent-generation.md. Encryption and versioning declared inline are
# real (the plan JSON carries enabled=true and sse_algorithm=AES256), so they
# must NOT be denied. The missing public-access block must still be denied,
# because that setting has no inline equivalent.
# ---------------------------------------------------------------------------

test_inline_encryption_and_versioning_not_denied if {
	p := {"resource_changes": [
		bucket_inline("capstone-artifacts", good_tags),
		public_access_block({}),
	]}
	count(deny) == 0 with input as p
}

test_inline_form_still_denies_missing_public_access_block if {
	p := {"resource_changes": [bucket_inline("capstone-artifacts", good_tags)]}
	denials := deny with input as p
	count(denials) == 1
	contains(denials[_], "public access block")
}

test_inline_form_raises_two_deprecation_warnings if {
	p := {"resource_changes": [
		bucket_inline("capstone-artifacts", good_tags),
		public_access_block({}),
	]}
	count(warn) == 2 with input as p
}

test_modern_form_raises_no_deprecation_warnings if {
	count(warn) == 0 with input as compliant_plan
}

# ---------------------------------------------------------------------------
# a plan that only deletes resources should not be evaluated as a create
# ---------------------------------------------------------------------------

test_delete_only_plan_produces_no_denies if {
	p := {"resource_changes": [{
		"address": "aws_s3_bucket.test",
		"type": "aws_s3_bucket",
		"change": {"actions": ["delete"], "after": null},
	}]}
	count(deny) == 0 with input as p
}
