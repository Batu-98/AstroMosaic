# Desktop UI Architecture and Status

Reviewed on November 26, 2026 against application version `0.1.0b20`.

The desktop interface lives in `src/astromosaic/ui/` and uses PySide6 Qt Widgets. Python classes define the screen layouts. The shared palette and stylesheet live in `appearance.py`. The desktop starts with `python -m astromosaic.ui`, which creates a `QApplication` and opens `ProjectWindow`. [Desktop entry point](../src/astromosaic/ui/__main__.py) · [Architecture plan](../astro_mosaic_python_first_architecture_en.md#5-architecture-and-module-boundaries)

## Where the UI is defined

| Area | Implementation | Source |
| --- | --- | --- |
| Theme and shared styles | `apply_theme()` sets the Fusion style, system font, palette and inline Qt stylesheet. The styles cover headings, buttons, tables and job progress. Dark is the default. **View → Theme** switches between Dark and Light and saves the choice through `QSettings`. | [appearance.py](../src/astromosaic/ui/appearance.py) |
| Main workspace | `ProjectWindow` builds the menu bar and the vertical splitter, with the panel table above the preview. Layer selection, preview and export actions sit below the splitter. The Command Panel docks at the bottom. | [project_window.py](../src/astromosaic/ui/project_window.py) |
| Panel table | `PanelTable` uses `PanelTableModel` for panel properties and editable cells. The table offers Overview, Optics, Files and All properties views. | [panel_table.py](../src/astromosaic/ui/panel_table.py) |
| Preview | `SkyViewport` handles pan, zoom, display stretch and resolution scale. It displays the overview and 1:1 detail through the OpenGL or CPU view. The crop interaction and preview state live in adjacent modules. | [sky_viewport.py](../src/astromosaic/ui/sky_viewport.py) · [preview_crop.py](../src/astromosaic/ui/preview_crop.py) · [preview_state.py](../src/astromosaic/ui/preview_state.py) |
| Settings and diagnostics | Project, panel and composition settings are grouped in `project_settings.py`. Plate-solving settings and diagnostic details have their own dialogs. | [project_settings.py](../src/astromosaic/ui/project_settings.py) · [plate_solve_settings.py](../src/astromosaic/ui/plate_solve_settings.py) · [plate_solve_details.py](../src/astromosaic/ui/plate_solve_details.py) |
| Editors | The sky mask editor and terrain control point editor each own their layout and draft editing controls. | [mask_editor.py](../src/astromosaic/ui/mask_editor.py) · [terrain_editor.py](../src/astromosaic/ui/terrain_editor.py) |
| Command Panel | The dock runs AstroMosaic commands and shows output, progress and session command history. | [command_panel.py](../src/astromosaic/ui/command_panel.py) |

## Main window and processing

At roughly 2,000 lines, `project_window.py` is the largest UI module. It coordinates the project lifecycle, undo and redo, live preview, and worker results alongside the workspace layout and action wiring. [Project window](../src/astromosaic/ui/project_window.py) · [Desktop edit history decision](adr/0032-desktop-project-history.md)

Preview, plate solving and export use `QThread` jobs that call the processing layer, send progress to the UI and support cancellation. The processing pipeline and standalone CLI are Qt-free. [Desktop jobs](../src/astromosaic/ui/mosaic_job.py) · [Mosaic pipeline](../src/astromosaic/pipeline/mosaic.py) · [Headless CLI](../src/astromosaic/__main__.py)

## Current status and verification

The desktop supports panel import and project save or reopen, plate solving, sky and foreground preview, mask and terrain edits, crop, and scientific or photo export. Project and editor draft undo and redo are available in beta 20. [Desktop guide](guide.md#run-the-desktop-app) · [Phase 9](phase-9.md)

Four Windows offscreen source tests passed during the UI review. They covered panel table edits, theme persistence, the GPU preference, and preview resolution. [Panel and theme test](../tests/integration/test_panel_table.py) · [GPU preference tests](../tests/integration/test_gpu_settings.py) · [Resolution test](../tests/integration/test_preview_resolution.py)

The reviewed application files match those from commit `f7035a89ef478a8f9be7a2d5018cfaa419cd34bc`, the source of the locally verified Windows beta 20 package. The recorded package acceptance exercised scientific FITS, photo TIFF and mixed composition workflows with CPU and OpenGL. [Phase 9 Windows acceptance](phase-9.md#9d-windows-acceptance-results) · [Windows build record](windows-release.md#verification-status)
