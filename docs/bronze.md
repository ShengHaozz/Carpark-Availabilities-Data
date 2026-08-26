# Bronze Layer Documentation

The **Bronze Layer** is the raw data ingestion tier of the Carpark Availabilities Data Platform. It collects unmodified, point-in-time snapshots of carpark lot availabilities from external Singapore government APIs and writes them directly to Amazon S3 as timestamped JSON objects.

---

## 1. Overview & Objectives

* **Immutability**: Raw API responses are archived without in-flight mutations to preserve an exact audit trail and enable historical replay/reprocessing.
* **Frequency**: Triggered every **10 minutes** via AWS EventBridge Scheduler.
* **Storage Format**: Hive-partitioned JSON files in S3.
* **Timestamp Alignment**: Snapshots are floored to the nearest 10-minute boundary (`HH:00`, `HH:10`, `HH:20`, `HH:30`, `HH:40`, `HH:50`) for consistent temporal joins downstream.

---

## 2. Ingestion Packages & Sources

### 2.1 LTA DataMall (`packages/lta_poller`)
* **Endpoint**: `https://datamall2.mytransport.sg/ltaodataservice/CarParkAvailabilityv2?$skip={skip}`
* **Authentication**: Header `AccountKey: <DATAMALL_ACCOUNT_KEY>`
* **Pagination**: Returns up to 500 records per page. The poller loops incrementing `$skip` by 500 until an empty `value` list is encountered (up to 10 pages).
* **Agencies Included**: LTA, URA, and HDB carparks with real-time telemetry.
* **Rate Limiting & Retries**:
  * Implements exponential backoff: `10 * (tries ** 2)` seconds or respects `Retry-After` header on HTTP 429.
  * Maximum 3 attempts per page before skipping.

### 2.2 Data.gov.sg HDB Poller (`packages/hdb_poller`)
* **Endpoint**: `https://api.data.gov.sg/v1/transport/carpark-availability`
* **Authentication**: Public API (no header required).
* **Payload**: Single JSON response containing an array of `carpark_data` with `carpark_number` and `carpark_info` (providing both `lots_available` and `total_lots`).
* **Rate Limiting & Retries**: Exponential backoff with up to 3 retries on transient network errors or HTTP 429.

---

## 3. S3 Storage & Partitioning Layout

All raw payloads are written to S3 using standard Hive-style partitioning paths:

```text
s3://<BUCKET_NAME>/level=bronze/source=<SOURCE>/year=<YYYY>/month=<MM>/day=<DD>/hour=<HH>/snapshot_<ISO_TIMESTAMP>.json
```

### Example S3 Keys:
* `level=bronze/source=lta/year=2026/month=08/day=26/hour=04/snapshot_2026-08-26T04:10:00+00:00.json`
* `level=bronze/source=hdb/year=2026/month=08/day=26/hour=04/snapshot_2026-08-26T04:10:00+00:00.json`

---

## 4. Snapshot Metadata Envelope Schema

Each JSON file written to S3 is wrapped with execution metadata for lineage and monitoring:

```json
{
  "timestamp": "2026-08-26T04:10:00+00:00",
  "source": "lta",
  "poll_start": "2026-08-26T04:10:02.123456+00:00",
  "poll_end": "2026-08-26T04:10:06.789012+00:00",
  "pages": 4,
  "records_count": 1850,
  "value": [
    {
      "CarParkID": "1",
      "Area": "Marina",
      "Development": "Suntec City",
      "Location": "1.29375 103.85718",
      "AvailableLots": 245,
      "LotType": "C",
      "Agency": "LTA"
    }
  ]
}
```

---

## 5. Infrastructure & Deployment

Bronze pollers are deployed as lightweight Python 3.13 zip packages via Terraform:

* **Terraform Module**: [`infra/app/bronze_lambda/`](file:///c:/Users/sheng/OneDrive/Documents/Carpark-Availabilities-Data/infra/app/bronze_lambda/)
* **EventBridge Schedules**:
  * `lta_scheduler`: Triggers `lta_poller` every 10 minutes (`rate(10 minutes)`).
  * `hdb_scheduler`: Triggers `hdb_poller` every 10 minutes (`rate(10 minutes)`).
* **Lambda Environment Variables**:
  * `BUCKET_NAME`: Target S3 bucket.
  * `LEVEL`: `bronze`
  * `SOURCE`: `lta` or `hdb`
  * `ACCOUNT_KEY`: (For LTA poller only) LTA DataMall API Key.

---

## 6. Local Testing & Verification

To run a poller locally for testing:

```bash
# Set environment variables
export BUCKET_NAME="my-test-bucket"
export LEVEL="bronze"
export SOURCE="lta"
export ACCOUNT_KEY="your-lta-datamall-api-key"

# Invoke the handler with a mock event
uv run python -c "from packages.lta_poller.src.lta_poller.handler import handler; handler({}, None)"
```

