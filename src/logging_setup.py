"""Centralized application logging setup.

All debug, informational, and error messages produced by ``src`` are emitted
through the stdlib :mod:`logging` framework. This module wires up the root
logger so messages are written to a rotating log file stored under
``AppSettings.workspace_root``. Nothing is printed to the console.
"""

import logging
import logging.handlers
from pathlib import Path

DEFAULT_LOG_FILE = "app.log"
LOG_DIR_NAME = "logs"

_LOGGING_CONFIGURED = "_logging_configured"


def configure_logging(
    workspace_root: Path,
    *,
    filename: str = DEFAULT_LOG_FILE,
    level: int = logging.DEBUG,
) -> None:
    """Configure application logging once.

    Args:
        workspace_root: Root directory under which the ``logs`` folder and the
            log file are created.
        filename: Name of the log file created inside ``workspace_root/logs``.
        level: Logging threshold applied to the file handler.
    """
    workspace_root = Path(workspace_root)
    log_dir = workspace_root / LOG_DIR_NAME
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    # Configure only once per process to avoid duplicate handlers.
    if getattr(root, _LOGGING_CONFIGURED, False):
        return

    # Keep third-party loggers (khl, apscheduler, httpx2, ...) at WARNING so
    # their INFO chatter does not flood the console. Only errors surface.
    root.setLevel(level)

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
    )

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / filename,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Only our own ``src`` namespace gets a lowered threshold so its debug and
    # informational messages are also persisted to the log file.
    logging.getLogger("src").setLevel(level)

    setattr(root, _LOGGING_CONFIGURED, True)
