# AstroMosaic v1

A Windows-first desktop application in development for assembling linear astronomical image panels into reproducible mosaics.

**Current state:** The Windows 11 x64 desktop app can save and relink projects, edit sky and foreground masks, and preview and export each layer or a visual composition. The CLI supports offline solving and mono relative refinement. Linux and macOS support is deferred.

## Start Here

| Document | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Mandatory working rules for development agents. |
| [progression.md](progression.md) | Current phase, concise work history, verification, and next action. |
| [questions_open_topics.md](questions_open_topics.md) | Open decisions, problems, risks, and their resolutions. |
| [Python-first architecture](astro_mosaic_python_first_architecture_en.md) | Active technical plan, revision 3.6, including [Phase 3A–3F](astro_mosaic_python_first_architecture_en.md#101-phase-3-delivery-stages). |
| [Phase 0 evidence](docs/phase-0.md) | Platform matrix, fixture tolerances, probe results, and packaging procedure. |
| [Phase 1 FITS reference](docs/phase-1.md) | CLI contract, fixtures, export checks, and measured resource use. |
| [Phase 2 astronomy reference](docs/phase-2.md) | Offline catalog setup, WCS sidecars, masks, refinement, and acceptance evidence. |
| [Phase 3A linear TIFF](docs/phase-3a.md) | Sample formats, WCS and coverage layout, interoperability limits, and Windows fixtures. |
| [Phase 3B projects and jobs](docs/phase-3b.md) | Desktop setup, project save and relinking, worker progress, and cancellation. |
| [Phase 3C sky preview and export](docs/phase-3c.md) | Preview controls, display backends, and comparison against reopened exports. |
| [Phase 3D sky masks](docs/phase-3d.md) | Foreground tags, editable masks, and sky-only processing. |
| [Phase 3E foreground and composition](docs/phase-3e.md) | Independent layers, shared horizon placement, seam controls, and layer exports. |
| [ADR-0001](docs/adr/0001-python-first-baseline.md) | Records which architecture is active and which decisions remain unverified. |

All project Markdown, source comments, identifiers, logs, and default application text are written in English.

## License

AstroMosaic is licensed under the [GNU General Public License version 3](LICENSE) (`GPL-3.0-only`).

## Initial Product Boundary

The headless reference processes calibrated, integrated, unstretched panels with matching channel layouts and brightness scales. It uses local astrometry, optional mono refinement, Gnomonic reprojection, and weighted blending. Float32 exports carry WCS and coverage in the same FITS or TIFF file. RGB mosaics export to TIFF. The desktop workflow follows in Phase 3B–3F.

The user workflow provides first-class support for both FITS and linear TIFF panels, with a target benchmark of 12 panels at 6000 × 4000 pixels across both formats and optional camera RAW import deferred. AstroMosaic will be open source and use open-source components. [Dual format decision](docs/adr/0006-dual-fits-and-tiff-workflow.md) · [Product scope decision](docs/adr/0004-open-source-image-workflow.md)

The offline solve order is validated existing WCS, local Gaia DR3, hinted ASTAP, then blind ASTAP. The `gaia` extra adds Seiza. Catalogs and the external ASTAP executable are installed separately. [Offline setup](docs/phase-2.md#offline-solvers)

Mixed FITS and TIFF panels can contribute selected sky pixels to plate solving, refinement, and mosaics. The next desktop stage adds independent foreground stitching and layer placement, seam, overlap, and crop controls. [Mixed-panel decision](docs/adr/0007-sky-and-foreground-mosaics.md)

The current lock uses CPython 3.13 with NumPy, SciPy, Astropy, SEP, reproject, tifffile, and imagecodecs. The `desktop` extra installs the PySide6 Essentials wheel.

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

`smoke` generates a tiny FITS fixture in a temporary directory and checks all 20 projected pixels and their coverage. `inspect` reads metadata from mono FITS and mono/RGB TIFF panels. Put local inputs in `data/` and experimental outputs in `output/` to keep them outside version control. Create the output directory before rendering.

Set `--center`, `--size`, and `--scale` for your field. The `mosaic` command uses the supplied ICRS TAN grid and the panels' WCS. Choose `.fits` for mono FITS or `.tif`/`.tiff` for mono or RGB TIFF. Run `astromosaic mosaic --help` for filter and brightness declarations, blend weights, crop and rotation, and resource limits. [TIFF sample and metadata contract](docs/phase-3a.md#sample-and-metadata-contract)

Use `solve` for panels that need a WCS. This example uses a separately installed local Gaia catalog with approximate pointing and scale. Use the saved sidecar for the matching input panel and add `--refine` to fit relative shifts, stellar gains, and a background offset. Add `--background plane` to evaluate a plane. Pass any supplied sky mask to both commands. [Catalog setup and diagnostics](docs/phase-2.md#offline-solvers)

```shell
poetry install -E gaia
poetry run astromosaic solve data/panel-a.fits --gaia-catalog catalogs/gaia/stars-gaia.bin --hint 359.999 20 --scale 2 -o output/panel-a.wcs.json
poetry run astromosaic mosaic data/panel-a.fits data/panel-b.fits --wcs 1=output/panel-a.wcs.json -o output/refined.fits --center 359.999 20 --size 1500 900 --scale 2 --refine --progress
```

## Run the Desktop App

```shell
poetry sync -E desktop
poetry run python -m astromosaic.ui
```

Add panels, set the mosaic grid, and save the project. Use the layer selector with **Build Preview** and **Export Mosaic** for sky, foreground, or composition. The **Layers** menu contains foreground alignment and composition controls. Both preview and export report progress and support cancellation. [Sky workflow](docs/phase-3c.md#desktop-workflow) · [Mixed-panel workflow](docs/phase-3e.md#desktop-workflow)

For a mixed panel, choose **Panel → Propose Sky Mask** and review the overlay, or draw the mask with **Edit Sky Mask**. Use **Panel Settings** to override the foreground tag. [Mixed-panel workflow](docs/phase-3d.md#desktop-workflow)

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
