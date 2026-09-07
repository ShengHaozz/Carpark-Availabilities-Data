# LTA Poller Package (`packages/lta_poller`)

The **LTA Poller Package** is an ingestion Lambda function that polls the Singapore Land Transport Authority (LTA) DataMall API every 10 minutes and writes timestamped raw JSON snapshot files to Amazon S3.

---

## 1. Overview & Ingestion Details

* **Target API**: LTA DataMall `CarParkAvailabilityv2` (`https://datamall2.mytransport.sg/ltaodataservice/CarParkAvailabilityv2?$skip={skip}`)
* **Schedule**: Triggered every 10 minutes via EventBridge Scheduler.
* **Pagination**: 500 records per page, paginating until an empty result set is reached (up to 10 pages).
* **Storage Location**: `s3://<BUCKET_NAME>/level=bronze/source=lta/year=<YYYY>/month=<MM>/day=<DD>/hour=<HH>/snapshot_<ISO_TIMESTAMP>.json`
* **Timestamp Flooring**: Snapshots are floored to 10-minute boundaries (`:00`, `:10`, `:20`, `:30`, `:40`, `:50`).

---

## 2. Environment Variables

| Variable | Required | Description |
| :--- | :--- | :--- |
| `ACCOUNT_KEY` | **Yes** | LTA DataMall API Account Key |
| `BUCKET_NAME` | **Yes** | Target S3 bucket name |
| `LEVEL` | No | Partition level (defaults to `bronze`) |
| `SOURCE` | No | Ingestion source name (defaults to `lta`) |

---

## 3. Local Development & Testing

```bash
# Linting and formatting
uv run ruff check packages/lta_poller/
uv run ruff format --check packages/lta_poller/

# Type checking
uv run mypy packages/lta_poller/
```
