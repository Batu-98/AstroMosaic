# Development Progress

Use this file for concise development history and handoff state. Detailed technical decisions belong in `docs/adr/`; unresolved work belongs in [questions_open_topics.md](questions_open_topics.md).

## Current State

- **Last updated:** 2026-11-16
- **Active baseline:** Python-first architecture revision 3.9, with [Phase 3.1 desktop plate solving](astro_mosaic_python_first_architecture_en.md#phase-31-desktop-plate-solving), [Phase 3.5 engine revalidation](astro_mosaic_python_first_architecture_en.md#phase-35-astronomy-engine-revalidation), and [Phase 4A–4C automation and scaling](astro_mosaic_python_first_architecture_en.md#102-phase-4-delivery-stages). See [ADR-0003](docs/adr/0003-windows-first-platform-scope.md) for Windows scope, [ADR-0006](docs/adr/0006-dual-fits-and-tiff-workflow.md) for formats, and [ADR-0007](docs/adr/0007-sky-and-foreground-mosaics.md) for mixed panels.
- **Current stage:** Phase 3.1A passed on Windows 11 x64. The Phase 3F clean-machine check remains open. Linux and macOS support is deferred.
- **Available artifacts:** [Panel WCS status and optical hints](docs/phase-3b.md#panel-wcs-and-plate-solve-hints), [portable Windows desktop and CLI bundles](docs/phase-3f.md), and [independent layer previews and exports](docs/phase-3e.md).
- **Implementation / verification:** All 79 native Windows tests passed, with test windows and dialogs on the secondary monitor. Rebuilt desktop checks passed on offscreen CPU and native OpenGL. The packaged CLI passed worker spawning, FITS and TIFF export, and optical-hint solves with local Gaia and ASTAP. Ruff, mypy, Poetry lock validation, and documentation links passed.
- **Version control:** The Windows packaging and revision 3.9 planning snapshot is published as `6685e0f` on `origin/main`. Phase 3.1A is in the local working tree. [AstroMosaic GitHub repository](https://github.com/Batu-98/AstroMosaic)
- **Next action:** Implement Phase 3.1B local plate solve settings. Run the portable launcher and export check in parallel when a clean Windows 11 x64 installation is available.
- **Open dependencies:** Q-003 through Q-005, Q-009, and Q-010 track later numerical, resource, distribution, format, and mixed-panel gates. Q-008 tracks deferred platforms, Q-011 tracks deferred visual fill, and Q-012 tracks desktop terminal scope. Q-006, Q-007, and Q-013 are resolved for the Windows solver, FITS export, and optical hint references.

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
| 3C - Preview and export | Complete | Verified shared preview/export geometry, pan and zoom, display-only stretch, and GPU/CPU fallback on Windows. |
| 3D - Sky masks | Complete | Verified automatic proposals, manual tag and mask edits after reopening, and sky-only solving and fitting. |
| 3E - Foreground and composition | Complete | Verified WCS-independent foreground alignment, separate layer exports, and saved placement, seam, and crop edits on Windows. |
| 3F - Windows acceptance | Local checks passed | Packaged workflows, recovery, cancellation cleanup, and CPU fallback passed on the development host. Clean-machine validation remains open. |
| 3.1A - Panel WCS and optical metadata | Complete | Per-panel WCS status, embedded and edited optical hints, scale derivation, and older project compatibility verified on Windows. |
| 3.1B - Local plate solve settings | Not started | Gaia DR3 and ASTAP paths persisted and validated with actionable diagnostics. |
| 3.1C - Desktop plate solve job | Not started | Packaged Windows workflow solves eligible panels, attaches reusable WCS, and handles cancellation and retry. |
| 3.5A - Phase 2 review | Not started | Criteria mapped to current evidence, baseline rerun, and gaps and added thresholds recorded. |
| 3.5B - Revision | Not started | Acceptance findings resolved with focused regression evidence. |
| 3.5C - Verification | Not started | Numerical and packaged CLI results meet the Phase 2 criteria before Phase 4 starts. |
| 4A - Headless project automation | Not started | Windows CLI project creation, validation and export, machine-readable results, and scripted batch and cancellation checks. |
| 4B - Large mosaics and improved blends | Not started | Budgeted rendering of 12 FITS and TIFF panels at 6000 × 4000, including a mixed scene, incremental export, tile/halo correctness, and measured improvement for any optional multiband blend. |
| 4C - Desktop terminal panel | Not started | Shared AstroMosaic commands, live progress, history, and cancellation verified in a responsive desktop panel. |
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

## Entry Template

Copy this format into a new entry immediately above this template, preserving chronological order:

```markdown
### YYYY-MM-DD - Phase N - Status: short outcome

- **Changed:** Brief summary of useful work, or the attempted step if incomplete.
- **Verified:** Relevant commands/checks and their result; identify unavailable checks.
- **Related:** Question IDs, ADRs, or evidence paths; use "None" when appropriate.
- **Next:** One concrete next step and any blocker that affects it.
```
