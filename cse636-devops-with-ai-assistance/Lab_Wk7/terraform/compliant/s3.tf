# s3.tf -- COMPLIANT. This is Step 1 of the lab: the Terraform an agent produced
# from the natural-language request in week-07-lab.md.
#
# The prompt I gave (verbatim from the lab doc):
#
#   Generate a Terraform aws_s3_bucket resource named "capstone-artifacts".
#   It must have: versioning enabled, server-side encryption (AES256),
#   public access blocked, and tags: Environment=capstone, ManagedBy=terraform.
#
# Everything below satisfies policy/s3.rego, which is the whole point -- the
# agent proposes, the policy decides. See ../../docs/step1-agent-generation.md
# for what the agent got wrong on the first pass.

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Mock credentials + the three skip_* flags let `terraform plan` run with no AWS
# account and no network calls to AWS. Nothing here is ever applied -- this lab
# stops at `plan`, which is exactly the least-privilege posture the notes argue
# for (an agent with no apply credentials cannot apply anything).
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
    Environment = "capstone"
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
