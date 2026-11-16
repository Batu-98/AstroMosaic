# Phase 2 Astronomy Reference

The original checks and results below are the baseline for [Phase 3.5 astronomy engine revalidation](../astro_mosaic_python_first_architecture_en.md#phase-35-astronomy-engine-revalidation).

## Acceptance Fixtures

Fix the following thresholds for the named synthetic cases before tuning the fit. Stellar and extended-signal checks use generated truth independent of the fitting code. The offline solver checks use the public M13 DSS sample and archive provenance from Phase 0. [Phase 0 solver experiment](phase-0.md#offline-astap-experiment)

| Case | Acceptance |
| --- | --- |
| Three overlapping mono panels, with the first and third connected through the middle panel | Anchor the first panel. Held-out relative alignment 95th-percentile error below 0.5 output pixels. Report median and RMS separately from catalog matching residuals. |
| Common isolated stars with different panel gains, known shifts, and noise | Relative gain error below 1% against injected gains. Verify recovered aperture flux of an independent isolated star to 1% in the final mosaic. |
| Isolated star profile in the corrected final mosaic | Centroid within 0.12 pixels on each axis, moment-derived FWHM within 8%, ellipticity within 0.05, and outer annulus residual above −0.2 brightness units for the named bilinear fixture. |
| Additive gradients and shared faint emission | Evaluate an independent faint emission injection against the known sky with at most 5% aperture-flux bias. Accept a plane only with enough spatial support and improved held-out overlap error. |
| A mixed panel with a supplied binary sky mask | Bright terrestrial features are excluded from source detection, fitting, and rendered science pixels. A nominal sky pixel supported only by masked samples is uncovered. |
| Weak or disconnected panels | Identify insufficient evidence and disconnected components without publishing a forced relative calibration. |
| Offline astrometry on Windows | Validate primary WCS reuse, Gaia DR3, hinted and blind ASTAP, and ordered fallback diagnostics. Check cancellation, exhausted cases, and original input bytes. Record real solver evidence by catalog and binary version. |

The [generated panels](../tests/numerical/phase2_reference.py) use deterministic Gaussian stars and 0.035 brightness-unit noise in a 360 × 144 ICRS TAN reference. The 176-pixel-wide panels begin at x = 0, 86, and 184. Their WCS offsets, relative gains, and additive coefficients are declared in the fixture. The center panel has a supplied horizon mask and bright foreground. The isolated test star lies outside the overlaps. A control image uses identical noise and stellar data with the faint emission removed so the recovered emission can be evaluated independently.

## Offline Solvers

`astromosaic solve` attempts existing WCS, Gaia DR3, hinted ASTAP, and blind ASTAP in that order. Existing WCS is checked for explicit celestial geometry and a valid round trip. Explicit pointing and scale hints take precedence over numeric FITS `RA`, `DEC`, and `PIXSCALE` values. Gaia requires a local catalog and either pointing plus scale or a matched blind index. The Gaia match check uses at least eight stars, false-match probability at most 0.001, and RMS at most two fitted source pixels. ASTAP's FITS WCS and status cards must agree. [Seiza API](https://pypi.org/project/seiza/0.48.2/) · [ASTAP command-line guide](https://www.hnsky.org/astap.htm#astap_command_line)

Use an optional unscaled byte FITS primary image of identical dimensions for `--sky-mask`, with 1 for sky and 0 for exclusion. Gaia takes masked SEP centroids. ASTAP receives a temporary float32 image whose excluded samples are filled with a single sampled sky level. A masked panel contributes only sky samples to the exported mosaic. A successful solve can be saved with `-o panel.wcs.json` and consumed by `mosaic --wcs 1=panel.wcs.json`. Reuse requires the source and optional mask fingerprints to match. An exhausted chain exits with a nonzero status and structured stage diagnostics.

### Catalog setup and updates

Install the optional binding with `poetry install -E gaia`. Install the chosen local files separately with the upstream fetch utility, which checks SHA-256 against its versioned manifest. For example, the following installs the deep Gaia catalog and its blind index under the ignored `catalogs/` directory. Use the paths printed by the command in `--gaia-catalog` and `--gaia-index`.

```shell
poetry run python -c "import seiza; print(seiza.fetch_catalogs(['stars-deep-gaia17.bin', 'blind-gaia16.idx'], cache_dir='catalogs/gaia'))"
```

For a smaller hinted installation, fetch `stars-gaia.bin` and supply pointing and scale. Use one manifest version for the deep catalog and index. Install updates in a separate directory, verify sizes and hashes, rerun the reference solve, and then switch both configured paths together. Keep the previous files available for reproducible runs. Install ASTAP and its star database separately and use the archive hashes from Phase 0 for the tested D05 install. [Versioned Gaia manifest](https://downloads.seiza.fyi/data/v4/manifest.json) · [Seiza catalog setup](https://github.com/theatrus/seiza/blob/v0.48.2/docs/catalogs.md) · [ASTAP reference downloads](phase-0.md#offline-astap-experiment)

### Windows solver evidence

Windows 11 x64 with CPython 3.13.18 and Seiza 0.48.2 tested the v4 Gaia bundle dated 2026-11-15. The catalog and index files matched manifest byte lengths and SHA-256 values. The test used a primary-image-only copy of the M13 DSS archive with pointing and WCS removed. The original archive and the staged source remained byte-identical to their pre-run state.

| Solver and data | Matches | Internal RMS | Center error versus archive WCS | Maximum error at five samples |
| --- | ---: | ---: | ---: | ---: |
| Seiza hinted, Gaia DR3 G ≤ 15 | 132 | 0.469″ | 0.317″ | 0.367″ |
| Seiza blind, Gaia DR3 G ≤ 17 and G ≤ 16 index | 482 | 0.413″ | 0.364″ | 0.406″ |
| ASTAP 2026.11.01 hinted, D05 | — | — | 0.357″ | 0.531″ |
| ASTAP 2026.11.01 blind, D05 | — | — | 0.395″ | 0.573″ |

A deliberately incorrect position led to Gaia and hinted ASTAP failures, followed by a successful blind ASTAP result. Missing Gaia and ASTAP data produced an unsolved result with no sidecar. A real ASTAP process stopped and its staging directory was removed within about 166 ms of a cancellation request. Masked real-image staging solved an M13 copy with an injected bright foreground and left that input unchanged. Automated tests exercise valid-WCS reuse, ordered failure, timeout and cancellation, exhausted catalogs, and sidecar reimport. [Offline integration tests](../tests/integration/test_offline_solve.py)

On the development host, the unhinted Gaia reference solve took 4.68 s after scientific imports in one run with a previously accessed index. With one OpenBLAS thread it peaked at 1066 MiB working set and 281 MiB process commit, including native catalog access. The working set after return was 105 MiB. These are separate from the 64 MiB estimated tile buffer budget. [Windows process memory counters](https://learn.microsoft.com/en-us/windows/desktop/api/psapi/ns-psapi-process_memory_counters)

## Relative Refinement

For compatible, unstretched mono inputs, `mosaic --refine` measures local SEP centroids and background-subtracted aperture fluxes, rejects blends and stars above a declared FITS `SATURATE` level, and accounts for the local pixel solid angle in flux matching. The overlap graph starts from sampled full-WCS boundaries. Mutual star matches supply robust relative translations and log-gain ratios. The first input anchors the fit, and held-out matched stars measure alignment and gain error. The output reports weak or disconnected graphs and declines the refined export in those cases.

The correction fits small translations in the chosen ICRS TAN output grid. The original full source WCS, including any supplied SIP terms, supplies the base geometry. Background fitting uses paired sky samples in source coordinates after stellar gain matching. It anchors the reference panel's background, samples away from detected objects, and uses held-out residuals to choose a constant offset. With `--background plane`, a spatially supported plane with slope regularization must improve held-out error by at least another 15%. The renderer applies the accepted corrections as it samples each original panel and records them in FITS history and the JSON diagnostic report. The absolute sky background remains undetermined.

The input buffers, star extraction, and background sampling use bounded windows. The CLI sets one OpenBLAS thread by default. The estimated buffer budget covers AstroMosaic allocations. The native Gaia catalog mappings and external ASTAP process have their own working sets.

### Refinement evidence

| Case | Result |
| --- | --- |
| Three-panel injected reference | 5 held-out stars, alignment median 0.00034 px, RMS 0.00038 px, P95 0.00056 px. The largest fitted gain error versus truth was 0.031%. |
| Relative gradients and faint emission | Held-out median background difference fell from 2.119 to 0.029 brightness units. The injected emission aperture recovered 101.93% of expected flux. |
| Isolated stellar profile | Aperture flux recovered within 1%. Centroid, width, ellipticity and outer-annulus residual met the fixture limits. |
| Offset-only control, mixed sky, and unsupported graphs | The offset model beat the unsupported plane, output pixels and coverage agreed across tile sizes, the horizon gap stayed uncovered, and weak/disconnected jobs produced diagnostics. |
| Two 900 × 880 DSS cuts with injected shift, gain and offset | Seventeen held-out stars gave median 0.0047 px, RMS 0.0175 px and P95 0.0396 px. Fitted gain was 1.12002 for 1.12 injected. Held-out background differences fell from 26.92 to 0.51 ADU. |

[Numerical and failure-case tests](../tests/numerical/test_refinement.py)

## Windows Development Bundle

The one-directory PyInstaller build used a clean Windows x64 environment with the locked `main,build` groups and `gaia` extra. It copied AstroMosaic and Seiza package metadata. From an unrelated working directory the frozen CLI ran real hinted Gaia and ASTAP solves, saved and reimported a masked WCS sidecar, rendered the three-panel refinement, and passed the spawned smoke job. CFITSIO independently reopened the refined FITS and coverage. Qt, `fitsio`, ASTAP, and catalog data were outside the bundled runtime.

The source suite passed 37 tests, Ruff lint and format, mypy, and Poetry lock validation. The [Phase 3A reference](phase-3a.md) extends the headless workflow to mono and RGB TIFF.
