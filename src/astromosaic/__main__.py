"""Launch the headless CLI in Python or from a frozen bundle."""

from multiprocessing import freeze_support

if __name__ == "__main__":
    freeze_support()

    from astromosaic.cli import main

    raise SystemExit(main())
