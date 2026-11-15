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
- **Opened / updated:** 2026-11-15 / 2026-11-15
- **Affected phase:** 0 fixture design; required for numerical gates in phases 1, 2, and 4.
- **Impact and evidence:** The [Phase 1 fixtures](docs/phase-1.md) fix two-panel geometry, masks, weights, tolerances, and independent export truth. Exact pixels and coverage, analytic TAN and SIP checks, and the 1% solid-angle-weighted Gaussian flux check passed.
- **Current assumption:** Generate small deterministic same-filter FITS fixtures for development. Store provenance for external data with the validation procedure.
- **Next action / responsibility:** Freeze injected-gradient, faint-signal, difficult-registration, and supplied sky-mask cases before Phase 2 algorithm tuning. Define dedicated TIFF test samples and Phase 4 tolerances with their workloads.
- **Closure condition:** Freeze dataset-specific tolerances before algorithm tuning, including alignment, stellar profiles/flux, injected faint emission, and tiled/reference agreement. Link the fixture manifest and test results.

### Q-004 - Resource budgets and representative workload

- **Status / priority:** Investigating / P1
- **Opened / updated:** 2026-11-15 / 2026-11-15
- **Affected phase:** 0 scheduling contracts; phases 1 and 4 bounded rendering; phase 3 preview performance.
- **Impact and evidence:** The one-worker FITS renderer enforces a combined tile reservation with no queue. A two-panel 3328 × 1536 render peaked at 89.0 MiB working set and 101.5 MiB commit with one OpenBLAS thread. A tighter reservation produced identical output. Cancellation cleaned up the partial file and released handles. [Phase 1 working set](docs/phase-1.md#working-set-and-cancellation)
- **Current assumption:** Default to 128-pixel tiles, an estimated 64 MiB tile working budget, and a 2048 MiB FITS output limit. Desktop preview and large-job budgets need measurements for their own workloads.
- **Next action / responsibility:** Account for GUI/GPU and cache use in Phase 3. Repeat bounded-render and cancellation checks in Phase 4 with 12 panels at 6000 × 4000 for FITS, TIFF, RGB, and mixed cases.
- **Closure condition:** Document initial defaults and over-budget behavior; verify bounded queues, temporary allocations, cancellation, and peak usage for a named workload. Revisit defaults during the Phase 4 large-mosaic benchmark.

### Q-005 - Application licensing and distribution model

- **Status / priority:** Open / P1
- **Opened / updated:** 2026-11-15 / 2026-11-15
- **Affected phase:** 0 dependency/license inventory and release packaging; required before license-sensitive code reuse or redistribution.
- **Impact and evidence:** The [initial license inventory](docs/phase-0.md#license-inventory) identifies LGPL-licensed SEP, Qt for Python options, PyInstaller's exception, external ASTAP, and separate D05 data. `fitsio` is scoped to development tests and carries GPL-2.0-or-later. The owner confirmed open-source distribution and open-source components. The exact application license and distribution notices remain undecided. [Phase 1 dependency evidence](docs/phase-1.md#numerical-and-windows-checks)
- **Current assumption:** Maintain original implementation. Obtain solver binaries and catalog data separately for experiments.
- **Next action / responsibility:** Inventory bundled transitive notices and catalog redistribution terms. Evaluate compatible open-source license options. The owner selects the exact application license.
- **Closure condition:** Record the distribution decision, attribution/license inventory, and compatibility of any reused code or bundled materials. Independent development can continue while this decision is open.

### Q-006 - Offline solver and catalog deployment

- **Status / priority:** Investigating / P1
- **Opened / updated:** 2026-11-15 / 2026-11-15
- **Affected phase:** 0 adapter experiment and 2 offline astrometry; does not block Phase 1 fixtures with valid WCS.
- **Impact and evidence:** [ASTAP CLI 2026.11.01 and D05](docs/phase-0.md#offline-astap-experiment) solved an M13 DSS cutout on Windows. Output agreed with the archive header to 0.36 arcseconds. Verified source hash, Unicode image basename, missing catalog, real timeout cleanup, and simulated interrupt cleanup.
- **Current assumption:** Use validated WCS, local Gaia DR3, hinted ASTAP, then blind ASTAP. The verified D05 case used a hinted 0.92° field. Use explicit local catalogs and separate scratch files.
- **Next action / responsibility:** Select an open-source Gaia backend and local index or catalog deployment. Test hinted and blind ASTAP and the full fallback order on representative Windows fixtures. Define catalog update and integrity checks.
- **Closure condition:** Record a tested solver/version/catalog matrix and deployment/update policy, including ordered fallbacks, cancellation, missing-catalog diagnostics, exhausted-chain behavior, and unchanged-source checks.

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
- **Opened / updated:** 2026-11-15 / 2026-11-15
- **Affected phase:** Dual FITS and TIFF workflows throughout phases 1-4; optional camera RAW import after a future scope decision.
- **Impact and evidence:** Both FITS and TIFF are primary, first-class workflows. Camera RAW is deferred and may be revisited as an import-only feature.
- **Current assumption:** Provide first-class support for both scientific FITS panels and linear TIFF panels across the pipeline. If camera RAW is requested later, use an open-source linear decoder and preserve relevant sensor and color metadata.
- **Next action / responsibility:** Define TIFF scaling, channel layout, WCS/coverage metadata, and sample fixtures alongside the [verified FITS contract](docs/phase-1.md#render-and-export-contract). Verify linear mono and RGB TIFF input and output before Phase 3 acceptance. Revisit camera models and decoder compatibility when camera RAW import is requested.
- **Closure condition:** Validate FITS and TIFF sample integrity, metadata, memory, and reproducible import-to-mosaic workflows on Windows. If camera RAW is activated, establish separate acceptance criteria for the selected models.

### Q-010 - Foreground recognition, masks, and composition

- **Status / priority:** Open / P1
- **Opened / updated:** 2026-11-15 / 2026-11-15
- **Affected phase:** Phase 2 masked sky processing, Phase 3 mixed-panel desktop workflow, and Phase 4 resource validation.
- **Impact and evidence:** Mixed panels need a foreground tag, an editable sky mask, two registrations, and a reproducible horizon seam. Automatic classification, boundary accuracy, and alignment confidence have no measured baseline yet.
- **Current assumption:** Use local thumbnail detection, separate segmentation, and image-space foreground registration. Derive an automatic composition proposal from a shared mixed panel and provide manual adjustment. Start with the overlap percentage convention in the [plan](astro_mosaic_python_first_architecture_en.md#67-mixed-sky-and-foreground-panels).
- **Next action / responsibility:** Define mixed FITS and TIFF fixtures with known masks and overlaps. Measure detection latency and segmentation error on low-contrast and irregular horizons. Test manual corrections, mismatched frames, and seams with partial or zero common coverage before selecting backends.
- **Closure condition:** Verify the Phase 2 and 3 mixed-panel gates, including separate layer exports and saved edits, then run the Phase 4 mixed workload within measured memory and worker limits.

### Q-011 - Optional generative fill for a visual seam

- **Status / priority:** Deferred / P2
- **Opened / updated:** 2026-11-15 / 2026-11-15
- **Affected phase:** Optional follow-on to the Phase 3 composition workflow.
- **Impact and evidence:** Uncovered regions may remain after aligning and cropping the sky and foreground layers. The baseline composite exposes the gaps.
- **Current assumption:** Evaluate fill as an opt-in local visual operation restricted to uncovered seam gaps. Keep its synthetic pixels and provenance separately identifiable.
- **Next action / responsibility:** Revisit after the crop and overlap controls are tested and the owner wants fill for remaining gaps. Evaluate open-source software, model weights, licenses, and local resource use then.
- **Closure condition:** If selected, verify that fill is confined to the selected gaps and its synthetic mask and provenance survive export. Scientific layer exports retain observed samples.

## Resolved Topics

### Q-001 - Python, dependency, and platform compatibility matrix

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-15 / 2026-11-15
- **Affected phase:** 0.
- **Impact and evidence:** CPython 3.13 and the Poetry lock passed native imports, CLI and worker startup, ASTAP, PySide6, and two local bundle runs on Windows 11 x64.
- **Current assumption:** Use CPython 3.13 and the optional PySide6 Essentials extra for the initial Windows target.
- **Next action / responsibility:** Verify clean-machine installation during release packaging. Revisit additional platforms under Q-008.
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
