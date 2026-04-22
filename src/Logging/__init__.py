"""Centralized application logging configuration."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from src.config import settings

APP_LOGGER_NAME = "mistria"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(lineno)s | %(message)s"

_base_logger = logging.getLogger(APP_LOGGER_NAME)


def _configure_logging() -> logging.Logger:
    if getattr(_base_logger, "_mistria_configured", False):
        return _base_logger

    os.makedirs(settings.logging.directory, exist_ok=True)

    formatter = logging.Formatter(LOG_FORMAT)
    log_level = getattr(logging, settings.logging.level, logging.INFO)

    file_handler = RotatingFileHandler(
        settings.logging.file_path,
        maxBytes=settings.logging.max_bytes,
        backupCount=settings.logging.backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(log_level)

    _base_logger.handlers.clear()
    _base_logger.setLevel(log_level)
    _base_logger.propagate = False
    _base_logger.addHandler(file_handler)
    _base_logger.addHandler(stream_handler)
    _base_logger._mistria_configured = True  # type: ignore[attr-defined]
    _base_logger.debug(
        "Configured application logging level=%s file=%s max_bytes=%s backup_count=%s",
        settings.logging.level,
        settings.logging.file_path,
        settings.logging.max_bytes,
        settings.logging.backup_count,
    )
    return _base_logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return the configured app logger or a child logger for the given module."""
    base_logger = _configure_logging()
    if not name:
        return base_logger

    normalized_name = name.removeprefix("src.")
    if normalized_name == APP_LOGGER_NAME or normalized_name.startswith(f"{APP_LOGGER_NAME}."):
        return logging.getLogger(normalized_name)
    return base_logger.getChild(normalized_name)


logger = get_logger()

__all__ = ["get_logger", "logger"]
