# Phase 4C - Desktop command panel

## Scope and Acceptance

Expose the AstroMosaic CLI inside the desktop app. Verify that the panel opens at startup and records desktop operation summaries even when hidden. Verify that a saved project produces the same validation report and export through the panel and the standalone CLI. Exercise quoted Windows paths, session history, command errors, live render progress, cancellation after temporary output is created, and retry at the same destination. Verify that the desktop event loop continues to run during rendering and that closing the window waits for cleanup. Run the saved-project flow in a copied Windows desktop bundle. [Phase 4 delivery stages](../astro_mosaic_python_first_architecture_en.md#102-phase-4-delivery-stages) · [Worker decision](adr/0019-desktop-command-worker.md)

## Desktop Workflow

The **Command Panel** opens at startup. Toggle its visibility from **Tools → Command Panel**. The session log records project and panel changes, settings, and the start and outcome of desktop jobs, including failures and cancellations. Summaries continue to accumulate while the panel is hidden.

The panel shows the working folder. Relative paths start from the folder containing the open saved project. An untitled project uses the application's startup folder. The shared CLI commands read saved data from disk. Use `session` commands for the active desktop project, including its unsaved edits. Press Enter or choose **Run**.

```text
--help
project validate "Saved project.astromosaic" --json
project export "Saved project.astromosaic" -o "Night run\Sky.fits" --json --progress
project export "Saved project.astromosaic" -o "Composition.tiff" --layer composition --json
```

Create the output folder before exporting. Choose a new destination. Use quotes around arguments containing spaces. Windows paths keep their backslashes. You can paste an AstroMosaic command beginning with `astromosaic`, `astromosaic-cli`, or either launcher name with `.exe`.

Use Up and Down in the command field to navigate the last 100 commands from this window and return to the current draft. The panel shows CLI output and desktop summaries in arrival order and keeps the latest 2,000 text blocks. The progress bar updates during rendering. Add `--json` for the versioned project report and `--progress` for CLI progress lines in the log. [CLI arguments and reports](phase-4a.md#result-contract)

Choose **Cancel Command** during an active job. When the renderer acknowledges cancellation, the job reports exit code 130 and removes incomplete output before the panel allows the next command. You can retry with the same output path. If the export already finished, the panel reports success and keeps the completed file. Hiding the panel keeps the job running. Closing the application requests cancellation and waits for its cleanup.

## Control the Active Project Without Dialogs

The original panel exposed saved-project CLI commands. First save and Save As required a file picker, opening or closing an edited project could wait for confirmation, and the standalone export read the earlier saved settings. Enter `session --help` in the Command Panel to use explicit destinations and actions on the live project.

| Workflow | Session command |
| --- | --- |
| Show the path, panel count and unsaved state | `session status` |
| Start an untitled project or open a manifest | `session new` or `session open "Night.astromosaic"` |
| Add panels or repair a moved source | `session add "Panel A.fits" "Panel B.fits"` or `session relink 1 "Moved Panel.fits"` |
| Save the current contents | `session save "Night.astromosaic"` for the first save or a new path, then `session save` for that file |
| Preview, solve or export the active project | `session preview`, `session solve`, or `session export -o "Sky.fits" --layer sky` |
| Choose or adopt the sky preview grid | `session preview --grid auto`, `session preview --grid saved`, or `session use-preview-grid` |
| Close the window | `session close` |

A named save uses a new file unless you pass `--replace`. New, open and close require a saved project or an explicit `--discard` for unsaved changes. The panel reports invalid arguments, an occupied destination, a failed relink or an unsaved project in the log. An export uses the active snapshot and accepts `--layer` and `--band`. Preview, solving and rendering use the desktop job and **Cancel Job**. `session solve --panel 2` revalidates an individual sky panel with the saved solver settings. For scripts that process files without opening the desktop, use the [project commands](phase-4a.md#prepare-a-project-without-the-desktop).

Exercise the workflow with a Unicode panel path, a missing project, an occupied save path, and a changed render crop that has yet to be saved. Verify that commands report their outcomes without invoking a dialog, that failed commands preserve the working project, and that export uses the new crop. Reopen the saved result, relink a moved source matching its fingerprint, save and close. Run the case through the Windows bundle as well as the [desktop regression](../tests/integration/test_desktop_commands.py).

## Windows Verification

The source integration checks exercise startup visibility, logging while hidden, desktop job outcomes, command entry and history. They compare validation JSON and FITS export bytes with the standalone CLI and test cancellation, retry and window close while a Qt timer remains active. The copied-bundle checker uses a saved mixed FITS/TIFF project, compares sky and composition files with the desktop layer exports, exercises a nested CLI worker with `smoke --spawn`, and checks cancellation after progress begins. [Command panel test](../tests/integration/test_desktop_commands.py) · [Desktop project test](../tests/integration/test_desktop_project.py) · [Portable desktop checker](../packaging/check-windows-desktop.py)

### Local Windows Results

- All 155 tests passed on Windows 11 x64 with native OpenGL enabled. The command panel and other desktop test windows ran on the second display. Ruff lint and format, mypy, and the lock check passed.
- The copied desktop bundle passed both the offscreen CPU and native Windows OpenGL checks. The panel's sky FITS and composition TIFF matched the desktop layer exports byte for byte. The fixture had 3,347 sky coverage pixels and 7,574 composition coverage pixels. Cancelling during rendering returned 130 and removed temporary output in both runs.
- The windowed `AstroMosaic.exe` ran project validation and FITS export from the panel on the second display. The rebuilt portable console produced the same validation JSON and byte-identical FITS output for the 16 × 12 fixture with 126 covered pixels. The copied Qt-free console also passed its own worker, FITS, and TIFF checks. [Portable CLI checker](../packaging/check-windows-cli.py)

The locally tested bundles are in the ignored `.tooling/phase4c-windows/dist/` directory. The separate clean-machine distribution check remains open. [Distribution tracking](../questions_open_topics.md#q-005---application-licensing-and-distribution-model)
