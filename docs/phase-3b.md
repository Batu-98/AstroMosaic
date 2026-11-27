# Phase 3B Projects and Background Jobs

## Desktop Workflow

Install the desktop extra and start the application.

```shell
poetry sync -E desktop
poetry run python -m astromosaic.ui
```

1. Use **Add Panels** to select calibrated mono FITS or mono/RGB TIFF or XISF inputs with a common channel layout. Use **Panel Settings** to set the blend weight and attach a saved WCS solution or a supplied FITS sky mask. The headless `solve` command can create a solution for a panel.

   Phase 3D adds foreground suggestions and masks stored in the project. [Editing and solving masked panels](phase-3d.md#desktop-workflow)
2. Use **Mosaic Settings** to enter the ICRS tangent point, output size and scale, and any rotation or crop. Declare a common filter and brightness scale when required by the inputs. Mono refinement can be disabled or can use stellar refinement with no background correction, an offset, or a plane.
3. Use **File → Save Project** to save a `.astromosaic` file. Reopen it with **File → Open Project**. If a source moved, select its row and choose **More → Relink**. The replacement must retain the original size and modification time. For a new revision, remove the old entry and add the new source. To update a mask or solution reference, browse to it again in **Panel Settings**.
4. Choose **Export Mosaic** and a new TIFF or FITS output filename. TIFF supports mono and RGB. FITS export supports mono. The progress bar reports output pixels. **Cancel Job** requests cancellation at the next engine checkpoint. The output is published only after a successful render. Closing the window during a job requests the same cancellation and waits asynchronously for cleanup.

The saved manifest holds the settings and paths needed to reproduce a job. Files on the same drive use relative paths, so moving a project and its referenced files together preserves the links. During a render the editor uses the snapshot from job start. [Sky preview workflow](phase-3c.md#desktop-workflow)

## Panel Control Table

The table shows one row per project panel above the mosaic preview. Drag the divider to resize these two areas. **Overview** groups file names, sky inclusion, WCS, blend weight, band, focal length, camera, image dimensions, and the latest solve result. Choose **Optics** to compare effective and embedded measurements, **Files** to inspect references and source details, or **All properties** for every available column. Missing measurements appear as a dash.

Double-click a weight, band, focal length or pixel size to edit the selected panel. Clear a band or optical edit to restore its inherited value. Toggle **Sky** to include or skip the panel in the sky layer. **Panel Settings** contains the foreground override and attachments. **More** contains relinking, sky mask editing, and panel removal. Save the project to retain panel edits.

The default theme is **Dark**. Choose **View → Theme → Light** or **Dark** to change the application palette. AstroMosaic stores this choice in the local user's preferences. Both themes use the same preview stretch and export settings.

## Panel WCS and Plate Solve Hints

The WCS column shows **Embedded**, **Sidecar**, **Missing**, **Invalid**, or **Unavailable** after a background inspection. The panel tooltip gives the reason. An attached sidecar is the project's selected WCS and is checked against the source and current sky mask. A stale sidecar reports **Invalid** and can be cleared or replaced in **Panel settings**.

**Panel settings** fills the focal length in millimeters and effective X and Y pixel sizes in micrometers as background inspection finishes. It also shows the camera model when available. The tooltip identifies the embedded value. Edit a field to override it for the panel, or clear an edit and accept the dialog to use the file value again. Manifest versions 4 through 6 store explicit edits. Version 5 adds a saved projection and version 6 adds saved sky band overrides. AstroMosaic opens versions 1 through 6. [Projection persistence](phase-5b.md#scope) · [Band persistence](phase-5c.md#scope)

- FITS, AstroMosaic TIFF, and XISF with FITS keywords share `FOCALLEN`, `XPIXSZ`, and `YPIXSZ`. For binned data, explicit comments identifying native or effective pitch take precedence. The reader multiplies native pitch by the declared binning once and treats the pitch from N.I.N.A. 1.10 and later and MaxIm DL as effective when the comment is unspecified. Ambiguous binned pitch remains unset. [N.I.N.A. FITS fields](https://nighttime-imaging.eu/docs/master/site/advanced/file_formats/fits.html) · [N.I.N.A. release notes](https://github.com/isbeorn/nina/blob/develop/RELEASE_NOTES.md) · [MaxIm DL FITS fields](https://cdn.diffractionlimited.com/help/maximdl/FITS_File_Header_Definitions.htm)
- TIFF also reads physical focal length and sensor pitch from EXIF, primary-directory tags, and XMP. Focal-plane resolution in inches or centimeters can supply nominal sensor pitch. A declared reference-size mismatch or digital zoom leaves the inferred pitch unset. [TIFF conventions and owner fixtures](phase-36a.md#tiff-metadata-at-panel-import)
- XISF image properties can supply focal length, pixel sizes, binning, camera, telescope, and filter when the corresponding FITS-style values are unavailable. The reader converts focal length from meters to millimeters. [XISF interchange](phase-5a.md#scope) · [N.I.N.A. XISF writer](https://github.com/isbeorn/nina/blob/develop/NINA.Image/FileFormat/XISF/XISFHeader.cs)
- The headless `solve` command uses an explicit `--scale`, then a positive embedded `PIXSCALE`, then the scale derived from effective pitch and focal length. A project solve uses saved panel overrides when deriving that scale. Gaia receives a scalar derived hint when the two axis scales agree. ASTAP's field height uses the Y scale. Available blind solver paths can handle missing pointing or scale hints. [Optics and WCS tests](../tests/integration/test_panel_inspection.py)

On Windows 11 x64, the Phase 3.1A source and packaged CLIs solved an M13 reference copy with both local Gaia DR3 and hinted ASTAP using generated optical metadata equivalent to 1.0069 arcseconds per pixel. The copy retained its original bytes through each check. The native desktop regression checked the embedded hints, manual edit, restored project values, and WCS state after relinking on the secondary monitor. [M13 source provenance](phase-0.md#offline-astap-experiment) · [Desktop regression](../tests/integration/test_desktop_project.py)

## Local Plate Solve Settings

Open **Tools → Plate Solve Settings** even with an empty project. The paths and database selection belong to the local Windows user and are restored when the application restarts.

1. For Gaia DR3, select an installed Seiza star catalog file. Select its matching blind index for panels without usable pointing and plate scale. Keep the catalog and index from the same Seiza bundle. The source desktop needs the optional `gaia` extra for this backend. [Seiza catalog setup](phase-2.md#catalog-setup-and-updates)
2. For ASTAP, select the ASTAP command-line executable and the folder containing the unpacked database tiles. Choose D05, D20, D50, or D80 to match the installed database. [ASTAP command line and databases](https://www.hnsky.org/astap.htm#astap_command_line)
3. Select **Check Paths** to see each backend's results. Seiza attempts to open the selected files. ASTAP checks the layout of a matching sample tile and requests the executable's version through its help command. Select **Save** to retain the paths and database. Check the paths again after moving the catalog or reconnecting its drive. [Path check tests](../tests/integration/test_solver_setup.py)

The settings can hold either backend or both. The offline chain tries Gaia DR3 before ASTAP after checking for usable WCS. Solve diagnostics retain the backend version and the Gaia catalog and index identities or the selected ASTAP database. [Offline solver order](adr/0005-offline-solver-chain.md) · [Desktop solve stages](../astro_mosaic_python_first_architecture_en.md#phase-31-desktop-plate-solving)

Use Seiza's `stars-gaia.bin` for hinted solves or the `stars-deep-gaia17.bin` and `blind-gaia16.idx` pair for blind solves. PixInsight `.xpsd` files return a format error when selected in the Gaia catalog or index field. A solved FITS from an external workflow can enter AstroMosaic through its embedded WCS. [M42 format and reuse checks](phase-35.md#m42-offline-astrometry-and-documents-catalogs)

On Windows 11 x64, separate desktop processes checked and restored the real Gaia DR3 catalog and blind index and ASTAP CLI 2026.11.01 with D05 in an isolated settings store. The warning path identified missing files after reopening. The rebuilt CPU and OpenGL desktop bundles also checked missing paths and saved settings. [Desktop settings regression](../tests/integration/test_desktop_solver_settings.py) · [Packaged desktop checks](../packaging/check-windows-desktop.py)

## Desktop Plate Solving

1. Set the local solver paths and choose **Plate Solve** in the Panels controls. The job uses the selected sky layer inputs, each panel's optical hints and sky mask, and the saved backend settings. The progress bar and percentage share the status row with elapsed time and **Cancel Job**. The percentage updates as the job checks reusable WCS, prepares each panel, searches and validates a candidate, and saves the accepted WCS. The status names the active panel and backend. Elapsed time continues to update during a search until the next measured step.
2. Plate Solve starts directly from a saved or untitled project. A saved project writes new sidecars in a sibling folder such as `Night.astromosaic.wcs`. An untitled project writes them in the `wcs` subfolder of the local AstroMosaic application data directory. Saving the project retains links to previously written sidecars. Include those files when transferring the project. Each completed solution is written atomically with its source and sky mask identity.
3. Read each attempted panel's result in the list and hover over the row to see the solver attempts and errors. **Cancel Job** beside the progress status finishes cleanup and attaches any completed results. The final percentage and solved or failed totals remain visible after the job stops. Choose **Plate Solve** again to retry panels that still need a valid WCS. Preview and export use the attached WCS. Save the project to keep the links across sessions. [Desktop regression](../tests/integration/test_desktop_plate_solve.py)

Phase 3.6 runs ASTAP first for new solves and uses Automatic catalog selection on a fresh setup. In **Plate Solve Settings**, set the panel, attempt and optional batch limits. The **Panel → Plate Solve Details** dialog shows the selected model, catalog errors and spatial support. **Panel → Revalidate Plate Solution** requests a new catalog fit and preserves the earlier sidecar on failure. [Current solve behavior](phase-36-results.md#behavior)

The earlier Phase 3.1C Windows checks passed on offscreen CPU and native OpenGL with the solver order of that checkpoint. The mixed project reused its embedded and attached WCS, skipped its foreground-only panel, and used real Gaia DR3 and ASTAP D05 on M13. Cancelling a later ASTAP attempt reaped the process and removed staging files while keeping the first solution. The saved project reopened and preview and FITS export used the attached solutions. [Historical packaged checks](phase-3f.md#background-checks)

### Beta 10 progress verification

On a real M13 DSS FITS panel, the copied desktop runtime showed 10%, 32%, 37%, 42%, 77% and 100% at WCS eligibility, ASTAP preparation, search, validation, sidecar publication and completion. Gaia DR3 also showed preparation, search and validation checkpoints. While the native search was active, elapsed time updated and the stage percentage stayed steady. The two-panel ASTAP run cancelled at 68%, retained the first WCS and solved the second panel when retried. Revalidation with an existing preview also passed.

The CPU and OpenGL checks ran on the secondary LS24DG30X screen. The bar measured 1,040 × 27 logical pixels in the standard dark window and 660 × 27 in the compact light window. The active percentage and Cancel Job were visible in both. [Beta 10 build record](windows-release.md#verification-status)

## Verification

- Persistence tests check Unicode paths, project folder moves, all render settings and attachment references, fingerprint-matching relink, changed and missing file errors, unsupported schemas, and preservation of the original manifest after a failed atomic replacement. [Persistence tests](../tests/integration/test_project.py)
- The Qt workflow test adds FITS and TIFF panels, sets a blend weight, attaches a saved WCS and FITS sky mask, edits the grid, saves, and reopens the project. It relinks a moved source, checks progress from the worker, and verifies the GUI timer still runs during rendering. It cancels after the first real tile, checks temporary-file cleanup, retries to a valid TIFF output, and closes the window during another render to check asynchronous cleanup. The output history confirms that the saved attachments were used. The test supplies file dialog selections programmatically. [Desktop test](../tests/integration/test_desktop_project.py)
- Windows 11 x64 with PySide6 6.12 passed the workflow under the native Windows Qt platform plugin. Packaged installation and recovery checks remain in Phase 3F. [Delivery stages](../astro_mosaic_python_first_architecture_en.md#101-phase-3-delivery-stages)
