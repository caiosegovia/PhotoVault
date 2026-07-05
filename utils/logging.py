import logging
import sys
import threading
from pathlib import Path

from utils.constants import CONFIG_DIR


LOG_PATH = CONFIG_DIR / "photovault.log"


def setup_logging() -> None:
    """Configure file logging once for app diagnostics."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if any(getattr(handler, "baseFilename", None) == str(LOG_PATH) for handler in root.handlers):
        return

    root.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s"
    )
    try:
        file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        fallback = logging.StreamHandler(sys.stderr)
        fallback.setFormatter(formatter)
        root.addHandler(fallback)
    logging.getLogger("exifread").setLevel(logging.ERROR)

    def excepthook(exc_type, exc, tb):
        logging.getLogger("photovault").exception(
            "Unhandled exception",
            exc_info=(exc_type, exc, tb),
        )
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = excepthook

    if hasattr(threading, "excepthook"):
        def thread_hook(args):
            logging.getLogger("photovault").exception(
                "Unhandled thread exception in %s",
                args.thread.name,
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )

        threading.excepthook = thread_hook


def get_log_path() -> Path:
    return LOG_PATH
