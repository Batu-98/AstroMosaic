# Phase 3F Windows Package Acceptance

## Build

Build with the locked Python 3.13 `main,build` groups in a dedicated Windows x64 environment. The desktop extra supplies Qt. The Gaia extra supplies the local Seiza binding for the desktop and CLI bundles.

```powershell
poetry sync --only main,build -E desktop -E gaia
.\packaging\build-windows.ps1
.\packaging\build-windows.ps1 -DesktopCheck
```

The desktop launcher is `dist/windows/AstroMosaic/AstroMosaic.exe`. The console launcher is `dist/windows/astromosaic-cli/astromosaic-cli.exe`. Keep each executable with its `_internal` directory. The acceptance executable in `build/windows/checks` is a development artifact. The portable builds include the application license and a generated third-party notice inventory. [Build script](../packaging/build-windows.ps1) · [Windows release preparation](windows-release.md)

## Background Checks

Run the commands from the development environment with the desktop extra and the development dependencies. Each check copies a bundle to a temporary working directory and limits `PATH` to the Windows directories. The desktop check copies only the acceptance executable into that directory alongside the deployed launcher and `_internal` libraries. It uses the same application modules built from the current source. The check provides file paths directly to the dialog entry points and exercises the project window and job handlers.

```powershell
poetry run python packaging/check-windows-cli.py dist/windows/astromosaic-cli
poetry run python packaging/check-windows-desktop.py dist/windows/AstroMosaic build/windows/checks/astromosaic-desktop-check/astromosaic-desktop-check.exe
poetry run python packaging/check-windows-desktop.py dist/windows/AstroMosaic build/windows/checks/astromosaic-desktop-check/astromosaic-desktop-check.exe --backend OpenGL
```

The CPU check uses Qt's offscreen platform with the application's ordinary backend selection. The OpenGL check uses a hidden window with the native Windows driver and reads its framebuffer. Use `--test-secondary-screen` on the desktop launcher for a visible test when a second monitor is available. [Desktop checker](../packaging/check-windows-desktop.py) · [CLI checker](../packaging/check-windows-cli.py)

To include the real desktop plate solve acceptance cases, add `--solve-fixtures .tooling` to either desktop check. The fixture directory supplies `phase2-solve-evidence/m13-primary.fits`, `phase2-gaia/stars-gaia.bin`, `astap/cli/astap_cli.exe`, and `astap/catalog`. The checker creates project inputs from the reference image in its scratch workspace. [M13 reference and catalog setup](phase-2.md#offline-solvers)

## Windows Evidence

The checks passed on Windows 11 Pro x64, build 26200. Both desktop modes aligned the mixed FITS and Deflate TIFF project, relinked the moved source, preserved the saved manifest after a simulated publication failure, and reopened the edited composition. Both cancelled a running render after it reported tile progress, removed its temporary output, and successfully retried to the same filename. Preview samples and coverage matched the reopened exports. The sky FITS retained its WCS, and the composition TIFF contained all four layer contribution codes.

| Desktop check | Sky covered pixels | Foreground covered pixels | Composition covered pixels |
| --- | ---: | ---: | ---: |
| Offscreen CPU | 3,347 | 5,073 | 7,574 |
| Hidden native OpenGL | 3,347 | 5,073 | 7,574 |

The regular packaged desktop launcher also opened on the second monitor, showed the native file chooser, relinked a moved TIFF, and displayed the mixed project's foreground with OpenGL. The packaged CLI spawned a worker and passed FITS, LZW, Deflate RGB, and PackBits TIFF exports. Its hinted Gaia DR3 and ASTAP solves passed with separately installed local catalogs. The offscreen source suite passed 73 tests and skipped the source suite's native viewport test.

## Pending Clean-Machine Check

The checks used copied runtime files on the development host. A separate Windows 11 x64 installation check remains open. Windows Sandbox and Hyper-V were disabled on the available host. Repeat the portable launch and export on a fresh Windows installation to check for system dependencies that might already exist on the development host.

The beta 9 copied-runtime checks also ran on the development host. Use the same candidate for the clean-machine [6E lifecycle](phase-6.md#6e-verify-native-lifecycle-and-windows-packages) and [7F terrain review](phase-7.md#7f-ship-the-review-workflow-and-verify-windows) checks.
