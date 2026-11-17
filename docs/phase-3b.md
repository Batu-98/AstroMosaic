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

## Local Plate Solve Settings

Open **Tools → Plate Solve Settings** even with an empty project. The paths and database selection belong to the local Windows user and are restored when the application restarts.

1. For Gaia DR3, select an installed Seiza star catalog file. Select its matching blind index for panels without usable pointing and plate scale. Keep the catalog and index from the same Seiza bundle. The source desktop needs the optional `gaia` extra for this backend. [Seiza catalog setup](phase-2.md#catalog-setup-and-updates)
2. For ASTAP, select the ASTAP command-line executable and the folder containing the unpacked database tiles. Choose D05, D20, D50, or D80 to match the installed database. [ASTAP command line and databases](https://www.hnsky.org/astap.htm#astap_command_line)
3. Select **Check Paths** to see each backend's results. Seiza attempts to open the selected files. ASTAP checks the layout of a matching sample tile and requests the executable's version through its help command. Select **Save** to retain the paths and database. Check the paths again after moving the catalog or reconnecting its drive. [Path check tests](../tests/integration/test_solver_setup.py)

The settings can hold either backend or both. The offline chain tries Gaia DR3 before ASTAP after checking for usable WCS. Solve diagnostics retain the backend version and the Gaia catalog and index identities or the selected ASTAP database. [Offline solver order](adr/0005-offline-solver-chain.md) · [Desktop solve stages](../astro_mosaic_python_first_architecture_en.md#phase-31-desktop-plate-solving)

On Windows 11 x64, separate desktop processes checked and restored the real Gaia DR3 catalog and blind index and ASTAP CLI 2026.11.01 with D05 in an isolated settings store. The warning path identified missing files after reopening. The rebuilt CPU and OpenGL desktop bundles also checked missing paths and saved settings. [Desktop settings regression](../tests/integration/test_desktop_solver_settings.py) · [Packaged desktop checks](../packaging/check-windows-desktop.py)

## Desktop Plate Solving

1. Set the local solver paths and choose **Plate Solve** in the Panels controls. The job uses the selected sky layer inputs, each panel's optical hints and sky mask, and the saved backend settings. It shows how many panels need a WCS and reports progress as they finish. It reuses validated embedded WCS and sidecars.
2. For a saved project, the job writes new sidecars in a sibling folder such as `Night.astromosaic.wcs`. For an untitled project, choose a folder for the sidecars. Each completed solution is written atomically with its source and sky mask identity.
3. Read each attempted panel's result in the list and hover over the row to see the solver attempts and errors. **Cancel Job** finishes cleanup and attaches any completed results. Choose **Plate Solve** again to retry panels that still need a valid WCS. Preview and export use the attached WCS. Save the project to keep the links across sessions. [Desktop regression](../tests/integration/test_desktop_plate_solve.py)

The rebuilt Windows 11 x64 desktop checks passed on offscreen CPU and native OpenGL. The mixed project reused its embedded and attached WCS, skipped its foreground-only panel, and used real Gaia DR3 and ASTAP D05 on the M13 reference. Cancelling the second ASTAP attempt reaped the process and removed staging files while keeping the first solution. The retry used blind ASTAP after Gaia and hinted ASTAP failed with shifted pointing. The saved project reopened, preview and FITS export used the attached solutions, and source image hashes matched. [Packaged desktop checks](phase-3f.md#background-checks)

## Verification

- Persistence tests check Unicode paths, project folder moves, all render settings and attachment references, fingerprint-matching relink, changed and missing file errors, unsupported schemas, and preservation of the original manifest after a failed atomic replacement. [Persistence tests](../tests/integration/test_project.py)
- The Qt workflow test adds FITS and TIFF panels, sets a blend weight, attaches a saved WCS and FITS sky mask, edits the grid, saves, and reopens the project. It relinks a moved source, checks progress from the worker, and verifies the GUI timer still runs during rendering. It cancels after the first real tile, checks temporary-file cleanup, retries to a valid TIFF output, and closes the window during another render to check asynchronous cleanup. The output history confirms that the saved attachments were used. The test supplies file dialog selections programmatically. [Desktop test](../tests/integration/test_desktop_project.py)
- Windows 11 x64 with PySide6 6.12 passed the workflow under the native Windows Qt platform plugin. Packaged installation and recovery checks remain in Phase 3F. [Delivery stages](../astro_mosaic_python_first_architecture_en.md#101-phase-3-delivery-stages)
