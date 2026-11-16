"""Run one immutable project snapshot on a Qt worker thread."""

import logging
from pathlib import Path
from threading import Event
from time import monotonic

from PySide6.QtCore import QObject, QThread, Signal

from astromosaic.core.job import JobContext, MosaicCancelled
from astromosaic.display import DisplayFrame, normalize_preview
from astromosaic.pipeline.mosaic import MosaicResult, PreviewFrame
from astromosaic.storage.project import MosaicProject, preview_project, render_project


class _ProjectJob[Result](QThread):
    progress = Signal(object, object)

    def __init__(self, project: MosaicProject, parent: QObject) -> None:
        super().__init__(parent)
        self.project = project
        self.result: Result | None = None
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
            self.result = self.perform(JobContext(self._cancel.is_set, self._progress))
        except MosaicCancelled:
            self.cancelled = True
        except (OSError, RuntimeError, ValueError) as error:
            self.error = str(error)
        except Exception as error:
            logging.getLogger(__name__).error("Unexpected job error (%s).", type(error).__name__)
            self.error = f"Unexpected job error ({type(error).__name__})."

    def perform(self, context: JobContext) -> Result:
        raise NotImplementedError


class MosaicJob(_ProjectJob[MosaicResult]):
    def __init__(self, project: MosaicProject, destination: Path, parent: QObject) -> None:
        super().__init__(project, parent)
        self.destination = destination

    def perform(self, context: JobContext) -> MosaicResult:
        return render_project(self.project, self.destination, context)


class PreviewJob(_ProjectJob[DisplayFrame]):
    proxy_ready = Signal(object)

    def _publish_proxy(self, preview: PreviewFrame) -> None:
        self.proxy_ready.emit(normalize_preview(preview))

    def perform(self, context: JobContext) -> DisplayFrame:
        frame = normalize_preview(preview_project(self.project, context, self._publish_proxy))
        context.check_cancelled()
        return frame
