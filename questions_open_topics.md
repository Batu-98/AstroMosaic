# Questions and Open Topics

This register tracks unresolved decisions, problems, and risks. It is not a work log. Read it at the start of each development session and update it when evidence changes.

## Tracking Rules

- IDs are stable and increasing: `Q-001`, `Q-002`, and so on. Never reuse an ID.
- Status: `Open`, `Investigating`, `Blocked`, `Deferred`, or `Resolved`.
- Priority: `P0` = immediate correctness/data-loss blocker; `P1` = required before an identified gate; `P2` = planned improvement or later decision.
- Record the affected action or phase. Priority alone does not block all development.
- The agent resolves technical questions through investigation. Ask the owner only when a product preference or missing authority is actually needed.
- Keep resolved entries with a dated resolution and evidence. A deferred entry must name its revisit trigger.
- Use the fields below for new entries; omit no closure condition. Keep details concise and link larger evidence separately.

## Active Topics

### Q-003 - Reference datasets and frozen acceptance thresholds

- **Status / priority:** Investigating / P1
- **Opened / updated:** 2026-11-15 / 2026-11-21
- **Affected phase:** Phase 0 fixture design and the numerical gates in phases 1, 2, 3.5, 3.6, 4, 6 and 7.
- **Impact and evidence:** The [Phase 1 fixtures](docs/phase-1.md) verify independent FITS export truth. [Phase 2](docs/phase-2.md#acceptance-fixtures) fixes and verifies held-out alignment, stellar flux and profile, injected extended signal, masks, and weak or disconnected inputs. [Phase 3A fixtures](docs/phase-3a.md#acceptance-fixtures) fix sample, channel, coverage, and WCS tolerances for linear TIFF. [Phase 3C](docs/phase-3c.md#windows-verification) confirms preview and export agreement at coincident sample positions. [Phase 3.5A](docs/phase-35.md#frozen-supplementary-fixtures) reran the baseline and froze cases for narrow support, saturation, and explicit DSS crops. The [sidecar check](docs/phase-35.md#masked-wcs-sidecar-reuse) uses the existing bilinear and WCS bounds.
- **Current assumption:** Phases 6 and 7 use real observations with recorded provenance and independent measurements. The [3.6A manifest](tests/fixtures/plate_solve_v36.json) identifies the established catalog-quality and timing contracts.
- **Next action / responsibility:** Repeat the ALPACA translation, Oxford similarity, La Silla nightscape and real rejection controls on the fresh Windows candidate. The local 7F review and exports passed. A new camera-rotation reference should supply a controlled lens entrance-pupil pivot and independent near/far landmarks before reopening model admission. [Reference cases](docs/phase-7.md#frozen-7a-references) · [7F results](docs/phase-7.md#7f-local-windows-results)
- **Closure condition:** Record dataset-specific tolerances and reference results before algorithm tuning. Include the applicable Phase 4 large-mosaic, RGB photometry and mixed-scene measurements. Link the Phase 6 and 7 reference inventories and independent measurements of the real cases.

### Q-005 - Application licensing and distribution model

- **Status / priority:** Investigating / P1
- **Opened / updated:** 2026-11-15 / 2026-11-22
- **Affected phase:** Public source publication and Windows binary distribution.
- **Impact and evidence:** AstroMosaic source uses `GPL-3.0-only`. The portable builder collects wheel notices, the CPython runtime license, upstream supplements for selected dependencies and the native file inventory. The local 6E candidate recorded 223 desktop and 178 CLI native files and the exact source and binary archive hashes. [License decision](docs/adr/0009-gpl-v3-application-license.md) · [Windows release preparation](docs/windows-release.md) · [6E candidate evidence](docs/phase-6.md#local-windows-lifecycle-and-package-results)
- **Current assumption:** Publish the source on GitHub. Keep portable ZIP builds local until the remaining binary distribution review passes. Obtain external ASTAP binaries, solver catalogs and archive FITS references from upstream.
- **Next action / responsibility:** Match the binary inventory, including Little CMS 2.20.0 in the locked imagecodecs wheel, to the exact corresponding sources. Confirm Microsoft runtime redistribution terms before publishing Windows downloads. Before adopting the optional 7C wheel for distribution, review the pinned OpenCV and FFmpeg native contents, corresponding sources and notices, and verify that exact package on clean Windows. [7C wheel inventory](docs/phase-7.md#7c-real-observation-results) · [8C Windows probe](docs/phase-8.md#color-patches-and-profile-assignment)
- **Closure condition:** Record the applicable notices, matching source and redistribution terms for publicly distributed artifacts. Keep separately obtained data subject to its upstream terms.

### Q-008 - Linux and macOS support

- **Status / priority:** Deferred / P2
- **Opened / updated:** 2026-11-15 / 2026-11-15
- **Affected phase:** Future platform expansion.
- **Impact and evidence:** Candidate wheels matched the historical Ubuntu x86-64 and macOS arm64 targets. Native operation and packaging are unverified.
- **Current assumption:** Preserve portable engine code and isolate platform-specific behavior in adapters.
- **Next action / responsibility:** Revisit when the owner requests another platform and native test resources are available.
- **Closure condition:** Select the added OS and CPU targets and verify native installation, jobs, viewport, solver, and packaging on each added target.

### Q-009 - Dual FITS and TIFF workflows and camera RAW import

- **Status / priority:** Open / P1
- **Opened / updated:** 2026-11-15 / 2026-11-23
- **Affected phase:** Dual FITS and TIFF workflows throughout phases 1-4, Phase 5C band-local channels, and optional camera RAW import after a future scope decision.
- **Impact and evidence:** The [Phase 3A Windows fixtures](docs/phase-3a.md#windows-evidence) verified mono and RGB TIFF import and export, including samples, channel order, WCS, and coverage. The [Phase 3B desktop workflow](docs/phase-3b.md#verification) reopens a mixed FITS/TIFF project and renders it to TIFF. [Phase 4B](docs/phase-4b.md#windows-baseline-results) independently verified all samples and coverage in full-size mono FITS, RGB TIFF and mixed exports. [Phase 5C](docs/phase-5c.md#local-windows-results) verified band-local units and channel order with mixed mono and RGB membership. Camera RAW is deferred as an import-only feature.
- **Local preparation evidence** The public Nikon captures reproduce as seven linear RGB UInt16 TIFFs using isolated RawPy tooling. Four Nocturne RGB FITS cubes use Float32 TIFF derivatives under the current monochrome FITS input contract. Every covered sample and binary coverage code matched. [Public preparation and checks](docs/public-test-data.md#local-verification)
- **MOANA reference:** Four signed Float32 RGB TIFFs reopened with matching binary masks and sampled values. The offline diagnostic reads the calibrated scale directly. Production photo profile resolution requires UInt16 RGB TIFF. The source and preparation data are in `output/phase8d-public-validation-20261123/moana/`.
- **M33 follow-up:** Five new signed Float32 RGB TIFFs reopened with the original-size binary masks and verified sampled values. The legacy FITS omit row order. A detector hot-pixel comparison confirmed identity orientation between the lights and the supplied master dark. [M33 preparation and results](docs/phase-8d.md#moana-standard-replay-and-independent-m33-observations)
- **Current assumption:** Provide first-class support for both scientific FITS panels and linear TIFF panels across the pipeline. If camera RAW is requested later, use an open-source linear decoder and preserve relevant sensor and color metadata.
- **Next action / responsibility:** Repeat the [packaged Windows exports](docs/phase-3f.md#windows-evidence) on a clean Windows installation. Define and verify channel-specific calibration before enabling RGB photometric refinement. Revisit camera models and decoder compatibility when camera RAW import is requested.
- **Closure condition:** Validate FITS and TIFF sample integrity, metadata, memory, and reproducible import-to-mosaic workflows on Windows. If camera RAW is activated, establish separate acceptance criteria for the selected models.

### Q-010 - Foreground recognition, masks, and composition

- **Status / priority:** Investigating / P1
- **Opened / updated:** 2026-11-15 / 2026-11-21
- **Affected phase:** Phase 2 masked sky processing, Phase 3D mask editing, Phase 3E foreground alignment and composition, Phase 3F packaged acceptance, Phase 4 resource validation, Phase 6B real-scene validation, and Phase 7 panorama registration.
- **Impact and evidence:** [Phase 3D](docs/phase-3d.md#windows-verification) verifies local suggestions, manual overrides and masks, and exclusion of foreground from sky fitting. [Phase 3E](docs/phase-3e.md#windows-verification) verifies WCS-free alignment and exports, shared-reference placement, saved edits, and seams with partial and zero common coverage. [Phase 4A](docs/phase-4a.md#local-windows-results) reproduced all three desktop layers from a saved mixed project in the portable CLI. Small, rotated, and ambiguous terrain still needs manual review.
- **Current assumption:** The saved three-label mask selects the foreground support. Legacy correlation assumes the same raster size and scale. Version 7 control-point fits support anchored translation and similarity. Composition uses similarity placement and blends within valid common coverage.
- **Next action / responsibility:** Repeat the desktop review and exports on a fresh Windows installation. The local 7F PA4 replay retains six singleton groups. The reviewed overlaps have missing or insufficient saved ground support. The PA4 metadata and PASSTA rotation trials also exceed the frozen residual tolerance. Revisit calibration, viewpoint shift and omitted ground support before admitting these models or links. [7F results](docs/phase-7.md#7f-local-windows-results) · [PA4 pair review](docs/phase-7.md#initial-7a-measurements) · [7D results](docs/phase-7.md#7d-real-observation-results)
- **Closure condition:** Verify separate layer exports, saved edits and measured resource limits. Pass the Phase 6B diagnostics and the Phase 7 positive, held-out, negative and legacy checks on real captures. Account for the PA4 pair outcomes and document unsupported geometry.

### Q-011 - Optional generative fill for a visual seam

- **Status / priority:** Deferred / P2
- **Opened / updated:** 2026-11-15 / 2026-11-15
- **Affected phase:** Optional follow-on to the Phase 3 composition workflow.
- **Impact and evidence:** Uncovered regions may remain after aligning and cropping the sky and foreground layers. The baseline composite exposes the gaps.
- **Current assumption:** Evaluate fill as an opt-in local visual operation restricted to uncovered seam gaps. Keep its synthetic pixels and provenance separately identifiable.
- **Next action / responsibility:** Revisit after the crop and overlap controls are tested and the owner wants fill for remaining gaps. Evaluate open-source software, model weights, licenses, and local resource use then.
- **Closure condition:** If selected, verify that fill is confined to the selected gaps and its synthetic mask and provenance survive export. Scientific layer exports retain observed samples.

### Q-016 - Plate solve quality, incorrect-scale recovery and distortion

- **Status / priority:** Investigating / P1
- **Opened / updated:** 2026-11-17 / 2026-11-23
- **Affected phase:** Phase 3.6A quality/fixture freeze, 3.6D bad-scale recovery, 3.6E SIP/edge validation, 3.6F acceptance, 6C masked solve recovery, and 8D wide-field geometry.
- **Impact and evidence:** The [Mosaic Master comparison](docs/plate-solve-comparison.md) verified that the Seiza wrapper retains a supplied scale within 0.8–1.2 on blind retry and does not request SIP (`sip_order=0` in installed Seiza 0.48.2). The earlier ASTAP wrapper retained the supplied vertical FOV on blind retry. Geometry checks alone leave catalog accuracy at the edges unmeasured. Q-015 records the measured 40′ M42 blind limit.
- **Current assumption:** The source uses the common 15-match and RMS gate, Gaia's confidence check, unrestricted Gaia 0.1–120 arcsec/pixel recovery and a spatial holdout for application SIP promotion. The rerun of the original D05 and Gaia cases met their archive envelopes. ASTAP-only local FOV recovery retains pointing when both hints were supplied. [Measurements](docs/phase-36-results.md)
- **Phase 8D Nightscape evidence:** Direction estimates from masked sky windows recovered Gaia candidates on all three 35 mm and four 20 mm TIFFs. All seven failed the full-field held-out gate (2.58–6.87 px overall and 2.62–8.39 px at the edge). One 35 mm crop passed. Nine provisional same-series pair scores ranged from 2.91 to 4.73 nominal native px at P95. The per-panel reports are in `output/phase8d-public-validation-20261123/nightscape/`.
- **35 mm follow-up:** Regional Gaia matches and regularized SIP yielded three accepted masked-sky WCS solutions. Primary final P95 was 0.490–0.591 px overall and 0.489–0.537 px at the edge. All three fits also passed the larger disjoint Gaia audit. The primary overlap P95 was 0.482–0.611 native px. All three extra-sample overlaps missed 0.5 px at 0.888–1.046 px. The Lensfun rectification trial exceeded the per-frame catalog limits. [35 mm Nightscape results](docs/phase-8d.md#35-mm-nightscape-field-wide-gaia-refit)
- **35 mm overlap audit:** Preserve the WCS and the disjoint Gaia sample. The more elongated stratum had 0.976–1.056 px P95 versus 0.592–0.820 px in the next axis-ratio stratum. The outer radius gave 1.045–1.349 px versus 0.692–0.876 px at intermediate radii. Raw green flux had weak negative rank association with error. Gaia magnitude and FWHM did not explain the tails consistently. [35 mm held-out residuals](docs/phase-8d.md#35-mm-overlap-tails-on-independent-gaia-stars)
- **20 mm follow-up:** Regional Gaia fits accepted all four frames on two disjoint samples. Extra-sample whole-mask P95 was 0.676–0.962 px and edge P95 was 0.677–1.395 px. All six primary native overlaps missed 0.5 px at 0.606–0.896 px. The larger disjoint overlap sample reached 0.742–0.966 px. [20 mm results](docs/phase-8d.md#20-mm-nightscape-regional-gaia-validation)
- **Centroid validation:** The elliptical moment blend improved mean 35 mm selection pair P95 by 0.01987 px. With the same WCS and Gaia identities the larger independent sample worsened by 0.05054 px on average. Its refits exceeded 1.0 px overall on 35 mm frames 1 and 3 and 20 mm frames 008 and 009. All refit edge P95 values met 1.5 px. Only the SEP control on primary 35 mm pair 2–3 passed 0.5 native px. The larger sample gave 0.930 px on the published WCS for that pair. The held-out result excludes the alternative. [Centroid study](docs/phase-8d.md#nightscape-validation-of-elongated-star-centers)
- **Next action / responsibility:** Obtain independent faint and elongated star support to distinguish centroid repeatability from geometric residuals. Evaluate a measured calibration on a matched Nikon body and lens if available. Keep independent edge and two-direction overlap checks for both focal lengths. The 6C D50 replay moved all three resource-limited candidates to association at 17.69–23.92 MiB. The shifted-control, held-out and edge-support failures still exclude those frames. Reuse those diagnostics when stronger PA4 sky support is available. Review the D80 Orion candidate's 1.02 px held-out whole-field P95 and the D20 M13 archive comparison of 0.452″ against the 0.451″ reference envelope. Assess Automatic recovery and additional real sparse fields within the existing budgets. [Phase 6C measurements](docs/phase-6.md#local-masked-solve-results) · [Dense catalog results](docs/phase-36-results.md#dense-astap-catalog-verification)
- **Closure condition:** The implemented match/RMS boundaries, bad-hint recovery, supported SIP/edge cases, legacy reuse and Windows source/portable regressions meet the frozen 3.6 gates with independently recorded errors. Planning alone does not resolve this topic.

### Q-020 - Additional XISF variants

- **Status / priority:** Deferred / P2
- **Opened / updated:** 2026-11-18 / 2026-11-18
- **Affected phase:** Phase 5A interchange and future XISF expansion.
- **Impact and evidence:** XISF permits block compression, non-attached storage, checksums and private astrometric metadata. The [Phase 5A checks](docs/phase-5a.md#local-windows-results) independently reopened raw attachments with FITS-compatible metadata. A compressed attachment produced a conversion diagnostic.
- **Current assumption:** Use a compatible XISF attachment or a supported FITS/TIFF file for interchange. Solve or attach a sidecar when the XISF panel needs celestial WCS.
- **Next action / responsibility:** Revisit when a representative workflow requires broader support. Check codec block sizes and bounded decode or staging, checksum cost, and native WCS agreement before extending the adapter.
- **Closure condition:** Reopen representative files from named external writers and verify data integrity, WCS, channel order, resources and packaging for each variant added.

### Q-029 - Configurable color photometry and optics

- **Status / priority** Deferred / P2
- **Opened / updated** 2026-11-21 / 2026-11-26
- **Affected phase** Phase 8 photo export and configurable corrections.
- **Impact and evidence** The owner opened `GHGH.tiff` from the original `20.TIF` and `21.TIF` pair in Photoshop at 100% layer opacity with the RGB channels. The screenshot shows black outside the panel footprints, a lifted sky background and visible overlap boundaries. On the same WCS grid and coverage, sampled median code values were 33,410 DN with `Use Preview Tone` and 7,878 DN with `Preserve Tone`. [Initial investigation](docs/phase-8-photo-mosaic-findings-and-recommendations.md) · [8B package evidence](docs/phase-8.md#8b-local-windows-package-results)
- **Current assumption** The linear-light SIP-3 refit reduced the reserved Gaia P95 on all four panels. The independent overlap P95 was 0.700 px for `20.TIF`–`21.TIF` and 1.200 px for PA4 `10.TIF`–`11.TIF`, above the 0.5 px target. The controlled 8C fits recovered the known exposure changes. The unchanged owner pair selected brightness Off after overlap validation. [Gaia holdout](docs/phase-8.md#8b-gaia-holdout-for-wcs-candidates) · [8C source results](docs/phase-8.md#8c-local-source-results)
- **8D evidence** The chain selected Standard and the cycle selected a global plane on the frozen crop. Both preserved the disconnected group and reproduced the same result after reordering. PA4 frames 19–22 retained Off after both global models exceeded coefficient bounds. The inspected DNGs yielded level mapping opcodes. Visible-band flat qualification and a measured lens calibration remain open. [8D reference and intake](docs/phase-8d.md)
- **Independent candidate** The public Nocturne M31 test yielded a three-frame raw Bayer network with two links below 0.5 px. Color interpolation moved the native-size RGB measurements above the target, and the frozen fit retained Off with weak rank. The separate PA4 full sky screen found no qualified network. [Independent M31 measurements](docs/phase-8d.md#independent-m31-candidate)
- **Stacked control** Three M31 pointing stacks passed the geometry gate on all three edges. Standard's 4.95% reduction on the selection regions fell short of the frozen gate, and both global fits lacked support. The stack-to-anchor aperture comparison recorded median differences of 1.28%–5.71% in magnitude. [M31 pointing-stack results](docs/phase-8d.md#separate-m31-pointing-stacks)
- **Calibrated control** SDSS M2 passed all three geometry checks. A 5.36% Advanced improvement in the final RGB residual came with median stellar flux ratios up to 38.30% below peer apertures. Fixed-gain backgrounds preserved the ratios but selected Off. The source CLI Standard workflow assigned gain 0.636 to one calibrated panel. [Independent calibrated SDSS panels](docs/phase-8d.md#independent-calibrated-sdss-panels)
- **Stellar gain control** The offline guard rejected the SDSS M2 Standard and Advanced gain candidates and accepted the injected gains on the wider owner crop. M31 retained Off. A positive Advanced result on an independently exposed network is still needed. [Independent stellar gain qualification](docs/phase-8d.md#independent-stellar-gain-qualification)
- **Production Standard** Beta 15 rejected M2's 0.636 gain on 147 independent stars and applied only offsets. The same source, desktop and console workflow retained the known 1.25 gain on the mixed-ICC control. The masked crop also passed the console check. [8D Standard results](docs/phase-8d.md#standard-local-windows-results)
- **Restored sky control** The SDSS M2 and M77 archives supplied the actual sky models removed from each scan. M2's unity-gain global plane improved final mean RGB P95 by only 0.036% over Standard. It preserved sampled coverage and kept the worst per-panel aperture-error P95 at 0.741%. The relative sky color leaves a measurable residual under any linked scalar correction at unity gain. [Restored sky results](docs/phase-8d.md#restored-sdss-sky-backgrounds)
- **Origin controls** M51 and M37 provide 14 catalog-validated exposures and a measured M37 detector flat. Both triplets missed the native overlap and Advanced improvement gates. M37 verified flat normalization, detector samples, binary coverage and WCS. Its archived flat pedestal is unresolved and only two to three final stars per edge moved across at least 1% flat response. Aperture repeatability was mixed. [Origin controls](docs/phase-8d.md#origin-broadband-exposures-and-detector-flat)
- **NIRCam flat reference** Three additive-calibrated dithered exposures replayed 12,327,893 detector samples, their binary masks and both propagated variance planes exactly against independent archive products. All three overlap P95 values were below 0.5 px. Aperture repeatability was mixed despite 340–680 px detector shifts. The edge with eight final stars crossing at least a 1% response change reduced that subset's P95 from 7.70% to 5.54%, while the final median error was −2.50%. [NIRCam flat results](docs/phase-8d.md#nircam-dithered-detector-flat-reference)
- **Wide NIRCam dithers** Six NRCB4 F200W exposures replayed 24,940,290 valid detector samples and matched all six masks and both variance planes. Ten overlaps passed geometry. Four supported a high-signal exposure comparison. One flat application reduced all four full-sample P95 values to 0.82%–2.58%, with three to seven final apertures per overlap. Only two scored pairs had a final star crossing at least 2% response difference. [Wide NIRCam dither results](docs/phase-8d.md#nircam-f200w-large-dither-flat-reference)
- **Calibrated M8–M20 sequence** Three independent five-exposure stacks reached 0.079–0.110 px native overlap P95. The unity-gain plane's final P95 was 0.19% higher than Standard. Selection-block color floors and spatial spans were comparable. [M8–M20 comparison](docs/phase-8d.md#calibrated-m8m20-exposure-sequence)
- **Expanded SDSS M2 screen** The best of 216 RGB sky-only cycles improved the global offset by 4.15%, below the 15% plane margin. A separate r-band run passed the sky-only check on 217 cycles. Its strongest cycle yielded only 1.27% final improvement relative to Standard after restoring the celestial signal. [Expanded SDSS screen](docs/phase-8d.md#expanded-sdss-m2-sky-screen)
- **Linked offset bound and M51 intake** The pooled RGB lower bound ruled out the frozen unity-gain plane margin on 125 of the 216 M2 sky-only cycles. The Bath M51 intake validated 13 of 24 red and green exposures. The three accepted red exposures missed the 0.5 px native overlap gate at 1.036–1.243 px P95. [Linked offset results](docs/phase-8d.md#linked-additive-correction-limits) · [M51 geometry intake](docs/phase-8d.md#bath-m51-geometry-intake)
- **Public library** The library adds 202 separate M8 exposures from the MOANA mosaic and the accompanying master darks and flats. Seven prepared wide-angle TIFFs from two nightscape sequences passed input reads. The first unmasked strict Gaia check yielded one rejected candidate and six timeouts. Documented, independently processed panels qualify for brightness testing when the processing preserves the measured sky variation and relative linear scale. [Public library](docs/public-test-data.md) · [Reference preparation](docs/phase-8d.md#reference-input-preparation)
- **MOANA four-night reference** Four disjoint 120 s RGB stacks passed all six native geometry checks (0.193–0.408 px P95). Standard passed the stellar guard and reduced final mean RGB P95 by 10.06% versus Off. The global plane improved by 0.085% over Standard in final blocks and fell short in selection. Sampled coverage was identical for all models. The measured diffuse comparison is relative to peer exposures. The source flat pedestal and absolute flux and diffuse references remain unverified. See `output/phase8d-public-validation-20261123/moana/comparison/photometry.json`.
- **Independent M33 follow-up** Three same-pointing nights reached 0.196–0.237 native px on 103–116 high-signal final stars per edge. The unscreened samples exceeded 0.5 px. The selection-block linked offset bound admitted unity-gain candidates. The free-gain offset lowered final RGB P95 by 13.74% relative to Standard, but its 0.695–0.697 gains shifted the two final reference-edge stellar medians to −23.13% and −27.05%. The unity-gain plane improved final P95 by 0.0043% versus Standard. The guarded choice was Off. The sparse cross-pointing chain also retained Off. Both comparisons retained their binary coverage and measured relative diffuse and aperture results on final blocks. [M33 brightness and reserved audits](docs/phase-8d.md#m33-brightness-and-reserved-block-audits)
- **Independent Pleiades follow-up** Three disjoint time stacks passed reserved native geometry at 0.135–0.149 px. The unscreened stellar P95 also passed. The linked spatial span was 0.98–1.48 times the RGB color floor across five candidate groups. The fixed-gain pre-screen admitted both fits. The free-gain rank ratios were below 0.00945 against 0.015. The unity-gain plane improved selection by 0.56% versus Off, below 15%, with unchanged final coverage. The final aperture and diffuse audits reproduced. The guarded choice was Off. [Pleiades measurements](docs/phase-8d.md#independent-pleiades-spatial-background-screen)
- **Stripe 82 gradient intake** Fourteen separately archived sky models around NGC 1087 supplied 91 pairs. The greatest selection spatial-span to RGB color-floor ratio was 0.260 against a priority of 2. The replay supplied no sufficiently coherent sky-only candidate for the scene test. [Stripe 82 intake](docs/phase-8d.md#stripe-82-gradient-intake)
- **Independent Lagoon 300 s follow-up** Four stacks use 35 new admitted lights. The chosen triplet passes native geometry at 0.137–0.250 px. One edge has a linked span 2.282 times the RGB color floor. All Advanced designs pass the rank check. Standard reduces final RGB P95 by 13.80% versus Off with stellar support, and all Advanced variants score higher than Standard. The final coverage is identical across variants. The new reports and earlier Lagoon 120 s control reproduce. [Long-exposure Lagoon results](docs/phase-8d.md#separate-300-s-lagoon-observations)
- **Visible flat checks** MOANA confirmed detector orientation and matched the RGB filter labels. Its flat bias history is unresolved and the recorded electrons per DN differ from the 120 s lights. The documented HST F606W flat comparison retained every native and sampled coverage mask. Two pairs met geometry and support at 0.072 and 0.106 px. Once-applied aperture P95 was 2.784% and 4.484%. One supported test star crossed at least 2% response and fell to 0.559% error with one application. [Visible-band flat-field results](docs/phase-8d.md#visible-band-flat-field-validation)
- **F438W RAW follow-up** The 47 Tuc wide-dither triplet supplies 44 and 15 distinct reserved stars crossing 2% and 3% measured response. Its CALWF3 bias- and dark-corrected RAW replay matches all 50,225,160 valid Once samples within the archive tolerance. All three pairs pass native geometry at 0.054–0.086 px P95 and all masks agree. Once reaches 3.887%–7.062% aperture P95 on complete reserved samples against the 1% target. On the strongest link, the five S/N ≥ 300 reserved stars crossing 3% improve from 1.293% Off to 0.666% Once and 1.263% Twice. Diffuse peer P95 improves versus Off on two pairs, with a persistent sky offset of about 0.015 e⁻/s on the third exposure. [F438W RAW and held-out results](docs/phase-8d.md#f438w-wide-dithers-from-raw)
- **F438W CTE follow-up** The three CALWF3 FLCs match the RAW-derived Once output on all 50,187,153 valid pixels within tolerance. Native geometry stays below 0.110 px P95 with the corrected centroids. With all 122 test memberships on shared valid support, pooled Once P95 moves from 6.664% to 6.619%. The three CTE pair scores are 3.956%, 6.580% and 12.062%, all above 1%. The CTE changes are larger for fainter stars. Residual errors have weak rank relationships with detector transfer distance. A shared core mask increases one error, and the clear-core sample still misses the target. The replay matches the coverage, diffuse and detector results. [F438W pixel CTE results](docs/phase-8d.md#f438w-pixel-cte-follow-up)
- **Independent F606W flat replay** The 11444 LMC series and same-configuration 47 Tuc repeat match all 100,351,695 valid FLC samples with one flat application. All six LMC overlaps meet native geometry at 0.052–0.093 px P95. All miss the complete held-out 1% flux target with Once P95 of 1.464%–7.792%. Four also miss the 15-star support floor. The largest dither has 21 and seven common stars crossing 2% and 3% response, with two and zero in the test blocks. The 40.61 px repeat gives 1.871% Once P95 and 0.699% robust scatter with a 0.166% median response change. Native and sampled coverage agree across modes. The F438W CTE regression reproduced all results and masks. [Independent LMC and repeat results](docs/phase-8d.md#independent-lmc-f606w-flat-replay)
- **Independent F606W repeatability** The original 47 Tuc 14-star test reproduces three errors above 1% and Once P95 of 1.871%. Three separate 348 s GO-12379 FLCs in the same hardware configuration supply 95–102 frozen test stars per pair in 42–43 blocks. Both geometry directions reach 0.019–0.035 px P95. The selected 10 px annulus median reaches 3.952%–5.107% full-sample flux P95, with 22–30 stars above 1% per link. A robust sky plane loses on the selection sample and also misses the test gate. The S/N ≥ 300 diagnostic still exceeds 1%. The earlier F606W and F438W numerical references reproduce. [Independent repeat and per-star evidence](docs/phase-8d.md#independent-f606w-repeatability-control)
- **F606W aperture-profile repeat** On the shared 3, 5, 7 and 10 px support, the original 47 Tuc pair and the opened GO-12379 triangle supply 19 distinct stars with a significant 5/10 profile change by the diagnostic rule. A separate three-exposure Visit 07 holdout excludes previously opened test stars and passes both native geometry directions at 0.017–0.026 px on 78–92 stars per link. Selection retained the 10 px aperture after the spatial 5-to-10 px correction raised P95 on one selection link. The complete 10 px test reaches 2.350%–4.337% P95, against a 1% target. Changes in the neighbor-axis wing asymmetry have the strongest association with the 10 px errors (Spearman ρ 0.539, 95% sky-block interval 0.408–0.644). A repeated localized contribution on `obq` leaves blending, profile change and detector artifacts to distinguish. The new and earlier numerical references replay. [Profile and independent holdout results](docs/phase-8d.md#f606w-aperture-profile-repeatability)
- **F606W native residual follow-up** The opened `obq` impulse is confined to that exposure at the observed amplitude. Three separate no-injection F606W exposures place its sky counterpart on UVIS1 and permit a separate probe of the original UVIS2 pixel. Neither location repeats the excess. All three independent links pass both native geometry directions at 0.049–0.063 px P95 and miss the 1% flux gate at 4.680%–6.049% on 30–34 stars per link. No fresh star meets the frozen compact-wing rule. One fresh star shows distributed wing residuals as well as an exposure-local peak in a post-score check. The origin of the remaining wing signal is unresolved. [Native results and replay](docs/phase-8d.md#native-residual-follow-up)
- **Independent local F606W PSF test** Three unscored 30 s no-injection exposures supply 117 frozen test memberships. The train-only local PSF predicts the 3–5 px direction and magnitude on `hrq–c0q` and `hrq–hgq`. The improvements outside the native 3 × 3 peaks are uncertain. Every 5–10 px link has higher magnitude error than the zero-change reference, with two to six well-signed changes per link. No overlap supports both rings. Both geometry directions pass on every link, with unchanged 10 px photometry at 1.752%–2.403% P95. [PSF measurements and replay](docs/phase-8d.md#independent-local-f606w-psf-test)
- **Independent within-pixel F606W PSF** Four 348 s Visit 07 exposures supply 357 fresh test memberships. The explicit x/y slopes raise outer-ring MAE against both the previous local PSF and zero on all six pairs. All paired intervals favor the comparisons and only 4–8 stars per pair have well-signed outer changes. All six links pass geometry and miss the 1% full-sample aperture limit at 2.455%–6.828% P95. [Within-pixel PSF results](docs/phase-8d.md#independent-f606w-within-pixel-psf-test)
- **F606W two-axis half-pixel screen** GO-11680 Visit 02 confirms the commanded half-pixel phase on both axes in a fresh 610 s pair. The six matches have median fractions of 0.570 px in x and 0.543 px in y. One of two test stars survives common pixels and zero survive same-chip donor support. PSF and 10 px photometry remain unevaluated. [Archive screen and reproducible evidence](output/phase8d-f606w-half-pixel-20261124/README.md)
- **Richer-field F606W follow-up** The registered extension measures 109 fresh links. None of the 34 nominal half-pixel links realizes the two-axis majority. M5 has 206 matched stars and seven jointly in range. Relative field rotation is about 0.90°. A common archived IDC WCS recovers eight matches for the Omega Centauri pair and two are jointly in range. [Richer-field result and replay](docs/phase-8d.md#richer-field-f606w-follow-up)
- **Compact same-visit F606W screen** Eighteen new configuration-matched links have documented compact diagonals. Two GO-16361 pairs realize both centroid phase limits with verified guiding. Each has a single fresh UVIS1 match, zero qualified test stars and inadequate donor support. The held-out PSF and 10 px tests remain open. [Compact dither archive screen](docs/phase-8d.md#compact-same-visit-f606w-dither-screen)
- **Same-orbit F606W stellar field preflight** The targeted intake checks 348 roots across 99 visits. Seven fresh configuration-matched links lack a two-axis half-pixel command. The nominal NGC 1835 diagonal is on shutter B. Its same-acquisition shutter-A pair yields zero reciprocal matches and no test sample. [Stellar field preflight](docs/phase-8d.md#same-orbit-f606w-stellar-field-preflight)
- **M5 F606W acquisition** Public MAST supplies 12 FLCs in the targeted field and no long shutter-A pair within one acquisition. GO-12517 Visit 13 confirms the realized two-axis shift for pointing only, with 138/270 matches from a B/A pair. A dedicated four-exposure worksheet is ready for an allocated visit and APT validation. [M5 acquisition and worksheet](docs/phase-8d.md#m5-f606w-acquisition-check)
- **M5 APT feasibility** The four-exposure local visit fits one orbit in APT 2026.5.1 with one modeled acquisition and zero overruns. Visit Planner gives three potential visibility windows. Actual guide-star selection and observing allocation remain pending. [APT feasibility](docs/phase-8d.md#m5-apt-feasibility-check)
- **Bat and Wing selection screen** Five fresh 60 s stacks from 45 disjoint MOANA lights pass all ten selection geometry checks at 0.104–0.162 native px P95. The strongest shared variation is 1.064 times the color floor and the strongest cross-pointing link has R–B correlation −0.327. No triplet passes intake. The best rejected triplet retains Off on selection. The final reserve stays sealed. Both Lagoon controls and the M33 gain veto replay exactly. [Bat and Wing decision and replay](docs/phase-8d.md#independent-bat-and-wing-selection-screen)
- **ZTF and M51 archive intake** North America fields 730 and 768 supply 18 frozen ZTF observations. Repeated HTTP 503 leaves five of 36 products. The HST M51 fallback gives four calibrated panels, 5–96 selection samples per link, and zero usable native geometry links. The final blocks remain reserved and the separate reversed-order replay matches. [Archive and M51 results](docs/phase-8d.md#ztf-archive-intake-and-hst-m51-fallback)
- **Recovered ZTF network** All 36 products for the 18 frozen exposures verify. Retaining source annotations restores all 15 native geometry links at 0.051–0.088 px P95. The strongest shared variation is only 0.180 times the RGB color floor and no triplet qualifies. The best rejected triplet retains Standard on selection. The final reserve stays sealed. [ZTF selection and replay](docs/phase-8d.md#recovered-ztf-north-america-nebula-network)
- **Orion OSC screen** The independently exposed 2 × 2 broadband mosaic qualifies four links after strict catalog solving. The largest qualified shared span is 0.620 times the RGB color floor. It reaches 0.708 in the flat-bias sensitivity run. The leading rejected triplet retains Standard on selection, and final blocks remain reserved. [Orion measurements](docs/phase-8d.md#orion-simultaneous-broadband-rgb-screen)
- **Elephant Trunk intake** The publisher confirms a broadband OSC mosaic with four pointings. The audit checks all 240 short calibration headers. The closest flat and short dark are 9.1 °C apart, leaving the additive flat correction unverified. The candidate stays at intake, and both the selection and final reserves remain closed. The receipts and downloaded bytes match a separate retrieval. [Calibration audit](docs/phase-8d.md#elephant-trunk-broadband-and-calibration-intake)
- **Public broadband archive search** Six 3AM and three MILAN observing ZIPs expose 4,677 science FITS and zero named calibration companions. The 3AM North America and Pelican samples use the LP dual-band mode. The MILAN sessions lack native flat provenance. Both scoring reserves stay closed, and the independent retrieval reproduces the nine sample FITS checksums and the archive receipt. [Archive results](docs/phase-8d.md#public-broadband-calibration-archive-search)
- **GROND matched-flat source** Same-night optical flats and darks calibrate two candidate triplets. J1016+0419 falls short of the geometry support threshold. The independently exposed 2XMMJ1745-2902 field retains 10, 10 and 11 flats across g′, r′ and i′. Its three r′ links qualify at 0.1029–0.1315 native px P95 on 49–56 selection stars. The same-night archive frames and reversed replay verify. [GROND source and geometry](docs/phase-8d.md#grond-observations-with-same-night-optical-flats)
- **GROND RGB selection** The common training and selection geometry qualifies all three links. The linked spatial spans reach 0.609, 0.374 and 0.491 times the color floor, with a negative channel-pair correlation on each link. Zero links meet network admission. Standard is the selection diagnostic result. Fixed-gain alternatives miss the improvement gates and free-gain fits lack rank. The final reserve stays sealed. The source receipts, binary masks and reversed comparison verify. [GROND selection and repeat commands](docs/phase-8d.md#grond-rgb-coherence-and-selection)
- **Canon Whirlpool OSC selection** The same-session ISO 800 triplet passes three relative links at 0.429–0.479 native px P95. All nine channel-pair correlations are positive. The shared span tops out at 0.999 times the color floor. The rejected network retains Standard on selection with the final reserve sealed. The independent replay matches samples, masks and reports. The 19 °C flats use their own shielded pedestal with the remaining warm spatial additive term unverified. [Whirlpool results](docs/phase-8d.md#same-session-canon-whirlpool-osc-screen)
- **Jellyfish ISO 100 calibration** All 45 Jellyfish calibration headers verify. Its 17 ISO 100 flats are 2.5 s at 21–22 °C. All 28 named additive exposures are ISO 800 at 11 °C. Five companion archives share the same flat identities and add 87 ISO 1600 additive identities. The 132-header audit finds zero ISO 100 bias or dark matches. The candidate remains at calibration intake and its RGB reserves stay sealed. [Header results and repeat command](docs/phase-8d.md#jellyfish-iso-100-calibration-audit)
- **Jellyfish shielded pedestal** All 17 ISO 100 flats verify. The two masked strips agree to 0.386 DN P95. The same-frame phase estimator reaches 0.959 DN P95 on the held strips' 64-row bands, ahead of the other-frame, scalar and row-band estimates. Frame-to-frame variation is 1.021 DN in G1 and at most 0.156 DN in the other phases. The active-area additive term remains unverified. The independent replay matches and RGB reserves stay sealed. [Pedestal measurements and rerun](docs/phase-8d.md#jellyfish-shielded-pedestal-repeatability)
- **Jellyfish active-area additive fit** A free intercept improves reserved calibration prediction by 22.6% in mean P95. Independent training-half maps disagree by 492–920 DN P95. The full-training and reserve fits share spatial structure and differ by 105–200 DN. The illumination zero remains unconstrained, and RGB scoring stays sealed. The reverse replay matches both receipts and 17 source hashes. [Identifiability evidence](docs/phase-8d.md#jellyfish-active-area-additive-identifiability)
- **Jellyfish zero-light search** All 677 remaining CR2 headers from the six archives match the reference camera body. Zero have ISO 100. The only matches to the full capture settings among 809 distinct CR2s are the 17 illuminated flats. The local inventory yields no verified zero-light sequence. The archive replay matches and the RGB reserves stay sealed. [Search results](docs/phase-8d.md#jellyfish-same-detector-zero-light-search)
- **SkyMapper DR4 Rho Ophiuchi** Nine new g/r/i exposures supply three independent linear RGB panels. Zero overlaps qualify on native stellar geometry. The largest common spatial span is 0.0400 times the RGB color floor. Free-gain candidates miss the rank gate on every link. Independent replay matches the decoded source data and selection measurements. Final blocks stay sealed. [Alternate source results](docs/phase-8d.md#skymapper-rho-ophiuchi-selection-screen)
- **CFHT MegaCam M13** Nine short Elixir exposures on CCD 12 supply independent g/r/i panels. An affine refinement fit on training blocks qualifies three links at 0.270–0.331 native px P95. The strongest common spatial span reaches 1.712 times the color floor. The unity-gain Advanced offset improves selection mean P95 by 1.202% and `5.034e-7`, below both limits. Off ties Standard, and final samples stay sealed. Both sets of data, masks and comparison measurements replay. [Results and repeat commands](docs/phase-8d.md#cfht-megacam-m13-short-exposure-selection)
- **CFHT detector extension and visible flat** The seeded CCD 13 triplet qualifies all native links at 0.303–0.402 px. The best shared spatial-to-color ratio is 1.546. Both full five-dither screens reject every triplet. Their native geometry qualifies 19 of 20 links. The archive's exact red flat yields seven selection memberships at 2% response across both CCDs and zero at 3%. Replays agree, with the RGB and optical reserves sealed. [Detector and optical results](docs/phase-8d.md#cfht-adjacent-detector-and-five-dither-screen)
- **Revisit trigger** Resume a candidate when a qualifying observation or calibration becomes available, or the owner schedules the feature. Advanced and optical candidates require production preview and export verification after qualification. Additional optical fits, joint exposure and illumination fitting, seam methods, bracket response and HDR remain deferred. [Phase 8 closure](docs/phase-8.md#phase-8-closure)
- **Next action on revisit** Obtain a calibrated independent RGB network with coherent spatial variation on two or more overlaps. Keep the Lagoon and M33 controls. For visible optics, use a reference with stronger measured flat response leverage. For the locally checked F606W M5 path, obtain observing time and confirm guide stars through the allocated program. Require at least 15 precision-qualified test stars in three blocks after common-pixel and donor screening. Run the wider-dither screen after every geometry-qualified link reaches full-test flux P95 at or below 1%. Arrange a separate Windows 11 x64 environment for portable acceptance. Jellyfish remains at calibration intake pending matching original capped CR2s. Track wide-field lens calibration and overlap under Q-016. Retain the NIRCam, MOANA and visible HST references. Prepare stable exposure brackets and separate lookup-table, rendering-intent and black point controls. [Delivery stages](docs/phase-8.md#delivery-stages)
- **Closure condition** Each shipped method exposes its data requirements, effective settings and fit diagnostics. Verify source preservation, desktop/CLI parity, reproducible tagged photo export and scientific output parity on the frozen cases.

### Q-035 - Desktop panel import and sky preview latency

- **Status / priority** Open / P2
- **Opened / updated** 2026-11-26
- **Affected workflow** Add Panels, first sky preview, and repeated previews on large TIFF inputs.
- **Impact and evidence** Two real 6000 × 4000 RGB TIFFs took about 2.5 s to add while foreground detection scanned 48 million source pixels. Each CPU overview requested 232 million source pixel positions across 240 TIFF windows. The first proxy arrived in 3.0–9.1 s and the overview took 11.1–18.3 s. [Source measurements](progression.md#2026-11-26---desktop-diagnosis---measured-panel-import-and-sky-preview-latency)
- **Current assumption** The owner selected GPU acceleration without adding a preview cache. The native sky preview now samples on hardware OpenGL and accesses compatible TIFF source points directly. [GPU sampling decision](docs/adr/0031-gpu-sky-preview-sampling.md)
- **Next action / responsibility** Measure first-frame latency with cold files on representative local and external storage. Track foreground import scanning separately from sky preview. The first original TIFF preview took 14.45 s while the repeat took 2.35 s on this workstation.
- **Closure condition** Verify improvement on representative real projects with cold and warm measurements, documented peak memory, responsive cancellation, and unchanged reference WCS, coverage, and export results.

## Resolved Topics

### Q-032 - Desktop edit history budget

- **Status / priority** Resolved / P1
- **Opened / updated** 2026-11-26
- **Affected phase** Phase 9C resource limits.
- **Resolution** Each project or draft history keeps up to 100 steps or 8 MiB of accounted immutable values. Shared values count once. An oversized edit remains applied and the Undo control reports the limit.
- **Evidence** Measured a six-panel session and full-sized mask histories on Windows. The regressions cover both eviction limits, branching, oversized edits, saved-state reporting and release on close. [9C measurements](docs/phase-9.md#9c-worker-and-retention-verification)

### Q-001 - Python, dependency, and platform compatibility matrix

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-15 / 2026-11-15
- **Affected phase:** 0.
- **Impact and evidence:** CPython 3.13 and the Poetry lock passed native imports, CLI and worker startup, ASTAP, PySide6, and two local bundle runs on Windows 11 x64.
- **Current assumption:** Use CPython 3.13 and the optional PySide6 Essentials extra for the initial Windows target.
- **Next action / responsibility:** Repeat the [copied-bundle workflow](docs/phase-3f.md#pending-clean-machine-check) on a fresh Windows 11 x64 installation. Revisit additional platforms under Q-008.
- **Closure condition:** Record the locked stack and successful checks for the initial Phase 0 target.
- **Resolution:** 2026-11-15. The Windows-only development gate is met. See [Phase 0 evidence](docs/phase-0.md) and [ADR-0003](docs/adr/0003-windows-first-platform-scope.md).

### Q-002 - Pixel-unit and pixel-area contract

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-15 / 2026-11-15
- **Affected phase:** 0 contracts and 1 reprojection.
- **Impact and evidence:** Pixel-area handling determines whether output samples preserve field brightness or represent integrated flux per pixel.
- **Current assumption:** Read source scaling and retain the unit label. Reproject declared surface brightness and include output pixel solid angles when integrating its aperture flux.
- **Next action / responsibility:** Apply the contract to Phase 1 reprojection and export. Add an area-aware conversion and dedicated tests when integrated-flux inputs enter scope.
- **Closure condition:** Document the convention and check its scale-change behavior against independently calculated values.
- **Resolution:** 2026-11-15. [ADR-0002](docs/adr/0002-surface-brightness-reference.md) records the convention. The uniform-field and Gaussian scale-change fixtures passed on Windows.

### Q-004 - Resource budgets and representative workload

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-15 / 2026-11-18
- **Affected phase:** Phase 0 scheduling, Phase 1 rendering, Phase 2 solvers, Phase 3 preview, Phase 3.6 deadlines, and Phase 4B large-job scaling.
- **Impact and evidence:** The renderer has one synchronous worker and no queued tiles. The optimized full Windows runs peaked at 20.215 MiB reservation, 140.68 MiB working set and 146.06 MiB commit across the three jobs. Separate evidence covers two-panel rendering, native catalog mappings and desktop preview memory. [Phase 4B results](docs/phase-4b.md#footprint-selection-results) · [Phase 1 measurements](docs/phase-1.md#working-set-and-cancellation) · [Phase 2 solver measurements](docs/phase-2.md#windows-solver-evidence) · [Phase 3C preview measurements](docs/phase-3c.md#resource-check)
- **Current assumption:** Default to 128-pixel render tiles, a 64 MiB working reservation and a 2048 MiB output limit. Reserve the preview raster and cap its longest edge at 512 pixels. Account for display, GPU and native catalog allocations separately. [TIFF decode reservation](docs/phase-3a.md#sample-and-metadata-contract) · [Solver staging limit](docs/phase-2.md#offline-solvers)
- **Next action / responsibility:** Measure any future blend buffers, parallel scheduler or extended workload against the named reference.
- **Closure condition:** Document defaults and over-budget behavior, and verify bounded queues, reservations, cancellation and measured peak usage at the Phase 4B scale.
- **Resolution:** 2026-11-18. The three full 12-panel exports, the 6 MiB forced split, the 2048 MiB output refusal and cancellation/retry passed. The benchmark's full RGB job uses a saved 3072 MiB limit. [Phase 4B reference and comparison](docs/phase-4b.md)

### Q-007 - FITS metadata, coverage, and independent export validation

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-15 / 2026-11-15
- **Affected phase:** 0 I/O contracts and 1 FITS export gate.
- **Impact and evidence:** The FITS reader applies source scaling and validity. The exporter writes float32 brightness, NaN for uncovered samples, and an unscaled binary `COVERAGE` image. The reader recognizes this coverage extension on reimport.
- **Current assumption:** Derive output WCS from the render grid and record shared `BUNIT`/`FILTER` and source fingerprints in the header.
- **Next action / responsibility:** Apply independent reopen checks to future formats and channel layouts when their contracts are implemented.
- **Closure condition:** Document and verify pixels, scaling, coverage, WCS, crop/rotation, and SIP removal with small fixtures and independent evidence.
- **Resolution:** 2026-11-15. CFITSIO reopened the exact two-panel result, and the cropped and rotated export matched analytic TAN and SIP checks. [Phase 1 FITS validation](docs/phase-1.md#numerical-and-windows-checks)

### Q-006 - Offline solver and catalog deployment

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-15 / 2026-11-17
- **Affected phase:** Phase 0 adapter experiment, Phase 2 offline astrometry, Phase 3.1 desktop solver settings and jobs, and Phase 3.5 revalidation.
- **Impact and evidence:** The Windows M13 reference passed both hinted and blind Gaia DR3 and ASTAP, ordered fallback, real ASTAP cancellation, missing-catalog diagnostics, and unchanged-source checks. The catalog and index were verified against the versioned manifest.
- **Current assumption:** Install explicit local Gaia and ASTAP files separately, keep the Gaia catalog and index version paired, and save solved WCS in a source-bound sidecar.
- **Next action / responsibility:** Recheck the solver matrix on catalog updates and during release packaging. Track the 40′ M42 coverage result under Q-015 and release notices and data terms under Q-005.
- **Closure condition:** Record a tested solver/version/catalog matrix and deployment/update policy, including ordered fallbacks, cancellation, missing-catalog diagnostics, exhausted-chain behavior, and unchanged-source checks.
- **Resolution:** 2026-11-15. The backend decision and Phase 2 evidence record results, catalog provenance, and the update procedure. The 3.5C Windows rerun verified the M13 matrix, new M42 fields, solver cleanup, and the Documents XPSD format diagnostics. [ADR-0010](docs/adr/0010-seiza-gaia-backend.md) · [Phase 2 setup](docs/phase-2.md#offline-solvers) · [Phase 3.1C desktop checks](docs/phase-3b.md#desktop-plate-solving) · [Phase 3.5C solver results](docs/phase-35.md#m42-offline-astrometry-and-documents-catalogs)

### Q-012 - Desktop terminal scope

- **Status / priority:** Resolved / P2
- **Opened / updated:** 2026-11-16 / 2026-11-18
- **Affected phase:** 4C desktop command panel.
- **Impact and evidence:** The desktop panel reuses the Phase 4A CLI arguments, report formats, render limits, and cancellation. [CLI contract](docs/phase-4a.md#result-contract) · [Worker decision](docs/adr/0019-desktop-command-worker.md)
- **Current assumption:** Keep the panel scoped to AstroMosaic commands, with session history, output, progress, and cancellation.
- **Next action / responsibility:** Retain the source and packaged command-panel checks for future CLI changes.
- **Closure condition:** Record the selected desktop terminal scope and verify its agreed workflows on Windows 11 x64.
- **Resolution:** 2026-11-18. Windows source and copied CPU/OpenGL desktop checks passed. The windowed executable and console CLI produced the same validation JSON and FITS bytes. The panel's progress, session history, cancellation, cleanup and retry passed. [Windows evidence](docs/phase-4c.md#local-windows-results)

### Q-013 - Optical metadata conventions for solve hints

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-16 / 2026-11-18
- **Affected phase:** 3.1A panel metadata and the 3.6A TIFF EXIF/XMP extension.
- **Impact and evidence:** FITS writers may report native or effective pixel pitch. The reader supports numeric FITS-style optical fields in FITS and AstroMosaic TIFF. Binned fixtures verify native and effective pitch, while a conventional TIFF resolution tag leaves the optical values unset. [Optics tests](tests/integration/test_panel_inspection.py)
- **Current assumption:** Interpret the documented field conventions and use panel overrides or a compatible blind solve when the image has no reliable scale hint.
- **Next action / responsibility:** Evaluate additional metadata mappings when a representative acquisition export establishes its field meaning and units.
- **Closure condition:** Document supported conventions and verify the derived scale and missing-metadata behavior with representative fixtures, including a binned case.
- **Resolution:** 2026-11-16. Synthetic FITS and TIFF cases passed, including stale masked WCS and ambiguous binning. Local Gaia and ASTAP solved M13 using embedded optical hints. [Supported metadata and Windows evidence](docs/phase-3b.md#panel-wcs-and-plate-solve-hints)

- **Extension:** 2026-11-18. [3.6A](docs/phase-36a.md#tiff-metadata-at-panel-import) verified standard EXIF/XMP physical focal length, focal-plane inch/centimeter units and camera display, including both owner TIFFs. Print DPI, 35 mm equivalents and ambiguous/invalid resampling or zoom metadata do not create sensor-scale hints. Explicit source fields and user overrides retain precedence; absent reference dimensions leave nominal pitch labeled as a hint.

- **Follow-up:** 2026-11-18. The panel dialog now fills its optical fields from background inspection. Standard TIFF tags and XISF image properties enter the same solve-hint path as FITS optical fields. FITS fixtures verify already-binned pitch from N.I.N.A. and MaxIm DL. A saved panel edit still overrides its corresponding optical measurement. [Updated import behavior](docs/phase-3b.md#panel-wcs-and-plate-solve-hints) · [Cross-format checks](tests/integration/test_panel_inspection.py)

### Q-014 - Regression coverage for narrow overlaps, saturation, and WCS reuse

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-17 / 2026-11-17
- **Affected phase:** 3.5B revision and 3.5C verification.
- **Impact and evidence:** Three automated regressions verify offset selection with a four-pixel overlap, exclusion of saturated stars from gain measurements, and masked WCS reuse. [Review and reproduction](docs/phase-35.md#supplementary-results-and-follow-up) · [3.5B results](docs/phase-35.md#phase-35b-regression-results)
- **Current assumption:** Use deterministic synthetic fixtures for the suite and the recorded M13 and M31 recipes for real-field checks.
- **Next action / responsibility:** Rerun the recorded cases when changing refinement, masks, or WCS reuse.
- **Closure condition:** The added regressions protect the frozen sample, geometry, and fitting criteria. The Windows source and bundled checks meet the recorded thresholds.
- **Resolution:** 2026-11-17. The 88 source tests, identical masked CLI exports for common WCS inputs, and the real-field checks met their thresholds in 3.5C. [Windows verification](docs/phase-35.md#phase-35c-windows-verification)

### Q-015 - Offline solver coverage on the 40′ Orion field

- **Status / priority:** Resolved / P2
- **Opened / updated:** 2026-11-17 / 2026-11-18
- **Affected phase:** Phase 3.6A fixtures and 3.6F real-field verification, following the coverage finding in 3.5C.
- **Impact and evidence:** Portable Seiza 0.48.2 solved the 40′ ESO M42 cutout with hints. Its blind index exhausted 400 hypotheses. ASTAP CLI-2026.11.01 with D05 failed hinted solving and timed out blind. Seiza solved the 55′ M42 cutout blind. [M42 inputs and results](docs/phase-35.md#m42-offline-astrometry-and-documents-catalogs)
- **Current assumption:** The verified 40′ ASTAP-only Orion workflow uses CLI-2026.11.01, D20 or D50, and pointing and scale. The policy can recover locally from a wrong scale when pointing is usable.
- **Next action / responsibility:** Retain the dense catalog matrix when checking future recovery policy changes. Q-016 tracks catalog-dependent quality and broader field coverage.
- **Closure condition:** Record validated solutions and elapsed times across a named subdegree sample, or document the supported hint requirements for those fields.
- **Resolution:** 2026-11-18. D20 and D50 qualified the 40′ Orion fixture with both hints. The three dense catalogs reached the 60-second cap in blind Orion trials. The named M31 40′ and M13 55′ controls recorded validated solutions and times. [Dense catalog results](docs/phase-36-results.md#dense-astap-catalog-verification)

### Q-017 - Automatic ASTAP catalog selection and ASTAP-only quality evidence

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-17 / 2026-11-18
- **Affected phase:** Phase 3.6A capabilities, 3.6B catalog automation, 3.6D candidate validation and 3.6F settings/migration.
- **Impact and evidence:** Earlier ASTAP silently substituted D05 for a missing manual D20. AstroMosaic now inventories tiles, checks the actual native catalog identity and verifies the selected catalog's solution. Verified D05 Auto and Unicode path coverage preceded the dense-catalog matrix. [Implementation results](docs/phase-36-results.md)
- **Current assumption:** Fresh settings use Automatic. Use verified native selection or explicitly pass a complete supported D-series set. Keep manual choices pinned and qualify ASTAP-only results with independent local catalog matches under the common quality thresholds.
- **Next action / responsibility:** Rerun selection and missing-tile controls on CLI or data updates. Q-016 tracks the Orion D80 quality rejection. Q-005 retains catalog redistribution review.
- **Closure condition:** Automatic/manual modes, actual catalog provenance and the ASTAP-only quality path pass real Windows native cases, including missing/partial catalogs and unknown/bad FOV. Preserve user ASTAP settings and original images, and report unsupported cases.
- **Resolution:** 2026-11-18. Real single and mixed D-series sets verified native Automatic and manual pinning. Automatic bypassed incomplete D80 and qualified with D50. Pinned incomplete and missing D80 produced diagnostics without sidecars. The alternate CLI used explicit D20. Source, copied console and native desktop checks verified catalog provenance, supported recovery, saved settings and unchanged source hashes. [Dense catalog results](docs/phase-36-results.md#dense-astap-catalog-verification)

### Q-018 - End-to-end solve deadlines and compatibility

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-17 / 2026-11-18
- **Affected phase:** Phase 3.6A budget freeze, 3.6C orchestration/cleanup, 3.6F CLI/desktop/report compatibility and Phase 4 automation.
- **Impact and evidence:** The implementation keeps `--timeout` per native attempt and shares a default 120-second panel deadline through source opening, staging, searches, validation, and sidecar publication. Gaia catalog/native work uses reaped spawn workers. Source tests pass late-candidate, late-publication and nonresponsive-worker cases. Version 1 reading and version 2 publication are covered. [Deadline contract](docs/phase-36.md#7-total-deadline-cancellation-and-reporting) · [Results](docs/phase-36-results.md#deadlines-and-compatibility)
- **Current assumption:** Local Windows samples support the stated deadlines at checkpoints. Filesystem and OS stalls can add a reported overrun. Neither the validation reserve nor worker cleanup restarts the panel timer.
- **Next action / responsibility:** Carry the panel and batch report into Phase 4 automation. Keep clean-machine and storage-dependent timings separate.
- **Closure condition:** Deterministic boundary tests and real source/portable jobs meet the frozen whole-pipeline, cancellation and cleanup limits, reject late success, retain earlier panels, and read old settings/projects/sidecars without silent semantic changes.
- **Resolution:** 2026-11-18. The source and portable local Windows gates passed. A real ASTAP cancellation reaped the process and cleared scratch in about 0.025 seconds. Portable exhaustion and timeout published no sidecars. [Deadline evidence](docs/phase-36-results.md#deadlines-and-compatibility)

### Q-019 - Owner wide-field TIFF solve and regional validation coverage

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-17 / 2026-11-18
- **Affected phase:** Phase 3.6A real fixtures, 3.6D scale recovery, 3.6E regional/SIP accuracy and 3.6F acceptance.
- **Impact and evidence:** The two 6000 × 4000 RGB owner TIFFs contain Nikon D5300 EXIF with 24 mm focal length and nominal 3.9083 micrometer pixels (33.59 arcsec/pixel). The load path now imports these hints; local Gaia TAN solves found 890/894 matches at about 54 arcsec RMS. [3.6A broad blind/SIP probes](docs/phase-36a.md#owner-wide-field-results) found 992/1009 native matches at about 10 arcsec RMS; independent D05 checks found 1425/1461 matches at about 13 arcsec RMS. The 21.TIF fine support map contains insufficient-star cells, so this is not an entire-frame accuracy certificate. Correct wide-field ASTAP hints recommend missing W08 and fail after D05 fallback/cropping.
- **Current assumption:** Keep source TIFFs ignored, immutable and offline. Use native EXIF focal-plane units rather than print DPI or 35 mm equivalent focal length. Distinguish approximate optical hints, native fit statistics and independent regional evidence. Keep supported ASTAP catalog domains and broad Gaia recovery ranges explicit.
- **Next action / responsibility:** Retain the private files as optional local regression inputs and continue to show insufficient regional support. Wide-field ASTAP catalog validation is a separate format and deployment follow-up.
- **Closure condition:** The owner cases have reproducible source/portable outcomes under the finalized quality/budget policy, with unchanged image hashes, explicit supported catalog/scale ranges and independent spatial accuracy or documented support limitations. Native solve success alone does not close this topic.
- **Resolution:** 2026-11-18. Both source and portable runs qualified SIP-3 after recovery. The independent D05 edge P95 values were 0.895 and 0.985 px. The original files matched their initial SHA-256 values, and each new sidecar drove an independently reopened RGB export. [Windows evidence](docs/phase-36-results.md#portable-windows-verification)

### Q-021 - ZEA antipode and exported crop validation

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-18 / 2026-11-18
- **Affected phase:** Phase 5B sky geometry and format reimport.
- **Impact and evidence:** The antipode is non-unique on the ZEA rim. With the installed WCSLIB, a polar rim coordinate could round-trip, and FITS header rounding could place a nominal rim sample just inside the domain.
- **Current assumption:** Apply a native-latitude guard around the antipode and keep the bounded full mapper. Allow a cropped source with valid support to validate at a nearby in-frame reference position.
- **Next action / responsibility:** Carry the fixture into future geometry changes and verify the domain of each added projection.
- **Closure condition:** The rim and exterior are uncovered, the valid crop reopens with its WCS, and an entirely invalid crop leaves the destination free.
- **Resolution:** 2026-11-18. The polar fixture passed with serialized WCS and a shifted panel. The rim-centered crop reopened with 12 valid positions. The fully outside crop removed its temporary output. [Windows results](docs/phase-5b.md#local-windows-results)

### Q-022 - Native desktop test automation process exits

- **Status / priority:** Resolved / P2
- **Opened / updated:** 2026-11-19 / 2026-11-19
- **Affected phase:** Local Windows desktop application test automation and Phase 6E native acceptance.
- **Impact and evidence:** An earlier multi-window run timed out and exited with `0xc0000409` on both renderers. The reduced real M17 and ALPACA replay reproduced the exit when it dropped the old window during deferred cancellation. Qt reported destruction of a running `QThread`. The initial local report is `output/application-tests/20261119-110157-116/test-report.md`. [Recorded lifecycle findings](docs/application-test-findings.md#native-desktop-lifecycle-and-release-acceptance)
- **Current assumption:** Retain the window through accepted close and worker teardown. Release OpenGL preview resources on the UI thread while their context is usable.
- **Next action / responsibility:** Retain the real replay and repeat the lifecycle checks on the clean-machine candidate selected for release.
- **Closure condition:** Identify the cause of the process exits and record a repeatable native run of the affected window transition on both renderers.
- **Resolution:** 2026-11-19. Eight orderly source and frozen desktop sequences passed across CPU and OpenGL. They verified idle reopen, close during preview and export, temporary-file cleanup and same-destination retry. The normal OpenGL teardown warning was traced to deferred texture destruction and fixed. [6E lifecycle evidence](docs/phase-6.md#local-windows-lifecycle-and-package-results)

### Q-023 - Wide ZEA preview coordinate warnings and runtime

- **Status / priority:** Resolved / P2
- **Opened / updated:** 2026-11-19 / 2026-11-19
- **Affected phase:** Shared sky coordinate mapping and Windows preview performance in phases 3C, 4B, 5B and 6D.
- **Impact and evidence:** Both desktop backends and the 6A source CLI emitted the Astropy all-NaN-slice warning on the PA4 ZEA mosaic. The PA4-10 replay located 16,384 finite sky directions outside the panel's TAN projection in the first 128 × 128 tile. [Original findings](docs/application-test-findings.md#wide-zea-diagnostics-and-preview-performance) · [6D replay](docs/phase-6.md#local-zea-geometry-and-performance-results)
- **Current assumption:** Send only finite core inverse seeds to the distortion solver. Use all-panel mapping wherever a conservative ZEA footprint is unavailable.
- **Next action / responsibility:** Retain the real PA4 replay and timing baseline for future geometry and scheduler changes. Carry the qualified outputs into 6E.
- **Closure condition:** Explain or handle the warning's confirmed cause, retain geometry and coverage checks, and record a repeatable timing comparison on a fixed project.
- **Resolution:** 2026-11-19. The real replay, native previews and full source export no longer emit the warning. The 6A reference and both guarded full ZEA paths match for samples, coverage and WCS. Candidate selection reduced the full-render mapping count from 4,335 to 1,086. TIFF reads account for the largest remaining preview cost. [6D measurements](docs/phase-6.md#local-zea-geometry-and-performance-results) · [ADR-0024](docs/adr/0024-conservative-zea-footprints.md)

### Q-024 - Preview of solved RGB TIFF panels

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-21 / 2026-11-21
- **Affected phase:** Phase 3C desktop preview and export setup.
- **Impact and evidence:** Two verified WCS sidecars reopened successfully. The saved project lacked filter and brightness declarations, and its default sky grid sampled only one panel. The original desktop failure gave a CLI flag instead of the corresponding setting.
- **Current assumption:** Use a grid that covers both panels and supply a common label and scale for compatible linear samples. Linearized sRGB derivatives can be used for a relative visual preview. [Desktop workflow](docs/phase-3c.md#desktop-workflow)
- **Next action / responsibility:** Retain the desktop calibration diagnostic regression when verifying the next Windows build.
- **Closure condition:** Explain the failure in the desktop log and verify a reopened preview that includes each panel and their common coverage.
- **Resolution:** 2026-11-21. The Command Panel identifies the missing settings. A separate project with linear-light visual copies and a fitted grid previewed both panels on native CPU and OpenGL. The source and portable CLI validated the project. The original file hashes matched.
- **Follow-up:** 2026-11-21. Beta 4 assigns `Unspecified` to unlabeled panels. The original project reaches brightness validation, and the packaged CPU and OpenGL backends previewed both real linear TIFF panels with their filter labels removed. [Per-band workflow](docs/phase-5c.md)
- **Follow-up:** 2026-11-21. The latest saved project still referenced the sRGB input TIFFs and the default output grid. A separate visual preview project reused the validated linear-light copies after checking their WCS against the latest sidecars and their sampled values against the sRGB transfer. The beta 6 CLI and native OpenGL checks passed with both panels represented.
- **Follow-up** 2026-11-21. Beta 7 previews the original TIFFs directly with automatic framing. See Q-028 for the packaged verification.

### Q-025 - Identify the local Windows build after source changes

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-21 / 2026-11-21
- **Affected phase:** Local Windows desktop builds and handoff.
- **Impact and evidence:** The earlier `0.1.0b2` executable came from a snapshot that preceded the Command Panel startup and sky preview diagnostic fixes. The merged source still reported the same version.
- **Current assumption:** Use the desktop title, versioned runtime folder and recorded source commit to identify a local beta. [Windows build workflow](docs/windows-release.md#build-portable-windows-packages)
- **Next action / responsibility:** Verify the title and the affected workflows on each successor build used for handoff.
- **Closure condition:** Provide a separately identified executable from the merged source and verify both desktop changes in the packaged runtime.
- **Resolution:** 2026-11-21. Local beta 3 reports its own title and carries the source revision and launcher hash. The Command Panel and preview checks passed on native Windows CPU and OpenGL.

### Q-026 - Plate Solve activity before the first panel finishes

- **Status / priority:** Resolved / P2
- **Opened / updated:** 2026-11-21 / 2026-11-21
- **Affected phase:** Phase 3.1C desktop plate solving.
- **Impact and evidence:** The desktop bar showed 0% until the first panel produced an outcome. A single-panel solve could look idle throughout its search. The desktop regression reproduced this display while the worker was active.
- **Current assumption:** Show percentages at completed solve steps and update elapsed time while the native solver searches. Display the active panel, backend and phase beside the job controls.
- **Next action / responsibility:** Retain the stage progression, narrow-window layout and real M13 Windows checks in later builds.
- **Closure condition:** Single-panel and batch solves report increasing percentage milestones. The status advances with the active work, and cancellation retains completed outcomes and reports partial progress.
- **Resolution:** 2026-11-21. Beta 5 rendered distinct animation frames during real single-panel and batch M13 solves in the packaged runtime. Cancellation preserved the first WCS, retry solved the remaining panel, and revalidation animated with CPU and OpenGL previews active. [Windows build verification](docs/windows-release.md#verification-status)
- **Follow-up:** 2026-11-21. Beta 10 adds the step-based percentage in a wider strip. The real ASTAP D05 and Gaia DR3 M13 runs verified the displayed stages, elapsed timer and cancellation in source and both packaged preview modes. The Command Panel shows its own progress during its commands. [Beta 10 progress verification](docs/phase-3b.md#beta-10-progress-verification)

### Q-027 - Dialog-free project lifecycle and headless preparation

- **Status / priority:** Resolved / P1
- **Opened / updated:** 2026-11-21 / 2026-11-21
- **Affected phase:** Phase 4A headless automation and Phase 4C desktop commands.
- **Impact and evidence:** The Command Panel could run CLI jobs against saved files. First save, open, relink and closing a dirty desktop project required GUI input. The standalone solver could produce a sidecar for one panel, and batch scripts needed a separate way to attach results to an existing project.
- **Current assumption:** Use explicit session paths and write new manifests for file-based preparation. Accept supplied label masks and numeric placement with the existing geometry validators. Phase 7E tracks saving and rendering terrain control-point geometry.
- **Next action / responsibility:** Keep the session and project preparation regressions in Windows verification for later builds.
- **Closure condition:** The live project can be saved, reopened and exported without dialogs. The standalone CLI can relink, solve and prepare mixed-layer projects from supplied paths, and failures preserve the inputs and permit retry.
- **Resolution:** 2026-11-21. The beta 6 desktop exercised the M13 lifecycle with zero modal dialogs, and the console attached WCS and exported M13 after a deadline retry. The real Paranal run imported label masks, aligned the two ground panels, verified proposed and numeric placement, and reopened the composition. [Windows evidence](docs/windows-release.md#verification-status)

### Q-028 - Automatic sky preview for solved panels

- **Status / priority** Resolved / P1
- **Opened / updated** 2026-11-21
- **Affected phase** Phase 3C desktop sky preview and export setup.
- **Impact and evidence** The beta 6 workflow for the owner TIFFs required a manually framed grid and separate linear-light copies. The original images carry standard sRGB profiles and have usable WCS after offline solving.
- **Current assumption** Fit new sky previews from the selected WCS footprints. Decode recognized unsigned 16-bit RGB sRGB TIFFs in the visual preview. Keep the fitted grid temporary until the user explicitly adopts it. [ADR-0025](docs/adr/0025-automatic-sky-preview.md)
- **Next action / responsibility** Keep the automatic grid, sRGB and science validation regressions in Windows verification.
- **Closure condition** Both original panels solve and appear in the preview with measurable overlap. The saved grid changes only on explicit adoption and scientific export still rejects the encoded panels.
- **Resolution** 2026-11-21. Source OpenGL and bundled CPU and OpenGL each solved both originals and built the preview. The bundled runs matched 109,331 valid samples and 23,020 common samples. Explicit grid adoption and scientific rejection passed, and the inputs retained their hashes. [Windows workflow verification](docs/phase-3c.md#windows-verification)

### Q-030 - Adaptive framing and interactive preview verification

- **Status / priority** Resolved / P1
- **Opened / updated** 2026-11-22
- **Affected phase** Phase 8B desktop preview and saved crop follow-up.
- **Impact and evidence** The fixed point overview could drop fine structures and enlarge aliasing at high zoom. The adaptive overview, 1:1 detail and crop editor must share the saved output geometry and retain fixed photo tone across view changes. [ADR-0027](docs/adr/0027-adaptive-sky-preview.md)
- **Current assumption** Use bounded linear-light area samples for the overview and exact full-resolution samples for a visible bounded detail window. Preserve user locks and adopt a dragged crop explicitly.
- **Next action / responsibility** Retain the real crop and zoom replay for future native releases. Include the adaptive workflow in the clean-machine acceptance matrix.
- **Closure condition** Verify crop editing and reopening, independent output WCS and samples, stable tone, native redraw, resource limits, cancellation and retry in source and portable Windows.
- **Resolution** 2026-11-22. Beta 12 verified the visible crop handles and 1:1 detail on native CPU and OpenGL. The copied CLI and both desktop paths exported identical crops. Independent WCS, exact RGB and coverage matched the full-resolution reference region. [Beta 12 results](docs/phase-8.md#8b-adaptive-preview-follow-up)

### Q-031 - Architecture review follow-up

- **Status / priority** Resolved / P2
- **Opened / updated** 2026-11-26 / 2026-11-26
- **Affected scope** Post-Phase-8 project plate solving.
- **Impact and evidence** The desktop and CLI duplicated the batch stop rules. CLI WCS reuse checks ran on the entire sky selection before filtering the requested panels, so an unselected panel could exhaust the job budget.
- **Resolution** The Qt-free [project module](src/astromosaic/storage/project.py) runs the ordered batch and stops on cancellation or job exhaustion. The desktop retains completed outcomes and the CLI publishes a complete copy atomically. [CLI reuse checks](docs/phase-4a.md#prepare-a-project-without-the-desktop) inspect just the panels selected for the job.
- **Verification** A selected-panel regression reproduced the old failure. All 36 focused Windows source tests passed after the fix, including native-solver diagnostics and CLI budget, cancellation and publication checks. The full offscreen source suite passed 261 tests with six documented skips.

### Q-033 - Composition overlap highlight at detail zoom

- **Status / priority** Resolved / P3
- **Opened / updated** 2026-11-26 / 2026-11-26
- **Affected scope** Desktop composition preview presentation.
- **Impact and evidence** Toggling Highlight Overlap changed the overview but left the displayed 1:1 detail in its previous colors. The detail worker applied the highlight once, and later redraws reused that choice.
- **Resolution** The viewport uses the active highlight setting for both views. It retains the original detail frame so the toggle can update color immediately in either direction while preserving the detail region, tone, coverage and 1:1 indicator. [Composition workflow](docs/phase-3e.md#desktop-workflow)
- **Verification** The framebuffer regression reproduced the mismatch on CPU and OpenGL before the fix. Native Paranal tests passed on both. They checked both toggle directions and a new 1:1 result delivered while Highlight Overlap was enabled.

### Q-034 - Sky preflight output suffix

- **Status / priority** Resolved / P2
- **Opened / updated** 2026-11-26 / 2026-11-26
- **Affected scope** Phase 4A scientific sky preflight.
- **Impact and evidence** A mono project could pass validation with a proposed `.bin` file and fail export because the FITS writer rejected the suffix.
- **Resolution** Scientific sky preflight and rendering now use the writer's suffix check. Existing FITS aliases remain case-insensitive. [CLI validation workflow](docs/phase-4a.md#create-and-validate)
- **Verification** The CLI regression reproduces the earlier mismatch and checks matching diagnostics, rejection without a part file, and acceptance of an uppercase `.FIT` destination.

## New Entry Template

```markdown
### Q-NNN - Short descriptive title

- **Status / priority:** Open / P1
- **Opened / updated:** YYYY-MM-DD / YYYY-MM-DD
- **Affected phase:** Phase and the specific action or gate affected.
- **Impact and evidence:** What is uncertain or failing; reproduction or evidence link.
- **Current assumption:** Safe temporary behavior or workaround, including limitations.
- **Next action / responsibility:** Concrete investigation or decision and who can resolve it.
- **Closure condition:** Observable evidence needed to close the topic.
- **Resolution:** Add the date, outcome, and evidence/ADR when resolved.
```
