from typing import Any, Protocol


class EventFormatter(Protocol):
    """Protocol for all event formatters."""

    def __call__(self, event: dict[str, Any], region: str) -> str:
        ...
