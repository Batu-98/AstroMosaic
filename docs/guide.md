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

For a sky preview, choose **Add Panels → Plate Solve → Build Preview**. **Auto Frame** starts on in a new desktop project. Use **Use Preview Grid** to adopt a fitted sky grid for export, or set a grid in **Mosaic Settings**. Use the layer selector for sky, foreground, or composition. The **Layers** menu contains foreground alignment and composition controls. [Sky workflow](phase-3c.md#desktop-workflow) · [Mixed-panel workflow](phase-3e.md#desktop-workflow)

**Settings → GPU Acceleration** lets you switch preview acceleration on or off. It starts on and remembers your choice. AstroMosaic uses CPU sampling automatically when hardware OpenGL compute is unavailable. [Preview settings](phase-3c.md#desktop-workflow)

Use **Resolution Scale** in the preview toolbar to choose **25%**, **50%**, **75%**, or **100%** of the normal overview resolution. The default is **50%**. [Preview geometry](phase-3c.md#geometry-and-display)

The panel control table opens in **Overview**. Choose **Optics**, **Files**, or **All properties** to compare additional columns. Use **Tab** and **Shift+Tab** to leave the table and the arrow keys to move between cells. Press **F2** or double-click to edit a weight, band, focal length, or pixel size. Press **Space** on the **Sky** checkbox to toggle inclusion in the sky layer. The desktop starts in dark mode. Choose **View → Theme** to switch between dark and light appearances. [Panel controls](phase-3b.md#panel-control-table)

Choose **TAN** or **ZEA** under **Mosaic Settings → Sky projection**. Set a new composition placement after changing the projection. [Sky projection](phase-5b.md)

Choose an available **Sky band** for a band-specific preview and export. Panels without a filter label or declared common filter use the `Unspecified` band. Assign a known label with **Panel Settings → Sky band override**. [Per-band workflow](phase-5c.md)

Choose **XISF mosaic** in the export dialog for a single file containing linear samples and coverage. **Add Panels** can reopen the exported sky image or another supported uncompressed XISF file. [XISF interchange](phase-5a.md)

For a mixed panel, choose **Panel → Propose Sky Mask** and review the overlay, or draw the mask with **More → Edit Sky Mask**. Use **Panel Settings** to override the foreground tag. [Mixed-panel workflow](phase-3d.md#desktop-workflow)

After **Layers → Align Foreground → Match Translations**, use **Foreground Alignment Details** to inspect paired panels, overlap support, correlation and rejection reasons. Select a pair and choose **Inspect Mask A** or **Inspect Mask B** to open its saved mask. Use **Review Control Points** to mark or refine shared terrain and fit a translation or similarity. [Foreground diagnostics](phase-6.md#local-foreground-diagnostics-results) · [Control point editing](phase-7.md#review-and-edit-control-points-in-the-desktop)

Use **Tools → Plate Solve Settings** to choose and check the local ASTAP CLI and Gaia paths. For an ASTAP installation, select `astap_cli.exe` and the folder containing its catalog tiles. Fresh ASTAP settings use **Automatic**. Set the per-panel, per-attempt and optional batch limits there. Select **Plate Solve** and save the project to retain the results. **Panel → Plate Solve Details** shows effective hints, the catalog, the result of each attempt and measured regional errors when available. **Panel → Revalidate Plate Solution** requests a fresh catalog fit. [Desktop plate solving](phase-3b.md#desktop-plate-solving) · [Masked solve results](phase-6.md#local-masked-solve-results)

The **Command Panel** opens at startup and records summaries of desktop operations alongside CLI output. Use **Tools → Command Panel** to toggle it. The panel runs commands such as `project validate` and `project export` and supports render progress, cancellation and session history. [Command panel workflow](phase-4c.md#desktop-workflow)

Use **Edit → Undo** with **Ctrl+Z** and **Redo** with **Ctrl+Y** or **Ctrl+Shift+Z**. Sky Mask and Terrain Control Points use the same shortcuts for their drafts. Applying a draft creates one project edit. Save keeps the history for the open session. New, Open and Close clear it. Each history keeps up to 100 steps or 8 MiB of project or draft values and drops the oldest steps first. [Desktop edit history](phase-9.md)

Build a visual sky preview from RGB UInt16 TIFFs with supported profiles to enable **Export Photo Mosaic**. Use the **Photo** tab in **Mosaic Settings** for profile, exposure and brightness choices, and **Panel Settings → Photo** for per-panel profile or EV overrides. Choose **Preserve Tone** or **Use Preview Tone** to write a tagged 16-bit TIFF at the full preview grid resolution. [Photo workflow and CLI](phase-8.md#8c-photo-color-and-exposure-workflow)

With **Live Sky Preview** enabled, an opened sky preview refreshes as its inputs change. Zoom for **1:1** detail and use **Edit Crop** to adjust the automatic bounds on the full grid. **Apply Crop** saves the selected pixel rectangle in the project grid for the next export. [Framing locks and crop controls](phase-3c.md#adaptive-framing-and-interactive-crop)

Press **Tab** to focus a loaded mosaic preview, or click its image area. Use the arrow keys to pan, **+** or **=** to zoom in, **−** to zoom out, and **Home** to fit the view. **Tab** moves from the preview to **Fit View**. For exact crop coordinates with the keyboard, use **Mosaic Settings → Crop (x, y, width, height)**.

**Edit Crop** focuses the preview as soon as the full grid is ready. In this mode, the arrow keys move the rectangle one output pixel at a time, **Shift+arrows** adjust its right or bottom edge, and **Ctrl+arrows** pan the view. **Shift+Tab** reaches **Cancel**, **Apply Crop**, and **Use Auto Crop** in that order. Press **Space** to activate the focused button or **Esc** with the preview focused to discard the draft.

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

Use `project solve` to save a new project with its solved WCS attached. The preparation commands also relink moved inputs, align foreground masks, and save proposed or explicit composition placement. In the desktop Command Panel, `session save "Night.astromosaic"` saves the active project directly and `session export -o "Sky.fits"` uses its current settings. [Headless preparation](phase-4a.md#prepare-a-project-without-the-desktop) · [Live session controls](phase-4c.md#control-the-active-project-without-dialogs)

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
| [Application workflow reference](workflows.md) | Current desktop, CLI and batch flowcharts, including data validation, failure, cancellation and retry. |
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
| [Phase 8 color, photometry and optics](phase-8.md) | Photo export, input profiles, matrix color conversion, linked exposure and brightness. Later stages cover advanced fits and optics. |
| [Phase 9 desktop undo and redo](phase-9.md) | Planned project and editor history, saved-state behavior, worker results and Windows acceptance. |
| [ADR-0001](adr/0001-python-first-baseline.md) | Records which architecture is active and which decisions remain unverified. |

All project Markdown, source comments, identifiers, logs, and default application text are written in English.
