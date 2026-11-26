# Phase 8 Configurable Color Photometry and Optics

**Status** Closed on 2026-11-26 at the request of the project owner. [Phase 8 closure](#phase-8-closure)

**Verified milestones** The 8A contract is frozen. The 8B photo export passed local Windows verification in `0.1.0b11`, adaptive preview and crop in `0.1.0b12`, and preserved tone and transparent canvas in `0.1.0b13`. The 8C color and exposure workflow passed local Windows verification in `0.1.0b14`. [Architecture and milestones](../astro_mosaic_python_first_architecture_en.md#106-phase-8-delivery-stages) · [8C Windows results](#8c-local-windows-package-results)

AstroMosaic 0.1.0b7 already frames selected sky panels from their WCS, decodes recognized sRGB TIFFs for Visual Preview and renders scientific mosaics from compatible linear inputs. Its optional scientific relative refinement currently uses mono panels. The new options extend those paths through the same bounded CPU renderer. [Current sky workflow](phase-3c.md#desktop-workflow) · [Existing relative refinement](phase-2.md#relative-refinement)

[8A contract](#8a-frozen-photo-export-contract) · [Settings](#workflow-and-settings) · [Input profiles and color](#input-profile-and-color-conversion) · [Exposure and brightness](#exposure-and-brightness-matching) · [Lens geometry](#lens-geometry) · [Vignetting](#vignetting-and-flat-field-correction) · [Delivery stages](#delivery-stages)

## 8A Frozen photo export contract

8B adds a distinct sky export intent. A completed, covered visual sky preview provides the selected band, resolved grid and linked display statistics for the desktop export. The headless command resolves the saved or automatically fitted grid and, for preview tone, samples the same final preview grid. It never needs a Qt session. Project manifests and scientific output keep their existing contracts. Visual input eligibility precedes the render, with diagnostics naming the affected panel.

The table records the initial 8B output through beta 12. [Beta 13 photo tone and transparency](#8b-photo-tone-and-transparency-follow-up) extends the photo TIFF layout and sets the default tone.

| Selection or input | 8B behavior |
| --- | --- |
| Photo, all selected panels are RGB UInt16 TIFF with recognized embedded matrix/TRC sRGB | Read original pixels and masks through the validated WCS, including its SIP terms when present. Decode canonical sRGB before bilinear sampling and validity-weighted blending. Keep effective input ICC fingerprints, WCS origin, weight, band, and tone in the output history or metadata. |
| Photo, an untagged, unsupported-profile, mono, or scientific panel in the selected band | Reject the first ineligible panel with its name. Profile assignment, mixed-profile conversion and a linear photo intent require their own qualified inputs in later stages. |
| Photo, missing WCS or sky, mixed bands without an effective band choice, or enabled scientific refinement | Report the failed prerequisite. Use existing sky masks and band selection. Additional exposure, camera response, brightness, lens and illumination corrections are off for this delivery. |
| Photo, **Use Preview Tone** | Apply the linked 1st and 99.5th percentiles measured on the final covered preview, falling back to the full sampled range if the percentiles coincide. A flat range maps to 0.5. Apply the selected midtones transfer, then the canonical forward sRGB transfer and nearest-integer 16-bit quantization. Record the effective black point, white point and midtones. |
| Photo, **Preserve Tone** | Apply the canonical forward sRGB transfer and 16-bit quantization directly to the blended linear sRGB. Both modes clip to the representable range. |
| Photo TIFF | Write contiguous RGB UInt16 with the ICC profile in tag 34675, the celestial WCS and band in the AstroMosaic TIFF description, and the binary coverage in its SubIFD. Store zero RGB codes for missing coverage. A covered zero sample has mask value 1. Store a photo intent marker and omit scientific units. Publish at a new local path after the job completes. |
| Scientific sky export | Require compatible linear inputs. An explicit common-scale declaration cannot qualify encoded sRGB. Keep existing scientific FITS, TIFF and XISF samples, WCS, masks and optional mono refinements. |
| Foreground and composition | Use their existing export contracts. Phase 8B covers the sky photo layer. |

The output profile is the February 2015 revision of `sRGB2014.icc` from the International Color Consortium. Its size is 3,024 bytes and SHA-256 is `384b832de3412066743b52a75ee906b6fb9fb8d9e09e936fc2c43223815c6e0a`. The profile's embedded copyright identifies ICC and the registry permits redistribution and embedding under its general profile terms. The profile ships unchanged. Little CMS 2 identified the exact file as RGB v2, matrix/shaper, with sRGB colorants. The analytic transfer is the production conversion for 8B. [ICC profile and provenance](https://registry.color.org/rgb-registry/srgbprofiles#v2) · [Profile licensing](https://registry.color.org/profile-library/#license) · [sRGB transfer reference](https://www.w3.org/TR/css-color-4/#color-conversion-code)

| Reference | Frozen evidence and limits |
| --- | --- |
| Original owner `20.TIF` and `21.TIF` | Use the [recorded source SHA-256 values](../tests/integration/test_owner_tiff.py). Both 6000 × 4000 originals have the same embedded profile SHA-256 `2b3aa1645779a9e634744faf9b01e9102b0c9b88fd6deced7934df86b949af7e`. The local Gaia SIP solutions produce an 8917 × 10259 automatic TAN grid at 34.59134313160837 arcsec/px and 109,331 covered 445 × 512 preview samples, including 23,020 shared samples. Reuse this grid for the full export and verify both original hashes. |
| Analytic sRGB controls and real sampled tiles | Compare a double-precision decode, valid weighted bilinear blend, fixed tone and encode reference against the reopened TIFF within 2 UInt16 codes at corresponding pixel centers. Include the sRGB toe, RGB ordering, covered black, holes, and a coincident proxy grid. Require exact coverage at compared positions and published WCS within 1e-9 degrees of the resolved grid. Compare the CPU and OpenGL display with preview-tone references within one 8-bit level at base-level sample positions. |
| Linear FITS, TIFF and XISF with existing mixed-layer control | Preserve exact samples and masks, and WCS within 1e-9 degrees. Use the [Phase 6 parity products](phase-6.md#local-windows-lifecycle-and-package-results) and existing numerical TIFF and XISF references. Reuse PA4 only under the real-data protocol when replaying its Phase 6 or 7 outcomes. |
| Resource and failure checks | Require the default 64 MiB tile working-byte reservation and 2 GiB output limit on the real pair. The uncompressed photo payload is 7 bytes per output pixel, with TIFF and ICC overhead checked against the same limit. Record elapsed time and cache state. Exercise cancellation during tile writes, verify no output or part file remains, then retry the same destination. Check refusal of an occupied destination, unsupported output format and grids without coverage. |

The initial ICC and exposure references are frozen in 8C. Independent lookup-table and rendering-intent references, measured lens calibration, compatible flats and stable exposure brackets are tracked in Q-029. [8C reference results](#8c-frozen-color-and-exposure-references)

## 8B Export a photo mosaic

1. Add the tagged sRGB TIFFs, plate solve the sky panels and select the sky band when the project contains several bands.
2. Choose **Build Preview**. Use **Auto Frame** to fit the solved footprints or turn it off to use the saved sky grid.
3. **Preserve Tone** encodes the blended linear colors directly and is the default from beta 13. Choose **Use Preview Tone** and set **Midtones** to apply a display stretch at full resolution.
4. Choose **Export Photo Mosaic** and a new TIFF path. The export uses the preview's full grid, with the original panels sampled at each output pixel. **Use Preview Grid** can adopt the framing for subsequent saved-grid work. The File menu has **Export Scientific Mosaic** for the scientific sky workflow.

The Command Panel accepts `session export-photo -o "Mosaic.tiff"` after a completed covered visual sky preview. It uses the active band, grid and tone controls.

```powershell
astromosaic project export-photo "Solved.astromosaic" -o "Natural.tiff" --grid auto --progress --json
astromosaic project export-photo "Solved.astromosaic" -o "Stretched.tiff" --tone preview --midtones 25
```

Without `--grid`, the CLI uses the project's saved preview mode. `--midtones` alone selects preview tone for existing scripts. Omit `--band` for a project with one effective sky band. The JSON result contains the resolved grid mode, effective tone and render measurements. [Current photo TIFF format](#8b-photo-tone-and-transparency-follow-up)

### 8B Photo tone and transparency follow-up

Beta 13 writes contiguous RGBA UInt16 with TIFF associated alpha. The coverage alpha is 65,535 for covered pixels, including black sky, and zero for areas outside valid panel coverage. RGB codes are zero wherever alpha is zero. The ICC profile, WCS description, band and tone metadata describe the same sky grid. The tile writer accounts for eight bytes per output pixel plus TIFF and ICC overhead and publishes atomically.

AstroMosaic reopens beta 11 and 12 photo TIFFs using their binary coverage SubIFD. Open beta 13 photo TIFFs in beta 13 or an editor that supports 16-bit TIFF alpha. Source panels remain the render inputs when re-exporting a previously stretched photo. [Photo alpha and tone decision](adr/0028-transparent-photo-tiff.md)

The copied beta 13 console exported the original 8917 × 10259 owner grid using the default tone. Every RGB code matched the earlier Preserve Tone reference. The alpha matched its coverage at all 43,897,047 opaque pixels and 47,582,456 transparent pixels. The ICC profile, WCS and original file hashes matched their references. The 731,841,752-byte TIFF fit the default output and working reservations. On the same covered grid, the sampled median code value was 7,878 DN with Preserve Tone and 33,410 DN in the owner's earlier preview-tone export. The respective counts of pixels with at least one channel at full scale were 5,844 and 228,623.

The copied CPU and OpenGL desktops exported the same real footprint crop as the console, matching the full TIFF's crop exactly. Photoshop 27.7 opened the full TIFF as a 16-bit layer with transparency and reproduced the expected alpha in a PNG crop. The nine scientific references matched their samples and masks. The full source suite passed 235 tests with two native cases skipped offscreen, and three native checks passed separately. Ruff, scoped mypy and the Poetry lock check passed. [Local Windows packages](windows-release.md#verification-status)

### 8B Source verification

The double-precision test covers both tone modes, weighted linear-light bilinear sampling, the sRGB toe, coincident preview and export positions, covered black, WCS and output limits. LibTIFF reopens the UInt16 RGB plane and Little CMS identifies the embedded profile. The source Windows **Preserve Tone** export of the real pair completed in about 184 seconds. Independent projection, interpolation and encoding at 4,966 covered locations measured a maximum error of one UInt16 code. Coverage matched at the compared locations, including 1,047 overlap samples and 5,417 uncovered positions.

Source tests passed 231 cases with the previously measured OpenCV wheel available through the isolated Phase 7 test environment. Four native checks passed separately, including both opt-in OpenGL checks and the 630-pixel multi-band layout. The lockfile, Ruff and scoped mypy checks passed. [Numerical and failure checks](../tests/numerical/test_preview.py) · [Desktop and CLI parity test](../tests/integration/test_desktop_project.py) · [Native viewport checks](../tests/integration/test_sky_viewport.py)

### 8B Adaptive preview follow-up

The desktop overview now uses masked area subsampling. Zoom requests full-resolution detail from the visible grid region. The crop editor shows the full grid and lets the user apply a rectangle in output pixels. A version 9 project records per-field automatic framing locks or the automatic mono refinement choices when used. Earlier manifests retain their saved grid and numeric refinement settings. The fixed 512-edge point sample defines the photo tone on the active export grid in both the desktop and CLI. [Controls and persistence](phase-3c.md#adaptive-framing-and-interactive-crop) · [Preview decision](adr/0027-adaptive-sky-preview.md)

The beta 12 source suite passed 234 offscreen checks with the isolated SIFT test dependency. Four native Windows checks passed separately, including both opt-in OpenGL checks. The targeted cases verified mono match-radius bounds, valid-area averaging, exact 1:1 samples, fitting locks, live refresh after a panel edit, crop reset and cancel, and version 9 save and reopen. Ruff, scoped mypy and the lockfile check passed.

The portable desktop and console were built from clean source `99491ad34bbd6cb6469c0f8f7d8bcdf35793baa8` using the Poetry lock. The copied CPU and OpenGL runtimes replayed the original pair with their saved Gaia WCS on the second display. They cancelled and rebuilt the overview, retained the fixed beta 11 tone reference, and loaded the 851 × 226 visible detail in 0.71 and 0.72 seconds respectively on the development host. The warmed full overviews took about 22 seconds with the tests running concurrently. Native framebuffer and screen captures also confirmed the OpenGL detail and the visible crop bounds.

Both desktops dragged and applied the same 1137 × 889 crop at source-grid position (3890, 5096). The reopened project preserved the rectangle and the cropped photo matched the console byte for byte. Independent reopening of Preserve Tone matched all 1,010,793 coverage entries and UInt16 RGB codes against the corresponding region in the full beta 11 reference. Corner and center WCS matched to the measured precision. Nine scientific and layer references also matched on the copied console. A separate clean-machine installation and redistribution review remain open. [Windows launchers](windows-release.md#verification-status)

### 8B Local Windows package results

The final beta 11 bundles were built with CPython 3.13.18 and the Poetry lock from clean commit `e644768177da5013d9aa909621bc38a3d45756ce`. The packaged desktop on the secondary display solved both original TIFFs with the local Gaia catalog. Each backend built a 445 × 512 visual preview and showed the complete export button text at the compact width. Cancelling after tile progress cleared the temporary TIFF and retained the preview. The CPU button workflow and the OpenGL `session export-photo` command both retried successfully at the original destination.

Both desktop modes and the copied Qt-free console produced byte-identical 8917 × 10259 TIFFs with **Use Preview Tone** at midtones 37. The original input hashes matched. The TIFF contained 43,897,047 covered pixels and its SHA-256 was `7d4bc6f6ac2ceb45ca584475d623ac42eae5349b115b761d2e699ce29925828f`. Independent LibTIFF and Little CMS reopening checked RGB UInt16 and the sRGB2014 profile. The WCS matched within 1e-9 degrees and the independent sample and coverage comparison repeated the source bounds.

| Copied workflow | Photo export time | Resource measurement |
| --- | ---: | --- |
| Native desktop CPU | 208.33 s | 230.80 MiB peak working set and 200.18 MiB peak commit |
| Native desktop OpenGL | 207.71 s | 304.29 MiB peak working set and 308.31 MiB peak commit |
| Standalone CLI | 222.52 s | 20,328,667 peak reserved tile bytes across 5,670 tiles |

The three jobs ran concurrently on a Windows 11 Pro x64 build 26200 host with an i5-14600K and RTX 4070, after earlier reads of both 6000 × 4000 inputs. The desktop figures cover the parent process through solve, preview and export. The CLI reservation tracks the renderer's bounded buffers. The output occupied 640,362,687 bytes.

The source and copied console also matched nine real scientific and layer references for float32 values, coverage, applicable contribution masks and WCS. These included the M17 and atlas chain FITS, the M42 solved FITS, wide RGB TIFF, ALPACA sky and foreground plus FITS and XISF composition, and Paranal TIFF composition. The two historical PA4 exports retain the current encoded-sRGB scientific rejection. A separate clean Windows installation run remains open. Local measurements and the independent reopen report are in `.tooling/desktop-0.1.0b11/`. [Windows launchers and build records](windows-release.md#verification-status)

### 8B Owner overlap baseline

The overlap diagnostic replays the original `20.TIF` and `21.TIF` with the saved Gaia SIP solutions and the full beta 13 Preserve Tone export. It projects linear-light samples from each original onto the 8917 × 10259 TAN grid and checks the normalized weighted mean against the TIFF. The WCS matched at nine positions. Coverage matched at all 9,951 lattice positions, including 4,764 covered positions, and the largest RGB difference was one UInt16 code. The two source SHA-256 hashes matched their frozen references before and after the run. [Replay tool](../tools/phase8_photo_overlap.py) · [Real-data regression](../tests/integration/test_phase8_photo_overlap.py)

| Stellar comparison | Matches | Median | RMS | P95 |
| --- | ---: | ---: | ---: | ---: |
| Saved WCS, all matched stars | 221 | 0.340 px | 0.424 px | 0.692 px |
| Saved WCS, held-out stars | 56 | 0.374 px | 0.430 px | 0.751 px |
| Trial translation, same held-out stars | 56 | 0.338 px | 0.423 px | 0.662 px |

The tool detected stellar centroids independently in each original, paired mutual nearest neighbors, and removed candidates with a clipped or invalid sample in either aperture. It reserved every fourth pair in output-x order when fitting the translation. That split tests the translation relative to the saved WCS. The trial shift applied to the second panel's positions was (+0.042, +0.101) output pixels. Both held-out P95 values exceed the 0.5 px starting target. [Numerical targets](../astro_mosaic_python_first_architecture_en.md#11-validation-and-acceptance-criteria)

On the 96 px lattice, 697 of 1,001 common positions survived the detected-star and clipping masks. The median paired difference `20.TIF − 21.TIF` was −0.000136 in linear Rec. 709 luminance on the unit scale. The absolute difference had a median of 0.00776 and a P95 of 0.03089. Rank correlations with position, detector radius and sampled horizontal overlap width had magnitudes of 0.18 or less on this pair. The horizontal width is the count of common grid samples on each row times 96 px. A radial illumination fit requires independent calibration evidence.

At the left edge of `20.TIF`, 78 crossing strips measured a median step of +0.00039 and a P95 absolute step of 0.01160 in linear luminance. At the right edge of `21.TIF`, 59 strips measured +0.00301 and 0.01204, respectively. Each estimate uses the star-masked overlap samples 2–8 source pixels inside the entering panel's boundary and checks the continuing panel's coverage on both sides. It measures the contribution added by the weighted mean relative to the continuing panel on the same output pixels.

On the development host, reproduce the run with the saved project used for the beta 13 reference export.

```powershell
.\.venv\Scripts\python.exe tools/phase8_photo_overlap.py .tooling/desktop-0.1.0b11/final-owner-cpu/Owner.astromosaic output/phase8b13/Photo-mosaic-preserved-transparent.tiff
```

The diagnostic emits JSON with input fingerprints, sample support and per-edge results. The local result is in `output/phase8-overlap/owner-baseline.json`. The subsequent spatial holdout checks the stellar residuals with both a same-camera pair and an independent observatory control. Use the background samples to compare the 8C exposure and offset candidates on held-out regions. [Spatial holdout results](#8b-spatial-holdout-and-alignment-controls) · [Q-029](../questions_open_topics.md#q-029---configurable-color-photometry-and-optics)

Two warm-cache source runs on an Intel Core i5-14600K with one OpenBLAS thread reproduced the measurements. The 64 MiB window budget took 26.5 seconds with a 183.0 MiB peak working set and 189.6 MiB peak commit. The 32 MiB replay took 27.5 seconds with a 159.9 MiB peak working set and 166.8 MiB peak commit.

### 8B Spatial holdout and alignment controls

Divide the matched-star extent on the output grid into nine rectangular regions. Hold out each occupied region in turn and compare the saved WCS, a median translation, and a least-squares similarity transform with translation, rotation and uniform scale. Each fit uses the other regions and requires at least 12 training pairs and a smaller-to-larger positional singular-value ratio of at least 0.05. Score all three models on the same held-out stars. Report individual regions with at least five matches. The outer statistic combines matches within an outer 20% strip of either source detector and requires at least ten pairs. [Replay tool](../tools/phase8_photo_overlap.py)

| Observations and output scale | All / outer matches | Saved WCS P95 | Translation P95 | Similarity P95 |
| --- | ---: | ---: | ---: | ---: |
| Owner `20.TIF`–`21.TIF`, 34.591″/px | 221 / 167 | 0.692 / 0.691 px | 0.713 / 0.716 px | 0.757 / 0.762 px |
| PA4 `10.TIF`–`11.TIF`, 34.595″/px | 117 / 112 | 1.148 / 1.142 px | 1.007 / 1.008 px | 0.919 / 0.903 px |
| ESO ALPACA A/B, 140″/px | 30 / 18 | 0.179 / 0.209 px | 0.183 / 0.213 px | 0.191 / 0.223 px |

The owner pair's highest regional P95 was 0.941 px in the upper-right block, supported by 21 stars. The median horizontal displacement changed sign across the overlap. Both global corrections increased the whole-region holdout P95 on this pair. The similarity fit improved the same-camera PA4 pair while its P95 stayed above the 0.5 px starting target. The independently exposed ALPACA pair stayed below 0.5 px with its saved WCS. Its retained FITS crops have no declared saturation threshold. The M17 atlas pair triggered the insufficient-support diagnostic with three matches. [PA4 capture and overlap inventory](application-test-findings.md#local-evidence) · [Independent ALPACA calibration](phase-6.md#calibrated-alpaca-mixed-reference) · [M17 source](application-tests.md#source-credits-and-fixture-limits)

The separate Gaia sidecar holdouts had P95 values of 0.781 and 0.764 source px for `20.TIF` and `21.TIF`. The outer values were 0.837 and 0.874 source px. For PA4 `10.TIF` and `11.TIF`, the corresponding whole-detector values were 0.831 and 0.901 source px. These are absolute catalog checks on the saved solutions. The table reports relative panel agreement in output pixels.

The owner command above also emits the spatial report. For the independent case, pass the saved ALPACA project by itself. The local PA4 control project selects frames 10 and 11 from the existing PA4 sky project and uses automatic TAN framing at native scale with zero rotation and no saved crop. The JSON reports under `output/phase8-overlap/` are `owner-spatial.json`, `pa4-10-11-spatial.json` and `alpaca-spatial.json`.

```powershell
.\.venv\Scripts\python.exe tools/phase8_photo_overlap.py output/application-tests/phase6b-work/alpaca-mixed/mixed.astromosaic
.\.venv\Scripts\python.exe tools/phase8_photo_overlap.py output/phase8-overlap/pa4-10-11.astromosaic
```

The Gaia holdout below compares the saved SIP solutions with fresh fits on both wide-angle pairs. The ALPACA case provides a separate control for already well-aligned geometry. [Numerical targets](../astro_mosaic_python_first_architecture_en.md#11-validation-and-acceptance-criteria) · [Open Phase 8 work](../questions_open_topics.md#q-029---configurable-color-photometry-and-optics)

### 8B Gaia holdout for WCS candidates

The replay reproduced all four saved SIP-3 headers with the installed Gaia DR3 catalog and blind index. Frame 10 matched when replayed with its original project and solve options. Its 1,500 raw detections matched at the original 128 MiB budget and the comparison's 64 MiB budget. The catalog and index SHA-256 values matched the local bundle manifest. The candidate comparison uses the frozen saved headers and the same original images and TAN output grids as the spatial holdout. [Local catalog setup](phase-2.md#catalog-setup-and-updates) · [Candidate comparison tool](../tools/phase8_wcs_validation.py)

Measure stars in linear-light sRGB and associate them with Gaia using the saved WCS and the solver's mutual-match and shifted-control checks. Reject clipped or invalid apertures. Reserve catalog matches whose measured and saved-projected positions are both more than five source pixels from the replayed raw solver detections. Exclude the union of those Gaia coordinates from both panel fits. Fit TAN, SIP-2 and SIP-3 to the same remaining stars. Check detector coverage, parity and inverse round trips. Score the fixed overlap pairs on their original output grid and use a separate overlap holdout with neither centroid near a raw solver or candidate fit position.

For this comparison, a candidate needs at least 10% lower whole-detector catalog P95 on each panel and outer catalog P95 within the existing Phase 3.6 allowance. The independent overlap needs at least 15 pairs, including 10 outer pairs, and P95 below 0.5 output px both overall and at the outer detector. These thresholds apply to the Phase 8 comparison. The plate solver retains its own astrometric acceptance criteria. [Existing SIP and edge limits](phase-36.md#6-sip-and-field-edge-accuracy)

| Panel | Reserved Gaia matches, all / outer | Saved SIP-3 P95, all / outer source px | Linear-light SIP-3 refit P95, all / outer source px |
| --- | ---: | ---: | ---: |
| `20.TIF` | 327 / 203 | 0.804 / 0.844 | 0.707 / 0.748 |
| `21.TIF` | 383 / 218 | 0.808 / 0.873 | 0.702 / 0.737 |
| `10.TIF` | 409 / 257 | 0.833 / 0.900 | 0.722 / 0.756 |
| `11.TIF` | 414 / 230 | 0.879 / 0.958 | 0.735 / 0.801 |

| Independent overlap | All / outer pairs | Saved WCS P95 | TAN P95 | SIP-2 P95 | SIP-3 refit P95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `20.TIF`–`21.TIF` | 42 / 32 | 0.748 / 0.748 px | 7.258 / 7.423 px | 6.219 / 6.247 px | 0.700 / 0.716 px |
| `10.TIF`–`11.TIF` | 25 / 22 | 1.348 / 1.375 px | 10.431 / 10.466 px | 7.248 / 7.336 px | 1.200 / 1.224 px |

The SIP-3 refit improved the absolute catalog P95 on every panel. The independent overlap still exceeded 0.5 px on both pairs. On the full fixed pair samples, the refit moved P95 from 0.692 to 0.720 px on the owner pair and from 1.148 to 0.885 px on the PA4 pair. The low-order candidates in this comparison leave the alignment gate open. Save the results as geometry evidence for later optical work. The exposure and ICC reference checks for 8C can proceed on qualified controls. [Phase 8 delivery stages](#delivery-stages)

Run the comparison from the checkout root. The local JSON and native solve replay evidence are stored under `output/phase8-overlap/wcs-candidates/`.

```powershell
.\.venv\Scripts\python.exe -m tools.phase8_wcs_validation .tooling/desktop-0.1.0b11/final-owner-cpu/Owner.astromosaic --catalog .tooling/phase2-gaia/stars-deep-gaia17.bin
.\.venv\Scripts\python.exe -m tools.phase8_wcs_validation output/phase8-overlap/pa4-10-11.astromosaic --catalog .tooling/phase2-gaia/stars-deep-gaia17.bin
```

## 8C Frozen color and exposure references

### Color patches and profile assignment

The reference derives double-precision RGB-to-XYZ matrices from the documented primaries and D65 white point, then converts into linear sRGB. It evaluates 11 RGB UInt16 patches, including the sRGB toe and saturated primaries, plus all 65,536 neutral input codes. The profile-assignment fixture holds the same RGB codes constant across embedded, explicitly assigned and untagged inputs. It defines precedence, expected linear triplets, and outcomes for conflicts and invalid profile bytes. The TIFF check verifies that these inputs preserve their stored codes. [ICC reference program](../tools/phase8c_color_reference.py) · [Profile-assignment fixture](../tests/fixtures/phase8c_profile_assignment.json) · [W3C color-space definitions](https://www.w3.org/TR/2026/CRD-css-color-4-20261029/#predefined)

Use relative colorimetric intent with black point compensation off for the first matrix candidate. Compare UInt16 and normalized float32 inputs to a float32 linear working buffer. The candidate limit is `1.5e-4` absolute linear error against the reference and `2e-7` between the two input representations. The neutral ramp must retain every step and the wide-gamut primaries must retain negative and above-one working values until output encoding.

| Profile tested | Maximum absolute linear error | Repeated neutral steps per channel | Result |
| --- | ---: | ---: | --- |
| Display P3 v4 | 0.00003221 | 0 | Matrix candidate passed |
| Adobe RGB compatible v2 | 0.00003756 | 0 | Matrix candidate passed |
| Sampled sRGB2014 v2 | 0.00030279 | 18,818 | Use the existing canonical sRGB transfer for this recognized encoding |

The locked `imagecodecs 2026.11.11` wheel uses Little CMS `2.20.0`. A separate Windows x64 PyInstaller probe reproduced the source report exactly with the same `_cms` binary and only system folders on `PATH`. Include `imagecodecs._cms` with the existing shared extensions when the matrix path is wired into the application package. The beta 13 package contains the Little CMS notice. Independent profile lookup-table, perceptual intent and black point compensation checks remain open. [Little CMS tutorial](https://www.littlecms.com/LittleCMS2.18%20tutorial.pdf) · [Native distribution review](../questions_open_topics.md#q-005---application-licensing-and-distribution-model)

### Exposure and background controls

Use a registered, unresampled 768 × 512 crop at source pixel (2048, 1408) in `20.TIF`. Decode the original samples with an independent sRGB calculation. Generate the paired UInt16 observations by applying a known linear gain and offset, then re-encoding. The affine reference uses `adjusted = gain × sample + offset`. Express the offset relative to the selected sky pedestal when comparing the Standard formulation. Keep coverage, masked photometry samples and the holdout separate. The fit uses the training blocks, and the P95 comparison and three stellar apertures use the reserved 64 × 64 blocks. This isolates photometry from reprojection and records the synthetic correction applied to a real capture. [Exposure reference program](../tools/phase8c_exposure_reference.py)

| Control | Known affine correction | Expected effective method |
| --- | --- | --- |
| Identity | Gain 1, offset 0 | Off |
| One stop | Gain 2, offset 0 | Manual +1 EV |
| Pedestal difference | Gain 1, offset −0.004 | Sky Offset |
| Gain and pedestal | Gain 1.25, offset −0.003 | Standard |
| Masked contamination | Gain 1.25, offset −0.003 with a masked brightness patch | Standard on the eligible samples |
| Weak gain | Gain 1, offset −0.0025 with low signal variation | Offset Only |
| Insufficient overlap | Same gain and pedestal with 16 training and 16 held-out samples | Off with a support diagnostic |

The independent reference calculation recovered gain 1.2500004 and offset −0.0030000 on the gain-and-pedestal control. On 61,057 held-out pixels, RGB P95 decreased from 0.002837 to 0.00000167 in normalized linear units. The largest stellar aperture-flux error across the usable controls was 0.00493%. Require gain within 1%, absolute linear offset within `2e-4`, held-out RGB P95 at most `3e-5`, and aperture-flux error within 1% on these controlled samples. The weak case has a training luminance span of `9.66e-5` between the 5th and 95th percentiles. A measurable gain control needs a span of `0.003` and at least 128 eligible samples in each split.

The unchanged owner TIFF metadata records 10 seconds, f/4 and ISO 6400 in both exposures. The metadata controls cover unity for equal settings with compatible provenance, a gain of two for half shutter time, four for doubling the f-number, and unresolved gain for missing aperture or an ISO change without a sensor response model. The owner pair remains the separate real overlap challenge.

The local reports and the 29 numerical arrays are under `output/phase8c-references/`. Its `reference-lock.json` records the program, profile, report, sample and Windows probe hashes. Run from the checkout root and choose a new path for each NPZ replay.

```powershell
.\.venv\Scripts\python.exe tools/phase8c_color_reference.py
.\.venv\Scripts\python.exe -m tools.phase8c_exposure_reference tests/20.TIF tests/21.TIF --samples output/phase8c-references/exposure-replay.npz
```

Use the frozen controls to implement the shared profile resolution and matrix conversion in preview and photo export, followed by exposure metadata, manual EV and Standard matching. The geometry and brightness gates still apply to the subsequent Distance Feather comparison. [8C regression checks](../tests/numerical/test_phase8c_references.py) · [Delivery stages](#delivery-stages)

## 8C Photo color and exposure workflow

1. In **Mosaic Settings → Photo**, choose the input profile, exposure normalization, and brightness matching for the selected sky band. **Auto (embedded or EXIF)**, exposure **Off** and brightness **Off** are the defaults.
2. In **Panel Settings → Photo**, inspect the source color, assign a profile if needed, and enter the panel EV when **Manual EV** is selected. The per-panel choice takes precedence. **Assume sRGB when untagged** supplies a fallback when the source has no usable declaration and no embedded profile.
3. Build the sky preview. The Command Panel reports the effective profile and provenance, exposure gain, reference panel, overlap support, brightness correction and fallback reasons. **Export Photo Mosaic** writes the same effective methods into the 16-bit TIFF history. The CLI also reports them in the `photo` object with `--json`.

The photo reader supports RGB UInt16 TIFFs. Assignable profiles include sRGB, linear sRGB, Display P3, Adobe RGB and local RGB matrix ICC files. Auto uses a supported embedded profile or an explicit EXIF/XMP sRGB declaration. Conflicts call for a named panel assignment. Manifest version 10 stores non-default photo settings, and an assigned file retains its local path and SHA-256. Older manifests load with the default controls. [Matrix color and overlap design](adr/0029-photo-matrix-color-and-overlap-fit.md)

```powershell
astromosaic project set-photo "Solved.astromosaic" -o "Photo.astromosaic" --panel-profile "2=DisplayP3.icc" --exposure metadata --brightness standard
astromosaic project export-photo "Photo.astromosaic" -o "Matched.tiff" --progress --json
astromosaic project export-photo "Photo.astromosaic" -o "Baseline.tiff" --exposure off --brightness off
```

The export overrides apply to one run. Use `--photo-profile` for the project default and `--panel-profile PANEL=inherit` to clear a panel override. Use `--exposure manual --panel-ev 2=1` for one stop on panel 2. Exposure metadata uses shutter and aperture for compatible cameras with matching ISO. Missing or conflicting capture values produce a unity gain with a reason.

**Sky Offset** fits linked RGB at unit gain. **Standard** estimates the sky pedestal and a linked affine correction using spatially separated fit and validation blocks. It requires at least 128 samples and two blocks in each split. The gain fit also requires a 5th-to-95th percentile luminance span of 0.003. The reference is selected by source path within the band, and eligible overlaps can extend that reference to connected panels. [Photo fit](../src/astromosaic/pipeline/photo_fit.py)

Photo preparation resolves working colors and reserves memory for retained ICC profiles. It fits overlap corrections on the full resolved grid so the overview, detail view, and cropped export use the same corrections. [Photo preparation](../src/astromosaic/pipeline/photo_preparation.py)

### 8C Local source results

| Control | Effective method | Gain | Affine offset | Frozen held-out RGB P95 |
| --- | --- | ---: | ---: | ---: |
| Identity | Off | 1.0 | 0 | 0 |
| One stop | Manual EV | 2.0 | 0 | 1.85e-6 |
| Pedestal | Sky Offset | 1.0 | −0.004000 | 1.56e-6 |
| Gain and pedestal | Standard | 1.249999 | −0.003000 | 1.67e-6 |
| Masked contamination | Standard | 1.249999 | −0.003000 | 1.67e-6 |
| Weak gain | Offset Only | 1.0 | −0.002500 | 1.11e-6 |
| Insufficient overlap | Off | 1.0 | 0 | 0.00510 |

The largest aperture-flux error was 0.00494%. The reopened Standard TIFF matched the independent RGB codes and coverage. On the mixed Display P3/sRGB control, Standard reduced held-out RGB P95 from 0.002860 to 2.83e-6. The source rendered nine scientific products that matched their references and retained both PA4 scientific eligibility diagnostics. Peak reservation was 23.83 MiB on the controlled preview and 63.78 MiB on the fitted owner grid.

The unchanged owner pair resolved a metadata gain of 1.0 for both panels. The overlap for `21.TIF` yielded 11,356 fit samples and 3,444 held-out samples. The gain candidate exceeded the fitting range, and the validation RGB P95 of 0.02927 favored Off over the sky offset. The wide-field geometry qualification remains open. [Gaia holdout](#8b-gaia-holdout-for-wcs-candidates)

The source suite passed 248 checks with two offscreen OpenGL skips. Native CPU and OpenGL runs exercised both Photo tabs, local ICC assignment, save and reopen, preview and export on the secondary display. The source CLI also exported a project whose panel name required escaping in redirected ASCII output. Ruff, scoped mypy and Poetry lock validation passed.

### 8C Local Windows package results

The local `0.1.0b14` desktop and console came from clean commit `2e39e7908b3f45d5e6258346571a57f45f3aedad` with the locked CPython 3.13.18 build environment. Both copied bundles loaded the same Little CMS 2.20.0 extension binary as the locked wheel. The desktop title and the CLI version identified beta 14. [Launchers and build records](windows-release.md#verification-status)

- On the secondary display, the CPU desktop exported the mixed-profile control through the photo button and the OpenGL desktop used `session export-photo`. Both reopened the version 10 project with the assigned ICC. Their RGB and alpha samples matched the standalone CLI and source over 389,120 covered pixels. Independent reopening checked UInt16 RGBA, the sRGB2014 ICC and WCS.
- The copied console tested metadata gain, Standard overlap diagnostics, and an export with a Unicode source name and redirected ASCII output. The full fitted owner pair reproduced beta 13 RGBA across the 8,917 × 10,259 grid with 43,897,047 covered pixels. A cold process rendering and independently comparing the result took 143.3 seconds and reserved 19.39 MiB at peak. Both original TIFF hashes matched the frozen reference.
- The copied console reproduced all nine scientific products, including the FITS, TIFF and XISF controls. It retained the PA4 scientific eligibility diagnostics on both grids. The local record is in `.tooling/desktop-0.1.0b14/release-verification/verification.json`. Clean-machine Windows acceptance and the native distribution review remain open. [Clean-machine gate](phase-3f.md#pending-clean-machine-check) · [Distribution tracking](../questions_open_topics.md#q-005---application-licensing-and-distribution-model)

## Workflow and settings

Keep **Add Panels → Plate Solve → Build Preview** as the short sky workflow. Once a preview has coverage, **Export Photo Mosaic** uses its selected sky band and resolved grid to render a full-resolution 16-bit TIFF. **Export Scientific Mosaic** uses the configured scientific grid and the existing calibration checks. **Use Preview Grid** can adopt the framing for that export. Expose method choices under **Mosaic Settings**, with source-specific overrides in **Panel Settings** and shared optical calibration for matching camera and lens groups.

| Setting | Selectable methods at their delivery stages | Proposed starting choice |
| --- | --- | --- |
| Input profile | Use embedded profile, assign profile, use declared linear data, assume sRGB | Auto recognition or explicit linear provenance. Show the evidence per panel. |
| Color conversion | Preserve linear samples, transfer curve and matrix, ICC color management | Use the smallest supported conversion for the declared input and output. |
| Exposure source | Off, manual EV and levels, exposure metadata | Off. Apply any selected normalization to the input used by the overlap fit. |
| Brightness matching | Off, sky offset, Standard, Advanced, stellar relative fit, joint exposure and color | Off in the initial photo delivery. Evaluate Standard as the later photo default. |
| Camera response | Known linear response, supplied curve, estimate from exposure brackets | Use documented source provenance. Bracket estimation is a separate research delivery. |
| Lens geometry | Existing WCS, catalog fit, calibrated lens profile, embedded optical calibration, manual radial or Brown–Conrady, shared optical fit, fisheye | Existing validated WCS for sky. Keep Phase 7 terrain pose selection independent. |
| Vignetting | Off, flat field, calibrated lens profile, manual radial, overlap fit | Off. Offer a matched flat as the first measured correction. |
| Blending | Validity-weighted mean, distance feather, optimal seam, multiband | Existing weighted mean initially. Evaluate distance feather for photo mosaics. |

A preset fills these individual fields. The initial photo preset uses supported embedded sRGB, linear sRGB as the working space, the current WCS and a tagged sRGB TIFF. The scientific preset uses the input sampling and unit contract and offers the established mono refinement. Expert users can change the eligible fields and inspect the effective methods before a build. Show the selected reference panel, applied corrections, and overlaps with too little evidence. [Surface brightness contract](adr/0002-surface-brightness-reference.md) · [Sky preview framing](adr/0025-automatic-sky-preview.md)

## Input profile and color conversion

### Use embedded profile

Read the embedded ICC profile and fingerprint the profile bytes, with bounded metadata and a validated RGB input match. Record the transfer curve, primaries or ICC transform, and source of the decision. Start with the recognized matrix/TRC sRGB TIFF path in beta 7. Extend recognition to other formats and profile classes as their readers gain test coverage. A credible EXIF color-space declaration can resolve a known photo profile when the ICC tag is absent. Treat profile conflicts as a named panel diagnostic and offer an explicit override.

Resolve an explicit panel override first, then an effective group or project override. Automatic interpretation checks the embedded ICC, then a supported declared color space. A photo panel with unresolved interpretation asks for a profile choice. The scientific preset independently checks the declared sample scale and filter.

### Assign a profile

Let the user choose sRGB, linear sRGB or an available ICC file for the panel or compatible input group. Assignment specifies how the stored numbers should be interpreted. The selected conversion then computes working-space values. Offer Display P3, Adobe RGB and ProPhoto RGB as assignable profiles when the implementation ships or locates verified profiles for them. Record whether the choice came from a file or the user. Use imported profiles and source images as read-only references.

### Use declared linear data

Use declared linear data for calibrated mono and compatible RGB FITS, TIFF and XISF. Retain the unit, scale and band provenance. Scientific export requires evidence for its sample scale and band. A TIFF container, a float sample type and a histogram shape are each insufficient evidence for detector linearity. [FITS unit keywords](https://fits.gsfc.nasa.gov/users_guide/users_guide/node22.html)

### Assume sRGB

Offer an explicit photo policy for untagged RGB images that the user knows share standard sRGB encoding. Display the assumption per panel and record it in exported history. Decode the samples with the standard sRGB inverse transfer curve. The profile choice applies to the color conversion. [ICC specification](https://www.color.org/specifications/ICC.1-2022-05.pdf)

### Preserve linear samples

Use the existing sample path when values are already linear in a compatible working representation. For scientific jobs preserve declared surface brightness, finite negative values, valid zeros, values above one, and the common validity mask. Preserve individual filters by default. Triplets assembled from narrowband exposures keep the spectral meaning of their channels and require an explicit mapping before display as a palette.

### Transfer curve and matrix

Decode known per-channel curves into float32 and map compatible RGB primaries with a verified matrix where needed. Set a common white point with a specified chromatic adaptation in the visual transform. The first fast path uses the current inverse sRGB transfer and its matching output encoding. Extend the analytic path only to documented profile shapes. Check encoded and linear reference patches, neutrals, the toe of the transfer curve and high-end values. Keep the decoding policy identical in preview and photo export. [sRGB characterization](https://registry.color.org/rgb-registry/srgb) · [Reference color conversions](https://www.w3.org/TR/2026/CRD-css-color-4-20261009/#color-conversion-code)

### ICC color management

Evaluate Little CMS 2 for ICC v2/v4 matrix and lookup-table profiles and transforms between supported photo working spaces. Use a verified high-precision path with float or supported high-bit-depth buffers. Treat relative colorimetric and perceptual as distinct output choices. Expose black point compensation only where the chosen transform supports it, with a test for shadow behavior. Use an independent profile transform to compare color patches, gamut boundaries and 16-bit gradients. Qualify the locked native dependency and notices on Windows before making this method available. [Little CMS transform and rendering-intent tutorial](https://www.littlecms.com/LittleCMS2.18%20tutorial.pdf)

### Working and output color spaces

Start with linear sRGB for the photo working space and tagged sRGB for the 16-bit TIFF. Evaluate linear Display P3 or another wide-gamut linear RGB representation for mixed profiles after the ICC path passes. Restrict general gamut compression and output transfer encoding to photo export. Fix the display mapping for the job from the preview settings and shared statistics so re-rendered tiles reproduce the selected appearance. Expose output profile and bit depth independently when additional output formats become eligible.

## Exposure and brightness matching

### Exposure correction off

Keep unit exposure gain and zero offset. Use this option for a consistent set of inputs or to compare a result against a fitted correction. A separately selected brightness fit still operates on the panel values.

### Manual EV and levels

Apply a panel gain of `2^EV` in the working linear domain. Allow linked RGB gain first. Per-channel gains and a black-level offset belong under advanced photo controls, with an effective value and reference saved in the project. Validate finite gains, offsets and their accepted range and offer a reset to unity gain and zero offset.

### Exposure metadata

Use compatible exposure metadata to seed or apply a relative exposure normalization. For camera panels, consider shutter time and aperture together. Use a documented sensor gain model before treating ISO as a calibrated multiplier. For astronomical stacks, inspect `EXPTIME`, integration time and whether the array contains sums, means or already normalized signal. Expose **Metadata only** and **Metadata as a fit prior** when supported. Missing, contradictory or ambiguous fields leave the factor unresolved. A selected automatic fallback displays the resulting method and reason. [PTGui exposure value and HDR metadata guidance](https://www.ptgui.com/faq)

### Sky offset

Measure robust backgrounds from valid source or overlap windows. Use source masks and reject stars, their wings, defects, saturated samples, bright nebulosity and contaminated regions. With a qualified background estimate, add an offset toward the reference sky level. Keep the gain at unity. An extended nebula or a masked horizon can leave too little independent sky. Report the failed fit and its evidence.

### Standard brightness matching

First align the sky pedestal with the reference using robust background samples. Next fit each panel against the reference or a deterministically accumulated connected mosaic, using corresponding overlap blocks on the chosen celestial grid. Scale the signal about the common sky level and allow a residual offset. Linked channels are the initial photo default. Per-channel gains are a separate option for compatible RGB panels with sufficient signal in each channel.

`adjusted = sky + gain × (sample − sky) + offset`

Use robust residual rejection and require spatial coverage and signal variation after masking. A weak gain fit retains a qualified sky offset and reports **Offset only**. A weak sky offset leaves the panel at identity under the documented auto policy. Report overlap area, retained samples, gain, offset, before-and-after residuals and the reference. Evaluate the method with several predetermined panel orders. Mosaic Master shows the precedent for sky pedestal and overlap matching. [Mosaic Master Standard method](https://github.com/setiastro/setiastrosuitepro/blob/V1.24.7/src/setiastro/saspro/docs/mosaic_master.html#L138-L145) · [Overlap implementation](https://github.com/setiastro/setiastrosuitepro/blob/V1.24.7/src/setiastro/saspro/mosaic_master.py#L5790-L5826)

Standard also requires independent stellar aperture evidence for material gains. When the evidence is weak or the gain fails the stellar check, use the validated sky offset or Off. [Production Standard gate](phase-8d.md#standard-photo-gain-integration)

### Advanced global matching

Freeze common sky samples and fit all qualified overlaps jointly. Each panel may have a gain, a background offset and optional plane slopes in normalized source coordinates. Anchor the chosen reference to unity gain and zero correction. Compare **Offset**, **Plane** and **Automatic model selection** with held-out samples. Enable a slope only with spatial support on the relevant axis and a measured improvement. Use noise-aware weights, robust rejection and confidence bounds. Compare connected components separately and show every component without a reference connection. A science blend that requires a single shared scale needs valid evidence across those components.

Use small sampled blocks and bounded accumulators for the solve. Read each source tile through the fitted corrections during final rendering. This controls memory even when most mosaic pixels have no coverage from a given panel. Benchmark the global fit against Standard on real multi-panel data and quantify preservation of stars and diffuse structures. [Mosaic Master global method](https://github.com/setiastro/setiastrosuitepro/blob/V1.24.7/src/setiastro/saspro/docs/mosaic_master.html#L411-L423) · [AstroMosaic background and gain contract](../astro_mosaic_python_first_architecture_en.md#64-relative-gain-and-background-correction)

### Stellar relative calibration

Reuse the existing anchored mono method. Estimate relative gains from background-subtracted aperture fluxes of unsaturated common stars in compatible passbands, then estimate offsets or planes from corresponding background samples. Surface brightness and integrated stellar flux use their respective pixel-area semantics. Report held-out star matches, gain uncertainty and residuals. Qualify an RGB extension only with independent per-channel or linked-signal evidence and compatible color and band provenance. [Current stellar method and acceptance cases](phase-2.md#relative-refinement)

### Joint exposure color and illumination fit

Evaluate a PTGui-inspired photo optimizer for linear-light overlap measurements. Fit relative exposure, optional per-channel balance, and a low-order additive flare or background term. A shared radial lens illumination curve can join the same solve after the simpler overlap and vignetting methods are qualified. Group lens terms by the calibrated camera, lens, focal length and aperture conditions. Fix the reference exposure and lens response at the optical center. Use distinct source radii, multiple supported overlaps and held-out areas to separate lens falloff from exposure and sky variation. Report which parameters were identifiable and retain the last qualified simpler method when the advanced fit lacks evidence. PTGui publicly documents overlap-based exposure, white balance, flare and vignetting adjustments. [PTGui Pro vignetting and color optimization](https://ptgui.com/examples/vigntutorial.html)

### Camera response and exposure brackets

Treat input profile decoding and camera response as separate parameters. Per the documented PTGui approach, define the camera response relative to values after the input profile transfer is decoded. [PTGui camera response and HDR workflow](https://ptgui.com/versionhistory.html)

#### Known linear response

Apply identity in the detector-response stage when the input's provenance supports it. Check that this choice preserves the calibrated samples before relative matching.

#### Supplied response curve

Import a measured monotonic response with a specified domain, normalization and inverse. Check the curve across its entire declared domain and report any samples outside that domain. Store it with the camera and processing conditions it represents.

#### Estimate response from brackets

Evaluate curve recovery from aligned exposures of the **same field** at known, distinct exposures. Reject saturated, clipped and low-signal samples. Validate against unused exposure levels and reject ambiguous fits. Use dedicated bracket data. Neighboring mosaic tiles supply different fields and call for overlap matching. [Debevec and Malik response recovery](https://www.pauldebevec.com/Research/HDR/debevec-siggraph97.pdf)

#### HDR and exposure fusion

Evaluate radiance-map HDR and exposure fusion as optional photo methods after bracket identification. HDR estimates relative radiance from valid exposures on a shared grid and uses the qualified response model. Exposure fusion selects locally useful brightness, contrast and saturation for the final appearance. Require stable alignment and real changes in captured exposure. [PTGui HDR workflow](https://ptgui.com/versionhistory.html) · [Mertens exposure fusion](https://www.cs.princeton.edu/courses/archive/spr14/cos426/papers/Mertens07.pdf)

## Lens geometry

### Existing WCS

Use the validated embedded or sidecar WCS in the original source pixel frame. An accepted SIP solution maps the detector directly to the sky, including its measured nonlinear distortion. That mapping owns the geometric correction for the default sky path. [Optical hints and WCS workflow](phase-3b.md#panel-wcs-and-plate-solve-hints)

### Catalog fit

Explicitly rerun the supported astrometric solver and compare its existing TAN and supported SIP models using catalog stars and held-out edge support. Use focal length and pixel pitch as initial scale hints. Promote the qualifying model and record the outer-field residual, spatial support and coordinate frame. [SIP model and edge gates](phase-36.md#36e--supported-sip-and-independent-edge-checks)

### Off for additional terrain lens geometry

Use the selected Phase 7 translation or similarity pose in the supplied terrain pixel frame. Switch to a calibrated lens mapping only after the chosen terrain pose is fitted in that calibration's coordinate frame. Use independent sky geometry for any mixed panel. [Terrain persistence and rendering](phase-7.md#7e-integrate-geometry-rendering-and-persistence)

### Calibrated lens profile

Resolve a user-supplied calibration or evaluate Lensfun for a matching camera, lens, focal length and sensor crop. Query distortion, lateral chromatic aberration and vignetting availability independently. Persist the database release, profile identity, applicable conditions and orientation or crop transform. Treat ambiguous matches as an explicit choice. For sky, solve or validate WCS in the profile's virtual rectified frame, then compose the inverse WCS and the profile mapping back to original samples. A raw-pixel SIP solution and a rectifying profile require selecting the intended geometry path before sampling. [Lensfun lens and calibration models](https://lensfun.github.io/manual/latest/group__Lens.html) · [Lensfun operation order](https://lensfun.github.io/manual/v0.3.2/corrections.html)

### Embedded optical calibration

Evaluate this option with future RAW or DNG support. Use only documented calibration payloads with a known pixel frame and decoder history. Record whether the converter already executed the relevant warp or illumination correction. An exported TIFF's lens make and focal length can identify an external calibration. The embedded method requires a supported correction payload and provenance. PTGui documents this path for selected DNG inputs. [PTGui embedded lens profile support](https://ptgui.com/versionhistory.html)

### Manual radial model

Import a radial transform with model name, units, optical center, normalization radius and mapping direction. A panorama radial polynomial can use the documented `a/b/c` convention when its coordinate transform is fully specified. Require a monotonic mapping across the valid radius and held-out improvement toward the corners. Save qualified coefficients as a reusable local profile. [PTGui lens calibration](https://www.ptgui.com/faq#6_3) · [PTGui lens parameter conventions](https://www.ptgui.com/faq#6_43)

### Brown–Conrady model

Use calibrated camera intrinsics and radial coefficients, with optional tangential terms for decentering. Start with the lowest order supported by the measurements and promote tangential terms only when an independent edge check improves. Validate inversion across the actual detector. Bind the calibrated focal lengths, principal point, dimensions and coordinate convention to the saved model. [OpenCV camera models](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html)

### Shared optical fit

Evaluate one common optical model for panels from the same camera, lens and focal length. Optimize the model against catalog stars for sky. Terrain requires qualified control points and camera-pose support under Phase 7. Use independent edge points or withheld panels to compare with fixed calibration and lower-order models. Promote extra parameters only after repeatable improvement. The existing near/far terrain rejection gates still apply when a common lens profile is available. [Phase 7 calibrated comparisons](phase-7.md#7d-real-observation-results)

### Fisheye models

Evaluate calibrated equidistant or equisolid projection candidates with angular coverage and distortion coefficients from the matching lens. Treat the usable image circle and projection domain as part of the calibration. Check inverse support, masks and held-out edge geometry across the full field. [OpenCV fisheye model](https://docs.opencv.org/4.x/db/d58/group__calib3d__fisheye.html) · [Lensfun lens models](https://lensfun.github.io/manual/latest/group__Lens.html)

### Lateral chromatic aberration

An optional calibrated profile supplies per-channel source coordinates around a reference channel. Validate the separation of red, green and blue stellar centroids toward the edges. Compose the channel offsets with the chosen lens geometry for direct sampling and propagate channel-aware validity. Qualify this option separately from the lens distortion profile. [Lensfun subpixel geometry](https://lensfun.github.io/manual/latest/structlfModifier.html)

## Vignetting and flat-field correction

### Off or already corrected

Record the calibration state per panel. **Off** is the default. A source previously flat-fielded or corrected by a RAW converter can be marked **Already Corrected** for that operation. Use one illumination model per panel. Surface gradients in the sky are handled by the selected background matching method.

### Flat field

Apply a compatible normalized two-dimensional master flat from the same optical train, sensor coordinates, focal length, aperture and filter as applicable. The source must have suitable linear samples and provenance for its additive calibration. Divide by the flat before geometric sampling. Carry the flat's bad-pixel mask and flag very low response regions before division. If variance weights are used, propagate the `1 / flat²` change. This option imports a measured calibration product. Master-flat construction belongs to a separately scoped calibration workflow. [Astropy ccdproc flat correction](https://docs.astropy.org/projects/ccdproc/en/latest/api/ccdproc.flat_correct.html)

### Calibrated lens vignetting

Use relative lens transmission from the matched lens profile. Verify focal length, aperture, crop and focus distance when required by the calibration. Evaluate the correction about the profile's center in original detector coordinates. Treat extreme or nonpositive transmission as out-of-domain and report affected coverage. An eligible vignetting profile can be selected independently of geometry when a raw-pixel WCS already models the lens distortion. [Lensfun vignetting calibration](https://lensfun.github.io/calibration-tutorial/lens-vignetting.html)

### Manual radial vignetting

Accept a measured curve or a low-order transmission model such as `T(r) = 1 + k1 r² + k2 r⁴ + k3 r⁶` in the stated radius coordinates. Apply a gain of `1 / T(r)` over its valid domain. Show center, corner gain and coverage in the preview. Evaluate a simple cos-fourth model as a visual reference when the optical geometry supports it. Scientific use requires a measured calibration and independent verification of the effective transmission.

### Overlap-fitted vignetting

Estimate a shared radial falloff from identical sky locations recorded at several sensor radii. Fit a positive low-order response anchored at the optical center while constraining exposure and additive level. Require broad radius coverage and a repeated reduction in held-out corner residuals. A single overlap strip, vignetted sources with unknown previous edits, or a field dominated by a real gradient may give an underdetermined fit. Report that outcome and offer a flat or a measured lens profile. [PTGui calibrated and overlap-based vignetting](https://ptgui.com/examples/vigntutorial.html)

## Blending and output

### Blending methods

Keep the normalized validity-weighted mean as the reference. Evaluate **Distance Feather** for photo mosaics with qualified alignment and brightness matching. The weight increases with distance from the valid panel boundary, with an adjustable transition slope. Measure seam residuals, support near holes and isolated stellar profiles. **Optimal Seam** and **Multiband** are later photo candidates. The former selects a path through low-disagreement overlap, and the latter controls transitions at multiple spatial scales. Validate rich star fields, fine structures, masks and tile halos before promoting either. [PTGui seam placement and blending](https://ptgui.com/whatsnew/120000) · [Mosaic Master distance weighting](https://github.com/setiastro/setiastrosuitepro/blob/V1.24.7/src/setiastro/saspro/docs/mosaic_master.html#L339-L353)

### Photo mosaic

Render the chosen grid and band from the source files at full resolution with the selected correction settings. Apply the chosen display tone and output ICC encoding once to the mosaic. First output is RGB 16-bit TIFF with sRGB ICC, WCS metadata and coverage for reopen in AstroMosaic. Verify which WCS/coverage representations survive an independent TIFF reader. Add PNG, JPEG or wide-gamut TIFF only with a separately verified geometry metadata or sidecar contract. Record profile policies, fitted corrections and the resolved grid.

Offer **Preserve Tone** for color encoding without an added stretch and **Use Preview Tone** for the fixed black point, white point and midtones chosen in the preview. Use the same tone parameters for every export tile. Preview the chosen encoding with the appropriate display transform and compare shared sample positions with a reopened TIFF in a color-managed reader. Establish an approved source for the embedded sRGB profile. [ICC sRGB profiles](https://registry.color.org/rgb-registry/srgbprofiles)

The first photo delivery covers the sky layer. Foreground and mixed photo exports depend on compatible input color representations, independent layer geometry and a qualified composition seam. Use the existing foreground and composition reference cases when extending the method to those layers.

### Scientific mosaic

Export the original linear measurements after permitted, validated corrections with their configured scientific WCS and coverage. Preserve physical units when supplied and document any explicitly declared compatible relative scale. Carry the history and uncertainty/coverage conventions needed to interpret the result. Restrict display-oriented transformations, soft seam modes and heuristic exposure methods to photo products until a particular scientific variant passes the photometric gates. Calibrated spectral channels retain their values and meaning. [Current scientific export settings](phase-3c.md#desktop-workflow)

## Integration and compatibility

1. **Inspect inputs.** Resolve the output intent, band, profile, sample type and units, calibration history, source masks, camera and lens metadata, and WCS provenance. Validate method combinations and identify affected panels.
2. **Establish geometry.** Choose the original or virtual rectified source frame. Validate or fit the matching WCS and resolve the target grid. Map output coordinates to original pixels once per contributing channel and retain the validity mask.
3. **Prepare source samples.** Decode the input transfer. Apply any qualified camera-response or illumination correction in its specified linear source domain. Apply channel-dependent source corrections in their calibrated channel basis. For ICC lookup-table profiles whose color and tone stages are coupled, first qualify the exact combination of transform and sensor corrections.
4. **Fit and apply photometry.** Derive overlap samples in the shared geometry, with a common linear working representation or scientific unit. Use a selected metadata prior and measurable support. Cache compact fitted models and reuse them when preview and export inputs agree. Evaluate source-space background terms in source coordinates.
5. **Sample and publish.** Use the composed coordinate mapping and bounded original-source windows. Blend using coverage and accepted corrections. Apply final display tone and color encoding for photo output, write metadata and masks, and publish atomically after validation.

The fit identity includes source fingerprints, effective masks, WCS and optical mapping, selected band, profile and calibration references, method parameters and the implementation version. Record the source coordinate frame of every flat and lens model. Resolve external profiles from local references and include their identities in diagnostics. Color and display edits invalidate the affected image or fit cache. A geometry edit invalidates solutions tied to a changed pixel frame and dependent placement where applicable. Preserve source pixels and raw-coordinate masks across every rebuild. [Storage and render worker decision](adr/0012-project-manifest-and-render-worker.md) · [Source-coordinate masks](adr/0014-source-coordinate-mask-grid.md)

Store stable method identifiers and version their settings independently of the application. Earlier manifests resolve to their earlier processing choices and saved geometry. A disabled or unavailable method is reported with its reason, enabling data or a compatible choice. Use the same validation and fitted results for the desktop, session commands and standalone CLI. Provide explicit paths, progress and cancellation for automatic jobs. Keep profile reads, background samples, fitting, source tile buffers and any temporary files within job budgets. Validate optional native libraries and calibration catalogs independently for packaging and licensing. [Local automation](adr/0016-local-automation.md) · [Lensfun library and database license terms](https://lensfun.github.io/manual/v0.3.95/license.html) · [Distribution tracking](../questions_open_topics.md#q-005---application-licensing-and-distribution-model)

### Method compatibility

| Input or combination | Required behavior |
| --- | --- |
| Same color profile with inconsistent prior stretch | A photo job can report suspicious tone spread and overlap residuals. Use distribution statistics as a diagnostic and retain the scientific scale checks. |
| Different declared RGB profiles in one photo job | Convert every panel into the selected common working space with a supported transform. Identify the panel whose profile or transfer is unresolved. |
| Scientific input with unknown scale or incompatible filter | Identify the missing calibration or band evidence. The common-scale declaration applies to demonstrably compatible linear inputs. |
| Existing SIP and an additional lens profile | Use one WCS that describes the selected source coordinate frame. A profile used for vignetting alone leaves the valid raw-pixel WCS usable. |
| Flat, lens-profile illumination and joint vignetting fit | Choose the source of the illumination correction. When the joint solve fits it, store its radial term as that panel's effective vignetting method. |
| Metadata normalization with Standard or Advanced | Use it as a recorded seed or prior when selected. The fit estimates the remaining change on the effective sample scale. |
| Insufficient overlap, field coverage or signal | The automatic policy can select an eligible simpler result and explain the fallback. A requested fit with explicit prerequisites reports the missing support. |

## Phase 8 closure

Phase 8 closed on the locally verified Windows beta 15 scope on 2026-11-26. The delivery table below preserves the original criteria for future work.

| Stage | Outcome at closure |
| --- | --- |
| 8A through 8C | Contract frozen. Tagged 16-bit photo TIFF export, adaptive preview and crop, tone and transparency choices, matrix-profile conversion, exposure controls and Standard brightness matching verified locally. |
| 8D | The Standard gain safeguard checks independent stars before applying a material gain. Advanced matching and optical corrections still require independent RGB, visible flat and lens evidence and subsequent production integration. |
| 8E | Additional optical fits, joint exposure and illumination fitting and seam methods deferred. |
| 8F | Local package checks recorded. Separate Windows acceptance and native redistribution review remain publication gates. Bracket-response and HDR research deferred. |

[Standard verification](phase-8d.md#standard-local-windows-results) | [Deferred methods and revisit conditions](../questions_open_topics.md#q-029---configurable-color-photometry-and-optics) | [Wide-field astrometry](../questions_open_topics.md#q-016---plate-solve-quality-incorrect-scale-recovery-and-distortion) | [Clean Windows checks](phase-3f.md#pending-clean-machine-check) | [Distribution review](../questions_open_topics.md#q-005---application-licensing-and-distribution-model)

## Delivery stages

| Stage | Deliverable and impact | Acceptance evidence |
| --- | --- | --- |
| 8A | Freeze photo and scientific intents, supported method settings, coordinate frames and test data. Define profile and calibration provenance, compatibility rules and diagnostics. | Document the outcome of each legal and rejected first-release method combination. Freeze representative fixture inputs, known corrections, reference outputs and numerical limits before tuning. |
| 8B | Add full-resolution photo TIFF output from the existing visual sky workflow. Reuse known sRGB conversion, current geometry, simple weighting, preview tone and the atomic writer. Add equivalent dialog-free operation. | Open the two original sRGB TIFFs, solve, preview and export a tagged 16-bit mosaic. Independently reopen RGB, bit depth, ICC, WCS and coverage. Check source hashes, preview/export samples at coincident positions, earlier science output parity and cancellation cleanup. |
| 8C | Add profile assignment and qualified ICC conversion. Deliver manual EV, exposure metadata, sky offset and Standard matching with overlap diagnostics. | Verify ICC reference patches and high-bit-depth gradients. Compare Off and Standard on held-out overlaps, with positive controls and weak or contaminated cases. Test absent profiles and exposure metadata and show each effective fallback. |
| 8D | Add Advanced global matching and the first qualified optical corrections. Retain the existing stellar mono control. Start optics with imported calibration geometry and a matched flat or verified lens vignetting profile. | Verify order stability and disconnected groups. Compare held-out stars, background residuals and diffuse signal. Check masks, corner WCS, no double geometry or illumination correction, flat normalization, and full-field sample and coverage parity. [Frozen 8D controls and local results](phase-8d.md) |
| 8E | Evaluate additional optical fits, joint exposure and illumination optimization, and photo seam methods as independent candidates. Compare manual and catalog model options. | Each method improves its target metric on independent control data, passes visual and scientific eligibility checks, and stays within its measured CPU and memory limits. Weak, ambiguous and extrapolated cases remain diagnosable. |
| 8F | Verify each shipped option on Windows. Evaluate bracket-response and HDR research when calibrated bracket data is ready. | Reopen old and new projects, exercise commands and native CPU/OpenGL display, independently verify exports, and test cancellation, cleanup and dependency loading from a clean Windows package. Qualify each bracket method against measured exposures before adding it to production choices. |

### Reference cases and measurements

- Use the original `20.TIF` and `21.TIF` for the first photo export. Use the existing PA4 sky case for wide coverage and multi-panel work, and retain linear FITS/TIFF/XISF and Paranal mixed-layer controls for science and composition parity. [Two-panel Windows evidence](phase-3c.md#windows-verification) · [PA4 and mixed-layer controls](phase-6.md#6d-reproduce-the-zea-warning-and-measure-preview-cost)
- Acquire a known lens calibration or measured wide-field stellar control, compatible flats across relevant apertures, and a bracket sequence from a stable scene before qualifying data-dependent methods. Include known previous correction, missing metadata, saturated samples, weak overlaps, unsupported radii and deliberate profile disagreements. Follow the real-data requirements whenever the work replays Phase 6 or Phase 7. [Real data and acceptance measures](phase-7.md#real-data-and-acceptance-measurements)
- Measure representative tile RGB errors against an independent transform, preview fidelity at shared sample positions, held-out registration median and P95, valid-area coverage, aperture flux and FWHM, seam/background residuals, and diffuse-region brightness. Start with the existing `0.5 px` geometry and `1%` aperture-flux targets for comparable well-sampled controls. Freeze method-specific limits in 8A. Record runtime, memory, input count and cache state. [Current numerical gates](../astro_mosaic_python_first_architecture_en.md#11-validation-and-acceptance-criteria)

The 8B photo output supplies a baseline for later corrections. The order of Advanced, optical and bracket features depends on which real calibration data is ready. [Open decisions and reference data](../questions_open_topics.md#q-029---configurable-color-photometry-and-optics)
