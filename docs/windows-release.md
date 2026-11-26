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

The initial source beta is tagged `v0.1.0b1`. The current development version on `main` is `0.1.0b16`. The Phase 6E local verification record and ZIPs in `.tooling/phase6e-20261119/artifacts/` identify the tested `0.1.0b1` build and its SHA-256 hashes. [Phase 6E evidence](phase-6.md#local-windows-lifecycle-and-package-results) · [GitHub releases](https://github.com/Batu-98/AstroMosaic/releases)

The beta 16 source pre-release uses annotated tag `v0.1.0b16` at `e0b3085bca12c5e22e6ae3279c5f10814397a4b5`. The downloaded source ZIP matches the published SHA-256 receipt. The local Windows desktop and console are in `dist/AstroMosaic-0.1.0b16-windows-x64/` and `dist/astromosaic-cli-0.1.0b16-windows-x64/`. Each `BUILD-INFO.json` records the matching source commit, build time with UTC offset and verified launcher checksum. CPU and OpenGL desktop checks solved, revalidated, cancelled and retried M13. The console solved only the selected panel, reused its WCS on retry and cleaned up an expired batch. Public Windows downloads remain pending clean-machine acceptance and native redistribution review. [Beta 16 pre-release](https://github.com/Batu-98/AstroMosaic/releases/tag/v0.1.0b16)

The local beta 15 launchers are in `dist/AstroMosaic-0.1.0b15-windows-x64/` and `dist/astromosaic-cli-0.1.0b15-windows-x64/`. Their `BUILD-INFO.json` records clean source commit `e4029cc2a279a6eb109b7b5c4ef8a6e15e54d26e`, the build time with UTC offset and the verified launcher checksum. Source, copied desktop and copied console agreed on the M2 rejection and the known mixed-ICC gain. The copied console retained the known gain with masked contamination. Both native desktop preview backends passed. [8D Standard results](phase-8d.md#standard-local-windows-results)

The beta 14 desktop and console are in `dist/AstroMosaic-0.1.0b14-windows-x64/` and `dist/astromosaic-cli-0.1.0b14-windows-x64/`. Their `BUILD-INFO.json` files record clean commit `2e39e7908b3f45d5e6258346571a57f45f3aedad`, the local build time with UTC offset and the verified launcher SHA-256. The copied CPU and OpenGL desktops and console matched the source on the mixed matrix ICC and Standard exposure control. The console also matched the full owner pair reference and nine scientific products. [8C local Windows results](phase-8.md#8c-local-windows-package-results)

The beta 13 desktop and console are in `dist/AstroMosaic-0.1.0b13-windows-x64/` and `dist/astromosaic-cli-0.1.0b13-windows-x64/`. Their `BUILD-INFO.json` files record clean source commit `7083c6f3b9947ff73c2fda67c7acd3364d10179a` and the verified launcher hashes. The local desktop and console default to Preserve Tone. Both desktop backends and the console produced identical footprint crops. The full-resolution console output matched the earlier Preserve Tone RGB reference and opened with transparent canvas in Photoshop 27.7. [Photo tone and transparency evidence](phase-8.md#8b-photo-tone-and-transparency-follow-up)

The beta 12 launchers are in `dist/AstroMosaic-0.1.0b12-windows-x64/` and `dist/astromosaic-cli-0.1.0b12-windows-x64/`. The build records identify clean source commit `99491ad34bbd6cb6469c0f8f7d8bcdf35793baa8` and the launcher checksums. The copied desktop passed real 1:1 detail and mouse crop editing on native CPU and OpenGL. The copied console reopened the saved selection and produced the same tagged TIFF. [Adaptive preview evidence](phase-8.md#8b-adaptive-preview-follow-up)

The beta 11 desktop and console are in `dist/AstroMosaic-0.1.0b11-windows-x64/` and `dist/astromosaic-cli-0.1.0b11-windows-x64/`. Each `BUILD-INFO.json` records the build time, launcher SHA-256 and source commit `e644768177da5013d9aa909621bc38a3d45756ce`. The copied CPU desktop, OpenGL session and CLI produced identical full-resolution tagged sRGB photo TIFFs. Both native display paths passed the compact layout and cancellation/retry checks. [Phase 8B results](phase-8.md#8b-local-windows-package-results)

The beta 10 desktop and console are in `dist/AstroMosaic-0.1.0b10-windows-x64/` and `dist/astromosaic-cli-0.1.0b10-windows-x64/`. Their build records identify source commit `ca0238003f8631ff1eb93ceb0e5def27c4ee2be4` and the launcher checksums. The desktop shows a step-based Plate Solve percentage in a wider progress strip. Native CPU and OpenGL on the second display verified ASTAP D05 and Gaia DR3 M13 solutions, cancellation and retry in both themes. [Plate Solve results](phase-3b.md#beta-10-progress-verification)

The beta 9 desktop and console are in `dist/AstroMosaic-0.1.0b9-windows-x64/` and `dist/astromosaic-cli-0.1.0b9-windows-x64/`. Their build records identify source commit `ba8d217ed22688f6f4c48296cc040a6bc18d5eda` and the launcher checksums. The copied desktop runtimes verified control-point editing, version 8 reopen, cancelled jobs and retry on both preview backends. Oxford foreground and Paranal sky and composition matched the copied console byte for byte. A separate Windows installation and native redistribution review remain open. [Phase 7F results](phase-7.md#7f-local-windows-results)

The beta 8 desktop and console are in `dist/AstroMosaic-0.1.0b8-windows-x64/` and `dist/astromosaic-cli-0.1.0b8-windows-x64/`. Their build records identify source commit `3ab8e3eb8f899da31722316ec06002d0e74a4c0f` and the launcher checksums. The console saved and exported the real Oxford and ALPACA fits, and the desktop CPU and OpenGL previews reopened the Oxford fit on the second display. The Oxford exports matched across the two launchers and source. Fresh Windows acceptance and redistribution review remain open. [Phase 7E evidence](phase-7.md#7e-local-windows-package-results)

The beta 7 desktop and console are in `dist/AstroMosaic-0.1.0b7-windows-x64/` and `dist/astromosaic-cli-0.1.0b7-windows-x64/`. Their build records identify clean source commit `023595ec62f4d634da64ebb7f37e0f0744a0021d` and the launcher checksums. The launchers report version `0.1.0b7`. The bundled desktop solved the two original owner TIFFs and built the fitted sRGB preview in an untitled project on native CPU and OpenGL. Existing saved projects can enable **Auto Frame**. Scientific rendering requires compatible linear sources, including when a common scale is declared. [Beta 7 workflow and evidence](phase-3c.md#windows-verification)

The beta 6 local launchers are in `dist/AstroMosaic-0.1.0b6-windows-x64/` and `dist/astromosaic-cli-0.1.0b6-windows-x64/` with their build records. The desktop session saved, solved, exported unsaved WCS, relinked and closed on a real M13 panel without dialogs. The standalone console created, relinked, solved and exported M13, recovered from a solve deadline, and prepared the real Paranal masks, foreground alignment and placement for composition export. [Live desktop commands](phase-4c.md#control-the-active-project-without-dialogs) · [Headless preparation](phase-4a.md#prepare-a-project-without-the-desktop)

The verified local beta 5 desktop is in `dist/AstroMosaic-0.1.0b5-windows-x64/` with its `BUILD-INFO.json`. The title shows `AstroMosaic 0.1.0b5 (Beta)`. The packaged runtime animated the bar during real M13 solves with ASTAP D05. The batch status advanced to the next panel, cancellation retained the first solution, and retry solved the remaining panel. Revalidation showed the animation with both CPU and OpenGL previews. [Desktop plate solving](phase-3b.md#desktop-plate-solving)

The verified local beta 4 desktop is in `dist/AstroMosaic-0.1.0b4-windows-x64/` with its `BUILD-INFO.json`. The title shows `AstroMosaic 0.1.0b4 (Beta)`. Both Windows preview backends rendered the two linear TIFF panels in the automatic `Unspecified` band. The bundled CLI listed the same band for the saved project. [Per-band workflow](phase-5c.md)

The verified local beta 3 desktop is in `dist/AstroMosaic-0.1.0b3-windows-x64/`. Its `BUILD-INFO.json` records the source commit, launcher hash and test results. The main window title shows `AstroMosaic 0.1.0b3 (Beta)`. Windows CPU and OpenGL checks verified that the Command Panel opens at startup, preview diagnostics identify missing settings, and the recovered two-panel project previews successfully. [Command Panel workflow](phase-4c.md#desktop-workflow) · [Build Preview workflow](phase-3c.md#desktop-workflow)

The local `0.1.0b2` development bundles in `.tooling/plate-solve-phase7-20261121/artifacts/` use a hashed working-tree snapshot and the locked dependencies. The desktop starts Plate Solve directly in untitled projects. The standard CLI provides the manual terrain fit. A separate experimental CLI also bundles the measured headless OpenCV wheel for automatic terrain matching. The tagged release build, fresh Windows 11 x64 acceptance and native redistribution review remain open. [Desktop solve workflow](phase-3b.md#desktop-plate-solving) · [Phase 7 commands](phase-7.md#run-the-automatic-terrain-fit) · [Clean-machine check](phase-3f.md#pending-clean-machine-check)
