# Phase 8 photo mosaic findings and recommendations

- **Review date** 2026-11-22
- **Investigation baseline** AstroMosaic `0.1.0b12`, Phase 8B full-resolution sRGB photo export
- **Verified follow-up** AstroMosaic `0.1.0b13`, built from `7083c6f3b9947ff73c2fda67c7acd3364d10179a`
- **Real-observation inputs** `tests/20.TIF` and `tests/21.TIF`

[Phase 8 specification](phase-8.md) · [Photo TIFF decision](adr/0028-transparent-photo-tiff.md) · [Windows build records](windows-release.md#verification-status) · [Q-029](../questions_open_topics.md#q-029---configurable-color-photometry-and-optics)

## 1. Executive summary

The beta 12 export showed a lifted sky background, black canvas around the panels and hard transitions within the overlap. Beta 13 completes the tone and transparency fixes for the local Phase 8B delivery. On the preserved-tone mosaic, the held-out stellar displacement has a P95 of 0.751 px. A trial translation brings it to 0.662 px, above the 0.5 px starting target. The overlap also shows measurable panel-edge steps. [Beta 13 verification](phase-8.md#8b-photo-tone-and-transparency-follow-up) · [Owner overlap baseline](phase-8.md#8b-owner-overlap-baseline)

## 2. Empirical comparison

The inputs are 6000 × 4000 UInt16 sRGB TIFFs developed in Adobe Camera Raw from Nikon D5300 exposures. The two exports use the same 8917 × 10259 TAN grid and valid sky coverage. The beta 13 file was rendered from the original panels and is available locally at `output/phase8b13/Photo-mosaic-preserved-transparent.tiff`. [Original panel and grid evidence](phase-8.md#8a-frozen-photo-export-contract)

| Property | Beta 12 `tests/GHGH.tiff` | Beta 13 photo TIFF |
| --- | --- | --- |
| Tone mode | Use Preview Tone, midtones 0.25 | Preserve Tone, default |
| Samples | UInt16 RGB with a binary 0/1 coverage SubIFD | UInt16 RGBA with associated alpha |
| Covered pixels | 43,897,047 | 43,897,047 with alpha 65,535 |
| Uncovered pixels | 47,582,456 displayed as black | 47,582,456 with alpha 0 |
| Sampled median encoded value | 33,410 DN | 7,878 DN |
| Covered pixels with at least one channel at 65,535 | 228,623 | 5,844 |
| File size | 640,362,687 bytes | 731,841,752 bytes |

The median uses Rec. 709 channel weights on encoded RGB codes sampled every 16 pixels at shared valid positions. The full-scale count covers every valid position. These measurements describe the exported files and quantify how strongly the preview tone affected the same image content. [Full-resolution comparison](phase-8.md#8b-photo-tone-and-transparency-follow-up)

## 3. Root causes and corrections

### 3.1 Black canvas outside the panels

Beta 12 stored validity as a grayscale 0/1 SubIFD and wrote zero RGB codes outside coverage. Photoshop opened the primary RGB image as an opaque layer at 100% opacity. The owner saw a black border around the projected panels.

Beta 13 stores validity in the fourth UInt16 sample using TIFF associated alpha (`ExtraSamples = 1`). Covered black retains alpha 65,535. Transparent pixels carry zero alpha and zero RGB. The photo reader also reopens beta 11 and 12 exports using their SubIFD coverage. [TIFF writer](../src/astromosaic/io/tiff_export.py) · [TIFF reader](../src/astromosaic/io/tiff.py) · [ADR-0028](adr/0028-transparent-photo-tiff.md)

### 3.2 Brightened background and highlight clipping

Beta 12 defaulted to **Use Preview Tone**. The export applies a black point and white point from the 1st and 99.5th percentiles of the covered preview, clips normalized values to the unit range, applies the midtones transfer, and encodes sRGB. In `GHGH.tiff`, the black and white points were approximately 0.001826 and 0.134781 in linear light. With the recorded midtones value of 0.25, a 7,000 DN sample taken at its original pixel center maps to approximately 30,536 DN before blending with other panels. Values clipped to either end of the range share an output code. Re-exporting from the original panels recovers the gradations collapsed by that stretch. [Photo tone implementation](../src/astromosaic/photometry/photo.py)

Beta 13 uses **Preserve Tone** by default in the desktop and CLI. It decodes sRGB, samples and blends in linear light, then encodes sRGB with the embedded `sRGB2014.icc` profile. Reprojection can change local samples even in regions covered by a single panel. Compare output codes at matching positions on the same WCS grid. [Photo export contract](phase-8.md#8b-photo-tone-and-transparency-follow-up)

### 3.3 Hard transitions around panel boundaries

The renderer normalizes each panel's scalar weight over valid contributors. When two equally weighted panels contribute, the output is $(P_1 + P_2)/2$. Crossing the edge of panel 1 leaves $P_2$, so a local brightness difference produces a step at the boundary. The owner observed these transitions in the overlap.

The renderer currently limits scientific relative refinement to its supported linear workflows. Possible contributors to the observed differences include registration residuals, light pollution or exposure differences, and residual vignetting after the source development. Measure their contribution on the owner pair. [Weighted tile renderer](../src/astromosaic/pipeline/mosaic.py) · [Photo blending methods](phase-8.md#blending-methods)

## 4. Export workflow in beta 13

1. Open the saved project with the original TIFFs and solved WCS, or solve the pair again from the source panels.
2. Choose **Build Preview**, then **Export Photo Mosaic** with the default **Preserve Tone** and a new TIFF path.
3. Open the TIFF in Photoshop. The panel footprints occupy the visible layer and the uncovered area is transparent.

The CLI uses the same default. Select preview tone when a rendered display stretch is desired. Existing calls that supply `--midtones` alone select preview tone.

```powershell
astromosaic project export-photo "Solved.astromosaic" -o "Mosaic.tiff"
astromosaic project export-photo "Solved.astromosaic" -o "Stretched.tiff" --tone preview --midtones 25
```

[Desktop and CLI workflow](phase-8.md#8b-export-a-photo-mosaic)

## 5. Recommendations for the overlap work

### 5.1 Preserved-tone baseline measured

The replay measured 221 matched, unclipped stars and 697 paired background samples after masking detected stars and saturated samples. At the right edge of `21.TIF`, 59 crossing strips showed a median linear luminance step of +0.00301 and a P95 absolute step of 0.01204 on the unit scale. [Method, source and reproduction](phase-8.md#8b-owner-overlap-baseline)

The regional holdout found an upper-right owner overlap P95 of 0.941 px. The whole-overlap P95 was 0.692 px with the saved WCS, 0.713 px with translation and 0.757 px with similarity. The same-camera PA4 pair also stayed above the 0.5 px target. The independently exposed ALPACA control measured 0.179 px with the saved WCS. [Spatial holdout and control results](phase-8.md#8b-spatial-holdout-and-alignment-controls)

The fixed-star Gaia comparison found a lower catalog P95 on all four panels with the linear-light SIP-3 refit. The independent overlap P95 was 0.700 px for the owner pair and 1.200 px for PA4. Both remained above the 0.5 px target. Use the geometry results for the later optical comparison and prepare independent ICC and exposure controls for 8C. [Gaia holdout results](phase-8.md#8b-gaia-holdout-for-wcs-candidates)

### 5.2 Evaluate distance-transform feathering

After measuring alignment and background agreement, try a photo blend weight based on distance from the valid source boundary. A candidate is the clipped cosine ramp $w(d) = [1 - \cos(\pi \min(d/W, 1))]/2$, where $W$ is the transition width in source pixels. Sample the weights with the image, multiply by the panel weight and normalize across valid contributors in linear light. Preserve sole-contributor pixels and use the validity-weighted mean where the candidate weights sum to zero.

Test narrow overlaps and holes in coverage. Use bounded windows and halos for the distance calculation, and compare full exports with matching crops and different tile splits. Keep the output alpha tied to valid coverage. [Phase 8 blending methods](phase-8.md#blending-methods)

### 5.3 Qualify exposure matching and vignetting

Stage 8C qualifies profile assignment, ICC conversion and documented exposure and brightness methods. Test relative gain and background offsets on held-out overlap samples. Stage 8D adds qualified optical corrections such as a matched flat or verified lens profile. A low-order radial response such as $V(r) = 1 + k_1 r^2 + k_2 r^4$ requires broad sensor-radius coverage and evidence of improvement on held-out samples. Check the source processing history before applying an illumination correction. [Phase 8 delivery stages](phase-8.md#delivery-stages) · [Vignetting methods](phase-8.md#vignetting-and-flat-field-correction)

The 8C references now include independent color patches and a registered real sky crop with known exposure changes, reserved regions and weak-support cases. The two owner TIFFs record equal capture settings. [Frozen color and exposure references](phase-8.md#8c-frozen-color-and-exposure-references)

### 5.4 Evaluate multiband blending when the baseline warrants it

Stage 8E can compare broader low-frequency transitions and narrower high-frequency transitions on calibrated, well-aligned overlaps. Measure stellar aperture flux, FWHM and any double or blurred stars, along with the remaining seam and diffuse-signal residuals. Verify the tile halos and memory costs against the simpler blend. [Phase 8 blending methods](phase-8.md#blending-methods)

## 6. Verification and acceptance

### Beta 13 local evidence

- The full-resolution export matched every RGB code in the earlier Preserve Tone reference, its WCS at the comparison points, its embedded ICC profile and its binary coverage through alpha. Both original input hashes matched their frozen references.
- Photoshop 27.7 opened the full TIFF as a 16-bit layer with transparency. A PNG crop reproduced the coverage at the footprint boundary. A separate probe verified that covered black stays opaque.
- Packaged CPU, OpenGL and CLI exported byte-identical real footprint crops that matched the corresponding full TIFF region. Nine real scientific products matched their reference samples and masks.
- The source suite passed 235 checks with two native skips offscreen. Three native checks passed separately. Ruff, scoped mypy, Poetry lock validation and launcher checksum verification passed.

[Full verification and compatibility](phase-8.md#8b-photo-tone-and-transparency-follow-up) · [Local launchers](windows-release.md#verification-status)

### Evidence required for the next photo blend

| Area | Comparison |
| --- | --- |
| Seam and background | Measure the baseline and compare changes across real overlap boundaries on the same WCS. Set the seam target after measuring the baseline and independent controls. |
| Stars and diffuse signal | Track median and P95 stellar residuals, aperture flux, FWHM and diffuse-region brightness. Start with the plan's 0.5 px geometry and 1% aperture-flux targets for comparable well-sampled controls. |
| Coverage and WCS | Confirm exact coverage, opaque covered black, transparent gaps, preserved WCS and corresponding preview or crop samples. |
| Resource and failure behavior | Check the configured tile reservation, including the 64 MiB default, measure actual process memory and runtime, and exercise cancellation, cleanup and retry. |

[Phase 8 reference cases and measurements](phase-8.md#reference-cases-and-measurements)
