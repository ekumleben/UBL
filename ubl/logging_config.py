"""Logging configuration for UBL. Call setup_logging() once at startup."""

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger with a standard format.

    Args:
        level: Log level name (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="[%(asctime)s] %(name)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
