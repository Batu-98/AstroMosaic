# Phase 3B Projects and Background Jobs

## Desktop Workflow

Install the desktop extra and start the application.

```shell
poetry sync -E desktop
poetry run python -m astromosaic.ui
```

1. Use **Add Panels** to select calibrated mono FITS or mono/RGB TIFF inputs with a common channel layout. Use **Panel Settings** to set the blend weight and attach a saved WCS solution or a supplied FITS sky mask. The headless `solve` command can create a solution for a panel.
2. Use **Mosaic Settings** to enter the ICRS tangent point, output size and scale, and any rotation or crop. Declare a common filter and brightness scale when required by the inputs. Mono refinement can be disabled or can use stellar refinement with no background correction, an offset, or a plane.
3. Use **File → Save Project** to save a `.astromosaic` file. Reopen it with **File → Open Project**. If a source moved, select its row and choose **Relink**. The replacement must retain the original size and modification time. For a new revision, remove the old entry and add the new source. To update a mask or solution reference, browse to it again in **Panel Settings**.
4. Choose **Export Mosaic** and a new TIFF or FITS output filename. TIFF supports mono and RGB. FITS export supports mono. The progress bar reports output pixels. **Cancel Job** requests cancellation at the next engine checkpoint. The output is published only after a successful render. Closing the window during a job requests the same cancellation and waits asynchronously for cleanup.

The saved manifest holds the settings and paths needed to reproduce a job. Files on the same drive use relative paths, so moving a project and its referenced files together preserves the links. During a render the editor uses the snapshot from job start. [Sky preview workflow](phase-3c.md#desktop-workflow)

## Verification

- Persistence tests check Unicode paths, project folder moves, all render settings and attachment references, fingerprint-matching relink, changed and missing file errors, unsupported schemas, and preservation of the original manifest after a failed atomic replacement. [Persistence tests](../tests/integration/test_project.py)
- The Qt workflow test adds FITS and TIFF panels, sets a blend weight, attaches a saved WCS and FITS sky mask, edits the grid, saves, and reopens the project. It relinks a moved source, checks progress from the worker, and verifies the GUI timer still runs during rendering. It cancels after the first real tile, checks temporary-file cleanup, retries to a valid TIFF output, and closes the window during another render to check asynchronous cleanup. The output history confirms that the saved attachments were used. The test supplies file dialog selections programmatically. [Desktop test](../tests/integration/test_desktop_project.py)
- Windows 11 x64 with PySide6 6.12 passed the workflow under the native Windows Qt platform plugin. Packaged installation and recovery checks remain in Phase 3F. [Delivery stages](../astro_mosaic_python_first_architecture_en.md#101-phase-3-delivery-stages)
