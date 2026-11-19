# AstroMosaic application test findings

Review date 2026-11-19. This report covers the five base cases, the ten extended cases, and the local owner-supplied PA4 retest. It records the evidence and proposes implementation work for follow-up on Windows 11 x64.

## What the tests established

| Test set | Observed result | What it establishes |
| --- | --- | --- |
| Five base cases | All five passed in the source CLI, portable CLI, and native desktop with CPU and OpenGL previews. The ten standard exports matched across launchers. Two display stretches produced identical scientific output. | Saved geometry, mask editing, independent layers, and the separation of display stretch from export worked for these fixtures. |
| Ten extended cases | All ten passed through the same four paths. Each path exported 18 products. The 54 comparisons against source CLI products matched samples, coverage, layer contributions, and applicable WCS and filter metadata. | The tested paths agree for narrow overlaps, polar and skewed views, wide SIP imagery, scaled FITS, XISF coverage holes, filter bands, and three additional nightscapes. |
| PA4 sky | The two-panel TAN and 15-panel ZEA TIFFs matched the CPU desktop exports exactly. CPU and OpenGL previews completed. The independent check compared 9,472 covered positions within 0.002 DN. All 23 original TIFF hashes matched. | The renderer can combine this real wide-angle sequence once validated WCS is available. |
| PA4 recovery | Gaia accepted 15 of 23 frames. The eight horizon frames remained excluded from the ready sky mosaic. ASTAP produced one additional standard-gate TAN candidate, which failed the required-edge retry. Foreground alignment reported disconnected groups for the tested mask sets. | Plate-solve recovery and terrestrial overlap are the two unresolved steps for adding the horizon frames to a mixed mosaic. The foreground rejection verified error handling. |

The extended suite compared 27,988 covered sky samples against independent interpolation or weighting. It also verified finite signed samples, covered zero, above-one values, uncovered pixels, and band-local metadata. Keep these outputs as regression references when changing the solver, renderer, or UI. For sky geometry, the reference-grid comparisons measure export-coordinate consistency. Catalog residuals and held-out matches measure astrometric accuracy. [Base acceptance criteria](application-tests.md#per-case-acceptance) · [Extended acceptance criteria](application-tests-extension.md#acceptance-by-case)

The 15 standard cases include 12 synthetic fixtures, two cases with distinct 2MASS atlas tiles, and a case made from two crops of one Paranal panorama. The three-scan atlas chain connected through measured sky overlaps of 11.57% and 12.01%. The panorama crop result is a foreground translation control with real texture. PA4 supplies the independently acquired mixed-scene challenge. [Reference data and attribution](application-tests.md#source-credits-and-fixture-limits) · [Extended fixture inputs](application-tests-extension.md#prepare-the-fixtures)

## Recommended software work

The [Phase 6 plan](phase-6.md) defines the diagnostic work and real-data baselines. The [Phase 7 plan](phase-7.md) uses those ground measurements to develop and verify terrain control points and panorama geometry. Both phases use real observations for every follow-up test.

| Priority | Work | First implementation step |
| --- | --- | --- |
| P1 | Explain real foreground alignment failures | Add per-pair rejection reasons and source panel names to the existing alignment result. |
| P1 | Improve plate-solve recovery on masked wide fields | Separate search, catalog resource, association, and edge-support failures in the panel report. Reuse the measurements to test a bounded catalog-query change. |
| P2 | Diagnose wide ZEA preview warnings and runtime | Replay the warning from a real PA4 tile and measure coordinate mapping, source reads, and preview delivery. |
| P2 | Reproduce the native multi-window process exit | Record worker and window lifetimes around close and reopen. |

### Foreground alignment and mask feedback

**Observed.** The saved foreground controls recovered known translations within 0.5 source pixels per axis. The gap composition produced zero common coverage and retained separate sky and foreground contributions. PA4's six-panel ground group produced six singleton groups. The two separately tested pairs also produced disconnected results. A read-only replay of the saved six-panel project measured the existing thumbnail matcher on all 15 pairs. Each pair had candidate shifts that met the masked support and texture checks. The best eligible correlations ranged from 0.236 to 0.522 against the 0.72 threshold. All 15 pairs stopped at that gate. [Foreground implementation](../src/astromosaic/pipeline/foreground.py) · [Independent layer design](adr/0015-independent-layer-rendering.md)

**Change.** Make the existing matcher report a compact record for each evaluated pair. Include source panel identifiers, valid masked support, the peak and competing peak when available, and the rejection stage. Show the selected pair and its masks from the desktop failure result. Keep the current translation fit and thresholds during this diagnostic change. The 10% fixture-overlap rule measures preparation coverage. The ground matcher applies its own minimum of 18% of the smaller valid thumbnail support, with a floor of 24 samples, followed by texture, correlation, ambiguity, and refinement checks. Show the measured quantities and applicable threshold with their units. [Foreground matcher](../src/astromosaic/pipeline/foreground.py) · [Source mask design](adr/0014-source-coordinate-mask-grid.md)

**Acceptance and follow-up.** Apply the diagnostics to PA4 and independently captured translation and negative controls. Verify the expected current-model results and record the effective masks, pair outcomes and identifiable overlap. Use that evidence for Phase 7A's expanded point annotations, held-out split and model comparisons. [Phase 6B acceptance](phase-6.md#6b-explain-foreground-alignment-rejections) · [Phase 7A](phase-7.md#7a-freeze-the-reference-and-diagnose-pa4)

### Plate solving on masked wide fields

**Observed.** In the Gaia retest, three horizon frames produced no verified hypothesis. Four failed held-out residual limits and one failed the catalog RMS limit. The ASTAP D50 verifier exceeded its retained star budget in three frames. With D05, one of those frames failed the shifted chance-match control and one failed the held-out whole-field criterion. The third produced a standard-gate TAN result with 292 unique matches and 33.15 arcseconds RMS. Its outer support was insufficient and its mandatory-edge retry rejected it. This distinguishes search recovery, reference-query capacity, association confidence, and field-edge validation. [Frozen solve policy](phase-36.md#2-frozen-36a-decisions-and-values) · [Shared solver design](adr/0017-astap-first-validated-solving.md)

**Change.** Extend the existing Plate Solve Details and attempt reports so the user can identify the stage, effective hints, catalog, and quality gate for a rejected or partially supported result. Retain the measured region view and identify where edge evidence is insufficient. For the D50 resource failure, instrument the existing regional queries with per-region detected, decoded and retained counts, area, bytes and time. Then test narrower detection-bearing subregions or bounded pre-retention filtering that preserves association margins and shifted controls. The current association code already divides wide fields into cells and prunes catalog stars after projection. The ASTAP adapter can hit its retention cap before that pruning executes. [ASTAP validation and budgets](../src/astromosaic/astrometry/solve.py) · [Regional association](../src/astromosaic/astrometry/solve_validation.py) · [Existing desktop details](../src/astromosaic/ui/plate_solve_details.py)

**Acceptance and follow-up.** Repeat PA4, the real narrow-field M13/M42 controls, and the retained wide-field observations with the same baseline gates. Record whether each D50 candidate reaches association under the existing byte and deadline budgets and report its downstream quality result. Any new strict-edge acceptance must meet the current held-out P95 limits of 1.0 source px overall and 1.5 px at supported edges. Mask edits must retain source-bound WCS provenance and invalidate a stale sidecar when sky selection changes. Capture which of the eight frames recovered and their edge support before changing the ready mosaic. [Real-field baselines](phase-36-results.md#real-field-source-checks) · [Phase 6C acceptance](phase-6.md#6c-diagnose-and-improve-masked-plate-solve-recovery)

### Wide ZEA diagnostics and preview performance

**Observed.** The 15-panel ZEA preview emitted an Astropy all-NaN-slice warning while completing with coverage. In this run, that preview took 30.86 s with the CPU viewport and 28.47 s with OpenGL. The CLI export at 2097 × 2071 took 80.84 s and reported about 73.5 MiB of peak tracked render reservations. Its 26.9 million rejected coordinates count unusable per-panel mapping attempts, and its exported coverage was 3,238,763 pixels. This run gives a baseline for profiling the same manifest. [Panel inverse and round-trip checks](../src/astromosaic/geometry/__init__.py) · [Tiled mapping and footprint selection](../src/astromosaic/pipeline/mosaic.py)

**Reproduced.** The first 128 × 128 tile of the saved PA4 ZEA output contains 16,384 finite directions, all outside PA4-10's TAN hemisphere. Its third-order SIP inverse received an all-NaN core projection and triggered the warning. The real-data replay also covers mixed batches and the ZEA rim. [6D observations](phase-6.md#local-zea-geometry-and-performance-results)

**Change.** Filter nonfinite core projections before the shared distortion inverse. The full-size profile identified panel mapping as the major export cost. Conservative spherical bounds cut evaluated ZEA panel/tile mappings from 4,335 to 1,086 on PA4. [ZEA footprint decision](adr/0024-conservative-zea-footprints.md)

**Result.** The guarded replay and export completed without the Astropy warning. Both full render paths and the 6A reference matched for samples, coverage and WCS. The independent grid, cropped exports and native preview profiles are recorded in the 6D report. [Phase 6D results](phase-6.md#local-zea-geometry-and-performance-results)

### Native desktop lifecycle and release acceptance

**Observed.** Early base-suite automation hit a timeout and later exited with Windows exception `0xc0000409` when moving between separate windows. The reduced M17 and ALPACA replay reproduced the exception on CPU and OpenGL when replacing the old window before its export worker finished cancelling. Qt reported destruction of a running `QThread`. The local 6E matrix ran on one display. [Desktop automation issue](../questions_open_topics.md#q-022---native-desktop-test-automation-process-exits) · [Earlier packaged Windows evidence](phase-3f.md#windows-evidence)

**Result.** Retaining the window through accepted close allowed workers to finish before window destruction. An independent normal OpenGL warning led to explicit release of its resources during close. Eight source and frozen desktop sequences passed the native transitions and same-path retry checks. The clean-machine run remains pending for the recorded ZIPs. [Window and job lifecycle](../src/astromosaic/ui/project_window.py) · [6E results](phase-6.md#local-windows-lifecycle-and-package-results)

The application test matrix used the local 0.1.0 portable console candidate. Build the intended desktop and console release bundles from the matching release source for the clean Windows 11 x64 check. On a fresh system, check normal project opening, a sky export, and independently reopened foreground and composition exports. Repeat visible window and dialog placement on a second monitor when that configuration is available. Record the build, display setup, dependency environment, and outcomes. [Phase 6E acceptance](phase-6.md#6e-verify-native-lifecycle-and-windows-packages) · [Windows release procedure](windows-release.md)

## Follow-up test set

Use real observations exclusively for all follow-up tests. Start Phase 6 with PA4, the archive sky controls, an independently captured mixed case for the existing translation model, and a real low-texture or disconnected pair. Carry those results into Phase 7 and add the independent geometry and holdout controls described there. Keep owner images and raw run artifacts local. [Phase 6 test data](phase-6.md#test-data-requirement) · [Phase 7 real-data controls](phase-7.md#real-data-and-acceptance-measurements)

## Local evidence

The run directories sit under `output/application-tests/` in the development workspace. The report and log names below identify the evidence used for each finding.

| Run directory | Evidence |
| --- | --- |
| `20261119-110157-116/` | `test-report.md`, `independent-all.jsonl`, `full-overlap.jsonl`, `initial-automation-exits.log` |
| `extended-20261119/` | `test-report.md`, `cross-entry-point.json`, `source/results.json`, `diagnostics.json` |
| `pa4-retest-20261119-1145/` | `test-report.md`, `index.json` and 60 individual logs, including the foreground group, the D05 standard and strict-edge attempts, both sky exports, and native preview results |
