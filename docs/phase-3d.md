# Phase 3D Foreground Tags and Sky Masks

## Desktop Workflow

1. Use **Add Panels** to import FITS or linear TIFF sources. The app checks each panel for a horizon in a background job. The panel list shows mixed suggestions, uncertain cases, and panels for which the check found no horizon. **Panel → Check Foreground** repeats the check for the selected panel.
2. Use **Panel Settings → Foreground tag** to mark an undetected mixed panel or declare a panel **Sky only**. A saved manual tag takes precedence over later suggestions. Mixed or uncertain panels need a mask for sky jobs. Select **Sky only** for a false positive.
3. Choose **Panel → Propose Sky Mask** for a mixed or uncertain panel. Review the overlay before applying. To open the saved mask or draw one from scratch, choose **Edit Sky Mask**. Drag with **Trace horizon** to set sky above and foreground below. Use the three paint tools to refine the selection and restore any uncertain cells. **Reset Edits** restores the displayed starting mask for that editing session.
4. Choose **Apply Mask** and save the project. The mask appears when the project reopens. Preview and export use the edited selection. A new mask change clears the cached mosaic preview.

The mask can also come from an existing binary FITS file in **Panel Settings**. Applying edits to the FITS mask overlay replaces its attachment in the project with the editable grid. The original external mask file stays on disk. Keep the full-resolution FITS attachment when its precise pixel boundaries are required.

## Solve a Saved Project Panel

For a panel that needs a WCS, pass the saved `.astromosaic` file and the panel's one-based number to `solve`. Add the local catalog options described in the [offline solver setup](phase-2.md#offline-solvers).

```shell
poetry run astromosaic solve night.astromosaic --panel 2 --gaia-catalog catalogs/gaia/stars-gaia.bin --hint 250.42 36.46 --scale 1.007 -o panel-2.wcs.json
```

Attach the result under **Panel Settings → WCS sidecar**. The saved sky selection applies to star extraction and solver staging. A sidecar created for a previous sky selection is rejected. Solve and attach a new sidecar after changing that selection, or clear the attachment if the panel already has a valid embedded WCS.

## Mask Geometry and Limits

The detector checks an area-averaged luminance thumbnail of up to 128 cells on its longest side. A separate job proposes a mask on an editing grid of up to 384 cells. The local heuristic looks for a supported horizon extending across neighboring columns. It can miss small, rotated, or ambiguous terrain and can flag other strong horizontal transitions. Review the proposal or trace and paint the mask manually for those cases.

Each grid cell covers the original pixel rectangle between adjacent integer grid edges. Labels are independent of scientific intensity and input validity. Sky processing intersects the sky label with valid input pixels. Proposals leave a band around the horizon and poorly supported columns unclassified. Strong edges get a narrower band. Edits change the common three-label grid so each source pixel belongs to at most one layer.

The worker reads bounded source tiles one at a time. It reserves 128 bytes per thumbnail cell for thumbnail and proposal buffers, then reduces the tile size if source decoding or the remaining budget requires it. A square 384-cell label grid uses 144 KiB before manifest encoding. The editor and automatic check can be cancelled between source tiles.

## Windows Verification

- Low-contrast, irregular injected horizons were classified on mono FITS and compressed RGB TIFF. On the named fixtures the proposals did not assign ground to sky or sky to foreground. A partial horizon was flagged as uncertain, and a smooth sky gradient received no foreground suggestion. Tests also cover tile edges, invalid samples, budget rejection, and cancellation. [Mask tests](../tests/numerical/test_masking.py)
- Native Qt tests exercised the foreground scan, a manual tag surviving a recheck, cancellation of a proposal, painting a proposed mask, tracing a missed horizon, and reopening both saved edits. The source bytes remained unchanged. [Desktop tests](../tests/integration/test_desktop_project.py)
- The project-panel CLI excluded injected ground features from SEP measurements and used neutral values in the masked ASTAP staging file. Preview reused the sidecar for the saved mask and rejected it after a sky edit. The three-panel refinement kept the same stellar and background acceptance thresholds and output as a supplied mask with the same selection. [Solver tests](../tests/integration/test_offline_solve.py) · [Refinement tests](../tests/numerical/test_refinement.py)
- On the 3267 × 3274 M13 DSS input, the 128-cell check found no horizon in the original and detected the injected foreground in the mixed copy. The scans took about 0.9 seconds per FITS file and the mixed proposal took about 0.8 seconds in the final run. The proposal retained 99.27% of the known sky and left 1.04% of the source unclassified, with no swapped labels. Hinted ASTAP 2026.11.01 with D05 solved the project panel. Its WCS differed from the solution using the full-resolution reference FITS mask by at most 0.0072 arcseconds across five samples. [Reference source and solver setup](phase-2.md#windows-solver-evidence)
- Hinted Gaia DR3 exhausted its match search on that masked M13 copy. ASTAP with D05 provided the verified WCS for this case.
