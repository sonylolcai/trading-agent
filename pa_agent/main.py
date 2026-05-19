"""Application entry point for PA Agent (smoke target for task 1)."""
from __future__ import annotations

import logging
import sys

from PyQt6.QtWidgets import QApplication, QMainWindow

from pa_agent.app_context import AppContext
from pa_agent.util.logging import configure_logging

logger = logging.getLogger(__name__)


def _build_main_window(ctx: AppContext) -> QMainWindow:
    window = QMainWindow()
    window.setWindowTitle("PA Agent")
    window.resize(1280, 800)
    return window


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    argv = list(sys.argv if argv is None else argv)
    logger.info("PA Agent starting up")
    app = QApplication(argv)
    ctx = AppContext.bootstrap()
    logger.debug("AppContext bootstrapped")
    window = _build_main_window(ctx)
    window.show()
    logger.info("Main window shown")
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
