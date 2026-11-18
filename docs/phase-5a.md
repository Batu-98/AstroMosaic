# Phase 5A XISF Interchange

## Scope

Import two-dimensional, uncompressed monolithic XISF 1.0 attachments with linear Float32 or UInt16 mono and RGB samples. Support planar and interleaved layouts and both byte orders. Convert to float32 for processing while preserving numeric sample values, RGB order, and top-left row order. Read FITS-compatible keywords for WCS, units, and filter metadata. The optical metadata reader also accepts inline `Instrument` image properties for focal length, pixel size, binning, camera, telescope, and filter. A panel with only private astrometric properties can use the existing local plate solver or attach a validated WCS sidecar. [Panel optics](phase-3b.md#panel-wcs-and-plate-solve-hints)

Export a single XISF file containing the float32 science image and a matching byte image named `AstroMosaicCoverage`. Composition exports also contain an `AstroMosaicLayers` byte image with the existing contribution codes. Preserve the sky grid with FITS-compatible keywords and write the rendered values directly. See [ADR-0020](adr/0020-bounded-xisf-interchange.md) and the [XISF 1.0 specification](https://pixinsight.com/doc/docs/XISF-1.0-spec/XISF-1.0-spec.html).

The shared source interface connects the format to saved projects, sky masks, plate solving, previews, and render jobs. The output path suffix selects the writer. The same pixel and WCS contracts apply when a subsequent stage adds projections or band-specific output.

## Acceptance Cases

| Case | Required result |
| --- | --- |
| Import and validity | Read offset windows and clipped halos from an independently constructed RGB Float32 fixture and a big-endian mono UInt16 fixture. Verify negative, zero, above-one and 65535 samples, masked finite pixels, non-finite values, channel order, and unchanged input files. Combine attached FITS sky masks with the XISF coverage. |
| Sky export | Render a rotated and cropped grid. Compare float32 samples and the binary coverage exactly against the shared renderer's TIFF or FITS output. Reopen XISF with an independent decoder and verify FITS keywords for `BUNIT`, `FILTER`, and sky coordinates within 1e-9 degrees. |
| Foreground and composition | Reopen the image and coverage for each layer. For composition, verify all four contribution codes and confirm that positive codes equal coverage. Validate matching preview and export samples. |
| Resource and failure behavior | Read only requested row fragments. Reject malformed attachment ranges and unsupported storage with a diagnostic. Exercise the tile and exact output-byte limits, cancellation after tile progress, retry at the same path, and occupied output paths. |
| Windows workflow | Create and validate an XISF project, export again, and reopen it from the copied Qt-free console bundle. Add an XISF panel, preview it, and export through the copied desktop bundle using both CPU and OpenGL. |

Compressed and non-attached data blocks, declared checksum verification, native astrometric properties, and broader XISF compatibility are tracked in [Q-020](../questions_open_topics.md#q-020---additional-xisf-variants).

## Use the Format

Open a supported file with **Add Panels** or `astromosaic inspect panel.xisf`. Use an attached WCS sidecar or the local solver when the panel needs a celestial solution. For export, choose **XISF mosaic** or pass a new `.xisf` destination to `mosaic` or `project export`.

The XML header is limited to 1 MiB. The adapter reads row fragments into the tile budget. The writer reserves aligned attachments on disk and verifies their full file size against the output limit before processing tiles. External readers can reopen the additional mask images by their IDs. Use `AstroMosaicCoverage` values 0 and 1 for uncovered and covered pixels. For compositions, `AstroMosaicLayers` encodes the sky and foreground bits as 1 and 2.

## Local Windows Results

- All 165 source tests passed on Windows 11 x64 with native OpenGL and test windows on the second display. The focused 24-test rerun covered both layouts and byte orders, rotated and cropped RGB parity, mono and RGB layer exports, output limits, cancellation, retry, and an occupied destination. Sky WCS agreed within 1e-9 degrees. Ruff, format, mypy and Poetry lock checks passed. [XISF tests](../tests/numerical/test_xisf.py) · [Layer tests](../tests/numerical/test_layers.py)
- The independent `xisf` 1.0.1 writer generated a planar RGB input with one missing pixel. Its decoder reopened the source CLI and portable CLI exports with 71 covered positions and exact sample, coverage, and filter and unit metadata agreement. It also reopened the mono and RGB compositions with 7,928 covered pixels each. Their samples, binary coverage and four contribution codes matched the FITS and TIFF references. The independent reader ran in a local validation environment. [Independent reader](https://github.com/sergio-dr/xisf)
- The copied Qt-free console passed RGB XISF export, project creation, validation, re-export, and embedded WCS reuse. The copied desktop passed CPU and native OpenGL checks. The export dialog supplied the `.xisf` extension, **Add Panels** reopened the file with its embedded WCS, and the preview matched at all 3,347 covered positions. The rebuilt launchers are in ignored `.tooling/phase5a-windows/dist/windows/`. [Console checker](../packaging/check-windows-cli.py) · [Desktop checker](../packaging/check-windows-desktop.py)

The local acceptance cases passed. A separate clean Windows installation remains part of [distribution acceptance](phase-3f.md#pending-clean-machine-check). The next Phase 5 workflow is an additional sky projection with saved grid settings and shared preview and export geometry.
