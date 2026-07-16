"""
Logging configuration.

Every signal check is always persisted to SQLite (bot.storage.log_signal_check)
regardless of verbosity — this only controls console/file text noise. Pass
quiet=True (or set LOG_LEVEL=WARNING) to silence routine INFO chatter while
still surfacing warnings and errors.
"""
import logging
import os

from . import config


def setup_logging(quiet: bool = False):
    os.makedirs(config.LOG_DIR, exist_ok=True)

    level = logging.WARNING if quiet else getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    file_handler = logging.FileHandler(config.LOG_FILE)
    file_handler.setLevel(logging.DEBUG)  # full history always on disk
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(fmt)
    root.addHandler(console_handler)

    return root
