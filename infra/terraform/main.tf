# AWS resources for the cloud version of the raw layer. Not applied by the local demo (it uses MinIO).
# Usage: cd infra/terraform && terraform init && terraform apply -var="bucket_name=<globally-unique-name>"
terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

variable "bucket_name" { type = string }
variable "region" {
  type    = string
  default = "ap-south-1"
}

provider "aws" { region = var.region }

resource "aws_s3_bucket" "raw" { bucket = var.bucket_name }

resource "aws_s3_bucket_versioning" "raw" {
  bucket = aws_s3_bucket.raw.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "AES256" } }
}

resource "aws_s3_bucket_public_access_block" "raw" {
  bucket                  = aws_s3_bucket.raw.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Cost control: raw files move to cheaper storage, quarantine files expire.
resource "aws_s3_bucket_lifecycle_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id
  rule {
    id     = "raw-to-infrequent-access"
    status = "Enabled"
    filter { prefix = "raw/" }
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
  }
  rule {
    id     = "expire-quarantine"
    status = "Enabled"
    filter { prefix = "quarantine/" }
    expiration { days = 90 }
  }
}

# Least-privilege identity for the pipeline: read/write only this bucket.
data "aws_iam_policy_document" "pipeline" {
  statement {
    actions   = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
    resources = [aws_s3_bucket.raw.arn, "${aws_s3_bucket.raw.arn}/*"]
  }
}

resource "aws_iam_policy" "pipeline" {
  name   = "${var.bucket_name}-pipeline"
  policy = data.aws_iam_policy_document.pipeline.json
}

output "bucket" { value = aws_s3_bucket.raw.bucket }
output "policy_arn" { value = aws_iam_policy.pipeline.arn }
