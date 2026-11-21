# AstroMosaic application test guide

Use these cases to verify the Windows desktop and the headless CLI with merge-ready panels. The pack exercises archive WCS, narrow and skewed geometry, wide-angle sky, independent foreground registration, and visual composition. Each pair meets the 10% overlap requirement on its applicable layers.

The [application test findings](application-test-findings.md) record measured results from the base, extended, and owner-supplied cases, with proposed changes and acceptance checks.

## Fixtures

The prepared pack lives in `data/application-tests/`. Open its `contact-sheet.png` to identify the panels. Subdirectories for the five pairs in the table contain the labeled A and B images, a ready `project.astromosaic`, and `case.json` with dimensions, grid settings, SHA-256 hashes, and overlap counts. The two mixed cases also include an `unaligned.astromosaic` and full-size `*.labels.fits` maps. The saved project carries the editable labels. The external maps show the same labels for independent inspection.

Optional owner-supplied cases appear in `local_cases` in the local `fixtures.json`. Follow the linked guide inside each case directory. Keep the original files available at their saved paths and use the case's own acceptance criteria. The CLI loop below runs the reproducible pairs listed in `cases`.

Ten additional cases cover an atlas chain, polar geometry, unequal scales, SIP distortion, scaled FITS, input coverage, separate filter bands and three wide-angle nightscapes. Their fixtures and runner use the `extended/` pack. [Extended test guide](application-tests-extension.md)

Sky overlap is the number of shared valid sample positions divided by the count supported by the smaller panel on the saved TAN grid. It is measured with a nearest-pixel footprint and the saved sky labels where applicable. Foreground overlap uses the same denominator on the ground alignment grid, using the known image-space crop offsets. The ground controls use same-size, same-scale, same-orientation panels. Composition seam overlap is a separate placement setting.

| Case | Folder | Panel size and format | Horizontal field per panel | Sky overlap | Ground overlap |
| --- | --- | --- | --- | ---: | ---: |
| SKY-01 | `sky01-m17-atlas` | 512 × 1024 mono FITS | 0.142° | 11.74% | — |
| SKY-02 | `sky02-narrow-skew` | 780 × 540 mono FITS | 0.465° | 19.33% | — |
| SKY-03 | `sky03-wide-rgb` | 960 × 560 RGB TIFF | 46.38° | 38.55% | — |
| MIX-01 | `mix01-synthetic-ridge` | 896 × 544 RGB TIFF | 40.51–40.74° | 43.81% | 52.49% |
| MIX-02 | `mix02-paranal` | 1100 × 925 RGB TIFF | 99° of source panorama longitude | 53.96% | 61.75% |

### Refresh or transfer the pack

1. Start in the checkout root with CPython 3.13 and the locked dependencies. Use `poetry sync -E desktop -E gaia` when preparing a fresh development environment. The Gaia extra is needed for the optional local solver check.
2. Use the ready pack when available. To rebuild it, run the command below. Use `--output data/application-tests-rerun` for a fresh copy when the default directory already exists. `--download` fetches the three pinned public files into `data/application-test-sources/` and verifies their hashes. Omit the option when the source cache is complete.
3. Keep the input files and prepared manifests together. A saved project uses the input size and modification time. After moving the pack, preserve those timestamps or regenerate the manifests by rebuilding the pack on the target system. Put outputs, edited projects, and diagnostic logs in a separate run directory.

```powershell
poetry run python tools/prepare_application_test_fixtures.py --download
```

[Fixture generator](../tools/prepare_application_test_fixtures.py) · [Project reopening and relinking](phase-3b.md)

## Run the CLI cases

Run from the repository root in PowerShell 7 after the fixtures are ready. The script writes machine-readable preflight and render results and separate progress logs. Set `$Python` to the locked interpreter if Poetry places the environment outside the checkout.

```powershell
$Python = (Resolve-Path '.venv/Scripts/python.exe').Path
$Fixtures = (Resolve-Path 'data/application-tests').Path
$Run = (New-Item -ItemType Directory -Path ('output/application-tests/' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))).FullName
$Cases = (Get-Content -LiteralPath (Join-Path $Fixtures 'fixtures.json') -Raw | ConvertFrom-Json).cases

function Invoke-RecordedCli {
    param([string]$LogName, [string[]]$Arguments)
    $reportPath = Join-Path $Run "$LogName.json"
    $logPath = Join-Path $Run "$LogName.stderr.jsonl"
    & $Python -m astromosaic @Arguments --json 1> $reportPath 2> $logPath
    $code = $LASTEXITCODE
    $result = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
    if ($code -ne 0 -or $result.status -ne 'ok') {
        throw "$LogName failed with exit $code. Read $reportPath and $logPath."
    }
}

foreach ($case in $Cases) {
    $id = $case.case
    $project = Join-Path $Fixtures "$id/$($case.project)"
    $extension = if ($case.images[0].channels -eq 1) { 'fits' } else { 'tiff' }
    $sky = Join-Path $Run "$id-sky.$extension"
    Invoke-RecordedCli "$id-validate" @('project', 'validate', $project, '-o', $sky)
    Invoke-RecordedCli "$id-sky" @('project', 'export', $project, '-o', $sky, '--progress')

    if ($case.foreground_overlap) {
        foreach ($layer in @('foreground', 'composition')) {
            $output = Join-Path $Run "$id-$layer.tiff"
            Invoke-RecordedCli "$id-$layer" @('project', 'export', $project, '--layer', $layer, '-o', $output, '--progress')
        }
    }
    if ($case.zea_project) {
        $zea = Join-Path $Fixtures "$id/$($case.zea_project)"
        Invoke-RecordedCli "$id-zea" @('project', 'export', $zea, '-o', (Join-Path $Run "$id-zea.xisf"), '--progress')
    }
}
```

For a portable pass, point the helper at `astromosaic-cli.exe` and pass the same arguments without `-m astromosaic`. Keep the launcher beside `_internal`. For a fresh Windows installation, use the [distribution acceptance procedure](phase-3f.md#pending-clean-machine-check) and log that installation separately. [CLI result and exit contract](phase-4a.md#result-contract)

## Per-case acceptance

| Case | Actions and pass criteria |
| --- | --- |
| SKY-01 | Reopen the mono FITS export with CFITSIO through `fitsio`. Expect a 1024 × 1320 TAN grid, `FILTER=Ks`, `BUNIT=DN`, and binary `COVERAGE`. In the overlap, stars should register using the supplied atlas WCS. Compare the output sky coordinates at its center and four corners with the grid in `case.json` to within 1e-9 degrees. Treat this as a real geometry and format check. The atlas zero-point match leaves both frames' backgrounds observable. |
| SKY-02 | Confirm B has 16° of rotation and horizontal shear 0.16, equivalent to about 9.09° of detector-axis skew. Both panels must open with embedded WCS. Export the 1540 × 850 TAN mosaic and inspect shared stars and the diffuse band at the seam. Map the prepared FITS panels into the output WCS independently. At interior points supported only by B, compare the export against bilinear interpolation of the prepared B raster within 1e-6 in sample units. B already contains one resampling from fixture preparation. |
| SKY-03 | Export the 1620 × 680 TAN project to RGB TIFF. At zero-based `(x=60, y=68)`, check the covered RGB sample `[-0.125, 0, 1.5]` within 1e-6, and verify the hole at `(90, 100)` is uncovered. Export the supplied ZEA project to XISF and reopen its pixels, coverage and WCS using the [independent attachment reader](../tests/numerical/xisf_reference.py). Check both sides of the 0° longitude wrap in supported regions. Compare TAN and ZEA at the same sky direction when checking samples across projections. |
| MIX-01 | Open `unaligned.astromosaic` and run **Layers → Align Foreground → Match Translations**. Expect B relative to A to shift by (+454, +8) source pixels within 0.5 px on each axis. The embedded WCS gives a different sky offset. Export sky and foreground from the ready project, then export its composition. Confirm the ridge and lights stay in the foreground and the stars stay in the independent sky layer. Inspect all four contribution codes in the composition. |
| MIX-02 | Align the real terrain crops with the provided masks. Expect B relative to A at (+510, 0) pixels within 0.5 px on each axis. Inspect the common telescope domes, the horizon and the Milky Way in the separate layers and composition. The adapted photograph uses a display WCS and relative RGB samples. Use it for masks, registration, and visual blending. Record the supplied original attribution with screenshots. |

For the controlled TIFF checks, reopen exports with tifffile. The first SubIFD holds binary coverage. In a composition the second SubIFD holds `0` uncovered, `1` sky, `2` foreground and `3` both. Verify that the coverage plane equals the nonzero contribution mask. Record `common_pixels` as the full-resolution layer intersection and compare the preview overlap overlay at corresponding sample positions. The ground export is defined in image pixels. The independent sky export carries celestial WCS.

The following independent check exercises the wide signed sample, the invalid patch and the mixed export masks after the PowerShell run.

```powershell
@'
from pathlib import Path
import sys

import numpy as np
import tifffile

run = Path(sys.argv[1])
with tifffile.TiffFile(run / "sky03-wide-rgb-sky.tiff") as tiff:
    page = tiff.pages[0]
    pixels, coverage = page.asarray(), page.pages[0].asarray()
    assert pixels.dtype == np.float32
    assert coverage[68, 60] == 1 and coverage[100, 90] == 0
    np.testing.assert_allclose(pixels[68, 60], [-0.125, 0, 1.5], atol=1e-6, rtol=0)
    assert np.isnan(pixels[100, 90]).all()

for case in ("mix01-synthetic-ridge", "mix02-paranal"):
    with tifffile.TiffFile(run / f"{case}-composition.tiff") as tiff:
        page = tiff.pages[0]
        coverage = page.pages[0].asarray()
        contributions = page.pages[1].asarray()
        assert set(np.unique(contributions)) == {0, 1, 2, 3}
        np.testing.assert_array_equal(coverage, contributions != 0)
'@ | & $Python - $Run
```

## Run the desktop cases

1. Start from the source entry point with `& $Python -m astromosaic.ui --test-secondary-screen`. Use the second monitor when one is available. Run one pass with the default renderer selection and one with `--cpu-preview --test-secondary-screen`. Record the viewport backend shown in the UI.
2. Open each `project.astromosaic`. Confirm that the A and B rows point to the labeled fixture images, both panels have embedded WCS, and the chosen sky projection survives a reopen.
3. Select **Sky** and **Build Preview**. Inspect pan, zoom, automatic framing and display stretch. Export the same layer twice after changing the display stretch. Independently compare sample values and coverage. Save edited copies inside a copied fixture folder so the saved relative paths still resolve.
4. For the mixed cases, begin with **Edit Sky Mask** and check sky, foreground, and the unclassified strip against the label files. On each `unaligned.astromosaic`, run **Layers → Align Foreground → Match Translations** and then **Layers → Propose Placement**. Open **Composition Settings** and adjust the offset, seam and sky crop. Use **Highlight Overlap**, save an edited copy and reopen it. Use the original ready project for the unchanged placement comparison.
5. Export the Sky, Foreground and Composition layers from a ready mixed project. Reopen the desktop and CLI products independently and compare float32 samples with NaNs treated as equal, exact coverage and layer-contribution masks, and the applicable WCS. For preview comparisons, use coincident pixel centers because the viewport preview can be downsampled.

[Mask workflow](phase-3d.md) · [Foreground and composition workflow](phase-3e.md) · [Preview and export workflow](phase-3c.md)

## Recovery and optional solver checks

- Submit a prepared export to an occupied destination and verify exit code 1, an actionable diagnostic, and the original file hash. Exercise a missing source using a disposable copy of a fixture folder, and verify that preflight identifies the missing panel.
- Use a fresh large render from the [Phase 4B benchmark](phase-4b.md) to test cancellation after progress appears. Confirm exit code 130 in the CLI or an explicit cancellation in the desktop. Check for partial outputs, then retry at the same destination.
- Check WCS reuse by running `astromosaic solve` on a prepared SKY-01 input with its embedded WCS. For a new solve with actual catalog stars, use the independently verified 40′ Orion recipe with ASTAP D20 or D50, and compare the saved sidecar with the archive WCS. Keep solver outputs beside disposable copies. [Narrow-field solve evidence](phase-36-results.md#dense-astap-catalog-verification)

## Record results

Record the repository commit, Windows version, launcher and viewport backend, case and variant, input hashes, projection, coverage counts, output paths, elapsed times and diagnostics. Use **Pass**, **Fail** or **Skipped** per case and entry point. Attribute a failed check to the specific layer and format. Capture the manifest, stdout report, stderr progress and a second-monitor screenshot when the failure is visual. Check the input and label hashes again after the run.

### Local baseline

The prepared cases passed five sky preflights and ten source CLI exports. Independent readers reopened the FITS, TIFF and XISF outputs. The packaged CLI produced a byte-identical Paranal composition. The independent narrow-field comparison matched all 1,153 sampled B-only pixels. Native CPU previews passed for the wide RGB sky and the Paranal composition. Qt reported one available display during this run. All 16 focused regressions passed, and a rebuild from freshly downloaded sources reproduced the fixture hashes and overlap counts.

| Case | Covered TAN sky pixels | Covered ZEA sky pixels | Covered foreground pixels | Covered composition pixels |
| --- | ---: | ---: | ---: | ---: |
| SKY-01 | 969,235 | — | — | — |
| SKY-02 | 760,980 | — | — | — |
| SKY-03 | 867,800 | 680,044 | — | — |
| MIX-01 | 417,908 | — | 320,549 | 720,600 |
| MIX-02 | 1,138,045 | — | 319,044 | 1,434,510 |

## Source credits and fixture limits

- **SKY-01** uses separate K-band atlas tiles `ki1350080.fits` and `ki1420198.fits`. The preparation preserves the atlas WCS, scales to a common `MAGZP`, and labels both files in DN. The Two Micron All Sky Survey was a joint University of Massachusetts and IPAC/Caltech project funded by NASA and NSF. [2MASS data at IPAC](https://irsa.ipac.caltech.edu/data/2MASS/docs/) · [Atlas image service](https://irsa.ipac.caltech.edu/applications/2MASS/IM/docs/siahelp.html)
- **SKY-02, SKY-03 and MIX-01** use deterministic synthetic fields with exact capture transforms. Their WCS coordinates provide model geometry for reprojection and alignment. Use the Orion recipe for catalog-solving performance.
- **MIX-02** crops two views from one published sRGB panorama. The preparation applies the inverse sRGB transfer curve, draws terrain masks and assigns a display grid. This covers real scenery texture with controlled offsets. Independent terrestrial captures remain a separate field validation case. **Credit ESO/H.H. Heyer.** [Original Paranal panorama](https://www.eso.org/public/images/vlt-mw-potw/) · [ESO usage terms](https://www.eso.org/public/outreach/copyright/) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
