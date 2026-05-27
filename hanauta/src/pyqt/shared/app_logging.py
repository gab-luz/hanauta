from __future__ import annotations

import faulthandler
import logging
import sys
import threading
import traceback
from pathlib import Path


def init_app_logging(app_name: str) -> tuple[Path, Path]:
    safe_name = "".join(
        ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(app_name).strip().lower()
    ) or "app"
    log_dir = Path.home() / ".local" / "state" / "hanauta" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{safe_name}.log"
    fault_file = log_dir / f"{safe_name}_fault.log"

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    has_file_handler = False
    for handler in root_logger.handlers:
        if (
            isinstance(handler, logging.FileHandler)
            and getattr(handler, "baseFilename", "") == str(log_file)
        ):
            has_file_handler = True
            break
    if not has_file_handler:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

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

