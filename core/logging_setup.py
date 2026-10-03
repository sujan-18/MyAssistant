"""Application logging configuration with bounded local log files."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(log_dir: Path, level: str = "INFO") -> logging.Logger:
    """Configure console and rotating file output once for the process."""
    logger = logging.getLogger("myassistant")
    logger.setLevel(getattr(logging, level))
    logger.propagate = False

    # Reconfiguration is useful for app restarts and isolated runtime paths.
    # Remove only handlers created by this function; retain caller-owned ones.
    for existing in tuple(logger.handlers):
        if getattr(existing, "_myassistant_owned", False):
            logger.removeHandler(existing)
            existing.close()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console._myassistant_owned = True  # type: ignore[attr-defined]
    file_handler = RotatingFileHandler(
        log_dir / "myassistant.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler._myassistant_owned = True  # type: ignore[attr-defined]
    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger


def shutdown_logging(logger: logging.Logger | None = None) -> None:
    """Remove and close only handlers owned by this logging setup."""
    target = logger or logging.getLogger("myassistant")
    for handler in tuple(target.handlers):
        if getattr(handler, "_myassistant_owned", False):
            target.removeHandler(handler)
            handler.close()
