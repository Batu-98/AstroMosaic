"""Start the AstroMosaic desktop application."""

import os
import sys


def main() -> int:
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    from PySide6.QtWidgets import QApplication

    from astromosaic.ui.project_window import ProjectWindow

    app = QApplication(sys.argv)
    app.setApplicationName("AstroMosaic")
    window = ProjectWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
