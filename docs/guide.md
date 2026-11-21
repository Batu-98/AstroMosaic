# AstroMosaic Guide

AstroMosaic assembles calibrated, integrated, linear astrophotography panels into mosaics.

[Desktop quick start](#run-the-desktop-app) · [CLI quick start](#run-the-headless-cli) · [Develop and verify](#develop-and-verify) · [Project documentation](#project-documentation) · [README](../README.md)

## Features

- Import and export monochrome FITS, as well as mono and RGB linear TIFF and uncompressed XISF. Sky exports store float32 samples, world coordinate system (WCS) metadata, and coverage in one file. [FITS and TIFF workflow](adr/0006-dual-fits-and-tiff-workflow.md) · [XISF interchange](phase-5a.md)
- Reuse validated WCS or plate solve offline with local ASTAP or Gaia catalogs. Refine relative alignment and brightness for mono panels.
- Build sky mosaics on a TAN or ZEA grid and preview or export individual filter bands on the same grid.
- Save projects and relink moved panels. Edit sky masks, stitch the foreground separately, and preview or export either layer or a visual composition in the desktop app.

## Quick Start

AstroMosaic is in beta. Windows 11 x64 is the tested platform. Run these source setup commands from the repository root in PowerShell with CPython 3.13 and Poetry 2.5 installed. Portable Windows distribution awaits redistribution review and clean-machine validation. [Release process](windows-release.md)

### Run the Desktop App

```powershell
poetry env use 3.13
poetry sync --only main -E desktop
poetry run python -m astromosaic.ui
```

Choose **Add Panels**, set the mosaic grid, and save the project. Use the layer selector with **Build Preview** and **Export Mosaic** for sky, foreground, or composition. The **Layers** menu contains foreground alignment and composition controls. Both preview and export report progress and support cancellation. [Sky workflow](phase-3c.md#desktop-workflow) · [Mixed-panel workflow](phase-3e.md#desktop-workflow)

The panel control table opens in **Overview**. Choose **Optics**, **Files**, or **All properties** to compare additional columns. Double-click a weight, band, focal length, or pixel size to edit it. Use the **Sky** checkbox to include a panel in the sky layer. The desktop starts in dark mode. Choose **View → Theme** to switch between dark and light appearances. [Panel controls](phase-3b.md#panel-control-table)

Choose **TAN** or **ZEA** under **Mosaic Settings → Sky projection**. Set a new composition placement after changing the projection. [Sky projection](phase-5b.md)

Choose an available **Sky band** for a band-specific preview and export. Assign a filter label with **Panel Settings → Sky band override**. [Per-band workflow](phase-5c.md)

Choose **XISF mosaic** in the export dialog for a single file containing linear samples and coverage. **Add Panels** can reopen the exported sky image or another supported uncompressed XISF file. [XISF interchange](phase-5a.md)

For a mixed panel, choose **Panel → Propose Sky Mask** and review the overlay, or draw the mask with **More → Edit Sky Mask**. Use **Panel Settings** to override the foreground tag. [Mixed-panel workflow](phase-3d.md#desktop-workflow)

After **Layers → Align Foreground**, use **Foreground Alignment Details** to inspect paired panels, overlap support, correlation and rejection reasons. Select a pair and choose **Inspect Mask A** or **Inspect Mask B** to open its saved mask. [Foreground diagnostic results](phase-6.md#local-foreground-diagnostics-results)

Use **Tools → Plate Solve Settings** to choose and check the local ASTAP CLI and Gaia paths. For an ASTAP installation, select `astap_cli.exe` and the folder containing its catalog tiles. Fresh ASTAP settings use **Automatic**. Set the per-panel, per-attempt and optional batch limits there. Select **Plate Solve** and save the project to retain the results. **Panel → Plate Solve Details** shows effective hints, the catalog, the result of each attempt and measured regional errors when available. **Panel → Revalidate Plate Solution** requests a fresh catalog fit. [Desktop plate solving](phase-3b.md#desktop-plate-solving) · [Masked solve results](phase-6.md#local-masked-solve-results)

The **Command Panel** opens at startup and records summaries of desktop operations alongside CLI output. Use **Tools → Command Panel** to toggle it. The panel runs commands such as `project validate` and `project export` and supports render progress, cancellation and session history. [Command panel workflow](phase-4c.md#desktop-workflow)

On import or project reopen, **Panel Settings** automatically fills the available focal length and X and Y pixel sizes and shows the camera model. The readers use FITS keywords, TIFF EXIF/XMP and FITS-style metadata, and XISF instrument properties and FITS keywords. Per-panel edits override the corresponding file values. [Supported optics and units](phase-3b.md#panel-wcs-and-plate-solve-hints)

### Run the Headless CLI

For a CLI-only setup, install the core dependencies. The desktop setup also includes the CLI.

```powershell
poetry env use 3.13
poetry sync --only main
```

Run `smoke` to verify a tiny FITS projection and its coverage. To work with your own panels, put them in `data/` and create `output/` for exports. Both directories are ignored by Git.

```powershell
poetry run astromosaic smoke
New-Item -ItemType Directory -Path output -Force
poetry run astromosaic inspect data/panel-a.fits
poetry run astromosaic mosaic data/panel-a.fits data/panel-b.fits -o output/mosaic.fits --center 359.999 20 --size 1500 900 --scale 2 --progress
```

`inspect` reports the available camera and telescope names, focal length, pixel pitch, and image scale. Use inputs with compatible channel layouts and brightness scales within each render or filter band.

Set `--center`, `--size`, and `--scale` for your field. The `mosaic` and `project create` commands default to TAN. Pass `--projection ZEA` for a zenithal equal-area sky grid. Choose `.fits` for mono FITS, `.tif`/`.tiff` for TIFF, or `.xisf` for uncompressed XISF. Run `astromosaic mosaic --help` for filter and brightness declarations, blend weights, crop and rotation, and resource limits. [ZEA workflow](phase-5b.md) · [TIFF contract](phase-3a.md#sample-and-metadata-contract) · [XISF contract](phase-5a.md#scope)

Use `astromosaic project create` to save a sky project that the desktop can reopen. Use `astromosaic project validate` to check the saved sky layer. Use `astromosaic project export` to render a saved sky, foreground or composition layer. Project commands accept `--json` for scripts. Pass `--progress` to report export progress. [Project commands](phase-4a.md) · [Python and PowerShell batch examples](phase-4a.md#run-a-batch)

Use `astromosaic project bands` to list a saved project's filter groups. Pass `--band FILTER` to `project validate` or `project export` to work with one band on the saved grid. Add a `band` to each job in a batch list to export several bands. [Per-band workflow](phase-5c.md)

Use `astromosaic project fit-foreground` to evaluate terrain correspondences against a saved project's ground masks. Supply `--points` for manual correspondences or `--automatic` with the optional SIFT backend. [Manual terrain fit](phase-7.md#run-a-manual-terrain-fit) · [Automatic terrain fit](phase-7.md#run-the-automatic-terrain-fit)

Use `solve` to reuse a validated WCS or try the configured local ASTAP CLI followed by Gaia. New solutions must pass catalog match and RMS checks within the default 120-second panel budget. Install the catalogs and the ASTAP CLI separately. [Offline solver setup](phase-2.md#offline-solvers) · [Plate solve validation](phase-36-results.md)

This example uses a local Gaia catalog with approximate pointing and scale. Use the saved sidecar for the matching input panel and add `--refine` to fit relative shifts, stellar gains, and a background offset. Add `--background plane` to evaluate a plane. Pass any supplied sky mask to both commands.

```powershell
poetry install -E gaia
poetry run astromosaic solve data/panel-a.fits --gaia-catalog catalogs/gaia/stars-gaia.bin --hint 359.999 20 --scale 2 -o output/panel-a.wcs.json
poetry run astromosaic mosaic data/panel-a.fits data/panel-b.fits --wcs 1=output/panel-a.wcs.json -o output/refined.fits --center 359.999 20 --size 1500 900 --scale 2 --refine --progress
```

## Develop and Verify

```powershell
poetry sync -E desktop
poetry check --lock
poetry run pytest
poetry run python -m astromosaic smoke --spawn
poetry run ruff check src tests
poetry run mypy
poetry run python -m astromosaic.ui.viewport_probe --backend gpu
poetry run python -m astromosaic.ui.viewport_probe --backend cpu
```

The viewport command checks a small projection and exits. The [Phase 0 evidence](phase-0.md) includes build commands for both local bundles and a reproducible offline ASTAP trial. Update [development progress](../progression.md) and [open topics](../questions_open_topics.md) after meaningful changes.

## Project Documentation

| Document | Purpose |
| --- | --- |
| [AGENTS.md](../AGENTS.md) | Mandatory working rules for development agents. |
| [progression.md](../progression.md) | Current phase, concise work history, verification, and next action. |
| [questions_open_topics.md](../questions_open_topics.md) | Open decisions, problems, risks, and their resolutions. |
| [Python-first architecture](../astro_mosaic_python_first_architecture_en.md) | Active technical plan, revision 3.12, covering desktop workflows, astronomy validation, automation, formats, and [Phase 7 terrain panorama registration](../astro_mosaic_python_first_architecture_en.md#105-phase-7-delivery-stages). |
| [Phase 0 evidence](phase-0.md) | Platform matrix, fixture tolerances, probe results, and packaging procedure. |
| [Phase 1 FITS reference](phase-1.md) | CLI contract, fixtures, export checks, and measured resource use. |
| [Phase 2 astronomy reference](phase-2.md) | Offline catalog setup, WCS sidecars, masks, refinement, and acceptance evidence. |
| [Phase 3A linear TIFF](phase-3a.md) | Sample formats, WCS and coverage layout, interoperability limits, and Windows fixtures. |
| [Phase 3B projects and jobs](phase-3b.md) | Desktop setup, project save and relinking, worker progress, and cancellation. |
| [Phase 3C sky preview and export](phase-3c.md) | Preview controls, display backends, and comparison against reopened exports. |
| [Phase 3D sky masks](phase-3d.md) | Foreground tags, editable masks, and sky-only processing. |
| [Phase 3E foreground and composition](phase-3e.md) | Independent layers, shared horizon placement, seam controls, and layer exports. |
| [Phase 3F Windows package](phase-3f.md) | Reproducible package build, background acceptance checks, and clean-machine follow-up. |
| [Application test guide](application-tests.md) | Agent instructions and reproducible sky-only, wide-field, skewed and foreground fixture pairs. |
| [Phase 3.6 plan](phase-36.md) | ASTAP priority, automatic catalogs, match/RMS evidence, scale recovery, SIP/edge validation and total solve budgets. |
| [Phase 3.6 results](phase-36-results.md) | Windows plate-solving evidence, supported catalog modes and remaining checks. |
| [Phase 3.6A evidence](phase-36a.md) | Native capabilities, frozen contracts, TIFF EXIF/XMP import and the reference experiments. |
| [Phase 4B large mosaics](phase-4b.md) | Reproducible 12-panel benchmarks, memory measurements and independent FITS/TIFF checks. |
| [Phase 5A XISF interchange](phase-5a.md) | Linear XISF inputs, exports, supported metadata, and verification. |
| [Phase 5B sky projection](phase-5b.md) | Equal-area ZEA grids, saved settings, and wide-field geometry checks. |
| [Phase 5C per-band output](phase-5c.md) | Saved sky band assignments, individual previews and exports, and batch jobs. |
| [Phase 6 real-observation reliability](phase-6.md) | Reference data, foreground pairing, masked solving, ZEA previews, and Windows lifecycle and release acceptance. |
| [Phase 7 terrain panorama registration](phase-7.md) | Panorama research, manual and automatic terrain points, camera geometry, and real-data Windows acceptance. |
| [ADR-0001](adr/0001-python-first-baseline.md) | Records which architecture is active and which decisions remain unverified. |

All project Markdown, source comments, identifiers, logs, and default application text are written in English.
