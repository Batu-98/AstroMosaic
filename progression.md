# Development Progress

Use this file for concise development history and handoff state. Detailed technical decisions belong in `docs/adr/`; unresolved work belongs in [questions_open_topics.md](questions_open_topics.md).

## Current State

- **Last updated:** 2026-11-15
- **Active baseline:** Python-first architecture revision 3.5. See [ADR-0003](docs/adr/0003-windows-first-platform-scope.md) for Windows scope, [ADR-0006](docs/adr/0006-dual-fits-and-tiff-workflow.md) for formats, and [ADR-0007](docs/adr/0007-sky-and-foreground-mosaics.md) for mixed panels.
- **Current stage:** The Phase 1 headless FITS gate passed on Windows 11 x64. Linear mono/RGB TIFF validation follows before Phase 3 acceptance. Linux and macOS support is deferred.
- **Available artifacts:** Tiled FITS mosaic CLI, the [Phase 1 reference and resource measurements](docs/phase-1.md), a local Windows CLI bundle at `dist/astromosaic-cli-phase1`, and the earlier ASTAP D05 and PySide6 viewport probes.
- **Implementation / verification:** 28 tests, Ruff lint and format, mypy, and Poetry lock checks passed. The Windows CLI bundle rendered the two-panel reference and ran `inspect` and `smoke --spawn` from an unrelated directory. CFITSIO verified the output. Two larger runs verified identical pixels and coverage under different working budgets.
- **Version control:** The initial `main` snapshot is prepared for the private [AstroMosaic GitHub repository](https://github.com/Batu-98/AstroMosaic).
- **Next action:** Define the linear mono/RGB TIFF data and metadata contract and its fixtures. Freeze the Phase 2 reference cases before tuning registration and photometry.
- **Open dependencies:** Q-003 through Q-006, Q-009, and Q-010 track later numerical, resource, solver, distribution, and mixed-panel gates. Q-008 tracks deferred platforms and Q-011 tracks deferred visual fill. Q-007 is resolved for FITS export.

## Phase Overview

The table is a status summary, not a replacement for the full exit gates in Section 10 of the active architecture. Update it when evidence changes. Keep partial or unavailable validation visible.

| Phase | Status | Required exit evidence |
| --- | --- | --- |
| Preparation | Complete | Agent instructions, English documentation, tracking conventions, active-plan identification, and next task established. |
| 0 - Compatibility and scope | Complete | Locked environment, initial fixtures/contracts, solver and PySide float-texture experiments, packaged skeleton, and a small job verified on Windows 11 x64. |
| 1 - Headless reference | FITS gate passed | Correct two-panel FITS geometry, values, and coverage, independent reopening, bounded access, and a Qt-free CLI verified. Linear mono/RGB TIFF validation is due before Phase 3 acceptance. |
| 2 - Robust astronomy engine | Not started | Local Gaia and ASTAP solving, masked sky checks, overlap registration, relative stellar scales, constrained backgrounds, held-out and injected-signal checks, and explicit weak or disconnected states. |
| 3 - Desktop workflow | Not started | Responsive projects and jobs, foreground tags and editable masks, separate foreground stitching, automatic and manual composition, preview/export agreement, recovery, and CPU fallback on Windows. |
| 4 - Large mosaics and improved blends | Not started | Budgeted rendering of 12 FITS and TIFF panels at 6000 × 4000, including a mixed scene, incremental export, tile/halo correctness, and measured improvement for any optional multiband blend. |
| 5 - Extended formats and channels | Not started | Format/channel/projection contracts and packaging checks for each added workflow. |

## Journal Rules

- Append an entry after each meaningful completed, partial, failed, or decision step and before handoff. Do not log every tool call.
- Keep older entries intact; append corrections. The current-state summary and phase table may be edited in place.
- Use a dated heading and three to five short bullets: change, verification, related topics/decisions, and next action.
- Distinguish implementation completion from phase acceptance. Record checks that could not run and do not imply they passed.
- Dates use ISO format. Optional timestamps use `Europe/Istanbul` with an explicit UTC offset.

## Journal

### 2026-11-15 - Preparation - Completed: development workflow established

- **Changed:** Added `AGENTS.md`, `README.md`, `questions_open_topics.md`, this journal, and ADR-0001. Established English project language, bounded development steps, scientific safeguards, and mandatory issue/progress updates.
- **Verified:** Reviewed both supplied plans and confirmed revision 3.0 explicitly supersedes the earlier infrastructure. Initial workspace inspection found only those plans and no Git repository; application tests were not applicable.
- **Related:** ADR-0001 identifies the existing Python/PySide6 baseline. Q-001 through Q-007 capture compatibility, units, fixtures, budgets, licensing, solving, and FITS validation decisions.
- **Next:** Validate the new documents, then hand off the Phase 0 package/CLI and compatibility work. No application implementation is claimed by this preparation step.

### 2026-11-15 - Preparation - Completed: documentation checks passed

- **Changed:** Finalized the five new guidance/tracking documents and the initial Phase 0 handoff; retained both supplied architecture documents unchanged.
- **Verified:** Local-link and nonempty-file checks passed across all seven Markdown files; code fences are balanced and all seven seeded topic IDs are unique. Reviewed the new text for English language and consistency with revision 3.0. No application tests were run because no implementation exists yet.
- **Related:** Q-001 through Q-007 remain open with explicit actions and closure conditions; ADR-0001 records baseline selection without claiming platform compatibility.
- **Next:** Start Phase 0 with local version control, the minimal package/headless CLI, dependency checks, and numerical contracts. The development preparation request is complete.

### 2026-11-15 - Preparation - Completed: simplified agent instructions

- **Changed:** Shortened `AGENTS.md` by about two thirds, removed repeated technical detail, and reduced Section 7 to four practical completion checks. Detailed feature and phase requirements remain in the architecture plan.
- **Verified:** Reviewed the English text and preserved the baseline, data-protection rules, and tracking duties. Local links passed; application tests were not needed for this documentation edit.
- **Related:** No new open topics or architecture decisions.
- **Next:** Use the simplified instructions for Phase 0 development.

### 2026-11-15 - Phase 0 - Started: local runtime and headless scaffold

- **Changed:** Initialized local Git and added repository ignore rules, a Python 3.13 Poetry manifest, a headless CLI, and an initial bounded FITS cutout job.
- **Verified:** Installed CPython 3.13.18 and Poetry 2.5.1 in workspace-local tooling on Windows x64. Local WSL has no Linux distribution. Dependency and application checks follow the lock installation.
- **Related:** Q-001, Q-003, Q-004, Q-007.
- **Next:** Exercise the synthetic job and numerical contracts, then run the independent desktop and offline-solver experiments.

### 2026-11-15 - Phase 0 - Partial: headless checks and first ASTAP solve

- **Changed:** Locked the scientific stack and verified read-only primary FITS access with raw scaling, validity, bounded sections, and an analytic TAN reference. Added a D05 ASTAP probe that isolates source files from solver writes.
- **Verified:** The first 12 tests and the synthetic CLI job passed on Windows x64, including a real spawned worker in an installation without Qt. ASTAP solved a public DSS cutout. Filtering legacy DSS plate keywords and cross-checking ASTAP's two output files recovered the solved WCS.
- **Related:** The initial all-wheel-only install exposed the `pims` source build. Packaging with pytest installed caused the Astropy hook to abort in optional visualization discovery. The build group allows a clean retry without the test toolchain. Q-001, Q-003, Q-006, Q-007.
- **Next:** Verify the packaged CLI, exercise the signed-texture desktop probe and CPU path, and record the remaining platform gates.

### 2026-11-15 - Phase 0 - Partial: Windows compatibility experiments passed

- **Changed:** Added the signed R32F/TAN desktop probe with a CPU raster path, documented the first numerical and resource contracts, and recorded the surface-brightness decision in [ADR-0002](docs/adr/0002-surface-brightness-reference.md).
- **Verified:** 14 tests, Ruff, mypy, and Poetry lock validation passed. The frozen CLI inspected a synthetic FITS file and ran the cutout in a spawned worker. The frozen viewport passed context recreation, 1× and 2× framebuffer checks, and automatic CPU fallback. ASTAP matched the DSS reference to 0.36 arcseconds with unchanged input and verified timeout cleanup.
- **Related:** The initial Windows desktop bundle selected a foreign ICU DLL from `PATH`. A clean-path rebuild and rerun passed. [Phase 0 evidence](docs/phase-0.md) records the build steps, the measured smoke job, licenses, and target matrix. Local link and ignore-rule checks passed. The superseded, ignored `.tooling/venv-qt-meta` environment remains on disk because the tooling policy blocked recursive cleanup.
- **Next:** Collect native Ubuntu and macOS results before closing Phase 0. The separate Phase 1 gate still requires a bounded two-panel render and independent FITS export checks.

### 2026-11-15 - Phase 0 - Completed: Windows-first development gate

- **Changed:** Revised the active plan to 3.1 and recorded the owner's Windows 11 x64 scope in [ADR-0003](docs/adr/0003-windows-first-platform-scope.md). Deferred Linux and macOS support.
- **Verified:** Reviewed the revised gate against the existing Windows job, dependency lock, ASTAP and viewport experiments, and packaged runs. Reviewed the affected documents and local links. Application tests were not repeated for this documentation change.
- **Related:** Q-001 is resolved for Phase 0 and Q-008 tracks later platform support. Reviewed Mosaic Master's local Gaia and web fallback paths alongside the general solver chain.
- **Next:** Define the two-panel Phase 1 reference fixture.

### 2026-11-15 - Scope update - Open-source TIFF workflow and camera RAW

- **Changed:** Recorded open-source distribution and components, the 12-panel 6000 × 4000 TIFF target, and camera RAW priority in revision 3.2 and [ADR-0004](docs/adr/0004-open-source-image-workflow.md).
- **Verified:** Reviewed milestone and topic consistency and checked local links. This documentation change required no application tests.
- **Related:** Q-004 tracks resource measurements, Q-005 tracks the exact license and notices, and Q-009 tracks the camera RAW input contract.
- **Next:** Define the two-panel FITS reference and use its numerical contracts for the TIFF workflow.

### 2026-11-15 - Scope update - Offline solver chain and deferred camera RAW

- **Changed:** Revised the plan to 3.3. Recorded WCS reuse, local Gaia DR3, hinted ASTAP, and blind ASTAP in order. Deferred camera RAW as an import-only option.
- **Verified:** Reviewed milestone scope and checked local links. The hinted ASTAP probe remains the existing runtime evidence. This documentation update did not implement the chain.
- **Related:** [ADR-0005](docs/adr/0005-offline-solver-chain.md), Q-006, and Q-009.
- **Next:** Continue with the Phase 1 FITS reference fixture. Implement and validate the full local chain in Phase 2.

### 2026-11-15 - Scope update - Dual first-class FITS and TIFF workflows

- **Changed:** Revised the plan to 3.4 and recorded first-class status for both FITS and linear TIFF panels in [ADR-0006](docs/adr/0006-dual-fits-and-tiff-workflow.md), amending [ADR-0004](docs/adr/0004-open-source-image-workflow.md). Updated 12-panel 6000 × 4000 benchmark targets to cover both formats.
- **Verified:** Reviewed consistency across `astro_mosaic_python_first_architecture_en.md`, `README.md`, `questions_open_topics.md`, and `AGENTS.md`. Checked local markdown links.
- **Related:** [ADR-0004](docs/adr/0004-open-source-image-workflow.md), [ADR-0006](docs/adr/0006-dual-fits-and-tiff-workflow.md), Q-004, and Q-009.
- **Next:** Define the Phase 1 deterministic two-panel FITS fixture and proceed with reference headless mosaic engine development.

### 2026-11-15 - Scope update - Mixed sky and foreground mosaics

- **Changed:** Revised the plan to 3.5. Added foreground tagging, editable masks, independent sky and foreground stitching, and composition controls for placement, seam overlap, and sky-edge crop.
- **Verified:** Reviewed scope and milestone consistency, checked local document links, and recorded the requirements in [ADR-0007](docs/adr/0007-sky-and-foreground-mosaics.md). This was a documentation update.
- **Related:** Q-010 tracks mixed-panel validation. Q-011 tracks optional generative fill for visual seam gaps.
- **Next:** Define the Phase 1 two-panel FITS reference fixture. Introduce supplied sky masks in Phase 2 and the mixed-panel desktop workflow in Phase 3.

### 2026-11-15 - Phase 1 - Started: two-panel FITS reference

- **Changed:** Defined the scaled-integer and float FITS fixtures, weighted overlap, expected pixels and mask, and analytic TAN checks. Locked CFITSIO-backed `fitsio` in the development group for independent reopening.
- **Verified:** The 14 baseline tests passed. Generated both panels and checked their dimensions, sample decoding, and selected values against the [fixture manifest](docs/phase-1.md#two-panel-fixture). The reference has 65 covered pixels.
- **Related:** Q-003, Q-004, Q-007, and ADR-0002.
- **Next:** Implement the renderer, incremental export, and CLI against the frozen reference.

### 2026-11-15 - Phase 1 - Implemented: tiled FITS mosaic and export

- **Changed:** Added the Qt-free `mosaic` command, validated WCS reuse, per-tile masked sampling and weighted blending, and atomic float32 FITS export with binary `COVERAGE`.
- **Verified:** The two-panel demonstration reopened through CFITSIO with all 65 covered pixels and the full mask matching the independent reference. Astropy also verified the FITS structure.
- **Related:** Q-003, Q-004, Q-007, and ADR-0002.
- **Next:** Run the full tests, measure a larger two-panel render and cancellation, and exercise the Windows CLI bundle.

### 2026-11-15 - Phase 1 - Verified: bounded FITS reference on Windows

- **Changed:** Defaulted the mosaic CLI to one OpenBLAS thread after measuring library import commit. Documented the bounded sampler decision, export contract, and Windows measurements.
- **Verified:** 28 tests, Ruff, mypy, and lock validation passed. CFITSIO verified all 5,111,808 pixels and coverage values with two tile reservations. The 64 MiB budget case used 89.0 MiB peak working set and 101.5 MiB peak commit. Cancellation cleaned up at the next tile boundary. The new headless Windows bundle passed the reference mosaic, inspection, and spawned smoke checks from an unrelated directory. The local DSS geometry comparison also passed.
- **Related:** [Phase 1 evidence](docs/phase-1.md), [ADR-0008](docs/adr/0008-bounded-fits-sampling.md), and Q-003, Q-004, Q-007, Q-009. Q-007 is resolved for the FITS output contract.
- **Next:** Define the TIFF metadata and sample contract before desktop acceptance. Phase 2 solver, registration, and photometric acceptance cases remain open.

### 2026-11-15 - Repository setup - Prepared initial GitHub snapshot

- **Changed:** Created the private GitHub repository and prepared the source code, tests, dependency lock, and documentation for the initial commit.
- **Verified:** Reviewed the file list against the ignore rules for local tooling, images, catalogs, caches, and build outputs.
- **Next:** Push `main` and verify the remote commit.

## Entry Template

Copy this format into a new entry immediately above this template, preserving chronological order:

```markdown
### YYYY-MM-DD - Phase N - Status: short outcome

- **Changed:** Brief summary of useful work, or the attempted step if incomplete.
- **Verified:** Relevant commands/checks and their result; identify unavailable checks.
- **Related:** Question IDs, ADRs, or evidence paths; use "None" when appropriate.
- **Next:** One concrete next step and any blocker that affects it.
```
