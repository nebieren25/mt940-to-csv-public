"""
Configurable logging for web adapter.
Uses LOG_LEVEL (default INFO) and optional LOG_FILE (default: console only).
"""

import logging
import os
import sys


def configure_logging() -> None:
    """Configure root logger from ENV: LOG_LEVEL, LOG_FILE."""
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    log_file = os.environ.get("LOG_FILE")

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt=datefmt)

    root = logging.getLogger()
    root.setLevel(level)
    # Remove existing handlers to avoid duplicate logs
    for h in root.handlers[:]:
        root.removeHandler(h)

    handler: logging.Handler
    if log_file:
        handler = logging.FileHandler(log_file, encoding="utf-8")
    else:
        handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a logger for the given name (e.g. __name__)."""
    return logging.getLogger(name)
