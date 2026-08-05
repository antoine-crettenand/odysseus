"""Background QRunnable helpers for desktop workflow operations."""

from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


logger = logging.getLogger(__name__)


class _WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    progress = Signal(object)
    finished = Signal()


class _Worker(QRunnable):
    """Run a blocking workflow operation outside the Qt UI thread."""

    def __init__(self, function: Callable, *, with_progress: bool = False) -> None:
        super().__init__()
        self.function = function
        self.with_progress = with_progress
        self.signals = _WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            if self.with_progress:
                result = self.function(self.signals.progress.emit)
            else:
                result = self.function()
        except Exception as error:
            logger.exception("Desktop workflow operation failed")
            self.signals.error.emit(str(error) or error.__class__.__name__)
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()
