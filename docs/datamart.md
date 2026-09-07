# Datamart & CloudFront CDN Documentation

The **Datamart Layer** exports pre-computed, historical probability distributions and carpark availability metrics from the analytical **Gold Layer** into lightweight, highly-optimized JSON documents served globally via **Amazon CloudFront CDN**.

---

## 1. Architecture & Serving Pipeline

```mermaid
flowchart LR
    SFN["AWS Step Functions\n(carpark-daily-pipeline)"] -->|Task 3| Lambda["datamart_publisher Lambda\n(packages/datamart)"]
    Lambda -->|Read CSV directly| S3_CSV[("S3 CSV Mart\nlevel=mart/target=publisher/")]
    Lambda -->|Upload JSON| S3[("Private S3 Bucket\nlevel=mart/target=downstream/version=v1/\n(Public Access Blocked)")]
    
    Client["Vercel Frontend / Mobile Client"] -->|HTTPS GET /carparks/ACB_C.json| CF["Amazon CloudFront CDN\n• Origin Access Control (OAC)\n• Auto Brotli/Gzip Compression\n• 24h Edge Cache\n• Parameterized CORS"]
    CF -->|Cache Miss (Private SigV4)| S3
    CF -->|Cache Hit (< 20ms)| Client
```

---

## 2. CloudFront CDN & S3 Origin Access Control (OAC)

1. **100% Private S3 Storage**:
   * S3 public access is blocked completely (`block_public_acls = true`, `restrict_public_buckets = true`).
   * CloudFront accesses S3 using AWS **Origin Access Control (OAC)** with SigV4 signing.
   * S3 bucket policy strictly permits read access (`s3:GetObject`) only to the CloudFront distribution ARN principal.
2. **Edge Performance**:
   * Requests hit CloudFront edge locations in Singapore (`SIN`) with sub-20ms latency.
   * Auto-compression (`Brotli` and `Gzip`) reduces individual carpark JSON sizes to ~1.5 KB.
   * Default cache TTL is set to **24 hours** via `Managed-CachingOptimized` (`658327ea-f89d-4fab-a63d-7e88639e58f6`).

---

## 3. CORS Configuration for Vercel Frontend

CloudFront uses a dedicated response headers policy (`aws_cloudfront_response_headers_policy.datamart_cors_policy`) parameterized via Terraform:

```hcl
variable "cors_allowed_origins" {
  type        = list(string)
  description = "Allowed origins for Datamart CloudFront CORS"
  default     = ["*"]
}
```

### Production Deployment Action:
When deploying your frontend to Vercel, update `cors_allowed_origins` in your `terraform.tfvars` or deployment variables:

```hcl
cors_allowed_origins = [
  "https://my-carpark-app.vercel.app",
  "https://*.vercel.app",
  "http://localhost:3000"
]
```

---

## 4. S3 Key Hierarchy & Endpoints

Base path: `s3://<BUCKET_NAME>/level=mart/target=downstream/version=v1/`
CloudFront distribution maps `/` directly to `/level=mart/target=downstream/version=v1/`:

| Path | CDN Endpoint | Description |
| :--- | :--- | :--- |
| `manifest.json` | `https://<cdn-domain>/manifest.json` | Root index listing metadata, generation timestamp, and total carparks. |
| `carparks/{id}_{lot_type}.json` | `https://<cdn-domain>/carparks/ACB_C.json` | Individual carpark profile containing full 7-day $\times$ 24-hour distribution stats. |
| `summary/weekly_carpark_distributions.json.gz` | `https://<cdn-domain>/summary/weekly_carpark_distributions.json.gz` | Consolidated GZIP bundle of all carparks for bulk client preload. |

---

## 5. Schema Contracts

### 5.1 Carpark with Capacity Data (e.g. HDB)
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "metadata": {
    "version": "1.0.0",
    "generated_at": "2026-09-03T00:15:00+08:00",
    "timezone": "Asia/Singapore (UTC+8)",
    "lookback_window_days": 60
  },
  "carpark": {
    "carpark_id": "ACB",
    "lot_type": "C",
    "lot_type_description": "Cars",
    "development": "BLOCK 270/271 ALBERT CENTRE BASEMENT CAR PARK",
    "agency": "HDB",
    "area": "Bencoolen",
    "total_lots": 500,
    "has_capacity_data": true,
    "coordinates": { "latitude": 1.30123, "longitude": 103.85412 }
  },
  "weekly_distribution": {
    "1": {
      "day_name": "Monday",
      "day_of_week": 1,
      "is_weekend": false,
      "daily_summary": {
        "observation_count": 1440,
        "lots_available": {
          "min": 2, "p10": 15, "p25": 45, "p50": 120, "p75": 280, "p90": 410, "max": 495, "mean": 165.4, "std_dev": 112.3
        },
        "occupancy_rate": {
          "min": 0.01, "p10": 0.18, "p25": 0.44, "p50": 0.76, "p75": 0.91, "p90": 0.97, "max": 0.996, "mean": 0.6692, "std_dev": 0.2246
        },
        "probability_full": 0.045,
        "probability_high_occupancy_ge_90pct": 0.215
      },
      "hourly_distribution": [
        {
          "hour_of_day_sgt": 8,
          "time_window": "08:00 - 08:59",
          "observation_count": 60,
          "lots_available": {
            "min": 10, "p10": 25, "p25": 40, "p50": 60, "p75": 90, "p90": 130, "max": 180, "mean": 68.5, "std_dev": 35.2
          },
          "occupancy_rate": {
            "min": 0.64, "p10": 0.74, "p25": 0.82, "p50": 0.88, "p75": 0.92, "p90": 0.95, "max": 0.98, "mean": 0.863, "std_dev": 0.0704
          },
          "probability_full": 0.0,
          "probability_high_occupancy_ge_90pct": 0.35
        }
      ]
    }
  }
}
```

### 5.2 Carpark without Capacity Data (e.g. Non-HDB / LTA Malls)
For carparks where `total_lots` is unknown:
* `has_capacity_data: false`
* `total_lots: null`
* `occupancy_rate: null`
* `probability_high_occupancy_ge_90pct: null`
* `lots_available` statistics and `probability_full` ($0$ lots available) remain fully computed and available.
