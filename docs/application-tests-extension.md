# Ten additional AstroMosaic application cases

The extension adds seven sky cases and three wide-angle nightscapes. Each required sky or ground connection has at least 10% overlap. SKY-04 uses 2MASS atlas tiles from three scans. The other cases use deterministic synthetic captures with known geometry, sample values, or mask boundaries.

## Prepare the fixtures

The local pack is at `data/application-tests/extended/`. Open `contact-sheet.png` to identify each labeled image. Each case folder has a ready `project.astromosaic`, source images and a `case.json` containing hashes, overlaps and geometry. The nightscapes also have an `unaligned.astromosaic` and per-panel `*.labels.fits` masks.

Use the ready pack when available. From the checkout root in PowerShell 7 with the locked Python environment, use the following commands for a fresh build and source CLI run. Omit `--download` when the three pinned atlas files are cached. To rebuild beside an existing pack, supply a new `--output` to the generator and pass that directory to the checker with `--fixtures`.

```powershell
$Python = (Resolve-Path '.venv/Scripts/python.exe').Path
& $Python tools/prepare_application_test_extension.py --download
$Run = 'output/application-tests/extended-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
& $Python tools/check_application_test_extension.py --output (Join-Path $Run 'source')
```

The checker runs sky preflight, export and independent file checks. It saves each CLI JSON response and progress log, along with a `results.json` summary. Supply `--launcher <path-to-astromosaic-cli.exe>` and a fresh output directory for the portable pass. Keep the executable beside its `_internal` directory. SKY-09 records a fresh XISF creation timestamp on each rebuild, so use the hashes from that build's manifest. [Generator](../tools/prepare_application_test_extension.py) · [Checker](../tools/check_application_test_extension.py) · [Base cases](application-tests.md)

Sky percentages use the shared nearest-sample footprint divided by the smaller panel's valid footprint on the saved grid. Foreground percentages use the same denominator in ground coordinates with the known crop offsets and foreground masks. The table gives the smallest overlap needed to connect a case or band. Panel pairs within a chain can have zero direct overlap if the middle panel connects them.

| Case | Folder | Inputs | Sky overlap | Ground overlap |
| --- | --- | --- | ---: | ---: |
| SKY-04 | `sky04-atlas-chain` | Three 512 × 1024 mono FITS atlas tiles | 11.57% | — |
| SKY-05 | `sky05-polar-rotation` | Two mono FITS with rotated polar views | 44.38% | — |
| SKY-06 | `sky06-mixed-scale` | Two narrow mono FITS at different scales | 41.50% | — |
| SKY-07 | `sky07-wide-sip` | Two wide RGB TIFFs with TAN and TAN-SIP WCS | 47.20% | — |
| SKY-08 | `sky08-scaled-fits` | Two 448 × 298 signed int16 FITS | 40.69% | — |
| SKY-09 | `sky09-xisf-holes` | Two 525 × 372 RGB panels, TIFF and XISF | 41.17% | — |
| SKY-10 | `sky10-filter-bands` | Two mono H-alpha FITS and two RGB O III TIFFs | 42.86% | — |
| MIX-03 | `mix03-diagonal-ground` | Two 630 × 510 RGB TIFFs | 55.91% | 54.46% |
| MIX-04 | `mix04-cropped-seam` | Two 660 × 505 RGB TIFFs | 47.12% | 55.32% |
| MIX-05 | `mix05-panel-chain` | Three 640 × 500 RGB TIFFs | 38.33% | 34.41% |

## Acceptance by case

| Case | Actions and expected results |
| --- | --- |
| SKY-04 | Export the 1470 × 1330 TAN FITS with `FILTER=Ks` and `BUNIT=DN`. Compare bright features in the two common WCS regions. The A–B and B–C edge supports are 11.57% and 12.01%. A and C have zero common support. Require each pair's bright-sample correlation to reach 0.8 and inspect both seams. |
| SKY-05 | Export the 976 × 650 TAN FITS with 17° output rotation. Panel B is rotated by 26° relative to A. Verify covered directions at RA 0°, 90°, 180° and 270° at Dec +89.98°. These world-to-pixel-to-world checks should agree within 1e-9 degrees. |
| SKY-06 | Export the 1060 × 660 TAN FITS at 0.92 arcseconds per output pixel. Compare the measured relative source scale matrix with `panel_b_to_a_matrix` in `case.json`. B uses unequal axis scales and 0.30 horizontal shear before its −23° rotation. Check both a one-panel region and the overlap against bilinear source samples. |
| SKY-07 | Verify that B carries third-order SIP coefficients and A carries TAN. Export the 1260 × 750 ZEA TIFF. Check coverage at RA 359.8° and 0.2° at Dec +18° and compare input SIP mappings to exported sample values. |
| SKY-08 | Export the 766 × 398 TAN FITS. Compare the `case.json` checks in zero-based coordinates. Expect −5 and a covered zero in A, 13.25 in a 1:3 weighted overlap, and 10 where B supplies a sample at A's BLANK. The A-only BLANK patch has zero coverage and NaN. |
| SKY-09 | Export the 650 × 650 TAN mosaic as XISF. Verify that the TIFF alone supplies `[0, 0.5, 2]` at (480, 320), the XISF-only hole at (150, 539) is uncovered, and (315, 555) retains `[-0.02, 0, 2.45]`. The XISF input's coverage attachment excludes deliberately bright samples in both holes. |
| SKY-10 | List membership with `project bands`. H-alpha uses panels 1 and 2, including one saved override. O III uses panels 3 and 4. Render the two bands on the same 806 × 436 cropped ZEA grid. H-alpha is mono in `MJy/sr` and O III is RGB in `Jy/sr`. An unknown band should fail preflight and name the selection. |
| MIX-03 | Align foreground in `unaligned.astromosaic`. B's ground shift is (−288, −45) source pixels within 0.5 px on each axis. The sky offset is (−282, −29). Export independent sky, foreground and composition TIFFs. The composition should contain all four contribution codes. |
| MIX-04 | Align the ground pair at (+326, −4) px within 0.5 px on each axis. Verify a normal composition from the ready project. Open `project-gap.astromosaic` and check that the saved sky crop and ground shift produce a visible gap. Expect common coverage of zero and contribution codes 0, 1 and 2. Opening the ready project restores common coverage. |
| MIX-05 | Recover ground offsets of (0, 0), (+358, +25) and (+736, 0) px within 0.5 px on each axis. Verify separately connected sky and ground mosaics. In a disposable project with only A and C, foreground alignment should report weak or disconnected overlap. |

For all sky exports, independently compare WCS at the center and corners to 1e-9 degrees. For interior samples with unambiguous coverage, bilinearly sample the original panels and normalize by their saved weights. The checker uses an absolute tolerance of 2e-6 plus a relative tolerance of 2e-7 for float32 roundoff. At positions where only some interpolation neighbors are valid, use the explicit hole and BLANK checks above.

The FITS `COVERAGE` extension, TIFF first SubIFD, and XISF coverage attachment must contain binary uint8 values. Scientific rasters use float32 and contain finite values at covered pixels and NaN elsewhere. The TIFF second SubIFD for a composition uses `0` uncovered, `1` sky, `2` foreground, and `3` both. Compare its nonzero positions with coverage. The CLI's `common_pixels` counts positions supported by both layers before feathering.

## Native desktop pass

1. Start with `& $Python -m astromosaic.ui --test-secondary-screen`. Repeat from a clean launch with `--cpu-preview --test-secondary-screen`. Use the second monitor when available and record the actual viewport backend.
2. Open each ready project with **File → Open Project**. Check all expected source rows and embedded WCS. Select **Sky**, build the preview, and export to the format listed above. Confirm that the desktop result matches the CLI's scientific samples, masks, and WCS.
3. For SKY-10, choose each **Sky band** before preview or export. Use FITS for H-alpha and TIFF for O III.
4. For the mixed cases, open the unaligned variant and inspect the external mask files against the saved editor labels. Run **Layers → Align Foreground** and compare the known shifts. Reopen the ready project to preview and export Sky, Foreground and Composition. Check the two MIX-04 variants and the overlap overlay.
5. Put any edited project copies in the same case folder so its relative sources resolve. Store exports separately. Record the project variant, actual renderer, output sizes, overlap or coverage findings and any diagnostics. Check the source image and mask hashes after running the cases.

The 2MASS case preserves archive WCS and scales to a common `MAGZP`. The Two Micron All Sky Survey was a joint UMass and IPAC/Caltech project funded by NASA and NSF. The file URLs and SHA-256 values are pinned by the generator. [2MASS data at IPAC](https://irsa.ipac.caltech.edu/data/2MASS/docs/) · [Atlas image service](https://irsa.ipac.caltech.edu/applications/2MASS/IM/docs/siahelp.html)
