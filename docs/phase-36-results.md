# Phase 3.6 Implementation and Windows Evidence

- **Date:** 2026-11-18
- **Scope:** Shared local solver, catalog selection, quality and recovery, spatial distortion checks, budgets and desktop/CLI integration.
- **References:** [Phase plan](phase-36.md) · [Capability baseline](phase-36a.md) · [Frozen fixtures and thresholds](../tests/fixtures/plate_solve_v36.json) · [Historical Phase 3.5 results](phase-35.md#offline-solver-rerun)
- **Host:** Windows 11 Pro x64 build 26200, Intel Core i5-14600K. The local runs used the pinned ASTAP CLI-2026.11.01, D05 epoch 2025, and Seiza 0.48.2 catalog bundle v4-2026-11-15. Times from fresh processes used previously accessed files. Some source measurements overlapped development verification work.

## Behavior

AstroMosaic first reuses valid effective WCS. For a new result it runs the installed ASTAP CLI with a masked mono staging image, followed by local Gaia when ASTAP is unavailable or its candidate fails. Fresh settings use Automatic. The verified CLI chooses the database and AstroMosaic records the actual identity from native output. An explicit D-series choice requires a complete local tile set. When native Auto could choose an incomplete or unsupported set, the adapter passes the densest complete supported D-series name explicitly and reports that decision.

Qualified candidates have at least 15 unique image/catalog associations, angular RMS at or below `max(3 arcsec, 2 × smaller center scale)` and finite, invertible geometry. Gaia also retains its native false-match check. SEP measurements are shared across attempts. The validation uses mutual nearest pairs, robust distance filtering and shifted controls for coincidental matches. The Gaia and D05 verification coordinates both have Gaia lineage. The model holdout excludes its stars from the AstroMosaic fits. The native seed's own fit membership is unavailable.

The application compares TAN, SIP-2 and SIP-3 using the same spatial holdout. It checks original-domain parity and round trips on a 9 × 9 grid. The chosen model is stored in a source- and sky-mask-bound v2 sidecar. Version 1 and embedded WCS remain readable with geometry-only evidence when quality is unavailable. Preview and export use the same chosen WCS while sampling source pixels.

The desktop **Panel → Plate Solve Details** dialog provides model displacement relative to TAN, vector components in the cell tooltips, and a measured residual view in source pixels. A cell with fewer than five catalog stars shows an unavailable residual. Grid samples also record local X/Y scales, anisotropy, shear, and inverse error. **Panel → Revalidate Plate Solution** attaches a new sidecar on success. A failed attempt leaves earlier saved references in place.

## Real-Field Source Checks

| Fixture and mode | Accepted model | Catalog matches | RMS | Held-out whole / outer P95 | Archive center/corner max |
| --- | --- | ---: | ---: | ---: | ---: |
| M13, both backends configured, ASTAP Auto picked D05 | TAN | 164 | 0.442″ | 0.858 / 0.752 px | 0.315″ |
| M13, hinted Gaia G ≤ 15 | TAN | 127 | 0.397″ | 0.677 / 0.653 px | 0.369″ |
| M13, blind Gaia G ≤ 17 | TAN | 478 | 0.388″ | 0.786 / 0.819 px | 0.384″ |
| M42 40′, hinted Gaia G ≤ 15 | SIP-2 | 105 | 0.419″ | 0.725 / 0.878 px | 0.320″ |
| M42 55′, blind Gaia G ≤ 17 | TAN | 553 | 0.288″ | 0.589 / 0.601 px | 0.531″ |

The M13 results passed the corresponding Phase 3.5 archive maxima plus 0.1″. The two successful M42 results were within the earlier two-pixel center and five-pixel grid envelopes. The 40′ M42 cutout still reached the 30-second broad Gaia cap without a solution. The initial trials used D05. The [dense-catalog follow-up](#dense-astap-catalog-verification) repeated the narrow Orion case.

ASTAP with D05 timed out at 25 seconds on M13 with both scale and pointing unset. Four native threads and an unrestricted search that started near the correct pointing also timed out. The native FOV-auto loop solved in about 5.4 seconds when the same pointing had a 3° search radius. In an ASTAP-only setup with both hints supplied, the source policy now uses that local retry, clearing FOV while preserving pointing. The half-scale and double-scale runs passed in 9.76 and 11.38 seconds, including preparation and validation. Without any hints, the 60-second ASTAP-only allowance let D05 recover in 41.38 seconds. All three runs accepted TAN with 161 matches, 0.404″ RMS, 0.550 px held-out edge P95, and 0.337″ maximum archive separation. With Gaia available, ASTAP's recovery clears both hints and retains its 25-second cap. [Recovery decision](phase-36.md#3-ordered-local-solve-policy)

## Owner Wide-Field TIFFs

Both private 6000 × 4000 Nikon D5300 files import 24 mm focal length and nominal 3.9083 µm pixel pitch. Source and portable tests keep the images local and compare original SHA-256 values before and after processing. The source integration solved both from a deliberately wrong position and half-scale hint through the broad Gaia interval of 0.1–120 arcsec/pixel. The automated owner regressions additionally use the double-scale hint on 21.TIF and reopen the selected SIP sidecar against the original WCS geometry.

| Owner TIFF | Accepted model | Catalog matches | RMS | Held-out whole / outer P95 | Measured 9 × 9 cells | Peak modeled displacement |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 20.TIF | SIP-3 | 1352 | 10.786″ | 0.781 / 0.837 px | 73 of 81 | 27.66 px |
| 21.TIF | SIP-3 | 1387 | 10.981″ | 0.764 / 0.874 px | 68 of 81 | 27.52 px |

The last column measures displacement relative to the accepted model's linear TAN component. The edge P95 and measured cells report actual star residuals. Regions below the five-star floor have null measured metrics. Linear skew is the angle between the detector axes in the linear tangent projection minus 90°. Local skew and scales use the sampled sky Jacobian.

## Deadlines and Compatibility

The desktop and CLI start a panel deadline before opening the image. The default is 120 seconds. `--timeout` still limits each native attempt. `--total-budget` and optional `--job-budget` set outer deadlines. The desktop also reports queue and eligibility time. Native Gaia catalog opening, searching and validation use reaped spawn workers. ASTAP owns a disposable scratch directory and polls its native process. Late candidates and late sidecar writes are rejected, and completed panels survive cancellation.

The source numerical tests cover 14/15/16 matches, comparable RMS bounds with unequal scales, duplicate and unrelated catalog cases, RA wrap, parity, known skew, synthetic SIP displacement, sparse edge support and original-domain inversion. The original FITS samples, SIP preview and independent CFITSIO export are checked against the same coordinate mapping. Fake-clock tests cover shared budget arithmetic and late publication. A real sleeping spawn worker covers timeout and cancellation of noncooperative native work. Local I/O checks run at tile and publication boundaries. OS or storage stalls remain visible as timing overruns.

The native Windows trial cancelled a live ASTAP process after 0.2 seconds of searching and took about 0.025 seconds from the cancellation signal to a reaped process and empty scratch directory. The portable CLI tested an expired panel budget during preparation and a 0.05-second native attempt cap. Neither published a sidecar or left staged files.

## Portable Windows Verification

- **Source:** 139 tests passed with native Windows Qt and OpenGL. The active display was G274QPF E2. Ruff, format, mypy and Poetry lock checks passed.
- **CLI:** The copied package ran with only Windows system folders on `PATH`. The worker-spawn and independent FITS, LZW TIFF, Deflate RGB TIFF and PackBits TIFF checks passed. M13 used Auto/D05 when both backends were configured. A missing manual D20 skipped ASTAP and the broad Gaia retry recovered from deliberately wrong pointing and double scale.
- **Desktop:** The copied runtime passed offscreen CPU and native OpenGL acceptance. The checks exercised settings, embedded and attached WCS reuse, foreground exclusion, real hinted Gaia and ASTAP, cancellation of a live ASTAP run, partial completion, retry via scale-free Gaia, project reopen, preview and FITS export.
- **Build:** An earlier build environment lacked the required TIFF codec extension and failed the LZW check. Rebuilding from the locked environment containing imagecodecs 2026.11.11 passed. The build script now checks for the codec extension before creating a bundle.

The portable matrix also repeated ASTAP-only FOV recovery on M13, hinted M42 40′ and blind M42 55′. A supplemental M42 40′ blind run exposed a worker reply racing with the parent closing its pipe at the deadline. The rebuilt CLI returned normal timeout reports with empty stderr and no sidecars at both 2.5- and 6-second attempt limits. A focused regression covers the closed pipe.

The portable CLI read both original TIFFs locally and accepted the same SIP-3 geometry as the source check. The 0.5× trial on 20.TIF took 44.551 seconds and the 2× trial on 21.TIF took 41.166 seconds, including ASTAP attempts. The raw images retained their SHA-256 values. Each selected sidecar drove a 128 × 96 RGB TIFF export. Independent reopening confirmed all 12,288 pixels were covered and the output center matched the chosen geometry.

| Portable owner result, checked against D05 | Independent matches | RMS | Whole / outer P95 |
| --- | ---: | ---: | ---: |
| 20.TIF | 1425 | 12.917″ | 0.797 / 0.895 px |
| 21.TIF | 1461 | 13.134″ | 0.847 / 0.985 px |

The D05 comparison evaluates stored coordinates without refitting. It provides a second catalog check of the selected geometry. These matches share Gaia source lineage and their native-fit membership is unknown.

## Dense ASTAP Catalog Verification

The Windows follow-up used source revision `3bc1807`, the corresponding copied console bundle and the pinned ASTAP CLI-2026.11.01. Each dense set contained 1,476 Gaia DR3 tiles at epoch 2025. The test folders contained single sets, D05 with D20, all four D-series sets, or all four with one D80 tile omitted. The D50 and D80 Debian archives supplied the same portable `.1476` data format for the Windows CLI. Only their catalog tiles were extracted.

| Catalog | Upstream archive | Verified SHA-256 |
| --- | --- | --- |
| D20 | [ZIP](https://sourceforge.net/projects/astap-program/files/star_databases/d20_star_database.zip/download) | `c1cb092cb47563ebf095988358746e0c905a16f6a9b860152bc1caf10b788252` |
| D50 | [Debian package](https://sourceforge.net/projects/astap-program/files/star_databases/d50_star_database.deb/download) | `f3afbd345c05685c2ea3988f584f08f8ded8a9760f73c111f988d1fa2a2cc39e` |
| D80 | [Debian package](https://sourceforge.net/projects/astap-program/files/star_databases/d80_star_database.deb/download) | `fda9ecd2f43969b3b2a767e36be472c3661e521e4d3fb8549216f8ff521b616e` |

The M13 55′, M42 40′ and M31 40′ trials used primary-only FITS samples and compared each saved WCS with the corresponding DSS archive at the center and four corners. The M31 fixture uses the complete 2376 × 2381 archive raster from Phase 3.5, copied into a new primary HDU with no pointing or WCS. All six source and archive hashes matched their pre-run values. The accepted rows used TAN and supported held-out edges. Times measure the panel job through sidecar publication on the development host. Some checks ran concurrently.

| Field and source CLI case | Catalog | Matches | RMS (″) | Held-out whole / outer P95 (px) | Archive maximum (″) | Panel time (s) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| M42 40′, single catalog, supplied hints and local FOV recovery | D20 | 282 | 0.332 | 0.625 / 0.592 | 0.349 | 2.77 |
| M42 40′, single catalog, supplied hints and local FOV recovery | D50 | 401 | 0.341 | 0.876 / 0.783 | 0.372 | 2.72 |
| M42 40′, all catalogs, manual D50 and local FOV recovery | D50 | 401 | 0.341 | 0.876 / 0.783 | 0.372 | 2.52 |
| M31 40′, single catalog, pointing and scale | D20 | 504 | 0.341 | 0.559 / 0.528 | 0.325 | 2.02 |
| M13 55′, D05 and D20 installed, manual D05 | D05 | 164 | 0.442 | 0.858 / 0.752 | 0.315 | 4.03 |
| M13 55′, D05 and D20 installed, native Automatic | D20 | 808 | 0.451 | 0.724 / 0.673 | 0.452 | 4.25 |
| M13 55′, all catalogs, native Automatic and local FOV recovery | D80 | 1282 | 0.401 | 0.845 / 0.784 | 0.450 | 8.85 |

- The 40′ Orion field needed usable pointing and a supplied scale to enter local FOV recovery in these ASTAP-only runs. Doubling the scale hint still recovered the same D20 solution in 2.43 seconds. With both hints absent, D20, D50 and D80 exhausted the 60-second native search cap in about 60.25, 60.25 and 60.24 seconds of panel time. M31 with D20 also reached the cap in 60.22 seconds.
- For Orion with every set present, native Automatic selected D80 during recovery. Its held-out whole-field P95 was 1.02 px, above the 1.0 px limit. The candidate was rejected and the job returned no sidecar. D80 alone and manual D80 in the mixed folder reproduced the rejection. D80 alone solved M13 with the same metrics as the mixed-folder run.
- With `d80_3601.1476` omitted, Automatic selected complete D50 explicitly and solved Orion with the same D50 metrics. Manual D80 reported the missing tile and skipped native search. With D50 alone and manual D80 selected, the job reported that there were no D80 files. Neither manual failure published a sidecar.
- The copied console repeated the D20 and manually pinned D50 successes, the native D80 quality rejection, both incomplete-D80 outcomes and the blind D50 timeout. All tested CLI runs cleaned their scratch folders. The native desktop selected D50 through **Plate Solve Settings** with all four sets present, restored the selection on reopening the dialog, solved Orion and saved its sidecar reference. The desktop and dialog opened on the second display. CFITSIO reopened the 128 × 96 export with all 12,288 pixels covered. Samples agreed with independent bilinear interpolation within 0.002 ADU.
- The alternate Windows x64 executable reported CLI-2026.09.19, SHA-256 `10022ab8b5bcbe448ddfbdc7a12a3d6c99b714ae321ddd1f630de33854f6c252`. AstroMosaic resolved Automatic explicitly to D20 in the D05/D20 folder. M13 passed with 790 matches, 0.361″ RMS and 0.434″ maximum archive deviation in 4.32 seconds. The alternate CLI returned no Orion candidate with either correct or doubled scale. [Upstream archive](https://sourceforge.net/projects/astap-program/files/windows_installer/older%20versions/astap_command-line_version_win64%20v2026.10.19.zip/download)
- The native D20 M13 result passed the common catalog and edge checks. Its 0.452″ maximum archive deviation is slightly above the original hinted ASTAP D05 result of 0.351″ plus the frozen 0.1″ allowance. The repeated D05 result met that envelope. Track cross-catalog repeatability and the D80 Orion rejection under [Q-016](../questions_open_topics.md#q-016---plate-solve-quality-incorrect-scale-recovery-and-distortion).

To repeat the Orion check, use the [unsolved Phase 3.5 fixture](phase-35.md#m42-offline-astrometry-and-documents-catalogs) and point the CLI at a local directory containing the selected catalog's tiles. The example pins D50 in the mixed test directory.

```powershell
poetry run python -m astromosaic solve output/phase35c/m42/m42-no-wcs.fits --astap .tooling/astap/cli/astap_cli.exe --astap-catalog .tooling/phase36-dense/all --astap-database d50 --hint 83.82227830552856 -5.391041688918124 --scale 1.007233325874722 -o output/m42-dense-d50.wcs.json
```

Use `--astap-database auto` to exercise selection. For a blind run, omit `--hint` and `--scale` on an input with no embedded pointing or scale. Use a new destination for each run. The test folders and raw reports are local under ignored `.tooling/phase36-dense/`.

## Reproduction

Run the normal source test suite. The optional private owner TIFF and Seiza cases run when their pinned paths are available.

```powershell
poetry run pytest -q
poetry run python -m astromosaic solve .tooling/phase2-solve-evidence/m13-primary.fits --astap .tooling/astap/cli/astap_cli.exe --astap-catalog .tooling/astap/catalog --hint 250.42 36.46 --scale 0.50345
poetry run python -m astromosaic solve tests/21.TIF --gaia-catalog .tooling/phase2-gaia/stars-deep-gaia17.bin --gaia-index .tooling/phase2-gaia/blind-gaia16.idx --hint 10 10 --scale 67.2 --require-edge-validation
```

Raw source results are in ignored `.tooling/phase36-source-matrix/`, `.tooling/phase36-astap-recovery/` and `.tooling/phase36-source-preview/`. Locked builds and portable evidence are in `.tooling/phase36-windows/dist/` and `.tooling/phase36-windows/evidence/`.

## Remaining Acceptance

The real D05, D20, D50 and D80 selection matrix passed on the development host. The supported hint requirements for the 40′ M42 field are documented above. Further quality work covers the catalog-dependent Orion rejection, cross-catalog repeatability and additional sparse fields. The ASTAP GUI executable, W08/G05 validation and the separate clean-machine check remain outside the verified matrix. [Open topics](../questions_open_topics.md)
