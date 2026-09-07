# HDB Poller Package (`packages/hdb_poller`)

The **HDB Poller Package** is an ingestion Lambda function that polls the Data.gov.sg HDB Carpark Availability API every 10 minutes and writes timestamped raw JSON snapshot files to Amazon S3.

---

## 1. Overview & Ingestion Details

* **Target API**: Data.gov.sg `carpark-availability` (`https://api.data.gov.sg/v1/transport/carpark-availability`)
* **Schedule**: Triggered every 10 minutes via EventBridge Scheduler.
* **Payload**: Single JSON array containing `carpark_number` and `carpark_info` (`lots_available`, `total_lots`, `lot_type`).
* **Storage Location**: `s3://<BUCKET_NAME>/level=bronze/source=hdb/year=<YYYY>/month=<MM>/day=<DD>/hour=<HH>/snapshot_<ISO_TIMESTAMP>.json`
* **Timestamp Flooring**: Snapshots are floored to 10-minute boundaries (`:00`, `:10`, `:20`, `:30`, `:40`, `:50`).

---

## 2. Environment Variables

| Variable | Required | Description |
| :--- | :--- | :--- |
| `BUCKET_NAME` | **Yes** | Target S3 bucket name |
| `LEVEL` | No | Partition level (defaults to `bronze`) |
| `SOURCE` | No | Ingestion source name (defaults to `hdb`) |

---

## 3. Local Development & Testing

```bash
# Linting and formatting
uv run ruff check packages/hdb_poller/
uv run ruff format --check packages/hdb_poller/

# Type checking
uv run mypy packages/hdb_poller/
```
