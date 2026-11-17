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
- **Opened / updated:** 2026-11-15 / 2026-11-16
- **Affected phase:** Phase 0 fixture design and the numerical gates in phases 1, 2, 3.5, and 4.
- **Impact and evidence:** The [Phase 1 fixtures](docs/phase-1.md) verify independent FITS export truth. [Phase 2](docs/phase-2.md#acceptance-fixtures) fixes and verifies held-out alignment, stellar flux and profile, injected extended signal, masks, and weak or disconnected inputs. [Phase 3A fixtures](docs/phase-3a.md#acceptance-fixtures) fix sample, channel, coverage, and WCS tolerances for linear TIFF. [Phase 3C](docs/phase-3c.md#windows-verification) confirms preview and export agreement at coincident sample positions.
- **Current assumption:** Generate small deterministic same-filter FITS fixtures for development. Store provenance for external data with the validation procedure.
- **Next action / responsibility:** In [Phase 3.5A](astro_mosaic_python_first_architecture_en.md#phase-35-astronomy-engine-revalidation), review the Phase 2 reference coverage and freeze thresholds for any added cases before revising the engine. Freeze large-mosaic, RGB photometry, and mixed-scene tolerances for Phase 4.
- **Closure condition:** Freeze dataset-specific tolerances before algorithm tuning, including alignment, stellar profiles/flux, injected faint emission, and tiled/reference agreement. Link the fixture manifest and test results.

### Q-004 - Resource budgets and representative workload

- **Status / priority:** Investigating / P1
- **Opened / updated:** 2026-11-15 / 2026-11-16
- **Affected phase:** Phase 0 scheduling contracts, Phase 1 rendering, Phase 2 solvers and fitting, Phase 3 preview, and Phase 4 large-job scaling.
- **Impact and evidence:** The one-worker FITS renderer enforces a combined tile reservation with no queue. A two-panel 3328 × 1536 render peaked at 89.0 MiB working set and 101.5 MiB commit with one OpenBLAS thread. An unhinted Gaia solve with the deep native index peaked at 1066 MiB working set and 281 MiB commit. The desktop preview of the same two-panel workload peaked at 226.7/259.8 MiB on OpenGL and 175.9/164.0 MiB on CPU for working set and commit. [Phase 1 rendering measurements](docs/phase-1.md#working-set-and-cancellation) · [Phase 2 solver measurements](docs/phase-2.md#windows-solver-evidence) · [Phase 3C preview measurements](docs/phase-3c.md#resource-check)
- **Current assumption:** Default to 128-pixel render tiles, an estimated 64 MiB working buffer budget, and a 2048 MiB output limit. Reserve the active preview raster in the job budget and cap its longest edge at 512 pixels. Account for the display buffers, Qt framebuffers, and driver allocation separately. [TIFF](docs/phase-3a.md#sample-and-metadata-contract) reserves compressed-segment decode buffers as well as the requested window. Budget native catalog mappings separately from science tiles. The [Phase 2 solver settings](docs/phase-2.md#offline-solvers) include a separate ASTAP staging limit.
- **Next action / responsibility:** The [Phase 3F package checks](docs/phase-3f.md#windows-evidence) passed background cancellation and retry on Windows. Repeat bounded-render and cancellation checks in Phase 4 with 12 panels at 6000 × 4000 for FITS, TIFF, RGB, and mixed cases.
- **Closure condition:** Document initial defaults and over-budget behavior; verify bounded queues, temporary allocations, cancellation, and peak usage for a named workload. Revisit defaults during the Phase 4 large-mosaic benchmark.

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
- **Opened / updated:** 2026-11-15 / 2026-11-16
- **Affected phase:** Dual FITS and TIFF workflows throughout phases 1-4; optional camera RAW import after a future scope decision.
- **Impact and evidence:** The [Phase 3A Windows fixtures](docs/phase-3a.md#windows-evidence) verified mono and RGB TIFF import and export, including samples, channel order, WCS, and coverage. The [Phase 3B desktop workflow](docs/phase-3b.md#verification) reopens a mixed FITS/TIFF project and renders it to TIFF. Camera RAW is deferred as an import-only feature.
- **Current assumption:** Provide first-class support for both scientific FITS panels and linear TIFF panels across the pipeline. If camera RAW is requested later, use an open-source linear decoder and preserve relevant sensor and color metadata.
- **Next action / responsibility:** Repeat the [packaged Windows exports](docs/phase-3f.md#windows-evidence) on a clean Windows installation. Define and verify channel-specific calibration before enabling RGB photometric refinement. Revisit camera models and decoder compatibility when camera RAW import is requested.
- **Closure condition:** Validate FITS and TIFF sample integrity, metadata, memory, and reproducible import-to-mosaic workflows on Windows. If camera RAW is activated, establish separate acceptance criteria for the selected models.

### Q-010 - Foreground recognition, masks, and composition

- **Status / priority:** Investigating / P1
- **Opened / updated:** 2026-11-15 / 2026-11-16
- **Affected phase:** Phase 2 masked sky processing, Phase 3D mask editing, Phase 3E foreground alignment and composition, Phase 3F packaged acceptance, and Phase 4 resource validation.
- **Impact and evidence:** [Phase 3D](docs/phase-3d.md#windows-verification) verifies local suggestions, manual overrides and masks, and exclusion of foreground from sky fitting. [Phase 3E](docs/phase-3e.md#windows-verification) verifies WCS-free alignment and exports, shared-reference placement, saved edits, and seams with partial and zero common coverage. Small, rotated, and ambiguous terrain still needs manual review.
- **Current assumption:** Use the saved three-label mask for same-size, same-scale foreground translations. Use similarity placement between layers and restrict seam blending to valid common coverage.
- **Next action / responsibility:** The [mixed-panel workflow](docs/phase-3f.md#windows-evidence) passed in the Phase 3F bundle on the development host. Use real terrestrial captures to measure how often the detector and translation model need manual correction or a broader registration model. Verify the 12-panel mixed workload in Phase 4.
- **Closure condition:** Verify the Phase 2 and 3 mixed-panel gates, including separate layer exports and saved edits, then run the Phase 4 mixed workload within measured memory and worker limits.

### Q-011 - Optional generative fill for a visual seam

- **Status / priority:** Deferred / P2
- **Opened / updated:** 2026-11-15 / 2026-11-15
- **Affected phase:** Optional follow-on to the Phase 3 composition workflow.
- **Impact and evidence:** Uncovered regions may remain after aligning and cropping the sky and foreground layers. The baseline composite exposes the gaps.
- **Current assumption:** Evaluate fill as an opt-in local visual operation restricted to uncovered seam gaps. Keep its synthetic pixels and provenance separately identifiable.
- **Next action / responsibility:** Revisit after the crop and overlap controls are tested and the owner wants fill for remaining gaps. Evaluate open-source software, model weights, licenses, and local resource use then.
- **Closure condition:** If selected, verify that fill is confined to the selected gaps and its synthetic mask and provenance survive export. Scientific layer exports retain observed samples.

### Q-012 - Desktop terminal scope

- **Status / priority:** Open / P2
- **Opened / updated:** 2026-11-16 / 2026-11-16
- **Affected phase:** 4C desktop terminal panel.
- **Impact and evidence:** The packaged CLI already runs in a Windows terminal. An in-app AstroMosaic command panel can reuse the Phase 4A interface. An embedded Windows shell would require different interaction and process handling. [Windows CLI package](docs/phase-3f.md#build) · [Phase 4 stages](astro_mosaic_python_first_architecture_en.md#102-phase-4-delivery-stages)
- **Current assumption:** Provide an in-app AstroMosaic command panel with session history, job output, progress, and cancellation.
- **Next action / responsibility:** Review the expected terminal workflows at the start of Phase 4C and record the selected scope.
- **Closure condition:** Record the selected desktop terminal scope and verify its agreed workflows on Windows 11 x64.

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
- **Opened / updated:** 2026-11-15 / 2026-11-15
- **Affected phase:** Phase 0 adapter experiment, Phase 2 offline astrometry, and Phase 3.1 desktop solver settings and jobs.
- **Impact and evidence:** The Windows M13 reference passed both hinted and blind Gaia DR3 and ASTAP, ordered fallback, real ASTAP cancellation, missing-catalog diagnostics, and unchanged-source checks. The catalog and index were verified against the versioned manifest.
- **Current assumption:** Install explicit local Gaia and ASTAP files separately, keep the Gaia catalog and index version paired, and save solved WCS in a source-bound sidecar.
- **Next action / responsibility:** Recheck the solver matrix through the desktop job in Phase 3.1C, on catalog updates, and during release packaging. Release notices and data terms remain under Q-005.
- **Closure condition:** Record a tested solver/version/catalog matrix and deployment/update policy, including ordered fallbacks, cancellation, missing-catalog diagnostics, exhausted-chain behavior, and unchanged-source checks.
- **Resolution:** 2026-11-15. [ADR-0010](docs/adr/0010-seiza-gaia-backend.md) records the backend. The [Phase 2 solver matrix and setup](docs/phase-2.md#offline-solvers) record results, catalog provenance, and the update procedure.

### Q-013 - Optical metadata conventions for solve hints

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-16 / 2026-11-16
- **Affected phase:** 3.1A panel metadata.
- **Impact and evidence:** FITS writers may report native or effective pixel pitch. The reader supports numeric FITS-style optical fields in FITS and AstroMosaic TIFF. Binned fixtures verify native and effective pitch, while a conventional TIFF resolution tag leaves the optical values unset. [Optics tests](tests/integration/test_panel_inspection.py)
- **Current assumption:** Interpret the documented field conventions and use panel overrides or a compatible blind solve when the image has no reliable scale hint.
- **Next action / responsibility:** Evaluate additional metadata mappings when a representative acquisition export establishes its field meaning and units.
- **Closure condition:** Document supported conventions and verify the derived scale and missing-metadata behavior with representative fixtures, including a binned case.
- **Resolution:** 2026-11-16. Synthetic FITS and TIFF cases passed, including stale masked WCS and ambiguous binning. Local Gaia and ASTAP solved M13 using embedded optical hints. [Supported metadata and Windows evidence](docs/phase-3b.md#panel-wcs-and-plate-solve-hints)

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
