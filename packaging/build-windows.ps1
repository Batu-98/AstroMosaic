param([string]$Python = "", [switch]$DesktopCheck)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $projectRoot
$previousPath = $env:Path
$previousCache = $env:PYINSTALLER_CONFIG_DIR
try {
    if (-not $Python) {
        $Python = poetry env info --executable
        if ($LASTEXITCODE -ne 0 -or -not $Python) {
            throw 'Sync the locked build environment first or pass its Python executable.'
        }
    }
    $Python = (Resolve-Path -LiteralPath $Python).Path
    $distPath = Join-Path $projectRoot 'dist/windows'
    $workPath = Join-Path $projectRoot 'build/windows'
    if ($DesktopCheck) { $distPath = Join-Path $workPath 'checks' }
    foreach ($directory in @('dist', 'build', 'dist/windows', 'build/windows',
            'dist/windows/AstroMosaic', 'dist/windows/astromosaic-cli',
            'build/windows/AstroMosaic', 'build/windows/astromosaic-cli', 'build/windows/cache',
            'build/windows/checks', 'build/windows/checks/astromosaic-desktop-check',
            'build/windows/astromosaic-desktop-check')) {
        $path = Join-Path $projectRoot $directory
        if ((Test-Path -LiteralPath $path) -and
            ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Expected a workspace directory for the build output: $path"
        }
    }
    New-Item -ItemType Directory -Force -Path $distPath, $workPath | Out-Null
    $env:Path = "$env:SystemRoot\System32;$env:SystemRoot"
    $env:PYINSTALLER_CONFIG_DIR = Join-Path $workPath 'cache'
    $common = @(
        '-m', 'PyInstaller', '--onedir', '--clean', '--noconfirm', '--noupx',
        '--distpath', $distPath, '--workpath', $workPath, '--specpath', $workPath,
        '--copy-metadata', 'astromosaic',
        '--hidden-import', 'imagecodecs._imcd',
        '--hidden-import', 'imagecodecs._deflate',
        '--hidden-import', 'imagecodecs._shared',
        '--hidden-import', 'imagecodecs._shared_cython'
    )
    if ($DesktopCheck) {
        & $Python @common --console --name astromosaic-desktop-check packaging/check-windows-desktop.py
        if ($LASTEXITCODE -ne 0) { throw 'The desktop acceptance executable failed to build.' }
        return
    }
    & $Python @common --windowed --name AstroMosaic src/astromosaic/ui/__main__.py
    if ($LASTEXITCODE -ne 0) { throw 'The desktop bundle failed to build.' }
    & $Python @common --console --name astromosaic-cli --copy-metadata seiza `
        --exclude-module PySide6 --exclude-module shiboken6 src/astromosaic/__main__.py
    if ($LASTEXITCODE -ne 0) { throw 'The CLI bundle failed to build.' }
    foreach ($bundle in @('AstroMosaic', 'astromosaic-cli')) {
        Copy-Item -LiteralPath LICENSE -Destination (Join-Path $distPath "$bundle/LICENSE")
    }
} finally {
    $env:Path = $previousPath
    $env:PYINSTALLER_CONFIG_DIR = $previousCache
    Pop-Location
}
