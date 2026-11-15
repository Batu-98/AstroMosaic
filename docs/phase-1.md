# Phase 1 FITS Reference

## Two-Panel Fixture

The [deterministic fixture](../tests/numerical/mosaic_reference.py) uses a 15 × 9 ICRS TAN grid centered at RA 359.999°, Dec 20°, with 7.2 arcseconds per pixel. Coordinates below are zero-based pixel centers. The reference pixel is `(7, 4)` and the grid crosses RA zero.

| Panel | Inclusive bounds on the output grid | Surface brightness | Missing samples |
| --- | --- | --- | --- |
| A | `x=1..8`, `y=1..6` | `x + 2y − 8`, stored as int16 with `BSCALE=0.5` and `BZERO=−4` | `(3, 3)`, `(7, 3)`, `(8, 5)` marked with `BLANK` |
| B | `x=6..12`, `y=2..6` | `x + 2y − 4.5`, stored as float32 | `(6, 4)`, `(8, 5)` are NaN and `(11, 6)` is infinite |

Both headers declare filter `L` and `MJy/sr`. Weights are 1 and 3. Where both panels contribute, the expected brightness is `x + 2y − 5.375`. A single contributor gives its decoded brightness exactly. A pixel with no contributor has NaN brightness and zero coverage. There are 65 covered pixels, including a valid zero at `(4, 2)` and a hole inside the overlap at `(8, 5)`.

The expected grid uses rectangle membership and arithmetic independently of the renderer, FITS scaling, and WCS library. Acceptance requires exact finite values and the exact binary coverage image for this integer-aligned case. The exported coordinates must agree with the analytic inverse TAN calculation within `1e-9` degrees at sampled pixels. The reference is generated in temporary directories.

## Render and Export Contract

Use `astromosaic mosaic --help` for the command options. Supply calibrated linear mono FITS panels of the same filter and brightness scale with validated celestial WCS. The job uses a caller-defined ICRS TAN center, dimensions, and pixel scale. The optional zero-based crop shifts `CRPIX` within that grid. Positive rotation turns the output +x direction from west toward north.

- Input `BSCALE` and `BZERO` are applied before sampling. Raw nonfinite values, integer `BLANK`, and zero-valued pixels in an optional binary `COVERAGE` extension mark missing samples. Finite science pixels of any sign are eligible for sampling.
- Explicit `--filter` supplies missing filter metadata. Input `BUNIT` labels must describe a common scale. A declared `--assume-surface-brightness` records the user's interpretation for ambiguous input units. Explicit per-pixel units require area-aware conversion. [ADR-0002](adr/0002-surface-brightness-reference.md)
- The CPU mapper requires a successful coordinate round trip within `1e-4` output pixels. It uses bilinear interpolation with valid support, clipping to the outer pixel centers inside the half-pixel footprint. A `1e-7` source-pixel tolerance stabilizes edges and integer-aligned samples. The blend uses one positive weight per panel, with equal weights by default. [ADR-0008](adr/0008-bounded-fits-sampling.md)
- The primary image stores linear float32 samples in the declared units and NaN outside coverage. The same-shape byte `COVERAGE` image uses 1 for covered and 0 for missing. The primary header records fresh ICRS TAN WCS, common metadata, processing choices, and ordered source fingerprints and weights. [FITS standard guide](https://science.data.nasa.gov/fits/documentation/standard)
- The destination is published after the last tile, flush, and cancellation check. Choose a new filename in an existing directory. Cancellation and errors remove the temporary output, including a publication race where another job created the destination first. The CLI provides progress on stderr and a JSON summary on stdout after successful publication.

## Numerical and Windows Checks

- `fitsio` 1.4.2 backed by CFITSIO (reported version `4.060`) independently read the two-panel export. All 135 science and coverage values, including 65 covered pixels, matched the reference. `fitsio` is a GPL-2.0-or-later development test dependency. [Package metadata and Windows wheel](https://pypi.org/project/fitsio/1.4.2/)
- A rotated and cropped SIP source agreed with its analytic bilinear values and the untiled `reproject_interp` baseline within `2e-6` brightness units. Fresh output WCS matched analytic TAN coordinates within `1e-9` degrees and omitted the source SIP coefficients. Additional tests exercised RA wrap, swapped longitude/latitude axes, inverse nonconvergence, singularities, an explicit coverage mask, true zero, and source-window subdivision. The 2 to 1 arcseconds-per-pixel Gaussian fixture preserved solid-angle-weighted aperture flux within 1%, and the uniform field retained exact brightness. [Numerical tests](../tests/numerical/test_mosaic.py)
- A local M13 DSS experiment used two overlapping 384 × 384 crops with the previously solved ASTAP WCS. The 612 × 400 mosaic matched the `reproject_interp` reference coverage at all 224,646 covered pixels and differed by at most 0.00101 ADU. The test used a declared common brightness scale for the archive samples and verified the original archive file's SHA-256. [Local source and solve provenance](phase-0.md#offline-astap-experiment)
- The Windows 11 x64 development bundle was rebuilt from the locked `main,build` environment in one-directory mode. From an unrelated working directory it rendered the weighted reference, inspected its output, and passed `smoke --spawn`. An independent CFITSIO read verified the bundled job's output. Archive inspection found the expected headless runtime, and the source CLI also passed with Qt and `fitsio` imports blocked. [Build procedure](phase-0.md#desktop-probe-and-packaging)

## Working Set and Cancellation

The reference has one synchronous render worker and zero queued tiles. Defaults are 128 pixels per tile side, a 64 MiB estimated buffer budget, and a 2048 MiB output file limit. The reservation covers geometry, sampling, blending, source section assembly, and tile export buffers. It uses `64 KiB + 1024 × output pixels` and adds `64 × source pixels + 512 × source rows` for one source window. Over-budget tiles split before the oversized allocation or read. FITS sections use ordinary reads, and the writer keeps a single disk-backed output with space checked before rendering. The Windows process counters also include imported libraries and their allocations. [Memory counters](https://learn.microsoft.com/en-us/windows/desktop/api/psapi/ns-psapi-process_memory_counters)

The CLI defaults OpenBLAS to one thread before scientific imports, honoring an explicit `OPENBLAS_NUM_THREADS` setting. On the development host the inherited `OMP_NUM_THREADS=20` produced about 1317 MiB of process commit by the time NumPy and SciPy loaded. With one OpenBLAS thread, the same imports committed about 96 MiB before rendering.

The benchmark used Windows 11 x64 build 26200, CPython 3.13.18, and an Intel Core i5-14600K. Each fresh process rendered two 2048 × 1536 float32 `L` panels with a 768-pixel overlap onto a 3328 × 1536 grid, using the same center and scale as the small fixture. The samples were `(x % 17) − 8 + ((y % 13) − 6) / 2` in global coordinates, plus 2 for the second panel. Weights were 1 and 3. Timing starts after imports, and OS file cache state was uncontrolled. CFITSIO verified all 5,111,808 output pixels and all coverage values per run against the formula. Each export occupied 25,565,760 bytes.

| Working buffer budget | Tiles | Peak reservation | Peak working set | Peak commit | Render time |
| --- | ---: | ---: | ---: | ---: | ---: |
| 64 MiB | 312 | 17.125 MiB | 89.0 MiB | 101.5 MiB | 4.70 s |
| 6 MiB | 1248 | 4.344 MiB | 85.7 MiB | 97.2 MiB | 6.80 s |

On the same workload a progress callback requested cancellation at 524,288 written pixels. Cancellation and cleanup completed in about 2.0 ms from that tile boundary. The tests also verify handle release, retry, insufficient budgets, and a destination publication race. [Job tests](../tests/integration/test_mosaic_job.py)

The [Phase 3A reference](phase-3a.md) adds linear mono and RGB TIFF input and output. The Phase 4 benchmark will revisit memory and disk budgets for 12 panels at 6000 × 4000. [Open topics](../questions_open_topics.md)
