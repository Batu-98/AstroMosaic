"""Start the AstroMosaic desktop application."""

import os
import sys
from multiprocessing import freeze_support


def main() -> int:
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    from PySide6.QtWidgets import QApplication

    from astromosaic.ui.project_window import ProjectWindow

    cpu_preview = "--cpu-preview" in sys.argv[1:]
    second_screen = "--test-secondary-screen" in sys.argv[1:]
    app = QApplication(
        [
            sys.argv[0],
            *(
                arg
                for arg in sys.argv[1:]
                if arg not in {"--cpu-preview", "--test-secondary-screen"}
            ),
        ]
    )
    app.setApplicationName("AstroMosaic")
    window = ProjectWindow(use_gpu=not cpu_preview)
    if second_screen:
        secondary = next(
            (screen for screen in app.screens() if screen != app.primaryScreen()), None
        )
        if secondary is not None:
            area = secondary.availableGeometry()
            window.move(area.center() - window.rect().center())
    window.show()
    return app.exec()


if __name__ == "__main__":
    freeze_support()
    raise SystemExit(main())
