"""Unified logging setup for local_ai scripts."""
from __future__ import annotations

import logging
import sys


def info(msg: str) -> None:
    """Write a simple informational message to stderr."""
    print(f"[info] {msg}", file=sys.stderr)


def warn(msg: str) -> None:
    """Write a simple warning message to stderr."""
    print(f"[warn] {msg}", file=sys.stderr)


def error(msg: str) -> None:
    """Write a simple error message to stderr."""
    print(f"[error] {msg}", file=sys.stderr)


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a logger that writes to stderr with a consistent format."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger
