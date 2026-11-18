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
- **Opened / updated:** 2026-11-15 / 2026-11-17
- **Affected phase:** Phase 0 fixture design and the numerical gates in phases 1, 2, 3.5, 3.6, and 4.
- **Impact and evidence:** The [Phase 1 fixtures](docs/phase-1.md) verify independent FITS export truth. [Phase 2](docs/phase-2.md#acceptance-fixtures) fixes and verifies held-out alignment, stellar flux and profile, injected extended signal, masks, and weak or disconnected inputs. [Phase 3A fixtures](docs/phase-3a.md#acceptance-fixtures) fix sample, channel, coverage, and WCS tolerances for linear TIFF. [Phase 3C](docs/phase-3c.md#windows-verification) confirms preview and export agreement at coincident sample positions. [Phase 3.5A](docs/phase-35.md#frozen-supplementary-fixtures) reran the baseline and froze cases for narrow support, saturation, and explicit DSS crops. The [sidecar check](docs/phase-35.md#masked-wcs-sidecar-reuse) uses the existing bilinear and WCS bounds.
- **Current assumption:** Generate small deterministic same-filter FITS fixtures for development. Store provenance for external data with the validation procedure.
- **Next action / responsibility:** Use the [frozen 3.6A manifest](tests/fixtures/plate_solve_v36.json) for match/RMS, bad-hint, SIP/edge and time tests before tuning B–F, preserving Phase 3.5 envelopes. Then freeze large-mosaic, RGB photometry and mixed-scene tolerances for Phase 4. [3.5 verification results](docs/phase-35.md#phase-35c-windows-verification)
- **Closure condition:** Freeze dataset-specific tolerances before algorithm tuning, including alignment, stellar profiles/flux, injected faint emission, and tiled/reference agreement. Link the fixture manifest and test results.

### Q-005 - Application licensing and distribution model

- **Status / priority:** Open / P1
- **Opened / updated:** 2026-11-15 / 2026-11-15
- **Affected phase:** 0 dependency/license inventory and release packaging; required before license-sensitive code reuse or redistribution.
- **Impact and evidence:** The owner chose `GPL-3.0-only` for the application. The [initial license inventory](docs/phase-0.md#license-inventory) covers SEP, Qt, PyInstaller, ASTAP, and separate D05 data. `fitsio` is a GPL-2.0-or-later development dependency. Seiza is an optional Apache-2.0 backend whose local data are installed separately. TIFF uses BSD-3-Clause tifffile and imagecodecs. [License decision](docs/adr/0009-gpl-v3-application-license.md) · [Seiza decision](docs/adr/0010-seiza-gaia-backend.md) · [tifffile license](https://github.com/cgohlke/tifffile/blob/master/LICENSE) · [imagecodecs license](https://github.com/cgohlke/imagecodecs/blob/master/LICENSE)
- **Current assumption:** Maintain original implementation. Obtain solver binaries and catalog data separately for experiments.
- **Next action / responsibility:** Inventory bundled transitive notices and review catalog redistribution terms for the release.
- **Closure condition:** Record the distribution decision, attribution/license inventory, and compatibility of any reused code or bundled materials. Independent development can continue while this decision is open.

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
- **Affected phase:** Dual FITS and TIFF workflows throughout phases 1-4; optional camera RAW import after a future scope decision.
- **Impact and evidence:** The [Phase 3A Windows fixtures](docs/phase-3a.md#windows-evidence) verified mono and RGB TIFF import and export, including samples, channel order, WCS, and coverage. The [Phase 3B desktop workflow](docs/phase-3b.md#verification) reopens a mixed FITS/TIFF project and renders it to TIFF. [Phase 4B](docs/phase-4b.md#windows-baseline-results) independently verified all samples and coverage in full-size mono FITS, RGB TIFF and mixed exports. Camera RAW is deferred as an import-only feature.
- **Current assumption:** Provide first-class support for both scientific FITS panels and linear TIFF panels across the pipeline. If camera RAW is requested later, use an open-source linear decoder and preserve relevant sensor and color metadata.
- **Next action / responsibility:** Repeat the [packaged Windows exports](docs/phase-3f.md#windows-evidence) on a clean Windows installation. Define and verify channel-specific calibration before enabling RGB photometric refinement. Revisit camera models and decoder compatibility when camera RAW import is requested.
- **Closure condition:** Validate FITS and TIFF sample integrity, metadata, memory, and reproducible import-to-mosaic workflows on Windows. If camera RAW is activated, establish separate acceptance criteria for the selected models.

### Q-010 - Foreground recognition, masks, and composition

- **Status / priority:** Investigating / P1
- **Opened / updated:** 2026-11-15 / 2026-11-18
- **Affected phase:** Phase 2 masked sky processing, Phase 3D mask editing, Phase 3E foreground alignment and composition, Phase 3F packaged acceptance, and Phase 4 resource validation.
- **Impact and evidence:** [Phase 3D](docs/phase-3d.md#windows-verification) verifies local suggestions, manual overrides and masks, and exclusion of foreground from sky fitting. [Phase 3E](docs/phase-3e.md#windows-verification) verifies WCS-free alignment and exports, shared-reference placement, saved edits, and seams with partial and zero common coverage. [Phase 4A](docs/phase-4a.md#local-windows-results) reproduced all three desktop layers from a saved mixed project in the portable CLI. Small, rotated, and ambiguous terrain still needs manual review.
- **Current assumption:** Use the saved three-label mask for same-size, same-scale foreground translations. Use similarity placement between layers and restrict seam blending to valid common coverage.
- **Next action / responsibility:** The [12-panel mixed comparison](docs/phase-4b.md#footprint-selection-results) matched the baseline under the saved limits and known fixture translations. Use real terrestrial captures to measure how often the detector and translation model need manual correction or a broader registration model.
- **Closure condition:** Verify the Phase 2 and 3 mixed-panel gates, including separate layer exports and saved edits, then run the Phase 4 mixed workload within measured memory and worker limits.

### Q-011 - Optional generative fill for a visual seam

- **Status / priority:** Deferred / P2
- **Opened / updated:** 2026-11-15 / 2026-11-15
- **Affected phase:** Optional follow-on to the Phase 3 composition workflow.
- **Impact and evidence:** Uncovered regions may remain after aligning and cropping the sky and foreground layers. The baseline composite exposes the gaps.
- **Current assumption:** Evaluate fill as an opt-in local visual operation restricted to uncovered seam gaps. Keep its synthetic pixels and provenance separately identifiable.
- **Next action / responsibility:** Revisit after the crop and overlap controls are tested and the owner wants fill for remaining gaps. Evaluate open-source software, model weights, licenses, and local resource use then.
- **Closure condition:** If selected, verify that fill is confined to the selected gaps and its synthetic mask and provenance survive export. Scientific layer exports retain observed samples.

### Q-015 - Offline solver coverage on the 40′ Orion field

- **Status / priority:** Open / P2
- **Opened / updated:** 2026-11-17 / 2026-11-18
- **Affected phase:** Phase 3.6A fixtures and 3.6F real-field verification, following the coverage finding in 3.5C.
- **Impact and evidence:** Portable Seiza 0.48.2 solved the 40′ ESO M42 cutout with hints. Its blind index exhausted 400 hypotheses. ASTAP 2026.11.01 with D05 reported an unsuccessful hinted fit and timed out blind. A 55′ M42 cutout solved blind with the same Seiza bundle. [M42 inputs and results](docs/phase-35.md#m42-offline-astrometry-and-documents-catalogs)
- **Current assumption:** Use pointing and scale for the 40′ reference or the tested wider field for blind solving. The 3.6 source runs reproduced hinted 40′ and blind 55′ success. The 40′ blind Gaia retry reached the 30-second cap. [Updated measurements](docs/phase-36-results.md#real-field-source-checks)
- **Next action / responsibility:** Benchmark the 40′ cutout and additional subdegree fields with denser installed ASTAP catalogs under the [Phase 3.6](docs/phase-36.md) priority, quality and total-budget policy. Record measured coverage or supported hint requirements; do not assume density alone fixes the case.
- **Closure condition:** Record validated solutions and elapsed times across a named subdegree sample, or document the supported hint requirements for those fields.

### Q-016 - Plate solve quality, incorrect-scale recovery and distortion

- **Status / priority:** Investigating / P1
- **Opened / updated:** 2026-11-17 / 2026-11-18
- **Affected phase:** Phase 3.6A quality/fixture freeze, 3.6D bad-scale recovery, 3.6E SIP/edge validation and 3.6F acceptance.
- **Impact and evidence:** The [Mosaic Master comparison](docs/plate-solve-comparison.md) verified that the Seiza wrapper retains a supplied scale within 0.8–1.2 on blind retry and does not request SIP (`sip_order=0` in installed Seiza 0.48.2). Blind ASTAP retains a supplied vertical FOV. Existing geometry checks do not independently establish catalog accuracy at field edges. Q-015 separately tracks the real 40′ M42 blind coverage result.
- **Current assumption:** The source uses the common 15-match and RMS gate, Gaia's confidence check, unrestricted Gaia 0.1–120 arcsec/pixel recovery and a spatial holdout for application SIP promotion. Real M13/M42 checks preserve the earlier supported envelopes. ASTAP-only local FOV recovery retains pointing when both hints were supplied. [Measurements](docs/phase-36-results.md)
- **Next action / responsibility:** Broaden real sparse and dense-catalog coverage as separate datasets become available. Local source and portable results retain an explicit insufficient result for unsupported grid regions. [Windows acceptance](docs/phase-36-results.md#portable-windows-verification)
- **Closure condition:** The implemented match/RMS boundaries, bad-hint recovery, supported SIP/edge cases, legacy reuse and Windows source/portable regressions meet the frozen 3.6 gates with independently recorded errors. Planning alone does not resolve this topic.

### Q-017 - Automatic ASTAP catalog selection and ASTAP-only quality evidence

- **Status / priority:** Investigating / P1
- **Opened / updated:** 2026-11-17 / 2026-11-18
- **Affected phase:** Phase 3.6A capabilities, 3.6B catalog automation, 3.6D candidate validation and 3.6F settings/migration.
- **Impact and evidence:** The earlier ASTAP CLI silently substituted D05 for a missing manual D20. The new adapter inventories tiles, checks actual native catalog identity and independently validates the selected catalog. Native D05 Auto passed M13 with 164 measured matches and 0.442″ RMS. Local catalog paths outside the Windows code page used a scratch alias. [Results](docs/phase-36-results.md)
- **Current assumption:** Fresh settings use one Automatic mode; preserve manual choices. Prefer verified native auto with recorded selected data, otherwise resolve to an explicit installed catalog. Use the actual local command-line program. ASTAP-only operation must meet the 15-match/RMS contract without requiring Seiza or treating detections as matches.
- **Next action / responsibility:** Exercise D20, D50 and D80 in real installations with one and several complete sets. Fixtures currently cover alternatives and truncated/moved tiles. Review actual alternate executable versions and catalog terms before adding their support claims.
- **Closure condition:** Automatic/manual modes, actual catalog provenance and the ASTAP-only quality path pass real Windows native cases, including missing/partial catalogs and unknown/bad FOV. Preserve user ASTAP settings and original images; unsupported cases remain explicit.

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

### Q-014 - Regression coverage for narrow overlaps, saturation, and WCS reuse

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-17 / 2026-11-17
- **Affected phase:** 3.5B revision and 3.5C verification.
- **Impact and evidence:** Three automated regressions verify offset selection with a four-pixel overlap, exclusion of saturated stars from gain measurements, and masked WCS reuse. [Review and reproduction](docs/phase-35.md#supplementary-results-and-follow-up) · [3.5B results](docs/phase-35.md#phase-35b-regression-results)
- **Current assumption:** Use deterministic synthetic fixtures for the suite and the recorded M13 and M31 recipes for real-field checks.
- **Next action / responsibility:** Rerun the recorded cases when changing refinement, masks, or WCS reuse.
- **Closure condition:** The added regressions protect the frozen sample, geometry, and fitting criteria. The Windows source and bundled checks meet the recorded thresholds.
- **Resolution:** 2026-11-17. The 88 source tests, identical masked CLI exports for common WCS inputs, and the real-field checks met their thresholds in 3.5C. [Windows verification](docs/phase-35.md#phase-35c-windows-verification)

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
