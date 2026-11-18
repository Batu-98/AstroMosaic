# Phase 4B - Large Mosaics and Blend Quality

Phase 4B starts from the [verified project CLI](phase-4a.md). Use the same saved project and renderer for local measurements, desktop export, and later automation. The [architecture](../astro_mosaic_python_first_architecture_en.md#102-phase-4-delivery-stages) defines the 12-panel workload and the tile scheduling requirements.

## Scope and Acceptance

| Step | Scope | Acceptance evidence |
| --- | --- | --- |
| Full-size reference | Render twelve 6000 × 4000 panels per case in mono FITS, compressed RGB TIFF, and a mixed sky and foreground project. | Reopen every science sample and coverage pixel in bounded strips. Compare against the analytic field with absolute error at most `8e-6`. Verify coverage and composition contributions exactly, and check the sky WCS to `1e-9` degrees. |
| Resource and tile checks | Retain the saved working and output limits. Measure elapsed time, peak tile reservation, process working set and process commit. | Observe progress while the writer holds a temporary raster. Verify a tight-budget crop that crosses compressed source blocks and splits output tiles. Verify rejection before writing at an insufficient output limit and retry the full export after cancellation. |
| Candidate selection | Use the timing and profile to reduce work for panels outside a tile. Preserve the existing full WCS and SIP contract for inputs that require it. | Establish conservative bounds and test cases involving correction shifts, crop, rotation, RA wrap, masks and distortion. Compare coverage and original-sample correctness against this reference, then rerun the full-scale timing matrix. |
| Optional blend comparison | Retain weighted linear blending as the reference. Evaluate a multiband implementation only with a representative overlap and established registration and background fits. | Measure seam residuals and held-out stellar and faint-signal preservation. Verify halo support, coverage, memory and runtime for any added mode. |

Keep the single-worker reference and saved job contracts available for Phase 4C. Bound any future candidate index, queue, halo or extra raster in the working-set measurements. The phase validates the export path from saved WCS and foreground geometry. Plate solving and foreground fitting have separate evidence.

## Reference Workloads

Every case uses a 4 × 3 layout with 4096 × 2560 pixel steps. The sky canvas is 18,288 × 9,120. The synthetic brightness field includes signed values, true zero and two no-data rectangles. Each panel has a saved weight. The three channels in the RGB case use distinct linear combinations of the brightness field.

- **FITS** uses twelve mono float32 panels and writes float32 FITS with binary coverage and celestial WCS.
- **RGB TIFF** uses twelve float32 RGB panels with 128 × 128 Deflate source tiles and a quarter-pixel shift in both axes. The independent reference accounts for every bilinear tap and panel-edge clamp. The saved output limit is 3072 MiB. The default 2048 MiB limit rejects this full output before tile writing.
- **Mixed** uses six mono FITS and six mono TIFF panels. The bottom four have saved sky and foreground masks and known fixture translations. The saved composition has a 256-pixel overlap. Its 18,288 × 8,864 TIFF carries coverage and layer contributions, with the sky grid in its provenance.

The full cases use 128-pixel output tiles and a 64 MiB working reservation limit. The tight RGB check uses a 513 × 385 crop crossing a validity gap, 193-pixel requested tiles and a 6 MiB limit. The reservation covers rendering buffers. The Windows process counters include the loaded runtime and its allocations.

## Reproduce

Use the locked development environment and the [Qt-free Windows console package](phase-3f.md#build). Run from a Windows console for the interrupt check. Use a new ignored output directory for each separate run.

```powershell
$cli = 'dist/windows/astromosaic-cli/astromosaic-cli.exe'
foreach ($case in 'fits', 'rgb-tiff', 'mixed') {
    $fixture = ".tooling/phase4b/$case"
    poetry run python tools/phase4b_benchmark.py prepare $case $fixture
    if ($case -eq 'fits') {
        poetry run python tools/phase4b_benchmark.py run $case $fixture --cli $cli --cancel
    }
    poetry run python tools/phase4b_benchmark.py run $case $fixture --cli $cli
    poetry run python tools/phase4b_benchmark.py verify $case $fixture
}
poetry run python tools/phase4b_benchmark.py halo .tooling/phase4b/rgb-tiff --cli $cli
```

The generator writes one panel at a time. Each render starts a fresh console process with one OpenBLAS and OpenMP thread, then saves raw result JSON, progress and the process measurements beside the output. FITS verification uses CFITSIO. TIFF verification maps the exported rasters and reads one strip at a time. The analytic WCS check uses the known tangent point and grid scale. [Benchmark and verifier](../tools/phase4b_benchmark.py)

## Windows Baseline Results

The three full exports ran concurrently on Windows 11 Pro x64 build 26200 with an Intel Core i5-14600K and the Phase 4A portable console build. Each render used one synchronous tile worker and zero queued tiles. Times are launch to observed process exit. The operating system file cache was uncontrolled. Fixtures, exports and raw measurements are in ignored `.tooling/phase4b-baseline/`.

| Workload | Output pixels | Tiles | Elapsed | Peak reservation | Peak working set | Peak commit | Output |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Mono FITS | 166,786,560 | 10,296 | 592.03 s | 17.125 MiB | 134.76 MiB | 139.97 MiB | 795.31 MiB |
| RGB TIFF | 166,786,560 | 10,296 | 622.87 s | 19.397 MiB | 140.75 MiB | 145.09 MiB | 2067.79 MiB |
| Mixed composition | 162,104,832 | 10,010 | 575.97 s | 20.211 MiB | 140.18 MiB | 144.88 MiB | 927.58 MiB |

- All 495,677,952 output pixel positions were checked, including each RGB channel. FITS and mixed sample values matched exactly. RGB maximum absolute error was `3.815e-6`. Sky WCS maximum error was `5.685e-14` degrees. All source fingerprints matched their saved references.
- Coverage matched exactly in each case. The mixed raster contained 1,536 uncovered, 125,527,296 sky-only, 31,894,363 foreground-only and 4,681,637 feathered pixels. Its TIFF contained no celestial WCS and retained the sky geometry in processing history.
- All full exports reported monotonic progress while the temporary raster was visible. The FITS console break cancelled after the first 16,384 pixels and returned exit code 130 in about 0.31 seconds as observed by the monitor. The final target and temporary file were absent after cancellation. The full FITS run succeeded at the same path.
- The 6 MiB RGB crop completed in 80 split tiles with a 5.284 MiB peak reservation. All 197,505 positions and masks matched the corresponding region of the full output exactly. The separate 2048 MiB output-limit trial rejected the full RGB TIFF before tile writing. The full render used the saved 3072 MiB limit.
- All 147 native Windows source tests passed, including OpenGL on the second monitor. Ruff, format, mypy and the lock check passed.

## Footprint Selection Results

The renderer now selects panels using padded footprints in the output grid. It uses full WCS mapping for SIP, TPV, alternate frames and projections whose corners cannot be bounded conservatively. Ground footprints include the saved translations and composition placement. [ADR-0018](adr/0018-conservative-panel-footprints.md)

The final portable CLI repeated the three overlapping runs on the same Windows host with the same physical source files, manifests and limits. The revised exports and the 6 MiB RGB crop matched the earlier files byte for byte. Independent verification also checked each science position, coverage and layer mask, and the sky WCS. The measurements and SHA-256 comparisons are in ignored `.tooling/phase4b-footprints/`. The updated console package is in `.tooling/phase4b-footprints-windows/dist/`.

| Workload | Baseline | With selection | Time reduction | Peak reservation | Peak working set | Peak commit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Mono FITS | 592.03 s | 170.34 s | 71.2% | 17.128 MiB | 134.85 MiB | 139.91 MiB |
| RGB TIFF | 622.87 s | 199.31 s | 68.0% | 19.400 MiB | 140.68 MiB | 146.06 MiB |
| Mixed composition | 575.97 s | 149.99 s | 74.0% | 20.215 MiB | 139.84 MiB | 144.80 MiB |

- The matching 1728 × 1024 FITS crop profile reduced mapping calls from 1,344 to 448 over 112 tiles. The renderer read 448 source windows in both runs. Time inside coordinate mapping fell from 6.888 to 2.116 seconds, and profiled raster writing fell from 10.137 to 4.969 seconds.
- The 6 MiB RGB crop used 80 split tiles and a 5.287 MiB peak reservation. The saved 2048 MiB trial rejected the full RGB output before writing. FITS console cancellation cleared temporary output in about 0.31 seconds and the retry published at the original path.
- Focused comparisons with the full panel list covered RA wrap, rotated and cropped grids, a fitted shift, mirrored axes, a sky mask, scaled preview, and rotated foreground placement at a negative origin. Bounds fall back for SIP, TPV, alternate frames and projection horizons. A packaged TPV/TAN pair matched the baseline file exactly.
- All 154 native Windows tests passed, including OpenGL on the second monitor. The copied console workflows and the installed and portable Python and PowerShell batch checks passed.

Use the same baseline files for a comparison by saving the original references in a fresh case directory.

```powershell
$baseline = '.tooling/phase4b-baseline/rgb-tiff'
$trial = '.tooling/phase4b-repeat/rgb-tiff'
$cli = 'dist/windows/astromosaic-cli/astromosaic-cli.exe'
poetry run python tools/phase4b_benchmark.py prepare rgb-tiff $trial --reuse $baseline
poetry run python tools/phase4b_benchmark.py run rgb-tiff $trial --cli $cli
poetry run python tools/phase4b_benchmark.py verify rgb-tiff $trial --baseline $baseline
```

## Next Step

Phase 4B meets the required local Windows gates. Weighted linear blending is the verified reference. Optional multiband work can be evaluated when a calibrated overlap with seam and scientific residual measurements is available. Phase 4C uses the verified commands, progress and cancellation in a responsive desktop panel. [Phase 4C gate](../astro_mosaic_python_first_architecture_en.md#102-phase-4-delivery-stages)
