# CloudFront Origin Access Control (OAC) for securing S3 origin
resource "aws_cloudfront_origin_access_control" "datamart_oac" {
  name                              = "datamart-s3-oac"
  description                       = "Origin Access Control for Carpark Datamart S3 Origin"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# CloudFront Response Headers Policy for CORS & Cache Control
# NOTE: To restrict access to your specific Vercel frontend site in production,
# set var.cors_allowed_origins in terraform.tfvars or environment variables.
resource "aws_cloudfront_response_headers_policy" "datamart_cors_policy" {
  name    = "datamart-cors-and-security-policy"
  comment = "CORS response headers policy for Vercel web client access and browser caching"

  cors_config {
    access_control_allow_credentials = false

    access_control_allow_headers {
      items = ["*"]
    }

    access_control_allow_methods {
      items = ["GET", "HEAD", "OPTIONS"]
    }

    access_control_allow_origins {
      items = var.cors_allowed_origins
    }

    access_control_max_age_sec = 86400
    origin_override            = true
  }

  custom_headers_config {
    items {
      header   = "X-Datamart-Version"
      override = true
      value    = var.datamart_version
    }
  }
}

# CloudFront Distribution for Edge Delivery of Datamart JSON Files
resource "aws_cloudfront_distribution" "datamart_cdn" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "Carpark Availabilities Datamart Edge CDN"
  default_root_object = "manifest.json"
  price_class         = "PriceClass_100" # Singapore, US, Europe (Cost-optimized / Free Tier)

  origin {
    domain_name              = aws_s3_bucket.bucket.bucket_regional_domain_name
    origin_id                = "S3-Carpark-Datamart"
    origin_access_control_id = aws_cloudfront_origin_access_control.datamart_oac.id
    origin_path              = "/level=mart/target=downstream/version=${var.datamart_version}"
  }

  default_cache_behavior {
    target_origin_id       = "S3-Carpark-Datamart"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD", "OPTIONS"]
    compress               = true # Automatic Brotli and Gzip compression

    # AWS Managed Caching Policy: Managed-CachingOptimized (ID: 658327ea-f89d-4fab-a63d-7e88639e58f6)
    # Query strings and cookies ignored, TTL: min 1s, default 86400s (24h), max 31536000s
    cache_policy_id            = "658327ea-f89d-4fab-a63d-7e88639e58f6"
    response_headers_policy_id = aws_cloudfront_response_headers_policy.datamart_cors_policy.id
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = {
    Environment = "prod"
    Layer       = "datamart"
    Project     = "Carpark-Availabilities"
  }
}
