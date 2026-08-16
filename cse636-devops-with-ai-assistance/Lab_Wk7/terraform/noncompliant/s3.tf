# s3.tf -- NON-COMPLIANT ON PURPOSE. This is Step 4 of the lab.
#
# Identical to terraform/compliant/s3.tf except for one line: the Environment
# tag says "staging" instead of "capstone". That single character-level change
# is enough for policy/s3.rego to block the plan before any apply.
#
# The point of keeping it as a separate directory rather than editing the
# compliant file in place (which is what the lab literally says to do) is that
# both plans stay in version control, so the pass and the fail are both
# reproducible from a clean checkout. `make policy-fail` runs this one.

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

  tags = {
    Environment = "staging" # <-- THE BREAK: policy requires "capstone"
    ManagedBy   = "terraform"
  }
}

resource "aws_s3_bucket_versioning" "capstone_artifacts" {
  bucket = aws_s3_bucket.capstone_artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "capstone_artifacts" {
  bucket = aws_s3_bucket.capstone_artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "capstone_artifacts" {
  bucket = aws_s3_bucket.capstone_artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
