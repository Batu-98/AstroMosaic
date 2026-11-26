# Phase 8D Advanced Matching Reference

**Disposition** Phase 8 closed on the locally verified beta 15 scope. The experiments below preserve the original acceptance criteria and evidence for deferred methods. [Phase 8 closure](phase-8.md#phase-8-closure)

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

### Reference input preparation

Original exposures, calibrated images and independently integrated panel stacks can supply this comparison. Record the source exposures, calibration, stacking, any resampling and the effective color transfer. Use disjoint observations for each panel and preserve the relative sky variation on a common linear RGB scale. Keep panels with per-panel sky removal or local tonal edits for the geometry, preview or export cases their processing supports.

The public library adds seven native-size 20 mm and 35 mm photo panels and a two-pointing MOANA reference with separate exposures across multiple nights. Verify geometry and the existing selection and acceptance limits on each candidate. The wide-angle TIFF preparation preserves the original lens mapping. [Public observation library](public-test-data.md)

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

### Restored SDSS sky backgrounds

The M2 and M77 FITS files also retain the sky that SDSS removed from each observation. Reconstruct it by bilinearly interpolating `ALLSKY` at the detector coordinates in `XINTERP` and `YINTERP`, holding the nearest edge value outside the low-resolution map. Multiply each detector sample by its calibration-vector value before projecting it onto the comparison grid. Adding that sky back to HDU0 retains the calibrated flux scale and exposes the actual differences in observing background. The sky-subtracted HDU0 gives a same-scan reference. [SDSS frame data model](https://data.sdss.org/datamodel/files/BOSS_PHOTOOBJ/frames/RERUN/RUN/CAMCOL/frame.html)

The diagnostic samples i, r and g separately on the saved comparison grid with the original `0.04 + flux / 4` encoding, eight-pixel stride and 64-pixel spatial splits. It takes the native geometry qualification from the preceding comparison. The sky fit uses the common faint, encodable support from HDU0. The diffuse check compares the corrected pair differences to the HDU0 pair differences in the final blocks. This measures the relative background error independently of the two scans' differing celestial samples. The stellar check remeasures the same native r-grid apertures before and after correction within final blocks. It also reports the peer-based gain check on separate selection and test apertures from the prepared TIFFs. [Restoration diagnostic](../tools/phase8d_sdss_sky.py)

| Scene | Final mean RGB P95 Off | Standard | Unity-gain global offset | Unity-gain global plane | Largest per-panel aperture error P95 across models |
| --- | ---: | ---: | ---: | ---: | ---: |
| M2 | 0.067232 | 0.037985 | 0.038011 | 0.037971 | 0.741% across 233 apertures |
| M77 | 0.097894 | 0.062402 | 0.062442 | 0.062345 | 0.965% across 80 apertures |

The stellar-guarded selection chose Standard with unity gains in both fields. The free-gain candidates lacked fit rank. In M2 the unity-gain plane lowered the mean RGB P95 by 0.31% versus Standard in selection and 0.036% in the final blocks. It fell short of the frozen improvement margin. M77 also fell short and remains a geometry-negative control. The M2 diffuse P95 with the plane was 0.01167–0.03870 by edge. The archived sky differences have a color component. At unity gain, the best scalar correction at each location leaves at least half the RGB range in one channel. The median of that lower bound was 0.00440–0.03255 across the three M2 edges. All candidates preserved the sampled coverage masks and reversing panel order reproduced the same fit.

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$sdss = 'output/phase8d-candidates/sdss'
.\.venv\Scripts\python.exe -m tools.phase8d_sdss_sky "$sdss/m2/comparison.astromosaic" "$sdss/source-m2.json" "$sdss/raw" -o "$sdss/m2/sky-qualification-replay.json"
```

Choose a new output filename on each run. Substitute `m77` for `m2` to replay the second field. Use the local source-manifest and prepared-project files from the calibrated comparison above. Both reports and the frozen PA4 report reproduced byte for byte. The reference `sky-qualification.json` SHA-256 values are `ad91891600e3d4fc11de645170a781acfe58de44a6f55577567f02ef1d94ac3d` for M2 and `be6a591bbe504559e210ff89d700616acc0a6cb7f9a2f3a730e4dfad1c76e201` for M77. A positive case for linked Advanced still requires compatible channel backgrounds and sufficient spatially varying sky signal. Full-resolution export, native preview and measured optical calibration remain separate acceptance checks.

## Origin broadband exposures and detector flat

The OriginStack M51 and M37 archives provide raw broadband Bayer exposures and the calibration files included with each session. Verify the publisher's archive SHA-256 before using them. For the initial screen, sample seven exposures spread over each session and choose the first, middle and last of those seven for photometry. The two triplets are `Light0005`, `Light0112`, `Light0217` and `Light0001`, `Light0041`, `Light0063`. All 14 solved locally with the ASTAP/Gaia policy and passed the solver's field-edge check. The overlap test then measures independent stellar positions between the frames. [OriginStack sample sessions and license](https://originstack.site/sample-sessions.html) · [M51 archive](https://doi.org/10.5281/zenodo.23895652) · [M37 archive](https://doi.org/10.5281/zenodo.23896484)

Use the original 3056 × 2048 RGGB detector raster. Interpolate the missing colors, retain the observed CFA sample in its own channel and mask saturated source support. The photo comparison uses the same linear RGB assignment, 2.95534 arcsec/px sampling grid and frozen whole-block splits for all three exposures in each case. The M51 lights were taken at ISO 500 for 20 seconds. The archive's darks use other settings, so this screen encodes the raw ADU divided by four. The M37 lights and master dark share ISO 200, 30 seconds, 1×1 binning and the detector format. The dark temperature is 23.1 °C and the selected light temperatures span 25.4–26.5 °C. Subtract the dark once in detector coordinates and encode the signed calibrated values as `round(ADU / 12 + 2048)` for the photo reference.

| Triplet | Native held-out overlap P95 | Final mean RGB P95 Off | Standard | Unity-gain global plane |
| --- | ---: | ---: | ---: | ---: |
| M51 raw | 0.709–0.852 px | 0.010295 | 0.007146 | 0.007131 |
| M37 dark-only | 1.058–1.153 px | 0.006942 | 0.003292 | 0.003284 |

The gain guard selected Standard for both triplets. The free-gain candidates lacked fit rank. The plane improved final mean P95 by 0.20% on M51 and 0.26% on M37 relative to Standard. Both missed the frozen improvement margin and the 0.5 px overlap target. The M37 flat variants also selected Standard.

### M37 flat intake and independent aperture audit

The supplied `flat.fits` is a 30-exposure Clear master at ISO 23 in the same RGGB binning and dimensions. The science header identifies an Origin178 on a 335 mm f/2.2 RASA. The archive includes an ISO 200 science bias with a median of 4,996 ADU. Its inventory supplies no ISO 23 additive reference for the flat. Check pedestal sensitivity at zero and 5,000 ADU. For each case divide the master by the central 128 × 128 median of each CFA phase after the pedestal subtraction. Apply the result to the dark-subtracted samples before interpolation. The four corner-patch response medians across the CFA phases spanned 0.964–0.985 with no subtraction and 0.953–0.978 with 5,000 ADU subtracted. The two pedestal choices define the sensitivity check. [Celestron flat and bias calibration](https://www.celestron.com/blogs/knowledgebase/the-ultimate-guide-to-calibration-frames-for-astrophotography)

Independent TIFF reopening reproduced the full binary masks and identical WCS headers in both flat variants and the dark-only comparison. The original CFA channel agreed with the independently calculated result within one UInt16 code at all 1,003 tested positions per variant. Compare aperture flux on the same matched centroids with a 12 px radius and 16–22 px sky annulus. Fit each relative exposure only on the training blocks. Keep the final apertures and annuli inside the reserved blocks. The three edges yielded 23, 21 and 30 final matched apertures. Only two, three and two respectively moved across a measured flat response difference of at least 1%.

| M37 exposure pair | Final stellar flux error P95 after dark | Flat with zero pedestal | Flat with 5,000 ADU pedestal |
| --- | ---: | ---: | ---: |
| 0001–0041 | 26.93% | 25.54% | 24.33% |
| 0001–0063 | 31.41% | 42.76% | 42.22% |
| 0041–0063 | 21.73% | 21.94% | 22.33% |

These fractional errors measure repeatability against the training-block median flux ratio on each pair. The measured field response gives a detector-frame reference and the archival data verifies arithmetic, masks and WCS. The small detector displacement and larger stellar scatter leave the flat's on-sky improvement unresolved. A multi-pointing or deliberately dithered series with the same optical configuration and temperature-matched additive calibration is the next optics control.

The local files under `output/phase8d-candidates/origin-m51/` and `output/phase8d-candidates/origin-m37/` include the source manifests, fixed selections, solver logs, comparison projects and the `flat-audit.json` result. M51 `raw/` and M37 `dark-12/`, `flat0-12/` and `flat5000-12/` hold the four comparisons.

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$m37 = 'output/phase8d-candidates/origin-m37'
.\.venv\Scripts\python.exe -m tools.phase8d_overlap_reference tests/20.TIF --project "$m37/dark-12/comparison.astromosaic" --preserve-calibrated-scale --stellar-gain -o "$m37/dark-12/overlap-replay.json"
.\.venv\Scripts\python.exe "$m37/audit_flat.py" flat-audit-new.json
```

Run from the repository root and choose new output filenames. The M37 detector and aperture audit reproduced SHA-256 `e53006557b6a56940f78bf31f1ae1ac737cbbd39b93fa9dedc09edb35ae1f490`.

## Calibrated M8–M20 exposure sequence

Colmic's Siril tutorial supplies 15 independent 180 s light frames along with 15 matching darks, 15 flats and 15 three-second dark flats. The 6248 × 4176 RGGB lights use the ASI2600MC Pro at gain 100, offset 50 and 388 mm focal length with an L-Pro filter. Their start times span 20:25:30 to 21:12:12 UTC on August 18, 2020. All 15 lights passed the local ASTAP/Gaia field-edge check. [Siril tutorial and source data](https://siril.org/tutorials/tuto-scripts/index.html)

Subtract the median 180 s dark in detector coordinates. Normalize each dark-subtracted flat at the center by CFA phase and use the normalized median response. Interpolate missing RGB samples, retain measured CFA samples, and mask saturation and its interpolation support. Encode the signed calibrated samples as `round(ADU / 2 + 1024)` with the same linear RGB assignment across all panels. Compare the first, middle and last individual frames. Then group frames 1–5, 6–10 and 11–15 into three disjoint median stacks. Sample each group onto its middle frame's native WCS in 256-pixel tiles with a minimum of four supporting exposures. Keep the original sky levels of each frame throughout preparation.

| Input network | Native overlap P95 | Final mean RGB P95 Off | Standard | Global gain and plane | Unity-gain global plane |
| --- | ---: | ---: | ---: | ---: | ---: |
| Three individual exposures | 0.175–0.189 px | 0.00070564 | 0.00070164 | 0.00068754 | 0.00070063 |
| Three chronological stacks | 0.079–0.110 px | 0.00034437 | 0.00033179 | 0.00033269 | 0.00033242 |

The stack geometry uses 297–330 held-out stars per edge at 1.999 arcsec/px. The brightness comparison uses a saved 5.997 arcsec/px grid and the frozen eight-pixel stride and spatial splits. Both networks retained **Off** after the model-selection margins were applied. On the stacks, the fixed-gain plane reduced selection P95 by 0.18% relative to Standard. Final P95 increased by 0.19%. The sample-level improvement from stacking supplied better geometry and a lower-noise comparison, while the inter-exposure spatial contribution stayed small.

The optional `--background-support` report measures the median right-minus-left RGB difference in each shared block with at least eight faint samples. At unity gain, the midpoint of the minimum and maximum channel differences gives the best scalar correction in that block. Half their range is the residual that remains in at least one channel. Report the P05–P95 span of midpoints and P95 of the color floor separately for the training, selection and final blocks. Across the three stacked overlaps, the selection spatial spans were `4.65e-5`–`5.66e-5` and the corresponding color floors were `4.19e-5`–`5.26e-5`. The comparable magnitudes explain the limited scope for a linked plane on this sequence.

Independent TIFF reopening verified all binary coverage codes and checked 12,420 measured CFA samples and 2,484 reprojected stack RGB locations within one UInt16 code. The four corner coordinates of each stack matched its anchor. The final stellar comparison used 156–176 reserved apertures per stack edge. The source hashes, calibration, preparation scripts and fit reports are under `output/phase8d-candidates/siril-m8-m20/`.

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$siril = 'output/phase8d-candidates/siril-m8-m20'
.\.venv\Scripts\python.exe -m tools.phase8d_overlap_reference tests/20.TIF --project "$siril/stacks/comparison.astromosaic" --preserve-calibrated-scale --stellar-gain --background-support -o "$siril/stacks/background-replay.json"
```

Use the `single` subfolder for the original triplet and choose a new report filename. The stacked diagnostic replayed byte for byte with SHA-256 `4efaf3912dd94202520c1a7afd0095c5b5bfe360f577be1408143378dd1edfc6`.

## Expanded SDSS M2 sky screen

Select the closest field in each of 12 M2 drift scans from the SDSS query already used for the calibrated control. Use the archived i, r and g sky models and their calibration vectors on a shared 768 × 768 TAN grid at 0.792 arcsec/px. Fit the unity-gain global offset and plane to the measured sky differences in the training blocks, and rank every available three-scan cycle by the selection-block improvement. The FITS primary images define the common faint support. [SDSS frame access](https://www.sdss.org/dr20/data_access/get_data/) · [Restored sky method](#restored-sdss-sky-backgrounds)

All 66 pairs supplied enough samples for the fit. The two models were available on 216 of the 220 cycles. The strongest sky-only cycle used runs 1040, 3360 and 4192 and reduced selection mean RGB P95 by 4.15% relative to the global offset. The frozen plane margin is 15%. Recombining the archive sky with the celestial signal raised the plane's selection P95 relative to Standard. It lowered the final mean from 0.018681 to 0.018518, a 0.87% improvement. The held-out diffuse residuals against the sky-subtracted archive images were mixed across the three edges.

A separate run supplied the original r-band samples to all three channels of the same fitter. On the sky-only models, 217 of 220 cycles met the plane margin. The strongest cycle reduced selection P95 by 90.84%. When the celestial samples were included, the same cycle's unity-gain plane reduced final mean P95 by only 1.27% relative to Standard. The sky-subtracted r images alone had a final mean P95 of 0.018646 on those pairs. The one-band experiment isolates the effect of channel differences in the sky-only screen and shows why the final comparison needs the independently exposed celestial signal.

The reports, local replay script and source manifest are under `output/phase8d-candidates/sdss-m2-screen/`. Run `screen.py` with a new JSON filename and add `--r-band` for the single-band control. The RGB and r-band screens reproduced SHA-256 `085284c283eac04493fa281871bc2bf8f08661330d5103b8e6ab40c0709832db` and `af2397f9d0b4406772fdc9906865d2724c234df3ff8b46d3092d1492a49947eb`, respectively. The default frozen PA4 report also replayed byte for byte after adding the optional background diagnostics.

## Linked additive correction limits

Use `--linked-offset-bound` to compute a lower bound on the pooled RGB P95 after any linked additive correction at unity gain. At each shared location, a linked offset can zero one channel difference. The second-smallest absolute residual must be at least half the closest pair's separation. The largest residual must be at least half the range across the three channels. Pool those three lower bounds per location and take the P95 in each existing spatial split, using the same channel pooling as the overlap score. Each array follows `scored_edges`. [Overlap diagnostic](../tools/phase8d_overlap_reference.py)

Compare the mean bound in the selection split with the frozen improvement threshold. A bound at or above the threshold rules out any linked offset or plane at unity gain for those samples. When the margin is possible, use the fitted candidates and the reserved measurements to assess it. The input differences include observed color, noise and sampling differences.

| RGB case | Selection mean lower bound | Selection mean Standard P95 | Selection mean unity-gain plane P95 | Final mean lower bound |
| --- | ---: | ---: | ---: | ---: |
| M8–M20 disjoint stacks | 0.00020318 | 0.00032466 | 0.00032407 | 0.00020520 |
| SDSS M2 with restored sky | 0.028224 | 0.037365 | 0.037247 | 0.028465 |
| SDSS M77 with restored sky | 0.048223 | 0.062550 | 0.062529 | 0.047917 |

The lower bounds fall below the 15% improvement targets calculated from the measured Standard scores. The fitted planes improved the selection score by at most 0.32%. The restored-sky runs verified the same sampled coverage and reserved aperture audits as the original runs. [M8–M20 stack preparation](#calibrated-m8m20-exposure-sequence) · [SDSS restoration](#restored-sdss-sky-backgrounds)

Across the 216 supported RGB sky-only cycles from the 12-scan M2 screen, the selection bound excluded 125 from achieving the frozen plane margin against the unity-gain global offset. The fitted planes fell short on the other 91 cycles. The audit uses the original faint sample masks and the frozen offset scores on each cycle. Run `audit_linked_bounds.py` in the local `output/phase8d-candidates/sdss-m2-screen/` evidence folder with a new report path as its argument. Its output replayed with SHA-256 `0c53f42bde21e9d9e04b738f8a4fd82d15025c6bfefb04bd4ed10158ede2d90b`. [Expanded SDSS scan selection](#expanded-sdss-m2-sky-screen)

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$siril = 'output/phase8d-candidates/siril-m8-m20/stacks'
$sdss = 'output/phase8d-candidates/sdss'
.\.venv\Scripts\python.exe -m tools.phase8d_overlap_reference tests/20.TIF --project "$siril/comparison.astromosaic" --preserve-calibrated-scale --stellar-gain --background-support --linked-offset-bound -o "$siril/linked-offset-bound-new.json"
.\.venv\Scripts\python.exe -m tools.phase8d_sdss_sky "$sdss/m2/comparison.astromosaic" "$sdss/source-m2.json" "$sdss/raw" --linked-offset-bound -o "$sdss/m2/restored-linked-offset-bound-new.json"
```

Use new report filenames and substitute `m77` for the second SDSS replay. The M8–M20, M2 and M77 reports replayed byte for byte with SHA-256 `a13efedb692efc9e48765bd723b5e30021d1501834ff8bfeb6531b960c212b80`, `ae3b1796ffa1ca31b6e500374b037f2f4af3e00d194da64936abddd2b2068977` and `16aeda2724331a1d49251ac782bc5e0714497499d875f77f09ce9922ce3ae3b4`, respectively.

## Bath M51 geometry intake

The University of Bath archive provides separate red, green and blue observations and calibration frames. Screen the fixed ordinal groups 1–4, 5–8 and 13–16 from the February 5, 2022 red and green sequences. These 24 lights share a 4656 × 3520 ASI1600MM Pro detector, 32 s exposure, gain 139, offset 10 and −5 °C recorded detector temperature. Use the existing strict Gaia DR3 solve and field-edge limits with the header's pointing and 0.490 arcsec/px nominal scale. [Peter Sloan's CC BY 4.0 dataset](https://doi.org/10.15125/BATH-01225)

Three red and ten green exposures passed the catalog validation. The other 11 had overall held-out P95 between 1.004 and 1.202 px against the 1 px solve limit. The three accepted red exposures, 003, 007 and 015, provide one independent exposure from each group. On their native-scale overlap comparison, reserved P95 was 1.036, 1.243 and 1.080 px with 16, 18 and 16 matched stars, respectively. This network missed the Phase 8D 0.5 px gate. Intake stopped at geometry, before assembling RGB or comparing brightness. The archive and FITS hashes, solve reports and native geometry are in `output/phase8d-candidates/bath-m51/`.

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$env:PYTHONPATH = (Get-Location).Path
$m51 = 'output/phase8d-candidates/bath-m51'
.\.venv\Scripts\python.exe "$m51/check_geometry.py" red "$m51/red-native-geometry-new.json"
```

Use a new output path. The geometry report replayed byte for byte with SHA-256 `d2f2082ce87190c89c7f354b8b8f9b4b49c46767621e802b8e3777e747b4324e`.

## MOANA Standard replay and independent M33 observations

The four existing Lagoon Nebula panels reproduced both reference JSONs byte for byte. All six native overlap P95 values remain 0.193–0.408 px. Standard passed the independent stellar gain check and reduced final mean RGB P95 by 10.06%. Retain the Lagoon panels for Standard regression. [Lagoon observation source](https://erellaz.com/moana/open-datasets/lagoon-nebula/)

The separate M33 acquisition supplies five disjoint stacks across two pointings and four UTC nights in October 2022. Use three chronological ranks per RGB channel per stack. All 45 lights are 60 s at gain 90 and −20 °C, and all passed strict catalog validation. Use the supplied dark and RGB flats and the native green anchor WCS. The legacy FITS omit row orientation metadata. A 75-hot-pixel audit matched the dark to all five green anchors in FITS array order with correlations of 0.995–1.000. Signed Float32 calibration preserves the common detector scale and measured sky. The flat pedestal, science offset and master-dark temperature are unresolved. [M33 observation source](https://erellaz.com/moana/open-datasets/m33-mosaic/)

The original geometry diagnostic admitted two of ten edges at 0.158 and 0.397 px P95 on seven and thirteen final stars. On the full matched samples, those edges were 0.866 and 1.017 px. The eight remaining edges missed the nominal 0.5 px holdout limit at 0.931–1.273 px. Remeasure without changing either the WCS or the native 0.5884 arcsec/px grid. Before scoring the reserved points, require a green aperture S/N of at least 25 in both panels, using local noise and the recorded detector gain. Require at least 15 final stars from three 256-pixel cells per edge. The three pointing-2 nights pass on all three edges with 103–116 final stars per edge and 0.196–0.237 native px P95. Their original, unscreened P95 is 0.976–1.273 px. Cross-pointing edges supply four to nine high-signal final stars each and fall short of the support threshold. The S/N result qualifies a same-pointing comparison on well-measured centroids.

### M33 brightness and reserved-block audits

Measure signed Float32 through the existing frozen fitter at 1.7653 arcsec/px with the eight-pixel sample stride. Run the linked additive bound on the selection blocks before fitting. The cross-pointing chain's mean bound is `3.20003e-4`, below the offset and plane ceilings of `4.65997e-4` and `4.16734e-4`. The pointing-2 cycle's mean bound is `3.33009e-4`, below its ceilings of `4.92796e-4` and `4.40712e-4`. Both networks therefore advance to fitting. Keep the sparse chain as a control for geometry and limited aperture support.

| Tested model | Pointing-2 selection mean RGB P95 | Pointing-2 final mean RGB P95 | Cross-pointing chain final mean RGB P95 |
| --- | ---: | ---: | ---: |
| Off | 0.000520837 | 0.000531876 | 0.000634046 |
| Standard-style | 0.000498612 | 0.000506692 | 0.000625575 |
| Advanced gain and offset | 0.000427733 | 0.000437086 | 0.000635985 |
| Advanced gain and plane | 0.000419562 | 0.000428943 | Insufficient rank |
| Advanced unity-gain offset | 0.000498820 | 0.000506746 | 0.000625905 |
| Advanced unity-gain plane | 0.000499072 | 0.000506670 | Insufficient rank |

In the cycle, Standard reduced selection P95 by 4.27% versus Off, below the 5% relative margin. The gain-and-offset candidate improved final RGB P95 by 13.74% versus Standard. Its gains of 0.697 and 0.695 triggered the stellar veto. The final block-weighted stellar medians on the two reference edges moved from +10.29% and +4.90% to −23.13% and −27.05%. Worst per-panel aperture change P95 was 30.46%. The free-gain plane reached a 15.85% selection reduction versus Standard and 1.91% versus the winning sky-only offset. It missed the incremental 15% margin and its aperture change reached 34.97% P95. The unity-gain plane's final advantage versus Standard was 0.0043%. Both networks retained **Off** after all frozen checks. In the sparse chain both planes' scaled singular-value ratios were below 0.00378 against the 0.015 limit. The proposed gain changes had two and four selection apertures on the two edges, below the required eight per edge.

In the cycle, 129–138 final matched apertures per edge and 476 separate same-panel apertures measured relative stellar flux. The 92–93 supported diffuse blocks per edge yielded block-median RGB P95 of `1.10e-4`–`2.79e-4` with Off, `9.42e-5`–`1.83e-4` with Standard, and `6.57e-5`–`2.26e-4` with Advanced gain and offset. The free-gain offset changed within-block diffuse contrast by up to `3.42e-5` at P95. The corresponding unity-gain plane value was `4.64e-7`. All models retained the same final binary coverage on both sampling grids. The cycle has 5,754 covered samples in the union and 5,625 in the three-panel intersection. These aperture and diffuse measurements compare independent exposures and the effects of corrections on the same input. Absolute flux and diffuse truth are unavailable.

The source manifests, native residuals, per-edge selection and test scores, measured coverage, commands and replay are in `output/phase8d-validation-followup-20261123/`. These results leave the positive Advanced gate open.

## Independent Pleiades spatial-background screen

Use the Nocturne Pleiades archive from August 10, 2026. The public ZIP has 304 ten-second Seestar S30 Pro IR-cut lights. The intake selected six at each chronological quartile, including both endpoints, for five disjoint time windows from 00:29:59 to 01:49:47 UTC. All 30 passed strict catalog validation. Stack each group onto its middle accepted exposure at native size (2160 × 3840). Use bilinear GRBG interpolation, mask the one-pixel saturation footprint and median-combine at least four of the six observations. Keep Float32 on the common detector-code scale and retain the measured background. Matched additive and flat calibration for these lights is unavailable. [Nocturne source data and attribution](https://nocturneastro.com/sample-data.html)

Freeze native geometry stars before scoring final blocks. Use isolated, unsaturated green centroids with sky-noise aperture S/N at least 25 and the pre-existing SEP shape limits. Require at least 15 stars across three reserved 256-pixel blocks per edge. Match all five candidate stacks and choose the triplet from the training and selection measurements. Photometry keeps the existing 64-pixel split. The selection sampler skips the final blocks.

Rank the ten triplets by supported geometry and coherent spatial background differences on the selection blocks. Across all ten edges, the ratio of the linked P05–P95 spatial span to the RGB color floor was 0.98–1.48, below the priority of 2. The strongest viable triplet by mean ratio uses A, C and D. Its linked span was `1.14e-4`–`1.37e-4` and its color floor `7.90e-5`–`1.09e-4`. Two of the three edges have at least one negative channel rank correlation. The candidate has measurable spatial variation and limited channel agreement.

| Final edge | S/N-qualified stars / blocks | Native P95 (px) | Before S/N screen P95 (px) |
| --- | ---: | ---: | ---: |
| A–C | 68 / 24 | 0.137 | 0.343 |
| A–D | 64 / 22 | 0.149 | 0.396 |
| C–D | 72 / 24 | 0.135 | 0.361 |

Geometry uses 3.7385 arcsec/px and passes the strict 0.5 px target on every edge. Photometry samples every eighth pixel on the 11.2155 arcsec/px grid. The selection mean `--linked-offset-bound` is `5.02756e-4`. It is below the unity-gain offset and plane ceilings of `7.53343e-4` and `6.73833e-4`. Both fixed-gain fits proceed. The free-gain offset and plane are rejected on scaled singular-value ratios of 0.009448 and 0.009445, below 0.015.

| Model | Selection mean RGB P95 | Final mean RGB P95 |
| --- | ---: | ---: |
| Off | 0.000795098 | 0.000803385 |
| Standard-style | 0.000791204 | 0.000801512 |
| Advanced unity-gain offset | 0.000791249 | 0.000802028 |
| Advanced unity-gain plane | 0.000790659 | 0.000801828 |

Standard reduced selection RGB P95 by 0.49% versus Off, below the 5% relative margin. The unity-gain plane improved selection by 0.56% versus Off, below 15%, and had slightly higher final RGB error than Standard. The frozen choice was **Off**. Measure 137–151 paired final stellar apertures per edge. Their signed peer medians span +8.07% to +20.53%. The largest P95 change relative to the original same-panel apertures was 0.0136% for the unity-gain plane. Its final diffuse block-median P95 was `1.47e-4`–`1.61e-4` across 49–51 blocks per edge, with P95 local contrast change below `2.79e-7`. All fits kept the same binary final coverage, with 2,733 union and 2,435 three-panel intersection samples. Aperture and diffuse measurements are relative. [Frozen acceptance](#selection-and-acceptance)

The frozen protocol, selection and final reports, source and preparation settings, and commands are in `output/phase8d-validation-spatial-20261123/`. In the same run, the Lagoon Standard result and M33 stellar veto reproduced byte for byte against their earlier reports.

### Stripe 82 gradient intake

Screen a separate field around NGC 1087. Choose the closest overlapping frame in each of fourteen archive runs and reconstruct the observed i, r and g sky models in their native calibration on a common 768 × 768 grid at 0.792 arcsec/px. Use only training and selection blocks from the existing split. The largest shared spatial-span to color-floor ratio among 91 edges was 0.260, below the priority of 2. On that edge, runs 4157 and 4868, the linked span was `6.62e-4`, the RGB color floor was `2.55e-3` and the G–B rank correlation was −0.330. The archive sky-only report reproduced byte for byte. It supplied no near-neutral background candidate for a final scene comparison. [Stripe 82 archive](https://www.sdss4.org/dr17/tutorials/get_stripe82_images/) · [Archived sky model method](#restored-sdss-sky-backgrounds)

### Separate 300 s Lagoon observations

Use 300 s MOANA Lagoon lights from July 19, 2023 UTC, separate from the previous 120 s control. Split each pointing and filter by the earliest and latest three timestamps. Strict catalog validation passes 35 of the 36 primary lights. The only unused tile-1 red reserve reaches 1.295 px overall P95, above the 1.0 px gate. The late tile-1 red stack therefore uses two accepted lights and requires both at every valid output pixel. This rule was fixed before any stack or overlap scoring. [Publisher data and acquisition notes](https://erellaz.com/moana/open-datasets/lagoon-nebula/) · [Catalog evidence and frozen support rule](../output/phase8d-moana-300s-20261125/README.md)

Use the supplied 300 s dark and normalized flats in detector coordinates and preserve the measured sky on the common linear scale. The flat pedestal remains undocumented. The native green anchors define four signed Float32 panels. Triplet selection uses the established fit and selection blocks on the same native and photometry scales as the 120 s control. [Selection rules](#selection-and-acceptance) · [Spatial-background protocol](../output/phase8d-moana-300s-20261125/protocol.md)

The frozen `t1-late`, `t2-early` and `t2-late` triplet passes native geometry at 0.221, 0.250 and 0.137 px P95 on 36, 37 and 246 reserved stars. Its selection spatial spans are 2.282, 1.717 and 1.143 times the respective RGB color floors. All three channel-pair rank correlations are positive on each edge. The selection mean linked-offset lower bound is `1.47743e-3`, below both the offset ceiling of `2.23094e-3` and the plane ceiling of `1.99589e-3`. All four Advanced designs pass the existing rank limit. [Selection-only report](../output/phase8d-moana-300s-20261125/selection.json) · [Reserved geometry](../output/phase8d-moana-300s-20261125/comparison/native-geometry.json)

| Candidate | Selection mean RGB P95 | Final mean RGB P95 |
| --- | ---: | ---: |
| Off | 0.00256298 | 0.00292450 |
| Standard-style | 0.00235046 | 0.00252097 |
| Advanced gain and offset | 0.00235403 | 0.00252200 |
| Advanced gain and plane | 0.00235544 | 0.00252494 |
| Advanced unity-gain offset | 0.00260611 | 0.00299287 |
| Advanced unity-gain plane | 0.00259765 | 0.00297321 |

The stellar guard retains **Standard**. It lowers mean RGB P95 by 8.29% in selection and 13.80% in the final blocks versus Off. All Advanced variants score above Standard on both means. The 252 reserved matched apertures support Standard's gains on all three edges. Both cross-tile block-weighted stellar medians move closer to zero. Diffuse block medians improve on both cross-tile edges and regress on the same-tile edge. All models preserve the same 10,248 final union and 1,034 three-panel intersection samples. The peer photometry and diffuse comparisons have no absolute scene truth. [Coefficients, apertures, diffuse checks and masks](../output/phase8d-moana-300s-20261125/comparison/photometry.json)

Retain the 300 s network as a second Lagoon Standard control with independently exposed input. The positive Advanced reference remains open. The four TIFFs, prepared source report, selection and three final reports reproduce byte for byte from the same saved strict WCS. Independent recalculation matches all 2,688 mask samples, all 16 WCS corners and the covered RGB samples within `3.65e-8`. Both earlier Lagoon 120 s reports also reproduce. [Reproduction and checks](../output/phase8d-moana-300s-20261125/README.md)

### Independent Bat and Wing selection screen

The fresh MOANA NGC 6995 campaign supplies five disjoint nightly RGB stacks across two pointings. All 45 admitted lights pass strict catalog validation. Their headers identify 60 s, gain 90 and −14 °C. Preparation uses the matching 60 s dark and normalized RGB master flats and retains the measured sky in signed linear Float32. The master flat pedestal remains undocumented. [Publisher data and license](https://erellaz.com/moana/open-datasets/) · [Input exposure and calibration hashes](../output/phase8d-rgb-network-20261125/observations/sources.json)

All ten links meet the selection geometry gate at 0.104–0.162 native px P95, with 56–274 stars in 14–54 blocks. The highest selection shared spatial span is 1.064 times the color floor. On the strongest cross-pointing link it is 1.046 times the floor and the R–B rank correlation is −0.327. None of the ten triplets supplies two links with a span at least twice the color floor and three positive channel correlations. The intake stops with the final reserve sealed. [Per-link geometry, color floor, correlations and rank](../output/phase8d-rgb-network-20261125/README.md#selection-measurements)

The best rejected triplet uses the June 26 and June 28 Bat panels and July 20 Wing panel, anchored to June 26 for selection diagnostics. Its free-gain offset and plane scaled singular-value ratios are 0.00742 and 0.00613 against the 0.015 limit. The unity-gain offset lowers mean selection RGB P95 from Standard's `4.50369e-4` to `4.49839e-4`, a 0.118% and `5.29e-7` reduction. The unity-gain plane reaches `4.51534e-4` and raises error on both cross-pointing links. The selection-only diagnostic retains **Off**. Final RGB, stellar flux, diffuse contrast and coverage remain unmeasured for Bat/Wing. [Per-link P95 and thresholds](../output/phase8d-rgb-network-20261125/README.md#standard-and-advanced-on-the-best-rejected-triplet)

The second destination reproduces all five prepared TIFFs, manifests and the selection report byte for byte. Reversing panel order reproduces the screening decision. Both Lagoon Standard controls and the M33 stellar-veto control replay exactly. The focused source suite passes 15 tests. Ruff, scoped mypy and Poetry lock validation pass. Q-029 still needs a fresh calibrated network with coherent spatial support on several overlaps. [Commands and replay](../output/phase8d-rgb-network-20261125/README.md#controls-and-reproduction)

### ZTF archive intake and HST M51 fallback

The public ZTF metadata screen returns 28,188 rows across eight diffuse fields. Fields 730 and 768 around the North America Nebula give six independent 30 s i, r and g panels on three UTC dates, with 17.87% nominal overlap of the smaller footprint. Repeated HTTP 503 responses leave five of 36 science and mask products available after direct and full-quadrant service attempts. The metadata decision replays exactly. No ZTF RGB panel is complete. [ZTF metadata, retrieved FITS hashes and commands](../output/phase8d-ztf-rgb-20261125/README.md)

The MAST fallback uses 12 ACS/WFC FLCs from four adjacent GO-10452 M51 pointings. Verify completed flat and pixel-CTE correction. Reproject the original two-chip WCS with distortion lookups onto each native-scale 0.05 arcsec/px panel. Keep the DQ-masked sky in signed linear R, G and B from F814W, F555W and F435W on a common electron-rate scale. [MAST M51 program and mosaic](https://archive.stsci.edu/prepds/m51/) · [FLC roots, calibration and checksums](../output/phase8d-hst-rgb-20261125/README.md#sources-and-preparation)

All six links lack the matched stars needed for native geometry. Their selection samples range from 5 to 96 against the minimum 128. The strongest measurable shared span is 1.249 times the color floor on POS1–POS3, with R–B correlation −0.500. All measurable plane designs miss the 0.015 rank limit. No triplet advances, and the final reserve stays sealed. The four TIFFs and selection report replay byte for byte with reversed input order. Fifteen source tests, Ruff, scoped mypy and Poetry lock validation pass. [Selection table and replay](../output/phase8d-hst-rgb-20261125/README.md#selection-measurements)

### Recovered ZTF North America Nebula network

Sequential IRSA downloads and two longer retries recover all 36 science and mask products for the frozen 18 ZTF exposures. Their observation identities and raster lengths match the archive records. The recovered six panels use the original r detector grids, linear calibrated ADU and separate binary coverage. [Acquisition receipts and replay](../output/phase8d-ztf-recovery-20261125/README.md#archive-recovery)

The initial zero-mask preparation admits zero eligible stars. Archive bits 1 and 11 describe source detections. Retaining those annotations and invalidating all other flags recovers 919,649–1,313,072 covered pixels per panel and preserves every previously valid RGB value. The revised masks are frozen before repeating the selection. [ZTF mask specification, §10.3](https://irsa.ipac.caltech.edu/data/ZTF/docs/ztf_explanatory_supplement.pdf) · [Mask audit and reproduction](../output/phase8d-ztf-recovery-20261125/README.md#archive-mask-correction)

All 15 links qualify for selection at 0.051–0.088 native px P95 on 20–162 stars. The largest shared spatial span is 0.180 times the RGB color floor and the same link has R–B and G–B correlations of −0.042 and −0.030. No triplet meets the two-link coherence threshold, so the final reserve stays sealed. The highest-ranked rejected triplet retains **Standard** on selection at mean RGB P95 `9.17558e-4`. The free-gain fits lack joint rank. The unity-gain offset and plane raise RGB P95 by 0.283% and 0.384% on average, with losses on every link. [All overlap metrics and selection model scores](../output/phase8d-ztf-recovery-20261125/source-mask/measurements.md)

The corrected TIFFs, masks, source catalogs and reports replay byte for byte under reversed input order. Independent reopening matches 54,123,707 green anchor samples with exact corner and center coordinates. Both Lagoon Standard controls and the M33 stellar veto replay exactly. Fifteen focused tests, Ruff, scoped mypy and Poetry lock validation pass. The next candidate should provide simultaneous broadband RGB and qualified spatial support across multiple overlaps. [Evidence and command](../output/phase8d-ztf-recovery-20261125/README.md#verification-and-replay)

### Orion simultaneous broadband RGB screen

The JF1960 Orion archive provides four distinct pointings, 233 separate 90 s Bayer exposures and three full-size CFA calibration masters. Seven timestamp-spaced observations per pointing form four independent native-grid stacks. The reference retains a common signed linear RGB scale, the observed sky and separate coverage masks. The master flat's bias treatment is undocumented, so an additional selection-only preparation subtracts the supplied bias before flat normalization. [Source identities, protocol and checksums](../output/phase8d-osc-intake-20261125/README.md)

The archive WCS qualifies zero links. Each of the same 28 exposures then passes strict edge-supported catalog astrometry. The rebuilt network qualifies four overlaps at 0.098–0.138 native px P95. Two diagonal overlaps have four eligible stars and 51–60 sky samples per selection split. On qualified overlaps the largest shared spatial span is 0.620 times the color floor, with a G–B correlation of −0.045. The strongest overlap with all three correlations positive reaches 0.472. Subtracting bias from the flat raises the best qualified ratio to 0.708. Either calibration gives zero links at the 2.0 coherence threshold. [Geometry, support, color and rank by overlap](../output/phase8d-osc-intake-20261125/results.md)

Standard is the selection-only result for the highest-ranked rejected triplet and the four-link diagnostic. On all four links, Standard reaches mean RGB P95 `5.35829e-4`. Both free-gain variants fail the rank test. The fixed-gain offset and plane raise the four-link mean by 0.39% and 0.25%. The plane improves two overlaps and worsens two, including a 2.48% increase on p21 / p22. The final geometry, sky, aperture and diffuse blocks remain reserved. Q-029 remains open. [Per-overlap model comparisons and acceptance limits](../output/phase8d-osc-intake-20261125/results.md)

The second destination rebuilds the TIFFs and masks and reproduces the results byte for byte with reversed panel order. Reopening confirms binary coverage and exact native WCS at every panel's corners and center. Both Lagoon Standard controls and the M33 stellar-veto control reproduce byte for byte. Fifteen focused source tests, Ruff, scoped mypy and Poetry lock validation pass. [Repeat command and verification](../output/phase8d-osc-intake-20261125/README.md#verification)

### Elephant Trunk broadband and calibration intake

Corsec's shared IC 1396 archive lists four pointings with 240 separate 120 s lights each across six acquisition folders. The 24 sample light files carry native ASI533MC Pro RGGB images with WCS. The observer's equipment record lists Baader UV/IR Cut / Luminance and the integration row names no filter. Both support the broadband intake. The FITS headers leave the exact filter state unspecified. The presented mosaic used standalone panel stacks and post-stitch background extraction. [Observer capture record](https://app.astrobin.com/i/qt1os4?r=0) · [Capture provenance and archive identities](../output/phase8d-corsec-intake-20261125/publisher-source.md)

The 120 s master dark matches the detector layout and electronic gain. Its filename gives a −10 °C setpoint and its cold pedestal is close to the six sample short darks. The full audit of 120 flats and 120 short darks gives temperature ranges of −0.5 to +16.0 °C and −10.3 to −9.6 °C, respectively. The closest pair in the archive is 9.1 °C apart. The additive component in the flats remains unverified. Keep the candidate at intake and preserve the selection and final reserves. [Per-date calibration results and repeat command](../output/phase8d-corsec-intake-20261125/README.md)

A second retrieval reproduces the receipt, 37 complete FITS checksums and 240 calibration header-range checksums. The prior Lagoon Standard and M33 stellar-veto records verify. Eleven focused tests and the intake lint checks pass. [Verification](../output/phase8d-corsec-intake-20261125/verification.json)

### Public broadband calibration archive search

The file-level intake inspects six 3AM Astro ZIPs and three MILAN North America and Pelican sessions. Their directories expose 4,677 FITS images without named flat, short-dark, bias or offset companions. One CRC-verified FITS sample per archive confirms the detector metadata. The 3AM M31 sample uses broadband IRCUT in a single light folder. The five remaining 3AM samples use the Seestar LP dual-band mode. MILAN supplies three independent sessions from the same Stellina sensor. Its released calibration record leaves the optical flat-field correction unverified. [Per-archive counts, source licenses and header receipts](../output/phase8d-broadband-calibration-intake-20261125/README.md)

No new network advances to model selection or final scoring. The second destination reproduces all nine FITS samples, 27 independently fetched byte ranges and the audit receipt. The frozen Lagoon Standard and M33 stellar-veto controls match. Eleven focused tests and the intake lint checks pass. [Repeat command and verification](../output/phase8d-broadband-calibration-intake-20261125/README.md#reproduce-the-audit)

The ESO archive supplies three 66 s GROND exposures in OB #8 with nominal 19.8–35.1 arcsecond center shifts and concurrent g′, r′, i′ and z′ from four CCDs. The nearest indexed optical flat is 169.4 days later and lacks an established calibration association. The archive's 8,134 optical flat products provide a way to search for another GROND run with a calibration link. [Raw FITS preflight and calibration record](../output/phase8d-broadband-calibration-intake-20261125/README.md#grond-optical-follow-up)

### GROND observations with same-night optical flats

The initial `J1016+0419` triplet shares the 2014-03-28 optical calibration. The 28 original FITS files agree in detector clock, binning and amplifier layout. All 12 flats qualify per channel after overscan, bias and measured dark correction. The best r′ overlap reaches 0.387 native px P95 with four selection stars, below the 15-star minimum. The third exposure has only one surviving catalog star and the other two links lack training support. [Calibration and relative geometry](../output/phase8d-grond-flat-first-20261125/README.md#j10160419-baseline)

An archive-only density screen of 3,949 science rows selects the 2015-03-17 `2XMMJ1745-2902` template. The three independent 62 s optical exposures share the same-night calibration and have nominal centers 17.8–20.3 arcseconds apart. All 28 original FITS files verify. The flat strength and saturation limits retain 10, 10 and 11 exposures for g′, r′ and i′. The verified relative r′ geometry passes all three links at 0.1029–0.1315 px P95 with 49–56 selection stars in 13 blocks per link. The independently exposed, calibrated source triplet advances to cross-channel registration and the selection-only RGB coherence screen. [Source lineage, flat metrics and overlap support](../output/phase8d-grond-flat-first-20261125/README.md#dense-field-retry)

Both triplets replay exactly in reversed order, including archive bytes, CCD calibration, native masks and geometry reports. The Lagoon Standard and M33 stellar-veto controls verify alongside 11 focused tests and lint. Model selection and final RGB, aperture and diffuse blocks remain reserved. [Repeat command and verification](../output/phase8d-grond-flat-first-20261125/README.md#reproduction)

### GROND RGB coherence and selection

Train and validate the relative geometry of the three 62 s `2XMMJ1745-2902` exposures on the common split. The composed native r′ overlap maps pass at 0.086–0.110 px P95. The six g′ and i′ maps reach 0.114–0.177 px P95 against r′. Use i′, r′ and g′ as signed linear RGB with one common divisor and preserve the calibrated sky and binary masks. The fixed reference is p1. [Frozen geometry, calibration identities and protocol](../output/phase8d-grond-rgb-20261125/README.md#source-and-frozen-geometry)

| Overlap | Selection span divided by RGB color floor | Standard RGB P95 | Unity-gain offset RGB P95 | Unity-gain plane RGB P95 |
| --- | ---: | ---: | ---: | ---: |
| p1 / p2 | 0.609 | 3.32258e-4 | 3.33025e-4 | 3.32195e-4 |
| p1 / p3 | 0.374 | 3.68355e-4 | 3.69202e-4 | 3.67714e-4 |
| p2 / p3 | 0.491 | 3.16074e-4 | 3.14362e-4 | 3.17004e-4 |

Every link has a negative channel-pair correlation. Zero links meet the ratio of 2 and all-positive requirement. The network stays out of final scoring. Standard is retained in the selection diagnostic. The free-gain designs miss the 0.015 rank gate. The unity-gain offset lowers the mean by 0.0096% while raising the error on two links. The plane raises the mean by 0.0222% and worsens p2/p3. Both miss the required mean improvement. The selection aperture guard has 57–60 matches per link. The independent reversed replay matches all images, masks and receipts exactly. Both Lagoon controls retain Standard and M33 retains its stellar veto. No held-out stellar or diffuse measurement was made for the rejected network. [Full per-link tables and repeat commands](../output/phase8d-grond-rgb-20261125/README.md)

### Same-session Canon Whirlpool OSC screen

The Santiago Rodriguez archive supplies 941 original CR2 lights in eight target folders. The nine-archive inventory also finds 98 JPEG lights for Andromeda. Three recovered samples per CR2 folder establish the native pointings and capture settings. The Jellyfish triplet spans 19.7–27.7 arcminutes, and its three sampled ISO 100 flats lack a verified ISO-matched additive reference. Select the Whirlpool triplet of 45.3 s ISO 800 exposures with centers separated by 7.9–17.6 arcminutes. Use same-date dark and flat samples, measure the additive pedestal in the shielded pixels of each frame and preserve the signed linear RGB sky. The warmer flats leave the temperature-dependent spatial additive term unverified. [Source rights, exposure identities and calibration](../output/phase8d-osc-session-20261125/README.md#frozen-whirlpool-inputs)

The middle panel's best absolute Gaia solve reaches 1.103 native px P95, above the 1.0 px overall limit. The separately frozen relative retry retains all three overlaps at 0.429–0.479 native px P95 in the selection blocks. All nine channel-pair correlations are positive. The shared spatial spans reach 0.980, 0.999 and 0.611 times their RGB color floors. Zero links reach the ratio of 2.0, and final blocks stay reserved. [Relative geometry and selection evidence](../output/phase8d-osc-session-20261125/README.md#selection-evidence)

| Overlap | Standard selection RGB P95 | Advanced unity-gain offset | Advanced unity-gain plane |
| --- | ---: | ---: | ---: |
| p1 / p2 | 4.85749e-4 | 4.86283e-4 | 4.84303e-4 |
| p1 / p3 | 5.27086e-4 | 5.27552e-4 | 5.25871e-4 |
| p2 / p3 | 4.91737e-4 | 5.01188e-4 | 5.01650e-4 |

Standard survives the selection diagnostic. The free-gain candidates miss the 0.015 rank gate. The unity-gain plane improves the first two links and raises p2/p3 by about 2.0%. The network mean rises by 0.482%. The offset raises the mean by 0.695%. All candidates use the same binary coverage. There are 43–51 selection aperture matches per link and all fitted gains are unity. The independent second destination reproduces the 42 recovered CR2s, signed panels, masks and selection reports. The two Lagoon Standard controls, M33 stellar veto and 11 focused checks pass. [Verification and repeat commands](../output/phase8d-osc-session-20261125/README.md#reproduction)

### Jellyfish ISO 100 calibration audit

The complete Jellyfish calibration inventory yields 17 ISO 100 flats at 2.5 s and 21–22 °C. All 28 listed additive frames are ISO 800 at 11 °C. The 17 darks are 60 s. The bias folder contains ten 1 s frames and one 60 s file. Five companion Canon 40D archives carry the same flat identities and add 87 distinct ISO 1600 additive identities. The six archives cover 331 calibration paths and 132 distinct size-and-CRC identities. No listed bias or dark matches the flats' ISO. [Measurements, source identities and replay](../output/phase8d-jellyfish-calibration-20261125/README.md)

The CRC-verified project descriptor lists background extraction and tone transforms. It supplies no calibrated input lineage that qualifies the published outputs for this comparison. The candidate remains at calibration intake with both RGB reserves sealed. The independent reverse retrieval reproduces all 132 compressed ranges and decoded prefixes, six ZIP directories and the project descriptor. Nine earlier complete Jellyfish files match the expected full hashes and the new header samples. Both Lagoon Standard controls, the M33 stellar veto and 11 focused checks pass. [Verification receipt](../output/phase8d-jellyfish-calibration-20261125/verification.json)

### Jellyfish shielded pedestal repeatability

Decode the full raw mosaic of all 17 Canon 40D ISO 100 flats and retain their shielded detector columns. The two 12-column strips supply 7,806 samples per Bayer phase per frame. Their whole-strip trimmed phase estimates agree to 0.386 DN P95 and 0.486 DN maximum. Across frames, the R, G2 and B estimates span 0.125–0.156 DN. G1 spans 1.021 DN, with both column strips showing the lower level on the same four exposures. [Inputs, geometry and strip measurements](../output/phase8d-jellyfish-pedestal-20261125/README.md#input-and-measurement)

In 5,576 held-strip phase and row-band comparisons, the same-frame phase estimate yields 0.959 DN P95. The other-frame phase estimate yields 1.057 DN, the same-frame scalar 1.177 DN, and the same-frame 64-row phase fit 1.253 DN. Retain one electronic pedestal per frame and phase for the next detector experiment. The flat-center brightness span is 4.57–4.95% within each phase. The illuminated-area additive pattern at ISO 100 and 21–22 °C remains unverified. Both RGB reserves stay sealed. The reversed independent replay matches all 17 CR2s and the measurement. Both Lagoon Standard controls, the M33 stellar veto and 11 focused tests pass. [Comparison and repeat commands](../output/phase8d-jellyfish-pedestal-20261125/README.md)

### Jellyfish active-area additive identifiability

Use the original 17 ISO 100 flats with their shielded phase pedestal and freeze nine training, four selection and four calibration reserve frames. Fit the fixed detector response and response with a free intercept on the same 591 raw detector tiles. The training illumination spans 4.57–4.94% by phase. The scaled singular-value ratios of 0.00750–0.00780 amplify formal intercept uncertainty by 21.4–22.2 times the tile residual noise. [Protocol and frozen calibration fits](../output/phase8d-jellyfish-flat-leverage-20261125/README.md#frozen-experiment)

The intercept lowers the mean frame P95 from 12.673 to 10.455 DN on selection and from 9.667 to 7.484 DN on the reserved calibration frames. Three reserved frames improve and `IMG_7293.CR2` worsens by 0.440 DN. The two disjoint training-half intercept maps disagree by 492–920 DN P95 and have negative spatial rank correlation in every phase. The full-training and reserve fits have positive spatial rank correlations of 0.929–0.962 and differ by 105–200 DN P95. A 100 DN change in the illumination zero shifts the map and reproduces the same predictions within `1.82e-12` DN. The absolute active-area additive pattern remains unresolved. The RGB reserves stay sealed. The independent reverse replay reproduces both receipts and checks all 17 complete source hashes. [Measurements and repeat commands](../output/phase8d-jellyfish-flat-leverage-20261125/README.md)

### Jellyfish same-detector zero-light search

The 677 remaining CR2s across the six Santiago Rodriguez archives all share the Canon MakerNote body ID of the 17 complete Jellyfish flats. Their exposures are 30–75 s at ISO 640, 800 or 1600. Across the full 809 distinct CR2 identities, the only ISO 100, 2.5 s, 21–22 °C files are the 17 known illuminated flats. The local inventory also yields zero verified zero-light exposures at those settings. The active-area additive zero remains unmeasured, and Jellyfish stays at calibration intake with both RGB reserves sealed. [Source identities, results and repeat command](../output/phase8d-jellyfish-zero-light-20261125/README.md)

The reversed independent run reproduces all six ZIP tails, 677 compressed ranges, decoded headers and the search receipt. Both Lagoon Standard decisions and the M33 stellar gain veto verify. Eleven focused source tests pass. The remaining acquisition is an independent capped RAW sequence from the original detector at the flat settings. [Verification receipt](../output/phase8d-jellyfish-zero-light-20261125/verification.json)

### SkyMapper Rho Ophiuchi selection screen

An independent SkyMapper DR4 candidate uses nine disjoint g/r/i exposures across three native CCD footprints. The survey supplies overscan, bias, flat-field and i-band fringe calibration. FITS scaling and the documented approximate zeropoints produce a common signed linear scale without further sky subtraction. The source receipts retain the exposure and calibration identities, cutout and mask checksums, source rights and preparation rules. [Data, calibration and repeat commands](../output/phase8d-skymapper-intake-20261125/README.md)

The three overlaps have 272–305 source-free selection samples in six blocks each. Their spatial spans reach 0.03567, 0.02530 and 0.03999 times the RGB color floor. Only p2/p3 has positive correlations across all channel pairs. The native geometry has too few stars to report P95 on all three links. All free-gain offset and plane designs miss the 0.015 rank gate. The network remains outside method selection with final blocks sealed. [Per-overlap evidence](../output/phase8d-skymapper-intake-20261125/README.md#training-and-selection)

The reverse replay agrees on decoded data, stable FITS headers, TIFF masks and selection measurements. The service adds a request timestamp and supplies invalid embedded science checksums, so both independent file hashes and decoded pixel hashes are recorded. Both Lagoon Standard controls, the M33 stellar veto and 11 focused source tests pass. [Verification receipt](../output/phase8d-skymapper-intake-20261125/verification.json)

### CFHT MegaCam M13 short-exposure selection

Ten public CADC queries return 392 Elixir product rows in g/r/i below 29.99 s. M13 program 04AC03 yields five complete same-night dither groups. Three groups provide nine disjoint 5.113–5.140 s exposures on CCD 12. Elixir 2.0 applies its mask, overscan, bias and flat-field correction. These short exposures skip the large-scale sky modes and fringe corrections. Linear photometric conversion preserves the measured sky and keeps separate binary coverage. [Source identities, licence and repeat commands](../output/phase8d-cfht-elixir-20261126/README.md)

The archive WCS cannot qualify an overlap. A co-pointed i WCS seeds the two nominal p2 filter solutions. A relative affine fit on training blocks alone brings all three selection links to 0.270–0.331 native px P95 on 20–38 qualified stars per link. Shared spatial-to-color ratios are 1.712, 1.270 and 1.431. Two links have positive channel correlations throughout. No link reaches 2.0, and all free-gain fits miss the rank gate. [Native geometry and per-link coherence](../output/phase8d-cfht-elixir-20261126/README.md#geometry-and-selection)

The selection diagnostic retains Off in a tie with Standard. The best Advanced offset lowers the selection mean by 1.202% and `5.034e-7`. The plane lowers it by 0.892%. The two unity-gain Advanced models improve all three edges and miss their mean thresholds. Both RGB reserves stay sealed. Independent reverse retrieval agrees on the detector arrays, stable FITS headers, both prepared TIFF and mask sets, affine coefficients and selection results. Both Lagoon controls, M33's veto and 11 focused tests pass. [Per-link P95 and replay](../output/phase8d-cfht-elixir-20261126/README.md#geometry-and-selection)

### CFHT adjacent detector and five-dither screen

The CCD 13 repeat on distinct detector pixels qualifies all three relative links at 0.303–0.402 native px P95. Its strongest spatial-to-color ratio is 1.546, and each link has at least one negative channel correlation. Off ties Standard. The unity-gain offset lowers the mean by 0.732% and `3.424e-7` while worsening p1/p2. The plane also lowers the mean and raises p1/p2. Both miss the selection improvement gates. [CCD 13 scores and independent replay](../output/phase8d-completion-20261126/README.md#cfht-m13-archive-extension)

Expand both native CCDs to all five published same-night dither groups. CCD 12 qualifies nine of ten geometry links and CCD 13 qualifies all ten. Their strongest shared spatial spans are 1.395 and 1.316 times the color floor, respectively. None of the 20 triplets qualifies. Both best-triplet diagnostics retain Off in a tie with Standard. The separate reversed runs reproduce 30 detector cutouts, masks, affine fits and numeric selection. Final RGB blocks remain sealed. [Inputs, geometry, results and repeat commands](../output/phase8d-completion-20261126/README.md)

### CFHT visible flat leverage

The CADC archive supplies the exact Elixir r master identified in all ten red science cutouts. Measure the response change between matched high-S/N stellar positions with five-pixel apertures on the two native flats, using training and selection only. Among 618 selection overlap memberships, seven cross 2% measured response and none cross 3%. The strongest link supplies four at 2%. The two flats and preflight replay exactly at the decoded-array and numeric levels. This evidence supports a low-leverage visible comparison. The full-test aperture qualification remains open. [Master identities, leverage and replay](../output/phase8d-completion-20261126/README.md#visible-calibration-follow-up)

### Phase 8D completion evidence

The NIRCam F150W and F200W optical references replay with their frozen report hashes. The full offscreen source suite passes 259 tests with six skips. Ruff and Poetry lock checks pass. The existing beta 15 launcher hashes and console version verify on the development host. The outstanding criteria at closure were an independent qualified Advanced network, adequately supported measured optical correction, production preview and export integration, and portable acceptance on a separate Windows 11 x64 installation. [Requirements and current evidence](../output/phase8d-completion-20261126/README.md#remaining-phase-gates)

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

### 35 mm Nightscape field-wide Gaia refit

Reopen the three original-domain `6032 × 4032` TIFFs and their existing sky masks. Use the previous TAN solutions to locate 9 × 9 detector windows in the local Gaia DR3 catalog. Estimate local translations and affine terms from training stars and keep isolated mutual matches within 2.75 px. Reject windows that fail the shifted-catalog chance check. The three frames supplied 1,150, 1,217 and 1,112 stars in 35, 36 and 38 windows. A fixed hash of the catalog coordinates assigns each star to the same training, selection or final split in every frame. Selected models retain the original TIFF coordinate frame. [Richard Tatti's original captures](https://www.nightscapeimages.com.au/workshops---online.html)

The NEF MakerNotes identify the Sigma 35 mm F1.4 DG HSM on a Nikon D750 at f/2.2 and full FX crop. The matching Lensfun model and mount record uses a full-frame Pentax K-1 measurement. Invert its fixed `poly3` distortion and fit a TAN WCS to the virtual rectified grid. The model reduced catalog errors relative to the prior TAN on these associations. Its 5.829–9.504 px whole-mask P95 and 7.277–13.860 px edge P95 exceeded the 1.0 and 1.5 px limits. The archive profile has no recorded measurement at the MakerNote's focus distance. [Pinned Lensfun calibration record](https://github.com/lensfun/lensfun/blob/37238fcef563196fb798f6151cb9023968b26c40/data/db/slr-sigma.xml#L2265-L2286) · [Lensfun radial model](https://lensfun.github.io/manual/latest/group__Lens.html)

The third- and fourth-order detector-wide fits missed the catalog gate. Unconstrained fifth- to seventh-order fits failed the original-domain inverse check. Fit a shared radial and tangential distortion model with two additional prism terms on the training stars. Constrain the per-frame fifth- and seventh-order SIP fits toward that training-only model below detector row 2,600, where the foreground leaves no useful calibration support. Choose among inverse-safe models using normalized whole-mask and edge P95 on the selection stars. Use the simplest within 10% of the best. Apply the 1.0 px whole-mask and 1.5 px edge limits on the final stars. The 9 × 9 inverse and parity checks cover the entire raster. The stellar accuracy measurements cover the sky admitted by the mask. The bottom 20% contains no Gaia stars in these samples.

| Frame | Selected original-domain WCS | Final stars, all / edge | Final P95, all / edge (px) | Independent extra stars, all / edge | Extra P95, all / edge (px) |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | Regularized SIP-5 | 248 / 198 | 0.544 / 0.537 | 1,138 / 926 | 0.832 / 0.829 |
| 2 | Regularized SIP-7 | 243 / 144 | 0.490 / 0.489 | 1,015 / 670 | 0.830 / 0.885 |
| 3 | Regularized SIP-5 | 239 / 100 | 0.591 / 0.528 | 1,153 / 518 | 0.899 / 1.078 |

Recompute the same-series overlap by projecting independently measured centroids through each accepted WCS into the peer detector. Count Gaia identities withheld in all three frames. Use the larger of the two directional native-pixel P95 values for each pair. Repeat on additional isolated detections with Gaia identities absent from every earlier fit, selection and final set. The extra Gaia stars are generally fainter and pass the individual WCS gates. Their overlap P95 exceeds 0.5 px on every pair.

| Pair | Shared primary final stars | Primary overlap P95 (px) | Primary overlap edge P95 (px) | Shared extra stars | Extra overlap P95 (px) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1–2 | 106 | 0.594 | 0.558 | 274 | 0.888 |
| 1–3 | 66 | 0.611 | 0.601 | 142 | 1.046 |
| 2–3 | 116 | 0.482 | 0.512 | 333 | 0.930 |

The reference accepts the three WCS fits on the masked sky. Pair 2–3 alone passed the 0.5 px whole-overlap target on the primary final sample. Keep this as offline evidence under Q-016. The new run includes the accepted FITS WCS headers, measured lens trial, regional match tables, detector-side errors and exact commands in `output/phase8d-validation-followup-20261123/`. [Wide-field tracking](../questions_open_topics.md#q-016---plate-solve-quality-incorrect-scale-recovery-and-distortion)

### 35 mm overlap tails on independent Gaia stars

Keep the three accepted 35 mm WCS headers fixed and use the additional Gaia identities that were excluded from all earlier fits and model selection. The reserved set contains 1,138, 1,015 and 1,153 stars per frame. Whole-mask Gaia P95 is 0.832, 0.830 and 0.899 px. Edge P95 is 0.829, 0.885 and 1.078 px. The three common samples contain 274, 142 and 333 stars and reproduce native overlap P95 of 0.888, 1.046 and 0.930 px. The 0.5 px pair gate remains unmet.

Measure green-channel second moments on the original detector using a seven-pixel aperture, a 10–13 pixel annulus and positive weights above twice the annular MAD noise. Keep every overlap star for the geometric scores. For each star use the greater directional residual, the lower measured flux and axis ratio, and the greater measured FWHM and normalized detector radius across the pair. The following strata have at least 15 stars each.

| Pair | Axis ratio below 0.65 P95 | Axis ratio 0.65–0.80 P95 | Radius 0.40–0.70 P95 | Radius at least 0.70 P95 |
| --- | ---: | ---: | ---: | ---: |
| 1–2 | 0.976 px | 0.740 px | 0.785 px | 1.045 px |
| 1–3 | 1.056 px | 0.820 px | 0.876 px | 1.204 px |
| 2–3 | 0.984 px | 0.592 px | 0.692 px | 1.349 px |

Lower measured green flux was associated with larger errors in all three pairs, with Spearman coefficients of −0.16 to −0.26. Gaia G magnitude shows weak, nonmonotonic behavior by magnitude bin. The FWHM rank correlations were +0.14, +0.15 and −0.02. Detector cells with at least 15 stars ranged from 0.520 to 1.450 px P95. The outer-radius and elongated-shape strata identify where larger tails recur. The measurements do not isolate a physical cause. The report records star-level residuals, original positions, fluxes, axes and adjusted rank summaries in `output/phase8d-validation-spatial-20261123/nightscape-35mm-tail-shapes.json`.

### 20 mm Nightscape regional Gaia validation

Use the four Nikon Z 6 TIFFs, their original sky masks and the prior full-frame TAN solutions. Locate regional matches on a 9 × 9 grid with a 72 px search and 2.75 px local association radius. The four frames supply 617, 595, 616 and 565 isolated matches across 24–35 populated windows. Assign Gaia identities the same fixed split across all four frames. Allocate three fifths to fitting, one fifth to model selection and one fifth to the primary final sample. Write the selected model before scoring its final stars. Reserve another set of identities absent from the combined regional tables. [Original Nightscape practice captures](https://www.nightscapeimages.com.au/workshops---online.html)

Compare TAN, individual SIP, and shared and constrained distortion models through the original-detector inverse and parity gate. Selection retained SIP-4, SIP-4, SIP-5 and SIP-3 by frame. All four met the 1.0 px whole-mask and 1.5 px edge Gaia limits on both final samples.

| Frame | Primary all / edge P95 (px) | Independent extra stars | Extra all / edge P95 (px) |
| --- | ---: | ---: | ---: |
| 008 | 0.600 / 1.219 | 560 | 0.962 / 1.395 |
| 009 | 0.621 / 0.379 | 652 | 0.827 / 0.886 |
| 010 | 0.558 / 0.418 | 994 | 0.695 / 0.768 |
| 011 | 0.423 / 0.282 | 1,095 | 0.676 / 0.677 |

| Pair | Primary common stars | Native P95 (px) | Extra common stars | Extra native P95 (px) |
| --- | ---: | ---: | ---: | ---: |
| 008–009 | 51 | 0.691 | 166 | 0.920 |
| 008–010 | 33 | 0.650 | 176 | 0.948 |
| 008–011 | 22 | 0.896 | 132 | 0.966 |
| 009–010 | 47 | 0.662 | 229 | 0.818 |
| 009–011 | 29 | 0.723 | 146 | 0.816 |
| 010–011 | 49 | 0.606 | 304 | 0.742 |

Use the larger of the two directional P95 values in original detector pixels. All six pairs missed the strict 0.5 px overlap target on both samples. The WCS and star-level evidence replayed byte for byte. Separate reports record the training and selection candidates, the prior TAN scores on the same primary sample, individual detector regions, and final pair errors. See `output/phase8d-validation-spatial-20261123/nightscape-20mm/`. [Wide-field tracking](../questions_open_topics.md#q-016---plate-solve-quality-incorrect-scale-recovery-and-distortion)

### Nightscape validation of elongated star centers

Hold the accepted 35 mm SIP headers, sky masks and Gaia identities fixed. Use the stored SEP windowed centers as the control. On training and selection stars, compare tapered elliptical moments, an elliptical Gaussian and a uniform Gaussian trail profile. Select the midpoint of the SEP position and a signed-flux moment measured in a two-sigma elliptical core with a one-sigma taper. The 35 mm selection mean pair P95 fell by 0.01987 px, with two pairs improving and the third increasing by 0.00867 px. Preserve this choice for the 20 mm transfer. Refit the same SIP model families on common training identities with both centroid methods. Save both refits before measuring either held-out sample.

The 35 mm fixed-WCS mean pair P95 rose by 0.033 px on the primary holdout and 0.051 px on the larger disjoint holdout. In the larger sample, the lower-axis-ratio stratum below 0.65 worsened on all three pairs. Median aperture sky S/N per frame was 6.33–6.74 on this sample and 16.99–18.30 on selection. Refit with the alternative and the larger-sample pair P95 values are 0.983, 1.081 and 0.988 native px. In this refit, frames 1 and 3 miss the 1.0 px overall Gaia limit at 1.074 and 1.063 px. The 35 mm 2–3 pair is the sole result under 0.5 px, on the primary holdout with SEP at 0.482/0.459 px on the original WCS and 0.479/0.451 px with the matched-training SEP refit. The larger sample still misses the overlap gate.

At 20 mm the alternative improves all six primary pairs with WCS fixed. The closest is 009–010 at 0.519/0.522 native px and it reaches 0.534/0.537 px after refitting. On the larger sample, the alternative refit gives 0.817–1.017 px pair P95. Its overall Gaia P95 exceeds 1.0 px on frames 008 and 009 at 1.121 and 1.005 px. All alternative edge scores remain within 1.5 px at both focal lengths. The primary stamp measurement loses 4 of 730 stars at 35 mm and 26 of 453 at 20 mm to saturated green cores. Failures and their matching SEP controls are recorded by sky S/N, shape, detector grid cell and radius. The alternative fails held-out qualification and the original mappings remain the reference.

The protocol, training-only headers, two-direction measurements, source checksums and exact commands are in `output/phase8d-nightscape-centroids-20261123/README.md`. The replay matched all 7,790 held-out frame measurements. The 64 previous control P95 values reproduced exactly. Thirty-two focused source tests and the Poetry lock check passed. The fixed-WCS comparison measures the effect of changing the centers under that mapping. A separate budget for lens distortion, profile asymmetry and noise remains open. [Q-016 tracking](../questions_open_topics.md#q-016---plate-solve-quality-incorrect-scale-recovery-and-distortion)

### Visible-band flat-field validation

Use twelve independent MOANA Lagoon lights, one 120 s exposure per RGB filter from each of four nights across the two tile pointings. Preserve the accepted individual WCS and use the 120 s master dark. The ASI1600MM detector raster, 1 × 1 binning, RGB filter names and TOP-DOWN order agree. Three strong dark defects recover at their stored positions on all twelve lights and fail the mirror, 180-degree and one-pixel controls. The masters' stored orientation gives the strongest inter-filter pixel-scale correlation. The 0.01 s flats report 4.96 e⁻/DN compared with 1.75987 on the lights and dark. The master history documents integration and provides no bias or matched short-dark provenance. Applying the normalized flats as supplied is a conditional diagnostic. [MOANA archive and camera configuration](https://erellaz.com/moana/open-datasets/)

Fit a separate exposure ratio per correction mode on training stars only. Reuse the same unsaturated S/N ≥ 100 aperture measurements and hold out complete spatial blocks. Ten of eighteen MOANA filter comparisons pass 0.5 native px and the sample floors. The cross-tile median moves are 2,851–2,935 px. Six reserved pair measurements cross a 2% response difference, all in red. Two of those are on a qualified overlap. None crosses 3%. Single application reduces P95 versus Off on four of ten supported comparisons and beats both Off and Twice on two. Once-applied absolute P95 is 2.450%–3.567% on supported comparisons.

Use three 350 s WFC3/UVIS F606W exposures of 47 Tuc from program 11452 as the documented visible reference. CALWF3 marks bias, dark, flat and chip-flux corrections complete. The archive's `zcv20548i_pfl.fits` is identified on every science frame and matches both native chips. Recover Off by multiplying the FLT by the PFLT, use the archived science as Once and divide it by the flat for Twice. Retain both chips' distorted WCS and apply the same local pixel-area factor to stellar apertures in every mode. This comparison isolates the flat multiplicative step with a reconstructed Off state. [HST flat construction](https://hst-docs.stsci.edu/wfc3dhb/chapter-5-wfc3-uvis-sources-of-error/5-4-uvis-flat-fields) · [HST additive and flat calibration](https://hst-docs.stsci.edu/wfc3dhb/chapter-3-wfc3-data-calibration/3-2-uvis-data-calibration-steps)

The two supported HST overlaps have native P95 of 0.072 and 0.106 px and 15 and 16 test stars. Off/Once/Twice absolute aperture P95 is 2.555/2.784/3.918% on the first and 4.507/4.484/4.466% on the second. The single ≥2% response match on the first overlap improves from 1.832% Off to 0.559% Once and rises to 3.150% Twice. A third overlap has ten test stars against the 15-star floor. It contains the only ≥3% response match. The complete test aperture samples exceed the 1% P95 target.

All 18 native detector/chip masks and all sampled common footprints agree across modes. Diffuse brightness, fixed-block contrast and changes in relative peer P95 are recorded for every overlap. Once reduces diffuse P95 versus Off on eleven of eighteen MOANA comparisons and two of three HST comparisons. Source checksums matched, both analysis reports reproduced byte for byte, and all 17 focused source tests passed. The calibrated flat provenance, normalized detector-domain operation and coverage have visible-band evidence. Repeatable aperture improvement on sufficient high-signal stars crossing several percent response remains open. Commands, full two-direction geometry, source identifiers and measurements are in `output/phase8d-visible-flat-20261123/README.md`. [Q-029 tracking](../questions_open_topics.md#q-029---configurable-color-photometry-and-optics)

### F438W wide dithers from RAW

Screen nine 350 s F438W exposures of 47 Tuc and nine 708 s F621M exposures of Omega Centauri before raw reduction. Use the distorted archive WCS, measured CRDS flat and common quality rules on a 0.04 arcsec/px TAN grid. The F621M sequence supplies no apertures through the frozen screening. Select WFC3/UVIS exposures `iaby01kcq`, `iaby01liq` and `iaby01lmq` from HST program 11452 using training response support. Before full processing, the selected WCS intersections cover 12,700–15,038 arcsec², or 48.13%–56.99% of the smaller footprint. Median same-chip motion is 1,400–2,051 px. There are 309 distinct unsaturated stars with S/N ≥ 100 in both exposures, including 154 crossing at least 2% and 70 crossing at least 3% measured PFLT response in a selected pair. Across the fixed reserved blocks those counts are 102, 44 and 15. [STScI measured flat construction](https://hst-docs.stsci.edu/wfc3dhb/chapter-5-wfc3-uvis-sources-of-error/5-4-uvis-flat-fields)

Run CALWF3 3.7.3 from the three MAST RAW files with `1681902ti_bia.fits` and `t3420177i_drk.fits`. The saved pre-flat products complete overscan, bias and dark correction. Apply `zcv2053si_pfl.fits` zero, one or two times with the same electron gain and chip sensitivity factor. The archive WCS, apertures and quality masks are fixed. The local Once result matches the independent FLT within `2e-4 + 2e-6 × |archive signal|` electrons on all 50,225,160 valid pixels. Of those, 48,556,021 are exact. [STScI calibration sequence](https://hst-docs.stsci.edu/wfc3dhb/chapter-3-wfc3-data-calibration/3-2-uvis-data-calibration-steps)

| Pair suffixes | Train / test stars | Reserved ≥2% / ≥3% | Native P95, worse direction (px) | All test Off / Once / Twice absolute P95 (%) |
| --- | ---: | ---: | ---: | ---: |
| `kcq–liq` | 69 / 40 | 18 / 4 | 0.0817 | 4.284 / 3.887 / 4.870 |
| `kcq–lmq` | 97 / 42 | 8 / 0 | 0.0539 | 6.671 / 6.398 / 6.313 |
| `liq–lmq` | 95 / 40 | 25 / 12 | 0.0859 | 7.746 / 7.062 / 6.620 |

Fit the exposure ratio independently for each mode using training stars only. The strongest link has 99 of 135 common stars crossing at least 2% response and 54 crossing at least 3%. Its twelve reserved ≥3% stars give 1.388%, 1.112% and 1.627% P95. The five of those with S/N ≥ 300 in both exposures give 1.293%, 0.666% and 1.263%. One application improves every complete sample relative to Off. All three complete samples exceed the 1% target, and two have a lower complete-sample P95 with Twice. The FLT path leaves pixel CTE uncorrected. Charge transfer, PSF changes and crowding remain plausible contributors to the aperture tails.

All six native masks and the sampled union and intersection masks agree across modes. One application changes fixed-quartile diffuse contrast by −7.50% to +1.62% across 178–204 retained sky blocks per pair. Scaled diffuse P95 improves versus Off on two pairs. The third exposure retains a median sky offset near +0.015 e⁻/s after the stellar scale, so the diffuse check remains relative. The local `output/phase8d-visible-flat-20261124/README.md` records source identities, counts at both S/N thresholds, reproduction commands and the per-chip and per-pair data. The replay reproduced the numerical reports, all nine mask arrays and the 18 pre-flat detector planes. The original F606W and MOANA result hashes match. [Optics tracking](../questions_open_topics.md#q-029---configurable-color-photometry-and-optics)

### F438W pixel CTE follow-up

MAST supplies matching CALWF3 3.7.3 FLC products for `iaby01kcq`, `iaby01liq` and `iaby01lmq`, each with `PCTECORR=COMPLETE` and the same SIP and table geometry as its FLT. Replay the three RAW exposures with `54l1347ei_cte.fits`, `zcv2057ni_bic.fits` and `01l21081i_dkc.fits` for pixel CTE, CTE bias and corrected dark. Disable the flat and chip photometric equalization for the saved pre-flat images. A single division by `zcv2053si_pfl.fits`, with the archive gain and chip sensitivity factor, matches all 50,187,153 valid FLC samples within the earlier detector tolerance. Of those, 48,522,699 match exactly. The replay preserves the 18 uncorrected detector planes from the FLT reference. [Archive and replay evidence](../output/phase8d-visible-flat-cte-20261124/README.md) · [STScI pixel CTE](https://hst-docs.stsci.edu/wfc3dhb/chapter-6-wfc3-uvis-charge-transfer-efficiency-cte/6-4-the-pixel-based-model)

Keep the 102 distinct test stars and all 122 pair memberships from the FLT comparison. Additional FLC hot-pixel flags require intersecting the valid native offsets across both exposures and both calibration branches. Each aperture retains at least 98.74% of its weight. Apply Off, Once and Twice on that support and fit the exposure ratios on the fixed training stars. The complete test sample determines the 1% absolute aperture P95 gate. The larger of the two native geometry directions stays below 0.5 px in every pair, including a separate check with CTE-corrected centers.

| Pair suffixes | Test stars | CTE geometry P95, worse direction (px) | Uncorrected Once P95 (%) | CTE Off / Once / Twice P95 (%) |
| --- | ---: | ---: | ---: | ---: |
| `kcq–liq` | 40 | 0.081 | 3.892 | 4.042 / 3.956 / 4.929 |
| `kcq–lmq` | 42 | 0.054 | 6.552 | 6.808 / 6.580 / 6.281 |
| `liq–lmq` | 40 | 0.109 | 12.120 | 12.487 / 12.062 / 11.543 |

The same-support pooled Once P95 changes from 6.664% to 6.619% with CTE. All pairs miss the 1% target. Restricting the sensitivity check to clear central 3 px gives 6.603% pooled CTE Once P95. One `liq–lmq` core mask shifts the uncorrected aperture error from 1.45% to 12.00%. The largest error on that pair changes from 38.33% to 38.15% with CTE. The absolute correction is larger at lower signal across the detector appearances (Spearman ρ = −0.673). Residual absolute errors have ρ = −0.269 with the weaker stellar signal, +0.071 with the farther parallel transfer distance and +0.003 with the distance difference. The high-signal five-star subset crossing 3% response improves from 0.666% to 0.586% Once P95. [Tail and mask diagnostics](../output/phase8d-visible-flat-cte-20261124/README.md#aperture-error-tails)

All modes use identical native and sampled common support. The common sky lattice retains 121,757–143,888 samples per pair and 178–204 reserved source-masked blocks. Relative to CTE Off, one application changes fixed-quartile diffuse contrast by −9.24% to +1.78%. Both pairs with `lmq` retain a scaled Once sky offset of about +0.015 e⁻/s. The replay matches all four numerical reports, 15 mask files and 18 pre-flat planes. Thirteen focused tests passed. Visible flat qualification remains open on the complete stellar sample. [Coverage and repeat commands](../output/phase8d-visible-flat-cte-20261124/README.md#diffuse-structure-and-sky-coverage)

### Independent LMC F606W flat replay

Screen 34 WFC3/UVIS FLCs with their archive WCS, measured CRDS flats and separate sky blocks for candidate selection, training and final test. Select four 349 s LMC exposures from HST program 11444 visit 02 and two 350 s small-shift 47 Tuc exposures from visit 01 with matching detector, gain, filter, flat and flash settings. The exposures are independent of the program 11452 F438W observations. Lock the exposure IDs, memberships and rules before the final test. Use all eligible S/N ≥ 100 stars and report the S/N ≥ 300 diagnostic. The strongest wide link, `iabj02abq–iabj02afq`, has 43 common stars, including 21 and seven crossing 2% and 3% response, at a median selection displacement of 1,618 px. Across the 52 distinct LMC test stars, seven cross 2% and one crosses 3%. [Candidate screen, inputs and protocol](../output/phase8d-visible-flat-independent-20261124/README.md#sources-and-prescreen) · [STScI WFC3 astrometric calibration](https://hst-docs.stsci.edu/wfc3dhb/chapter-4-wfc3-images-distortion-correction-and-astrodrizzle/4-1-wfc3-geometric-distortion)

Replay CALWF3 3.7.3 from RAW with the archive overscan, CTE bias and dark references and pixel CTE enabled. Keep the pre-flat detector planes in DN. One division by `zcv20548i_pfl.fits` with the archive gain and chip scaling matches all 100,351,695 valid native FLC samples within the F438W detector tolerance across the six exposures. All modes have identical 12 native masks and seven sampled sky mask sets. Use the same apertures and train each mode's exposure ratio on the training stars. All frozen memberships retain support. [Calibration and native coverage](../output/phase8d-visible-flat-independent-20261124/README.md#native-calibration)

| Pair suffixes | Test stars | Native geometry P95, worse direction (px) | Complete test Off / Once / Twice flux P95 (%) |
| --- | ---: | ---: | ---: |
| `a6q–a7q` | 15 | 0.093 | 7.237 / 7.792 / 10.330 |
| `a6q–abq` | 9 | 0.069 | 4.682 / 3.977 / 4.521 |
| `a6q–afq` | 11 | 0.085 | 2.756 / 2.358 / 2.536 |
| `a7q–abq` | 12 | 0.070 | 2.026 / 1.669 / 2.857 |
| `a7q–afq` | 20 | 0.052 | 2.047 / 2.506 / 3.884 |
| `abq–afq` | 9 | 0.067 | 1.422 / 1.464 / 3.835 |
| `zxq–zzq` repeat | 14 | 0.241 | 1.965 / 1.871 / 2.007 |

All LMC overlaps meet 0.5 native px in both directions. All miss the 1% Once flux gate. Four also fall below the 15-star sample floor. Once improves over Off on three LMC overlaps and improves over Twice on all six. The descriptive repeat control has a 40.61 px median motion and a 0.166% median flat response change. Its 14 test stars are all below 0.5% response change. The Once flux P95 is 1.871% and its robust scatter is 0.699%. [Final stellar scores and repeat control](../output/phase8d-visible-flat-independent-20261124/README.md#final-stellar-measurements)

Common LMC sky coverage is 50.90%–84.89% of the smaller footprints at 8 px spacing. In the 22–43 reserved source-masked blocks per pair, Once changes the bright-minus-faint contrast by −2.15% to +4.33% relative to Off. Once reduces the scaled diffuse peer P95 on two LMC pairs. The repeat keeps 97.61% common coverage and shows a scaled Once sky offset of +0.08319 e⁻/s. The numerical replay reproduces eight JSON reports and 19 mask files from the checked pre-flat planes. The earlier F438W CTE comparison reproduces four reports and 15 masks, and all 177 protected evidence hashes match. The visible flat gate remains open. [Diffuse and sampled coverage](../output/phase8d-visible-flat-independent-20261124/README.md#coverage-and-diffuse-brightness) · [Replay commands and verification](../output/phase8d-visible-flat-independent-20261124/README.md#reproduction)

### Independent F606W repeatability control

Replay the `iabj01zxq–iabj01zzq` diagnostic with its frozen 73 training and 14 test stars. The training-only Once scale of 0.998347811 changes absolute test P95 from 1.709% at unity to 1.871%. The three scaled errors above 1% are −1.045%, −2.785% and −1.379%. The first is on the lowest-S/N star. The largest error is on a star with S/N 479/459 and typical annular scatter. Its equivalent SEP width changes by 1.25 px, and the 3–10 px aperture region accounts for −2.116 percentage points of the error. The third star has the largest annular quadrant spread, 18.58/17.76 e⁻/px, beside a brighter neighbor 24.5 px away. That local structure motivates a single Huber sky plane on the existing annulus. [47 Tuc diagnostic and per-star measurements](../output/phase8d-f606w-repeatability-20261124/README.md#diagnostic-pair)

Use three public 348 s FLCs, `ibnh07nnq`, `ibnh07o7q` and `ibnh07ojq`, from GO-12379 visit 07 on 2010-11-20. The full-frame WFC3/UVIS F606W configuration, 1 × 1 binning, gain, amplifiers, zero flash, no charge injection and named flat match the diagnosis. Exclude its exposures and matched stars. Complete-tap enrollment reaches only 5–11 eligible stars per frame. Freeze the 10 px aperture on paired valid native offsets with clear central 3 px, at least 98% aperture weight and 90% annulus taps before any selection photometry or final scoring. Both methods use the same stars, centroid, valid pixels and aperture geometry. The trained annulus median beats the alternate in pooled selection, 2.179% versus 2.209% P95, and retains the pre-test method choice. [Archive provenance and frozen rules](../output/phase8d-f606w-repeatability-20261124/README.md#independent-archive-repeat)

| Pair suffixes | Test stars / blocks | Left / right geometry P95 (native px) | Median P95 (%) / stars >1% | Huber P95 (%) / stars >1% |
| --- | ---: | ---: | ---: | ---: |
| `nnq–o7q` | 96 / 42 | 0.03527 / 0.03527 | 3.952 / 26 | 4.090 / 30 |
| `nnq–ojq` | 102 / 43 | 0.01876 / 0.01876 | 5.107 / 30 | 5.375 / 31 |
| `o7q–ojq` | 95 / 43 | 0.02315 / 0.02315 | 4.086 / 22 | 3.982 / 23 |

The 293 test memberships span 151 distinct stars and 48 blocks. Every link meets the 0.5 px native geometry limit in both directions. Median test motion is 0.018–0.034 px and flat-response P95 is 0.015%–0.024%. All links exceed 1% flux P95 with and without the training scale. The S/N ≥ 300 diagnostic also exceeds 1% at 1.547%–2.318%. Use the complete small-shift test P95 to decide when to screen the same setup for wide dithers with sufficient 2% and 3% response crossings. The current screen is deferred and visible flat qualification remains open. The earlier F606W and F438W numerical reports and mask arrays reproduce. [Scores, evidence and repeat commands](../output/phase8d-f606w-repeatability-20261124/README.md)

### F606W aperture-profile repeatability

Measure cumulative 3, 5, 7 and 10 px flux on the original 47 Tuc pair and opened GO-12379 triangle with their frozen centers, common valid native offsets, fractional pixels and 14–19 px annulus median. In T09, the signed 3–10 px contribution is −2.310 percentage points of a −2.785% error. In the 5–10 px shell the contribution is −1.983 points, against 0.084 points from aperture ERR and 0.053 from random sky. Its 5/10 flux fraction changes by +1.819 points with a 0.095-point random uncertainty and a quadrant-sky sensitivity range of +1.531 to +2.210 points. Eighteen distinct stars in the old triangle meet the same profile evidence rule. The quadrant sky sensitivity spans 35 of that triangle's 78 errors above 1%. [Same-support diagnosis](../output/phase8d-f606w-profiles-20261124/README.md#same-support-diagnosis)

Screen all 21 pairs among the seven unscored Visit 07 FLCs and exclude the previously opened F606W and F438W test stars by sky position. The freeze picks `ibnh07nvq`, `ibnh07nzq` and `ibnh07obq` and fixes the entire sample before result scoring. Fit one robust spatial plane of `log(F10/F5)` per exposure and chip and use its prediction to scale 5 px flux to the 10 px reference. Fit both methods' exposure ratios on training stars. The candidate improves pooled selection P95 from 3.406% to 2.036% but raises `nvq–nzq` from 3.450% to 3.471%. The frozen per-link selection rule retains 10 px. [Frozen membership, provenance and selection](../output/phase8d-f606w-profiles-20261124/README.md#independent-group-and-method-selection)

| Pair suffixes | Test stars / blocks | Geometry left / right P95 (native px) | 10 px flux P95 / stars >1% | Corrected 5 px P95 / stars >1% |
| --- | ---: | ---: | ---: | ---: |
| `nvq–nzq` | 92 / 45 | 0.01691 / 0.01691 | 2.424% / 30 | 1.764% / 16 |
| `nvq–obq` | 78 / 42 | 0.02615 / 0.02615 | 2.350% / 21 | 1.826% / 15 |
| `nzq–obq` | 88 / 43 | 0.02641 / 0.02641 | 4.337% / 23 | 2.531% / 11 |

Both directions pass the 0.5 px geometry target. The selected method's full-test flux P95 exceeds 1% on each link, so the 2% and 3% flat-response prescreen remains deferred. The change in 3–10 px wing asymmetry toward a detected neighbor has the strongest association with absolute 10 px error. Pooled Spearman ρ is 0.539 with a 95% block-bootstrap interval of 0.408–0.644. SEP width change gives 0.216 and aperture ERR gives 0.195. The asymmetry shares aperture pixels with the error and can reflect profile variation, blending or local artifacts. The largest repeated error on the `obq` links includes a +13.4 to +13.5 percentage-point contribution at the same native offset. The new profiles, all frozen scores, and the earlier F606W and F438W numerical references replayed. [Uncertainty, per-star data and commands](../output/phase8d-f606w-profiles-20261124/README.md)

#### Native residual follow-up

The fresh Visit 07 replay confirms the three 10 px P95 values above and the +13.434 and +13.499 percentage-point contributions at offset (−3, +1). In `ibnh07obq`, the native UVIS2 peak has 7,124.1 e⁻ SCI, 87.9 e⁻ ERR and zero science and flat DQ. Its 3 × 3 patch accounts for 85%–88% of the full error. Two comparable stars on the same chip stay below 0.58% on all links. The Visit 07 sky and detector predictions round to the same pixel in both peers. Three separate GO-12379 exposures place the opened target on UVIS1, with the original UVIS2 pixel independently measurable. The five-tap native impulse is +5,241.9 e⁻ in `obq` and peaks at +13.53 e⁻ across the independent sky and detector probe neighborhoods. This supports an exposure-specific excess of the observed amplitude. Its physical origin remains open. [Native cutouts, neighbors and replay](../output/phase8d-f606w-native-20261124/README.md#visit-07-replay-and-detector-inspection)

The independent no-injection WFC3/UVIS F606W exposures `ibnh08hlq`, `ibnh11byq` and `ibnh13heq` use shutter B and 348–350 s, compared with shutter A and 348 s for Visit 07. Both sets use the same flat and pixel CTE model. The freeze excluded earlier test stars in sky coordinates, locked paired native validity masks, and assigned training, selection and test blocks before scoring. Each flux scale is the median ratio of training stars only. The 95 test memberships represent 62 stars in 34 blocks. [Frozen rules, sources and chronology](../output/phase8d-f606w-native-20261124/README.md#frozen-independent-observations-and-results)

| Pair suffixes | Test stars / blocks | Left / right geometry P95 (native px) | Full-test 10 px flux P95 | Stars >1% |
| --- | ---: | ---: | ---: | ---: |
| `hlq–byq` | 31 / 18 | 0.05885 / 0.05891 | 6.049% | 13 |
| `hlq–heq` | 34 / 28 | 0.04902 / 0.04904 | 5.932% | 9 |
| `byq–heq` | 30 / 21 | 0.06271 / 0.06266 | 4.680% | 10 |

No fresh star meets the frozen compact-wing rule. One fresh star meets the coherent-wing rule on both links to `hlq`, with −9.634% and −8.779% full errors. A post-score native cutout check finds an exposure-specific impulse in `hlq`, while the signed wings outside its 3 × 3 patch still contribute 2.31–3.33 points in the same direction. That remainder leaves exposure-dependent PSF variation, unresolved blending and distributed detector effects to distinguish. All three geometry-qualified P95 values exceed 1%, so the 2% and 3% wider-dither flat-response screen stays deferred. Next, test whether a local empirical PSF fitted on training stars predicts the distributed wing residual on a separate same-configuration repeat. [Scores, verification and rerun](../output/phase8d-f606w-native-20261124/README.md)

#### Independent local F606W PSF test

The unscored 30 s GO-12379 FLCs `ibnh08hrq`, `ibnh11c0q` and `ibnh13hgq` share the F606W UVIS detector configuration, measured flat and pixel CTE reference of the native residual experiment. These short exposures use shutter A and zero charge injection. Previous test stars were excluded by sky position. The freeze binds the paired native masks, 117 test memberships in 37 sky blocks and each same-exposure, same-chip training neighborhood. Training stars supply the empirical pixel templates and the exposure scales. The test prediction uses the left core for amplitude and no test-wing intensity. Selection fixed the 700 px spatial bandwidth before the test. [Frozen protocol, sources and training](../output/phase8d-f606w-local-psf-20261124/README.md#observations-and-freeze)

| Pair | Test stars / blocks | 3–5 px null / PSF MAE (pp) | 5–10 px null / PSF MAE (pp) | Left / right geometry P95 (px) | 10 px flux P95 / stars >1% |
| --- | ---: | ---: | ---: | ---: | ---: |
| `hrq–c0q` | 36 / 25 | 0.801 / 0.438 | 0.466 / 0.607 | 0.07998 / 0.08006 | 2.403% / 11 |
| `hrq–hgq` | 45 / 29 | 0.749 / 0.483 | 0.553 / 0.560 | 0.03582 / 0.03583 | 1.752% / 8 |
| `c0q–hgq` | 36 / 26 | 0.305 / 0.578 | 0.377 / 0.570 | 0.07834 / 0.07823 | 2.325% / 9 |

The first two links meet the inner-ring criterion, with 23 of 26 and 27 of 28 well-signed changes correctly predicted. Removing each observed 3 × 3 peak patch from the observations and model templates retains nominal inner-ring MAE gains of 28.6% and 24.3%, with both intervals spanning zero. The prior compact rule flags one single-link excess. Outside its patch the model predicts the sign of the 3–5 px change and leaves most of its magnitude. No 5–10 px link improves magnitude error, and only two to six changes per pair have well-measured direction. The prediction hypothesis therefore has inner-ring support on two links, and no link supports both rings. [Prediction errors, direction and patch checks](../output/phase8d-f606w-local-psf-20261124/README.md#wing-prediction-results)

All three links pass native geometry and miss the complete 10 px photometry target. The wider-shift 2% and 3% flat-response screen remains deferred. The fresh replay reproduces all test measurements and fitted inputs. Next, use one independent no-injection F606W repeat with enough bright reserved stars to test a phase-resolved empirical PSF on the 5–10 px ring. [Photometry, audit and rerun](../output/phase8d-f606w-local-psf-20261124/README.md#unchanged-10-px-photometry)

#### Independent F606W within-pixel PSF test

Four previously unscored 348 s no-injection Visit 07 FLCs supply 357 test memberships from 120 stars in 47 sky blocks. The archive inputs, common native masks, roles and donors were sealed before scoring. All pairs have 32–41 test stars that meet the core- and ERR-based precision proxy. The challenger adds local fractional x/y slopes to the previous 700 px template, which already weights donors by fractional phase proximity. The pair scales and both templates use training data only. [Observations, support and protocol](../output/phase8d-f606w-phase-psf-20261124/README.md#observations-and-freeze)

The x/y-slope model increases block-balanced 5–10 px MAE by 50.2%–72.9% over zero change and 35.8%–88.4% over the previous local PSF. All paired block intervals for improvement lie below zero. The 4–8 well-signed stars per pair occupy 4–7 blocks and fall below the ten-star direction floor. The model also misses the 3–5 px criteria on every pair, and the outer-ring error increase persists outside the 3 × 3 patches. [Primary and secondary pair tables](../output/phase8d-f606w-phase-psf-20261124/README.md#primary-510-px-ring)

Both native geometry directions pass on all six pairs at 0.021–0.046 px P95. The unchanged 10 px full-sample flux P95 spans 2.455%–6.828%, with 10–21 stars above 1% per pair. The 2% and 3% wider-shift flat-response screen stays deferred. The independent replay reproduces 21 evidence files byte for byte and both numerical summaries. With median detector shifts of 0.059–0.195 px and few well-signed outer changes, the next sample should have long, no-injection F606W exposures with deliberate offsets near half a native pixel in both axes. [Photometry and replay](../output/phase8d-f606w-phase-psf-20261124/README.md#unchanged-10-px-aperture-photometry)

### F606W two-axis half-pixel archive screen

The F606W screen registered a 0.40–0.60 native-pixel interval on both axes before inspecting the candidates. It retained the 0.30 arcsec sky exclusion, common-pixel rules, same-chip training support and the 0.50 percentage-point outer-ring precision proxy. The local and public archive intake covered 559 distinct roots and 99 centroid-screened pairs. One pair met the two-axis phase rule and fell short of blind stellar support. [Protocol, sources and pair table](../output/phase8d-f606w-half-pixel-20261124/README.md)

GO-11680 Visit 02 commanded the four-point UVIS box pattern. Its two unscored 610 s FLCs `ib2d02fwq` and `ib2d02g0q` use shutter A without charge injection or flash. Steps 2 and 3 have a nominal (−1.5, +2.5) px separation. Six fresh same-chip matches give median fractional shifts of 0.570 px in x and 0.543 px in y. All six fall inside the interval on both axes. One of two proposed test stars survives common native pixel support, and the donor checks leave zero qualified test stars. The limiting appearance has fewer than eight training stars on either chip. [Observation and support evidence](../output/phase8d-f606w-half-pixel-20261124/README.md#confirmed-planned-and-measured-displacement)

PSF prediction and full-sample 10 px photometry remain unevaluated for this screen. The 2% and 3% wider-shift flat screen remains deferred. The next task is to obtain a long, configuration-matched F606W series with the same deliberate two-axis phase step in a field that supplies at least 15 precision-qualified test stars across three blocks after the common-pixel and donor checks.

### Richer-field F606W follow-up

The follow-up retained the detector setup, source exclusions, both-axis tolerance and stellar support rules. It measured 109 new links across coordinated GO-12517 and GO-13410 visits and an Omega Centauri parallel pair. Thirty-four have nominal half-pixel steps on both axes. None reaches the simultaneous centroid gate. [Intake, plan and complete measured pairs](../output/phase8d-f606w-half-pixel-followup-20261124/README.md)

GO-12517 M5 supplies 206 fresh same-chip matches on its richest nominal pair. The median fractions are 0.431 px in x and 0.508 px in y. Only seven stars meet both limits simultaneously, with about 0.90° of measured relative field rotation. GO-15594 has zero matches with its active WCS and eight with the common archived IDC solution in a sensitivity check. Two of those eight meet the joint gate. [Measured centroid distributions](../output/phase8d-f606w-half-pixel-followup-20261124/README.md#realized-phases)

The PSF and full-sample 10 px photometry decisions remain open, with the wider flat-response screen deferred. Prioritize a same-visit long F606W series with guide-star continuity and a compact diagonal dither in a field rich enough to retain at least 15 precision-qualified test stars across three blocks.

### Compact same-visit F606W dither screen

The registered survey resolved 1,065 FLC roots from 258 visits with documented compact offsets and measured all 18 new configuration-matched links. GO-16361 Visit 03 (NGC1916) and Visit 05 (NGC1754) both command (+0.059, −0.095) arcsec and retain the same guide-star acquisition within each pair. The 408 s and 414 s links realize median native fractions of (0.456, 0.445) and (0.517, 0.494) px, respectively. Each result comes from one fresh UVIS1 star. GO-12020 supplies 66 matches, with zero jointly inside 0.40–0.60 px. The other 15 links supply no reciprocal same-chip matches under the frozen catalog rules. [Survey, distributions and reproduction](../output/phase8d-f606w-compact-dither-20261124/README.md)

The one star on each phase-qualified link falls in a training block and lacks paired common aperture pixels. Both links have zero eligible test stars and insufficient same-chip donors. The 5–10 px PSF comparison and full-test 10 px photometry remain unevaluated. The 2% and 3% wider-shift flat screen remains deferred. The next task is to qualify one intentionally dithered stellar calibration field in the same configuration, with an intra-orbit diagonal and enough isolated bright stars to pass common-pixel, donor-phase and 5–10 px precision checks.

### Same-orbit F606W stellar field preflight

The targeted follow-up checked 348 archived FLC headers across 99 visits, using recorded command offsets for WFC3 patterns beyond the earlier parser. Seven fresh same-target links in GO-16361 survive configuration and prior-use screening. The nominal two-axis diagonal at NGC 1835 in Visit 01 uses shutter B at both positions. The two 408 s shutter-A FLCs `iedx01ahq` and `iedx01alq` share a verified guide-star acquisition and command an approximately (+8.005, +3.022) px offset. Their blind preflight yields one and six fresh eligible catalog stars, zero reciprocal matches, and zero common-aperture, donor-supported or precision-qualified test stars. [Archive inventory and replay](../output/phase8d-f606w-stellar-preflight-20261124/README.md)

PSF prediction and 10 px photometry remain unevaluated. Obtain one deliberately dithered M5 sequence with long shutter-A F606W exposures at both positions in a single guide-star acquisition. The previous M5 pair supplies a populated field reference with 206 matches. A new sequence must pass the frozen realized-phase and reserved precision checks before scoring. [M5 field and requested dither](../output/phase8d-f606w-stellar-preflight-20261124/README.md#next-observation)

### M5 F606W acquisition check

The M5 cone and target searches resolve 12 individual FLCs from 11 archive records. GO-11615 supplies four 150 s images. Each of the four GO-12517 visits supplies one 350 s shutter-A FLC and one shutter-B FLC. Visit 13 commands a two-axis half-pixel step and shares one verified fine-lock acquisition. Its B-to-A pointing diagnostic measures median fractions of 0.472 px in x and 0.599 px in y, with 138 of 270 stars in range on both axes. The chip counts are 3/116 on UVIS1 and 135/154 on UVIS2. This archive result leaves the shutter-A PSF and 10 px photometry tests open. [Archive and centroid evidence](../output/phase8d-f606w-m5-acquisition-20261124/README.md)

The local observing worksheet orders four 350 s exposures at P0, P0, P1 and P1 in one uninterrupted visit. With alternating shutters it provides an A exposure at both positions for either initial blade. The arithmetic budget is 40 min 32 s, or 46 min 20 s with an allowance for a final serial dump. An allocated HST program and APT orbit and guide-star validation are needed to execute the visit. The frozen experimental and photometry gates still apply to the resulting data. [M5 observing worksheet](../output/phase8d-f606w-m5-acquisition-20261124/observing-visit.md)

### M5 APT feasibility check

APT 2026.5.1 Orbit Planner places all four 350 s exposures in one non-interruptible orbit, with one modeled FGS acquisition, one dither maneuver and zero overruns. The Visit Planner's single-gyro CASM calculation returns three positive visibility windows. The local Cycle 34 test has no observing allocation or guide-star selection for an execution date. The next dependency is an allocated HST program with guide-star confirmation for the chosen roll and date. The PSF and 10 px photometry checks remain open pending the executed shutter-A data. [Planner inputs, outputs and replay](../output/phase8d-f606w-m5-apt-20261125/README.md)


### NIRCam dithered detector-flat reference

Use NIRCam detector NRCB2, filter F150W and the Clear pupil from JWST program 1074. The three equal 96.631 s exposures from the same May 21, 2022 visit were deliberately dithered. Each has a 2048 × 2048 Level 2a `rate` file and a separate Level 2b `cal` file. They share the matching superbias `jwst_nircam_superbias_0246.fits` and dark `jwst_nircam_dark_0338.fits`. Those additive corrections are already complete in the `rate` input. The `cal` primary header identifies the detector-native reference `jwst_nircam_flat_0675.fits` under CRDS `jwst_1584.pmap`. [JWST program 1074](https://www.stsci.edu/jwst/phase2-public/1074.pdf) · [Calibration stages](https://jwst-docs.stsci.edu/jwst-science-calibration-pipeline/stages-of-jwst-data-processing)

The reference checks the detector, filter, pupil, array origin, exposure and calibration state before dividing the signed rate samples by the archived flat response. It masks samples flagged in either input, nonfinite values and response below 0.2. It compares the resulting science data after applying the archive's `PHOTMJSR` unit factor. Poisson and read-noise variances are divided by response squared and scaled by the square of the photometric factor. The archive's additional flat-uncertainty contribution is separate. [JWST flat-field and DQ propagation](https://jwst-pipeline.readthedocs.io/en/1.17.x/jwst/flatfield/main.html)

All 12,327,893 valid detector samples across the three exposures matched the separate `cal` products exactly, including 343,398 negative values. The full binary masks matched for all three exposures, and both propagated variance planes matched at every valid sample. Each reference read covers at most 304 × 304 pixels including the aperture halo. The tool checks all seven source hashes before and after processing. [Detector-flat reference tool](../tools/phase8d_nircam_flat.py)

Measure point-source repeatability at matched centroids in the original detector coordinates. Use the same valid aperture support for all modes. Measure a five-pixel aperture with a 7–10-pixel sky annulus and at least 25 times the local aperture noise. Match stars within one pixel on the 0.031 arcsec/px comparison grid using the archive's TAN-SIP WCS. Fit a relative flux scale separately for each mode on the training blocks and reserve whole final blocks as in the existing 8D split. The flat comparison holds coordinates fixed and includes a double-application control.

| Pair | Held-out geometry P95 | Median detector shift | Final stellar apertures | Flux error P95 Off | Flat once | Flat twice |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 00001–00002 | 0.221 px | 340 px | 28 | 12.17% | 10.89% | 12.83% |
| 00001–00003 | 0.313 px | 680 px | 22 | 9.10% | 9.62% | 9.59% |
| 00002–00003 | 0.206 px | 340 px | 31 | 13.05% | 10.63% | 10.06% |

The largest dither supplied eight reserved stars in eight blocks that crossed at least 1% flat response. Their flux-error P95 fell from 7.70% to 5.54% after one correction, and rose to 7.99% after two. The median signed error for those stars was −2.50% after one correction. The other edges supplied three such stars each. The dataset establishes an exact independent detector-output reference and meets the native geometry target. Stellar repeatability across all edges and broadband RGB qualification remain open. The preceding WFC3/IR search supplied larger detector moves as well. The January 2026 visit in program 17963 carries a guide-star failure and the alternate WFC3 trial supplied only two to three final apertures per edge. [HST 17963 observation strategy](https://www.stsci.edu/hst/phase2-public/17963.pro)

Download the matching `rate` and `cal` files with exposure numbers `00001` through `00003` using the stem `jw01074001001_06101_<exposure>_nrcb2`, plus the flat reference. The tool pins their SHA-256 values because MAST may reprocess archived observations. [MAST data access](https://archive.stsci.edu/datadownloads.html) · [CRDS reference file access](https://www.stsci.edu/hst/instrumentation/reference-data-for-calibration-and-tools)

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$nircam = 'output/phase8d-candidates/space-flat'
.\.venv\Scripts\python.exe -m tools.phase8d_nircam_flat $nircam -o "$nircam/nircam-reference-check.json"
```

Choose a new JSON filename for each run. Two runs reproduced the local `nircam-reference.json` byte for byte with SHA-256 `8e4c3426c0ba9739750f3955ea1feb700589bcd00c62d94c4d7511ca54004b94`.

### NIRCam F200W large-dither flat reference

Use the six 21.474 s NRCB4 F200W exposures from JWST program 1476, visit `01476001012`, observed on July 11, 2022. These are dither positions 4–9 of the LMC calibration field. NRCB4 has a documented region with several percent response variation. The archive products use CRDS context `jwst_1584.pmap`, flat `jwst_nircam_flat_0720.fits`, superbias `jwst_nircam_superbias_0216.fits` and dark `jwst_nircam_dark_0341.fits`. The flat header identifies commissioning program 1063 as its first in-flight input. The published Cycle 1 sky-flat selection used exposures of at least 300 s. [Program 1476 observing plan](https://www.stsci.edu/jwst/phase2-public/1476.pdf) · [NRCB4 flat response](https://jwst-docs.stsci.edu/jwst-near-infrared-camera/nircam-performance/nircam-flat-fields) · [Cycle 1 flat calibration](https://www.stsci.edu/files/live/sites/www/files/home/jwst/documentation/technical-documents/_documents/JWST-STScI-008607.pdf)

The independent `cal` files matched all 24,940,290 valid science samples, including 9,313,850 negative samples, all six binary masks, and the two propagated variance planes. The replay reads windows no larger than 304 × 304 pixels. Ten of the 15 overlaps met the 0.5 px geometry target on the 0.031 arcsec/px grid. Their held-out P95 ranged from 0.318 to 0.470 px and their median detector displacements ranged from 781 to 1,753 px.

Use the same five-pixel apertures, 7–10-pixel annuli and whole 64-pixel blocks as in the F150W comparison. Require an estimated aperture S/N of at least 100 in both exposures, using the original `rate` error plane and the uncertainty of the local sky median. All three flat modes share the apertures that pass. Fit the relative flux scale separately for each mode on the training blocks. A pair with fewer than eight training apertures reports the aperture and block counts with a null scale. The report also gives counts and residuals for apertures crossing at least 1% and 2% measured response differences.

| Exposure pair | Geometry P95 | Training / final apertures | Final flux error P95 Off | Flat once | Flat twice |
| --- | ---: | ---: | ---: | ---: | ---: |
| 00001–00005 | 0.428 px | 13 / 3 | 3.04% | 0.82% | 3.74% |
| 00001–00006 | 0.415 px | 11 / 4 | 4.11% | 2.58% | 3.63% |
| 00002–00003 | 0.318 px | 9 / 5 | 3.31% | 2.00% | 4.52% |
| 00002–00006 | 0.388 px | 11 / 7 | 2.64% | 1.39% | 2.63% |

One flat application produced the lowest full-sample P95 on all four measured overlaps. The magnitude of the signed median error after one application ranged from 0.11% to 0.60%. The 1% response subsets contained up to four final stars on a pair, and only two scored pairs had a star crossing 2%. Each row uses three to seven final apertures in distinct blocks. The production optics gate needs more reserved stars, and visible RGB photo validation remains open. The earlier NRCB4 F200W triplet from program 1074 also matched the archive exactly. Its three edges had four to seven high-signal training apertures each and yielded no fitted exposure scales.

Get exposures `00001` through `00006` with the stem `jw01476001012_02101_<exposure>_nrcb4`, both `rate` and `cal`, plus the matching flat. The diagnostic pins the SHA-256 of all 13 source files. [MAST JWST public mirror](https://registry.opendata.aws/mast-jwst/) · [CRDS F200W detector flat](https://jwst-crds.stsci.edu/unchecked_get/references/jwst/jwst_nircam_flat_0720.fits) · [Replay tool](../tools/phase8d_nircam_flat.py)

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$nircam = 'output/phase8d-candidates/space-flat/photometric/01476'
.\.venv\Scripts\python.exe -m tools.phase8d_nircam_flat $nircam --reference nrcb4-f200w -o "$nircam/reference-check.json"
```

Choose a new JSON filename for each run. The local archive URLs and checksums are in `sources.json`. The two F200W reports matched byte for byte with SHA-256 `21fa658bf5531e3185cfdd638a1aca3614d0780d63032733b60d1ad60921cdd3`. The local Windows replay took 25.2 s and peaked at 109.8 MiB working set and 121.2 MiB commit with one OpenBLAS thread. The original F150W report also retained its SHA-256.
