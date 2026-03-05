"""
utils/logging_config.py
AI Data Assistant — POC2

Centralised logging setup using loguru.
Call setup_logging() once at application startup.

Usage:
    from utils.logging_config import setup_logging
    setup_logging()
"""

import sys
import os
from loguru import logger
from config.settings import settings


def setup_logging() -> None:
    """
    Configure loguru for the application.
    - INFO+ to stderr (human-readable)
    - DEBUG+ to logs/app.log (rotating, JSON-friendly)
    """
    # Remove the default handler
    logger.remove()

    # Console handler — clean format
    logger.add(
        sys.stderr,
        level=settings.log_level.upper(),
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # File handler — full detail, rotating at 10 MB
    os.makedirs("logs", exist_ok=True)
    logger.add(
        "logs/app.log",
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        encoding="utf-8",
    )

    logger.info("Logging initialised")
