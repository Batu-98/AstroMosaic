# Phase 6 Real-Observation Reliability and Windows Acceptance

**Status** Stages 6A–6D and the local portion of 6E passed on Windows 11 x64. The [mixed control](#calibrated-alpaca-mixed-reference) has independently checked sky geometry and all three layer exports. The [masked solve replay](#local-masked-solve-results) measured the eight excluded horizon panels. The [ZEA replay and profiles](#local-zea-geometry-and-performance-results) cover the corrected PA4 warning and both native preview backends. The [6E results](#local-windows-lifecycle-and-package-results) identify the candidate that needs fresh-installation acceptance. Use the [foreground evidence](#local-foreground-diagnostics-results) for Phase 7A. [Architecture milestone](../astro_mosaic_python_first_architecture_en.md#104-phase-6-delivery-stages) · [Application test findings](application-test-findings.md)

## Test Data Requirement

**Use real observational data exclusively for every Phase 6 test.** This applies to reproductions, automated and manual regressions, benchmarks, and acceptance on source and portable builds. Use recorded astronomical observations or independently photographed terrestrial scenes. Calibrated exposures, documented crops and format conversions, masks traced on real panels, and coordinates derived during replay of a real project are valid inputs. Preserve the relationship to the original observations and their coordinate systems.

Record the capture or archive identifier, attribution and access terms, input hashes, dimensions, format, and preparation steps. Record mask and sidecar identities, reference measurements, and expected case outcomes with the saved project and test command. Keep owner images, their location metadata, and raw logs in ignored local directories. Publish provenance and aggregate measurements for public cases and use neutral case identifiers for private ones. [Project data rules](../AGENTS.md#9-workspace-care)

| Required case | Real data and purpose |
| --- | --- |
| PA4 sky and horizon row | Use the saved two-panel TAN and 15-panel ZEA projects as export references. Replay the eight excluded horizon frames for solve recovery. Use the six masked ground frames for the 15-pair foreground diagnosis. [PA4 evidence](application-test-findings.md#local-evidence) |
| Independent mixed translation control | Select separately exposed sky-and-ground panels with matching source dimensions, scale and orientation and identifiable terrain overlap. Use a project with verified sky geometry for mixed exports. Include a documented low-texture or disconnected case made from real panels. |
| Archive sky and solve controls | Use M17 and the three-scan 2MASS atlas chain (SKY-01 and SKY-04) for sky export and overlap. Use the established M13 and M42 archive cutouts for narrow-field solve checks. Use the retained owner wide-field TIFFs where permitted for the distorted-field reference. [M17 source](application-tests.md#source-credits-and-fixture-limits) · [Atlas chain](application-tests-extension.md#prepare-the-fixtures) · [Archive baselines](phase-36-results.md#real-field-source-checks) · [Wide-field baselines](phase-36-results.md#owner-wide-field-tiffs) |
| Wide TAN-SIP to ZEA | Reproduce the original warning on the PA4 project and reduce it to an affected tile or documented crop from the same observations. Use the full PA4 ZEA grid for timing and coverage. [Existing timing evidence](application-test-findings.md#wide-zea-diagnostics-and-preview-performance) |
| Native Windows workflows | Use the archive sky project and the independent mixed sequence for window lifecycle and portable sky, foreground, and composition checks. Use the actual candidate binaries for clean-machine acceptance. |

## 6A Freeze the Real-Data Baseline

1. Create a local inventory containing the cases above, their exact versions and hashes, the project grid and mask revisions, and the usable reference products. When reusing the historical application packs, select the real case manifests individually for the test invocations. Record unavailable inputs and their next action under the relevant open topic. Proceed with the stages whose real references are ready.
2. For the translation control, measure the expected X/Y shift from shared real landmarks independently of the aligner. Record the source-pixel measurement method, marking uncertainty, and tolerance for the existing fit. Record the common terrain and expected disconnected groups in the positive and negative controls. Use these measurements as the reference for the current translation model.
3. Record the current source commit, settings, installed solver/catalog versions, Windows build, display backend, and resource limits. Replay the relevant current workflows with the frozen real data. Capture current accepted solves, failed attempts, foreground pair measurements, WCS, coverage, sample comparisons, and input hashes. Record the baseline exports and diagnostic summaries under ignored `output/application-tests/`.

**Acceptance** Each case used for tuning has a repeatable invocation, input identities, measured expectations, and a reference or a documented expected rejection. Record the reference set before changing a matcher, solver, or renderer. [Q-003 and related topics](../questions_open_topics.md#q-003---reference-datasets-and-frozen-acceptance-thresholds)

### Local Baseline Measurements

The 2026-11-19 run used source commit `c0a0190` (`0.1.0b1`), Windows 11 x64 build 26200, CPython 3.13.18, and one OpenBLAS thread. The local `output/application-tests/phase6a-20261119-155643-651/reference-inventory.json` pins the sources, projects, grids, masks, WCS sidecars, catalogs and reference exports. It includes ASTAP CLI-2026.11.01 with D05 and D50, and Seiza 0.48.2 with the Gaia DR3 v4 catalog and blind index. This source replay used the CLI and headless processing. Earlier CPU and OpenGL observations came from the single-display PA4 retest. [Prior Windows evidence](application-test-findings.md#local-evidence)

| Sky case | Reference grid | Covered pixels | Independently checked sample positions | Maximum sample error |
| --- | --- | ---: | ---: | ---: |
| PA4 two-panel TAN | 1460 × 1531 | 1,028,380 | 2,308 | 0.0018854 DN |
| PA4 fifteen-panel ZEA | 2097 × 2071 | 3,238,763 | 7,164 | 0.0018658 DN |
| SKY-01 M17 2MASS atlas | 1024 × 1320 TAN | 969,235 | 5,651 | 0.000161 DN |
| SKY-04 2MASS atlas chain | 1470 × 1330 TAN | 1,422,222 | 8,442 | 0.000170 DN |

PA4 matched the previous coverage and the 0.002 DN sample tolerance. Its 23 original TIFF hashes and eight saved source masks matched. The ZEA export reproduced the all-NaN warning on the full grid in 74.37 s with 73.47 MiB in peak tracked reservations. Its 26,923,967 rejected mapping attempts count per-panel coordinates. Use the recorded grid and inputs to isolate the affected tile in 6D. The two 2MASS FITS exports reopened with `FILTER=Ks`, `BUNIT=DN`, binary coverage and center/corner WCS within 1e-9°. The SKY-04 bright-sample correlations were 0.99961 and 0.97506 across the two connected overlaps. [2MASS provenance and preparation](application-tests.md#source-credits-and-fixture-limits) · [Atlas chain](application-tests-extension.md#prepare-the-fixtures)

The eight PA4 horizon panels repeated the earlier Gaia outcomes of three search failures, four held-out failures and one RMS failure. D50 hit the retained-star budget on the same three panels. The one D05 TAN candidate under the standard gate remained excluded after strict field-edge verification. The baseline also repeated the M13 D05, M42 40′ D50, M42 55′ Gaia and two private wide-field SIP-3 solves within their existing quality limits. The three DSS results agreed with the archive at the center and corners within 0.315″, 0.372″ and 0.531″, respectively. [Existing solver limits and archive provenance](phase-36-results.md)

The saved six-panel PA4 ground variant produced six singleton groups. `pa4-foreground-pairs.json` records the measured shared support and peak correlation for all 15 pairs. The peaks ranged from 0.236 to 0.522 against the 0.72 gate. Use this read-only replay at the recorded source commit for the 6B comparison.

### Independently Exposed Foreground Controls

The ALPACA control uses two 4096 × 4096, 120-second ESO observations, `ALPACA.2023-06-04T04:49:26.740` and `ALPACA.2023-06-04T04:51:28.530`, under program `60.A-9300(B)`. The local `data/application-tests/phase6a-alpaca/reference.json` records archive hashes, source coordinates and masks for the three unresampled 640 × 480 FITS crops. The positive pair includes common telescope enclosure features. The negative pair uses separate enclosures with disjoint terrain support. [ESO instrument and observation access](https://eso.org/cms/eso-archive-news/alpaca-all-sky-images-from-paranal-available-in-the-archive.html) · [ESO archive terms, CC BY 4.0](https://archive.eso.org/cms/eso-data-access-policy.html)

Six independently selected landmarks gave a B-to-A shift of (+47.98, +16.23) source pixels. Local gradient differences measured the positions to subpixel precision. The largest deviations from the medians were 0.20 px in X and 1.27 px in Y, and the per-axis control tolerance is 1.5 px. The saved matcher returned (+48, +16) with 0.992 thumbnail correlation and three agreeing full-resolution patches. The negative control returned two singleton groups. CFITSIO independently verified all 80,158 covered foreground samples and binary coverage, with zero sample difference. The export uses the nominal visible band and a common relative ADU scale for the two exposures.

The archive files use pixel coordinates. The initial masked, hinted Gaia probe returned eight and ten matches. The [independent calibration](#calibrated-alpaca-mixed-reference) used the full exposures to identify the catalog stars and attached checked crop WCS to the mixed project.

### Calibrated ALPACA Mixed Reference

Fit the all-sky orientation and radial projection from Gaia DR3 matches outside the eastern test field. Use that orientation to identify stars in the eastern field, then reserve alternating matches in source X order inside each sky crop. Fit a local TAN-SIP model of order three with the remaining matches and check the reserved identifications in source pixels. Accept an overall held-out P95 of at most 1.0 px and at most 1.5 px for the supported edge sample, with five or more edge matches per crop. [Fisheye calibration method](https://doi.org/10.1051/0004-6361/201935580) · [Gaia catalog setup](phase-2.md#catalog-setup-and-updates)

| Crop | Training stars | Held-out stars | Held-out edge stars | Held-out P95 | Edge P95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| A | 77 | 15 | 7 | 0.363 px | 0.335 px |
| B | 82 | 13 | 7 | 0.410 px | 0.218 px |

The saved mixed project `output/application-tests/phase6b-work/alpaca-mixed/mixed.astromosaic` uses the frozen cropped FITS inputs and masks. The WCS sidecars bind the calibration to the corresponding source and sky mask. Use the previously measured (+48, +16) px foreground alignment. The visual composition uses saved manual placement with a 22% seam band so the retained sky and terrain have common support. The scientific sky grid uses TAN at 140 arcsec/px. The source catalogue identities, validation star coordinates, fitted WCS, results and independent export checks are local to `output/application-tests/phase6b-work/`.

### Repeat the Baseline

From the checkout root, select the public atlas cases individually with the locked Python environment and a fresh output directory.

```powershell
$Python = (Resolve-Path '.venv/Scripts/python.exe').Path
$Run = 'output/application-tests/phase6a-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
$env:OPENBLAS_NUM_THREADS = '1'
& $Python tools/check_application_test_extension.py --case-manifest data/application-tests/sky01-m17-atlas/case.json --output (Join-Path $Run 'sky01')
& $Python tools/check_application_test_extension.py --case-manifest data/application-tests/extended/sky04-atlas-chain/case.json --output (Join-Path $Run 'sky04')
```

On the host with the private PA4 inputs, run `.tooling/run_pa4_checks.py` with the fresh run directory and `sky`, `ground` or `integrity`. The recorded run folder also contains `record_pa4_pairs.py`, `record_pa4_horizon.py`, and `record_solve_controls.py`. Run the pair and solve control scripts from copies in a fresh output folder. Pass the horizon script a new report directory as its argument. Use `prepare_alpaca_control.py --output <new-fixtures>` to rebuild the ESO crops from the cached archive FITS files and `check_alpaca_control.py --fixtures <new-fixtures> --output <new-report-directory>` to replay the ground alignment. These local commands and artifacts stay with the ignored evidence.

## 6B Explain Foreground Alignment Rejections

1. Instrument the existing translation matcher in `pipeline/foreground.py`. For each evaluated pair report panel IDs, usable mask support and its threshold in thumbnail samples, peak correlation, competing peak where measured, full-resolution patch evidence where measured, and the acceptance or rejection stage. Use the existing fit and thresholds with the same memory and cancellation limits.
2. Surface the result through the shared alignment operation and desktop **Align Foreground**. Show the disconnected groups and let the user identify the corresponding panels and inspect their masks. Provide stable reasons for support, texture, correlation, ambiguity, refinement, and graph disagreement when each is applicable. Preserve useful reasons on failure and render with the current saved transforms for already aligned projects.
3. Replay the saved six-frame PA4 group with its original masks and compare all 15 pair scores with the baseline. It measured 0.236–0.522 at the thumbnail correlation gate against the current 0.72 threshold. Inspect effective masks for shared terrain that was omitted or obscured. Compare any corrected mask on a derived project and record the changed mask revision and pair outcomes. Record unresolved geometry questions with the evidence available for each pair.
4. Repeat the real positive and negative controls. Check the accepted translation against 6A and verify the expected disconnected groups. Record resource use and verify that diagnostic collection retains the established cancellation and retry behavior. Check ground alignment without WCS and independently reopen sky, foreground, and composition exports from the mixed control with verified sky geometry.

**Acceptance** The PA4 replay reports all 15 outcomes and their measured stages. The positive control has a connected ground graph and meets the frozen translation tolerance. The negative control reports the expected weak or disconnected overlaps. Saved mask edits reopen correctly, and independent reads verify coverage and layer contributions on the mixed project's exported layers. [Foreground design](adr/0015-independent-layer-rendering.md) · [Q-010](../questions_open_topics.md#q-010---foreground-recognition-masks-and-composition)

### Local Foreground Diagnostics Results

Run **Layers → Align Foreground**, then open **Foreground Alignment Details** to see each panel pair, its measured support and correlation, the competing peak and refinement evidence when available. Select a row and choose **Inspect Mask A** or **Inspect Mask B** to open that source mask. The details include disconnected groups and identify overlaps that disagree with the graph fit. The shared alignment operation emits completed pair records through `on_pair`; graph rejections provide structured panel groups and residuals. Saved foreground geometry and match evidence use the existing project format.

- **PA4** All 15 original peak and support values matched 6A. The matcher rejected each peak below 0.72 and returned six singleton groups. A derived project removed one cell from the boundary of each saved ground mask and reopened with the same sky mask fingerprints. The 15 peaks spanned 0.286–0.637 after the edit, with the same six groups. The saved mask and pair records carry the specific support and scores for each comparison. Shared landmarks, any omitted terrain and depth-dependent motion require further review in 7A.
- **ALPACA** The real positive pair retained (+48, +16) px, a 0.992 peak and a 0.847 competing peak. Three of 20 sampled full-resolution patches matched and agreed. The disjoint pair returned two singleton groups and a 0.570 peak. A saved mask with one retained ground cell reproduced the separate insufficient-support diagnosis. Cancelling after a reported real pair and retrying recovered the same translation and evidence.
- **Resources** The PA4 source replays used the same 128 MiB working setting. Observed process peak working set was 136.5 MiB with the diagnostic callback omitted and 136.7 MiB with it enabled, including Python and native libraries. The separately reopened mixed FITS exports used at most 20.9 MiB of tracked rendering reservations.

| ALPACA FITS export | Grid | Covered pixels | Maximum sample error |
| --- | --- | ---: | ---: |
| Sky | 586 × 550 TAN | 204,293 | 0.001941 DN |
| Foreground | 212 × 427 | 80,158 | 0 DN |
| Composition | 586 × 666 | 246,642 | 0.003281 DN |

CFITSIO independently reopened the exports. Direct bilinear calculations verified coverage, all covered samples within 0.015 DN and the four composition contribution codes. Both layers covered 12,979 common pixels and contributed together to 11,671 pixels. Sky WCS agreed at the center and corners within 1e-9°. Native Windows CPU and OpenGL previews and exports passed on one display. Reopened desktop FITS rasters, masks and headers matched the source CLI products for all three layers.

Run the [focused regression](../tests/integration/test_foreground_diagnostics.py) from the checkout root with `.venv/Scripts/python.exe -m pytest -q tests/integration/test_foreground_diagnostics.py`. The ALPACA and PA4 tests use the local frozen projects. For a fresh calibration run, copy `fit_alpaca_orientation.py`, `fit_alpaca_wcs.py`, `prepare_alpaca_mixed.py` and `check_alpaca_mixed.py` from the local evidence folder to a fresh output folder. Run them from the checkout root in that order. Before the last script, use `astromosaic project export` to export `sky.fits`, `foreground.fits` and `composition.fits` for their corresponding layers beside `mixed.astromosaic`. The original evidence folder also records both native preview runs and the PA4 original and derived mask variants.

### Handoff to Phase 7A

Record the following in the existing local application-test results once the 6A terrain references and 6B diagnostics pass their checks.

- Case and panel identifiers, source hashes and dimensions, available lens and capture information, saved project variants, original and edited mask revisions, and repeatable commands at the recorded software revision.
- The expected translations and tolerances for the positive control, expected disconnected groups for the negative control, observed results, and references to the independently reopened outputs.
- The PA4 pair results, accepted and rejected connections, and notes on verified overlap, mask gaps and open geometry questions. Keep original and edited-mask runs identifiable.

Start [7A](phase-7.md#7a-freeze-the-reference-and-diagnose-pa4) from these records while 6C–6E proceed on their own references. Phase 7A prepares extended correspondence annotations and a held-out split and compares geometry models. [Phase 7 entry conditions](phase-7.md)

## 6C Diagnose and Improve Masked Plate-Solve Recovery

1. Extend the attempt report and **Plate Solve Details** to show the effective pointing and scale hints, resolved backend and catalog, and stage of rejection. Distinguish search failure, resource exhaustion, association confidence, RMS or held-out failure, and insufficient edge support. Show measured error and support where the image has catalog evidence.
2. Instrument ASTAP regional verification before association. Report detections, cone area, decoded and retained catalog stars, bytes read, and elapsed time per region. Replay the three D50 resource failures on the PA4 horizon row. Use the observed distributions to test tighter detection-bearing subregions or bounded filtering before retention. Preserve search margins, unique association, shifted chance-match controls, and the existing caps of 100,000 retained stars per cone and 64 MiB read per candidate validation.
3. Rerun the eight horizon frames and the real M13, M42, and wide-field controls with the saved catalog and hint settings. Measure which D50 candidates reach association and which satisfy the downstream quality checks. Preserve the Phase 3.6 match floor of 15, the RMS policy, the measured narrow-field envelopes, and the default 120-second total panel deadline. Apply the current strict-edge support and held-out P95 limits of 1.0 source pixel overall and 1.5 pixels at supported edges to any new PA4 admission. Retain explicit reasons and evidence for each excluded frame.
4. Verify that changing effective sky selection invalidates a stale WCS sidecar. For newly accepted frames, check the source and mask identities, save and reopen the sidecars, and independently verify the new sky export. Check cancellation, late completion, and retry with the real input and local catalogs before adopting changed query behavior.

**Acceptance** Every horizon attempt has a diagnosable outcome. Adopt a query change only when measurement shows that it advances previously resource-limited candidates to association within the configured caps and preserves the real-field quality controls. If the experiment finds no safe improvement, record the measured limit and next action. Admission to the ready PA4 mosaic requires strict-edge verification for each new frame. Preview and export use the same accepted geometry and all original input hashes match. [Frozen Phase 3.6 rules](phase-36.md#2-frozen-36a-decisions-and-values) · [Field-edge rules](phase-36.md#6-sip-and-field-edge-accuracy) · [Q-016](../questions_open_topics.md#q-016---plate-solve-quality-incorrect-scale-recovery-and-distortion)

### Local Masked Solve Results

The development host's `C:\Program Files\astap\astap_cli.exe` identified itself as `CLI-2026.11.01`. Its SHA-256 matched the previously pinned CLI. The installed folder contains complete D05 and D20 sets, plus G05 and W08. AstroMosaic Automatic selection used D20 in that folder. The D50 replay used the same installed CLI with the complete local `.tooling/phase36-dense/d50` directory. [ASTAP selection policy](adr/0017-astap-first-validated-solving.md)

Solve results record effective position, scale or search interval, resolved catalog and the failing gate. The CLI JSON and the desktop's current **Panel → Plate Solve Details** attempt view report one-based catalog region indices, measured detections, solid angle, decoded and retained star counts, bytes read, elapsed time and the region outcome. Saved version 2 sidecars keep the compact attempt fields and measured WCS quality. The full regional read records are available in the running desktop session and CLI report.

The original three D50 candidates hit 100,000 retained stars in their first or second cone. The failing cones covered about 38–43 square degrees with 14–37 detections. Restricting cones to the detections and the shifted-control margin still exhausted retention on all three seeds. The adopted wide-field query uses the documented bright-to-faint order of `.1476` records. It projects bounded blocks into the existing padded region, retains the same brightest eligible subset and stops reading a tile after reaching fainter magnitudes. Stable order within equal magnitudes preserves ties. Mutual matching, shifted controls, the 100,000 per-cone retention cap and the 64 MiB per-candidate read cap apply throughout. [ASTAP catalog format](https://www.hnsky.org/astap.htm#1476)

| PA4 panel | D50 result | D50 catalog regions / MiB read | Gaia result |
| --- | --- | ---: | --- |
| 01, 02, 05 | No native solution | — | No verified hypothesis |
| 03 | Association rejection with 351 unique matches and 109 shifted-control matches | 41 / 23.92 | Held-out residuals |
| 04, 08 | No native solution | — | Held-out residuals |
| 06 | Held-out P95 1.68 px overall and 1.35 px at the edge | 49 / 22.12 | Held-out residuals |
| 07 | Edge support rejection with 19 held-out stars across two edge sectors | 54 / 17.69 | RMS 70.8″ against 69.0″ |

All eight panels were replayed with the default 120-second total panel deadline and the strict edge gate. The longest panel took 55.08 seconds. Each of the three formerly resource-limited candidates completed its catalog queries and reached association. D05's standard-gate panel 07 repeated its 292 matches and 33.15″ RMS. Comparing the filtered and full D05 cones gave identical WCS, measured regions, matches and shifted-control counts. Installed D05 and D20 both rejected panel 07 under strict edge validation. The ready PA4 sky mosaic retains its 15 qualified inputs.

M13 D05, M42 40′ D50 and installed Automatic D20, M42 55′ Gaia, and the two wide-field SIP-3 controls passed. The DSS center and corner comparisons stayed within their frozen archive envelopes. The new D50 Orion sidecar reopened with its project and produced identical preview and export samples. CFITSIO verified 12,288 covered FITS pixels within 0.001 DN of independent bilinear samples. All 23 PA4 source hashes and eight mask file hashes matched the 6A inventory.

The native details dialog opened for a rejected D50 solution and displayed its scale, database, edge support and 54 catalog regions. Changing the effective sky mask rejected a previously saved sidecar. The real-data checks cover cancellation during a D50 catalog scan and retry, cancellation of the live installed ASTAP CLI, and removal of a sidecar when the deadline expires at publication. The M13 retry succeeded at the same destination. Seven new solve diagnostics tests, four owner TIFF tests and four foreground diagnostics regressions passed. The recorded native dialog ran on one display.

From the checkout root, run the [focused real-data tests](../tests/integration/test_real_solve_diagnostics.py) with `.venv/Scripts/python.exe -m pytest -q tests/integration/test_real_solve_diagnostics.py tests/integration/test_owner_tiff.py`. The local `output/application-tests/phase6c/` folder retains `capture_pa4_candidates.py`, `compare_cones.py`, `replay_6c.py`, `check_real_deadlines.py`, `check_controls.py` and their results. Copy the scripts to a fresh output folder for a new capture and replay; use `horizon`, `controls` and `installed` with `replay_6c.py`.

## 6D Reproduce the ZEA Warning and Measure Preview Cost

1. Capture the warning on the real PA4 project with the specific panel, tile, WCS and output-grid settings. Reduce it to an automated replay of the same tile or a documented crop of the source observations. Inspect which directions are nonfinite or outside the input projection domain. Use real derived coordinate batches to test wholly unprojectable regions and batches that also cover valid samples.
2. Handle unprojectable coordinates in the shared geometry path before SIP iteration where the replay demonstrates that cause. Preserve valid inverse results and return invalid samples as NaN with coverage unset. Check independent WCS and sample values on the same real crop and the full PA4 grid, including supported positions near domain boundaries. Confirm the warning from the recorded case is gone and that legitimate geometry errors still surface.
3. Profile the fixed 15-panel ZEA project at the same size, crop, grid, and resource settings. Record inverse mapping time, source reads, tile processing, viewport delivery, peak memory, and candidate counts. Repeat with named cold and warm conditions and report elapsed-time distributions for CPU and OpenGL. Report rejected mapping attempts in per-panel units and export coverage in output pixels.
4. Evaluate conservative ZEA candidate selection only if mapping is a measured bottleneck. Compare against all-panel sampling on the real data and adopt the optimization only if it improves repeatable timings and preserves coverage, samples and output WCS. Report the safe operating range and use the existing traversal when a conservative bound is unavailable.

**Acceptance** The automated replay uses real PA4 input and explains the warning. The corrected case and full PA4 render pass independent sample, coverage and WCS checks. The report includes repeatable timings and reservations on the fixed workload and any measured optimization benefit. [ZEA grid decision](adr/0021-zea-sky-grid.md) · [Q-023](../questions_open_topics.md#q-023---wide-zea-preview-coordinate-warnings-and-runtime)

### Local ZEA Geometry and Performance Results

The saved PA4 ZEA grid uses panels PA4-09 through PA4-23, 2097 × 2071 output pixels, 230″/px, zero rotation, the full grid, 128 px tiles, a 128 MiB working budget and a 256 MiB output limit. The first tile begins at `(0, 0)`. All 16,384 directions in it are finite in ZEA and 118.50–130.63° from the pointing of PA4-10, an ICRS TAN-SIP plate with third-order SIP. WCSLIB returned zero finite TAN inverse seeds for the batch. Astropy 8.0.2 reached an all-NaN reduction in its iterative inverse. AstroMosaic now delegates only rows with finite core seeds to the distortion inverse. The real regression exercises the recorded tile, a mixed batch with supported detector-edge samples, a direction outside the ZEA disk, and a singular WCS error. [Astropy inverse reference](https://docs.astropy.org/en/stable/api/astropy.wcs.WCS.html#astropy.wcs.WCS.all_world2pix) · [Real PA4 regression](../tests/integration/test_real_zea_mapping.py)

The full selected and guarded all-panel TIFFs match the 6A reference sample bytes, binary coverage and FITS WCS header. The new independent check uses the published ZEA projection equation, a Newton inverse of the saved SIP coefficients and bilinear samples from the original TIFFs. The three crops below match the guarded all-panel renderer byte for byte. The 33 × 33 crop uses the PA4-10 pointing at 174° from the recentered ZEA pole with 31° output rotation. It includes 303 covered samples near the rim and 433 positions outside the disk, all with coverage unset. [FITS projection equations](https://arxiv.org/abs/astro-ph/0207413) · [Conservative footprint decision](adr/0024-conservative-zea-footprints.md)

| PA4 product | Covered pixels | Coverage checks | RGB sample positions | Maximum sample error (DN) | Maximum direction error (°) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full ZEA | 3,238,763 | 12,099 | 8,973 | 0.0019458 | 7.23e-13 |
| Warning crop, 384 × 384 | 4,869 | 147,456 | 4,869 | 0.0018392 | 6.06e-13 |
| Rotated crop, 177 × 183 | 32,391 | 32,391 | 32,391 | 0.0019361 | 4.18e-13 |
| Rim crop, 33 × 33 | 656 | 1,089 | 656 | 0.0011679 | 6.03e-11 |

The warning crop also reopened as RGB XISF with the same samples, coverage and WCS. A rotated ZEA crop of the two real M17 2MASS exposures reopened as a mono FITS with `FILTER=Ks` and `BUNIT=DN`. Its 459,020 covered pixels included 2,670 independently checked sample positions with at most 0.000242 DN error. The ALPACA sky, foreground and composition FITS images and masks matched their mixed references, including 12,979 common composition pixels. All 23 original PA4 TIFF hashes and 29 additional frozen reference file hashes matched. [M17 provenance](application-tests.md#source-credits-and-fixture-limits) · [ALPACA reference](#calibrated-alpaca-mixed-reference)

#### Full-size Export

The profiler timed the current shared renderer with the finite-seed guard enabled in both trials. Candidate counts are panel/tile mappings. The rejection field counts only coordinates in attempted mappings on published tiles. The same 627 TIFF windows and 547,394,950 source pixels were read in both runs. All timings are wall seconds. Mapping includes inverse time, and tile processing includes mapping and reads.

| Renderer | Elapsed | Tile processing | Panel mapping | Inverses | TIFF reads | Panel/tile mappings | Rejected panel coordinates | Peak reservation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Guarded all panels | 83.91 | 83.17 | 61.44 | 52.49 | 14.08 | 4,335 | 26,923,967 | 73.47 MiB |
| ZEA selection | 38.25 | 37.50 | 14.84 | 12.03 | 14.81 | 1,086 | 0 | 73.48 MiB |

Peak Windows working set and commit were 164.41 and 171.32 MiB for the guarded all-panel export and 162.96 and 170.13 MiB with selection. Full-size candidate selection cut evaluated panel/tile mappings by 75% and elapsed time by 54% in these profiled runs. The source CLI validated and exported both PA4 manifests with empty stderr. The full ZEA CLI run took 39.43 s including process startup. Its TIFF matched the selected profile, and the two-panel TAN CLI output matched the 6A TIFF, including 1,028,380 covered pixels.

#### Native Preview

The source desktop ran on Windows 11 x64 build 26200 with an Intel Core i5-14600K, an RTX 4070, one display, Qt 6.12.0 and one OpenBLAS thread. The OpenGL viewport created a 3.2 context. Each independent process opened the saved PA4 project in one window. **Process-cold** denotes its first preview and **process-warm** the second preview in the same window. The Windows file cache stayed under OS management. Elapsed time starts at the preview button and ends after the first final-frame paint callback. The CPU computes the proxy and final samples for both viewport backends.

| Preview path | Viewport | Fresh processes | Process-cold median [min–max] (s) | Process-warm median [min–max] (s) |
| --- | --- | ---: | ---: | ---: |
| Unguarded all panels | CPU | 3 | 49.70 [38.81–51.24] | 46.54 [42.87–48.79] |
| Unguarded all panels | OpenGL | 3 | 42.39 [40.80–48.02] | 42.12 [41.57–51.51] |
| Guarded all panels | CPU | 1 | 51.61 | 48.29 |
| Guarded all panels | OpenGL | 1 | 50.55 | 46.67 |
| ZEA selection | CPU | 2 | 35.19 [33.86–36.52] | 38.08 [34.37–41.79] |
| ZEA selection | OpenGL | 2 | 38.52 [37.95–39.09] | 40.96 [38.59–43.33] |

| Median worker cost across both viewports (s) | Tile processing | Panel mapping | Inverses | TIFF reads |
| --- | ---: | ---: | ---: | ---: |
| Unguarded all panels | 44.60 | 9.72 | 8.18 | 26.83 |
| Guarded all panels | 49.30 | 10.93 | 9.31 | 29.29 |
| ZEA selection | 38.10 | 3.21 | 2.64 | 26.80 |

With selection, the final display frame reached the viewport 0.39–5.21 ms after worker completion across both backends. Delivery to the first final paint took 7.31–17.85 ms on CPU and 8.13–9.08 ms on OpenGL. Windows process high-water working set and commit were 251.84–256.28 and 227.89–229.60 MiB on CPU and 315.89–318.43 and 330.52–340.65 MiB on OpenGL. These high-water marks include the desktop runtime.

The proxy is 160 × 158 with 18,856 covered pixels. The final frame is 512 × 505 with 192,817 covered pixels. All 24 previews match the linear sample, coverage and WCS digests at both resolutions. The unguarded snapshot recorded 191 all-NaN warnings per preview with warnings recorded on every occurrence. Both guarded paths completed without runtime warnings.

For both frames combined, selection reduced evaluated panel/tile mappings from 3,322 to 1,169 and attempted panel coordinates from 7,629,312 to 2,644,080. Completed tiles reported 1,759,717 rejected coordinates with the full panel list and 11,104 with selection. Both paths completed 168 tiles after 148 budget split attempts and read 722 TIFF windows covering 1,252,860,359 source pixels, including retry work. Peak tracked reservations were 126.415 MiB for the full list and 126.418 MiB with selection. TIFF reads are still the largest measured preview cost.

The local evidence directory is `output/application-tests/phase6d/`. It contains the reduced baseline trace, the pre-change source snapshot, `profile_pa4.py`, the per-run profiles, `profile-summary.json`, the independent export verifier and its `scientific-verification.json`. Fifteen real-data regressions across 6B–6D passed, along with Ruff and mypy. With the local PA4 manifest available, rerun the focused replay with `python -m pytest -q tests/integration/test_real_zea_mapping.py`.

## 6E Verify Native Lifecycle and Windows Packages

1. Use the real sky and mixed projects in a minimal native Windows reproduction. Open successive projects in one window, close an idle window and reopen, and close a window during preview or export. Repeat with CPU and OpenGL. Record Qt messages, worker start, cancellation, completion, window destruction, and process exit. Compare the normal UI path with the earlier multi-window automation sequence to locate the failure.
2. Verify that completed exports can be reopened independently. For a cancelled export, check temporary-file cleanup, the original project and source hashes, and retry at the same destination. Treat a repeatable crash in the normal workflow as a release blocker and verify its fix in the affected sequence. Use the second screen for test windows and dialogs when available and record the actual display configuration.
3. Run the Phase 6 real-data cases through the source CLI, native desktop CPU and OpenGL, and the matching portable CLI and desktop builds. Use the frozen translation control for foreground and composition. Independently reopen the applicable FITS, TIFF and XISF products, including real data converted with a documented recipe when needed. Compare scientific samples, coverage, contribution masks, applicable WCS, metadata and channels. Verify older saved projects and sidecars that pass through the Phase 6 changes.
4. Build the intended portable bundles from the matching release source. On a fresh Windows 11 x64 installation, verify startup, project open, CPU operation, a sky export, and independently reopened foreground and composition exports. Record build identities, OS and runtime environment, display/backend and outputs. When one candidate contains both phases, run the 6E and 7F cases on that candidate in the same clean-machine session. Record both sets of results for that build. Keep clean-machine acceptance and the native corresponding-source and redistribution review in the release record. [Clean-machine procedure](phase-3f.md#pending-clean-machine-check) · [Windows release guide](windows-release.md) · [Phase 7F](phase-7.md#7f-ship-the-review-workflow-and-verify-windows) · [Q-005](../questions_open_topics.md#q-005---application-licensing-and-distribution-model)

**Acceptance** The reported window transition and cancellation paths have repeatable native CPU/OpenGL outcomes. The source and portable workflows agree on the real reference products. The clean-machine run is recorded for the actual candidate build. Keep any unavailable Windows test environment visible as pending. [Q-022](../questions_open_topics.md#q-022---native-desktop-test-automation-process-exits)

### Local Windows Lifecycle and Package Results

The reduced replay used the real 2MASS M17 export and the ALPACA project for the next window. It paused the export at its first real tile to enter the earlier automation's timed-out branch. That branch requested close, ran one event pass and replaced its only window reference while the close was still deferred. Both Windows renderer processes exited with `0xc0000409`. The recorded Qt fatal message identified destruction of a running `QThread`. The normal replay retains the window until the close is accepted and its workers have finished. [Original automation report](application-test-findings.md#native-desktop-lifecycle-and-release-acceptance)

A separate OpenGL warning occurred during a normal sequence. Python collected a texture wrapper in a later inspection worker, after its earlier window's context had gone away. On an accepted close the window now releases the preview texture, vertex array and shader on the UI thread, then clears its preview. The GPU fallback also releases its resources before removing the widget. The real M17 regression verifies that the resources are gone before window destruction. [Qt resource lifecycle](https://doc.qt.io/qt-6/qopenglwidget.html#resource-initialization-and-cleanup) · [Native regression](../tests/integration/test_real_desktop_lifecycle.py)

The corrected source and frozen desktop runs opened M17 and ALPACA in one window, closed and reopened an idle window, closed during a PA4 ZEA preview, and closed during a PA4 TAN export after a temporary file and tile progress were observed. Each backend ran twice in each runtime for eight successful sequences. The workers were cancelled, finished and destroyed before the window was destroyed. The temporary file was removed, and reopening the project and retrying to the same TIFF name reproduced the frozen TAN output. The instrumented windows ran on one display with native Qt 6.12.0 and Windows 11 Pro x64 build 26200.

The local candidate ZIPs were built with CPython 3.13.18 and PyInstaller 6.22.3 from a SHA-256 inventory of the working tree based on `c0a01907c30673d8bf06f5b4f0f5660abf2385ec`. The desktop inventory contains 223 native files and the Qt-free CLI inventory contains 178. The source snapshot, complete binaries, licenses, native-file inventories and `SHA256SUMS.txt` are in `.tooling/phase6e-20261119/artifacts/`. Each ZIP was extracted and checked against its build directory before running on the local host. [Release verification](windows-release.md#verification-status)

| Local candidate archive | SHA-256 |
| --- | --- |
| `AstroMosaic-0.1.0b1-phase6e-windows-x64.zip` | `0e7757762af11af18154e4afaf79b25d3202a373ae4ef8585337cef71b8b46de` |
| `astromosaic-cli-0.1.0b1-phase6e-windows-x64.zip` | `bdc29aa63a5064ae90f35cfd324a56e64ad8f8a4419ad05dceb5e2b688ecafe8` |
| `AstroMosaic-0.1.0b1-phase6e-source.zip` | `284e3bca25f8124c61e07a8c9d5d5cb282e7904e1f95213dc073577f05593843` |

The source CLI, native CPU and OpenGL desktop, portable CLI and frozen CPU and OpenGL desktop each exported the nine products below. The frozen probe ran against the extracted desktop runtime with a Windows-system-only `PATH`. Independent CFITSIO, TIFF and XISF readers verified all 54 products. Float32 science samples, binary coverage and applicable contribution masks matched the frozen references byte for byte. Center and corner WCS matched within `1e-9` degrees. The real `Ks` FITS outputs preserved `BUNIT=DN`. The ALPACA FITS and XISF compositions contain the same four contribution codes, with 11,671 pixels receiving a contribution from both layers. The existing version 4 and 5 manifests and pre-diagnostic version 2 PA4 sidecars opened and rendered successfully.

| Product | Format | Covered pixels |
| --- | --- | ---: |
| M17 atlas pair, `Ks` | FITS | 969,235 |
| Three-panel atlas chain, `Ks` | FITS | 1,422,222 |
| PA4 TAN pair | TIFF | 1,028,380 |
| PA4 full ZEA | TIFF | 3,238,763 |
| ALPACA sky | FITS | 204,293 |
| ALPACA foreground | FITS | 80,158 |
| ALPACA composition | FITS and XISF | 246,642 each |
| M42 with the saved D50 solution | FITS | 12,288 |

The regular packaged `AstroMosaic.exe` opened M17, built its CPU preview, saved a TIFF matching the M17 FITS reference and exited with code 0. Both CLIs passed their worker-spawn check and repeated all 14 frozen masked and archive solve cases. The same six controls solved and the same eight PA4 panels stayed excluded. Some unsuccessful native searches reached the timeout under replay while their diagnostic gate and admission outcome matched. The source and frozen desktop on both backends solved M13 with installed D05 and reopened the sidecar. Each M13 FITS had 65,536 covered pixels and matched across the four desktop runs. PA4-07 reached the D50 edge-support gate after 54 catalog regions and withheld its sidecar in each run. [Phase 6C reference](#local-masked-solve-results) · [M13 provenance](phase-0.md#offline-astap-experiment)

The 52 frozen PA4 file hashes and five ALPACA project, source and sidecar hashes matched. Twenty real-observation regressions, Ruff and mypy passed. `output/application-tests/phase6e/` contains the commands, Qt and worker events, scientific comparisons, solve reports, and the regular launcher's result.

The fresh-installation gate is pending. Windows Sandbox and Hyper-V were disabled on the available development host. The recorded archive hashes identify the locally tested `0.1.0b1` build. For `0.1.0b2`, build matching archives and record their hashes for the separate Windows 11 x64 installation check. Check CPU startup and project opening, then reopen a real sky export and the ALPACA foreground and composition outputs independently. Preserve fixture modification times when transferring the source-bound manifests and sidecars. Keep the native corresponding-source and redistribution review with the build selected for release. [Clean-machine procedure](phase-3f.md#pending-clean-machine-check) · [Distribution tracking](../questions_open_topics.md#q-005---application-licensing-and-distribution-model)

## Integration and Phase Completion

- Keep matching, solving, and shared geometry in the Qt-free processing core. Extend attempt and alignment diagnostics additively so existing readers remain compatible. Keep preview and final rendering on the same geometry and retain separate scientific sky and visual composition products. Changes that affect shared geometry must verify applicable formats and band-local metadata with real inputs. [Architecture contracts](../astro_mosaic_python_first_architecture_en.md#51-essential-contracts)
- Record the reference inventory, exact commands, results by entry point, independent reads, timing and resource evidence, failures, and next actions. Update the tracked topics and [progress log](../progression.md). Close the phase when the required evidence above is recorded for the real-observation cases and the prescribed checks pass on the intended Windows target.
