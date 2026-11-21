# Development Progress

Use this file for concise development history and handoff state. Detailed technical decisions belong in `docs/adr/`; unresolved work belongs in [questions_open_topics.md](questions_open_topics.md).

## Current State

- **Last updated:** 2026-11-21
- **Active baseline:** Python-first architecture revision 3.12 adds [Phase 7 delivery stages](astro_mosaic_python_first_architecture_en.md#105-phase-7-delivery-stages). [ADR-0023](docs/adr/0023-terrain-control-point-registration.md) records the translation and similarity decision. [ADR-0017](docs/adr/0017-astap-first-validated-solving.md) records the solver policy. See [ADR-0003](docs/adr/0003-windows-first-platform-scope.md) for Windows scope, [ADR-0006](docs/adr/0006-dual-fits-and-tiff-workflow.md) for formats, and [ADR-0007](docs/adr/0007-sky-and-foreground-mosaics.md) for mixed panels.
- **Current stage:** [Phases 6A–6D](docs/phase-6.md) and [local 6E](docs/phase-6.md#local-windows-lifecycle-and-package-results) passed on Windows. [Phase 7E](docs/phase-7.md#7e-local-windows-package-results) integrates the translation and similarity geometry evaluated in 7A–7D. The 7F desktop review workflow, clean-machine acceptance and native distribution review remain open. Linux and macOS support is deferred.
- **Available artifacts:** The verified beta 8 desktop and console are in `dist/AstroMosaic-0.1.0b8-windows-x64/` and `dist/astromosaic-cli-0.1.0b8-windows-x64/` with their build records. Earlier local betas remain in their versioned folders. The [application test guide](docs/application-tests.md) and [extended cases](docs/application-tests-extension.md) describe the ignored real-observation fixtures. [Release guide](docs/windows-release.md#verification-status)
- **Implementation / verification:** Beta 8 source and portable CLI and desktop produced identical Oxford Boat foreground FITS exports. The legacy ALPACA export, separate Paranal sky and composition, and real rejection checks passed. Source passed 220 offscreen and two native OpenGL tests. Ruff, scoped mypy and the Poetry lock check passed. [7E evidence](docs/phase-7.md#7e-local-windows-package-results)
- **Version control:** The current development version on `main` is `0.1.0b8`. The first published source beta uses the annotated Git tag `v0.1.0b1`. [AstroMosaic GitHub repository](https://github.com/Batu-98/AstroMosaic)
- **Next action:** Add 7F desktop control-point review and editing, then repeat the real validation matrix. Keep the 7C SIFT provider optional pending clean-machine checks and native distribution review under Q-005. Tagged release packaging and fresh Windows acceptance remain open. [7F plan](docs/phase-7.md#7f-ship-the-review-workflow-and-verify-windows)
- **Proposed follow-up** [Phase 8](docs/phase-8.md) covers full-resolution photo export and selectable color, brightness, lens and vignetting methods. Q-029 tracks the proposed acceptance data and backend choices.
- **Open dependencies:** Q-003 tracks reference data and frozen criteria. Q-010 tracks real-scene diagnostics and the proposed terrain models. Q-016 tracks astrometry. Q-005, Q-009 and Q-020 track distribution and format work. Q-008 tracks deferred platforms and Q-011 deferred visual fill. Resolved Q-022 and Q-023 record the Windows lifecycle and ZEA results.

## Phase Overview

The table is a status summary, not a replacement for the full exit gates in Section 10 of the active architecture. Update it when evidence changes. Keep partial or unavailable validation visible.

| Phase | Status | Required exit evidence |
| --- | --- | --- |
| Preparation | Complete | Agent instructions, English documentation, tracking conventions, active-plan identification, and next task established. |
| 0 - Compatibility and scope | Complete | Locked environment, initial fixtures/contracts, solver and PySide float-texture experiments, packaged skeleton, and a small job verified on Windows 11 x64. |
| 1 - Headless reference | Complete | Correct two-panel FITS geometry, values, and coverage, independent reopening, bounded access, and a Qt-free CLI. The deferred TIFF checkpoint passed in Phase 3A. |
| 2 - Robust astronomy engine | Original gate passed | Verified local Gaia/ASTAP fallback, supplied sky masks, anchored overlap registration and stellar gains, offset/plane selection, held-out and injected-signal gates, and weak/disconnected diagnostics on Windows. |
| 3A - Linear TIFF | Complete | Mono/RGB input and output verified on Windows for samples, channels, WCS, and coverage. |
| 3B - Projects and jobs | Complete | Project save/reopen, panel relinking, responsive progress, and cancellation verified on native Windows Qt. |
| 3C - Preview and export | Complete | Verified shared preview/export geometry, automatic sky framing, sRGB visual previews, pan and zoom, display stretch, and GPU/CPU fallback on Windows. |
| 3D - Sky masks | Complete | Verified automatic proposals, manual tag and mask edits after reopening, and sky-only solving and fitting. |
| 3E - Foreground and composition | Complete | Verified WCS-independent foreground alignment, separate layer exports, and saved placement, seam, and crop edits on Windows. |
| 3F - Windows acceptance | Local checks passed | Packaged workflows, recovery, cancellation cleanup, and CPU fallback passed on the development host. Clean-machine validation remains open. |
| 3.1A - Panel WCS and optical metadata | Complete | Per-panel WCS status, embedded and edited optical hints, scale derivation, and older project compatibility verified on Windows. |
| 3.1B - Local plate solve settings | Complete | Gaia DR3 and ASTAP paths and database choice restored across restarts. Source and packaged Windows checks verified actionable diagnostics. |
| 3.1C - Desktop plate solve job | Complete | Packaged Windows CPU and OpenGL checks verified eligible panels, Gaia and ASTAP fallback, WCS sidecars, cancellation and retry, and project reopen and export. |
| 3.5A - Phase 2 review | Complete | Phase 2 criteria mapped and rerun on Windows, with added cases, reproduction steps, and regression thresholds recorded. |
| 3.5B - Revision | Complete | Focused tests protect the frozen narrow-overlap, saturation, and masked WCS reuse cases on Windows. |
| 3.5C - Verification | Complete | Windows source, portable CLI, and desktop results cover the frozen criteria, M42 plate solves, and the M31 20% overlap merge. |
| 3.6A - Capabilities and contract freeze | Complete | Native D05 Auto/SIP/manual-fallback evidence, bounded ASTAP-only quality query, owner TIFF/EXIF checks, and frozen fixture/numerical/budget/schema contracts recorded. |
| 3.6B - ASTAP priority and catalogs | Complete | ASTAP priority, real single and mixed D-series sets, native Automatic and explicit resolution, manual pinning, missing/incomplete catalogs, Unicode paths and ASTAP-only qualification verified on Windows. |
| 3.6C - Total solve deadlines | Local checks passed | Shared deadline, late rejection, source prep exhaustion, native worker and ASTAP cancellation/cleanup, and preserved partial results checked. |
| 3.6D - Quality and scale recovery | Local checks passed | Match/RMS limits, Gaia confidence, false-match controls, ASTAP-only FOV recovery and Gaia recovery from wrong pointing and both scale factors. The narrow blind M42 and cross-catalog quality results are recorded. |
| 3.6E - SIP and full-field diagnostics | Local checks passed | Synthetic truth, TAN/SIP selection, map and support diagnostics, both real TIFFs and independent reopened export. |
| 3.6F - Integration and acceptance | Local checks passed | Qt-free portable CLI, desktop CPU/OpenGL, settings and v1/v2 migration, cancellation/retry, preview and independent exports. Full external acceptance remains open. |
| 4A - Headless project automation | Complete | Creation, sky preflight, saved-layer export, desktop parity and scripted FITS/TIFF batch, progress, failure and cancellation checks passed on Windows. |
| 4B - Large mosaics and improved blends | Complete | Full FITS, RGB TIFF and mixed Windows runs matched the reference after conservative candidate selection. Resource, halo, cancellation and output-limit checks passed. Optional multiband evaluation is deferred. |
| 4C - Desktop command panel | Complete | Standalone CLI parity, live progress, history, cancellation, and window-close cleanup verified on Windows. |
| 5A - XISF interchange | Complete | Bounded mono and RGB attachments, WCS, units, coverage and contribution masks verified through independent reopening and copied Windows workflows. |
| 5B - ZEA sky projection | Complete | Saved projection, longitude wrap, projection domain, preview and export agreement, and copied Windows workflows passed. |
| 5C - Per-band output | Complete | Saved membership, band-local units and channels, common geometry, independent exports, and Windows desktop, CLI and batch checks passed. |
| 6 - Real-observation reliability | Local 6A–6E checks passed | The real references, native lifecycle, and source and portable product comparison are recorded. Fresh Windows acceptance remains open for the named 6E build. |
| 7 - Terrain panorama registration | 7A–7E local checks passed | Add the 7F point review workflow. Verify real positive, mixed and negative cases, lifecycle and independent exports on native and fresh Windows. |

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
- **Published:** Pushed `main` and verified the remote initial commit `7faa650`.
- **Next:** Continue with the linear TIFF contract.

### 2026-11-15 - Licensing - Adopted GPL version 3

- **Changed:** Added the GPL v3 text and declared `GPL-3.0-only` in the README and Python package metadata.
- **Verified:** Compared the license text with the reference project and checked the lock and built wheel metadata.
- **Related:** [ADR-0009](docs/adr/0009-gpl-v3-application-license.md) records the decision. Q-005 remains open for third-party release notices and data terms.
- **Next:** Continue the TIFF contract and review bundled materials during release preparation.

### 2026-11-15 - Phase 2 - Started: astronomy acceptance cases

- **Changed:** Set the reference thresholds for held-out alignment, relative stellar gain, faint emission, supplied sky masks, and offline solver evidence.
- **Verified:** Reviewed the cases against the Phase 2 gate and the Phase 1 FITS input and memory contracts.
- **Related:** [Phase 2 fixture criteria](docs/phase-2.md#acceptance-fixtures), Q-003, Q-006, and Q-010.
- **Next:** Connect the solver adapters and build the deterministic masked FITS fixtures.

### 2026-11-15 - Phase 2 - Implemented: masked offline solving and relative refinement

- **Changed:** Added local Gaia and ASTAP stages, WCS sidecars, supplied sky FITS masks, and opt-in stellar and background refinement.
- **Verified:** Windows M13 solves passed in hinted and blind modes with both backends. The full local fallback order, native ASTAP cancellation, and masked staging passed. Synthetic and DSS refinement checks passed, including the stellar and faint-emission gates.
- **Related:** [ADR-0010](docs/adr/0010-seiza-gaia-backend.md), [Phase 2 evidence](docs/phase-2.md), Q-003, Q-006, and Q-010.
- **Next:** Verify the updated headless Windows bundle and finish the phase handoff.

### 2026-11-15 - Phase 2 - Completed: Windows astronomy gate

- **Changed:** Recorded the solver matrix, catalog installation and update policy, and relative refinement results. Built the local headless Windows CLI with the optional Gaia binding.
- **Verified:** 37 tests, Ruff, mypy, and lock validation passed. The bundle passed native Gaia and ASTAP solves, masked sidecar reimport, refinement, independent FITS reopening, and the spawned smoke case. Measured native Gaia index memory separately from render buffers.
- **Related:** Q-006 is resolved for the offline solver and catalog deployment. [Phase 2 evidence](docs/phase-2.md) records Q-003 and Q-010 checks, with later format and desktop work still tracked.
- **Next:** Validate linear mono/RGB TIFF input and output before Phase 3 desktop acceptance.

### 2026-11-15 - Repository update - Phase 2 snapshot

- **Changed:** Recorded the Phase 2 source, tests, lock, and documentation in the GitHub snapshot.
- **Verified:** All 37 tests, Ruff, mypy, and Poetry lock checks passed before publication.
- **Next:** Validate the linear TIFF workflow.

### 2026-11-15 - Dependencies - Completed: imagecodecs added for TIFF codecs

- **Changed:** Added `imagecodecs` to `pyproject.toml` and updated `poetry.lock` to provide fast C decoders (LZW, Deflate, ZSTD) for the linear TIFF workflow.
- **Verified:** Verified `imagecodecs` 2026.11.11 import and codec availability (LZW, ZSTD). All 37 existing tests, Ruff, mypy, and `poetry check --lock` passed cleanly.
- **Related:** [ADR-0006](docs/adr/0006-dual-fits-and-tiff-workflow.md), Q-009.
- **Next:** Define and verify the linear mono/RGB TIFF input/output contract.

### 2026-11-15 - Phase 3 - Planned A–F delivery stages

- **Changed:** Updated the architecture to revision 3.6 with separate acceptance gates for TIFF, projects and jobs, preview and export, masks, composition, and Windows acceptance.
- **Verified:** Reviewed the stages against the existing Phase 3 requirements and checked the documentation links.
- **Next:** Begin Phase 3A with the linear TIFF contract and fixtures.

### 2026-11-15 - Phase 3A - Implemented the headless TIFF path

- **Changed:** Defined the [linear TIFF contract](docs/phase-3a.md) and added bounded mono/RGB source windows, shared rendering, and single-file float32 TIFF export with embedded WCS and coverage.
- **Verified:** The existing 37-test FITS regression suite, mypy, and lock validation passed after integration. A TIFF writer probe reopened interleaved float32 science samples through libtiff and located the coverage SubIFD through tifffile.
- **Related:** [ADR-0011](docs/adr/0011-linear-tiff-interchange.md), Q-003, Q-004, and Q-009.
- **Next:** Run the mono and RGB acceptance fixtures on Windows, including output reopen, resource limits, and cancellation.

### 2026-11-15 - Phase 3A - Completed: linear TIFF Windows verification

- **Changed:** Added deterministic mono and RGB TIFF fixtures, including exact two-panel blends, crop and rotation, compressed and raw windows, mixed mono input formats, bounded failure, and cancellation cleanup.
- **Verified:** All 51 tests, lint, format, mypy, and lock validation passed. libtiff reopened both TIFF science layouts. The Windows M13 RGB TIFF matched the FITS Gaia solution. With a sky mask, Gaia exhausted its match search and hinted ASTAP produced the WCS used for a successful TIFF export.
- **Related:** [Windows evidence](docs/phase-3a.md#windows-evidence), [ADR-0011](docs/adr/0011-linear-tiff-interchange.md), Q-003 through Q-005, and Q-009.
- **Next:** Start Phase 3B. Verify packaged interoperability in Phase 3F and the representative TIFF resource workload in Phase 4.

### 2026-11-15 - Phase 3B - Implemented project persistence and desktop job controls

- **Changed:** Added versioned project manifests with file fingerprints, relative paths, mosaic settings, and atomic saves. Added the PySide6 project window and a cancellable render thread.
- **Verified:** The new window launched with the Windows PySide6 installation using the offscreen platform plugin. The empty project disables rendering and cancellation.
- **Next:** Exercise reopen, relinking, responsive progress, cancellation, retry, and cleanup with generated panels.

### 2026-11-15 - Phase 3B - Completed: project and render workflow

- **Changed:** Finished the desktop entry point, project and panel settings, file relinking, and a background worker with progress and cancellation. Closing during a job now defers window teardown until cleanup.
- **Verified:** All 58 tests passed on native Windows Qt. The desktop test saved and reopened a mixed-format project, relinked a moved panel, and rendered with its saved WCS and sky mask. A GUI timer fired during the live job. Cancellation and closing removed partial output, and the cancelled render could be retried successfully.
- **Related:** [Phase 3B evidence](docs/phase-3b.md), [ADR-0012](docs/adr/0012-project-manifest-and-render-worker.md), Q-004, and Q-009.
- **Next:** Add the interactive sky preview and compare its geometry with export in Phase 3C.

### 2026-11-15 - Repository update - Published the Phase 3A and 3B snapshot

- **Changed:** Committed the linear TIFF workflow, project manifests, desktop jobs, and their documentation as `1e3a05d`.
- **Verified:** All 58 tests, Ruff lint and format checks, mypy, and Poetry lock validation passed. `git ls-remote` confirmed that `origin/main` points to `1e3a05d`.
- **Next:** Implement the Phase 3C sky preview against the cropped export grid.

### 2026-11-16 - Phase 3C - Implemented the sky preview and export workflow

- **Changed:** Shared the cropped TAN sampling path between export and the preview worker. Added a progressive viewport with pan, cursor-centered zoom, and a display-only stretch on OpenGL and CPU.
- **Verified:** Reopened the cropped FITS and RGB TIFF outputs and compared their linear samples and coverage with the matching preview samples. Both display paths agreed within one 8-bit level on the native Windows framebuffer fixture. Using typed OpenGL uniform functions corrected a float uniform dispatch error exposed by that check.
- **Related:** Q-003, Q-004, and Q-009.
- **Next:** Run the full Windows regression suite and record the desktop memory and fallback checks.

### 2026-11-16 - Phase 3C - Completed: Windows sky preview and export gate

- **Changed:** Documented the viewport and shared export geometry. Set the preview's longest edge to 512 pixels, with a 160-pixel first pass for larger grids.
- **Verified:** All 62 tests passed on Windows 11 x64 with native OpenGL enabled. Focused checks passed at 2× device scale and on the offscreen CPU path. Ruff, mypy, Poetry lock validation, and local documentation links passed. Reviewed the native desktop capture and measured both display backends on the two-panel FITS workload.
- **Related:** [Phase 3C evidence](docs/phase-3c.md), [ADR-0013](docs/adr/0013-shared-preview-grid.md), Q-003, Q-004, and Q-009. Packaged acceptance remains in Phase 3F.
- **Next:** Start Phase 3D with foreground tags, source-coordinate masks, and tests for editing, reopening, and sky processing.

### 2026-11-16 - Repository update - Prepared the Phase 3C publication

- **Changed:** Prepared the shared sky preview and export snapshot for `main`.
- **Verified:** Re-ran all 62 tests on native Windows Qt with OpenGL required. Ruff lint and format checks, mypy, and Poetry lock validation passed.
- **Next:** Confirm the remote revision, then implement Phase 3D foreground tags and sky masks.

### 2026-11-16 - Repository update - Published Phase 3C

- **Changed:** Pushed the Phase 3C sky preview and export snapshot `e60d4a9` to `origin/main`.
- **Verified:** GitHub accepted the fast-forward from `1e3a05d`. The local `main` and remote-tracking `origin/main` both resolved to `e60d4a9` after the push.
- **Next:** Continue Phase 3D with foreground checks and mask editing.

### 2026-11-16 - Phase 3D - Implemented mask proposals and editing

- **Changed:** Added local thumbnail checks, a cancellable mask job, an overlay editor, and manifest persistence for foreground overrides and source-coordinate masks. Preview, export, refinement, and project-panel solving use the effective sky mask.
- **Verified:** The initial Phase 2 M13 trial recognized the synthetic foreground in the mixed copy and found no horizon in the original. The proposal on the mixed copy did not label any injected ground pixels as sky.
- **Related:** Q-010.
- **Next:** Exercise interactive edits, bounds, cancellation, and the full solver and refinement paths on Windows.

### 2026-11-16 - Phase 3D - Completed: saved sky mask workflow

- **Changed:** Rejected short horizon candidates caused by isolated stars and narrowed the unclassified band around strong edges. Saved the edited grid and foreground override in manifest version 2, with version 1 read support.
- **Verified:** All 68 native Windows tests passed. Focused 2× and CPU desktop checks, Ruff, mypy, Poetry lock validation, and local links passed. FITS and RGB TIFF fixtures verified the mask labels. ASTAP solved the mixed M13 project panel using the proposed mask. Hinted Gaia exhausted its match search on the same masked sample.
- **Related:** [Phase 3D evidence](docs/phase-3d.md), [ADR-0014](docs/adr/0014-source-coordinate-mask-grid.md), and Q-010.
- **Next:** Start Phase 3E with an independent foreground registration fixture and preserve the sky layer geometry for composition.

### 2026-11-16 - Repository update - Published Phase 3D

- **Changed:** Committed the foreground tags and editable sky masks as `1e682b1` and pushed the snapshot to `origin/main`.
- **Verified:** All 68 native Windows tests, Ruff, mypy, Poetry lock validation, and 97 local documentation links passed. `git ls-remote` confirmed the published commit.
- **Next:** Build and test image-space foreground alignment on panels without WCS.

### 2026-11-16 - Phase 3E - Implemented independent layers and composition

- **Changed:** Added masked foreground translation, a shared horizon placement proposal, and saved composition controls. Preview and export sample the original panels and record the actual layer contributions.
- **Verified:** FITS and RGB TIFF fixtures matched known terrestrial shifts. The larger case refined its result at source resolution. The native desktop workflow on the secondary monitor proposed placement, reopened the edited composition, showed common coverage, and exported a FITS composite.
- **Related:** [Phase 3E workflow](docs/phase-3e.md), [ADR-0015](docs/adr/0015-independent-layer-rendering.md), and Q-010.
- **Next:** Run the full native regression suite and focused CPU and high-DPI checks.

### 2026-11-16 - Phase 3E - Completed: Windows layer and composition gate

- **Changed:** Documented the common-raster translation model, contribution map formats, and composition workflow. The overlap display shows common coverage independently of the feathering band.
- **Verified:** All 74 native Windows tests passed with OpenGL enabled. The focused viewport and composition workflows passed at 2× device scale, and the offscreen CPU checks passed. Ruff, mypy, Poetry lock validation, and documentation links passed. Native test dialogs opened on the secondary monitor.
- **Related:** [Phase 3E evidence](docs/phase-3e.md), [ADR-0015](docs/adr/0015-independent-layer-rendering.md), Q-004, Q-009, and Q-010. Real terrestrial captures and the 12-panel workload remain follow-up checks.
- **Next:** Begin Phase 3F with a packaged Windows build and rerun the mixed-panel workflow, recovery, cancellation, and CPU fallback checks.

### 2026-11-16 - Repository update - Published Phase 3E and test guidance

- **Changed:** Added the secondary-monitor instruction for test windows and dialogs to `AGENTS.md`. Published it with the Phase 3E source and evidence.
- **Verified:** All 74 native Windows tests, Ruff, mypy, and Poetry lock validation passed. The test runner observed dialogs on the secondary monitor. The remote points to `f236a3a`.
- **Next:** Build and verify the Windows desktop and CLI packages for Phase 3F.

### 2026-11-16 - Phase 3F - Built the Windows packages

- **Changed:** Added a repeatable PyInstaller build for the desktop and Qt-free CLI with the required TIFF codecs. Added a launcher option for visible tests on the secondary monitor.
- **Verified:** The regular desktop launcher opened a native file chooser, relinked a moved TIFF, and drew the foreground in OpenGL on the second monitor. The frozen CLI passed spawned-worker, FITS, compressed TIFF, and local solver checks.
- **Next:** Verify the remaining desktop acceptance paths in the background.

### 2026-11-16 - Phase 3F - Passed local background acceptance

- **Changed:** Added a separate frozen desktop checker that runs with the portable bundle's native libraries and supplies paths to the normal project and export entry points.
- **Verified:** Offscreen CPU and hidden OpenGL passed the mixed-layer preview and export checks, relinking, simulated save failure recovery, running-job cancellation, and retry. The offscreen source suite passed 73 tests and skipped one native viewport test. Ruff, mypy, Poetry lock validation, and documentation links passed.
- **Related:** [Phase 3F evidence](docs/phase-3f.md), Q-001, Q-004, Q-005, Q-009, and Q-010.
- **Next:** Repeat the portable check on a clean Windows 11 x64 installation. The host provided no enabled Windows Sandbox or Hyper-V instance.

### 2026-11-16 - Phase 4 planning - Added local automation and desktop terminal stages

- **Changed:** Updated the plan to revision 3.7. Scheduled the scriptable project CLI in 4A, large-mosaic checks in 4B, and the desktop terminal panel in 4C.
- **Verified:** Reviewed the plan against the current CLI, headless project loader and layer renderer, and Windows package evidence. Checked local documentation links, stage and revision references, topic IDs, and patch whitespace. This was a documentation update.
- **Related:** [Phase 4 stages](astro_mosaic_python_first_architecture_en.md#102-phase-4-delivery-stages), [ADR-0016](docs/adr/0016-local-automation.md), and Q-012.
- **Next:** Define the 4A project validation and export commands and their JSON results. Repeat the portable bundle check when a clean Windows 11 x64 installation is available.

### 2026-11-16 - Phase 3.1 planning - Scheduled astronomy engine revalidation

- **Changed:** Updated the plan to revision 3.8. Added 3.1A review, 3.1B revision, and 3.1C verification of the Phase 2 engine before Phase 4A.
- **Verified:** Reviewed the sequence and exit criteria against the original Phase 2 fixtures, solver evidence, and current Windows workflows. Checked stage and revision references, local links, and patch whitespace.
- **Related:** [Phase 3.1 gates](astro_mosaic_python_first_architecture_en.md#phase-31-astronomy-engine-revalidation), [Phase 2 baseline](docs/phase-2.md#acceptance-fixtures), and Q-003.
- **Next:** Start 3.1A with the Phase 2 criteria-to-evidence review and baseline rerun.

### 2026-11-16 - Phase 3.1 planning - Scheduled desktop plate solving

- **Changed:** Updated the plan to revision 3.9. Added per-panel WCS and optical metadata, local solver settings, and the desktop solve job in 3.1A–3.1C. Renumbered the Phase 2 revalidation to 3.5A–3.5C and kept its verification as the entry condition for 4A.
- **Verified:** Reviewed the plan against the FITS and TIFF metadata readers, current Gaia and ASTAP adapters, and project job and WCS sidecar contracts. Checked the phase order, cross-references, local links, and patch whitespace.
- **Related:** [Desktop plate solving](astro_mosaic_python_first_architecture_en.md#phase-31-desktop-plate-solving), [Phase 3.5 revalidation](astro_mosaic_python_first_architecture_en.md#phase-35-astronomy-engine-revalidation), Q-003, and Q-013.
- **Next:** Start 3.1A by choosing representative metadata fixtures and mapping the effective WCS states.

### 2026-11-16 - Repository update - Published Windows bundles and planning snapshot

- **Changed:** Published the Phase 3F package scripts and local acceptance evidence with architecture revision 3.9 as `6685e0f`.
- **Verified:** The staged patch passed the whitespace check, and the remote main ref resolved to `6685e0f` after the push.
- **Next:** Implement Phase 3.1A with the existing Qt-free solver and project WCS contract.

### 2026-11-16 - Phase 3.1A - Completed panel WCS and optical hints

- **Changed:** Added background WCS inspection, embedded FITS and TIFF optical hints, editable overrides in manifest version 4, and shared scale derivation for the Qt-free solver. Existing project versions reopen directly.
- **Verified:** All 79 native Windows tests passed on the secondary monitor. Rebuilt desktop packages passed CPU and OpenGL checks, including WCS refresh after relinking. The CLI passed worker and export checks. Source and packaged CLIs solved the M13 reference copy using optical hints with both Gaia and ASTAP. Ruff, mypy, lock validation, and local documentation links passed.
- **Related:** [Panel workflow and Windows evidence](docs/phase-3b.md#panel-wcs-and-plate-solve-hints) and Q-013.
- **Next:** Implement Phase 3.1B local solver settings. The pending Phase 3F clean-machine check remains tracked separately.

### 2026-11-17 - Repository update - Published Phase 3.1A

- **Changed:** Published the completed Phase 3.1A code, Windows evidence, and project records as `2534333`.
- **Verified:** The staged patch passed the whitespace check. The remote main ref resolved to `2534333` after the push.
- **Next:** Implement and verify Phase 3.1B local solver settings.

### 2026-11-17 - Phase 3.1B - Completed local solver settings

- **Changed:** Added Tools → Plate Solve Settings, per-user path storage, and a cancellable background check for Gaia DR3 and ASTAP. The dialog reports the backend prerequisites and keeps path choices available when data moves.
- **Verified:** All 84 native Windows tests passed on the session's sole active display. Separate processes checked and restored real Gaia DR3 and ASTAP D05 settings. Rebuilt CPU and OpenGL desktop checks verified diagnostics and saving. The rebuilt CLI passed worker and export checks and solved M13 with both backends. Ruff, mypy, lock validation, and local links passed.
- **Related:** [Settings workflow and evidence](docs/phase-3b.md#local-plate-solve-settings) and Q-006.
- **Next:** Implement the 3.1C background desktop solve job with per-panel progress and sidecar attachment.

### 2026-11-17 - Development guidance - Added phase drafting rule

- **Changed:** Updated [AGENTS.md](AGENTS.md#1-language-and-plan) to cover phase scope, project impact, and potential improvements during drafting.
- **Verified:** Reviewed the wording against the owner’s instruction and checked the local link and patch whitespace.
- **Next:** Apply the rule when drafting or revising phase content.

### 2026-11-17 - Repository update - Published Phase 3.1B

- **Changed:** Published the local solver settings and phase drafting guidance as `31839b2`.
- **Verified:** The staged patch passed the whitespace check and the remote main ref resolved to `31839b2`.
- **Next:** Implement Phase 3.1C on the published settings and WCS contracts.

### 2026-11-17 - Phase 3.1C - Completed desktop plate solving

- **Changed:** Added the background Plate Solve job, per-panel reports, and atomic sidecar publication. Completed solutions are attached after cancellation or failure of another panel.
- **Verified:** All 85 native Windows tests passed. The session exposed one active display. Both desktop bundles passed the real Gaia DR3 and ASTAP D05 cases, including fallback, ASTAP process and staging cleanup, retry, project reopen and export, and unchanged source hashes. The packaged CLI, Ruff, mypy, lock validation, and local links passed.
- **Related:** [Desktop workflow and evidence](docs/phase-3b.md#desktop-plate-solving) and Q-006.
- **Next:** Start Phase 3.5A with the Phase 2 evidence map and baseline rerun.

### 2026-11-17 - Repository update - Published Phase 3.1C

- **Changed:** Published the desktop plate solve job, project handoff, and packaged Windows checks as `5c4bb68`.
- **Verified:** The staged patch passed the whitespace check and the remote main ref resolved to `5c4bb68`.
- **Next:** Review and rerun the Phase 2 baseline in Phase 3.5A.

### 2026-11-17 - Phase 3.5A - Completed Phase 2 baseline review

- **Changed:** Mapped every Phase 2 criterion to the current implementation and results. Recorded fixture recipes and thresholds for narrow sky support, saturation, masked WCS reuse, and real M13 crops.
- **Verified:** The 85 Windows tests, the offline solver matrix, and both packaged desktop modes passed. The held-out synthetic P95 was 0.000558 px. CFITSIO verified masked export coverage and geometry. The exploratory embedded-to-sidecar comparison found a maximum one-ULP brightness difference within the fixture tolerance. Ruff, mypy, and lock validation passed.
- **Related:** [Phase 3.5A evidence](docs/phase-35.md), Q-003, Q-006, and Q-014.
- **Next:** Add the focused regression tests in 3.5B and use the exact M13 crop recipe during 3.5C.

### 2026-11-17 - Phase 3.5B - Completed focused regression coverage

- **Changed:** Added deterministic tests for background plane rejection in narrow overlaps, saturated-star handling, and masked WCS reuse through the CLI.
- **Verified:** All 88 native Windows tests passed. Each new test detected a deliberately bypassed check in memory. The masked FITS retained its expected science samples, coverage, WCS, and sidecar provenance. Ruff, mypy, and lock validation passed.
- **Related:** [Phase 3.5B regression results](docs/phase-35.md#phase-35b-regression-results), Q-003, and Q-014.
- **Next:** Run 3.5C with the frozen synthetic and real fixtures through the source and portable Windows CLI.

### 2026-11-17 - Phase 3.5C - Completed Windows astronomy engine verification

- **Changed:** Recorded the frozen regression rerun, new M42 offline astrometry and Documents catalog format checks, and the saved M31 project and FITS mosaic with 20% panel overlap.
- **Verified:** All 88 tests and the packaged CLI and OpenGL checks passed. CFITSIO confirmed the masked reference and exact M31 reconstruction. M42 solved with hints on the 40′ field and blind on the 55′ field. A regional conversion of the Documents XPSD catalog yielded a separate validated M42 FITS with 115 Gaia matches. The narrower blind failure is recorded in Q-015. Ruff, mypy, and lock validation passed.
- **Related:** [Phase 3.5C evidence](docs/phase-35.md#phase-35c-windows-verification), Q-003, Q-006, Q-014, and Q-015.
- **Next:** Start Phase 4A. Repeat the separate 3F clean-machine check when a clean Windows host is available.

### 2026-11-17 - Local setup - Saved Gaia paths and verified portable ASTAP

- **Changed:** Saved the verified Seiza deep Gaia DR3 catalog and matching blind index in the current Windows user's Plate Solve settings.
- **Verified:** A fresh settings dialog loaded both paths and Seiza opened both files. Five settings tests passed. The portable ASTAP CLI 2026.11.01 and D05 catalog solved the M13 reference through the packaged CLI.
- **Related:** Q-006. The ASTAP check used explicit CLI paths. The desktop ASTAP fields are currently empty.
- **Next:** Start Phase 4A from the verified 3.5C baseline.

### 2026-11-17 - Local setup - Saved ASTAP paths

- **Changed:** Saved the verified portable ASTAP executable, local catalog folder, and D05 database in the current Windows user's Plate Solve settings.
- **Verified:** A separate process opened a fresh settings dialog with both the ASTAP and Gaia paths. Both backend path checks passed.
- **Related:** Q-006.
- **Next:** Start Phase 4A from the verified 3.5C baseline.

### 2026-11-17 - Research - Compared Mosaic Master and AstroMosaic plate solving

- **Changed:** Added a [source-based comparison](docs/plate-solve-comparison.md) separating Mosaic Master's Gaia/web panel route, SetiSuite's general four-pass solver, finished-canvas Gaia solving, and AstroMosaic's offline chain. Preserved existing working-tree changes and application code.
- **Verified:** Eleven existing AstroMosaic solver/setup/desktop tests passed. Isolated actual SetiSuite methods confirmed fallback routing, approximate quad-seed acceptance, fixed-parity TAN reconstruction, and the existing stale-SIP writer regression. A mocked Seiza probe confirmed confidence rejection and retained blind scale bounds; installed 0.48.2 signatures confirmed default SIP order zero. Full SetiSuite integration and comparative real-image timing were not run.
- **Related:** Q-016 records wrong-scale recovery and distortion validation; Q-015 retains the existing M42 coverage issue. ADR-0005 and ADR-0010 remain unchanged.
- **Next:** Use the report to scope a controlled solver benchmark; Phase 4A remains the active development next step.

### 2026-11-17 - Phase 3.6 - Planned ASTAP priority and reliable solving

- **Changed:** Revised the active architecture to 3.10 and added the [detailed 3.6A–3.6F plan](docs/phase-36.md) before Phase 4A. Defined ASTAP-first solving, Automatic/manual local catalogs, 15-match evidence, proposed RMS and total-budget values, bad-scale recovery, supported SIP/edge gates, migration and downstream impacts. ADR-0017 records the priority change; application code and earlier evidence remain unchanged.
- **Verified:** Reviewed the current adapters/settings/CLI, Phase 3.5 evidence and official ASTAP sources. A hidden help-only call confirmed installed CLI-2026.11.01 options; native auto selection, match/RMS extraction and SIP solving remain 3.6A checks. Content review, all 330 local file/directory links and anchors across 34 repository Markdown files, new-file whitespace/fences, unique topic IDs and `git diff --check` passed. No application tests were needed for this planning-only change.
- **Related:** Updated Q-003/Q-004/Q-015/Q-016 and added Q-017 for ASTAP automation/quality evidence and Q-018 for deadlines/migration. Existing user working-tree changes were preserved.
- **Next:** Start 3.6A capability probes and fixture/threshold freeze; do not claim implementation or 3.6 acceptance from the plan.

### 2026-11-17 - Phase 3.6 - Clarified full-field skew and distortion diagnostics

- **Changed:** Expanded 3.6E to quantify center/interior/edge geometry with a bounded model grid and regional measured-error/support views. Separated global linear skew, nonlinear WCS displacement, local scale/shear and actual star residuals. Unsupported/model-only regions cannot be presented as measured zero distortion.
- **Verified:** Reviewed the requirement against the existing SIP, source/mask identity, shared geometry and total-budget contracts. All 330 local links/anchors across 34 Markdown files, affected code fences and `git diff --check` passed; application code and tests are unchanged.
- **Related:** Q-016 now includes the full-field diagnostic and support requirement. The current phase remains planned, with implementation starting at 3.6A.
- **Next:** Freeze grid/reference definitions, regional sample support and synthetic skew/distortion truth cases in 3.6A.

### 2026-11-17 - Phase 3.6A - Started capability probes and owner TIFF validation

- **Changed:** Added reproducible local native probes and an original bounded ASTAP D-series cone decoder. Added TIFF EXIF/XMP optical hints to panel inspection, with camera display, unit/precedence checks and preserved manual overrides. Included the owner's ignored `20.TIF`/`21.TIF` as optional local regression inputs.
- **Verified:** Baseline tests passed 87 cases with the native OpenGL case skipped. Twenty-seven focused catalog/metadata/owner/inspection tests passed, and Ruff/mypy passed before subsequent probe refinements. ASTAP CLI-2026.11.01 solved M13 with omitted/explicit Auto and produced SIP-3 with `-sip`. Independent D05 checking found 168 TAN matches at 0.629 arcsec RMS; native SIP was slightly worse at 0.683 arcsec. After EXIF scale extraction, local Gaia solved both owner TIFFs with 890/894 matches in about 5–6 seconds. Original image hashes were unchanged.
- **Related:** Q-016/Q-017/Q-018 remain active. The owner TIFFs expose wide-field support and regional validation costs, tracked under Q-019. No new backend order or complete Phase 3.6 quality policy is claimed yet.
- **Next:** Finish capability evidence, spatial validation and frozen reference thresholds, then proceed to 3.6B. Keep expensive wide-field validation inside the eventual total deadline.

### 2026-11-18 - Phase 3.6A - Completed capability/reference freeze and TIFF metadata import

- **Changed:** Recorded [3.6A evidence](docs/phase-36a.md) and the [frozen manifest](tests/fixtures/plate_solve_v36.json). Added original bounded local catalog querying, native/reproducible probes and TIFF EXIF/XMP optics/camera loading with preserved overrides. Frozen broad Gaia recovery is now 0.1–120 arcsec/pixel to include the owner wide-field images; production dispatch/quality/SIP/deadline integration is still pending.
- **Verified:** All 117 source tests passed on native Windows, including OpenGL; dialogs/windows used the second monitor. Ruff, format, mypy and lock checks passed. Actual ASTAP Auto/SIP, missing manual-catalog fallback, independent M13 associations, owner TIFF staging/metadata and broad native Gaia/SIP experiments were recorded. All original image hashes were unchanged; all three Seiza files matched bundle SHA-256/size. Final documentation checks are recorded after the handoff review.
- **Related:** Q-016–Q-019 remain implementation/acceptance topics. Independent owner SIP checking improved RMS from about 50 to 13 arcsec, but fine-grid cells without enough stars remain unvalidated. W08 is absent; no catalog was installed implicitly. Earlier user changes and evidence were preserved.
- **Next:** Start 3.6B. Keep the experimental native fits distinct from final model acceptance, and retain the full Phase 3.6F portable/desktop gates.

### 2026-11-18 - Phase 3.6B - ASTAP first and catalog selection in source

- **Changed:** Existing WCS still wins. New candidates try the configured ASTAP CLI before Gaia. Fresh settings use Automatic and explicit D-series choices remain pinned. The adapter inventories complete tile sets and records actual native database identity.
- **Verified:** Twelve focused tests passed. The pinned CLI solved M13 with native Auto/D05. A real catalog path with spaces and a character outside the Windows code page required an ASCII scratch alias, then solved with the same CLI and data. Catalog files were read through links.
- **Next:** Apply one deadline around preparation, the native backends and publication. The 15-match gate and the supported SIP decision follow in 3.6D/E.

### 2026-11-18 - Phases 3.6C–3.6E - Integrated deadline, quality gate and spatial validation

- **Changed:** Source and desktop entry points share one deadline per panel. Gaia native search and validation run in bounded Windows spawn workers. Published sidecars use the version 2 quality report and retain version 1 reading.
- **Changed:** Production acceptance checks unique local catalog associations and comparable RMS, removes rejected position/scale hints during recovery, and compares TAN and SIP with a shared spatial holdout. The new panel details view separates model displacement from measured errors.
- **Verified:** Twenty-six focused numerical, workflow and deadline tests passed. Real M13 ASTAP-only and Gaia-only runs accepted TAN. Both owner TIFFs recovered SIP-3 from incorrect 0.5× scale and pointing in the initial source run, with held-out edge P95 below 0.9 px.
- **Next:** Complete native desktop and portable checks, repeat the frozen archive comparisons, and record unsupported catalogs and any remaining numerical or deployment gates.

### 2026-11-18 - Phase 3.6F - Portable Windows and owner-image checks passed

- **Changed:** Built the updated local portable package from the locked Windows environment. Added a TIFF codec prerequisite check after the first build failed LZW verification.
- **Verified:** All 138 source tests passed. The portable CLI passed independent FITS and compressed TIFF checks. Desktop CPU and OpenGL passed the plate-solve, cancellation/retry, save/reopen and export checks. A measured live ASTAP cancellation reaped its process and cleared scratch in about 0.025 seconds.
- **Verified:** Both owner files recovered SIP-3 in the portable CLI under 45 seconds. Held-out outer P95 was 0.837 and 0.874 px. Independent D05 outer P95 was 0.895 and 0.985 px. Original hashes were unchanged and both RGB exports reopened.
- **Next:** Keep [the Windows evidence](docs/phase-36-results.md) with the package. Real dense ASTAP combinations, the narrow M42 blind limit and the separate clean-machine run remain visible.

### 2026-11-18 - Phase 3.6F - Clean native timeout reporting

- **Changed:** A supplemental blind M42 deadline test found a child result colliding with the closed parent pipe. The worker now treats that closure as expected during timeout or cancellation.
- **Verified:** Added a targeted regression. The native suite passed all 139 tests. The rebuilt CLI reported timeouts with empty stderr and withheld sidecars at both 2.5- and 6-second attempt limits. The independent compressed TIFF and FITS checks and rebuilt desktop CPU/OpenGL runs passed again.
- **Verified:** Documentation review covered 36 Markdown files, 380 local links and anchors, 19 unique topic IDs and the frozen fixture manifest.
- **Next:** Retain the verified local package and the open real-catalog/clean-machine gates.

### 2026-11-18 - Phases 3.5–3.6 - Published the local Windows baseline

- **Changed:** Pushed the existing Phase 3.5 verification, solver comparison and Phase 3.6 implementation to `origin/main` as `ebb0095`.
- **Verified:** Reran all 139 native Windows source tests with OpenGL. Ruff, format, mypy, lock and staged patch checks passed. The remote branch advertises the published commit.
- **Related:** Q-015 through Q-017 and the separate clean-machine check still track the outstanding acceptance work.
- **Next:** Started Phase 4A from the verified local baseline at the owner's direction.

### 2026-11-18 - Phase 4A - Added sky project creation and preflight

- **Changed:** Added `project create` and `project validate` with version 1 JSON results and diagnostics. Creation uses the shared project writer. Validation uses the existing sky render preparation with metadata checks and an optional output path.
- **Verified:** All 143 native Windows source tests passed, including OpenGL on the second monitor. Installed and copied Qt-free CLI checks passed. The portable checker also reopened independent FITS and compressed TIFF exports. Ruff, format, mypy and lock checks passed.
- **Related:** [Phase 4A workflow and acceptance](docs/phase-4a.md) and [ADR-0016](docs/adr/0016-local-automation.md) record the CLI contract and its use in the later automation stages.
- **Next:** Add saved-layer export with progress and cancellation, then verify mixed-project parity and scripted batches.

### 2026-11-18 - Phase 4A - Verified saved-layer CLI export

- **Changed:** Added `project export` for the saved sky, foreground and composition layers through the shared project renderer. The CLI reports bounded tile progress and handles console interrupts through the job context. FITS and TIFF check cancellation at atomic publication.
- **Verified:** All 147 native Windows source tests passed, including OpenGL on the second monitor. Installed and copied portable CLI checks passed. An active Windows console break returned exit code 130 and removed scratch files in the Python module and portable launcher. Both retried at the same destination.
- **Verified:** The portable CLI and desktop produced identical pixels, coverage and contribution masks from the saved mixed FITS/TIFF project, with matching sky WCS. The copied bundle also passed independent FITS and RGB TIFF project exports.
- **Next:** Add PowerShell and Python batch examples and run the scripted success, failure and cancellation checks for Phase 4A acceptance.

### 2026-11-18 - Phase 4A - Completed Windows batch acceptance

- **Changed:** Added Python and PowerShell 7 examples using the same JSON job list and CLI output contract. The PowerShell example handles Windows console breaks while the active CLI completes its cancellation cleanup.
- **Verified:** Both examples passed against the installed CLI and a copied Qt-free portable CLI. All four cases reproduced independent FITS and TIFF results, continued past missing inputs and occupied targets, preserved completed exports during interruption, and retried at the same destination.
- **Verified:** All 147 native Windows source tests passed, including OpenGL on the second monitor. Ruff, format, mypy, PowerShell syntax and lock checks passed.
- **Next:** Start Phase 4B resource and large-mosaic checks through the verified CLI. The separate Phase 3.6 and clean-machine checks remain open.

### 2026-11-18 - Phase 4B - Verified the full-size Windows render baseline

- **Changed:** Added the [full-size generator, runner and verifier](tools/phase4b_benchmark.py) for twelve 6000 × 4000 mono FITS, RGB TIFF and mixed sources per case. Recorded the layout, limits and acceptance checks in [Phase 4B](docs/phase-4b.md).
- **Verified:** All three full outputs passed independent sample, coverage and applicable WCS checks. Peak reservations stayed from 17.125 to 20.211 MiB. The 6 MiB halo crop matched the full RGB result, the 2 GiB output cap rejected the oversized RGB job, and console cancellation cleaned up before a full FITS retry. All 147 native Windows tests and static checks passed.
- **Verified:** The FITS crop profile recorded twelve coordinate mappings and four source reads per tile. Mapping consumed 6.888 of 10.137 seconds of the profiled render.
- **Next:** Use conservative tile candidate bounds and compare the results and timings against these fixtures before changing the blending path.

### 2026-11-18 - Phase 4B - Completed conservative tile candidate selection

- **Changed:** Added output-plane footprints for ordinary TAN and placed foreground panels, with the full path for uncertain projections. The WCS check examines serialized projection cards to catch TPV normalization. The working reservation includes the cached bounds. [ADR-0018](docs/adr/0018-conservative-panel-footprints.md)
- **Verified:** The final portable CLI produced byte-identical FITS, RGB TIFF and mixed exports with 68.0–74.0% shorter elapsed times. The matching crop used 448 mappings instead of 1,344. Tight halo, output-limit rejection, cancellation and retry passed.
- **Verified:** All 154 native Windows tests, copied CLI checks and the four installed/portable batch runs passed. Q-004 records the verified resource contract.
- **Next:** Start the Phase 4C desktop command panel with the shared CLI report and cancellation contracts.

### 2026-11-18 - Phase 4C - Connected the desktop panel to the shared CLI

- **Changed:** Added the command panel and a spawned worker using the existing CLI parser, result formats, render callbacks, and cancellation context. Recorded the working-folder and session-history behavior. [Phase 4C](docs/phase-4c.md) · [ADR-0019](docs/adr/0019-desktop-command-worker.md)
- **Verified:** All seven focused desktop and project CLI tests passed. The panel's validation and exported FITS matched standalone CLI results. A cancelled export and an export interrupted by window close removed their temporary files. The test also covered Windows pipe closure after command exit.
- **Next:** Run the full native suite and the copied Windows desktop and CLI checks.

### 2026-11-18 - Phase 4C - Completed Windows command panel acceptance

- **Changed:** Extended the copied Windows desktop checker with validation, nested worker spawning, live cancellation, and sky and composition export comparisons.
- **Verified:** All 155 native Windows tests passed with OpenGL on the second display. The windowed application and portable console produced identical validation JSON and FITS bytes. The copied desktop CPU/OpenGL checks and Qt-free portable console check passed, along with Ruff, format, mypy, and the lock check. [Windows results](docs/phase-4c.md#local-windows-results)
- **Related:** Closed Q-012. The clean-machine distribution check remains open.
- **Next:** Define the first Phase 5 extended workflow and freeze its acceptance fixture.

### 2026-11-18 - Phase 4 - Verified the publication baseline

- **Changed:** Collected the Phase 4A–4C implementation, packaging checks, examples, and evidence in one baseline commit.
- **Verified:** Reran all 155 Windows tests with native OpenGL on the second display. Ruff lint and format, mypy, and the Poetry lock check passed. Reviewed the changed paths for repository scope.
- **Next:** Publish the baseline on `main`, then define the first extended format workflow for Phase 5.

### 2026-11-18 - Phase 5A - Published Phase 4 and selected XISF

- **Changed:** Pushed Phase 4A–4C as `e0a3a39` and defined the first Phase 5 workflow and fixture criteria.
- **Verified:** Queried the remote `main` reference and confirmed that it points to the published commit. Reviewed the format contract and the shared panel and export paths.
- **Related:** [Phase 5A](docs/phase-5a.md) and [ADR-0020](docs/adr/0020-bounded-xisf-interchange.md).
- **Next:** Implement the bounded reader and atomic export and run the acceptance checks.

### 2026-11-18 - Phase 5A - Implemented bounded XISF interchange

- **Changed:** Added tiled mono and RGB XISF imports, FITS-compatible WCS and calibration metadata, and atomic sky, foreground and composition exports through the CLI and desktop.
- **Verified:** The 24 focused source tests passed, including rotated RGB comparison, both byte orders, composition contribution codes, cancellation, and exact output-byte refusal. An independent `xisf` 1.0.1 RGB fixture round trip preserved 71 covered positions, sample values, and metadata.
- **Related:** Q-020 tracks broader XISF variants.
- **Next:** Finish the native Windows suite and copied-bundle checks.

### 2026-11-18 - Phase 5A - Completed local Windows acceptance

- **Changed:** Extended the copied Windows CLI and desktop checkers with XISF project, export and preview workflows. Updated the format and workflow documentation.
- **Verified:** All 165 native Windows tests passed with OpenGL on the second display. The copied Qt-free CLI and desktop CPU/OpenGL checks passed. Independent decoding matched the RGB sky export and both composition references, including coverage and contribution codes.
- **Verified:** Ruff lint and format, mypy, the Poetry lock check, and the added documentation links passed. The clean-machine distribution check remains open.
- **Next:** Define and verify the first additional sky projection.

### 2026-11-18 - Phase 5B - Selected ZEA and froze the geometry cases

- **Changed:** Defined the first additional sky grid, its manifest compatibility, and the acceptance fixtures for wide fields, the antipode, and cropped exports.
- **Verified:** The installed WCSLIB handled oblique and polar ZEA. A nominal antipodal coordinate serialized through FITS could round-trip at the rim because of floating-point rounding, so the projection needs an explicit validity guard.
- **Related:** [Phase 5B](docs/phase-5b.md) and [ADR-0021](docs/adr/0021-zea-sky-grid.md). Q-021 tracks the limiter check.
- **Next:** Wire the projection through saved settings, the tile mapper, and both entry points.

### 2026-11-18 - Phase 5B - Implemented the shared ZEA grid

- **Changed:** Added a projection setting to the CLI and desktop and persisted ZEA in manifest version 5. Preview and export share the selected geometry. Projection changes clear the desktop composition placement.
- **Verified:** The initial geometry tests passed for the oblique grid across RA zero, equivalent FITS, TIFF and XISF exports, and coverage and reimport at the polar rim. Legacy project and TAN preview tests passed.
- **Related:** Q-021 and ADR-0021.
- **Next:** Finish the native Windows suite and copied-bundle checks.

### 2026-11-18 - Phase 5B - Completed local Windows acceptance

- **Changed:** Added copied-package checks for saved ZEA projects and desktop projection selection, preview and export. Updated the workflow documentation.
- **Verified:** All 169 native Windows tests passed on the second display. The Qt-free console and CPU and OpenGL desktop package checks passed. The independently reopened wide-field exports matched preview pixels and coverage, and the tight-budget run matched the reference.
- **Related:** Closed Q-021. The clean-machine distribution check remains open.
- **Next:** Define per-band output with an explicit filter and unit contract on the saved sky grid.

### 2026-11-18 - Phase 5C - Defined saved band selection

- **Changed:** Defined band discovery, saved panel assignments, a single-band render, and the batch job selector on the existing sky grid.
- **Verified:** Reviewed the common-filter and brightness-scale checks, mask and sidecar handling, and the shared preview and export jobs.
- **Related:** [Phase 5C](docs/phase-5c.md) and [ADR-0022](docs/adr/0022-per-band-sky-products.md).
- **Next:** Add the selection through the project reader, renderer and both entry points.

### 2026-11-18 - Phase 5C - Implemented selected-band rendering

- **Changed:** Added saved panel band assignments, discovery, band-local validation, and selection in preview, export, and both batch runners.
- **Verified:** Focused source tests exercised independent mono and RGB products on the same ZEA grid, remapped masks, rejected incompatible units and layouts, and verified cancellation, retry, and CLI reports.
- **Next:** Run the full native test suite and the copied Windows and batch acceptance cases.

### 2026-11-18 - Phase 5C - Completed local Windows acceptance

- **Changed:** Added copied-package band selection checks and verified batch jobs that export multiple bands from one saved project.
- **Verified:** All 173 native Windows tests passed on the second display. Independent FITS, TIFF and XISF comparisons matched the per-band samples, coverage, units and ZEA grid. Copied CLI and desktop CPU/OpenGL checks passed. Both batch runners passed on both launchers, including cancellation and retry.
- **Related:** [Phase 5C results](docs/phase-5c.md#local-windows-results) and ADR-0022. The clean-machine distribution check remains open.
- **Next:** Complete the outstanding distribution and real catalog acceptance checks as the required test environments become available.

### 2026-11-18 - Panel import - Filled optical metadata across all supported formats

- **Changed:** Panel settings now fills available focal length and pixel size fields during background inspection. Added native XISF instrument properties, primary-directory TIFF optics, and producer-aware FITS pitch. The CLI `inspect` command now reports optical metadata and scales. Saved panel edits override the corresponding embedded values.
- **Verified:** All 33 focused tests passed for TIFF, FITS, and XISF inspection, solver hints, numeric units, missing metadata, and panel edits. Ruff, format, mypy, and Poetry lock checks passed.
- **Related:** Q-013 and [Panel WCS and plate solve hints](docs/phase-3b.md#panel-wcs-and-plate-solve-hints).
- **Next:** Run the full native Windows suite and verify the rebuilt Windows bundles.

### 2026-11-18 - Panel import - Verified Windows optical metadata workflows

- **Changed:** Rebuilt the desktop and console launchers in `.tooling/metadata-windows/dist/windows/`.
- **Verified:** All 178 source tests passed on Windows 11 x64. The native desktop import and panel settings check filled the synthetic FITS, TIFF, and XISF fields and the fields for both owner TIFFs. Both owner files returned 24 mm and about 3.9083 µm per axis. The packaged `inspect` command agreed across the formats. The copied console and desktop CPU/OpenGL acceptance checks passed.
- **Related:** Q-013, Q-019, and [Panel WCS and plate solve hints](docs/phase-3b.md#panel-wcs-and-plate-solve-hints).
- **Next:** Run the separate clean-machine Windows check and remaining catalog acceptance cases when their test environments are available.

### 2026-11-18 - Desktop - Introduced the panel control table and application themes

- **Changed:** Added a Qt table model with four property views, editable sky inclusion, weight, band and optics, and the existing panel actions. Placed the preview below the table. Added per-user dark and light themes with dark as the default.
- **Verified:** Native Windows tests covered editing, clearing overrides, saving, relinking, solving, and theme persistence. Inspected both themes in an M13 example. Fixed stale widget colors when switching to light. Ruff, format and mypy passed.
- **Related:** [Panel control table](docs/phase-3b.md#panel-control-table) and [desktop regression](tests/integration/test_panel_table.py).
- **Next:** Verify the full Windows test suite and copied desktop workflows.

### 2026-11-18 - Desktop - Verified the panel table and theme packages

- **Changed:** Built the updated Windows launchers in `.tooling/panel-table-windows/dist/windows/`.
- **Verified:** All 179 native Windows tests passed. A second desktop process loaded the saved light theme. Copied desktop bundles passed the table, theme, preview, and export workflows with CPU and OpenGL. The copied console passed its regression suite.
- **Related:** [Panel control table](docs/phase-3b.md#panel-control-table) and [packaged desktop checks](packaging/check-windows-desktop.py).
- **Next:** Run the separate clean-machine distribution check when a fresh Windows environment is available.

### 2026-11-18 - Version control - Consolidated the verified Phase 5 and desktop changes

- **Changed:** Consolidated XISF, ZEA, per-band exports, optical metadata import, the panel control table, and desktop themes into the next commit on `main`.
- **Verified:** The remote contained one branch at the Phase 4 baseline. Ruff, mypy, and whitespace checks passed before publication. The preceding desktop verification recorded 179 passing native Windows tests.
- **Next:** Run the outstanding clean-machine and catalog checks when their environments are available.

### 2026-11-18 - Phase 3.6 - Verified real dense ASTAP catalogs on Windows

- **Changed:** Recorded D20, D50 and D80 archive identities, real Windows selection and quality results, and the measured hint requirements for the 40′ Orion field.
- **Verified:** Source and copied console runs confirmed D20/D50 successes, the D80 quality rejection, incomplete-catalog handling and blind timeout. A native desktop solve with D50 passed settings, save and independent FITS export checks with the window and dialog on the second display. All source and archive hashes matched and 42 targeted tests passed.
- **Related:** Resolved Q-015 and Q-017. Q-016 retains the cross-catalog quality findings. [Dense catalog results](docs/phase-36-results.md#dense-astap-catalog-verification)
- **Next:** Inventory Windows bundle notices. The separate clean-machine check awaits a fresh Windows environment. Windows Sandbox and Hyper-V remain disabled on the development host.

### 2026-11-19 - Release - Prepared 0.1.0 source publication and Windows candidates

- **Changed:** Added a public-facing release guide and generated component notices for the desktop and CLI. The bundles carry the application license, runtime notices, upstream supplements and a native-file inventory.
- **Verified:** Both locked Windows x64 builds completed. Checked the two ZIP layouts and their 33 desktop and 31 CLI component entries, documentation links, Poetry lock and packaging code style. Application tests were deferred at the owner's request.
- **Related:** Q-005 tracks remaining binary redistribution work. [Release guide](docs/windows-release.md) · [GitHub repository](https://github.com/Batu-98/AstroMosaic)
- **Next:** Review native corresponding sources and redistribution terms before publishing the portable binaries. The clean-machine acceptance check remains open.

### 2026-11-19 - Application tests - Prepared five merge-ready image pairs

- **Changed:** Added an [agent runbook](docs/application-tests.md) and a fixture generator for real M17 tiles, narrow skewed and wide RGB skies, and synthetic and Paranal nightscapes. The local pack includes labeled panels, masks, saved projects, hashes and a contact sheet.
- **Verified:** All pairs exceeded 10% measured support overlap. Five preflights, ten source exports, independent FITS/TIFF/XISF checks, two native CPU previews and a packaged Paranal comparison passed. Qt reported one display. All 16 focused regression tests passed, and a fresh download and rebuild reproduced the fixture hashes.
- **Related:** Q-010 tracks independently acquired foreground frames. The Paranal case uses two adapted crops of one credited panorama.
- **Next:** Use the runbook for desktop and portable acceptance on a fresh Windows installation when available.

### 2026-11-19 - Application tests - Prepared a local wide-angle capture sequence

- **Changed:** Prepared a local owner-supplied case with an accepted multi-panel sky mosaic, a quick sky pair, editable masks and a foreground diagnostic. Added an optional case entry to the local fixture index.
- **Verified:** Both ready sky projects exceeded 10% overlap on their connecting edges and passed preflight, export, independent TIFF checks and desktop CPU preview. The desktop reproduced the foreground rejection. Original input hashes matched after the run.
- **Related:** Q-010 tracks the disconnected foreground alignment and Q-016 tracks the horizon-row solve failures and quality rejections.
- **Next:** Inspect shared foreground features and refine the horizon masks before retrying the excluded frames.

### 2026-11-19 - Application tests - Verified the five source and portable CLI cases

- **Changed:** Ran SKY-01 through MIX-02 through both CLI launchers. Recorded stdout JSON, progress, elapsed time and input fingerprints under `output/application-tests/20261119-110157-116/`.
- **Verified:** Both launchers passed five preflights and ten exports. Independent FITS, TIFF and XISF reads matched across launchers. All 27 prepared files retained their SHA-256 hashes.
- **Related:** Q-003 and Q-010. Full-resolution previews confirmed 17,857 and 22,579 common pixels for MIX-01 and MIX-02 respectively.
- **Next:** Finish native renderer and visual checks and summarize the run.

### 2026-11-19 - Application tests - Completed the five native desktop cases

- **Changed:** Tested all five fixture pairs on native Windows with CPU and OpenGL previews. The local `output/application-tests/20261119-110157-116/test-report.md` links the timings, logs, screenshots and independent checks. [Recorded findings](docs/application-test-findings.md#what-the-tests-established)
- **Verified:** Both renderers passed all five cases. Desktop exports matched CLI samples and masks, and display stretch left export values unchanged. The two foreground fits recovered (+454, +8) and (+510, 0) pixels. All 13 focused regressions passed with native OpenGL enabled.
- **Related:** Q-022 tracks early automation exits. Isolated runs passed, and both renderers also opened, previewed and exported the five sky projects in one window.
- **Next:** Use a fresh Windows installation for the clean-machine check. Second-monitor placement remains unverified on the single-display host.

### 2026-11-19 - Application tests - Prepared and verified ten extended cases

- **Changed:** Added a labeled pack with three separate atlas tiles, scaled FITS, polar and skewed views, wide SIP imagery, XISF validity, per-band products, and three wide nightscapes. The [extended guide](docs/application-tests-extension.md) covers overlap, expected values, and repeat runs.
- **Verified:** All ten cases passed the source and portable CLI and native CPU and OpenGL desktop. Each entry point produced 18 exports with identical samples, coverage, contribution masks, and applicable WCS metadata. Fresh public downloads reproduced the inputs and overlap geometry. The XISF input records a new creation timestamp per build. All 26 focused existing numerical tests passed.
- **Related:** Q-003 and Q-010. The single-window desktop run also provides evidence for Q-022. The local report is `output/application-tests/extended-20261119/test-report.md`. [Extended results](docs/application-tests-extension.md#native-desktop-pass)
- **Next:** Use the extended fixtures during clean Windows distribution acceptance. Qt reported one display on this host.

### 2026-11-19 - Application tests - Repeated the local owner sequence

- **Changed:** Repeated the two ready sky projects, masked plate solves and foreground checks. Saved 60 individual test logs in the local run directory.
- **Verified:** CLI and CPU desktop TIFFs matched exactly. Native CPU and OpenGL previews passed on one display. Gaia repeated 15 accepted solutions. ASTAP D05 found one additional TAN candidate under the standard gate, and mandatory edge validation rejected it. The foreground checks reproduced the expected disconnected-overlap diagnostic. All source hashes matched.
- **Related:** Q-010 and Q-016. The local report is `output/application-tests/pa4-retest-20261119-1145/test-report.md`. [PA4 findings](docs/application-test-findings.md#local-evidence)
- **Next:** Check outer-field star support and shared terrain control points before attempting another mixed mosaic.

### 2026-11-19 - Application tests - Reviewed results and proposed follow-up work

- **Changed:** Wrote the [application test findings](docs/application-test-findings.md) with priorities and measurable checks for foreground diagnostics, masked plate solving, wide ZEA preview performance and native window lifecycle.
- **Verified:** Cross-checked the three run reports, relevant logs, current code and frozen criteria. Reviewed report and guide links.
- **Related:** Q-010, Q-016 and Q-022 track existing behavior. Q-023 records the wide ZEA warning and profiling work.
- **Next:** Collect per-pair foreground rejection details and per-region catalog measurements. Clean-machine acceptance remains open.

### 2026-11-19 - Documentation - README quick starts and project support

- **Changed:** Added a Buy Me a Coffee section, moved the source quick starts ahead of the development references, and clarified supported formats and Windows release status.
- **Verified:** README link and heading checks, the support URL (HTTP 200), the Poetry lock check, and both dependency sync dry runs passed.
- **Related:** Q-005 tracks Windows distribution.
- **Next:** Continue the Windows redistribution review and clean-machine validation.

### 2026-11-19 - Documentation - Simplified the repository README

- **Changed:** Moved setup, command examples, and technical references to the [AstroMosaic guide](docs/guide.md). Put project support and licensing directly below the README introduction and updated the Windows release guide link.
- **Verified:** All five command examples were preserved. The revised Markdown links and headings resolved, the support URL returned HTTP 200, and `poetry check --lock` passed.
- **Related:** Q-005 tracks Windows distribution.
- **Next:** Continue the Windows redistribution review and clean-machine validation.

### 2026-11-19 - Release - Recorded AstroMosaic 0.1.0 Beta 1

- **Changed:** Set the installed version to `0.1.0b1`, show it with a Beta label in the desktop title, and document the source pre-release and verification process. [Release process](docs/windows-release.md)
- **Verified:** The Windows test suite passed 178 tests with the native Qt platform. The opt-in OpenGL test passed separately. The desktop title, CLI version, Poetry lock, wheel metadata, and documentation links were checked.
- **Related:** Q-005 tracks Windows binary distribution. [GitHub pre-release](https://github.com/Batu-98/AstroMosaic/releases/tag/v0.1.0b1)
- **Next:** Complete the redistribution review and clean Windows 11 x64 acceptance before publishing portable packages.

### 2026-11-19 - Documentation - Updated the GitHub repository description

- **Changed:** Updated the GitHub About description to identify AstroMosaic as Windows astrophotography mosaic software and name its supported panel formats and offline plate solving.
- **Verified:** The full description appears in the public repository page and API response.
- **Related:** [AstroMosaic GitHub repository](https://github.com/Batu-98/AstroMosaic)
- **Next:** Review search visibility after the updated description is crawled.

### 2026-11-19 - Application tests - Verified rejection stages and prioritized follow-up

- **Changed** Reviewed the application test matrix and recorded the foreground and inverse replays in the [test findings](docs/application-test-findings.md).
- **Verified** All 37 focused layer, ZEA, solve-quality, ASTAP catalog and solve-budget tests passed. The saved six-panel PA4 group rejected all 15 pairs at the thumbnail correlation gate. A synthetic TAN-SIP inverse reproduced the all-NaN warning for invalid input and for finite directions outside the projection domain.
- **Related** Q-010, Q-016, Q-022 and Q-023. Clean-machine acceptance for the intended Windows release bundles remains open.
- **Next** Add pairwise foreground diagnostic results and verify PA4 terrain correspondences. Measure D50 catalog resource rejections separately from association and edge quality.

### 2026-11-19 - Phase 6 - Planned real-observation reliability and Windows acceptance

- **Changed** Raised the architecture to revision 3.11 and defined [6A–6E](docs/phase-6.md) for reference preparation, terrain diagnostics, masked solving, ZEA preview and native Windows verification. Specified real observational data for every test in the phase.
- **Verified** Reviewed planned datasets and gates against PA4, the real archive and wide-field references, and the Windows release procedure. Reviewed Markdown content and links for this planning change.
- **Related** Q-003, Q-005, Q-010, Q-016, Q-022 and Q-023.
- **Next** Freeze the PA4 and archive references, select the independent positive and negative mixed captures, and record the baseline before tuning.

### 2026-11-19 - Mixed panels - Traced the current processing path

- **Reviewed** Followed the desktop import, mask editing, sky solving, ground alignment, placement, and shared rendering entry points in source.
- **Verified** The import job proposes a foreground tag. Defined mask labels select the sky and ground samples. Ground alignment estimates translations, and composition placement fits a similarity transform between the two layers.
- **Related** [Mask workflow](docs/phase-3d.md#desktop-workflow), [layer workflow](docs/phase-3e.md#desktop-workflow), and Q-010.
- **Next** Use the traced foreground and sky paths when freezing real-observation references in [Phase 6A](docs/phase-6.md#6a-freeze-the-real-data-baseline).

### 2026-11-19 - Phase 7 - Researched and planned terrain panorama registration

- **Changed** Added [Phase 7A–7F](docs/phase-7.md) in revision 3.12. Planned manual terrain points first, bounded automatic matching, measured camera-model selection, and shared rendering and Windows acceptance on real captures.
- **Verified** Compared PTGui and Hugin documentation and the original panorama literature with the PA4 measurements, translation matcher, persistence and composition paths. Reviewed the phase gates and documentation links.
- **Related** Q-003, Q-005, Q-010 and [proposed ADR-0023](docs/adr/0023-terrain-control-point-registration.md).
- **Next** Prepare the Phase 6A–6B real terrain references, annotate verified overlaps, and compare the candidate models using the Phase 7A split.

### 2026-11-19 - Phases 6 and 7 - Clarified foreground responsibilities and handoff

- **Changed** Assigned the current translation baseline and PA4 diagnostics to 6A–6B. Assigned expanded control points, holdout preparation and model comparison to 7A. Documented the handoff records and the Windows build covered by each acceptance run.
- **Verified** Reviewed the updated phase scope, acceptance gates and links against the existing translation matcher, mixed export workflow and Windows release procedure.
- **Related** Q-003 and Q-010. [Handoff to Phase 7A](docs/phase-6.md#handoff-to-phase-7a)
- **Next** Freeze the real translation and rejection controls and record the 6B pair evidence before the 7A model comparison.

### 2026-11-19 - Phase 6A - Recorded the first real-observation baseline

- **Changed** Added individual case selection to the application checker. Recorded the input and catalog hashes, projects, mask versions, exports, commands and diagnostics in `output/application-tests/phase6a-20261119-155643-651/`.
- **Verified** Independently reopened four sky exports and one foreground export. The eight PA4 horizon replays matched earlier outcomes. Five real solve controls met their quality limits. All 23 PA4 source hashes matched, and all 15 foreground comparisons reproduced their correlation rejections. Rebuilding the ESO control reproduced its reference manifest byte for byte. Ruff and the new documentation links passed.
- **Related** The real ESO ALPACA pair recovered (+48, +16) source px against the landmark reference (+47.98, +16.23) px. The disjoint control returned two singleton groups. Q-003, Q-010, Q-016 and Q-023. [Phase 6A measurements](docs/phase-6.md#local-baseline-measurements)
- **Next** Complete the mixed control's sky geometry and use the saved pair results for 6B. The ALPACA sky probe produced insufficient catalog matches, so its composition remains pending.

### 2026-11-19 - Phase 6A - Verified the independent mixed reference

- **Changed** Calibrated the two real ALPACA crops against Gaia DR3 and saved source- and mask-bound sidecars and a visual composition placement.
- **Verified** Held-out P95 was 0.363 and 0.410 source px. The independently reopened sky, foreground and composition FITS files passed the coverage, sample and contribution checks. The reference files and calibration evidence are in `output/application-tests/phase6b-work/`.
- **Related** Q-003 and Q-010. [Mixed reference](docs/phase-6.md#calibrated-alpaca-mixed-reference)
- **Next** Use the mixed project for the foreground diagnostics replay and later native Windows acceptance.

### 2026-11-19 - Phase 6B - Verified foreground alignment diagnostics

- **Changed** Added pairwise support, correlation and refinement outcomes to the shared alignment operation. The desktop details dialog lists the pairs and groups and opens either selected mask.
- **Verified** All 15 PA4 scores matched the original baseline. The reduced-mask variant saved and reopened and still gave six isolated groups. The ALPACA positive, negative, support and cancellation/retry checks passed. Native CPU and OpenGL mixed previews and exports, four focused real-data regressions, Ruff and mypy passed.
- **Related** Q-003 and Q-010. [6B results](docs/phase-6.md#local-foreground-diagnostics-results)
- **Next** Instrument the PA4 horizon solves in 6C and use the recorded terrain results to prepare the 7A landmark review.

### 2026-11-19 - Phase 6C - Measured catalog limits in the real horizon row

- **Changed** Added attempt gates, effective hints and regional ASTAP read diagnostics to the source CLI and desktop details. Verified the installed CLI and complete D05 and D20 catalogs.
- **Verified** Replayed the original three D50 failures from captured native candidates. Smaller detection-bearing cones still hit 100,000 retained stars. Identified the existing bright-subset selection and validated bounded early filtering against the full D05 reference.
- **Related** Q-016 and [Phase 6C measurements](docs/phase-6.md#local-masked-solve-results). The regional records and commands are in `output/application-tests/phase6c/`.
- **Next** Verify the bounded reader across all eight PA4 horizon frames and the real solve controls.

### 2026-11-19 - Phase 6C - Verified bounded validation and protected PA4 admission

- **Changed** Adopted bright-first filtering in wide ASTAP validation. The three previously resource-limited candidates reached association at 17.69–23.92 MiB per candidate.
- **Verified** All eight horizon frames retained explicit rejection reasons. The six real solve controls passed and the D50 Orion sidecar drove an independently verified FITS export. The real desktop rejection details, mask identity, source hashes, cancellation, late publication and retry checks passed. Fifteen targeted real-data tests, Ruff, mypy and local documentation links passed.
- **Related** Q-016 and [Phase 6C measurements](docs/phase-6.md#local-masked-solve-results). The ready PA4 sky mosaic retains 15 qualified panels.
- **Next** Capture the exact real PA4 ZEA warning for 6D.

### 2026-11-19 - Phase 6D - Isolated the PA4 inverse warning

- **Changed** Screened the core projection before the shared iterative inverse. The reduced replay uses PA4-10 and the first 128 × 128 tile of the recorded ZEA grid.
- **Verified** All 16,384 directions are finite in ZEA and outside PA4-10's TAN hemisphere. The baseline hit Astropy's all-NaN reduction. The corrected real tile, mixed batches, near-rim sample and singular WCS checks passed.
- **Related** Q-023 and [6D acceptance](docs/phase-6.md#6d-reproduce-the-zea-warning-and-measure-preview-cost).
- **Next** Compare conservative ZEA panel selection with all-panel renders and finish the native timing runs.

### 2026-11-19 - Phase 6D - Verified ZEA output and adopted conservative panel selection

- **Changed** Added conservative ZEA candidate bounds for ordinary ICRS TAN and TAN-SIP sources. Documented the bound and the full traversal fallback in [ADR-0024](docs/adr/0024-conservative-zea-footprints.md).
- **Verified** The full PA4 export matched the guarded all-panel and 6A TIFF references for samples, 3,238,763 covered pixels and WCS. Profiled export time fell from 83.91 to 38.25 s. The 24 native CPU and OpenGL previews matched at both resolutions. Independent cropped, rim, FITS and XISF checks, ALPACA layer parity, PA4 hashes, 15 real-data regressions, Ruff and mypy passed.
- **Related** Resolved Q-023. [6D evidence](docs/phase-6.md#local-zea-geometry-and-performance-results) records the cold and warm timings, inverse work, TIFF reads, candidate counts and reservations.
- **Next** Investigate native close, reopen and cancellation in 6E, then check the intended portable build on a clean Windows 11 x64 environment.

### 2026-11-19 - Phase 6E - Reproduced both Windows lifecycle failures

- **Changed** Added a real-data native replay with Qt messages and window and worker lifecycle events. Release OpenGL preview resources before closing an accepted project window.
- **Verified** Replacing a window while its real export was still cancelling reproduced `0xc0000409` on CPU and OpenGL. Qt reported a running `QThread` being destroyed. The orderly close waited for cancellation and removed the temporary export. The initial orderly OpenGL run exposed a separate texture destructor running during a later worker's Python garbage collection.
- **Related** Q-022 and [6E requirements](docs/phase-6.md#6e-verify-native-lifecycle-and-windows-packages). Initial traces are in `output/application-tests/phase6e/`.
- **Next** Rerun the native transitions with the OpenGL cleanup and verify packages built from the updated source.

### 2026-11-19 - Phase 6E - Verified the local Windows candidate

- **Changed** Built and inventoried the desktop and CLI packages from the same source snapshot. Recorded their ZIP and executable hashes and resolved Q-022.
- **Verified** Eight normal native lifecycle sequences passed with clean cancellation and same-name retry. The nine real products matched on all six source and portable entry points. The regular packaged launcher exported the M17 TIFF and exited normally. CLI solve admission, desktop M13 and PA4-07 checks, the frozen input hashes, 20 real-observation tests, Ruff and mypy passed.
- **Related** [6E evidence](docs/phase-6.md#local-windows-lifecycle-and-package-results), Q-022 and Q-005. Candidate files are in `.tooling/phase6e-20261119/artifacts/`.
- **Next** Record fresh Windows 11 x64 acceptance for the exact candidate and finish the redistribution review. The development host has Windows Sandbox and Hyper-V disabled.

### 2026-11-19 - Phase 6 - Prepared the source checkpoint

- **Changed** Collected the Phase 6 implementation, real-observation tests and updated architecture and test guides for `main`.
- **Verified** Matched all changed Python files to the verified 6E snapshot. Ruff, mypy and the repository link checks passed.
- **Related** [6E evidence](docs/phase-6.md#local-windows-lifecycle-and-package-results) and Q-005.
- **Next** Run fresh Windows acceptance for the recorded 6E archives.

### 2026-11-19 - Documentation - Recorded version control and release rules

- **Changed** Added the Git workflow, application and schema version rules, beta tags, and release verification to [AGENTS.md](AGENTS.md#10-version-control-and-releases).
- **Verified** Reviewed the rules against the current package version and release procedure. Checked all links in `AGENTS.md` and ran `git diff --check` for the documentation edits.
- **Related** [Release procedure](docs/windows-release.md#record-a-release) and Q-005.
- **Next** Apply the rules when preparing the next release.

### 2026-11-19 - Phase 6 - Advanced the development beta

- **Changed** Set the application version to `0.1.0b2` and recorded the version of the earlier Phase 6E build.
- **Verified** `poetry check --lock`, the wheel metadata, CLI version, and desktop title passed. The real M17 project validated and reopened after saving with the new application version.
- **Related** [Version control and releases](AGENTS.md#10-version-control-and-releases) and [Phase 6E evidence](docs/phase-6.md#local-windows-lifecycle-and-package-results).
- **Next** Build matching `0.1.0b2` Windows packages and complete the fresh-installation checks for that build.

### 2026-11-20 - Phase 7A - Measured the first PA4 terrain overlap

- **Changed** Reviewed 15 PA4 pair outcomes against both saved mask variants. Measured corresponding branches on 04–05 and compared translation and similarity on the same held-out landmarks. Extended the ALPACA translation reference and inventoried three real PASSTA panning captures.
- **Verified** Six PA4 source hashes and both sets of mask labels matched the Phase 6 inventory. PA4 held-out forward P95 fell from 306.08 to 72.11 px on visible terrain. Only two of ten quality-checked landmarks had joint ground support in the original masks. ALPACA translation reached 1.43 px held-out P95. Four foreground regressions passed, both local reports replayed byte-for-byte, and the PASSTA archive passed ZIP integrity and three image opens.
- **Related** Q-003 and Q-010. The [7A measurements](docs/phase-7.md#initial-7a-measurements) describe the open pair diagnoses and replay procedure.
- **Next** Independently re-mark the plausible overlaps and review the ground masks. Resolve the PASSTA calibration orientation and qualify the independent nightscape and depth-change cases.

### 2026-11-20 - Phase 7A - Froze the real reference set

- **Changed** Measured PA4-02/03 and 05/06 and reverse-refined the 04/05 points. Added Oxford Boat, La Silla, PASSTA and Adirondack controls with recorded source identity and fit/held-out assignments.
- **Verified** Boat similarity reached 1.02/1.16 px forward/reverse held-out P95 and La Silla translation reached 0.94 px in both directions. PASSTA's clockwise sensor orientation won on all three edges and the pairwise rotation loop closed to 0.0041°. Adirondack had about 122 px difference between near and far shifts. The six follow-up reports replayed byte-for-byte and four foreground tests passed.
- **Related** Q-003 and Q-010. [Frozen 7A references](docs/phase-7.md#frozen-7a-references)
- **Next** Implement and verify 7B with the fixed ALPACA and Oxford point cases. Keep PA4 ground-mask and depth hypotheses for terrain review and further model validation.

### 2026-11-20 - Phase 7B - Verified the headless manual terrain fit

- **Changed** Added the Qt-free manual control-point fit and `project fit-foreground`. It reports validation, anchored translation or similarity, per-point errors and rejected links. Project geometry persistence remains scheduled for 7E.
- **Verified** ALPACA, the two- and three-view Oxford cases, and La Silla passed the held-out limit. Adirondack, an inconsistent real-data cycle and underconstrained inputs returned rejection diagnostics. Cancellation and retry preserved the previous saved alignment. The full suite passed 199 tests with two opt-in OpenGL skips. The final focused replay passed 26 tests with the same skips. Five CLI control replays, Ruff and mypy passed.
- **Related** Q-003, Q-010 and ADR-0023. [7B command and results](docs/phase-7.md#run-a-manual-terrain-fit)
- **Next** Start the 7C bounded feature matching comparison with the 7B point sets and preserve the public negative controls.

### 2026-11-21 - Phase 7C - Evaluated bounded automatic terrain matching

- **Changed** Added optional SIFT point proposals and independent audits to the read-only foreground CLI. Added full-support thumbnails, mutual feature checks, source-patch refinement and spatial inlier requirements to the shared anchored fit.
- **Verified** The audited three-view Oxford graph reached 0.97 px maximum edge P95 and La Silla reached 0.98 px. The disconnected ALPACA group and Adirondack produced zero false links. Manual points recovered sparse ALPACA mask support at 1.43 px. The automatic ALPACA translation missed its frozen tolerance. Both PA4 mask variants and PASSTA remained disconnected. The full suite passed 204 tests with two opt-in OpenGL skips. Seven manual and missing-backend checks passed separately without OpenCV on the Python path. Ruff, mypy and the documentation link checks passed.
- **Related** Q-003, Q-005, Q-010 and [7C results](docs/phase-7.md#7c-real-observation-results). Ten Qt-free CLI reports repeated byte-for-byte with matching project hashes. Oxford and PA4 reservations peaked at 63.4 and 112.1 MiB respectively.
- **Next** Carry the frozen PASSTA calibration and landmarks into 7D. Review the local wheel inventory before any portable adoption.

### 2026-11-21 - Phase 7D - Evaluated rotation and retained translation and similarity

- **Changed** Added an offline replay for anchored rotation, one shared focal adjustment, one shared radial adjustment and the planar baselines. The replay uses the frozen observations and verifies calibration, crops, pixel scale, inverse maps and boundary samples.
- **Verified** PASSTA's independent loop closed to 0.0041°. The worst held-out P95 was 6.90 px with fixed calibration and 4.13 px with the best radial candidate. Adirondack rejected both a global pose and the far subset. The PA4 metadata estimate reached 8.34 and 3.07 px on visible terrain and kept the masked links unsupported. The report replayed byte-for-byte and the NumPy geometry agreed with the separate OpenCV probe. The full suite passed 205 tests with two opt-in OpenGL skips. Seven focused tests passed without OpenCV on the Python path. Ruff, mypy and the documentation link checks passed.
- **Related** ADR-0023, Q-003, Q-010 and [7D measurements](docs/phase-7.md#7d-real-observation-results).
- **Next** Integrate the verified translation and similarity models in 7E and check legacy saved translations, tile sampling, and scientific sky independence.

### 2026-11-21 - Desktop Plate Solve - Start directly in untitled projects

- **Changed** Removed the sidecar folder prompt from Plate Solve and Revalidate Plate Solution. Untitled projects use the local application data directory. Saved projects use their sibling WCS directory.
- **Verified** Five native Windows desktop tests passed. An untitled real M13 panel solved from the Plate Solve button with ASTAP D05 and zero folder requests. The saved project reopened with the generated sidecar and its input hash was preserved. The new 0.1.0b2 desktop executable started and closed cleanly.
- **Related** [Desktop plate solving](docs/phase-3b.md#desktop-plate-solving).
- **Next** Verify the packaged Phase 7 CLI and inventory the local development bundles.

### 2026-11-21 - Windows - Built local 0.1.0b2 with the Phase 7 CLI

- **Changed** Built the desktop and CLI from a hashed working-tree snapshot and the Poetry lock. Built a separate optional SIFT CLI with the measured OpenCV wheel. Archived the complete bundles with their notices and SHA-256 hashes.
- **Verified** The desktop reported 0.1.0b2, contained the corrected Plate Solve handler, and exited cleanly. Both CLIs reported 0.1.0b2. The standard CLI fit Oxford's three-view manual control at 1.10 px P95. The SIFT CLI reached 0.97 px on Oxford and 0.98 px on La Silla and rejected the disconnected ALPACA, Adirondack and PA4 controls. The suite passed 205 tests with two opt-in OpenGL skips. Ruff, mypy and documentation link checks passed.
- **Related** [Local release verification](docs/windows-release.md#verification-status), Q-005 and [Phase 7 commands](docs/phase-7.md#run-the-automatic-terrain-fit). Local replay reports are stored in `output/application-tests/plate-solve-phase7-20261121/`.
- **Next** Integrate Phase 7 geometry into rendering and project persistence. Use the local bundles for development, and verify an exact tagged build on a fresh Windows host before public distribution.

### 2026-11-21 - Phase 7 - Reviewed readiness for 7E

- Reviewed the working tree against the 7A–7F gates. The headless fit reports candidate poses. The foreground tile sampler and its footprint calculation still use saved panel shifts.
- Reran the 12 focused real-observation regressions for control points, automatic matching and the camera-model comparison. All 12 passed with the isolated OpenCV provider. In the standard environment, eight passed and the four provider-dependent checks skipped.
- Start 7E by saving and reopening Oxford's three-panel similarity fit and checking rendered samples and coverage. Keep ALPACA as the saved-translation control and verify sky-only samples, coverage and WCS for a mixed scene. [7E criteria](docs/phase-7.md#7e-integrate-geometry-rendering-and-persistence)

### 2026-11-21 - Desktop command panel - Opened at startup and recorded operation summaries

- **Changed** Opened the Command Panel at startup at its minimum dock height. Added project, panel and settings summaries and desktop job outcomes to the bounded session log, including while hidden.
- **Verified** All 207 tests passed on native Windows with OpenGL and the optional SIFT provider. Six focused desktop tests passed on native Windows and with Qt offscreen. Ruff, mypy, the Poetry lock check and the documentation link review passed.
- **Related** Q-012 and the [command panel workflow](docs/phase-4c.md#desktop-workflow).
- **Next** Include the updated command panel checks in the next Windows package verification.

### 2026-11-21 - Desktop sky preview - Recovered the two-panel TIFF project

- **Changed** Added desktop and Command Panel guidance for missing sky metadata and empty sky previews. Prepared a separate project with relative linear sRGB copies, the verified WCS and a TAN grid that encloses both panels.
- **Verified** The original project reproduced the missing filter and brightness diagnostics. The old grid covered one panel. The reopened preview covered 120,324 samples, including 25,786 shared by both panels. Native Windows CPU and OpenGL previewed it on the second display. Both CLIs validated the project, all 28 focused tests passed, and Ruff and mypy passed. The original project, images and sidecar hashes matched.
- **Related** Q-024 and [sky preview setup](docs/phase-3c.md#desktop-workflow).
- **Next** Carry the diagnostic checks into the next desktop package verification.

### 2026-11-21 - Source integration - Verified terrain and desktop changes for main

- **Changed** Prepared the Phase 7 terrain work, desktop solving, command panel, sky preview diagnostics and their records as separate source commits for `main`.
- **Verified** All 207 tests passed on native Windows with OpenGL and the isolated SIFT provider. The desktop checks used the second display. The standard environment passed seven terrain checks with four optional provider checks skipped. Ruff, mypy, the Poetry lock check and local documentation link checks passed.
- **Related** Q-003, Q-010, Q-012 and Q-024.
- **Next** Use the verified translation and similarity controls for Phase 7E. Include the desktop diagnostic checks in the next Windows package verification.

### 2026-11-21 - Windows build - Assigned beta 3 to the merged desktop fixes

- **Changed** Set the development version to `0.1.0b3` for a new local Windows build from the merged source.
- **Verified** The older `0.1.0b2` executable matches its archived launcher. Its source snapshot precedes the Command Panel startup and sky preview diagnostic changes.
- **Related** Q-012, Q-024 and the [Windows build workflow](docs/windows-release.md#build-portable-windows-packages).
- **Next** Build from this source revision and verify the title, Command Panel and Build Preview in the resulting Windows package.

### 2026-11-21 - Windows build - Verified the beta 3 desktop package

- **Changed** Built the desktop and standard CLI from clean commit `900dba19dc7de1c326c8c17878e812d64085a963` using the Poetry lock. Placed the desktop runtime and provenance in a versioned local folder.
- **Verified** The production EXE title and bundled CLI both reported `0.1.0b3`. On the second display, CPU and OpenGL reopened the copied package runtime, verified the default Command Panel and hidden history, reproduced both missing metadata diagnostics and built the recovered two-panel preview with 120,324 covered samples. The test used the same embedded desktop and preview modules as the launcher. The original project, images and sidecar hashes matched.
- **Related** Q-024, Q-025 and [Windows build verification](docs/windows-release.md#verification-status).
- **Next** Use this local beta for the combined desktop fixes. Record fresh Windows acceptance for a future tagged package.

### 2026-11-21 - Development workflow - Recorded Windows build handoff rules

- **Changed** Added instructions to `AGENTS.md` for delivering versioned Windows builds, recording their source commit and verifying the changed workflow in the packaged runtime.
- **Verified** Reviewed the rules against the release procedure and beta 3 evidence. Checked the document links and diff.
- **Related** Q-025 and [Local Windows Build Handoff](AGENTS.md#local-windows-build-handoff).
- **Next** Apply the handoff checks to the next Windows executable delivery.

### 2026-11-21 - Sky preview - Defaulted unlabeled panels to Unspecified

- **Changed** Shared the `Unspecified` fallback between desktop band selection, CLI project discovery and sky rendering. Assigned version `0.1.0b4` for the Windows handoff.
- **Verified** Fifteen focused tests passed. The saved two-panel project lists both panels in `Unspecified` and reaches brightness validation. Explicit labels still form their own groups. Ruff, mypy and the Poetry lock check passed.
- **Related** Q-024 and [sky band selection](docs/phase-5c.md).
- **Next** Verify the automatic label and a successful two-panel preview in the beta 4 desktop package.

### 2026-11-21 - Windows build - Verified the default sky band in beta 4

- **Changed** Built beta 4 from clean source commit `6ca71f54f89c7474ffe8376ddb18fa70f65d7aa5` with the Poetry lock. Saved the desktop runtime and build record in a versioned local folder.
- **Verified** All 208 tests passed on native Windows with OpenGL and the isolated SIFT provider. The packaged CLI listed both original panels in `Unspecified`. The production EXE reported beta 4. Native CPU and OpenGL on the second display previewed the unlabeled real linear TIFF copies with 120,324 covered samples. Source TIFF and project hashes matched, and the original display TIFFs reached brightness validation.
- **Related** Q-024, Q-025 and [Windows build verification](docs/windows-release.md#verification-status).
- **Next** Use beta 4 for the automatic band workflow and retain the real TIFF check for subsequent Windows packaging.

### 2026-11-21 - Plate Solve - Show activity while solving a panel

- **Changed** Enabled a busy progress bar during eligibility checks and solving. The status names the active panel in the batch and advances at every panel boundary. Assigned version `0.1.0b5` for the Windows handoff.
- **Verified** The new assertion reproduced the earlier bar staying at 0%. After the fix, 19 targeted tests passed, including cancellation with partial outcomes and a retry. Ruff, mypy and the Poetry lock check passed.
- **Related** Q-026 and [desktop plate solving](docs/phase-3b.md#desktop-plate-solving).
- **Next** Verify the animation during a real solve in the portable Windows runtime.

### 2026-11-21 - Windows build - Verified plate solve progress in beta 5

- **Changed** Built the beta from clean source commit `1c787b56176ccd9bf58befe1bb397f189301a825` with the Poetry lock. Saved the desktop and its build record in the versioned local folder.
- **Verified** All 208 source tests passed across offscreen and native OpenGL runs. The desktop title and bundled CLI reported `0.1.0b5`. On the second display, the packaged runtime animated through a single M13 DSS solve, a batch, cancellation and retry, and revalidation with either preview backend active. ASTAP D05 solved the real panels. Cancellation retained the completed WCS. The observational fixture and its staged copies kept their hashes.
- **Related** Q-026 and [Windows build verification](docs/windows-release.md#verification-status).
- **Next** Retain the active-panel and cancellation checks for subsequent desktop builds.

### 2026-11-21 - Phase 4 follow-up - Add dialog-free project operations

- **Changed** Audited file dialogs and the saved-project CLI boundary. Added Command Panel `session` commands for the live project and headless preparation for moved sources, plate solving, labeled masks, foreground alignment and composition placement. Assigned version `0.1.0b6` for the Windows handoff.
- **Verified** Source regressions exercised first save, occupied filenames, unsaved changes, export from the active project, relink and close without a dialog. CLI regressions covered reopen, WCS reuse, successful publication, failure and cancellation cleanup, label import and composition export.
- **Related** Q-027, [headless preparation](docs/phase-4a.md#prepare-a-project-without-the-desktop) and [live desktop commands](docs/phase-4c.md#control-the-active-project-without-dialogs).
- **Next** Run the complete source suite and verify the new CLI and session workflows in portable Windows builds.

### 2026-11-21 - Windows build - Verified beta 6 project automation

- **Changed** Built both launchers from clean source commit `a4ad3825adbf816c8a70246ecb24740998938d63` with the Poetry lock. Saved each runtime with its version and launcher checksum.
- **Verified** All 215 source tests passed across offscreen and native OpenGL. Ruff, mypy and the Poetry lock check passed. The second-display desktop run used real M13 data for first save, overwrite refusal, solve, preview, export from unsaved state, relink and close with zero dialogs. The Qt-free CLI recovered from a solve deadline and reopened an M13 FITS with 16,384 covered samples. It imported the two real Paranal editor-grid masks, aligned the foreground, checked both placement paths and reopened the composition TIFF with 1,434,510 covered samples. The original files and manifests kept their hashes.
- **Related** Q-027 and [Windows build verification](docs/windows-release.md#verification-status).
- **Next** Retain the dialog and atomic publication regressions. Continue the planned terrain pose persistence and rendering in [Phase 7E](docs/phase-7.md#7e-integrate-geometry-rendering-and-persistence).

### 2026-11-21 - Sky preview - Recovered a saved sRGB project

- **Changed** Prepared a separate visual preview project for the most recently saved copy of the two-panel TIFF project. It references the existing float32 linear-light conversions and uses a sky grid that covers both fields.
- **Verified** Reproduced the brightness-unit failure with the beta 6 CLI. Both original TIFFs have sRGB profiles and no `BUNIT`. The current WCS sidecars and the linear copies agree on a 33 × 33 sample grid per panel. The beta 6 CLI accepted the new project, and the native second-display OpenGL preview covered 120,324 samples, including 25,786 shared by the two panels. The inputs, current manifest and attached WCS files kept their hashes.
- **Related** Q-024 and [desktop sky preview](docs/phase-3c.md#desktop-workflow).
- **Next** Use the prepared project for the relative visual preview.

### 2026-11-21 - Documentation - Map the current application workflows

- **Changed** Added a [workflow reference](docs/workflows.md) for desktop, CLI and batch use, including the panel, solver, layer, preview, export and recovery branches. Linked it from the guide.
- **Verified** Parsed nine Mermaid flowcharts, checked 64 relative file and section links, and compared the documented commands and desktop controls with the beta 6 source.
- **Related** Q-024, Q-026 and Q-027.
- **Next** Update the reference when the implemented workflows change.

### 2026-11-21 - Sky preview - Implemented automatic framing and sRGB preview

- **Changed** Added WCS framing, a visual sRGB sky preview and explicit export grid adoption to the desktop and session commands.
- **Verified** The initial focused source suite passed 21 tests. The original TIFFs with their existing solved WCS covered 109,331 preview samples, including 23,020 shared samples. Science preflight rejected the encoded inputs even with a common-scale declaration.
- **Related** Q-028 and [ADR-0025](docs/adr/0025-automatic-sky-preview.md).
- **Next** Run the fresh solve workflow and verify the locked beta 7 Windows package.

### 2026-11-21 - Sky preview - Rechecked the PA4 ZEA case

- **Changed** The PA4 crop regression exercises the visual preview with the original sRGB TIFFs and checks that scientific export rejects them.
- **Verified** All four real PA4 ZEA tests passed. The 384 × 384 preview retains 4,869 covered samples. Pruned and all-panel sampling agree byte for byte, with identical coverage and WCS.
- **Related** Q-028 and [Phase 6D results](docs/phase-6.md#local-zea-geometry-and-performance-results).
- **Next** Finish the complete source and packaged preview checks.

### 2026-11-21 - Windows build - Verified beta 7 sky previews

- **Changed** Built the desktop and CLI from clean source commit `023595ec62f4d634da64ebb7f37e0f0744a0021d` using the locked dependencies. Recorded both launcher hashes and the build time in their versioned directories.
- **Verified** Source OpenGL and packaged CPU and OpenGL each solved the original TIFFs and previewed both panels in an untitled project. The packaged runs matched 109,331 valid samples and 23,020 shared samples on the second display. Both launchers report beta 7. Source checks passed 217 offscreen tests and two native OpenGL tests. Ruff, mypy and the Poetry lock check passed.
- **Related** Resolved Q-028. [Windows build record](docs/windows-release.md#verification-status) · [Preview workflow](docs/phase-3c.md#desktop-workflow).
- **Next** Retain the preview and export boundary regressions. The planned terrain work continues in Phase 7E, with clean-machine and public distribution checks tracked separately.

### 2026-11-21 - Phase 8 - Proposed configurable color photometry and optics

- **Changed** Added a method catalog and staged acceptance for photo export, profile conversion, exposure and brightness matching, lens geometry and vignetting. Linked the proposal from the active architecture.
- **Verified** Reviewed the proposed methods against the current beta 7 processing contract, published PTGui behavior, Mosaic Master source and the ICC and lens references. Checked the outline and document links.
- **Related** Q-029 and [proposed ADR-0026](docs/adr/0026-configurable-color-photometry-and-optics.md).
- **Next** Freeze the 8A contracts and reference data when the owner schedules Phase 8. Use the two original sRGB TIFFs for the 8B photo export acceptance.

### 2026-11-21 - Phase 7E - Integrated saved terrain poses and tile rendering

- **Changed** Added an output option to the terrain-fit command and integrated accepted translations and similarities with the shared foreground renderer, horizon placement and version 7 manifests. Assigned version `0.1.0b8` for the Windows handoff.
- **Verified** The nine real control-point checks passed. The independent Oxford Boat bilinear comparison, unpruned render, legacy ALPACA coverage, invalidation and cancellation, and Paranal sky parity and composition passed. The focused project and layer checks and scoped mypy checks passed.
- **Related** Q-003, Q-010 and [7E source results](docs/phase-7.md#7e-source-results).
- **Next** Build the locked beta and repeat the saved alignment workflow with the Windows launchers.

### 2026-11-21 - Windows build - Verified beta 8 terrain geometry

- **Changed** Built both launchers from clean commit `3ab8e3eb8f899da31722316ec06002d0e74a4c0f` using the Poetry lock. Recorded the build time and launcher hashes in the versioned directories.
- **Verified** The console saved and exported Oxford and ALPACA, rejected the Adirondack fit, and reopened the Paranal composition with sky bytes preserved. The bundled desktop on the secondary display matched the Oxford console export with both CPU and OpenGL. Source passed 220 offscreen and two native tests. The isolated SIFT save, Ruff, scoped mypy and Poetry lock checks passed. Full-tree mypy still reports an existing missing return annotation in the real ZEA regression.
- **Related** Q-003, Q-005, Q-010 and [beta 8 package results](docs/phase-7.md#7e-local-windows-package-results).
- **Next** Add the 7F desktop point-review workflow and run the remaining clean-machine checks on its candidate.

## Entry Template

Copy this format into a new entry immediately above this template, preserving chronological order:

```markdown
### YYYY-MM-DD - Phase N - Status: short outcome

- **Changed:** Brief summary of useful work, or the attempted step if incomplete.
- **Verified:** Relevant commands/checks and their result; identify unavailable checks.
- **Related:** Question IDs, ADRs, or evidence paths; use "None" when appropriate.
- **Next:** One concrete next step and any blocker that affects it.
```
