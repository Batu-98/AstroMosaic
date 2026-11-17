# Phase 3B Projects and Background Jobs

## Desktop Workflow

Install the desktop extra and start the application.

```shell
poetry sync -E desktop
poetry run python -m astromosaic.ui
```

1. Use **Add Panels** to select calibrated mono FITS or mono/RGB TIFF inputs with a common channel layout. Use **Panel Settings** to set the blend weight and attach a saved WCS solution or a supplied FITS sky mask. The headless `solve` command can create a solution for a panel.

   Phase 3D adds foreground suggestions and masks stored in the project. [Editing and solving masked panels](phase-3d.md#desktop-workflow)
2. Use **Mosaic Settings** to enter the ICRS tangent point, output size and scale, and any rotation or crop. Declare a common filter and brightness scale when required by the inputs. Mono refinement can be disabled or can use stellar refinement with no background correction, an offset, or a plane.
3. Use **File → Save Project** to save a `.astromosaic` file. Reopen it with **File → Open Project**. If a source moved, select its row and choose **Relink**. The replacement must retain the original size and modification time. For a new revision, remove the old entry and add the new source. To update a mask or solution reference, browse to it again in **Panel Settings**.
4. Choose **Export Mosaic** and a new TIFF or FITS output filename. TIFF supports mono and RGB. FITS export supports mono. The progress bar reports output pixels. **Cancel Job** requests cancellation at the next engine checkpoint. The output is published only after a successful render. Closing the window during a job requests the same cancellation and waits asynchronously for cleanup.

The saved manifest holds the settings and paths needed to reproduce a job. Files on the same drive use relative paths, so moving a project and its referenced files together preserves the links. During a render the editor uses the snapshot from job start. [Sky preview workflow](phase-3c.md#desktop-workflow)

## Panel WCS and Plate Solve Hints

The panel list shows **Embedded**, **Sidecar**, **Missing**, **Invalid**, or **Unavailable** after a background inspection. The panel tooltip gives the reason. An attached sidecar is the project's selected WCS and is checked against the source and current sky mask. A stale sidecar reports **Invalid** and can be cleared or replaced in **Panel settings**.

In **Panel settings**, the focal length and effective X and Y pixel sizes show embedded values as placeholders. Enter edited values in millimeters and micrometers for the panel. Clear an edit to use the embedded value again. The manifest stores explicit edits in version 4 and still opens versions 1 through 3.

- Import reads numeric `FOCALLEN`, `XPIXSZ`, and `YPIXSZ` from FITS and from the FITS-style header in AstroMosaic TIFF. For binning greater than one, pixel size is accepted when the card comment identifies native pitch or effective pitch. For native pitch the reader applies the declared binning once. Ambiguous binned pitch requires an override or another usable scale hint. [N.I.N.A. FITS fields](https://nighttime-imaging.eu/docs/master/site/advanced/file_formats/fits.html) · [N.I.N.A. binning behavior](https://github.com/isbeorn/nina/blob/develop/RELEASE_NOTES.md) · [ARGOS FITS fields](https://perretjules.com/argos/docs/fits_headers.html)
- The headless `solve` command uses an explicit `--scale`, then a positive embedded `PIXSCALE`, then the scale derived from effective pitch and focal length. A project solve uses saved panel overrides when deriving that scale. Gaia receives a scalar derived hint when the two axis scales agree. ASTAP's field height uses the Y scale. Available blind solver paths can handle missing pointing or scale hints. [Optics and WCS tests](../tests/integration/test_panel_inspection.py)

On Windows 11 x64, the Phase 3.1A source and packaged CLIs solved an M13 reference copy with both local Gaia DR3 and hinted ASTAP using generated optical metadata equivalent to 1.0069 arcseconds per pixel. The copy retained its original bytes through each check. The native desktop regression checked the embedded hints, manual edit, restored project values, and WCS state after relinking on the secondary monitor. [M13 source provenance](phase-0.md#offline-astap-experiment) · [Desktop regression](../tests/integration/test_desktop_project.py)

## Verification

- Persistence tests check Unicode paths, project folder moves, all render settings and attachment references, fingerprint-matching relink, changed and missing file errors, unsupported schemas, and preservation of the original manifest after a failed atomic replacement. [Persistence tests](../tests/integration/test_project.py)
- The Qt workflow test adds FITS and TIFF panels, sets a blend weight, attaches a saved WCS and FITS sky mask, edits the grid, saves, and reopens the project. It relinks a moved source, checks progress from the worker, and verifies the GUI timer still runs during rendering. It cancels after the first real tile, checks temporary-file cleanup, retries to a valid TIFF output, and closes the window during another render to check asynchronous cleanup. The output history confirms that the saved attachments were used. The test supplies file dialog selections programmatically. [Desktop test](../tests/integration/test_desktop_project.py)
- Windows 11 x64 with PySide6 6.12 passed the workflow under the native Windows Qt platform plugin. Packaged installation and recovery checks remain in Phase 3F. [Delivery stages](../astro_mosaic_python_first_architecture_en.md#101-phase-3-delivery-stages)
