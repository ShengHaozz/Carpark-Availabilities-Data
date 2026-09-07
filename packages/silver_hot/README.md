# Silver Hot Package (`packages/silver_hot`)

The **Silver Hot Package** is reserved for near real-time streaming ingestion and micro-batch processing of carpark availabilities into low-latency analytical stores (e.g. DynamoDB or direct hot cache).

---

## Status & Roadmap

* **Current Status**: Scaffolded for future near real-time processing capabilities.
* **Production Pipeline**: Batch processing is currently handled by [`packages/silver_cold`](../silver_cold) via daily Step Functions execution.
