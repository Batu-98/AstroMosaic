"""Start the AstroMosaic desktop application."""

import os
import sys


def main() -> int:
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    from PySide6.QtWidgets import QApplication

    from astromosaic.ui.project_window import ProjectWindow

    use_gpu = "--cpu-preview" not in sys.argv[1:]
    app = QApplication([arg for arg in sys.argv if arg != "--cpu-preview"])
    app.setApplicationName("AstroMosaic")
    window = ProjectWindow(use_gpu=use_gpu)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
