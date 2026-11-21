# AstroMosaic release process

AstroMosaic is a GPL-3.0-only application for calibrated, integrated astronomical panels. The initial source beta, `0.1.0b1`, targets Windows 11 x64. Desktop and CLI workflows cover linear FITS, TIFF and uncompressed XISF, offline plate solving, TAN and ZEA sky grids, and per-band sky exports. The desktop also supports separate foreground and sky layers and visual composition. [Application license](../LICENSE) · [Desktop and CLI quick start](guide.md#quick-start)

## Record a release

- Commit the application version in `pyproject.toml`. The desktop and CLI read the installed package version. Use Python's beta suffix for beta releases, such as `0.1.0b1`, and prefix the matching Git tag with `v`.
- Check the Poetry lockfile, run the relevant tests, and verify `python -m astromosaic --version` in the release environment. Create an annotated Git tag on the verified commit and leave published tags on their original commits.
- Generate the source archive from that tag. Record the full commit ID, verification results, and known issues in the GitHub release notes. Attach a `SHA256SUMS.txt` for the release archives and mark beta releases as pre-releases.
- Build portable Windows packages from a clean checkout of the tag and verify both launchers. Publish Windows downloads after the redistribution review and clean-machine acceptance described below.

## Build portable Windows packages

Use a dedicated Windows x64 environment with CPython 3.13 and Poetry 2.5. Poetry installs the dependency versions in [the lockfile](../poetry.lock). Record the exact Python runtime provider and version in the build notes.

```powershell
poetry env use 3.13
poetry sync --only main,build -E desktop -E gaia
.\packaging\build-windows.ps1
```

The desktop folder is `dist/windows/AstroMosaic`. The console folder is `dist/windows/astromosaic-cli`. Archive each complete folder, including its `_internal` directory. Extract the complete folder on Windows before opening `AstroMosaic.exe` or running `astromosaic-cli.exe --help` from PowerShell.

```powershell
$releaseVersion = poetry version --short
Compress-Archive -LiteralPath dist/windows/AstroMosaic -DestinationPath "dist/AstroMosaic-${releaseVersion}-windows-x64.zip"
Compress-Archive -LiteralPath dist/windows/astromosaic-cli -DestinationPath "dist/astromosaic-cli-${releaseVersion}-windows-x64.zip"
Get-FileHash -Algorithm SHA256 "dist/*-${releaseVersion}-windows-x64.zip"
```

The builder includes the application license, `THIRD_PARTY_NOTICES.md`, wheel and supplemental notices in `ThirdParty`, and a list of the bundled native files. The index uses the PyInstaller archive, bundled extension modules and installed wheel metadata to record component versions for each launcher. Review the inventory when the lockfile, Python provider or PyInstaller build changes. [Build script](../packaging/build-windows.ps1) · [Supplemental notice provenance](../packaging/notices/README.md)

Give each successive local beta its own version and folder. Record the exact source commit with the executable and verify the version in the desktop title and the CLI output. Open the executable from its matching folder so Windows loads the bundled `_internal` runtime.

## Third-party source and runtime materials

| Shipped component | Release materials |
| --- | --- |
| CPython and its DLLs | Use the Python license from the build environment and the matching runtime-provider source and dependency records. The local candidates use Python Build Standalone 20261110. [CPython 3.13.18 source](https://github.com/python/cpython/tree/v3.13.18) · [Runtime provider build](https://github.com/astral-sh/python-build-standalone/releases/tag/20261110) |
| PyInstaller bootloader and runtime | Retain the license and bootloader exception in the bundle. Use the source release matching the version in the generated index. [PyInstaller license and exception](https://www.pyinstaller.org/en/stable/license.html) |
| SEP and Seiza | The builder includes supplemental upstream texts for SEP and Seiza. The Seiza wheel supplies the bundled font notice. [SEP source](https://github.com/sep-developers/sep/tree/v1.4.1) · [Seiza source](https://github.com/theatrus/seiza/tree/v0.48.2) |
| Scientific libraries and image codecs | Preserve the wheel notices, including the native-library notices supplied by NumPy, SciPy, and imagecodecs. Use the exact wheel versions in the generated index when identifying matching native sources. [NumPy source](https://github.com/numpy/numpy) · [SciPy source](https://github.com/scipy/scipy) · [imagecodecs source](https://github.com/cgohlke/imagecodecs) |
| Qt, PySide6 and Shiboken | The desktop uses the open-source Qt distribution. Its dynamic libraries remain in `_internal`. The Qt software OpenGL DLL identifies Mesa 11.2.2 and LLVM 3.6.2. Preserve applicable GPL and LGPL texts and the Qt third-party notices. [Qt source archives](https://download.qt.io/archive/qt/) · [Qt for Python source](https://github.com/pyside/pyside-setup/tree/v6.12.0) · [Qt third-party notices](https://doc.qt.io/qt-6/licenses-used-in-qt.html) · [Qt software OpenGL builds](https://download.qt.io/development_releases/prebuilt/llvmpipe/windows/) |
| Microsoft runtime files | The selected CPython and PySide6 builds supply the Microsoft runtime DLLs listed in the inventory. Apply the distributor terms for these exact files when preparing public Windows downloads. [Microsoft redistribution terms](https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files) |

Public Windows binary distribution requires a complete notice and corresponding-source review of the native libraries supplied by the Python and Qt builds and compiled wheels. That review includes the Qt software OpenGL renderer, bundled Microsoft runtime files and any native components whose wheel notices do not identify the exact source. When distributing GPL-covered executables, make the corresponding source available alongside the binary download as described in GPLv3 §6. [GNU GPLv3](https://www.gnu.org/licenses/gpl-3.0.html#section6) · [Release tracking](../questions_open_topics.md#q-005---application-licensing-and-distribution-model)

## External solver and reference data

Install the ASTAP CLI and star databases separately from their upstream releases. Configure their local paths in the desktop or pass them to the CLI. Seiza bindings ship with these builds. Obtain the matching Seiza Gaia catalog and blind index separately. Use the credit and usage terms of the particular catalog package. ASTAP's D-series data and the Seiza catalogs are derived from Gaia data processed by ESA's Gaia Data Processing and Analysis Consortium. [ASTAP downloads and credits](https://sourceforge.net/projects/astap-program/files/star_databases/) · [Seiza catalog setup](phase-2.md#catalog-setup-and-updates) · [ESA Gaia DR3](https://gea.esac.esa.int/archive/documentation/GDR3/index.html)

Download public DSS reference images from their archives for optional reproduction. Follow the archive's image terms. The source distribution provides fixture recipes, synthetic fixtures and reports. [MAST DSS copyright notice](https://archive.stsci.edu/dss/copyright.html) · [Reference-field setup](phase-35.md#m42-offline-astrometry-and-documents-catalogs)

## Verification status

The initial source beta is tagged `v0.1.0b1`. The current development version on `main` is `0.1.0b3`. The Phase 6E local verification record and ZIPs in `.tooling/phase6e-20261119/artifacts/` identify the tested `0.1.0b1` build and its SHA-256 hashes. [Phase 6E evidence](phase-6.md#local-windows-lifecycle-and-package-results) · [GitHub releases](https://github.com/Batu-98/AstroMosaic/releases)

The verified local beta 3 desktop is in `dist/AstroMosaic-0.1.0b3-windows-x64/`. Its `BUILD-INFO.json` records the source commit, launcher hash and test results. The main window title shows `AstroMosaic 0.1.0b3 (Beta)`. Windows CPU and OpenGL checks verified that the Command Panel opens at startup, preview diagnostics identify missing settings, and the recovered two-panel project previews successfully. [Command Panel workflow](phase-4c.md#desktop-workflow) · [Build Preview workflow](phase-3c.md#desktop-workflow)

The local `0.1.0b2` development bundles in `.tooling/plate-solve-phase7-20261121/artifacts/` use a hashed working-tree snapshot and the locked dependencies. The desktop starts Plate Solve directly in untitled projects. The standard CLI provides the manual terrain fit. A separate experimental CLI also bundles the measured headless OpenCV wheel for automatic terrain matching. The tagged release build, fresh Windows 11 x64 acceptance and native redistribution review remain open. [Desktop solve workflow](phase-3b.md#desktop-plate-solving) · [Phase 7 commands](phase-7.md#run-the-automatic-terrain-fit) · [Clean-machine check](phase-3f.md#pending-clean-machine-check)
