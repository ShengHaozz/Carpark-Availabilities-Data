# Notifier Package (`packages/notifier`)

The **Notifier Package** is an alerting Lambda function that receives failure events from AWS Step Functions (`carpark-daily-pipeline`) and CloudWatch Alarms, formats informative markdown alerts, and broadcasts them to a designated **Telegram** chat.

---

## 1. Overview & Architecture

* **Trigger Source**: EventBridge Rule capturing Step Functions `Execution Status Change` (`FAILED`, `TIMED_OUT`, `ABORTED`).
* **Message Format**: Markdown-formatted Telegram messages including execution ARN, error cause, and execution timestamp.
* **Modular Formatters**: Uses specialized formatters in `src/notifier/formatters/` for Step Functions executions, Lambda invocations, and generic errors.

---

## 2. Environment Variables

| Variable | Required | Description |
| :--- | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | **Yes** | Telegram Bot API Token |
| `TELEGRAM_CHAT_ID` | **Yes** | Target Telegram Chat or Channel ID |

---

## 3. Local Development & Testing

```bash
# Run notifier unit tests
uv run pytest tests/unit/test_notifier.py tests/unit/test_notification_infra.py

# Linting and formatting
uv run ruff check packages/notifier/
uv run ruff format --check packages/notifier/

# Type checking
uv run mypy packages/notifier/
```
