# s3.tf -- THE DEPRECATED INLINE PATTERN. Not part of the lab's five steps; I
# added it after an experiment during Step 1 (see docs/step1-agent-generation.md).
#
# Before provider v4, S3 settings were inline attributes of aws_s3_bucket rather
# than separate resources. A large amount of Terraform training data still shows
# this style, so it is a realistic thing for an agent to emit. What makes it
# worth keeping as a fixture is how it behaves at each gate:
#
#   terraform validate  -> Success, with only deprecation WARNINGS
#   terraform plan      -> succeeds; encryption + versioning ARE really set
#   conftest            -> 1 deny + 2 warns
#
# The single deny is legitimate: there is no aws_s3_bucket_public_access_block
# here, and unlike encryption/versioning that setting has no inline equivalent,
# so this bucket genuinely would not have one.
#
# My first draft of the policy denied all three, because it only looked for the
# modern separate resources. Two of those three were false positives -- the plan
# JSON shows versioning enabled=true and sse_algorithm=AES256 really are present
# on the bucket. Policy now accepts either spelling for the security check and
# only warns about the deprecated syntax.

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region                      = "us-east-1"
  access_key                  = "mock_access_key"
  secret_key                  = "mock_secret_key"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
}

resource "aws_s3_bucket" "capstone_artifacts" {
  bucket = "capstone-artifacts"
  acl    = "private"

  versioning {
    enabled = true
  }

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }

  tags = {
    Environment = "capstone"
    ManagedBy   = "terraform"
  }
}

# NOTE: no aws_s3_bucket_public_access_block. There is no inline equivalent for
# it, which is exactly why the policy's remaining deny against this file is a
# true positive rather than a syntax complaint.
