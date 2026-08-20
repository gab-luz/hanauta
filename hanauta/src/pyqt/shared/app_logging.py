from __future__ import annotations

import faulthandler
import logging
import sys
import threading
import traceback
from pathlib import Path


def _handler_targets_file(handler: logging.Handler, path: Path) -> bool:
    return (
        isinstance(handler, logging.FileHandler)
        and getattr(handler, "baseFilename", "") == str(path)
    )


def _handler_targets_stderr(handler: logging.Handler) -> bool:
    return (
        isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, logging.FileHandler)
        and getattr(handler, "stream", None) is sys.stderr
    )


def init_app_logging(app_name: str) -> tuple[Path, Path]:
    safe_name = "".join(
        ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(app_name).strip().lower()
    ) or "app"
    log_dir = Path.home() / ".local" / "state" / "hanauta" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{safe_name}.log"
    fault_file = log_dir / f"{safe_name}_fault.log"

    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    )
    console_formatter = logging.Formatter(
        f"[{safe_name}] %(levelname)s [%(name)s] %(message)s"
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if not any(_handler_targets_file(handler, log_file) for handler in root_logger.handlers):
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    if not any(_handler_targets_stderr(handler) for handler in root_logger.handlers):
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    logging.info("logging initialized for %s", safe_name)

    try:
        fault_stream = open(fault_file, "a", encoding="utf-8")
        faulthandler.enable(fault_stream, all_threads=True)
        logging.info("faulthandler enabled for %s", safe_name)
    except Exception:
        logging.exception("failed to enable faulthandler for %s", safe_name)

    def _log_excepthook(exc_type, exc_value, exc_tb) -> None:
        logging.critical(
            "unhandled exception:\n%s",
            "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
        )

    def _log_thread_excepthook(args: threading.ExceptHookArgs) -> None:
        logging.critical(
            "unhandled thread exception (%s):\n%s",
            getattr(args, "thread", None),
            "".join(
                traceback.format_exception(
                    args.exc_type, args.exc_value, args.exc_traceback
                )
            ),
        )

    sys.excepthook = _log_excepthook
    threading.excepthook = _log_thread_excepthook
    return log_file, fault_file
