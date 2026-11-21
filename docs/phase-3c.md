# Phase 3C Sky Preview and Export

## Desktop Workflow

1. Add linear FITS, TIFF, or supported XISF panels to a project. Set the ICRS center, sky projection, dimensions, scale, rotation, and optional crop under **Mosaic Settings**. Attach WCS solutions or supplied sky masks under **Panel Settings** as needed. [Sky projection](phase-5b.md)
2. Choose **Build Preview**. Drag to pan, use the wheel to zoom around the pointer, and choose **Fit View** to reset framing. Adjust **Midtones** to see faint detail. The display mode appears beside the stretch control.
3. Choose **Export Mosaic** to write float32 samples with WCS and coverage. Use FITS for mono, or TIFF or XISF for mono and RGB. The project grid and panel settings control both jobs. Preview pan, zoom, and stretch are display controls. [XISF workflow](phase-5a.md#use-the-format)

Plate Solve supplies each panel's celestial coordinates. Set the **Mosaic Settings** grid to cover the panels you want in the preview. Unlabeled panels use `Unspecified` unless you assign a **Common filter**. For linear TIFF panels on a shared scale, use **Declare a common surface-brightness scale** when the unit is unavailable. Convert display-encoded TIFFs to linear samples before this workflow. The Command Panel reports conflicting filter labels and missing brightness settings. [TIFF sample contract](phase-3a.md#sample-and-metadata-contract)

Preview and export jobs run one at a time. **Cancel Job** stops at the next cancellation checkpoint. Editing the panels or mosaic settings clears the preview. Build it again after applying the edits. The app uses CPU raster display when OpenGL is unavailable. To choose CPU on startup, use `poetry run python -m astromosaic.ui --cpu-preview`.

## Geometry and Display

The final preview has a longest edge of up to 512 pixels. When a 160-pixel proxy is smaller and contains covered samples, it appears first. The final raster replaces it and keeps the current framing. For outputs within the limit, the final preview has one sample per output pixel. Each preview cell at column `i` and row `j` samples the output grid at `((i + 0.5) * output_width / preview_width - 0.5, (j + 0.5) * output_height / preview_height - 0.5)` in zero-based center coordinates. Crop, rotation, WCS, masks, blend weights, and optional mono refinement use the export geometry. Zoom magnifies the cached raster.

Black and white display points use the 1st and 99.5th percentiles of valid samples and are linked across RGB channels. The midtone transfer runs on cached display buffers. Uncovered cells use the canvas background. OpenGL minification averages valid colors using coverage-premultiplied mip levels and checks the base coverage at the sampled position. The CPU surface uses nearest-neighbor raster display.

## Windows Verification

- A rotated and cropped mono FITS fixture matched the preview's full-resolution samples and coverage exactly after CFITSIO reopening. The reopened WCS matched within `1e-9` degrees. A rotated and cropped RGB TIFF fixture matched exactly where the 512 × 48 proxy samples coincided with pixels of the 1536 × 144 export. The existing three-panel refinement fixture matched its masked and corrected FITS export. [Preview fixtures](../tests/numerical/test_preview.py) · [Refinement fixture](../tests/numerical/test_refinement.py)
- Native Windows Qt checks exercised both display backends, pointer-centered zoom, drag pan, fit, and a live midtone change. The framebuffer samples matched within one 8-bit level and kept coverage holes visible. An injected OpenGL upload error triggered CPU fallback with the same preview. The checks passed at 1× and 2× device scale. The project and CPU checks also passed with Qt's offscreen platform. [Viewport checks](../tests/integration/test_sky_viewport.py)
- The desktop workflow built, cancelled, and retried a project preview with FITS/TIFF panels, a WCS sidecar, and a sky mask. Export reused the saved geometry and left the displayed preview in place. [Desktop workflow test](../tests/integration/test_desktop_project.py)

To require native OpenGL in the viewport tests on Windows, run:

```powershell
$env:QT_QPA_PLATFORM = 'windows'
$env:ASTROMOSAIC_TEST_OPENGL = '1'
poetry run pytest tests/integration/test_sky_viewport.py
```

## Resource Check

The engine reserves space for the active preview raster within the job's working-byte limit. A 512 × 512 RGB linear raster plus validity uses at most 3.25 MiB. The normalized RGBA32F display buffer adds at most 4 MiB, with up to 5.33 MiB for its OpenGL texture and mip levels or 1 MiB for a cached CPU raster. Percentile calculation, display conversion, Qt framebuffers, and driver allocation add temporary or backend-specific memory. Only one desktop worker runs at a time.

The Windows 11 x64 check used the [Phase 1 two-panel workload](phase-1.md#working-set-and-cancellation), a 3328 × 1536 mono L mosaic on an i5-14600K with an RTX 4070, Qt 6.12, a 996 × 395 canvas at 1× scale, and warm source files. The first preview produced 160 × 73 and 512 × 236 rasters. Stretch timings cover 30 subsequent changes with synchronous canvas readback. Memory is the Windows process peak through the first build and the stretch samples.

| Display | First proxy | Final preview | Stretch + readback p50 / p95 | Peak working set / commit |
| --- | ---: | ---: | ---: | ---: |
| OpenGL | 444 ms | 514 ms | 0.61 / 0.76 ms | 226.7 / 259.8 MiB |
| CPU | 174 ms | 429 ms | 3.51 / 4.16 ms | 175.9 / 164.0 MiB |

Packaged Windows acceptance and the 12-panel resource workload follow in Phase 3F and Phase 4. [Delivery stages](../astro_mosaic_python_first_architecture_en.md#101-phase-3-delivery-stages)
