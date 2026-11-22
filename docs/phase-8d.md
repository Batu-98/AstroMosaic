# Phase 8D Advanced Matching Reference

The first 8D checkpoint freezes data, spatial splits and comparison limits for Advanced photo brightness matching. The offline diagnostic compares global linked RGB corrections with a Standard-style sequential baseline on the same observations. The 8D delivery gate also requires measured optical calibration and production integration. [Phase 8 delivery stages](phase-8.md#delivery-stages)

## Frozen controls

Use the original `tests/20.TIF` and its `768 × 512` detector crop starting at `(2048, 1408)`. The diagnostic checks the original SHA-256 before and after sampling. It decodes the real RGB samples independently, injects known linked gains and backgrounds into overlapping virtual panels, and quantizes the observations to UInt16. Background planes use normalized virtual detector coordinates. The chain has edges A–B and B–C. The cycle adds A–C and injects a plane. D and E overlap each other in both controls and have no path to A. A provides the reference scale. The disconnected group retains identity corrections.

Use the existing PA4 sky manifest for real panels 19–22 on its saved `2097 × 2071` ZEA grid. Sample every eighth output pixel through the saved WCS and sky selections. Exclude saturated source support and samples above 0.075 linear luminance. The diagnostic records source and sidecar hashes, shared sample counts, candidate decisions and final test errors. These four frames provide independent exposures and a real chain at the saved grid scale. Use the existing native-scale stellar geometry gate before accepting an optical correction. [PA4 fixture documentation](application-tests.md) · [Phase 8 geometry qualification](phase-8.md#lens-geometry)

## Selection and acceptance

- Assign whole 64-pixel blocks to fit, model selection or final test with `(block_y + 2 × block_x) modulo 5`. Use remainder 0 for final test, 1 for selection and 2–4 for fitting. A shared location keeps its split across all edges. Require at least 128 samples from at least two blocks in each split to qualify an edge.
- Compare Off, a Standard-style fit using the same splits, global gain and offset, and global gain with an additive plane. Weight each edge equally before robust reweighting. The reference solve uses a 64 MiB dense-fit reservation, a minimum scaled singular-value ratio of 0.015, gains in `[0.25, 4]`, and absolute full-field background bounded by 0.1 in normalized linear units.
- Select a model using mean per-edge selection RGB P95. The offset and plane candidates require 5% and 15% relative improvement respectively, a further absolute reduction above `2e-6`, and no per-edge regression beyond the larger of 5% or `2e-6`. Score the selected model on the untouched final blocks. Keep per-edge scores available when the aggregate improves.
- In the controls, require relative gain error at most 1%, offset and slope errors within `2e-4`, final overlap and diffuse RGB P95 at most `3e-5`, and stellar aperture-flux error at most 1%. Use the held-out C aperture centered at crop pixel `(739, 220)`. Require the same graph, method and values under a different panel order.

Before enabling a production Advanced mode, reproduce improvement over Standard on an independently exposed network with qualified geometry and check stellar flux, diffuse signal, coverage and memory. Include a weak-support case, verify saved-project behavior and run the native preview and copied CLI export from the same build.

## Local results

| Case | Selected model | Largest final overlap RGB P95 | Diffuse RGB P95 | Stellar aperture error |
| --- | --- | ---: | ---: | ---: |
| Controlled chain | Standard | 2.37e-6 | 1.46e-6 | 0.00222% |
| Controlled cycle | Gain and plane | 2.29e-6 | 1.43e-6 | 0.000584% |
| PA4 real chain | Off | 0.03355 | — | — |

The cycle's Standard-style baseline reached 0.00516 on its worst final edge. In PA4, the reference component spans the three adjacent edges. Standard's largest final P95 was 0.03355. Both global candidates exceeded the supported coefficient bounds. All three cases reproduced the same report after reordering inputs. The PA4 replay establishes a conservative fallback control. A positive independent-exposure network and native-scale alignment evidence remain acceptance requirements.

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
.\.venv\Scripts\python.exe -m tools.phase8d_overlap_reference tests/20.TIF --pa4 data/application-tests/owner01-pa4/project.astromosaic -o output/phase8d-references/replay.json
```

Choose a new output filename for each run. Omitting `--pa4` runs the controlled crop only. The local reference report is `output/phase8d-references/reference.json` with SHA-256 `e1f0d3af567db5db5f4a228fa1dba07beb64508075d338bfe95d3cecdc151549`. A separate process reproduced the report byte for byte in 12.27 seconds without a fit cache. The focused 8C and 8D selection passed 13 tests. Ruff, scoped mypy and Poetry lock validation passed. [Diagnostic](../tools/phase8d_overlap_reference.py) · [Controlled regression](../tests/numerical/test_phase8d_overlap_reference.py)

## Independent M31 candidate

Nocturne publishes the M31 Seestar S30 Pro mosaic exposures under CC BY 4.0. The linked ZIP contained 392 FITS entries when inspected. Four entries were acquired from byte ranges and fingerprinted in the local `output/phase8d-candidates/nocturne/source.json` record. All four are independent 10-second IR-cut exposures with distinct pointing and capture times. Two raw overlap edges met the geometry target, forming a three-panel network with B as the connecting panel. [Nocturne M31 observations and license](https://nocturneastro.com/sample-data.html)

The raw pilot used the FITS pointing and pixel scale as hints. ASTAP D05 with Gaia validation yielded SIP-3 solutions for all four frames. The full set includes A as a weaker geometry control. For B, C and D, the derived 2160 × 3840 RGB TIFFs preserve the detector raster and the validated raw WCS. Bilinear Bayer interpolation fills the missing color samples and retains the observed channel samples. The same linear assignment keeps the sensor RGB code scale common to all three panels for relative photometry.

| Overlap | Raw Bayer held-out stars | Raw P95 at 3.7385 arcsec/px | Native-size RGB P95 at 3.7385 arcsec/px |
| --- | ---: | ---: | ---: |
| B–C | 172 | 0.428 px | 0.513 px |
| B–D | 152 | 0.489 px | 0.521 px |
| C–D | 99 | 0.601 px | 0.509 px |

On the three-panel native-size RGB TIFFs, the frozen comparison selected **Off**. Maximum final overlap RGB P95 was 0.001889 with Off and 0.001880 with Standard. Both global candidates lacked independent signal or spatial support at the frozen rank threshold. The earlier four-panel Bayer superpixel version also selected Off. The candidate provides useful independent exposure and geometry evidence. The positive Advanced acceptance case remains open.

The PA4 archive screen found no connection below 0.5 px among all 15 available solved sky panels on the fitted native-scale ZEA grid. KGP and Uludağ supplied separate TIFF candidates and remain without validated sidecars after the local blind and hinted solves. The local Nikon archive contains 30 D5300 raw flat candidates with zero focal-length and f-number metadata. No optical match was established.

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
.\.venv\Scripts\python.exe -m tools.phase8d_overlap_reference tests/20.TIF --project output/phase8d-candidates/nocturne/native/comparison.astromosaic -o output/phase8d-candidates/nocturne/native/replay.json
```

The local project uses the native-size RGB TIFFs and a fixed 7.477 arcsec/px comparison grid to bound sky sampling. `native/geometry.json` holds the separate native-scale stellar checks, and `native/comparison.json` holds the photometry and source fingerprints. Use individual source frames from the public archive when reproducing the candidate. A finished mosaic combines the exposures and loses the separate overlap measurements.

### Separate M31 pointing stacks

The follow-up selects the eight nearest 10-second IR-cut observations from the 15 archive entries surrounding each B, C and D reference exposure. The selection radius was fixed at 0.55°. The most distant selected exposures were 0.486°, 0.442° and 0.425° from their respective reference positions. The three groups share no exposures. All 24 passed catalog validation and the solver's field-edge check. The local `nocturne/stacks/selection.json` records archive entries, CRC32 and SHA-256 values.

Reconstruct the detector-sized RGB rasters with the single-frame Bayer interpolation. Within each group, reproject to its reference detector WCS in 256-pixel tiles and combine by per-channel median. Include a pixel in the stack if at least six exposures support it. Publish the 16-bit RGB samples with a separate binary coverage image. Measure inter-stack alignment at 3.7385 arcsec/px and sample photometry on the 7.477 arcsec/px comparison grid. Use the frozen fit, selection and final-test splits for the brightness comparison.

| Stack | Covered pixels | Median green-channel noise reduction | Median aperture flux change against its reference exposure |
| --- | ---: | ---: | ---: |
| B | 6,635,988 | 2.54× | −5.71% |
| C | 6,686,351 | 2.53× | −4.68% |
| D | 7,001,945 | 2.54× | −1.28% |

All three edges met the 0.5 px geometry target. Held-out P95 was 0.274 px for B–C (187 stars), 0.228 px for B–D (174 stars), and 0.232 px for C–D (124 stars). Estimate noise from the high-pass green-channel MAD in 40 fixed fully supported blocks per stack. Measure the aperture comparison at matched held-out stars using the same radius of seven pixels and a sky annulus of 9–13 pixels in the coadd and its reference exposure. This check measures the effect of stacking relative to an individual exposure. A known flux reference is still needed to establish absolute flux preservation.

Standard lowered mean per-edge RGB P95 by 4.95% on the model-selection regions and 4.84% on the untouched final regions. The final mean went from 0.00072324 with Off to 0.00068827 with Standard. The selection threshold called for at least 5% plus the frozen absolute margin. Across 22,152 fit rows, the scaled singular-value ratios were 0.01224 for gain and offset and 0.01137 for gain and plane. Both fell below the 0.015 support threshold. The diagnostic selected **Off**.

Independent TIFF reopening matched the binary coverage, corner WCS and the median RGB codes at 36 positions per stack. All 24 source SHA-256 values matched. Eight focused tests passed. The saved project replay reproduced the comparison, including the order-independence result. The project and evidence are under `output/phase8d-candidates/nocturne/stacks/products/`. Use `--project` with `comparison.astromosaic` to replay. `comparison.json` has SHA-256 `8cc5b2e3bdd58182b1fad022946e902accec5762034a7ef4f749953436e590d5`.

## Independent calibrated SDSS panels

Use the public SDSS corrected frames in native nanomaggies. Assemble separate RGB panels from each scan's i, r and g frames on that scan's r WCS. M2 uses runs 2583, 4187 and 4192, camera column 2, fields 136, 104 and 111. M77 uses runs 94, 259 and 1752, camera column 3, fields 439, 227 and 132. The three scans in each field have distinct acquisition dates. The source FITS primary arrays and SHA-256 values remain local. Register the channels with the recorded WCS, then encode each calibrated value as `0.04 + flux / 4` for the common linear UInt16 test representation. Flag samples outside the encodable range or without full channel support. This encoding preserves a common relative scale for the three panels. The RGB channel assignment is for this diagnostic. [SDSS imaging tools](https://www.sdss.org/dr20/imaging/tools/) · [SDSS archive frame access](https://www.sdss.org/dr20/data_access/get_data/) · [SDSS attribution](https://www.sdss.org/collaboration/citing-sdss)

| Scene | Native overlap positional P95 | Final mean RGB P95 Off | Standard | Gain and offset | Fixed-gain plane |
| --- | ---: | ---: | ---: | ---: | ---: |
| M2 | 0.269–0.344 px | 0.012833 | 0.011253 | 0.010649 | 0.012491 |
| M77 | 0.477–0.634 px | 0.015584 | 0.012832 | 0.011686 | 0.015492 |

M2 passed the native 0.5 px geometry gate on all edges. The gain-and-offset candidate passed overlap-only selection and reduced final mean RGB P95 by 5.36% versus the reference Standard fit. It applied gains of 0.656 and 0.627 to the two peers. Relative aperture-flux medians on the reference edges shifted from +0.71% and −1.56% before correction to −33.96% and −38.30%. The exact aperture audit used a fixed seven-pixel radius and a 10–13-pixel sky annulus, with stars in the final spatial blocks and the brighter half of usable apertures. This rejects the apparent overlap improvement as a positive Advanced result. M77 supplied secondary evidence of the same flux problem and failed the full geometry gate.

The new diagnostic option keeps both the free-gain and fixed-gain results. The fixed-gain plane changed the M2 bright-star flux ratios by at most 0.21% at P95 relative to Off, but improved final mean RGB P95 by only 2.66% versus Off. The fixed-gain candidates selected **Off** in both fields. A source CLI export also reproduced the issue in the current Standard implementation: the M2 run-4187 panel received a gain of 0.636. The CLI uses a different overlap sampling setup from this reference tool. Track stellar constraints on inferred gains for both methods before release changes.

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
.\.venv\Scripts\python.exe -m tools.phase8d_overlap_reference tests/20.TIF --project output/phase8d-candidates/sdss/m2/comparison.astromosaic --preserve-calibrated-scale -o output/phase8d-candidates/sdss/m2/replay.json
```

The local folders under `output/phase8d-candidates/sdss/` contain the two prepared projects, source manifests, model scores, reserved aperture audit and native geometry. Reopening the TIFFs verified binary coverage, native WCS, and the r-channel encoding at 1,231 covered positions. All 18 source hashes matched. The PA4 frozen report reproduced byte for byte after adding the optional comparison. Nine focused tests passed, including recovery of a known background plane with gains locked to unity.

## Independent stellar gain qualification

The optional `--stellar-gain` comparison screens inferred gains before selecting a sky model. The existing result remains under `selected`. The guarded choice and the separate final stellar scores appear under `stellar_gain`. Use these measurements with comparably sampled panels in the same band and the separate native-scale geometry checks. [Stellar check](../tools/phase8d_stellar_gain.py)

- Match isolated detections one to one on the comparison WCS. Measure the original linear working samples with a seven-detector-pixel aperture and a 10–13-pixel local sky annulus. Require valid, unsaturated support, positive flux in all channels and a luminance flux above ten times the local robust aperture noise estimate.
- Keep the full projected aperture and annulus inside the matching 64-pixel spatial block. Use remainder 1 to screen sky-fit candidates and remainder 0 for the untouched stellar test. The sky coefficients use remainders 2–4.
- For a relative gain change above a factor of 1.01 in either direction, require at least eight matched stars across at least three selection blocks on each affected edge. Give each block equal weight. The median corrected log flux ratio must be within `log(1.05)` of zero. The 80th percentile of the absolute block log ratios must be at most `log(1.12)`. The median absolute log discrepancy may increase by at most `log(1.02)` versus Off.
- Select among the eligible sky candidates using the existing RGB residual margins. Apply the same stellar criteria on the test blocks for reporting. A unity-gain model makes no inferred gain change. The direct effect of additive backgrounds on measured aperture flux is covered by the separate fixed-gain aperture audit above.

| Case | Guarded choice | Stellar result |
| --- | --- | --- |
| Calibrated SDSS M2 | Off | Standard, global gain-and-offset and global gain-and-plane were rejected on both splits. The current application Standard gain of 0.636 was also rejected. |
| Independent M31 pointing stacks | Off | Standard had unity gains. Both free global candidates lacked sky-fit rank. |
| Real owner crop with injected terms | Standard or gain and plane, according to the injection | Both selection and final apertures accepted the true gain changes. All final edge medians were within 1% of unity. |

On the M2 run-2583–4187 edge, 35 selection stars in 13 blocks and 40 final stars in 14 blocks supported the decision. The final block-median flux ratio was 1.0175 with Off, 0.6672 with the global gain-and-offset candidate and 0.6470 with the application Standard gain. The application audit scores the existing export's gain with the same apertures. The application uses its own sky sampling split. The wider injected control uses the original `20.TIF` region `(2048, 1408, 1536, 1024)` with three overlapping detector crops and the known gains 1.00, 1.25 and 0.84. Separate cases inject constant and planar skies. A ten-star, single-block control checks insufficient spatial support. [Focused regressions](../tests/numerical/test_phase8d_stellar_gain.py)

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$m2 = 'output/phase8d-candidates/sdss/m2'
.\.venv\Scripts\python.exe -m tools.phase8d_overlap_reference tests/20.TIF --project "$m2/comparison.astromosaic" --preserve-calibrated-scale --stellar-gain --audit-standard-export "$m2/standard-export.json" -o "$m2/stellar-gain-replay.json"
```

The M2 report replay matched byte for byte. The M31 report is in `output/phase8d-candidates/nocturne/stacks/products/stellar-gain.json`. Sixteen focused tests passed, and the legacy PA4 report retained its original SHA-256.

`standard-export.json` is the preserved beta 14 export. Use the current source or beta 15 command below to verify the production fallback.

## Standard photo gain integration

Standard uses the existing sky fit and held-out RGB model selection. A candidate changing the scale by more than a factor of 1.01 also has to pass the matched-star check. Each native aperture and its clipping halo use detector samples outside the source reads for both sky splits in that pair. The check compares the exposure-normalized fluxes on the current reference edge and screens for comparable native scales. The shared job tries an accepted sky offset or identity when stellar support is insufficient or the gain is rejected. It can use a different connected peer when appropriate. The preview, output JSON and TIFF history report the effective method. The JSON keeps the first rejected check and peer in `rejected_gain`. [ADR-0030](adr/0030-independent-stellar-support-for-photo-gains.md)

```powershell
$m2 = 'output/phase8d-candidates/sdss/m2'
.\.venv\Scripts\python.exe -m astromosaic project export-photo "$m2/comparison.astromosaic" -o "$m2/standard-guarded.tiff" --brightness standard --progress --json
```

Advanced still needs a positive independent-exposure network, and the optics acceptance requires a measured calibration.

### Standard local Windows results

The source and copied beta 15 console agreed on the effective methods, verified RGBA samples, coverage, ICC tag and WCS. The copied desktop used both native CPU and OpenGL previews on the second monitor. Its M2 and mixed-ICC exports matched the source and console pixel for pixel. The desktop title and CLI reported `0.1.0b15`.

| Case | Effective result | Stellar evidence |
| --- | --- | --- |
| Calibrated SDSS M2 | Unity gains on all three panels and two offset-only corrections | The 0.63585 candidate was rejected using 147 stars in 53 cells. Its median flux deviation would move from +1.96% to −35.17%. |
| Owner crop with mixed ICC profiles | Standard gain 1.24991 | 11 stars in 10 cells. |
| Owner crop with masked contamination | Standard gain 1.25000 | 8 stars in 8 cells. |

The three exports used at most 26.1 MiB of the 64 MiB working reservation. The 8C source replay passed all frozen exposure and color cases and checked the original hashes again. The PA4 offline report retained its original SHA-256. The source tests also exercise cancellation at the stellar stage and fallback for a star-free overlap. [Windows build record](windows-release.md#verification-status) · [Source regression](../tests/numerical/test_phase8d_stellar_gain.py)

## Optical calibration intake

The PA4 working set has saved SIP solutions and source camera hints. A search of the local reference data and the capture's processing folders found no matching master flat or standalone measured lens calibration. Inspection of frames 19–22 in two DNG variants found `OpcodeList2` with three opcode ID 8 entries. The inspected opcode lists specify per-area polynomial level mappings. They supply no geometric warp or gain map, and the DNG-to-TIFF correction history remains unresolved. [Adobe DNG specification, Chapter 7](https://helpx.adobe.com/content/dam/help/en/camera-raw/digital-negative/jcr_content/root/content/flex/items/position/position-par/download_section_733958301/download-1/DNG_Spec_1_7_1_0.pdf#page=114)

Record the original detector frame, crop and orientation, focal length and aperture, calibration provenance and prior corrections for the first imported candidate. Require one geometric mapping, unchanged source pixels, and detector-wide reserved stars that meet the native overlap gate. For an illumination candidate, require a matched flat or measured transmission map, normalization and mask checks, independent sky and aperture validation, and a check against duplicate correction. Evaluate coverage and real-tile resource use before packaging each accepted method. [Optics tracking](../questions_open_topics.md#q-029---configurable-color-photometry-and-optics)
