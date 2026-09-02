import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

FormatterFunc = Callable[[dict[str, Any], str], str]

_FORMATTER_REGISTRY: dict[str, FormatterFunc] = {}
_FALLBACK_FORMATTER: FormatterFunc | None = None


def register_formatter(*args: Any) -> Any:
    """Decorator or function to register a formatter for one or more event sources.

    Usage as a decorator:
        @register_formatter("aws.states")
        def format_sfn(event, region): ...

        @register_formatter("aws.cloudwatch", "aws.alarm")
        def format_alarm(event, region): ...

    Usage as a direct function call:
        register_formatter("aws.glue", format_glue)
    """
    if not args:
        raise ValueError("register_formatter requires at least one source or callable")

    # If called directly: register_formatter("aws.glue", fn)
    if callable(args[-1]) and len(args) > 1:
        sources = args[:-1]
        fn = args[-1]
        for source in sources:
            _FORMATTER_REGISTRY[str(source)] = fn
            logger.debug("Registered formatter '%s' for source '%s'", fn.__name__, source)
        return fn

    # If called as a decorator with no arguments (single callable): @register_formatter
    if len(args) == 1 and callable(args[0]):
        fn = args[0]
        _FORMATTER_REGISTRY[fn.__name__] = fn
        return fn

    # Called as decorator with sources: @register_formatter("aws.states")
    sources = args

    def decorator(fn: FormatterFunc) -> FormatterFunc:
        for source in sources:
            _FORMATTER_REGISTRY[str(source)] = fn
            logger.debug("Registered formatter '%s' for source '%s'", fn.__name__, source)
        return fn

    return decorator


def register_fallback_formatter(fn: FormatterFunc) -> FormatterFunc:
    """Decorator or function to register the default fallback formatter."""
    global _FALLBACK_FORMATTER
    _FALLBACK_FORMATTER = fn
    logger.debug("Registered fallback formatter '%s'", fn.__name__)
    return fn


def get_formatter(event: dict[str, Any]) -> FormatterFunc:
    """Resolves the appropriate formatter based on the event source."""
    source = event.get("source")

    # 1. Exact match in registry
    if source and source in _FORMATTER_REGISTRY:
        return _FORMATTER_REGISTRY[source]

    # 2. Fallback formatter
    if _FALLBACK_FORMATTER:
        return _FALLBACK_FORMATTER

    return lambda evt, reg: str(evt)
