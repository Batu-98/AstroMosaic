# Phase 3C Sky Preview and Export

## Desktop Workflow

1. Choose **Add Panels** to load supported FITS, TIFF, or XISF files.
2. Choose **Plate Solve** for sky panels that need a WCS. Select a local solver under **Plate Solve Settings** during initial setup. If a panel contains foreground, apply a sky mask in **Panel Settings**.
3. Choose **Build Preview**. With **Auto Frame** on, the selected sky panels determine the preview framing from their WCS. Drag to pan, use the wheel to zoom, and choose **Fit View** to restore the overview. Close zoom samples the visible region at full output resolution and shows **1:1** when it is ready. Adjust **Midtones** to see faint detail. [Sky projection](phase-5b.md)

New desktop projects start with **Auto Frame** enabled. Existing projects use the saved grid until you enable **Auto Frame**. To render a scientific mosaic, choose **Use Preview Grid** after a fitted preview or set the export grid directly in **Mosaic Settings**. **Export Mosaic** writes float32 samples with WCS and coverage. FITS supports mono output. TIFF and XISF support mono and RGB output. [XISF workflow](phase-5a.md#use-the-format)

When every selected panel is an unsigned 16-bit RGB TIFF with a recognized sRGB ICC profile, the app shows **Visual Preview**. A covered visual sky preview enables **Export Photo Mosaic**. Scientific export requires compatible linear inputs. Use **Declare a common surface-brightness scale** when linear inputs share a scale and lack suitable units. Unlabeled panels use `Unspecified` unless you assign a **Common filter**. [Photo workflow](phase-8.md#8b-export-a-photo-mosaic) · [ICC and framing decisions](adr/0025-automatic-sky-preview.md) · [TIFF sample contract](phase-3a.md#sample-and-metadata-contract)

The app reports the panel and cause when a missing WCS, unusable mask or incompatible profile blocks a preview. Run Plate Solve, repair the mask, or choose compatible panels as indicated. The Command Panel equivalents are `session add <paths>`, `session solve` and `session preview`. Use `session preview --grid auto` to enable automatic framing or `session use-preview-grid` to adopt the fit. [Desktop commands](phase-4c.md#control-the-active-project-without-dialogs)

Preview and export jobs run one at a time. **Cancel Job** stops at the next cancellation checkpoint. The app uses CPU raster display when OpenGL is unavailable. To choose CPU on startup, use `poetry run python -m astromosaic.ui --cpu-preview`.

### Adaptive framing and interactive crop

**Mosaic Settings** shows the effective preview grid when one is available. Lock the center, projection, size, scale or crop to retain its entered value under Auto Frame. Editing a grid field locks its group. A fixed pixel crop retains its full grid size. Rotation remains explicit and **Use suggested rotation** can adopt an angle that reduces the footprint rectangle. **View → Live Sky Preview** refreshes an already opened sky preview after a panel, band, mask, WCS or setting change when the selected inputs are ready. The saved scientific grid is adopted explicitly.

The crop outline marks the rendered rectangle. Choose **Edit Crop** to view the full grid with draggable edges, corners and interior. **Use Auto Crop** loads the projected sky footprint bounds. **Apply Crop** adopts the full grid and selected rectangle for the project and switches to a fixed grid. **Cancel** restores the previous preview and settings. The project can be saved and reopened with the selected crop. [Adaptive preview decision](adr/0027-adaptive-sky-preview.md)

The selected band's available filter labels and brightness units appear in Mosaic Settings. Keep the common-scale checkbox for a verified user declaration. For compatible mono panels, choose **Auto** to test a supported background model against held-out samples. An automatic stellar radius uses the two largest qualified catalog RMS values in the selected band and is capped at six output pixels, with a one-pixel minimum and a six-pixel fallback when evidence is missing. A numeric radius remains available. [Mono refinement](phase-2.md#relative-refinement)

## Geometry and Display

The desktop first offers a 160-edge proxy, then a fixed reference preview and a viewport-sized overview within the job budget. When minifying, it averages a bounded grid of sub-samples per display cell in linear light and excludes invalid samples. At close zoom a cancellable worker reads an in-bounds visible rectangle, sampling the exact output pixel centers. The detail reuses the overview tone and is composited over the overview. Its maximum size is 1,048,576 output pixels. The original headless point-preview API remains available for coincident sample checks.

Black and white display points use the 1st and 99.5th percentiles of valid samples from the fixed 512-edge reference and are linked across RGB channels. The midtone transfer runs on cached display buffers. Uncovered cells use the canvas background. OpenGL uses coverage-premultiplied mip levels for additional display minification. The CPU smooths the overview when shrinking it to the canvas. Both use the zoomed detail at the same output positions.

## Windows Verification

- A rotated and cropped mono FITS fixture matched the preview's full-resolution samples and coverage exactly after CFITSIO reopening. The reopened WCS matched within `1e-9` degrees. A rotated and cropped RGB TIFF fixture matched exactly where the 512 × 48 proxy samples coincided with pixels of the 1536 × 144 export. The existing three-panel refinement fixture matched its masked and corrected FITS export. [Preview fixtures](../tests/numerical/test_preview.py) · [Refinement fixture](../tests/numerical/test_refinement.py)
- Native Windows Qt checks exercised both display backends, pointer-centered zoom, drag pan, fit, and a live midtone change. The framebuffer samples matched within one 8-bit level and kept coverage holes visible. An injected OpenGL upload error triggered CPU fallback with the same preview. The checks passed at 1× and 2× device scale. The project and CPU checks also passed with Qt's offscreen platform. [Viewport checks](../tests/integration/test_sky_viewport.py)
- The desktop workflow built, cancelled, and retried a project preview with FITS/TIFF panels, a WCS sidecar, and a sky mask. Export reused the saved geometry and left the displayed preview in place. [Desktop workflow test](../tests/integration/test_desktop_project.py)
- Beta 7 exercised **Add Panels → Plate Solve → Build Preview** on the original two 6000 × 4000 RGB TIFFs from a fresh untitled project. Local Gaia DR3 solved both panels. The bundled Windows CPU and OpenGL runs each produced a 445 × 512 visual preview with 109,331 valid samples, including 23,020 shared by both panels. Each panel's full WCS footprint was within the fitted grid on a 65 × 65 verification mesh. The saved grid changed on explicit adoption, scientific preflight rejected the encoded samples, and the original file hashes matched. [Windows build record](windows-release.md#verification-status)

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
