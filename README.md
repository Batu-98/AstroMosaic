# AstroMosaic v1

A Windows-first desktop application in development for assembling linear astronomical image panels into reproducible mosaics.

**Current state:** The Windows 11 x64 headless FITS reference can inspect and render calibrated monochrome panels with existing celestial WCS. Linux and macOS support is deferred.

## Start Here

| Document | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Mandatory working rules for development agents. |
| [progression.md](progression.md) | Current phase, concise work history, verification, and next action. |
| [questions_open_topics.md](questions_open_topics.md) | Open decisions, problems, risks, and their resolutions. |
| [Python-first architecture](astro_mosaic_python_first_architecture_en.md) | Active technical plan, revision 3.5, including milestones and acceptance gates. |
| [Phase 0 evidence](docs/phase-0.md) | Platform matrix, fixture tolerances, probe results, and packaging procedure. |
| [Phase 1 FITS reference](docs/phase-1.md) | CLI contract, fixtures, export checks, and measured resource use. |
| [ADR-0001](docs/adr/0001-python-first-baseline.md) | Records which architecture is active and which decisions remain unverified. |

All project Markdown, source comments, identifiers, logs, and default application text are written in English.

## Initial Product Boundary

The first headless reference processes calibrated, integrated, unstretched monochrome FITS panels from the same filter, using validated existing WCS, Gnomonic reprojection, weighted blending, and linear float32 FITS export. Robust solving, registration, and photometric matching follow in Phase 2; the full desktop workflow follows in Phase 3.

The user workflow provides first-class support for both FITS and linear TIFF panels, with a target benchmark of 12 panels at 6000 × 4000 pixels across both formats and optional camera RAW import deferred. AstroMosaic will be open source and use open-source components. [Dual format decision](docs/adr/0006-dual-fits-and-tiff-workflow.md) · [Product scope decision](docs/adr/0004-open-source-image-workflow.md)

The planned offline solve order is validated existing WCS, local Gaia DR3, hinted ASTAP, then blind ASTAP. [Solver decision](docs/adr/0005-offline-solver-chain.md)

The planned desktop workflow accepts panels that contain both sky and foreground. It proposes foreground tags and editable sky masks, stitches each layer independently, and supports automatic placement with manual seam, overlap, and crop controls. Plate solving applies to the sky layer. [Mixed-panel decision](docs/adr/0007-sky-and-foreground-mosaics.md)

The current lock uses CPython 3.13 with NumPy, SciPy, Astropy, SEP, and reproject. The `desktop` extra installs the PySide6 Essentials wheel.

## Run the Headless CLI

With a CPython 3.13 interpreter and Poetry 2.5 on your path, run these commands from the project root.

```shell
poetry env use 3.13
poetry sync --only main
poetry run astromosaic smoke
poetry run python -m astromosaic smoke --spawn
poetry run astromosaic inspect path/to/panel.fits
poetry run astromosaic mosaic data/panel-a.fits data/panel-b.fits -o output/mosaic.fits --center 359.999 20 --size 1500 900 --scale 2 --progress
```

`smoke` generates a tiny FITS fixture in a temporary directory and checks all 20 projected pixels and their coverage. `inspect` reads metadata from an uncompressed monochrome FITS primary image with optional binary `COVERAGE`. Put local inputs in `data/` and experimental outputs in `output/` to keep them outside version control. Create the output directory before rendering.

Set `--center`, `--size`, and `--scale` for your field. The `mosaic` command uses the supplied ICRS TAN grid and the panels' WCS. It writes linear float32 FITS pixels and a separate coverage image. Run `astromosaic mosaic --help` for filter and brightness declarations, blend weights, crop and rotation, and resource limits.

## Develop and Verify

```shell
poetry sync -E desktop
poetry check --lock
poetry run pytest
poetry run ruff check src tests
poetry run mypy
poetry run python -m astromosaic.ui.viewport_probe --backend gpu
poetry run python -m astromosaic.ui.viewport_probe --backend cpu
```

The viewport command checks a small projection and exits. The [Phase 0 evidence](docs/phase-0.md) includes build commands for both local bundles and a reproducible offline ASTAP trial. Update [development progress](progression.md) and [open topics](questions_open_topics.md) after meaningful changes.
