# Silver Cold Package (`packages/silver_cold`)

The **Silver Cold Package** is a daily batch reconciliation Lambda function that consolidates and cleans raw Bronze JSON snapshots from both LTA and HDB APIs into structured, columnar Apache Parquet files on S3.

---

## 1. Architecture & Execution Flow

* **Step Functions Step 1**: Invoked daily at `00:05 UTC` by EventBridge Scheduler.
* **Batch Window**: Processes 24 hours of Bronze data (`00:00` to `23:50` UTC).
* **Streaming Parquet Writes**: Uses `pyarrow.parquet.ParquetWriter` with **ZSTD** compression and streams hourly row groups to S3 to maintain low memory usage (< 512 MB).
* **Glue Catalog Integration**: Registered in AWS Glue (`silver.silver_cold`) with **Partition Projection** enabled.

---

## 2. Package Structure

```text
packages/silver_cold/src/silver_cold/
├── __init__.py      # Package export symbols
├── models.py        # Pydantic validation models (Datamall & HDB schemas)
└── handler.py       # Core transformation, join logic, PyArrow writer, and Lambda entrypoint
```

---

## 3. Environment Variables & Inputs

| Variable / Input | Required | Description |
| :--- | :--- | :--- |
| `S3_BUCKET` | **Yes** | Target S3 bucket name for Silver Parquet outputs |
| `date_str` | No | Target processing date in `YYYY-MM-DD` format (defaults to previous calendar day) |

---

## 4. Local Development & Testing

```bash
# Run silver_cold unit tests
uv run pytest tests/unit/test_silver_cold.py

# Linting and formatting
uv run ruff check packages/silver_cold/
uv run ruff format --check packages/silver_cold/

# Type checking
uv run mypy packages/silver_cold/
```
