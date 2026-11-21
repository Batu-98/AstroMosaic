# Phase 8 Configurable Color Photometry and Optics

**Status** Scheduled on 2026-11-21. The 8A contract for the first full-resolution photo mosaic is frozen. Each subsequent delivery qualifies its corrections against prepared references. [Architecture and milestones](../astro_mosaic_python_first_architecture_en.md#106-phase-8-delivery-stages) · [ADR-0026](adr/0026-configurable-color-photometry-and-optics.md)

AstroMosaic 0.1.0b7 already frames selected sky panels from their WCS, decodes recognized sRGB TIFFs for Visual Preview and renders scientific mosaics from compatible linear inputs. Its optional scientific relative refinement currently uses mono panels. The new options extend those paths through the same bounded CPU renderer. [Current sky workflow](phase-3c.md#desktop-workflow) · [Existing relative refinement](phase-2.md#relative-refinement)

[8A contract](#8a-frozen-photo-export-contract) · [Settings](#workflow-and-settings) · [Input profiles and color](#input-profile-and-color-conversion) · [Exposure and brightness](#exposure-and-brightness-matching) · [Lens geometry](#lens-geometry) · [Vignetting](#vignetting-and-flat-field-correction) · [Delivery stages](#delivery-stages)

## 8A Frozen photo export contract

8B adds a distinct sky export intent. A completed, covered visual sky preview provides the selected band, resolved grid and linked display statistics for the desktop export. The headless command resolves the saved or automatically fitted grid and, for preview tone, samples the same final preview grid. It never needs a Qt session. Project manifests and scientific output keep their existing contracts. Visual input eligibility precedes the render, with diagnostics naming the affected panel.

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

The ICC conversion matrix and reference patches, known exposure or background corrections, measured lens calibration, compatible flats and stable exposure brackets still need fixtures before the related 8C–8F methods can be qualified. Track their data and backend choices in Q-029.

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

## Delivery stages

| Stage | Deliverable and impact | Acceptance evidence |
| --- | --- | --- |
| 8A | Freeze photo and scientific intents, supported method settings, coordinate frames and test data. Define profile and calibration provenance, compatibility rules and diagnostics. | Document the outcome of each legal and rejected method combination. Freeze representative fixture inputs, known corrections, reference outputs and numerical limits before tuning. |
| 8B | Add full-resolution photo TIFF output from the existing visual sky workflow. Reuse known sRGB conversion, current geometry, simple weighting, preview tone and the atomic writer. Add equivalent dialog-free operation. | Open the two original sRGB TIFFs, solve, preview and export a tagged 16-bit mosaic. Independently reopen RGB, bit depth, ICC, WCS and coverage. Check source hashes, preview/export samples at coincident positions, earlier science output parity and cancellation cleanup. |
| 8C | Add profile assignment and qualified ICC conversion. Deliver manual EV, exposure metadata, sky offset and Standard matching with overlap diagnostics. | Verify ICC reference patches and high-bit-depth gradients. Compare Off and Standard on held-out overlaps, with positive controls and weak or contaminated cases. Test absent profiles and exposure metadata and show each effective fallback. |
| 8D | Add Advanced global matching and the first qualified optical corrections. Retain the existing stellar mono control. Start optics with imported calibration geometry and a matched flat or verified lens vignetting profile. | Verify order stability and disconnected groups. Compare held-out stars, background residuals and diffuse signal. Check masks, corner WCS, no double geometry or illumination correction, flat normalization, and full-field sample and coverage parity. |
| 8E | Evaluate additional optical fits, joint exposure and illumination optimization, and photo seam methods as independent candidates. Compare manual and catalog model options. | Each method improves its target metric on independent control data, passes visual and scientific eligibility checks, and stays within its measured CPU and memory limits. Weak, ambiguous and extrapolated cases remain diagnosable. |
| 8F | Verify each shipped option on Windows. Evaluate bracket-response and HDR research when calibrated bracket data is ready. | Reopen old and new projects, exercise commands and native CPU/OpenGL display, independently verify exports, and test cancellation, cleanup and dependency loading from a clean Windows package. Qualify each bracket method against measured exposures before adding it to production choices. |

### Reference cases and measurements

- Use the original `20.TIF` and `21.TIF` for the first photo export. Use the existing PA4 sky case for wide coverage and multi-panel work, and retain linear FITS/TIFF/XISF and Paranal mixed-layer controls for science and composition parity. [Two-panel Windows evidence](phase-3c.md#windows-verification) · [PA4 and mixed-layer controls](phase-6.md#6d-reproduce-the-zea-warning-and-measure-preview-cost)
- Acquire a known lens calibration or measured wide-field stellar control, compatible flats across relevant apertures, and a bracket sequence from a stable scene before qualifying data-dependent methods. Include known previous correction, missing metadata, saturated samples, weak overlaps, unsupported radii and deliberate profile disagreements. Follow the real-data requirements whenever the work replays Phase 6 or Phase 7. [Real data and acceptance measures](phase-7.md#real-data-and-acceptance-measurements)
- Measure representative tile RGB errors against an independent transform, preview fidelity at shared sample positions, held-out registration median and P95, valid-area coverage, aperture flux and FWHM, seam/background residuals, and diffuse-region brightness. Start with the existing `0.5 px` geometry and `1%` aperture-flux targets for comparable well-sampled controls. Freeze method-specific limits in 8A. Record runtime, memory, input count and cache state. [Current numerical gates](../astro_mosaic_python_first_architecture_en.md#11-validation-and-acceptance-criteria)

The 8B photo output supplies a baseline for later corrections. The order of Advanced, optical and bracket features depends on which real calibration data is ready. [Open decisions and reference data](../questions_open_topics.md#q-029---configurable-color-photometry-and-optics)
