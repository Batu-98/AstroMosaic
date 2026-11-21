# AstroMosaic

AstroMosaic builds mosaics from calibrated, stacked astrophotography panels in FITS, TIFF, and XISF. It provides a desktop app for interactive previews and editing and a command-line interface for batch exports.

**Beta.** The current release is a source pre-release for Windows 11 x64. [Release notes and source](https://github.com/Batu-98/AstroMosaic/releases) · [Report an issue](https://github.com/Batu-98/AstroMosaic/issues)

## Support the Work

If AstroMosaic helps with your mosaics, you can support its development with a coffee. [Buy Me a Coffee](https://buymeacoffee.com/batuhanozmen)

## License

AstroMosaic is open source under the GNU General Public License version 3 (`GPL-3.0-only`). [Full license](LICENSE)

## Get Started

Windows 11 x64 is the tested platform.

[Desktop setup](docs/guide.md#run-the-desktop-app) · [CLI setup](docs/guide.md#run-the-headless-cli) · [Full guide](docs/guide.md)

## Key Capabilities & Processing Highlights

- **Linear Multi-Format Support:** Ingests and exports monochrome FITS, linear 16-bit and 32-bit mono/RGB TIFF, and uncompressed XISF, preserving float32 intensity values, validity masks, and world coordinate system (WCS) metadata ([FITS and TIFF workflow](docs/adr/0006-dual-fits-and-tiff-workflow.md), [XISF interchange](docs/phase-5a.md)).
- **Astrometric Plate Solving:** Performs offline blind solving via local ASTAP (`astap_cli.exe`) with automatic database resolution and polynomial distortion (SIP) correction, with fallback to local Gaia DR3 catalogs ([Phase 3.6 results](docs/phase-36-results.md)).
- **Dual-Layer Composition & Terrain Alignment:** Decouples sky projections from terrestrial foregrounds. Supports automatic/manual sky masking, foreground translation and similarity alignment, and interactive control point editing ([Phase 7 terrain panorama registration](docs/phase-7.md)).
- **Sky Projections & Band Separation:** Projects sky mosaics onto Tangential (TAN) or Zenithal Equal-Area (ZEA) grids, with relative star flux scaling, background gradient leveling, and band-specific multi-filter extraction ([ZEA workflow](docs/phase-5b.md), [Per-band workflow](docs/phase-5c.md)).
- **Dual Presentation Surfaces:** Provides an interactive PySide6 graphical interface with GPU (OpenGL) and CPU preview modes, stretch functions, and an embedded Command Panel, alongside a standalone CLI for headless batch execution ([Guide](docs/guide.md)).

## System Design & Processing Pipeline

- **Strict Layer Decoupling:** Numerical algorithms, geometric transformations, and batch pipelines are completely independent of Qt and graphical display contexts. The UI layer purely orchestrates and visualizes engine tasks.
- **Non-Destructive Operations:** Original calibrated panels are treated as read-only. Transformations, background corrections, solved WCS headers, and mask edits are stored separately in project manifests until the final export.
- **Bounded Resource Streaming:** Large mosaics are rendered in streamed memory tiles with explicit buffer budgets, avoiding full-image intermediate allocations and preventing out-of-memory failures.
- **Responsive Background Execution:** Intensive numerical workloads run on worker threads off the main UI loop, ensuring smooth interface interaction, live progress reporting, and safe task cancellation.

## Codebase Organization & Directory Layout

- `src/astromosaic/`: Primary Python source package.
  - `astrometry/`: Local ASTAP integration, Gaia query adapters, and WCS extraction routines.
  - `cli/`: Headless CLI command structure, option parsers, and command dispatchers.
  - `core/`: Fundamental data types, project models, and coordinate definitions.
  - `geometry/`: Astrometric projection models (TAN, ZEA), distortion calculators, and coordinate transforms.
  - `io/`: Scientific image format adapters (FITS, TIFF, XISF) and metadata extractors.
  - `photometry/`: Star flux measurements, background gradient estimation, and relative gain fitting.
  - `pipeline/`: Mosaic assembly engines, tile-based processors, and export builders.
  - `resampling/`: Reprojection algorithms, interpolation kernels, and blend weight calculations.
  - `storage/`: Project file serialization (`.astromosaic`) and cache management.
  - `ui/`: PySide6 desktop application, OpenGL viewports, property dialogs, and embedded command console.
- `tests/`: Automated test suite covering unit tests, numerical contracts, offscreen GUI probes, and regression fixtures.
- `docs/`: Technical documentation, architectural decision records (`docs/adr/`), user instructions (`docs/guide.md`), and delivery phase reports.
- `packaging/`: PyInstaller specification files, build automation scripts, and license notices for Windows executables.
- `data/` & `output/`: Local git-ignored workspaces for input observation panels, intermediate caches, and exported mosaics.

## Astronomical Reference Data & Solving Engines

- **ASTAP Solving System:** Connects to a locally installed ASTAP executable (`astap_cli.exe`) alongside standard star database files (e.g. D05, D20, D50, or H18/H17). Provides fast offline field identification, optical scale recovery, and SIP distortion verification within configurable time limits.
- **Gaia DR3 Star Catalogs:** Supports offline Gaia DR3 binary files through the optional `seiza` component for high-precision astrometric reference validation.
- **Testing & Verification Data:** Synthetic fixtures in `tests/fixtures/` provide analytical ground truth for automated testing, while real observational datasets validate large-scale mosaics and terrain registrations.

## Package Ecosystem & Dependency Specifications

- **Python Runtime:** Managed via [Poetry](https://python-poetry.org/) and pinned in [poetry.lock](poetry.lock), targeting CPython 3.13 on Windows 11 x64.
- **Core Scientific Stack:**
  - `numpy` (>=2.0) and `scipy`: Fundamental numerical algorithms and spatial computations.
  - `astropy` and `reproject`: Astronomical coordinates, WCS handling, and image reprojection.
  - `sep`: Source extraction and stellar photometry.
  - `tifffile` and `imagecodecs`: High-performance scientific TIFF decoding and encoding.
- **Optional Feature Extras:**
  - `desktop`: PySide6-Essentials for the graphical user interface.
  - `gaia`: `seiza` for local Gaia DR3 database access.
- **Development Tooling:**
  - `dev` group: `pytest` (test harness), `ruff` (linter/formatter), `mypy` (strict type analysis), and `fitsio`.
  - `build` group: `pyinstaller` for assembling standalone binaries.

## Developer Environment & Quality Verification

1. **Initialize the Environment:**
   ```powershell
   poetry env use 3.13
   poetry sync --only main -E desktop
   ```

2. **Run Quality & Linting Checks:**
   ```powershell
   poetry check --lock
   poetry run ruff check src tests
   poetry run mypy
   ```

3. **Execute Test Suite & Probes:**
   ```powershell
   poetry run pytest
   poetry run python -m astromosaic smoke --spawn
   poetry run python -m astromosaic.ui.viewport_probe --backend gpu
   poetry run python -m astromosaic.ui.viewport_probe --backend cpu
   ```

## Portable Distribution & Release Bundling

- **Self-Contained Windows Executables:** PyInstaller scripts package the desktop and CLI applications into standalone portable bundles under `dist/AstroMosaic-<version>-windows-x64/` and `dist/astromosaic-cli-<version>-windows-x64/`.
- **Runtime Isolation:** Each distribution includes an internal Python environment (`_internal/`), precluding the need for external runtime installations on target machines.
- **Build Provenance & Verification:** Generated packages produce a `BUILD-INFO.json` file recording the Git commit hash, build timestamp, and launcher SHA-256 checksums.
- **Release Guidelines:** Refer to the [Windows Release Guide](docs/windows-release.md) for complete packaging steps and redistribution checklist requirements.
