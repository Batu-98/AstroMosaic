# Language Requirement

**The language of this document shall be English.** All requirements, explanations, architectural decisions, tables, and subsequent revisions must remain in English unless the project owner explicitly changes this requirement. Preserve official names, API identifiers, mathematical notation, and source references as appropriate. Application localization is a separate decision.

# AstroMosaic v1: Python-First Architecture and Implementation Plan

- **Revision:** 3.12
- **Date:** November 19, 2026
- **Status:** Proposed implementation baseline following local source inspection
- **Initial target:** Windows 11 x64
- **Deferred platform support:** Linux and macOS may be added later. See [ADR-0003](docs/adr/0003-windows-first-platform-scope.md).
- **Project directory:** `C:\Software\AstroMosaic_v1`
- **Reference repository inspected:** `C:\Software\setiastrosuitepro-main`
- **Decision convention:** Infrastructure choices are ranked as **First preference** and **Second preference**. An alternative is activated by evidence or a product decision, not implemented automatically alongside the first choice.

## 1. Executive Decision

Use Python for application orchestration, domain models, numerical workflows, project persistence, and the desktop interface. Use established compiled scientific libraries through Python APIs for heavy array operations. Keep GPU shader code and narrowly scoped compiled kernels available where measurements justify them.

The first-preference stack is **Python + PySide6 + NumPy + SciPy + Astropy + SEP + reproject**. Start with a CPU reference renderer and a separate interactive preview backend. Add Numba selectively after profiling. Do not make C#, a custom C++ engine, CUDA, or a machine-learning runtime a prerequisite for the first release.

The Seti Astro Suite Pro source supports the feasibility of this approach: it contains Python-based WCS/SIP reprojection, mosaicking, numerical acceleration, image-cache infrastructure, solver adapters, and desktop UI code. The same source also illustrates complexity that AstroMosaic should avoid: UI-coupled processing, broad dependencies, runtime-specific acceleration workarounds, and tiled coordinate calculations that still allocate full-canvas arrays.

This is a new focused application design. The review does not establish that the reference application meets AstroMosaic's performance or photometric requirements.

## 2. What Was Inspected and What Was Established

### 2.1 Review Scope

The review was a **static inspection of the local snapshot**, including dependency declarations, selected mosaic and solver implementations, preview/cache code, acceleration/bootstrap code, entry points, and relevant regression tests. The application and its tests were not executed. Runtime performance, graphics compatibility, and packaging success were not independently measured.

The local `pyproject.toml` declares version **1.24.3**, Python `>=3.10,<3.15`, and GPL-3.0 metadata. Some individual source files declare GPL v3 or later. These are observations about the supplied snapshot, not claims about the newest upstream release.

Source anchors below are relative to the inspected repository root and use line numbers from this snapshot. They may move in later versions.

### 2.2 Findings and Resulting Decisions

| ID | Observed evidence | Consequence for AstroMosaic |
| --- | --- | --- |
| R1 | `pyproject.toml` lists PyQt6, NumPy, SciPy, Astropy, SEP, reproject, Numba, OpenCV, and many additional astronomy/AI packages. | A Python scientific desktop stack is a relevant precedent. Start with a substantially smaller dependency set. The reference uses **PyQt6**, not PySide6. |
| R2 | `src/setiastro/saspro/mosaic_master.py:2455`, `_warp_via_wcs_remap_exact`, maps destination pixels through celestial coordinates into source pixels, respects SIP, and validates a forward round trip. | Retain full WCS transformations, footprint bounds, and convergence checks. A global homography is not a general replacement for SIP-aware geometry. |
| R3 | The same function allocates full destination image and optional mask arrays with `np.zeros` before iterating over coordinate tiles. Other accumulators use `smart_zeros`. | Coordinate tiling alone does not bound total memory. Organize final rendering around output tiles and never require a full reprojected canvas per source panel. |
| R4 | `mosaic_master.py:1202`, `_valid_data_mask`, derives coverage partly from nonzero intensities. | Carry explicit validity masks. Legitimate zero or negative values must remain usable data. Treat zero-filled legacy images as a separately declared import convention. |
| R5 | `PolyGradientRemoval.process` contains clipping to `[0,1]`; `MosaicMasterDialog` includes preprocessing, alignment, blending, solver access, and UI event handling. | Keep scientific pixels unclipped and immutable. Place processing in headless modules instead of dialog methods. Display/legacy preprocessing semantics are not the new engine's data contract. |
| R6 | `src/setiastro/saspro/imageops/tiled_canvas.py` implements a CPU/QPainter preview with visible tiles, mip selection, an LRU budget, and a small proxy image. | Adopt the cache and progressive-preview concepts. This is evidence for a useful CPU fallback, not evidence of a real-time spherical GPU viewport. |
| R7 | `src/setiastro/saspro/plate_solver.py` includes local ASTAP, local solve-field, online astrometry, and in-house Gaia paths. `gaia_blind_solver.py` produces seeds for later refinement. | Reuse valid WCS first. The panel path in this snapshot uses in-house Gaia blind solving followed by the Astrometry.net web API, while the general solver also includes ASTAP and local solve-field. Use the local Gaia and ASTAP sequence defined in Section 6.3. |
| R8 | `src/setiastro/saspro/plate_solve_cli.py:66`, `_ensure_qapp`, creates a Qt application for part of the CLI workflow. | AstroMosaic's processing CLI must run without constructing a QApplication or importing UI modules. |
| R9 | `src/setiastro/saspro/__main__.py` invokes `multiprocessing.freeze_support()` before GUI routing. | Design frozen-process startup explicitly. Background workers must not reopen the GUI or enter single-instance routing. |
| R10 | `src/setiastro/saspro/numba_bootstrap.py` implements threading-layer selection and documents a project-specific Windows/Python compatibility issue. | Validate a pinned Python/Numba combination, warm up outside user interactions, and retain non-JIT execution. Do not generalize its comments into a universal Numba defect. |
| R11 | `src/setiastro/saspro/gpu_warp.py` resolves optional Torch devices, supplies fallback behavior, and documents CPU/GPU numerical differences. | Keep compute acceleration optional and observable. Do not import Torch merely to provide a preview canvas. Define numerical equivalence tolerances before acceleration. |
| R12 | `tests/test_mosaic_solved_wcs.py` checks stale SIP removal; `test_viewport_render.py` checks display-sized output; memory tests cover read-only maps and project-save cache behavior. | Add these failure categories to our own independently written tests. Their presence is useful design evidence; their pass status was not verified. |

### 2.3 Patterns to Adopt and Patterns to Avoid

Adopt explicit solver adapters, WCS round-trip checks, display-sized previews, cache eviction, typed processing results, CPU fallback, and regression tests for geometry and memory behavior.

Avoid mixing Qt dialogs with numerical algorithms, treating missing pixels as a brightness value, modifying source FITS headers during ordinary solving, building full-canvas intermediates per panel, and assuming a successful import proves cross-platform compatibility.

The repository includes a GPL license. This plan incorporates architectural observations and proposes new implementation; it does not copy source code. Any later code reuse must be an explicit decision with the relevant file and dependency licenses recorded. PySide6 and PyQt6 also have different licensing options; the project should select the intended distribution model before packaging. [E1][E2]

## 3. Product Scope and Invariants

### 3.1 First End-to-End Slice

Accept calibrated, integrated, unstretched monochrome FITS panels from one filter, use or solve their WCS, align them into a Gnomonic output frame, perform conservative relative normalization, and export a linear float32 FITS mosaic.

Both FITS and TIFF are primary, first-class user workflows. FITS serves as the primary astronomical workflow with native celestial WCS, standard 32-bit floating-point data, and header preservation. Linear TIFF serves as the primary processing and post-processing interchange workflow for mono and RGB data, preserving sample values without clipping and using external WCS and coverage sidecars or embedded tags. Both formats receive first-class support across headless processing, desktop projects, and mosaic export. Camera RAW is deferred and may be added as an import-only workflow when needed. Additional projections, XISF, and per-band outputs follow as needed. See [ADR-0004](docs/adr/0004-open-source-image-workflow.md) and [ADR-0006](docs/adr/0006-dual-fits-and-tiff-workflow.md).

The Phase 1 reference uses sky-only panels. The Phase 3 desktop workflow also supports panels that contain both sky and foreground. It stitches the sky and foreground in their own coordinate frames and offers a separate visual composite with automatic placement and user controls. See [ADR-0007](docs/adr/0007-sky-and-foreground-mosaics.md).

Initial FITS reference exclusions include individual-exposure calibration and stacking, Bayer demosaicing, acquisition control, AI enhancement, and a custom blind plate solver. If camera RAW is scheduled later, evaluate linear decoding and any required demosaicing for the selected cameras.

### 3.2 Invariants

1. The initial engine and CLI target Windows 11 x64. Processing remains independent of Qt, the GPU, and Windows-specific services so additional platforms can be supported later.
2. Input files are immutable by default. Solved WCS and corrections are project metadata until export.
3. Float32 pixels retain negative values, valid zeros, and values above one.
4. Every stage propagates explicit validity/coverage independently of intensity.
5. Display stretch never changes processing pixels.
6. Preview and final output share geometry definitions and project state.
7. Final reprojection samples original pixels once using composed transformations.
8. RAM, VRAM, worker concurrency, and disk cache have explicit budgets.
9. Background matching does not claim to recover an unknown absolute sky background.
10. Candidate dependencies and performance targets are validated, not assumed from documentation or reference-code comments.
11. Mixed panels contribute only their respective masked regions to sky and foreground stitching. Keep the stitched layers independently exportable and save visual composition edits separately from the sky WCS and scientific pixels.

## 4. Ranked Infrastructure Decisions

| Area | First preference | Second preference | Reason and alternative trigger |
| --- | --- | --- | --- |
| Runtime | CPython 3.13 as the initial compatibility candidate | CPython 3.12 if required by a critical compiled dependency | Lock one tested minor version initially. Confirm wheels and bundling on the initial target, and verify JIT compatibility if introduced; do not adopt the reference project's entire version range. |
| Desktop binding | **PySide6** | **PyQt6** | Both expose Qt; PySide6 is the chosen baseline. PyQt6 becomes an alternative for a concrete compatibility or reuse decision with appropriate licensing. Never load both bindings into one application. [E1][E2] |
| UI toolkit style | Qt Widgets with a dedicated image viewport | Qt Quick/QML if interaction requirements justify it | Widgets simplify the initial scientific desktop workflow. QML would introduce another authored language and a different rendering integration. |
| Array operations | NumPy | Focused Numba kernels | Use vectorized compiled operations first. Add JIT only where profiling shows a benefit or where it avoids expensive intermediate arrays. |
| Fitting and sparse algebra | SciPy optimization/sparse routines | A small compiled extension for a demonstrated unmet requirement | Keep robust fitting and model logic in Python; avoid custom native numerical infrastructure initially. |
| FITS and WCS | Astropy | `fitsio` for selected FITS I/O bottlenecks while retaining Astropy WCS | Validate scaling, endianness, HDUs, partial reads, and resource ownership. A replacement must pass the same data-contract tests. |
| Source detection and aperture photometry | SEP | Photutils | SEP covers core array-based source measurements. Use Photutils if a required measurement/model or validation case warrants it. [E3] |
| Reprojection baseline | `reproject` through a small adapter | A custom output-tile mapper using Astropy WCS and compiled sampling primitives | Start with an established reference. Build specialized sampling only for missing controls or measured bottlenecks. `reproject_exact` refers to a particular area-overlap algorithm; do not confuse it with the reference repository's function named `remap_exact`. [E4] |
| Offline plate solving | Validated existing WCS, then local ASTAP with hinted/FOV recovery, then local Gaia DR3 with hinted/scale-free recovery | Report why the qualified local chain could not publish a WCS | Phase 3.6 implements ASTAP priority, automatic catalog selection, at least 15 matches, bounded low-order SIP validation and a total solve deadline. [Implementation evidence](docs/phase-36-results.md) [E5] |
| Preview renderer | QOpenGLWidget with a small shader pipeline and Python-managed resources | CPU tiled raster preview with a low-resolution reprojected proxy | Preserve responsive projection/framing as a GPU milestone. CPU fallback is functional but may update projection changes at lower resolution or frequency. [E7] |
| Additional OpenGL bindings | Qt-provided OpenGL wrappers where sufficient | PyOpenGL for missing calls after an integration test | Minimize packages and verify context ownership; do not add multiple rendering frameworks speculatively. |
| Final-image compute | CPU kernels through NumPy/SciPy/reproject | Optional accelerated backend after profiling | A GPU is never required for valid export. Choose a compute backend only after device coverage and precision tests; no default CUDA/Torch/ONNX dependency. |
| Baseline blend | Normalized quality-weighted linear blend | Custom masked float32 multiband blend after its quality gate | The first choice supplies a trustworthy reference. Promote multiband blending only when it improves seams while meeting flux/profile tolerances. |
| Working storage | Tiled reads plus `.npy` memory-mapped working arrays and explicit ownership | Zarr if chunk compression or storage access patterns justify it | Keep the first storage implementation small. Memory mapping complements scheduling; it does not eliminate allocation or resident-memory accounting. |
| Scheduling | Bounded thread workers for native operations and I/O | Spawn-based process workers for measured Python-bound or isolation needs | Do not layer process pools, BLAS threads, and Numba parallelism without a common concurrency budget. |
| Project format | Versioned JSON plus external source references and rebuildable cache | SQLite when transactional metadata or scale requires it | Save compact reproducible state; avoid embedding every pixel and undo image in the project file. |
| Dependency management | Poetry with a committed lock and controlled updates | `pyproject.toml` with a generated, platform-tested requirements lock workflow | The reference shows Poetry plus an exported requirements file. Maintain one authoritative dependency definition. Do not copy its broad dependency manifest. |
| Desktop bundling | PyInstaller in one-directory mode for the first distribution experiment | `pyside6-deploy` if it yields a better validated bundle | Start packaging early. Test native imports, Qt plugins, worker spawning, and external solver execution on the initial Windows target. Validate JIT cache paths if JIT is introduced. [E8][E9] |
| Code quality | Type annotations, a static type checker, linting, pytest, and small reference fixtures | Additional specialized tools only for identified gaps | Keep the default toolchain modest and automate the actual numerical and integration risks. |

### 4.1 Relationship to the Earlier .NET Plan

Python/PySide6 replaces .NET/Avalonia as the active baseline. Do not maintain two complete GUI stacks during v1.

If a later recorded decision returns to a .NET frontend, the previously requested ranking remains: **First preference: Avalonia; Second preference: WPF**. WPF is an optional Windows-only frontend and would complicate later Linux and macOS support. It is not a drop-in alternative to PySide6. Any such migration requires an explicit engine-interface decision.

### 4.2 Minimal Dependencies

The engine initially depends on NumPy, SciPy, Astropy, SEP, and reproject. The desktop extra adds PySide6. The development group adds testing, linting, typing, and packaging tools.

Keep optional acceleration and extra format dependencies out of the initial processing stack until their planned stages. Phase 3A uses tifffile and imagecodecs for [linear TIFF interoperability](docs/phase-3a.md). Revisit camera RAW when camera support is requested. Treat transitive compiled libraries as part of the package compatibility matrix even when our authored code remains Python.

AstroMosaic will be distributed as open source and will use open-source libraries, codecs, and solver executables for supported workflows. Review exact licenses and bundled notices before redistribution. Track catalog and fixture data terms separately. Keep unrelated reference-suite dependencies outside the initial application.

## 5. Architecture and Module Boundaries

```text
AstroMosaic_v1/
  pyproject.toml
  poetry.lock
  src/astromosaic/
    core/             # Typed domain models, units, masks, exceptions
    geometry/         # WCS adapters, projections, footprints, inverse mapping
    io/               # FITS reference, TIFF, and camera RAW adapters
    storage/          # Tile access, memmaps, cache ownership, manifests
    astrometry/       # Star catalogs, solver adapters, global registration
    photometry/       # Relative gain and constrained background models
    resampling/       # Reprojection adapters, sampling and coverage
    blending/         # Weighted reference and optional multiband engine
    pipeline/         # Job graph, budgets, progress, cancellation
    display/          # Display statistics, STF, preview specifications
    ui/               # PySide6 windows, controllers, models
      viewport/       # GPU rendering and CPU fallback
    cli/              # Headless entry points
  shaders/            # Small GPU-only programs
  tests/
    numerical/
    integration/
    portability/
    fixtures/
  benchmarks/
  packaging/
  docs/adr/
```

Dependency direction is `UI/CLI -> pipeline -> processing modules -> core/contracts`. Engine modules never import `ui`, PySide6, PyQt6, or QApplication. Importing a module must not initialize GPU devices, download catalogs, or start a worker pool.

Use ordinary functions, dataclasses, and narrow protocols. Avoid a plugin platform or generic distributed task framework before the application needs one.

### 5.1 Essential Contracts

| Contract | Required content or behavior |
| --- | --- |
| `PanelDescriptor` | Source fingerprint, dimensions, channel layout, filter, units/scaling, WCS provenance, mask provenance. |
| `TileSource` | Read a requested region and halo into bounded buffers; expose validity; close resources explicitly. |
| `GeometrySolution` | Full transformation, coordinate conventions, fit diagnostics, version, forward/inverse validity. |
| `PhotometricSolution` | Relative gain, additive surface coefficients, reference group, diagnostics, model domain. |
| `RenderSpec` | Output geometry with celestial WCS or an image-space mapping, dimensions, scale, projection, crop, kernel, blend mode, and resource budgets. |
| `JobContext` | Cancellation token, progress callback, memory reservation, temporary-file owner, structured logging. |
| `TileResult` | Float32 pixels, validity/coverage, weights where applicable, and processing diagnostics. |
| `PanelContent` | Automatic foreground classification, manual override, and versioned sky and foreground masks in source pixel coordinates. Combine content masks with source validity at sampling time. |
| `CompositionSpec` | Layer identities and transforms into the composition frame, reference panel or manual anchors, placement and crop, requested overlap, seam settings, and coverage. |

GUI communication uses small progress/result descriptors and signals. Do not pass mutable whole-image arrays between the UI and several workers without ownership rules. Create QPixmap and manipulate widgets on the GUI thread.

### 5.2 Local Automation for Agents and Scripts

Use the existing Qt-free CLI as the local automation interface. Make commands discoverable with `--help` and identify the installed release with `--version`. Keep existing invocations compatible. Document exit codes and provide an opt-in, versioned UTF-8 JSON format with one final result on stdout and newline-delimited progress and diagnostic events on stderr. Automation commands run without interactive prompts.

Use the saved `.astromosaic` manifest as the reusable job description. Provide commands to create a sky project from panel paths and render settings, check a saved project's inputs and settings before rendering, and export a selected sky, foreground, or composite layer from saved state. Project jobs use the same headless validation, renderer, resource budgets, and cancellation as desktop jobs. Require an explicit export destination, preserve source images, and publish completed outputs atomically. Provide PowerShell and Python examples that call the CLI to run projects in batch and read their results.

Open the desktop terminal panel at startup. Show AstroMosaic command output and concise summaries of desktop operations in the same bounded session log, including while the panel is hidden. Provide command history, progress, and cancellation. Run jobs off the UI thread. [Automation decision](docs/adr/0016-local-automation.md) · [Desktop command worker](docs/adr/0019-desktop-command-worker.md)

## 6. Processing Pipeline

### 6.1 Ingestion and Linear Data

Read metadata before pixels. Accept mono FITS first, including supported integer storage converted according to FITS scaling. A 32-bit format alone does not prove that pixels are unstretched.

Use float32 for image buffers and float64 for celestial geometry, fitting, and sensitive reductions. Preserve `BSCALE`, `BZERO`, units when known, channel layout, and header provenance. Never normalize every panel independently into `[0,1]` without a recorded reversible scale transformation.

Track invalid pixels, saturation, and excluded regions explicitly. For legacy zero-filled mosaics, let an import rule describe zero-as-no-data; do not apply it to all scientific inputs. FITS masks/coverage extensions and documented sidecars take precedence over intensity heuristics.

### 6.2 Display and Preview

Compute robust statistics on valid pixels. Apply a display-only midtone transfer function after mapping display black/white points:

```text
MTF(x, m) = ((m - 1) * x) / (((2 * m - 1) * x) - m)
```

Restrict `m` to a stable interval inside `(0,1)` and handle endpoints explicitly. Display clipping is allowed; processing clipping is not implied. Keep RGB channel-linking policy explicit.

Use a low-resolution proxy followed by visible tiles or GPU mip levels. Cache invalidation depends on source identity, geometry, correction parameters, and display settings. A display-stretch change must not rerun plate solving or export-quality reprojection.

The CPU fallback supports pan/zoom efficiently on cached imagery. Reframing into a new sky projection can require a new coarse preview; do not equate cached image panning with interactive spherical reprojection.

New desktop sky previews can fit a temporary ICRS grid to the effective WCS of the selected panels. Adopting the fit for export is an explicit project edit. A desktop visual sky preview can linearize recognized sRGB TIFF tiles before resampling. Scientific rendering keeps its linear-input and brightness requirements. [Automatic sky preview decision](docs/adr/0025-automatic-sky-preview.md)

### 6.3 WCS Reuse, Solving, and Registration

The planned Phase 3.6 policy tries the following local steps in order and stops at the first solution that passes the applicable quality and geometry checks. The existing Phase 2/3.5 implementation and evidence remain Gaia-first until this revision is implemented and verified.

1. Validate and reuse the effective celestial WCS, including a source/mask-bound project sidecar when selected. Distinguish geometry-only legacy reuse from measured catalog validation; provide an explicit revalidation path.
2. Run the installed local ASTAP executable with usable pointing and vertical field-of-view hints. Use Automatic catalog selection or a preserved manual override. Skip this attempt when pointing is absent.
3. Run bounded blind ASTAP recovery with the untrusted pointing and FOV removed. Reconsider the automatic catalog selection when the FOV assumption changes. Do not repeat an identical blind attempt.
4. Solve against the local Gaia DR3 catalog through Seiza, using pointing and scale when usable and an indexed scale-free blind recovery when available. Discard a failed scale constraint rather than retaining its narrow search interval. Keep the supported broad scale interval explicit.

[Phase 3.6A](docs/phase-36a.md) froze the planned broad recovery interval at 0.1–120 arcsec/pixel after the owner camera TIFFs demonstrated scales outside the earlier 0.1–20 wrapper range. Its native Auto/SIP and local validation probes are complete; dispatch and enforcement remain subsequent work. The frozen fixture/policy definitions are in the [reference manifest](tests/fixtures/plate_solve_v36.json).

Astrometry.net is outside the chain in both its web and local forms. If the chain is exhausted, report the sky region as unsolved. Respect cancellation and one monotonic panel deadline covering preparation, all attempts, validation and publication. Preserve per-attempt caps within that total and support an optional multi-panel job budget. Use headless adapters with ordered diagnostics, actual catalog identities and separately stored solved WCS. Preserve original source images. In mixed panels, apply the effective sky mask to star extraction and staged solver input. Foreground registration runs independently. [Original offline decision](docs/adr/0005-offline-solver-chain.md) · [Phase 3.6 priority decision](docs/adr/0017-astap-first-validated-solving.md)

New qualified ASTAP and Gaia results require at least 15 distinct accepted image/catalog matches, finite quality metrics and valid geometry. The proposed RMS ceiling is `max(3 arcsec, 2 * s)`, where `s` is the smaller local X/Y source-pixel scale at the solved center. Retain Gaia's false-match probability ceiling of 0.001. Freeze residual definitions, thresholds and a genuine ASTAP-only quality-evidence path in Phase 3.6A; detected stars or a success status are not equivalent to verified matches. Keep the previous real-field regression envelopes. Existing geometrically valid WCS without those metrics remains explicitly geometry-only rather than being silently recertified.

Evaluate TAN and supported SIP degree 2/3 only with sufficient star count and spatial coverage. Promote distortion terms with independent spatial validation and true held-out evidence where fitting is under application control; label native in-fit statistics accurately. Check supported field edges, parity, inverse stability and preview/export consistency. The [Phase 3.6 detailed plan](docs/phase-36.md) defines sample floors, candidate numerical targets, total-budget defaults, capability checks and stage acceptance.

Quantify the full source field with bounded spatial diagnostics: global linear skew/scale/rotation, nonlinear displacement relative to a defined TAN reference, local scale/shear, and measured regional star residuals. Start from a 9 × 9 model-sampling grid and record regional support. Keep model predictions separate from observed errors; regions without adequate stars or outside the sky mask cannot be reported as having measured zero distortion or verified accuracy. The detailed Phase 3.6 plan specifies the map, support labels and acceptance cases.

Extract stars with local noise/background estimates, reject saturation and blends, and estimate centroids with an explicit method. HFD is a profile diagnostic, not itself a centroid estimator.

Build an overlap graph from sampled full-WCS boundaries. Match stars through initial WCS predictions and spatial indexing. Refine globally with robust weights and an external/reference anchor. Add low-order SIP terms only when star count and spatial coverage support them. Report held-out relative alignment errors separately from catalog errors.

TPS stays outside v1. The Windows Phase 2 reference uses Seiza for local Gaia DR3 and fits relative translations on the anchored output grid. [Gaia backend decision](docs/adr/0010-seiza-gaia-backend.md) · [Phase 2 evidence](docs/phase-2.md)

### 6.4 Relative Gain and Background Correction

For panel `i`:

```text
J_i(x, y) = m_i * I_i(x, y) + S_i(x, y)
```

Estimate `m_i` from background-subtracted aperture fluxes of unsaturated common stars within compatible filters/channels. Fit overlap background differences after scales are constrained. Begin with offsets, then planes; promote model complexity only when held-out data justify it.

Represent each surface in normalized source coordinates. Evaluate paired samples at the source coordinates corresponding to the same sky position. Solve corrections jointly across the overlap graph with reference constraints, regularization, and confidence weighting. Fix reference gain and background per component and remove any remaining null modes of the chosen model.

Mask stars and their relevant wings, defects, and unreliable samples. Extended nebulosity is not automatically separable from sky background; protect it with conservative models, injected-signal tests, exclusion regions, and correction-map inspection.

Disconnected components cannot be relatively calibrated by overlap alone. A shared unknown absolute background remains undetermined. Report both limitations rather than forcing an arbitrary smooth-looking solution.

### 6.5 Geometry and Resampling

The shared transformation chain is:

```text
Output tile pixels -> output WCS -> sky positions
                   -> inverse source WCS/distortion -> source samples
```

Handle longitude wrap, pixel-origin conventions, reference frames, projection singularities, and inverse nonconvergence. Validate coordinate round trips and invalidate failed samples. A bounded output tile can map to a curved or disconnected source region; determine a conservative source footprint and subdivide when necessary.

Start with Gnomonic. Add Stereographic for wider fields, followed by Equirectangular and optional Mercator. Mercator does not include the poles; Stereographic preserves local angles but not constant scale.

Use reproject as the first reference implementation and evaluate its block/output-array options against our memory contract. Wrapping a function in a Python tile loop is insufficient if it materializes full source/output arrays internally. [E4]

The Phase 1 FITS renderer uses the bounded source-window mapper, with reproject retained for independent small-array comparisons. [ADR-0008](docs/adr/0008-bounded-fits-sampling.md)

Declare whether values represent surface brightness or integrated flux per pixel. Apply pixel-area handling appropriate to that convention and verify flux through scale/projection changes. No interpolation kernel alone establishes photometric fidelity. [E10]

If a specialized mapper becomes necessary, benchmark cubic and Lanczos candidates against stellar centroid, FWHM, ringing, aperture flux, and runtime. Do not hard-code a Lanczos-3 promise when a selected backend only implements Lanczos-4.

### 6.6 Blending and Export

First implement normalized weighted linear blending with validity and available quality/noise information. Keep it as the baseline for every later blend mode.

Add masked float32 Laplacian-pyramid blending only after registration and background matching pass their gates. Derive pyramid depth and seam width from output scale and overlap geometry. Ensure mask-aware filters do not blend invalid fill into real data. Narrow seams cannot repair geometric errors or arbitrary PSF differences.

OpenCV's ready-made multiband blender is not assumed to accept float32 mono/RGB data. If used for primitives, validate each operation's dtype and channel behavior. [E11]

Export a linear float32 FITS image first, with output-derived WCS, coverage, and processing history. Reopen with an independent reader. Do not preserve stale input SIP coefficients after producing a new output geometry. Record integer/stretched export conversions explicitly. Add format-specific celestial sidecars where WCS interoperability is absent.

### 6.7 Mixed Sky and Foreground Panels

#### Detection and editable masks

Run a lightweight foreground check on each imported thumbnail. Store the effective foreground tag, distinguish uncertain suggestions, and let the user mark missed panels or clear false positives. A manual tag takes precedence on subsequent runs. Run a separate, cancellable local segmentation job on tagged panels to propose a sky mask. Show the mask over the image and let the user edit it or create it manually. Use a reduced-resolution preview and refine boundaries only as needed within the memory budget.

Derive sky and foreground masks from the same segmentation and apply manual corrections to both consistently. Keep content selection separate from the input validity mask. Register each branch using only its selected valid pixels. Leave unclassified boundary pixels out of the fits until their masks are resolved. Save manual edits with the project and update affected tiles and derived results when the effective mask changes.

#### Independent stitching

- **Sky:** Use the existing celestial WCS and offline solver chain, then apply sky-only registration, photometric matching, reprojection, and blending. A sky-only panel contributes directly to this branch.
- **Foreground:** Use image-space registration based on matching overlapping terrestrial features. Use the foreground mask when estimating transforms and blending. This branch uses no plate solve and can still use a panel whose sky solution failed. Report weak or disconnected overlaps so they can be corrected before final rendering.

The Phase 3E foreground baseline fits translations. [Phase 7](docs/phase-7.md) compares masked terrain control-point fits with that baseline, starting with manual correspondences and similarity geometry. Adopt camera rotation or shared lens terms where real held-out observations support the added parameters. [Proposed foreground geometry decision](docs/adr/0023-terrain-control-point-registration.md)

Keep the coordinate transforms and fit diagnostics for each branch. Reuse the headless tile scheduler, validity-aware sampling, and blend primitives wherever their contracts apply. Keep separate stitched layers and coverage masks for preview and export.

#### Final composition

Propose alignment between the stitched layers by mapping both through a shared mixed reference panel where available. Use the resulting horizon as a starting seam. When the reference mapping is weak or missing, present manual alignment controls. Let the user adjust layer position, rotation and scale, the seam, and a reversible sky-edge crop. Store these adjustments in the composition project state. A reference exposure provides a placement at its capture time. A physical horizon transform would additionally depend on observer location and observation time. [Astropy horizontal coordinates](https://docs.astropy.org/en/stable/api/astropy.coordinates.AltAz.html)

Offer the requested overlap as a percentage of the shorter layer's height in the composition. Show the resulting seam width and where both masks actually provide coverage. Limit feathering to valid common coverage and keep any remaining gaps visible as uncovered. Preview and final export use the same placement, crop, seam, and mask state. A sky-only export keeps its own celestial WCS. A visual composite stores both layers' provenance and identifies where each contributes.

Consider generative fill later as an explicitly selected, local, open-source option for uncovered seam gaps in the visual composite. If implemented, mark generated pixels with a separate mask and record their provenance. Scientific layer exports contain observed data only.

## 7. Memory and Scheduling Model

### 7.1 Output-Tile Ownership

For each output tile:

1. Select only panels whose full footprints intersect it.
2. Reserve memory for coordinate arrays, source regions, masks, accumulators, and filter halos.
3. Read the necessary source regions into reusable buffers.
4. Reproject and accumulate panel contributions into the tile.
5. Finalize the tile and write it incrementally.
6. Release buffers or return them to a bounded pool.

Never allocate one entire output-canvas image per panel as a prerequisite for blending. Multi-resolution blending additionally requires coordinated pyramid levels, sufficient halos, and sometimes a disk-backed coarse global level; use a separate validated scheduling path for it.

### 7.2 Working-Set Accounting

The Windows reference workload is 12 panels at 6000 x 4000 pixels each, benchmarked across both FITS and TIFF formats. Their decoded float32 source pixels alone occupy **1.152 GB mono** or **3.456 GB RGB** before masks, output, caches, and work buffers. Use the RGB case to size and verify resource limits. A Python view may be cheap, but arithmetic, broadcasting outputs, advanced indexing, dtype conversion, and serialization can create additional full-sized arrays.

Budget resident arrays, memmap-backed dirty pages, source caches, worker queues, and GPU copies. A memmap is not a hard RAM limit. Prefer read-only input maps, explicit lifetimes, bounded queue depths, and output buffers reused through supported `out=` operations.

For non-tile-readable or compressed sources, plan an explicit conversion step into working storage and include that step in memory/disk estimates. Do not hide an unbounded full-image decode inside `read_tile`.

### 7.3 Parallelism and Responsiveness

Use bounded workers for native operations that release the GIL, and processes only for measured Python-bound work or isolation. NumPy releases the GIL for many operations, but sharing mutable arrays requires deliberate synchronization. [E12]

Pass file/tile descriptors to process workers rather than repeatedly serializing complete images. Use spawn-safe module entry points and frozen-build support. Coordinate worker count with BLAS/OpenMP/Numba thread limits to avoid oversubscription.

Long jobs report progress, support cancellation at tile boundaries, and leave temporary output recoverable or safely removable. Do not use repeated `QApplication.processEvents()` as the engine's scheduling mechanism.

## 8. Acceleration and Cross-Platform Strategy

Profile before adding an acceleration dependency. Numba is suitable for isolated numerical loops, but startup compilation, threading layers, cache permissions, and frozen applications need their own validation. Begin with deterministic non-parallel kernels when sufficient and avoid relaxed floating-point transformations in precision-sensitive code until their error is measured. [E13]

GPU preview and GPU scientific compute are different subsystems. A GLSL preview does not require an AI framework. Build an early PySide/OpenGL experiment on Windows and verify float textures, context recreation, shader results, high-DPI behavior, and fallback.

The proposed 60 FPS interaction target is conditional on a defined device, preview resolution, viewport size, and panel count. Measure warm and cold-cache frame-time percentiles. Keep reduced-detail interaction available; do not require export-quality rendering every frame.

Platform-specific paths, application data directories, external process launch flags, and native package resolution belong in adapters. Preserve Unicode paths and case-sensitive filesystem behavior. Release support is defined per OS version and CPU architecture after actual installation tests.

## 9. Persistence and Diagnostics

Save a versioned project manifest containing source fingerprints/paths, WCS solutions, solver/catalog identifiers, masks, fit parameters, output geometry, algorithm versions, and user overrides. Cache files are derived, relocatable, and rebuildable.

For mixed-panel jobs, persist foreground tag overrides, editable source masks, the two stitch solutions, and final composition state. Keep the mask revision in cache keys for derived solves and tiles.

Represent edits as parameter/state changes where possible instead of storing complete image copies for every undo step. Save atomically and provide source relinking. Track dirty state separately from cache completeness.

Record selected backend, fallback reason, dtype conversions, failed coordinate counts, fit quality, peak resource usage, and version information in a structured diagnostic report. Do not silently present an accelerated run when the CPU path actually ran.

## 10. Revised Milestones

| Phase | Deliverable | Exit gate |
| --- | --- | --- |
| 0: Compatibility and scope | Small locked environment, initial fixtures, solver adapter experiment, PySide float-texture test, and packaged skeleton | Start and run a small processing job and the packaged skeleton on Windows 11 x64. Establish the Python minor version and package compatibility on that target. |
| 1: Headless reference | FITS tile access, masks, WCS reuse, Gnomonic reprojection, weighted blending, FITS export | Two-panel FITS output with correct geometry and values, independently reopened, and a Qt-free CLI. Then verify linear mono and RGB TIFF input and output before Phase 3 desktop acceptance. |
| 2: Robust astronomy engine | Offline Gaia/ASTAP chain, masked sky processing, overlap graph, robust global registration, stellar scale, offset/plane corrections | Verify WCS reuse, fallback order, cancellation, and exhausted-chain diagnostics. Pass held-out alignment and injected-signal gates, including a mixed fixture with supplied masks, and report weak or disconnected cases. |
| 3: Desktop workflow | Six delivery stages covering TIFF interoperability, project and job management, preview and export, sky masks, foreground composition, and Windows acceptance. | Meet the [Phase 3A–3F gates](#101-phase-3-delivery-stages). |
| 3.1: Desktop plate solving | Per-panel WCS status and optical hints, local catalog settings, and a desktop solve job | Pass the [Phase 3.1A–3.1C checks](#phase-31-desktop-plate-solving) before starting Phase 3.5. |
| 3.5: Astronomy engine revalidation | Review Phase 2 evidence on the current engine, resolve findings, and verify the results | Pass the [Phase 3.5A–3.5C checks](#phase-35-astronomy-engine-revalidation) before starting Phase 3.6. |
| 3.6: Plate solve reliability | ASTAP priority and automatic catalogs, common match/RMS evidence, bad-scale recovery, supported SIP/edge validation and a total solve budget | Pass the [Phase 3.6A–3.6F gates](#phase-36-plate-solve-reliability), including ASTAP-only quality evidence and Windows CLI/desktop migration. |
| 4: Automation, large mosaics, and desktop terminal | Scriptable project commands, budgeted large renders and improved blends, and a desktop command panel | Meet the [Phase 4A–4C gates](#102-phase-4-delivery-stages). |
| 5: Extended formats and channels | Optional XISF, projections, and per-band outputs | Format, geometry, mask, unit, packaging, and channel-consistency checks pass for each added workflow. |
| 6: Real-observation reliability and Windows acceptance | Real-data baseline, foreground and plate-solve diagnostics, ZEA preview reliability, and native Windows lifecycle | Pass the [Phase 6A–6E gates](#104-phase-6-delivery-stages) using exclusively real observational data, with independently reopened exports and clean Windows 11 x64 evidence for the intended build. |
| 7: Terrain panorama registration | Ground control points, an anchored robust fit, and a verified camera model for real wide-angle captures | Pass the [Phase 7A–7F gates](#105-phase-7-delivery-stages). Demonstrate improvement on previously unsupported real terrain and retain the legacy, negative and sky regression checks. |
| 8: Photo export and corrections | Full-resolution photo export, color profiles, exposure and brightness | See the [Phase 8 disposition](#106-phase-8-delivery-stages) for delivered and deferred criteria. |
| 9: Desktop undo and redo | Reversible project edits, local mask and terrain editing, and safe restoration of worker results | Pass the [Phase 9A–9D gates](#107-phase-9-delivery-stages) for history, save state, resource bounds and Windows workflows. |
| 10: Desktop workspace and preview workflow | Left navigation with dedicated Panels and Preview views, restored workspaces, project intake, solve review, linked sky outlines, and export review | Pass the [Phase 10A–10H gates](#108-phase-10-delivery-stages) at the Full HD reference and compact sizes, including native Windows source and portable workflows. |

Memory and portability contracts begin in Phase 0; Phase 4 scales and verifies them. Do not postpone their architectural design until after the GUI or blend engine is complete.

### 10.1 Phase 3 Delivery Stages

| Stage | Deliverable | Acceptance evidence |
| --- | --- | --- |
| 3A | Linear mono and RGB TIFF interoperability | Define sample scaling, channel order, and how WCS and coverage travel with the image. Verify input and output with Windows fixtures that check sample values, channel order, WCS coordinates, and coverage after reopening. |
| 3B | PySide6 project and job workflow | Create, save, and reopen a project, then add and relink panels. Run a mosaic job off the UI thread. Verify responsive progress, cancellation, and cleanup of partial output. |
| 3C | Sky preview and export | Verify pan, zoom, and display-only stretch on the GPU viewport and CPU fallback. Export a sky mosaic using the same geometry as the preview and verify their agreement. This is the first usable desktop milestone. |
| 3D | Foreground tags and editable sky masks | Verify automatic tag and mask proposals plus manual overrides on mixed panels. Save and reopen a project with those edits. Verify that foreground features stay out of sky solving and fitting. |
| 3E | Foreground stitching and layer composition | Verify image-space foreground alignment without WCS and independent sky and foreground exports. Propose a composition from a shared mixed panel. Verify that manual placement, seam overlap, and sky-edge crop edits survive reopening. |
| 3F | Packaged Windows 11 x64 acceptance | Exercise the full FITS and TIFF workflows in the packaged app, including mixed panels. Verify preview/export agreement, project recovery and relinking, cancelled-job cleanup, and CPU fallback. Close Phase 3 after the cumulative checks pass. |

### Phase 3.1 Desktop Plate Solving

Start 3.1A after local Phase 3F acceptance. Run the [clean Windows 11 x64 check](docs/phase-3f.md#pending-clean-machine-check) in parallel when a test installation is available. Reuse the [offline solver chain](#63-wcs-reuse-solving-and-registration) and the project background job and sidecar contracts.

#### 3.1A Panel WCS status and optical metadata

- Display project panels in a control table with one row per source, editable panel settings, and selectable property columns. Show the effective WCS state for every row. Default to a dark desktop theme and remember the user’s choice of dark or light appearance. Distinguish validated embedded WCS, validated sidecar WCS, missing WCS, and invalid or stale WCS. Show why an input cannot be checked when its source is missing or unreadable. Refresh status on import, reopen, relink, mask edits, and solve completion.
- Populate focal length in millimeters and effective X and Y pixel sizes in micrometers from supported embedded FITS, TIFF, and XISF metadata. Read FITS producer conventions such as `FOCALLEN`, `XPIXSZ`, and `YPIXSZ`, TIFF EXIF/XMP sensor fields, and XISF instrument properties. Verify field meaning and units against representative files. Use focal-plane resolution for TIFF sensor pitch. Record the metadata source and let users fill or override values per panel. Save explicit edits in the project and support reopening earlier manifests. [Panel optics](docs/phase-3b.md#panel-wcs-and-plate-solve-hints)
- Derive an approximate image scale in arcseconds per pixel from the effective pixel pitch and focal length when both are usable. Use the axis geometry consistently when deriving the solver's field-of-view hint. Prefer an explicit scale if supplied, then a validated embedded scale, then a derived scale. Use valid pointing hints when present. Treat optical values as scale hints and use the applicable blind fallback when pointing is missing. Account for binning or resampling only when confirmed by the metadata convention. Leave ambiguous, missing, or invalid hints unset.
- Verify status and hint precedence across supported formats using valid, absent, and malformed metadata, including stale sidecar and binned-image cases. Verify automatic panel settings, manual overrides, and reopening older projects.

#### 3.1B Local plate solve settings

- Add a **Plate Solve Settings** section accessible before running a job. Let the user browse to a local Gaia DR3 catalog file and its matching blind index when needed, and to the ASTAP executable and local catalog directory with the appropriate database selection. Support either configured backend or both in the existing precedence order.
- Save the paths in local application settings. Validate configured paths and backend availability and explain missing or incompatible files and the hints or index needed for a usable attempt. Keep catalog identities in solve diagnostics. Verify path selection, persistence across application restarts, and actionable messages for missing or moved data.

#### 3.1C Desktop plate solve job

- Add a **Plate Solve** button that runs the existing Qt-free solver in a cancellable background job for sky-bearing panels without a validated effective WCS. Skip panels with validated WCS or no sky contribution. Use each panel's current hints and effective sky mask. Show the number of applicable panels, progress and per-panel outcomes, including the solver used and diagnostic reasons for failures.
- Publish each successful WCS atomically as a new source- and mask-bound sidecar. Use a sibling folder beside the saved project or a folder chosen for an untitled project. Attach successful results at job completion, refresh the WCS status and invalidate any stale preview. The normal project save persists the new references. Preserve original images and any earlier sidecars.
- Show each attempted panel's result in the panel control table and solver details in its tooltip. Retain completed results when another panel fails or the user cancels. Keep the remaining panels eligible for retry and clean up incomplete output and solver staging.
- Verify a mixed project with embedded WCS, a reusable sidecar, an unsolved sky panel, and a foreground-only panel in the Windows desktop bundle. Confirm only eligible panels reach the solver. Exercise Gaia DR3 and ASTAP configurations, fallback when both are configured, cancellation and retry, project save and reopen, and reuse of the solved WCS by preview and export. Verify unchanged inputs and that the CLI remains Qt-free.

<a name="phase-31-astronomy-engine-revalidation"></a>

### Phase 3.5 Astronomy Engine Revalidation

Start 3.5A after Phase 3.1 passes. Use the [original Phase 2 acceptance criteria and evidence](docs/phase-2.md#acceptance-fixtures) as the baseline. Include the Phase 3.1 desktop solve workflow in the regression review.

Review the supported mono workflow from solving through export. Cover WCS reuse and ordered offline Gaia/ASTAP fallback, sidecar validity, timeout and cancellation cleanup, and source immutability. Check sky masking with supplied masks and saved project edits, held-out alignment, relative stellar gain and profiles, offset and plane selection, faint emission recovery, and weak or disconnected overlaps.

Track how solver, mask, and refinement findings affect preview and export. Fix regression criteria for narrow overlaps, saturated stars, and masked WCS reuse before revising the engine. Keep an explicit real-field crop recipe for repeatable solver and refinement checks. [Phase 3.5A review](docs/phase-35.md)

| Stage | Deliverable | Acceptance evidence |
| --- | --- | --- |
| 3.5A | Review | Map each Phase 2 criterion to current code, fixtures, and results. Rerun the original baseline on Windows 11 x64. Record coverage gaps and failing cases with reproduction steps. Select representative cases for any gaps and freeze their acceptance thresholds before revising the engine. |
| 3.5B | Revision | Resolve findings that affect acceptance. Add focused regression checks for corrected behavior and missing evidence. Record before-and-after results for corrections and track any follow-up outside this gate in the topic register. |
| 3.5C | Verification | Rerun the full Phase 2 baseline and added regressions on Windows 11 x64 against the frozen criteria. Exercise offline solving, sidecar reuse, and a representative masked refinement and export through the Qt-free Windows CLI bundle. Reopen a FITS export independently and verify pixels, WCS, and coverage. Record the tested revision, fixture and catalog versions, measured results, and pass or fail for each gate. |

The owner requested new real fields for 3.5C. Verify M42 local astrometry against the original archive WCS and exercise the Documents Gaia catalog format. Reconstruct a separate M31 reference from two panels with 20% overlap relative to each panel's width, then compare science pixels, coverage, and WCS through CLI and desktop export. [Phase 3.5C evidence](docs/phase-35.md#phase-35c-windows-verification)

Close Phase 3.5 when the recorded evidence meets every Phase 2 acceptance criterion and all findings that affect acceptance are resolved.

### Phase 3.6 Plate Solve Reliability

Phase 3.6A completed its capability/reference freeze on 2026-11-18, including the owner TIFFs and automatic EXIF/XMP optical import. The solver policy and desktop/CLI integration are implemented. Track the measured Windows acceptance and remaining external gates in the [implementation results](docs/phase-36-results.md). [Capability evidence](docs/phase-36a.md) · [Frozen contracts](tests/fixtures/plate_solve_v36.json)

Start 3.6A after Phase 3.5C. The owner requested this phase after the [Mosaic Master comparison](docs/plate-solve-comparison.md). The [detailed plan](docs/phase-36.md) defines the implementation scope, candidate numerical thresholds, catalog options, fixtures, migration and downstream impact. [ADR-0017](docs/adr/0017-astap-first-validated-solving.md) records the ASTAP-first direction; this is not an implementation-completion claim.

Required outcomes are: reuse effective WCS, prioritize local ASTAP before Gaia, automatically select a usable installed ASTAP catalog while preserving manual choices, require at least 15 evidenced matches for new qualified results, recover from incorrect scale hints, validate supported low-order SIP at field edges, and enforce one preparation-to-publication time budget. Frozen 3.6A defaults include a 120-second panel budget and the RMS ceiling in Section 6.3; the reference manifest records the values for B–F implementation and acceptance. Keep native residuals, independent catalog verification and genuinely held-out errors distinct.

| Stage | Scope | Acceptance evidence |
| --- | --- | --- |
| 3.6A | Freeze capabilities, contracts and fixtures | Record the exact ASTAP CLI's automatic catalog and SIP behavior, a reproducible ASTAP-only match/RMS path, supported catalogs/domains, frozen numerical and time thresholds, fixture identities and compatibility policy. Do not infer matched stars from detection counts. |
| 3.6B | ASTAP priority and catalog automation | Verify existing-WCS reuse, ASTAP-before-Gaia dispatch, Automatic/manual catalog selection, actual resolved catalog identity, each backend alone, missing/corrupt data, and unchanged original images. Prefer verified ASTAP native selection; resolve explicitly when native behavior is opaque or unsupported. |
| 3.6C | Total deadline and cleanup | Include source work, catalog opening, staging, all attempts, validation and publication in one monotonic panel deadline; support a job-wide cap. Verify boundary timing, late success rejection, cancellation, worker/process cleanup and retention of completed panels. Preserve legacy per-attempt timeout meaning. |
| 3.6D | Match/RMS qualification and bad-scale recovery | Apply the common 15-match/quality gate to ASTAP and Gaia while retaining Gaia probability checks. Verify just-below/on/above thresholds, false matches and recovery from wrong position and 0.5×/2× scale without a stale FOV constraint, within the total budget. |
| 3.6E | Supported SIP and full-field geometry/error maps | Compare TAN with supported SIP-2/3 using the frozen spatial sample and validation policy. Verify linear skew, nonlinear displacement and regional measured-error/support maps, synthetic truth and real catalog errors, sparse/clustered rejection, corner/grid inverse stability, parity/RA wrap, stale-SIP removal and shared preview/export geometry. |
| 3.6F | Desktop/CLI migration and Windows acceptance | Verify Automatic settings and budget persistence, explicit revalidation, old projects/sidecars, quality/timing reports, cancellation/retry, and independent reopened exports. Run the current suite and appropriate source/portable CPU/OpenGL workflows with recorded solver/catalog versions. |

Do not treat native ASTAP success alone as the new match/RMS gate. Its present adapter does not supply those metrics; native matched-pair evidence or bounded local catalog validation is required, including ASTAP-only installations. This capability is an explicit 3.6A scope dependency. The implementation uses the real command-line solver and does not require GUI automation or unrequested downloads.

Keep source/mask-bound atomic sidecars and optional Seiza. Existing phase evidence remains historical; old WCS with unavailable match metrics stays readable with an honest evidence grade. Update order-sensitive tests and diagnostic formats deliberately. Phase 4A/4C consume the resulting shared solve/report contract, and Phase 4B retains its separate 12-panel resource and image-quality gates. The clean-machine check remains separate. Close Phase 3.6 only after all mandatory gates pass and unsupported cases are documented. [Q-015–Q-018](questions_open_topics.md)

### 10.2 Phase 4 Delivery Stages

The owner authorized starting [Phase 4A](docs/phase-4a.md) from the locally verified Phase 3.6F baseline on 2026-11-18. Track the remaining [Phase 3.6 acceptance checks](docs/phase-36-results.md#remaining-acceptance) as separate work. Reuse the solve quality, catalog and budget diagnostics in automation. Use the CLI from 4A for the 4B benchmarks. Build the desktop panel after the large-mosaic checks exercise progress and cancellation.

| Stage | Deliverable | Acceptance evidence |
| --- | --- | --- |
| 4A | Headless project automation and scripts | On Windows 11 x64, use the installed CLI and portable console launcher to create and validate a sky project, run a batch of saved FITS and TIFF projects, and reproduce a saved mixed-project export with matching pixels, coverage, and applicable WCS. Verify that scripts can parse results and progress, detect missing inputs and occupied output paths, and cancel a render without publishing a partial export. The workflow runs without Qt. |
| 4B | [Large mosaics and improved blends](docs/phase-4b.md) | Run 12-panel 6000 x 4000 FITS and TIFF jobs, including RGB and a mixed sky and foreground case, with enforced memory limits and incremental export. Verify output-tile correctness, seamless halo boundaries, bounded queue growth, and measured quality improvement for any optional multiband blend. |
| 4C | [Desktop command panel](docs/phase-4c.md) | Validate a saved project and export from the panel using the same commands and results as the standalone CLI. Verify default visibility, desktop operation summaries while hidden, command history, progress, and cancellation with partial-output cleanup while the Windows desktop stays responsive. |

The Phase 4 follow-up covers dialog-free first save, reopen, relink, active-project export and close through [desktop session commands](docs/phase-4c.md#control-the-active-project-without-dialogs). The [headless preparation commands](docs/phase-4a.md#prepare-a-project-without-the-desktop) attach qualified WCS, accept supplied masks, align foreground and save composition placement to new manifests. Verify preservation of the input project and source files, cleanup before retry, and both portable Windows entry points. Phase 7 still governs persistence and rendering of the newer terrain control-point geometry.

### 10.3 Phase 5 Delivery Stages

Start with [Phase 5A XISF interchange](docs/phase-5a.md). Use the shared panel and raster interfaces so a saved project supports XISF in preview, solving, and export. Verify mono and RGB sample values, coverage, FITS-compatible metadata, and resource limits before extending output geometry. Independent reopening must cover the sky grid, masked pixels, and composition contributions. The copied Windows CLI and desktop bundles must exercise XISF through their normal entry points.

[Phase 5B](docs/phase-5b.md) adds ICRS ZEA as an equal-area sky grid. Save the projection choice, preserve legacy TAN interpretation, and share preview and export geometry. Exercise longitude wrap, crop and rotation, the antipode, masked samples, and independently reopened WCS in every supported sky export format. Verify Qt-free CLI and desktop workflows with the copied Windows packages.

[Phase 5C](docs/phase-5c.md) renders one filter band's sky panels on the saved grid. Resolve explicit panel assignments, embedded labels and a declared common filter before assigning the `Unspecified` default. Validate band-local units and layout, and retain independent coverage and WCS in each output. Verify desktop selection, Qt-free automation, batch cancellation, and independent reopening of the mono and RGB products.

### 10.4 Phase 6 Delivery Stages

Follow the [detailed Phase 6 plan](docs/phase-6.md) after Phase 5. Start with the frozen real-data baseline and add diagnostics to the current terrain aligner. Open Phase 7A from the [6A–6B foreground evidence](docs/phase-6.md#handoff-to-phase-7a) while masked solving, ZEA and native Windows checks proceed on their own references. The [application test findings](docs/application-test-findings.md) provide the starting measurements.

| Stage | Deliverable | Acceptance evidence |
| --- | --- | --- |
| 6A | Real-observation reference inventory and baseline | Record reproducible inputs, provenance, masks, WCS, expected outcomes, and dataset-specific tolerances. Establish current behavior on PA4, archive sky fields, and independently captured positive and negative terrain cases. |
| 6B | Foreground diagnostics and mask feedback | Report the measured stage for all 15 PA4 pairs. Verify the existing translation against the real positive control and verify expected negative outcomes. Record the references, mask variants, and pair diagnostics for 7A. |
| 6C | Masked wide-field plate-solve recovery | Identify catalog resource, association, and edge-support outcomes within existing budgets. Repeat PA4 and the M13/M42 controls. Require strict-edge evidence for new frames admitted to the PA4 mosaic. |
| 6D | Wide ZEA inverse and preview performance | Replay the warning from a real observation, preserve independently checked samples and coverage, and measure coordinate mapping, source reads, and viewport cost on the fixed PA4 grid. |
| 6E | Native lifecycle and Windows package acceptance | Verify close, cancellation, cleanup, and retry on CPU and OpenGL. Compare real-data exports across Phase 6 source and portable launchers and verify the intended bundles on a clean Windows 11 x64 installation. |

### 10.5 Phase 7 Delivery Stages

Start 7A when the Phase 6A terrain references and 6B diagnostic checks are ready. The [detailed Phase 7 plan](docs/phase-7.md) uses those results to compare models, define measured quality limits, and verify source sampling, persistence and Windows delivery. [ADR-0023](docs/adr/0023-terrain-control-point-registration.md) records the proposal.

| Stage | Deliverable | Acceptance evidence |
| --- | --- | --- |
| 7A | Real terrain references and PA4 diagnosis | Freeze independent point annotations, overlap, expected rejections, and held-out tolerances. Compare candidate geometry on the same points. |
| 7B | Manual control points and anchored fit | Fit verified terrain with translation or similarity and report point residuals and disconnected groups. Reproduce the accepted transform from recorded inputs. |
| 7C | Automatic ground feature matching | Verify spatially distributed local matches within a measured CPU budget. Exercise manual recovery and rejection of misleading overlap on real controls. |
| 7D | Evidence-led camera and lens model | Compare rotation with the simpler models, verify near/far support and graph drift, and adopt added parameters only with repeatable held-out improvement. |
| 7E | Shared rendering and compatible persistence | Compose transforms in the tile sampler, check independent sky and ground coverage, and reopen both new and earlier saved geometry. |
| 7F | Point review and Windows delivery | Verify manual editing, preview, cancellation and independent exports across native Windows source and portable launchers on the real reference set. |

### 10.6 Phase 8 Delivery Stages

**Disposition, 2026-11-26.** The owner closed Phase 8 with the locally verified photo workflow through beta 15. The outstanding 8D criteria and remaining 8E and 8F work are recorded for follow-up. [Delivered scope and deferred criteria](docs/phase-8.md#phase-8-closure)

Phase 8 starts with full-resolution photo export from the current sRGB sky preview. Stage 8A freezes the sky photo and scientific output intents, source coordinate frame, color transfer, profiles, fixtures and numerical limits for 8B. Later stages qualify selectable profile, color conversion, exposure, brightness, lens geometry and vignetting methods with independent measurements. The delivery gates cover scientific output parity, bounded sampling, saved project compatibility and desktop/CLI automation. [8A contract](docs/phase-8.md#8a-frozen-photo-export-contract) · [Delivery and acceptance](docs/phase-8.md#delivery-stages) · [ADR-0026](docs/adr/0026-configurable-color-photometry-and-optics.md)

### 10.7 Phase 9 Delivery Stages

Plan session-scoped undo and redo for the desktop. Begin with panel edits and the saved-project checkpoint in 9A. Extend coverage to accepted dialogs and editor gestures in 9B, then handle worker results, sidecar references and bounded retention in 9C. In 9D, compare exports before and after history navigation and verify the packaged Windows workflow. [Detailed scope and acceptance criteria](docs/phase-9.md)

### 10.8 Phase 10 Delivery Stages

Use `0.1.0b28` and the 1920 × 1080 desktop as the reference. Measure the preview area and check accessibility in 10A. In 10B, add a left vertical menu to switch between dedicated Panels and Preview views, with a shared Command Panel and preview focus mode. Restore workspace settings and improve project intake in 10C. Add panel filtering and solve review in 10D, then preview scale and crop feedback in 10E. Link selection between the table and sky panel outlines in 10F. Review effective output settings before export in 10G and verify the whole workflow in 10H. [Detailed delivery and acceptance plan](docs/phase-10.md)

Use the existing project history, render geometry and export contracts. Verify that desktop view settings and actions preserve saved-project compatibility and that representative exports agree with the Qt-free CLI. Check Full HD at 100%, 125% and 150% scaling, the compact layout, and CPU and OpenGL on Windows. [Project impact](docs/phase-10.md#project-impact) · [Windows acceptance](docs/phase-10.md#10h-windows-acceptance-and-handoff)

## 11. Validation and Acceptance Criteria

**Phase 6 and 7 test data requirement.** Use real observational data exclusively for reproductions, automated and manual regressions, benchmarks, and acceptance in both phases. Establish truth from catalog matches, independently measured corresponding points, archive reference products, and independent sample and WCS checks. Keep source lineage for any calibrated or cropped copy. [Phase 6 data and provenance](docs/phase-6.md#test-data-requirement) · [Phase 7 real-data measurements](docs/phase-7.md#real-data-and-acceptance-measurements)

Phases 0–5 used synthetic data with known geometry, gains, gradients, and faint structures alongside representative real data. Select cases for the applicable workflow from sparse and dense star fields, saturation, low signal-to-noise, narrow or disconnected overlaps, strong distortion, negative and zero pixels, scaled FITS, holes in coverage, and oversized outputs.

| Area | Required evidence |
| --- | --- |
| Registration | Held-out median/RMS/95th-percentile residuals in output pixels; catalog error reported separately. |
| Photometry | Stellar aperture-flux bias, centroid/FWHM/ellipticity changes, and ringing near bright sources. |
| Extended signal | Earlier phases measured recovery of injected nebulosity and known background changes. Use independent measurements of observed extended structures for Phase 6 and 7 checks that affect this behavior. |
| Geometry | Round trips, SIP/no-SIP transitions, longitude wrap, singularities, crop/rotation, and independent WCS export checks. |
| Masks | Legitimate zero and negative values retained; missing data excluded; no fill bleeding through filters or pyramids. |
| Mixed panels | Review detection errors on dark or low-contrast horizons. Verify manual corrections survive reload, terrestrial features stay out of sky fits, stars stay out of ground fits, and ground stitching succeeds with absent WCS. Test weak or missing reference alignment, reversible sky crop, and compositing with partial or zero common coverage. |
| Memory | Peak resident/commit usage where available, bounded queue growth, read-only maps, resource closure, and project-save behavior. |
| Tiling | Agreement with an untiled small reference, including tile origins, halos, and pyramid boundaries. |
| UI/packaging | GUI responsiveness, cancellation, cold start, native imports, worker spawning, no-GPU operation, and clean-machine export. |

Freeze dataset-specific numerical tolerances before tuning. The earlier well-sampled synthetic cases had proposed starting targets of a held-out 95th-percentile alignment error below 0.5 output pixels and isolated-star aperture-flux bias below 1%. For phases 6 and 7, use the frozen Phase 3.6 limits for matching real astrometry cases and establish any new tolerances from independent real-data measurements.

Performance targets must name hardware, data dimensions, filters/channels, panel count, and cold/warm cache state. Do not import benchmark numbers from source comments as promises for AstroMosaic.

## 12. Immediate Implementation Backlog

The bootstrap list below records the original implementation sequence. See [progression.md](progression.md) for completed work and the active handoff.

1. Create the minimal Python package and a UI-independent CLI entry point.
2. Lock candidate dependencies and test compiled imports on Windows 11 x64.
3. Define `PanelDescriptor`, masks, tile access, coordinate origins, and pixel-unit semantics.
4. Implement two-panel FITS-to-FITS rendering using existing WCS and a bounded output buffer strategy.
5. Create a tiny PySide6 float-texture/projection experiment and package it separately from heavy processing.
6. Integrate the offline Gaia DR3 and ASTAP chain without mutating source images.
7. Establish independent WCS, negative/zero pixel, and injected-gradient fixtures.
8. Implement robust stellar normalization and constrained overlap background matching.
9. Start with the linear TIFF contract and fixtures in Phase 3A, then follow the [desktop delivery stages](#101-phase-3-delivery-stages).
10. Profile a representative large dataset before choosing Numba, custom resampling, or GPU compute.

## 13. Traceability and References

### 13.1 Local Snapshot Identification

Repository root: `C:\Software\setiastrosuitepro-main`.

| File | SHA-256 at inspection |
| --- | --- |
| `pyproject.toml` | `4E2325016A1BC0942405FEF01F8039E6074C6261A79695F22934612ADAD54091` |
| `src/setiastro/saspro/mosaic_master.py` | `5605A74ACB63FC2A4E35A8489B41C628E5ABE06C44230D6149504B72CC17D326` |

Additional inspected material: `README.md`, `LICENSE`, `license.txt`, `requirements.txt`, `PUBLISHING.md`, `numba_runtime_hook.py`; selected code in `memory_utils.py`, `numba_bootstrap.py`, `gpu_warp.py`, `plate_solver.py`, `plate_solve_cli.py`, `gaia_blind_solver.py`, `imageops/tiled_canvas.py`, and `__main__.py`; and the test files identified in Section 2, including `test_stacking_integration_memory.py` and `test_project_save_memory.py`.

This record identifies the review input without claiming a complete repository audit or a successful application test run.

### 13.2 Primary External References

- **[E1]** [Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html).
- **[E2]** [Riverbank PyQt introduction and licensing](https://www.riverbankcomputing.com/software/pyqt/intro).
- **[E3]** [SEP source extraction and photometry](https://sep.readthedocs.io/en/stable/).
- **[E4]** [Reproject performance, output arrays, and block processing](https://docs.astropy.org/projects/reproject/en/stable/performance.html).
- **[E5]** [ASTAP official documentation and platform downloads](https://www.hnsky.org/astap.htm).
- **[E6]** [WatneyAstrometry solver and database documentation](https://github.com/Jusas/WatneyAstrometry).
- **[E7]** [PySide6 QOpenGLWidget](https://doc.qt.io/qtforpython-6/PySide6/QtOpenGLWidgets/QOpenGLWidget.html).
- **[E8]** [Qt for Python deployment with PyInstaller](https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html).
- **[E9]** [pyside6-deploy](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html).
- **[E10]** [Reproject pixel-unit and flux conventions](https://reproject.readthedocs.io/en/stable/celestial.html).
- **[E11]** [OpenCV multiband blending implementation](https://github.com/opencv/opencv/blob/4.x/modules/stitching/src/blenders.cpp).
- **[E12]** [NumPy thread safety and GIL behavior](https://numpy.org/doc/stable/reference/thread_safety.html).
- **[E13]** [Numba performance guidance](https://numba.readthedocs.io/en/stable/user/performance-tips.html).
