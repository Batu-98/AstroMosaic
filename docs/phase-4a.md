# Phase 4A - Headless Project Automation

On 2026-11-18 the owner authorized starting Phase 4A from the verified local Windows baseline. Phase 3.6 acceptance still tracks real dense ASTAP catalogs and the 40′ M42 blind case. The clean Windows installation check is a separate gate. [Phase 3.6 evidence](phase-36-results.md#remaining-acceptance) · [Clean-machine check](phase-3f.md#pending-clean-machine-check)

## Scope and Acceptance

| Step | Scope | Windows 11 x64 acceptance |
| --- | --- | --- |
| Create and validate | Create a sky project from ordered FITS/TIFF panels and existing render options. Validate the saved sky selection through the same preparation used for export. | Open the created manifest using the desktop project's loader. Verify matching paths, weights, mask and WCS references, crop and refinement settings. Report missing inputs and occupied proposed output paths. Check JSON results and diagnostics on the installed CLI and the Qt-free portable launcher. |
| Export a saved layer | Export sky, foreground or composition through the shared project renderer using the saved grid, masks, alignment and composition settings and a new output path. | Reopen FITS and TIFF results independently. For a saved mixed project, compare pixels, coverage and applicable WCS with desktop exports. Stream tile progress and verify that interruption removes temporary output and allows a retry to the same path. |
| Scripted batches | Provide reproducible PowerShell and Python examples that run saved projects and read results, diagnostics and progress. | Run a batch containing FITS and TIFF projects through the installed CLI and portable launcher. Verify that the script can identify failed jobs, preserve completed exports and handle a missing input, an occupied output path and cancellation. |

Keep the existing command arguments and the manifest schema compatible. Use the shared solver and WCS sidecar policy, the saved resource limits and atomic publication for project jobs. Phase 4B uses this CLI for repeatable large-mosaic measurements. Phase 4C can run the same commands and consume the same progress and result records from the desktop. [Automation decision](adr/0016-local-automation.md) · [Phase 4 stages](../astro_mosaic_python_first_architecture_en.md#102-phase-4-delivery-stages)

## Create and Validate

Use a new project filename in an existing directory. The create command records source fingerprints and checks that the panels and supplied attachments can be opened. It can save unsolved panels for later plate solving. Supply an existing solution with `--wcs PANEL=PATH` and a FITS sky mask with `--sky-mask PANEL=PATH`. Panel numbers start at one. Pass `--projection ZEA` to save an equal-area sky grid. [ZEA workflow](phase-5b.md)

```powershell
poetry run astromosaic project create data/panel-a.fits data/panel-b.fits -o output/session.astromosaic --center 359.999 20 --size 1500 900 --scale 2
poetry run astromosaic project validate output/session.astromosaic -o output/session.fits --json
```

Validation opens the saved sky inputs and checks fingerprints, effective masks and WCS, the common channel layout and calibration, the output grid and the refinement prerequisites. With `-o`, it also checks the proposed output directory, path occupancy, format compatibility and preliminary byte limit. The render checks actual coverage, measures refinement and enforces the writer's exact limits. `astromosaic project create --help` lists the shared render settings.

## Prepare a Project Without the Desktop

Project preparation writes new `.astromosaic` files. The input project, original images and existing sidecars remain available for other runs. Use the same local ASTAP and Gaia flags as the single-panel `solve` command. `project solve` reuses valid WCS by default, respects saved masks and optical hints, and attaches qualified results directly to the new project. Repeat `--panel` to select one or more sky panels by their one-based numbers. Both WCS reuse checks and new solves are limited to those panels. `--revalidate` requests a new fit. Use `--progress --json` for panel counts and the ordered outcomes. Unsolved panels return an error and cancellation returns 130. In both cases keep the input project and retry at the same output path. New WCS sidecars are saved in an `astromosaic-wcs-*` folder beside the manifest.

```powershell
astromosaic project relink "Night.astromosaic" --panel '1=D:\Images\Panel A.fits' -o "Moved.astromosaic" --json
astromosaic project solve "Moved.astromosaic" --astap "C:\ASTAP\astap_cli.exe" --astap-catalog "C:\ASTAP\catalog" -o "Solved.astromosaic" --progress --json
astromosaic project export "Solved.astromosaic" -o "Sky.fits" --progress --json
```

For mixed projects, `project create --label-mask PANEL=PATH` imports a mono label raster at the source mask editor's grid dimensions. The source dimensions are used as-is up to a longest edge of 384 pixels. Larger sources use the same aspect-preserving rounded grid as the editor. Supply valid labels of `0` for unclassified, `1` for sky and `2` for foreground. Use `--foreground-only PANEL` to exclude a labeled ground panel from sky work. A binary `--sky-mask` remains available for sky-only masking. [Sky masks](phase-3d.md)

```powershell
astromosaic project align-foreground "Solved.astromosaic" -o "Aligned.astromosaic" --json
astromosaic project propose-placement "Aligned.astromosaic" -o "Placed.astromosaic" --json
astromosaic project export "Placed.astromosaic" --layer composition -o "Composition.tiff" --json
```

When the shared horizon lacks support, enter measured geometry using `project set-placement`. Supply `--offset X Y` and `--seam ROW` in sky-grid pixels. Optional `--rotation` in degrees, `--scale`, `--overlap` in percent and `--crop-bottom` in rows match the desktop composition fields. Use decimal notation for the two offsets and `--rotation=-1e-5` for a negative angle in scientific notation. The saved foreground masks and alignment determine the valid canvas. The [Phase 7 fit command](phase-7.md#run-a-manual-terrain-fit) reports measured ground control-point candidates. Saving and rendering those terrain poses is part of [Phase 7E](phase-7.md#7e-integrate-geometry-rendering-and-persistence).

Verify the headless pipeline with a moved source, a catalog solve, reopen and export. Exercise mask import, foreground alignment and both placement paths with masked observations. Verify output collisions, cancellation during solve and manifest publication, and cleanup before retry. The saved file is the publication boundary for each preparation command. [CLI regressions](../tests/portability/test_project_cli.py) · [Live desktop commands](phase-4c.md#control-the-active-project-without-dialogs)

## Export a Saved Layer

Use `project export` with a saved project and a new destination. It uses the same renderer and saved settings as the desktop. The default layer is `sky`. Use `--layer foreground` for the saved foreground alignment or `--layer composition` for the saved placement, crop and seam. Use FITS for mono, or TIFF or XISF for mono and RGB. [XISF workflow](phase-5a.md#use-the-format)

```powershell
poetry run astromosaic project export output/session.astromosaic -o output/sky.fits --progress --json
poetry run astromosaic project export output/mixed.astromosaic --layer composition -o output/composition.tiff --progress --json
```

Press Ctrl+C to cancel an active export. Windows automation can send `CTRL_BREAK_EVENT` to the running CLI's own console process group. The job checks cancellation through file publication and discards unfinished output. A cancelled job returns exit code 130 and can be retried at the same destination.

## Result Contract

`--json` writes one UTF-8 JSON object to stdout after the command runs. The object includes `schema_version` (1), `command`, `status` and `project`. Creation reports the panel count, and validation reports `panels`, `layer`, `width`, `height` and `channels`. Preparation reports include the output project path. `project solve` reports `reused` and `outcomes`. Its optional progress records use `stage` set to `solve`, with `completed_panels` and `total_panels`. Errors and interruptions include a `message`. Stderr diagnostics are newline-delimited JSON objects with `schema_version`, `event`, `level` and `message`.

Export reports include `layer` and `output`. A successful export also includes `width`, `height`, `covered_pixels`, `tiles`, `peak_reserved_bytes`, `rejected_coordinates` and `backend`. The rejection count covers unsuccessful mappings and layer clipping for evaluated panel candidates. `common_pixels` counts common coverage for compositions and is null for the other layers. `refinement` contains the fit report when available, including rejected overlap fits.

Selected-band validation and export reports include `band`. The `project bands` result lists labels and one-based member panel numbers. [Per-band workflow](phase-5c.md)

With `--progress`, export reports the first completed tile and each newly reached five-percent interval. Combine it with `--json` for one stderr record per update with `schema_version`, `event` set to `progress`, `stage` set to `render`, `completed_pixels` and `total_pixels`. The final stdout result and exit code confirm whether the file was published.

| Exit code | Meaning |
| --- | --- |
| 0 | The project was saved, the sky preflight passed or the export was published. |
| 1 | The command failed. The result status is `error`. |
| 2 | Argument parsing failed and printed CLI usage. |
| 130 | The command was interrupted. The result status is `cancelled`. |

## Run a Batch

Save a UTF-8 JSON job list beside the project files. Relative paths are resolved from the list's directory. Use a new destination for each export. The optional `layer` field defaults to `sky`. For sky jobs, the optional `band` field selects a filter label.

```json
[
  {"project": "session.astromosaic", "output": "batch-sky.fits"},
  {"project": "rgb.astromosaic", "output": "batch-rgb.tiff"},
  {"project": "mixed.astromosaic", "output": "batch-composition.tiff", "layer": "composition"},
  {"project": "filters.astromosaic", "output": "batch-OIII.tiff", "band": "O III"}
]
```

For a list saved as `output/jobs.json`, run either example from the project root. The PowerShell example uses PowerShell 7.

```powershell
poetry run python examples/export_batch.py output/jobs.json
pwsh -NoProfile -NonInteractive -File examples/export-batch.ps1 -Batch output/jobs.json -Python (poetry env info --executable)
```

To use the portable CLI, give the script its executable path. Keep the executable beside its `_internal` directory.

```powershell
$portableCli = 'dist/windows/astromosaic-cli/astromosaic-cli.exe'
python examples/export_batch.py output/jobs.json --cli $portableCli
pwsh -NoProfile -NonInteractive -File examples/export-batch.ps1 -Batch output/jobs.json -Cli $portableCli
```

Both scripts call `project export --json --progress` in order. They write one validated result per finished or cancelled job to stdout and forward live progress and diagnostics to stderr. Both streams use newline-delimited JSON. The scripts continue past ordinary export errors and keep completed files. Ctrl+C during a render lets the active CLI clean up and report cancellation before the batch ends.

| Batch exit code | Meaning |
| --- | --- |
| 0 | All jobs succeeded. |
| 1 | One or more exports failed, or the launcher or result contract failed. |
| 2 | The job list could not be read or parsed. |
| 130 | The batch was interrupted. Earlier exports were retained. |

[Python example](../examples/export_batch.py) · [PowerShell example](../examples/export-batch.ps1)

## Local Windows Results

All 147 native source tests passed, including OpenGL. The project CLI regressions verified manifest reopening, mask and WCS references, progress and diagnostic JSON, missing inputs, occupied paths, cancellation and retry. FITS and TIFF cancellation during the final flush left the destination free for retry. [CLI tests](../tests/portability/test_project_cli.py) · [Writer tests](../tests/integration/test_mosaic_job.py)

The installed Poetry console exported FITS with progress. The copied Qt-free CLI created, validated and exported FITS and Deflate RGB TIFF projects, with independent pixel, coverage and WCS checks. The portable console build is in ignored `.tooling/phase4a-export-windows/dist/astromosaic-cli/`. [Portable checker](../packaging/check-windows-cli.py)

For the packaged CLI and desktop CPU workflow, the same saved mixed FITS/TIFF project produced identical pixels, coverage and composition contributions. The sky WCS agreed at the sampled points within 1e-9 degrees. Independent reopening counted 3,347 sky pixels, 5,073 foreground pixels and 7,574 composition pixels. A source test also compares all three CLI exports against the actual desktop exports from a saved composition. [Desktop parity test](../tests/integration/test_desktop_project.py)

A targeted Windows console break after live progress returned exit code 130 for both the Python module and portable CLI. Both removed temporary files and published the expected FITS after retrying the same project and destination.

## Batch Acceptance

On the local Windows 11 x64 host, the Python and PowerShell 7.6.9 examples each passed against the installed CLI and a copied Qt-free portable CLI. All four runs parsed version 1 results and progress, preserved existing output, reported the missing input and occupied destination, continued to the RGB TIFF export, and reopened FITS and TIFF for pixel, coverage and WCS comparison.

A console break during the second job returned 130 in all four runs. The first export survived, the active temporary export was removed, and the remaining job stayed pending. Retrying through the same script published to the original destination. PowerShell handles the console callback in the parent process so the child can clean up and report its result.

Run the acceptance check from a Windows console with the development environment and PowerShell 7.

```powershell
poetry run python packaging/check-windows-batch.py dist/windows/astromosaic-cli
```

[Windows batch checker](../packaging/check-windows-batch.py)

## Next Steps

Phase 4A meets the local Windows acceptance criteria. Use the project CLI for the Phase 4B budget and quality measurements on the 12-panel 6000 × 4000 FITS, TIFF and mixed workloads. The separate fresh Windows installation check remains open. [Phase 4B reference](phase-4b.md)
