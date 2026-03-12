import logging
import sys
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
from utils.constants import APP_NAME, CONFIG_DIR

def setup_logging(level=logging.INFO):
    """Set up robust, rotating file logging and console output."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = CONFIG_DIR / 'photovault.log'

    # Create root logger
    logger = logging.getLogger()
    logger.setLevel(level)

    # Remove any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Rotating File Handler (max 5MB per file, keep 3 old copies)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logging.info(f"--- {APP_NAME} Logging Started ---")
    return logger

def get_logger(name):
    """Get a named logger."""
    return logging.getLogger(name)
