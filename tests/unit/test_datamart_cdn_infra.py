"""Unit tests verifying Terraform infrastructure definitions for CloudFront Datamart CDN and S3 OAC."""

from pathlib import Path


def test_cloudfront_tf_exists_and_is_configured():
    """Validates cloudfront.tf configuration for OAC, CORS response headers, and distribution settings."""
    tf_file = (
        Path(__file__).resolve().parent.parent.parent
        / "infra"
        / "app"
        / "cloudfront.tf"
    )
    assert tf_file.exists(), "infra/app/cloudfront.tf must exist"

    content = tf_file.read_text(encoding="utf-8")

    # 1. Origin Access Control (OAC)
    assert "aws_cloudfront_origin_access_control" in content
    assert '"datamart_oac"' in content
    assert '"sigv4"' in content
    assert '"always"' in content

    # 2. Response Headers Policy with CORS
    assert "aws_cloudfront_response_headers_policy" in content
    assert '"datamart_cors_policy"' in content
    assert "cors_config" in content
    assert "var.cors_allowed_origins" in content
    assert "86400" in content

    # 3. CloudFront Distribution
    assert "aws_cloudfront_distribution" in content
    assert '"datamart_cdn"' in content
    assert "compress               = true" in content or "compress = true" in content
    assert "redirect-to-https" in content
    assert "origin_path" in content
    assert "level=mart/target=downstream/version=" in content
    assert "658327ea-f89d-4fab-a63d-7e88639e58f6" in content  # Managed-CachingOptimized


def test_s3_bucket_policy_has_oac_read_access():
    """Validates that s3.tf grants read access specifically to the CloudFront OAC principal."""
    s3_tf = Path(__file__).resolve().parent.parent.parent / "infra" / "app" / "s3.tf"
    assert s3_tf.exists()

    content = s3_tf.read_text(encoding="utf-8")

    assert "AllowCloudFrontServicePrincipalReadOnly" in content
    assert "cloudfront.amazonaws.com" in content
    assert "level=mart/target=downstream/*" in content
    assert "aws_cloudfront_distribution.datamart_cdn.arn" in content


def test_variables_and_outputs_configured():
    """Validates that cors_allowed_origins and CloudFront outputs are defined."""
    vars_file = (
        Path(__file__).resolve().parent.parent.parent / "infra" / "app" / "variables.tf"
    )
    vars_content = vars_file.read_text(encoding="utf-8")
    assert "cors_allowed_origins" in vars_content
    assert "datamart_version" in vars_content

    outputs_file = (
        Path(__file__).resolve().parent.parent.parent / "infra" / "app" / "outputs.tf"
    )
    outputs_content = outputs_file.read_text(encoding="utf-8")
    assert "cloudfront_distribution_domain_name" in outputs_content
    assert "cloudfront_distribution_id" in outputs_content
