"""Run one immutable project snapshot on a Qt worker thread."""

import logging
from pathlib import Path
from threading import Event
from time import monotonic

from PySide6.QtCore import QObject, QThread, Signal

from astromosaic.core.job import JobContext, MosaicCancelled
from astromosaic.pipeline.mosaic import MosaicResult
from astromosaic.storage.project import MosaicProject, render_project


class MosaicJob(QThread):
    progress = Signal(object, object)

    def __init__(self, project: MosaicProject, destination: Path, parent: QObject) -> None:
        super().__init__(parent)
        self.project = project
        self.destination = destination
        self.result: MosaicResult | None = None
        self.error: str | None = None
        self.cancelled = False
        self._cancel = Event()
        self._last_update = 0.0

    def cancel(self) -> None:
        self._cancel.set()

    def _progress(self, done: int, total: int) -> None:
        now = monotonic()
        if done == total or now - self._last_update >= 0.05:
            self._last_update = now
            self.progress.emit(done, total)

    def run(self) -> None:
        try:
            self.result = render_project(
                self.project, self.destination, JobContext(self._cancel.is_set, self._progress)
            )
        except MosaicCancelled:
            self.cancelled = True
        except (OSError, RuntimeError, ValueError) as error:
            self.error = str(error)
        except Exception as error:
            logging.getLogger(__name__).error("Unexpected mosaic error (%s).", type(error).__name__)
            self.error = f"Unexpected rendering error ({type(error).__name__})."
