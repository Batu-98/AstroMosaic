# Questions and Open Topics

This register tracks unresolved decisions, problems, and risks. It is not a work log. Read it at the start of each development session and update it when evidence changes.

## Tracking Rules

- IDs are stable and increasing: `Q-001`, `Q-002`, and so on. Never reuse an ID.
- Status: `Open`, `Investigating`, `Blocked`, `Deferred`, or `Resolved`.
- Priority: `P0` = immediate correctness/data-loss blocker; `P1` = required before an identified gate; `P2` = planned improvement or later decision.
- Record the affected action or phase. Priority alone does not block all development.
- The agent resolves technical questions through investigation. Ask the owner only when a product preference or missing authority is actually needed.
- Keep resolved entries with a dated resolution and evidence. A deferred entry must name its revisit trigger.
- Use the fields below for new entries; omit no closure condition. Keep details concise and link larger evidence separately.

## Active Topics

### Q-003 - Reference datasets and frozen acceptance thresholds

- **Status / priority:** Investigating / P1
- **Opened / updated:** 2026-11-15 / 2026-11-21
- **Affected phase:** Phase 0 fixture design and the numerical gates in phases 1, 2, 3.5, 3.6, 4, 6 and 7.
- **Impact and evidence:** The [Phase 1 fixtures](docs/phase-1.md) verify independent FITS export truth. [Phase 2](docs/phase-2.md#acceptance-fixtures) fixes and verifies held-out alignment, stellar flux and profile, injected extended signal, masks, and weak or disconnected inputs. [Phase 3A fixtures](docs/phase-3a.md#acceptance-fixtures) fix sample, channel, coverage, and WCS tolerances for linear TIFF. [Phase 3C](docs/phase-3c.md#windows-verification) confirms preview and export agreement at coincident sample positions. [Phase 3.5A](docs/phase-35.md#frozen-supplementary-fixtures) reran the baseline and froze cases for narrow support, saturation, and explicit DSS crops. The [sidecar check](docs/phase-35.md#masked-wcs-sidecar-reuse) uses the existing bilinear and WCS bounds.
- **Current assumption:** Phases 6 and 7 use real observations with recorded provenance and independent measurements. The [3.6A manifest](tests/fixtures/plate_solve_v36.json) identifies the established catalog-quality and timing contracts.
- **Next action / responsibility:** Use the verified ALPACA translation and Oxford similarity references to check 7E rendering and model persistence. Retain La Silla for independent nightscape coverage, PASSTA's 4.13 px rotation result and Adirondack's depth rejection. A new camera-rotation reference should supply a controlled lens entrance-pupil pivot and independent near/far landmarks before reopening model admission. [Reference cases](docs/phase-7.md#frozen-7a-references) · [7D results](docs/phase-7.md#7d-real-observation-results)
- **Closure condition:** Record dataset-specific tolerances and reference results before algorithm tuning. Include the applicable Phase 4 large-mosaic, RGB photometry and mixed-scene measurements. Link the Phase 6 and 7 reference inventories and independent measurements of the real cases.

### Q-005 - Application licensing and distribution model

- **Status / priority:** Investigating / P1
- **Opened / updated:** 2026-11-15 / 2026-11-21
- **Affected phase:** Public source publication and Windows binary distribution.
- **Impact and evidence:** AstroMosaic source uses `GPL-3.0-only`. The portable builder collects wheel notices, the CPython runtime license, upstream supplements for selected dependencies and the native file inventory. The local 6E candidate recorded 223 desktop and 178 CLI native files and the exact source and binary archive hashes. [License decision](docs/adr/0009-gpl-v3-application-license.md) · [Windows release preparation](docs/windows-release.md) · [6E candidate evidence](docs/phase-6.md#local-windows-lifecycle-and-package-results)
- **Current assumption:** Publish the source on GitHub. Keep portable ZIP builds local until the remaining binary distribution review passes. Obtain external ASTAP binaries, solver catalogs and archive FITS references from upstream.
- **Next action / responsibility:** Match the binary inventory to the exact native corresponding sources and confirm Microsoft runtime redistribution terms before publishing Windows downloads. Before adopting the optional 7C wheel for distribution, review the pinned OpenCV and FFmpeg native contents, corresponding sources and notices, and verify that exact package on clean Windows. [7C wheel inventory](docs/phase-7.md#7c-real-observation-results)
- **Closure condition:** Record the applicable notices, matching source and redistribution terms for publicly distributed artifacts. Keep separately obtained data subject to its upstream terms.

### Q-008 - Linux and macOS support

- **Status / priority:** Deferred / P2
- **Opened / updated:** 2026-11-15 / 2026-11-15
- **Affected phase:** Future platform expansion.
- **Impact and evidence:** Candidate wheels matched the historical Ubuntu x86-64 and macOS arm64 targets. Native operation and packaging are unverified.
- **Current assumption:** Preserve portable engine code and isolate platform-specific behavior in adapters.
- **Next action / responsibility:** Revisit when the owner requests another platform and native test resources are available.
- **Closure condition:** Select the added OS and CPU targets and verify native installation, jobs, viewport, solver, and packaging on each added target.

### Q-009 - Dual FITS and TIFF workflows and camera RAW import

- **Status / priority:** Open / P1
- **Opened / updated:** 2026-11-15 / 2026-11-18
- **Affected phase:** Dual FITS and TIFF workflows throughout phases 1-4, Phase 5C band-local channels, and optional camera RAW import after a future scope decision.
- **Impact and evidence:** The [Phase 3A Windows fixtures](docs/phase-3a.md#windows-evidence) verified mono and RGB TIFF import and export, including samples, channel order, WCS, and coverage. The [Phase 3B desktop workflow](docs/phase-3b.md#verification) reopens a mixed FITS/TIFF project and renders it to TIFF. [Phase 4B](docs/phase-4b.md#windows-baseline-results) independently verified all samples and coverage in full-size mono FITS, RGB TIFF and mixed exports. [Phase 5C](docs/phase-5c.md#local-windows-results) verified band-local units and channel order with mixed mono and RGB membership. Camera RAW is deferred as an import-only feature.
- **Current assumption:** Provide first-class support for both scientific FITS panels and linear TIFF panels across the pipeline. If camera RAW is requested later, use an open-source linear decoder and preserve relevant sensor and color metadata.
- **Next action / responsibility:** Repeat the [packaged Windows exports](docs/phase-3f.md#windows-evidence) on a clean Windows installation. Define and verify channel-specific calibration before enabling RGB photometric refinement. Revisit camera models and decoder compatibility when camera RAW import is requested.
- **Closure condition:** Validate FITS and TIFF sample integrity, metadata, memory, and reproducible import-to-mosaic workflows on Windows. If camera RAW is activated, establish separate acceptance criteria for the selected models.

### Q-010 - Foreground recognition, masks, and composition

- **Status / priority:** Investigating / P1
- **Opened / updated:** 2026-11-15 / 2026-11-21
- **Affected phase:** Phase 2 masked sky processing, Phase 3D mask editing, Phase 3E foreground alignment and composition, Phase 3F packaged acceptance, Phase 4 resource validation, Phase 6B real-scene validation, and Phase 7 panorama registration.
- **Impact and evidence:** [Phase 3D](docs/phase-3d.md#windows-verification) verifies local suggestions, manual overrides and masks, and exclusion of foreground from sky fitting. [Phase 3E](docs/phase-3e.md#windows-verification) verifies WCS-free alignment and exports, shared-reference placement, saved edits, and seams with partial and zero common coverage. [Phase 4A](docs/phase-4a.md#local-windows-results) reproduced all three desktop layers from a saved mixed project in the portable CLI. Small, rotated, and ambiguous terrain still needs manual review.
- **Current assumption:** Use the saved three-label mask for same-size, same-scale foreground translations. Use similarity placement between layers and restrict seam blending to valid common coverage.
- **Next action / responsibility:** Integrate the verified translation and similarity geometry in 7E. PA4 metadata rotation improves the visible overlap but gives 8.34 and 3.07 px P95 and leaves the saved mask issues open. The PASSTA candidates also exceed the frozen tolerance. Revisit calibration, viewpoint shift and the omitted ground support before admitting these models or links. [PA4 pair review](docs/phase-7.md#initial-7a-measurements) · [7D results](docs/phase-7.md#7d-real-observation-results)
- **Closure condition:** Verify separate layer exports, saved edits and measured resource limits. Pass the Phase 6B diagnostics and the Phase 7 positive, held-out, negative and legacy checks on real captures. Account for the PA4 pair outcomes and document unsupported geometry.

### Q-011 - Optional generative fill for a visual seam

- **Status / priority:** Deferred / P2
- **Opened / updated:** 2026-11-15 / 2026-11-15
- **Affected phase:** Optional follow-on to the Phase 3 composition workflow.
- **Impact and evidence:** Uncovered regions may remain after aligning and cropping the sky and foreground layers. The baseline composite exposes the gaps.
- **Current assumption:** Evaluate fill as an opt-in local visual operation restricted to uncovered seam gaps. Keep its synthetic pixels and provenance separately identifiable.
- **Next action / responsibility:** Revisit after the crop and overlap controls are tested and the owner wants fill for remaining gaps. Evaluate open-source software, model weights, licenses, and local resource use then.
- **Closure condition:** If selected, verify that fill is confined to the selected gaps and its synthetic mask and provenance survive export. Scientific layer exports retain observed samples.

### Q-016 - Plate solve quality, incorrect-scale recovery and distortion

- **Status / priority:** Investigating / P1
- **Opened / updated:** 2026-11-17 / 2026-11-19
- **Affected phase:** Phase 3.6A quality/fixture freeze, 3.6D bad-scale recovery, 3.6E SIP/edge validation, 3.6F acceptance, and 6C masked solve recovery.
- **Impact and evidence:** The [Mosaic Master comparison](docs/plate-solve-comparison.md) verified that the Seiza wrapper retains a supplied scale within 0.8–1.2 on blind retry and does not request SIP (`sip_order=0` in installed Seiza 0.48.2). The earlier ASTAP wrapper retained the supplied vertical FOV on blind retry. Geometry checks alone leave catalog accuracy at the edges unmeasured. Q-015 records the measured 40′ M42 blind limit.
- **Current assumption:** The source uses the common 15-match and RMS gate, Gaia's confidence check, unrestricted Gaia 0.1–120 arcsec/pixel recovery and a spatial holdout for application SIP promotion. The rerun of the original D05 and Gaia cases met their archive envelopes. ASTAP-only local FOV recovery retains pointing when both hints were supplied. [Measurements](docs/phase-36-results.md)
- **Next action / responsibility:** The 6C D50 replay moved all three resource-limited candidates to association at 17.69–23.92 MiB. The shifted-control, held-out and edge-support failures still exclude those frames. Reuse those diagnostics when stronger PA4 sky support is available. Review the D80 Orion candidate's 1.02 px held-out whole-field P95 and the D20 M13 archive comparison of 0.452″ against the 0.451″ reference envelope. Assess Automatic recovery and additional real sparse fields within the existing budgets. [Phase 6C measurements](docs/phase-6.md#local-masked-solve-results) · [Dense catalog results](docs/phase-36-results.md#dense-astap-catalog-verification)
- **Closure condition:** The implemented match/RMS boundaries, bad-hint recovery, supported SIP/edge cases, legacy reuse and Windows source/portable regressions meet the frozen 3.6 gates with independently recorded errors. Planning alone does not resolve this topic.

### Q-020 - Additional XISF variants

- **Status / priority:** Deferred / P2
- **Opened / updated:** 2026-11-18 / 2026-11-18
- **Affected phase:** Phase 5A interchange and future XISF expansion.
- **Impact and evidence:** XISF permits block compression, non-attached storage, checksums and private astrometric metadata. The [Phase 5A checks](docs/phase-5a.md#local-windows-results) independently reopened raw attachments with FITS-compatible metadata. A compressed attachment produced a conversion diagnostic.
- **Current assumption:** Use a compatible XISF attachment or a supported FITS/TIFF file for interchange. Solve or attach a sidecar when the XISF panel needs celestial WCS.
- **Next action / responsibility:** Revisit when a representative workflow requires broader support. Check codec block sizes and bounded decode or staging, checksum cost, and native WCS agreement before extending the adapter.
- **Closure condition:** Reopen representative files from named external writers and verify data integrity, WCS, channel order, resources and packaging for each variant added.

## Resolved Topics

### Q-001 - Python, dependency, and platform compatibility matrix

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-15 / 2026-11-15
- **Affected phase:** 0.
- **Impact and evidence:** CPython 3.13 and the Poetry lock passed native imports, CLI and worker startup, ASTAP, PySide6, and two local bundle runs on Windows 11 x64.
- **Current assumption:** Use CPython 3.13 and the optional PySide6 Essentials extra for the initial Windows target.
- **Next action / responsibility:** Repeat the [copied-bundle workflow](docs/phase-3f.md#pending-clean-machine-check) on a fresh Windows 11 x64 installation. Revisit additional platforms under Q-008.
- **Closure condition:** Record the locked stack and successful checks for the initial Phase 0 target.
- **Resolution:** 2026-11-15. The Windows-only development gate is met. See [Phase 0 evidence](docs/phase-0.md) and [ADR-0003](docs/adr/0003-windows-first-platform-scope.md).

### Q-002 - Pixel-unit and pixel-area contract

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-15 / 2026-11-15
- **Affected phase:** 0 contracts and 1 reprojection.
- **Impact and evidence:** Pixel-area handling determines whether output samples preserve field brightness or represent integrated flux per pixel.
- **Current assumption:** Read source scaling and retain the unit label. Reproject declared surface brightness and include output pixel solid angles when integrating its aperture flux.
- **Next action / responsibility:** Apply the contract to Phase 1 reprojection and export. Add an area-aware conversion and dedicated tests when integrated-flux inputs enter scope.
- **Closure condition:** Document the convention and check its scale-change behavior against independently calculated values.
- **Resolution:** 2026-11-15. [ADR-0002](docs/adr/0002-surface-brightness-reference.md) records the convention. The uniform-field and Gaussian scale-change fixtures passed on Windows.

### Q-004 - Resource budgets and representative workload

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-15 / 2026-11-18
- **Affected phase:** Phase 0 scheduling, Phase 1 rendering, Phase 2 solvers, Phase 3 preview, Phase 3.6 deadlines, and Phase 4B large-job scaling.
- **Impact and evidence:** The renderer has one synchronous worker and no queued tiles. The optimized full Windows runs peaked at 20.215 MiB reservation, 140.68 MiB working set and 146.06 MiB commit across the three jobs. Separate evidence covers two-panel rendering, native catalog mappings and desktop preview memory. [Phase 4B results](docs/phase-4b.md#footprint-selection-results) · [Phase 1 measurements](docs/phase-1.md#working-set-and-cancellation) · [Phase 2 solver measurements](docs/phase-2.md#windows-solver-evidence) · [Phase 3C preview measurements](docs/phase-3c.md#resource-check)
- **Current assumption:** Default to 128-pixel render tiles, a 64 MiB working reservation and a 2048 MiB output limit. Reserve the preview raster and cap its longest edge at 512 pixels. Account for display, GPU and native catalog allocations separately. [TIFF decode reservation](docs/phase-3a.md#sample-and-metadata-contract) · [Solver staging limit](docs/phase-2.md#offline-solvers)
- **Next action / responsibility:** Measure any future blend buffers, parallel scheduler or extended workload against the named reference.
- **Closure condition:** Document defaults and over-budget behavior, and verify bounded queues, reservations, cancellation and measured peak usage at the Phase 4B scale.
- **Resolution:** 2026-11-18. The three full 12-panel exports, the 6 MiB forced split, the 2048 MiB output refusal and cancellation/retry passed. The benchmark's full RGB job uses a saved 3072 MiB limit. [Phase 4B reference and comparison](docs/phase-4b.md)

### Q-007 - FITS metadata, coverage, and independent export validation

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-15 / 2026-11-15
- **Affected phase:** 0 I/O contracts and 1 FITS export gate.
- **Impact and evidence:** The FITS reader applies source scaling and validity. The exporter writes float32 brightness, NaN for uncovered samples, and an unscaled binary `COVERAGE` image. The reader recognizes this coverage extension on reimport.
- **Current assumption:** Derive output WCS from the render grid and record shared `BUNIT`/`FILTER` and source fingerprints in the header.
- **Next action / responsibility:** Apply independent reopen checks to future formats and channel layouts when their contracts are implemented.
- **Closure condition:** Document and verify pixels, scaling, coverage, WCS, crop/rotation, and SIP removal with small fixtures and independent evidence.
- **Resolution:** 2026-11-15. CFITSIO reopened the exact two-panel result, and the cropped and rotated export matched analytic TAN and SIP checks. [Phase 1 FITS validation](docs/phase-1.md#numerical-and-windows-checks)

### Q-006 - Offline solver and catalog deployment

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-15 / 2026-11-17
- **Affected phase:** Phase 0 adapter experiment, Phase 2 offline astrometry, Phase 3.1 desktop solver settings and jobs, and Phase 3.5 revalidation.
- **Impact and evidence:** The Windows M13 reference passed both hinted and blind Gaia DR3 and ASTAP, ordered fallback, real ASTAP cancellation, missing-catalog diagnostics, and unchanged-source checks. The catalog and index were verified against the versioned manifest.
- **Current assumption:** Install explicit local Gaia and ASTAP files separately, keep the Gaia catalog and index version paired, and save solved WCS in a source-bound sidecar.
- **Next action / responsibility:** Recheck the solver matrix on catalog updates and during release packaging. Track the 40′ M42 coverage result under Q-015 and release notices and data terms under Q-005.
- **Closure condition:** Record a tested solver/version/catalog matrix and deployment/update policy, including ordered fallbacks, cancellation, missing-catalog diagnostics, exhausted-chain behavior, and unchanged-source checks.
- **Resolution:** 2026-11-15. The backend decision and Phase 2 evidence record results, catalog provenance, and the update procedure. The 3.5C Windows rerun verified the M13 matrix, new M42 fields, solver cleanup, and the Documents XPSD format diagnostics. [ADR-0010](docs/adr/0010-seiza-gaia-backend.md) · [Phase 2 setup](docs/phase-2.md#offline-solvers) · [Phase 3.1C desktop checks](docs/phase-3b.md#desktop-plate-solving) · [Phase 3.5C solver results](docs/phase-35.md#m42-offline-astrometry-and-documents-catalogs)

### Q-012 - Desktop terminal scope

- **Status / priority:** Resolved / P2
- **Opened / updated:** 2026-11-16 / 2026-11-18
- **Affected phase:** 4C desktop command panel.
- **Impact and evidence:** The desktop panel reuses the Phase 4A CLI arguments, report formats, render limits, and cancellation. [CLI contract](docs/phase-4a.md#result-contract) · [Worker decision](docs/adr/0019-desktop-command-worker.md)
- **Current assumption:** Keep the panel scoped to AstroMosaic commands, with session history, output, progress, and cancellation.
- **Next action / responsibility:** Retain the source and packaged command-panel checks for future CLI changes.
- **Closure condition:** Record the selected desktop terminal scope and verify its agreed workflows on Windows 11 x64.
- **Resolution:** 2026-11-18. Windows source and copied CPU/OpenGL desktop checks passed. The windowed executable and console CLI produced the same validation JSON and FITS bytes. The panel's progress, session history, cancellation, cleanup and retry passed. [Windows evidence](docs/phase-4c.md#local-windows-results)

### Q-013 - Optical metadata conventions for solve hints

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-16 / 2026-11-18
- **Affected phase:** 3.1A panel metadata and the 3.6A TIFF EXIF/XMP extension.
- **Impact and evidence:** FITS writers may report native or effective pixel pitch. The reader supports numeric FITS-style optical fields in FITS and AstroMosaic TIFF. Binned fixtures verify native and effective pitch, while a conventional TIFF resolution tag leaves the optical values unset. [Optics tests](tests/integration/test_panel_inspection.py)
- **Current assumption:** Interpret the documented field conventions and use panel overrides or a compatible blind solve when the image has no reliable scale hint.
- **Next action / responsibility:** Evaluate additional metadata mappings when a representative acquisition export establishes its field meaning and units.
- **Closure condition:** Document supported conventions and verify the derived scale and missing-metadata behavior with representative fixtures, including a binned case.
- **Resolution:** 2026-11-16. Synthetic FITS and TIFF cases passed, including stale masked WCS and ambiguous binning. Local Gaia and ASTAP solved M13 using embedded optical hints. [Supported metadata and Windows evidence](docs/phase-3b.md#panel-wcs-and-plate-solve-hints)

- **Extension:** 2026-11-18. [3.6A](docs/phase-36a.md#tiff-metadata-at-panel-import) verified standard EXIF/XMP physical focal length, focal-plane inch/centimeter units and camera display, including both owner TIFFs. Print DPI, 35 mm equivalents and ambiguous/invalid resampling or zoom metadata do not create sensor-scale hints. Explicit source fields and user overrides retain precedence; absent reference dimensions leave nominal pitch labeled as a hint.

- **Follow-up:** 2026-11-18. The panel dialog now fills its optical fields from background inspection. Standard TIFF tags and XISF image properties enter the same solve-hint path as FITS optical fields. FITS fixtures verify already-binned pitch from N.I.N.A. and MaxIm DL. A saved panel edit still overrides its corresponding optical measurement. [Updated import behavior](docs/phase-3b.md#panel-wcs-and-plate-solve-hints) · [Cross-format checks](tests/integration/test_panel_inspection.py)

### Q-014 - Regression coverage for narrow overlaps, saturation, and WCS reuse

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-17 / 2026-11-17
- **Affected phase:** 3.5B revision and 3.5C verification.
- **Impact and evidence:** Three automated regressions verify offset selection with a four-pixel overlap, exclusion of saturated stars from gain measurements, and masked WCS reuse. [Review and reproduction](docs/phase-35.md#supplementary-results-and-follow-up) · [3.5B results](docs/phase-35.md#phase-35b-regression-results)
- **Current assumption:** Use deterministic synthetic fixtures for the suite and the recorded M13 and M31 recipes for real-field checks.
- **Next action / responsibility:** Rerun the recorded cases when changing refinement, masks, or WCS reuse.
- **Closure condition:** The added regressions protect the frozen sample, geometry, and fitting criteria. The Windows source and bundled checks meet the recorded thresholds.
- **Resolution:** 2026-11-17. The 88 source tests, identical masked CLI exports for common WCS inputs, and the real-field checks met their thresholds in 3.5C. [Windows verification](docs/phase-35.md#phase-35c-windows-verification)

### Q-015 - Offline solver coverage on the 40′ Orion field

- **Status / priority:** Resolved / P2
- **Opened / updated:** 2026-11-17 / 2026-11-18
- **Affected phase:** Phase 3.6A fixtures and 3.6F real-field verification, following the coverage finding in 3.5C.
- **Impact and evidence:** Portable Seiza 0.48.2 solved the 40′ ESO M42 cutout with hints. Its blind index exhausted 400 hypotheses. ASTAP CLI-2026.11.01 with D05 failed hinted solving and timed out blind. Seiza solved the 55′ M42 cutout blind. [M42 inputs and results](docs/phase-35.md#m42-offline-astrometry-and-documents-catalogs)
- **Current assumption:** The verified 40′ ASTAP-only Orion workflow uses CLI-2026.11.01, D20 or D50, and pointing and scale. The policy can recover locally from a wrong scale when pointing is usable.
- **Next action / responsibility:** Retain the dense catalog matrix when checking future recovery policy changes. Q-016 tracks catalog-dependent quality and broader field coverage.
- **Closure condition:** Record validated solutions and elapsed times across a named subdegree sample, or document the supported hint requirements for those fields.
- **Resolution:** 2026-11-18. D20 and D50 qualified the 40′ Orion fixture with both hints. The three dense catalogs reached the 60-second cap in blind Orion trials. The named M31 40′ and M13 55′ controls recorded validated solutions and times. [Dense catalog results](docs/phase-36-results.md#dense-astap-catalog-verification)

### Q-017 - Automatic ASTAP catalog selection and ASTAP-only quality evidence

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-17 / 2026-11-18
- **Affected phase:** Phase 3.6A capabilities, 3.6B catalog automation, 3.6D candidate validation and 3.6F settings/migration.
- **Impact and evidence:** Earlier ASTAP silently substituted D05 for a missing manual D20. AstroMosaic now inventories tiles, checks the actual native catalog identity and verifies the selected catalog's solution. Verified D05 Auto and Unicode path coverage preceded the dense-catalog matrix. [Implementation results](docs/phase-36-results.md)
- **Current assumption:** Fresh settings use Automatic. Use verified native selection or explicitly pass a complete supported D-series set. Keep manual choices pinned and qualify ASTAP-only results with independent local catalog matches under the common quality thresholds.
- **Next action / responsibility:** Rerun selection and missing-tile controls on CLI or data updates. Q-016 tracks the Orion D80 quality rejection. Q-005 retains catalog redistribution review.
- **Closure condition:** Automatic/manual modes, actual catalog provenance and the ASTAP-only quality path pass real Windows native cases, including missing/partial catalogs and unknown/bad FOV. Preserve user ASTAP settings and original images, and report unsupported cases.
- **Resolution:** 2026-11-18. Real single and mixed D-series sets verified native Automatic and manual pinning. Automatic bypassed incomplete D80 and qualified with D50. Pinned incomplete and missing D80 produced diagnostics without sidecars. The alternate CLI used explicit D20. Source, copied console and native desktop checks verified catalog provenance, supported recovery, saved settings and unchanged source hashes. [Dense catalog results](docs/phase-36-results.md#dense-astap-catalog-verification)

### Q-018 - End-to-end solve deadlines and compatibility

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-17 / 2026-11-18
- **Affected phase:** Phase 3.6A budget freeze, 3.6C orchestration/cleanup, 3.6F CLI/desktop/report compatibility and Phase 4 automation.
- **Impact and evidence:** The implementation keeps `--timeout` per native attempt and shares a default 120-second panel deadline through source opening, staging, searches, validation, and sidecar publication. Gaia catalog/native work uses reaped spawn workers. Source tests pass late-candidate, late-publication and nonresponsive-worker cases. Version 1 reading and version 2 publication are covered. [Deadline contract](docs/phase-36.md#7-total-deadline-cancellation-and-reporting) · [Results](docs/phase-36-results.md#deadlines-and-compatibility)
- **Current assumption:** Local Windows samples support the stated deadlines at checkpoints. Filesystem and OS stalls can add a reported overrun. Neither the validation reserve nor worker cleanup restarts the panel timer.
- **Next action / responsibility:** Carry the panel and batch report into Phase 4 automation. Keep clean-machine and storage-dependent timings separate.
- **Closure condition:** Deterministic boundary tests and real source/portable jobs meet the frozen whole-pipeline, cancellation and cleanup limits, reject late success, retain earlier panels, and read old settings/projects/sidecars without silent semantic changes.
- **Resolution:** 2026-11-18. The source and portable local Windows gates passed. A real ASTAP cancellation reaped the process and cleared scratch in about 0.025 seconds. Portable exhaustion and timeout published no sidecars. [Deadline evidence](docs/phase-36-results.md#deadlines-and-compatibility)

### Q-019 - Owner wide-field TIFF solve and regional validation coverage

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-17 / 2026-11-18
- **Affected phase:** Phase 3.6A real fixtures, 3.6D scale recovery, 3.6E regional/SIP accuracy and 3.6F acceptance.
- **Impact and evidence:** The two 6000 × 4000 RGB owner TIFFs contain Nikon D5300 EXIF with 24 mm focal length and nominal 3.9083 micrometer pixels (33.59 arcsec/pixel). The load path now imports these hints; local Gaia TAN solves found 890/894 matches at about 54 arcsec RMS. [3.6A broad blind/SIP probes](docs/phase-36a.md#owner-wide-field-results) found 992/1009 native matches at about 10 arcsec RMS; independent D05 checks found 1425/1461 matches at about 13 arcsec RMS. The 21.TIF fine support map contains insufficient-star cells, so this is not an entire-frame accuracy certificate. Correct wide-field ASTAP hints recommend missing W08 and fail after D05 fallback/cropping.
- **Current assumption:** Keep source TIFFs ignored, immutable and offline. Use native EXIF focal-plane units rather than print DPI or 35 mm equivalent focal length. Distinguish approximate optical hints, native fit statistics and independent regional evidence. Keep supported ASTAP catalog domains and broad Gaia recovery ranges explicit.
- **Next action / responsibility:** Retain the private files as optional local regression inputs and continue to show insufficient regional support. Wide-field ASTAP catalog validation is a separate format and deployment follow-up.
- **Closure condition:** The owner cases have reproducible source/portable outcomes under the finalized quality/budget policy, with unchanged image hashes, explicit supported catalog/scale ranges and independent spatial accuracy or documented support limitations. Native solve success alone does not close this topic.
- **Resolution:** 2026-11-18. Both source and portable runs qualified SIP-3 after recovery. The independent D05 edge P95 values were 0.895 and 0.985 px. The original files matched their initial SHA-256 values, and each new sidecar drove an independently reopened RGB export. [Windows evidence](docs/phase-36-results.md#portable-windows-verification)

### Q-021 - ZEA antipode and exported crop validation

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-18 / 2026-11-18
- **Affected phase:** Phase 5B sky geometry and format reimport.
- **Impact and evidence:** The antipode is non-unique on the ZEA rim. With the installed WCSLIB, a polar rim coordinate could round-trip, and FITS header rounding could place a nominal rim sample just inside the domain.
- **Current assumption:** Apply a native-latitude guard around the antipode and keep the bounded full mapper. Allow a cropped source with valid support to validate at a nearby in-frame reference position.
- **Next action / responsibility:** Carry the fixture into future geometry changes and verify the domain of each added projection.
- **Closure condition:** The rim and exterior are uncovered, the valid crop reopens with its WCS, and an entirely invalid crop leaves the destination free.
- **Resolution:** 2026-11-18. The polar fixture passed with serialized WCS and a shifted panel. The rim-centered crop reopened with 12 valid positions. The fully outside crop removed its temporary output. [Windows results](docs/phase-5b.md#local-windows-results)

### Q-022 - Native desktop test automation process exits

- **Status / priority:** Resolved / P2
- **Opened / updated:** 2026-11-19 / 2026-11-19
- **Affected phase:** Local Windows desktop application test automation and Phase 6E native acceptance.
- **Impact and evidence:** An earlier multi-window run timed out and exited with `0xc0000409` on both renderers. The reduced real M17 and ALPACA replay reproduced the exit when it dropped the old window during deferred cancellation. Qt reported destruction of a running `QThread`. The initial local report is `output/application-tests/20261119-110157-116/test-report.md`. [Recorded lifecycle findings](docs/application-test-findings.md#native-desktop-lifecycle-and-release-acceptance)
- **Current assumption:** Retain the window through accepted close and worker teardown. Release OpenGL preview resources on the UI thread while their context is usable.
- **Next action / responsibility:** Retain the real replay and repeat the lifecycle checks on the clean-machine candidate selected for release.
- **Closure condition:** Identify the cause of the process exits and record a repeatable native run of the affected window transition on both renderers.
- **Resolution:** 2026-11-19. Eight orderly source and frozen desktop sequences passed across CPU and OpenGL. They verified idle reopen, close during preview and export, temporary-file cleanup and same-destination retry. The normal OpenGL teardown warning was traced to deferred texture destruction and fixed. [6E lifecycle evidence](docs/phase-6.md#local-windows-lifecycle-and-package-results)

### Q-023 - Wide ZEA preview coordinate warnings and runtime

- **Status / priority:** Resolved / P2
- **Opened / updated:** 2026-11-19 / 2026-11-19
- **Affected phase:** Shared sky coordinate mapping and Windows preview performance in phases 3C, 4B, 5B and 6D.
- **Impact and evidence:** Both desktop backends and the 6A source CLI emitted the Astropy all-NaN-slice warning on the PA4 ZEA mosaic. The PA4-10 replay located 16,384 finite sky directions outside the panel's TAN projection in the first 128 × 128 tile. [Original findings](docs/application-test-findings.md#wide-zea-diagnostics-and-preview-performance) · [6D replay](docs/phase-6.md#local-zea-geometry-and-performance-results)
- **Current assumption:** Send only finite core inverse seeds to the distortion solver. Use all-panel mapping wherever a conservative ZEA footprint is unavailable.
- **Next action / responsibility:** Retain the real PA4 replay and timing baseline for future geometry and scheduler changes. Carry the qualified outputs into 6E.
- **Closure condition:** Explain or handle the warning's confirmed cause, retain geometry and coverage checks, and record a repeatable timing comparison on a fixed project.
- **Resolution:** 2026-11-19. The real replay, native previews and full source export no longer emit the warning. The 6A reference and both guarded full ZEA paths match for samples, coverage and WCS. Candidate selection reduced the full-render mapping count from 4,335 to 1,086. TIFF reads account for the largest remaining preview cost. [6D measurements](docs/phase-6.md#local-zea-geometry-and-performance-results) · [ADR-0024](docs/adr/0024-conservative-zea-footprints.md)

### Q-024 - Preview of solved RGB TIFF panels

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-21 / 2026-11-21
- **Affected phase:** Phase 3C desktop preview and export setup.
- **Impact and evidence:** Two verified WCS sidecars reopened successfully. The saved project lacked filter and brightness declarations, and its default sky grid sampled only one panel. The original desktop failure gave a CLI flag instead of the corresponding setting.
- **Current assumption:** Use a grid that covers both panels and supply a common label and scale for compatible linear samples. Linearized sRGB derivatives can be used for a relative visual preview. [Desktop workflow](docs/phase-3c.md#desktop-workflow)
- **Next action / responsibility:** Retain the desktop calibration diagnostic regression when verifying the next Windows build.
- **Closure condition:** Explain the failure in the desktop log and verify a reopened preview that includes each panel and their common coverage.
- **Resolution:** 2026-11-21. The Command Panel identifies the missing settings. A separate project with linear-light visual copies and a fitted grid previewed both panels on native CPU and OpenGL. The source and portable CLI validated the project. The original file hashes matched.
- **Follow-up:** 2026-11-21. Beta 4 assigns `Unspecified` to unlabeled panels. The original project reaches brightness validation, and the packaged CPU and OpenGL backends previewed both real linear TIFF panels with their filter labels removed. [Per-band workflow](docs/phase-5c.md)
- **Follow-up:** 2026-11-21. The latest saved project still referenced the sRGB input TIFFs and the default output grid. A separate visual preview project reused the validated linear-light copies after checking their WCS against the latest sidecars and their sampled values against the sRGB transfer. The beta 6 CLI and native OpenGL checks passed with both panels represented.

### Q-025 - Identify the local Windows build after source changes

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-21 / 2026-11-21
- **Affected phase:** Local Windows desktop builds and handoff.
- **Impact and evidence:** The earlier `0.1.0b2` executable came from a snapshot that preceded the Command Panel startup and sky preview diagnostic fixes. The merged source still reported the same version.
- **Current assumption:** Use the desktop title, versioned runtime folder and recorded source commit to identify a local beta. [Windows build workflow](docs/windows-release.md#build-portable-windows-packages)
- **Next action / responsibility:** Verify the title and the affected workflows on each successor build used for handoff.
- **Closure condition:** Provide a separately identified executable from the merged source and verify both desktop changes in the packaged runtime.
- **Resolution:** 2026-11-21. Local beta 3 reports its own title and carries the source revision and launcher hash. The Command Panel and preview checks passed on native Windows CPU and OpenGL.

### Q-026 - Plate Solve activity before the first panel finishes

- **Status / priority:** Resolved / P2
- **Opened / updated:** 2026-11-21 / 2026-11-21
- **Affected phase:** Phase 3.1C desktop plate solving.
- **Impact and evidence:** The desktop bar showed 0% until the first panel produced an outcome. A single-panel solve could look idle throughout its search. The desktop regression reproduced this display while the worker was active.
- **Current assumption:** Animate the bar during preparation and solves and report the active panel's position in the eligible batch. The desktop job reports completion at panel boundaries.
- **Next action / responsibility:** Retain the desktop regression and the real M13 Windows verification for later builds.
- **Closure condition:** Single-panel and batch solves show activity. The batch labels advance and cancellation preserves completed outcomes.
- **Resolution:** 2026-11-21. Beta 5 rendered distinct animation frames during real single-panel and batch M13 solves in the packaged runtime. Cancellation preserved the first WCS, retry solved the remaining panel, and revalidation animated with CPU and OpenGL previews active. [Windows build verification](docs/windows-release.md#verification-status)

### Q-027 - Dialog-free project lifecycle and headless preparation

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-21 / 2026-11-21
- **Affected phase:** Phase 4A headless automation and Phase 4C desktop commands.
- **Impact and evidence:** The Command Panel could run CLI jobs against saved files. First save, open, relink and closing a dirty desktop project required GUI input. The standalone solver could produce a sidecar for one panel, and batch scripts needed a separate way to attach results to an existing project.
- **Current assumption:** Use explicit session paths and write new manifests for file-based preparation. Accept supplied label masks and numeric placement with the existing geometry validators. Phase 7E tracks saving and rendering terrain control-point geometry.
- **Next action / responsibility:** Keep the session and project preparation regressions in Windows verification for later builds.
- **Closure condition:** The live project can be saved, reopened and exported without dialogs. The standalone CLI can relink, solve and prepare mixed-layer projects from supplied paths, and failures preserve the inputs and permit retry.
- **Resolution:** 2026-11-21. The beta 6 desktop exercised the M13 lifecycle with zero modal dialogs, and the console attached WCS and exported M13 after a deadline retry. The real Paranal run imported label masks, aligned the two ground panels, verified proposed and numeric placement, and reopened the composition. [Windows evidence](docs/windows-release.md#verification-status)

### Q-028 - Automatic sky preview for solved panels

- **Status / priority** Verifying / P1
- **Opened / updated** 2026-11-21
- **Affected phase** Phase 3C desktop sky preview and export setup.
- **Impact and evidence** The beta 6 workflow for the owner TIFFs required a manually framed grid and separate linear-light copies. The original images carry standard sRGB profiles and have usable WCS after offline solving.
- **Current assumption** Fit new sky previews from the selected WCS footprints. Decode recognized unsigned 16-bit RGB sRGB TIFFs in the visual preview. Keep the fitted grid temporary until the user explicitly adopts it. [ADR-0025](docs/adr/0025-automatic-sky-preview.md)
- **Next action / responsibility** Replay the three desktop steps with the original TIFFs on source and packaged Windows.
- **Closure condition** Both original panels solve and appear in the preview with measurable overlap. The saved grid changes only on explicit adoption and scientific export still rejects the encoded panels.

## New Entry Template

```markdown
### Q-NNN - Short descriptive title

- **Status / priority:** Open / P1
- **Opened / updated:** YYYY-MM-DD / YYYY-MM-DD
- **Affected phase:** Phase and the specific action or gate affected.
- **Impact and evidence:** What is uncertain or failing; reproduction or evidence link.
- **Current assumption:** Safe temporary behavior or workaround, including limitations.
- **Next action / responsibility:** Concrete investigation or decision and who can resolve it.
- **Closure condition:** Observable evidence needed to close the topic.
- **Resolution:** Add the date, outcome, and evidence/ADR when resolved.
```
