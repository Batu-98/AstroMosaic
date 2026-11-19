# AstroMosaic 0.1.0 release preparation

AstroMosaic is a GPL-3.0-only application for calibrated, integrated astronomical panels. The initial source release targets Windows 11 x64. Desktop and CLI workflows cover linear FITS, TIFF and uncompressed XISF, offline plate solving, TAN and ZEA sky grids, and per-band sky exports. The desktop also supports separate foreground and sky layers and visual composition. [Application license](../LICENSE) · [Desktop and CLI quick start](guide.md#quick-start)

## Build portable Windows packages

Use a dedicated Windows x64 environment with CPython 3.13 and Poetry 2.5. This release preparation used CPython 3.13.18. Poetry installs the dependency versions in [the lockfile](../poetry.lock).

```powershell
poetry env use 3.13
poetry sync --only main,build -E desktop -E gaia
.\packaging\build-windows.ps1
```

The desktop folder is `dist/windows/AstroMosaic`. The console folder is `dist/windows/astromosaic-cli`. Archive each complete folder, including its `_internal` directory. Extract the complete folder on Windows before opening `AstroMosaic.exe` or running `astromosaic-cli.exe --help` from PowerShell.

```powershell
Compress-Archive -LiteralPath dist/windows/AstroMosaic -DestinationPath dist/AstroMosaic-0.1.0-windows-x64.zip
Compress-Archive -LiteralPath dist/windows/astromosaic-cli -DestinationPath dist/astromosaic-cli-0.1.0-windows-x64.zip
Get-FileHash -Algorithm SHA256 dist/*-0.1.0-windows-x64.zip
```

The builder includes the application license, `THIRD_PARTY_NOTICES.md`, wheel and supplemental notices in `ThirdParty`, and a list of the bundled native files. The index uses the PyInstaller archive, bundled extension modules and installed wheel metadata to record component versions for each launcher. Review the inventory when the lockfile, Python provider or PyInstaller build changes. [Build script](../packaging/build-windows.ps1) · [Supplemental notice provenance](../packaging/notices/README.md)

## Third-party source and runtime materials

| Shipped component | Release materials |
| --- | --- |
| CPython and its DLLs | Use the Python license from the build environment and the matching runtime-provider source and dependency records. The local candidates use Python Build Standalone 20261110. [CPython 3.13.18 source](https://github.com/python/cpython/tree/v3.13.18) · [Runtime provider build](https://github.com/astral-sh/python-build-standalone/releases/tag/20261110) |
| PyInstaller bootloader and runtime | Retain the license and bootloader exception in the bundle. Use the source release matching the version in the generated index. [PyInstaller license and exception](https://www.pyinstaller.org/en/stable/license.html) |
| SEP and Seiza | The builder includes supplemental upstream texts for SEP and Seiza. The Seiza wheel supplies the bundled font notice. [SEP source](https://github.com/sep-developers/sep/tree/v1.4.1) · [Seiza source](https://github.com/theatrus/seiza/tree/v0.48.2) |
| Scientific libraries and image codecs | Preserve the wheel notices, including the native-library notices supplied by NumPy, SciPy, and imagecodecs. Use the exact wheel versions in the generated index when identifying matching native sources. [NumPy source](https://github.com/numpy/numpy) · [SciPy source](https://github.com/scipy/scipy) · [imagecodecs source](https://github.com/cgohlke/imagecodecs) |
| Qt, PySide6 and Shiboken | The desktop uses the open-source Qt distribution. Its dynamic libraries remain in `_internal`. The Qt software OpenGL DLL identifies Mesa 11.2.2 and LLVM 3.6.2. Preserve applicable GPL and LGPL texts and the Qt third-party notices. [Qt source archives](https://download.qt.io/archive/qt/) · [Qt for Python source](https://github.com/pyside/pyside-setup/tree/v6.12.0) · [Qt third-party notices](https://doc.qt.io/qt-6/licenses-used-in-qt.html) · [Qt software OpenGL builds](https://download.qt.io/development_releases/prebuilt/llvmpipe/windows/) |
| Microsoft runtime files | The selected CPython and PySide6 builds supply the Microsoft runtime DLLs listed in the inventory. Apply the distributor terms for these exact files when preparing public Windows downloads. [Microsoft redistribution terms](https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files) |

This preparation publishes AstroMosaic source and produces local portable candidates. Public Windows binary distribution still requires a complete notice and corresponding-source review of the native libraries supplied by the Python and Qt builds and compiled wheels. That review includes the Qt software OpenGL renderer, bundled Microsoft runtime files and any native components whose wheel notices do not identify the exact source. When distributing GPL-covered executables, make the corresponding source available alongside the binary download as described in GPLv3 §6. [GNU GPLv3](https://www.gnu.org/licenses/gpl-3.0.html#section6) · [Release tracking](../questions_open_topics.md#q-005---application-licensing-and-distribution-model)

## External solver and reference data

Install the ASTAP CLI and star databases separately from their upstream releases. Configure their local paths in the desktop or pass them to the CLI. Seiza bindings ship with these builds. Obtain the matching Seiza Gaia catalog and blind index separately. Use the credit and usage terms of the particular catalog package. ASTAP's D-series data and the Seiza catalogs are derived from Gaia data processed by ESA's Gaia Data Processing and Analysis Consortium. [ASTAP downloads and credits](https://sourceforge.net/projects/astap-program/files/star_databases/) · [Seiza catalog setup](phase-2.md#catalog-setup-and-updates) · [ESA Gaia DR3](https://gea.esac.esa.int/archive/documentation/GDR3/index.html)

Download public DSS reference images from their archives for optional reproduction. Follow the archive's image terms. The source distribution provides fixture recipes, synthetic fixtures and reports. [MAST DSS copyright notice](https://archive.stsci.edu/dss/copyright.html) · [Reference-field setup](phase-35.md#m42-offline-astrometry-and-documents-catalogs)

## Verification status

The release preparation covers locked builds and inspection of the resulting package contents. Application tests were deferred at the owner's request. The separate Windows launcher and export check still needs a fresh Windows 11 x64 installation. [Prior Windows acceptance and clean-machine check](phase-3f.md#pending-clean-machine-check)
