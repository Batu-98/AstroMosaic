# AstroMosaic

AstroMosaic assembles calibrated, linear astronomical images into reproducible mosaics. On Windows 11 x64, the desktop app can save and relink projects, edit sky and foreground masks, and preview and export either layer or a visual composition. The CLI supports offline plate solving, mono relative refinement and scripted exports. Linux and macOS support is deferred.

[Desktop quick start](#run-the-desktop-app) · [CLI quick start](#run-the-headless-cli) · [Windows release preparation](docs/windows-release.md)

## Start Here

| Document | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Mandatory working rules for development agents. |
| [progression.md](progression.md) | Current phase, concise work history, verification, and next action. |
| [questions_open_topics.md](questions_open_topics.md) | Open decisions, problems, risks, and their resolutions. |
| [Python-first architecture](astro_mosaic_python_first_architecture_en.md) | Active technical plan, revision 3.10, including desktop plate solving, engine revalidation, [Phase 3.6 plate solve reliability](astro_mosaic_python_first_architecture_en.md#phase-36-plate-solve-reliability), and [Phase 4 automation and large mosaics](astro_mosaic_python_first_architecture_en.md#102-phase-4-delivery-stages). |
| [Phase 0 evidence](docs/phase-0.md) | Platform matrix, fixture tolerances, probe results, and packaging procedure. |
| [Phase 1 FITS reference](docs/phase-1.md) | CLI contract, fixtures, export checks, and measured resource use. |
| [Phase 2 astronomy reference](docs/phase-2.md) | Offline catalog setup, WCS sidecars, masks, refinement, and acceptance evidence. |
| [Phase 3A linear TIFF](docs/phase-3a.md) | Sample formats, WCS and coverage layout, interoperability limits, and Windows fixtures. |
| [Phase 3B projects and jobs](docs/phase-3b.md) | Desktop setup, project save and relinking, worker progress, and cancellation. |
| [Phase 3C sky preview and export](docs/phase-3c.md) | Preview controls, display backends, and comparison against reopened exports. |
| [Phase 3D sky masks](docs/phase-3d.md) | Foreground tags, editable masks, and sky-only processing. |
| [Phase 3E foreground and composition](docs/phase-3e.md) | Independent layers, shared horizon placement, seam controls, and layer exports. |
| [Phase 3F Windows package](docs/phase-3f.md) | Reproducible package build, background acceptance checks, and clean-machine follow-up. |
| [Phase 3.6 plan](docs/phase-36.md) | ASTAP priority, automatic catalogs, match/RMS evidence, scale recovery, SIP/edge validation and total solve budgets. |
| [Phase 3.6 results](docs/phase-36-results.md) | Windows plate-solving evidence, supported catalog modes and remaining checks. |
| [Phase 3.6A evidence](docs/phase-36a.md) | Native capabilities, frozen contracts, TIFF EXIF/XMP import and the reference experiments. |
| [Phase 4B large mosaics](docs/phase-4b.md) | Reproducible 12-panel benchmarks, memory measurements and independent FITS/TIFF checks. |
| [Phase 5A XISF interchange](docs/phase-5a.md) | Linear XISF inputs, exports, supported metadata, and verification. |
| [Phase 5B sky projection](docs/phase-5b.md) | Equal-area ZEA grids, saved settings, and wide-field geometry checks. |
| [Phase 5C per-band output](docs/phase-5c.md) | Saved sky band assignments, individual previews and exports, and batch jobs. |
| [ADR-0001](docs/adr/0001-python-first-baseline.md) | Records which architecture is active and which decisions remain unverified. |

All project Markdown, source comments, identifiers, logs, and default application text are written in English.

## License

AstroMosaic is licensed under the [GNU General Public License version 3](LICENSE) (`GPL-3.0-only`).

## Initial Product Boundary

The headless reference processes calibrated, integrated, unstretched panels with matching channel layouts and brightness scales. It uses local astrometry, optional mono refinement, TAN or ZEA sky reprojection, and weighted blending. Float32 exports carry sky WCS and coverage in one file. Use FITS for mono or TIFF and XISF for mono and RGB.

The Windows workflow supports FITS and linear TIFF panels. The development benchmarks include 12-panel, 6000 × 4000-pixel FITS and TIFF cases. Camera RAW import is deferred. [Dual format decision](docs/adr/0006-dual-fits-and-tiff-workflow.md) · [Windows benchmarks](docs/phase-4b.md)

The offline solver reuses validated WCS, then tries local ASTAP before Gaia. New solutions require at least 15 catalog matches and comparable RMS, with supported TAN/SIP selection and one default 120-second panel deadline. The `gaia` extra adds Seiza. Catalogs and the external ASTAP CLI are installed separately. [Offline setup](docs/phase-2.md#offline-solvers) · [Phase 3.6 results](docs/phase-36-results.md)

Mixed FITS and TIFF panels can contribute selected sky pixels to plate solving, refinement, and mosaics. The desktop stitches foreground separately and provides layer placement, seam, overlap, and crop controls for visual composition. [Mixed-panel workflow](docs/phase-3e.md)

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

`smoke` generates a tiny FITS fixture in a temporary directory and checks all 20 projected pixels and their coverage. `inspect` reports available camera and telescope names, focal length, pixel pitch, embedded scale, and the scale derived from optics for mono FITS and mono/RGB TIFF or XISF panels. Put local inputs in `data/` and experimental outputs in `output/` to keep them outside version control. Create the output directory before rendering.

Set `--center`, `--size`, and `--scale` for your field. The `mosaic` and `project create` commands default to TAN. Pass `--projection ZEA` for a zenithal equal-area sky grid. Choose `.fits` for mono FITS, `.tif`/`.tiff` for TIFF, or `.xisf` for uncompressed XISF. Run `astromosaic mosaic --help` for filter and brightness declarations, blend weights, crop and rotation, and resource limits. [ZEA workflow](docs/phase-5b.md) · [TIFF contract](docs/phase-3a.md#sample-and-metadata-contract) · [XISF contract](docs/phase-5a.md#scope)

Use `astromosaic project create` to save a sky project that the desktop can reopen. Use `astromosaic project validate` to check the saved sky layer. Use `astromosaic project export` to render a saved sky, foreground or composition layer. Project commands accept `--json` for scripts. Pass `--progress` to report export progress. [Project commands](docs/phase-4a.md) · [Python and PowerShell batch examples](docs/phase-4a.md#run-a-batch)

Use `astromosaic project bands` to list a saved project's filter groups. Pass `--band FILTER` to `project validate` or `project export` to work with one band on the saved grid. Add a `band` to each job in a batch list to export several bands. [Per-band workflow](docs/phase-5c.md)

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

The panel control table opens in **Overview**. Choose **Optics**, **Files**, or **All properties** to compare additional columns. Double-click a weight, band, focal length, or pixel size to edit it. Use the **Sky** checkbox to include a panel in the sky layer. The desktop starts in dark mode. Choose **View → Theme** to switch between dark and light appearances. [Panel controls](docs/phase-3b.md#panel-control-table)

Add panels, set the mosaic grid, and save the project. Use the layer selector with **Build Preview** and **Export Mosaic** for sky, foreground, or composition. The **Layers** menu contains foreground alignment and composition controls. Both preview and export report progress and support cancellation. [Sky workflow](docs/phase-3c.md#desktop-workflow) · [Mixed-panel workflow](docs/phase-3e.md#desktop-workflow)

Choose **TAN** or **ZEA** under **Mosaic Settings → Sky projection**. Set a new composition placement after changing the projection. [Sky projection](docs/phase-5b.md)

Choose an available **Sky band** for a band-specific preview and export. Assign a filter label with **Panel Settings → Sky band override**. [Per-band workflow](docs/phase-5c.md)

Choose **XISF mosaic** in the export dialog for a single file containing linear samples and coverage. **Add Panels** can reopen the exported sky image or another supported uncompressed XISF file. [XISF interchange](docs/phase-5a.md)

For a mixed panel, choose **Panel → Propose Sky Mask** and review the overlay, or draw the mask with **More → Edit Sky Mask**. Use **Panel Settings** to override the foreground tag. [Mixed-panel workflow](docs/phase-3d.md#desktop-workflow)

Use **Tools → Plate Solve Settings** to choose and check the local ASTAP CLI and Gaia paths. Fresh ASTAP settings use **Automatic**. Set the per-panel, per-attempt and optional batch limits there. Select **Plate Solve** and save the project to retain the results. **Panel → Plate Solve Details** shows predicted distortion and measured regional errors. **Panel → Revalidate Plate Solution** requests a fresh catalog fit. [Desktop plate solving](docs/phase-3b.md#desktop-plate-solving)

Open **Tools → Command Panel** to run AstroMosaic CLI commands such as `project validate` and `project export` inside the desktop app. The panel shows command output and render progress and supports cancellation and session history. [Command panel workflow](docs/phase-4c.md#desktop-workflow)

On import or project reopen, **Panel Settings** automatically fills the available focal length and X and Y pixel sizes and shows the camera model. The readers use FITS keywords, TIFF EXIF/XMP and FITS-style metadata, and XISF instrument properties and FITS keywords. Per-panel edits override the corresponding file values. [Supported optics and units](docs/phase-3b.md#panel-wcs-and-plate-solve-hints)

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
