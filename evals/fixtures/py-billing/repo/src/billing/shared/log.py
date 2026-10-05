"""Structured logging. Uses structlog when installed, stdlib logging otherwise.

Always log key=value pairs (``log.info("event", payment_id=...)``); never format
amounts as decimals in logs, log ``cents``.
"""
import logging


class _KeyValueLogger:
    def __init__(self, name: str) -> None:
        self._log = logging.getLogger(name)

    def _emit(self, level: int, event: str, **kw) -> None:
        if self._log.isEnabledFor(level):
            pairs = " ".join("%s=%s" % (k, kw[k]) for k in sorted(kw))
            self._log.log(level, "%s %s", event, pairs)

    def info(self, event: str, **kw) -> None:
        self._emit(logging.INFO, event, **kw)

    def warning(self, event: str, **kw) -> None:
        self._emit(logging.WARNING, event, **kw)


def get_logger(name: str):
    try:
        import structlog  # type: ignore

        return structlog.get_logger(name)
    except ImportError:  # pragma: no cover - dev envs without deps
        return _KeyValueLogger(name)
