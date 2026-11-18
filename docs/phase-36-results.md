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

The M13 results passed the corresponding Phase 3.5 archive maxima plus 0.1″. The two successful M42 results were within the earlier two-pixel center and five-pixel grid envelopes. The 40′ M42 cutout still reached the 30-second broad Gaia cap without a solution. A compatible denser ASTAP catalog was unavailable for that case. [Q-015](../questions_open_topics.md#q-015---offline-solver-coverage-on-the-40-orion-field)

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

## Reproduction

Run the normal source test suite. The optional private owner TIFF and Seiza cases run when their pinned paths are available.

```powershell
poetry run pytest -q
poetry run python -m astromosaic solve .tooling/phase2-solve-evidence/m13-primary.fits --astap .tooling/astap/cli/astap_cli.exe --astap-catalog .tooling/astap/catalog --hint 250.42 36.46 --scale 0.50345
poetry run python -m astromosaic solve tests/21.TIF --gaia-catalog .tooling/phase2-gaia/stars-deep-gaia17.bin --gaia-index .tooling/phase2-gaia/blind-gaia16.idx --hint 10 10 --scale 67.2 --require-edge-validation
```

Raw source results are in ignored `.tooling/phase36-source-matrix/`, `.tooling/phase36-astap-recovery/` and `.tooling/phase36-source-preview/`. Locked builds and portable evidence are in `.tooling/phase36-windows/dist/` and `.tooling/phase36-windows/evidence/`.

## Remaining Acceptance

The local source and package checks passed. The real catalog matrix currently covers D05. Tests simulate complete and incomplete D20, D50 and D80 sets. A real dense-catalog installation and the narrow blind M42 case remain open. The ASTAP GUI executable, W08/G05 validation and the separate clean-machine check remain outside the verified matrix. [Open topics](../questions_open_topics.md)
