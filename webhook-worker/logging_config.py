import logging
import os
from pathlib import Path

APP_NAME = "webhook-worker"
LOG_DIR = Path(os.getenv("LOG_DIR", "logs")) / APP_NAME
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def setup_logging() -> logging.Logger:
    """Configure logging to logs/<app_name>/ with level hierarchy (DEBUG, INFO, WARNING, ERROR, CRITICAL)."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, LOG_LEVEL, logging.INFO)
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    logger = logging.getLogger(APP_NAME)
    logger.setLevel(level)
    logger.handlers.clear()

    file_handler = logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    logger.addHandler(console_handler)

    return logger
