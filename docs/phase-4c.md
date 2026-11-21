# Phase 4C - Desktop command panel

## Scope and Acceptance

Expose the AstroMosaic CLI inside the desktop app. Verify that the panel opens at startup and records desktop operation summaries even when hidden. Verify that a saved project produces the same validation report and export through the panel and the standalone CLI. Exercise quoted Windows paths, session history, command errors, live render progress, cancellation after temporary output is created, and retry at the same destination. Verify that the desktop event loop continues to run during rendering and that closing the window waits for cleanup. Run the saved-project flow in a copied Windows desktop bundle. [Phase 4 delivery stages](../astro_mosaic_python_first_architecture_en.md#102-phase-4-delivery-stages) · [Worker decision](adr/0019-desktop-command-worker.md)

## Desktop Workflow

The **Command Panel** opens at startup. Toggle its visibility from **Tools → Command Panel**. The session log records project and panel changes, settings, and the start and outcome of desktop jobs, including failures and cancellations. Summaries continue to accumulate while the panel is hidden.

The panel shows the working folder. Relative paths start from the folder containing the open saved project. An untitled project uses the application's startup folder. Commands read saved data on disk, so save any unsaved edits you want a command to use. Press Enter or choose **Run**.

```text
--help
project validate "Saved project.astromosaic" --json
project export "Saved project.astromosaic" -o "Night run\Sky.fits" --json --progress
project export "Saved project.astromosaic" -o "Composition.tiff" --layer composition --json
```

Create the output folder before exporting. Choose a new destination. Use quotes around arguments containing spaces. Windows paths keep their backslashes. You can paste an AstroMosaic command beginning with `astromosaic`, `astromosaic-cli`, or either launcher name with `.exe`.

Use Up and Down in the command field to navigate the last 100 commands from this window and return to the current draft. The panel shows CLI output and desktop summaries in arrival order and keeps the latest 2,000 text blocks. The progress bar updates during rendering. Add `--json` for the versioned project report and `--progress` for CLI progress lines in the log. [CLI arguments and reports](phase-4a.md#result-contract)

Choose **Cancel Command** during an active job. When the renderer acknowledges cancellation, the job reports exit code 130 and removes incomplete output before the panel allows the next command. You can retry with the same output path. If the export already finished, the panel reports success and keeps the completed file. Hiding the panel keeps the job running. Closing the application requests cancellation and waits for its cleanup.

## Windows Verification

The source integration checks exercise startup visibility, logging while hidden, desktop job outcomes, command entry and history. They compare validation JSON and FITS export bytes with the standalone CLI and test cancellation, retry and window close while a Qt timer remains active. The copied-bundle checker uses a saved mixed FITS/TIFF project, compares sky and composition files with the desktop layer exports, exercises a nested CLI worker with `smoke --spawn`, and checks cancellation after progress begins. [Command panel test](../tests/integration/test_desktop_commands.py) · [Desktop project test](../tests/integration/test_desktop_project.py) · [Portable desktop checker](../packaging/check-windows-desktop.py)

### Local Windows Results

- All 155 tests passed on Windows 11 x64 with native OpenGL enabled. The command panel and other desktop test windows ran on the second display. Ruff lint and format, mypy, and the lock check passed.
- The copied desktop bundle passed both the offscreen CPU and native Windows OpenGL checks. The panel's sky FITS and composition TIFF matched the desktop layer exports byte for byte. The fixture had 3,347 sky coverage pixels and 7,574 composition coverage pixels. Cancelling during rendering returned 130 and removed temporary output in both runs.
- The windowed `AstroMosaic.exe` ran project validation and FITS export from the panel on the second display. The rebuilt portable console produced the same validation JSON and byte-identical FITS output for the 16 × 12 fixture with 126 covered pixels. The copied Qt-free console also passed its own worker, FITS, and TIFF checks. [Portable CLI checker](../packaging/check-windows-cli.py)

The locally tested bundles are in the ignored `.tooling/phase4c-windows/dist/` directory. The separate clean-machine distribution check remains open. [Distribution tracking](../questions_open_topics.md#q-005---application-licensing-and-distribution-model)
