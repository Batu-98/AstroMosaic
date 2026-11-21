# Phase 7 Terrain Panorama Registration

**Status** The 7A–7D checks ran on the Windows 11 x64 development host. Oxford Boat and La Silla passed independent automatic-fit checks, and the existing and manual translation paths cover ALPACA. The 7D experiment improved PASSTA and PA4 reprojection errors with camera rotation, but both cases still exceed the frozen tolerance. Translation and similarity are the supported models for 7E. The scientific sky pipeline continues to use its own masks and celestial WCS. [Phase 6 handoff](phase-6.md#handoff-to-phase-7a) · [Geometry decision](adr/0023-terrain-control-point-registration.md)

## Research Findings

| Reference | Documented approach | Implication for AstroMosaic |
| --- | --- | --- |
| PTGui alignment | The published workflow finds corresponding details and stores control-point pairs. The optimizer adjusts image parameters to bring matched features together. Users review residuals and can add points to connect missing overlaps. Lens and orientation variables have separate controls. [PTGui FAQ](https://www.ptgui.com/faq) | Make matched terrain points, residuals and connected groups available to the user. Use identifiable support across the overlap when fitting any additional camera or lens parameters. |
| PTGui Pro viewpoint and masking | The viewpoint tutorial assumes an approximately planar region and uses control points placed on that surface. The mask tool lets the user control which source regions contribute to the rendered blend. [Viewpoint correction](https://www.ptgui.com/examples/vptutorial.html) · [Masking](https://www.ptgui.com/examples/masktutorial.html) | Treat a translated camera and mixed-depth terrain as a separate failure mode. Use the ground mask at feature extraction and at render time. Retain explicit region selection for visual composition. |
| PTGui Pro seam placement | PTGui documents routing seams through lower-disagreement portions of the overlap and around objects. User masks can influence the route. [PTGui seam placement](https://www1.ptgui.com/whatsnew/120000) | Measure the geometry before assessing seam placement. Select seams within verified coverage using measured disagreement if a later experiment justifies the added cost. |
| Hugin | `cpfind` describes local features, distributes points across the image and uses RANSAC. It can remap wide images for matching and map the recovered points back to source pixels. Its geometric verification can use orientation and lens field-of-view information. `autooptimiser` stages geometry optimization based on the available points and offers separate photometric optimization. [cpfind manual](https://hugin.sourceforge.io/docs/manual/Cpfind.html) · [autooptimiser manual](https://hugin.sourceforge.io/docs/manual/Autooptimiser.html) | Bound work by panel and region, retain full-resolution source coordinates, and choose a model whose parameters the observations support. Compare all pairs for small projects before prioritizing candidates from capture order or known poses. |
| Brown and Lowe | Their published system verifies local matches, forms a connected image graph, and jointly optimizes camera orientations and focal lengths using robust reprojection error. Blending is a later operation. [Panoramic stitching paper, Sections 2–4](https://www.cs.ubc.ca/~lowe/papers/07brown.pdf) | Initialize from reliable edges, fix one reference frame, and optimize across all accepted overlaps. Use held-out points and graph loops to expose drift. Assess image seams after registration is verified. |

The PTGui comparison describes its published workflow. The algorithm choices below are proposals for AstroMosaic based on the open references and the project's own evidence.

## Current Behavior and Model Choice

`align_foreground()` currently uses up to 256-pixel thumbnails, masked normalized correlation and full-resolution patch refinement. It fits X/Y translations on a connected graph with one anchored panel. The model assumes the same pixel scale and orientation and enforces equal source dimensions. In the PA4 six-frame replay, every pair had masked support and texture at eligible shifts. The thumbnail peaks ranged from 0.236 to 0.522 against the 0.72 threshold. Real correspondences are needed to measure whether a different camera model aligns shared terrain. [Current matcher](../src/astromosaic/pipeline/foreground.py) · [PA4 evidence](application-test-findings.md#foreground-alignment-and-mask-feedback)

| Capture geometry | Candidate model and use | Evidence before adoption |
| --- | --- | --- |
| Same framing and scale with a small shift | Keep the existing translation path and use control-point translation as the simplest comparison. | The real translation control meets the frozen residual and coverage bounds. |
| Small field or local overlap with in-plane rotation or uniform scale change | Fit a 2D similarity transform with X/Y translation, rotation and one scale. Start here for manual and automatic points. | Distributed points support the model and it improves held-out residuals over translation beyond annotation repeatability. Scale and orientation stay plausible for the capture. |
| Rectilinear panels from a camera turned around a nearly fixed viewpoint | Map source pixels to lens-corrected bearing vectors, estimate relative three-axis rotations and fit rotations jointly in a fixed local reference frame. For undistorted pixels with known intrinsics, the pair mapping has the form `K_j R_ji K_i^-1`, where `R_ji` maps directions from camera `i` to `j`. | Same calibration or known focal data, broad enough support to constrain rotation, and better held-out coverage and residuals on a real panned or tilted sequence. Assess shared lens parameters only when residuals and coverage support them. [Rotation model](https://www.cs.ubc.ca/~lowe/papers/07brown.pdf) · [Camera model](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html) |
| Camera translated with identifiable terrain on an approximately planar surface | Evaluate a bounded homography as a planar comparison on that selected region. | Independent checks on the plane, conditioning and valid mapped boundaries. Release acceptance for the first panorama workflow uses the validated similarity or rotation model. [Alignment models and parallax](https://www.microsoft.com/en-us/research/publication/image-alignment-and-stitching-a-tutorial/) |
| Camera translated with significant near/far depth variation | Diagnose parallax using residuals on independently marked depth groups. Offer a mask that selects a coherent region, explicit manual point review or exclusion of the weak connection. | The output reports unsupported regions and leaves genuinely disconnected scenes separate. Accept a single transform for a selected region only when it meets the measured bounds. |

Keep matching, geometry estimation, and blending individually measurable. A low error on fitting points, a visually smooth seam, or a high match count can each coexist with a wrong geometric solution. [Stitching and ghosting analysis](https://www.microsoft.com/en-us/research/publication/image-alignment-and-stitching-a-tutorial/)

## Real Data and Acceptance Measurements

**Use real observational data exclusively for every Phase 7 test and benchmark.** Apply the provenance and privacy rules in Phase 6. Use separate exposures for capture-to-capture comparisons. Document any crop, calibration, mask edit, or format conversion and keep its source-pixel coordinate mapping. Retain owner images and raw measurement files locally. [Phase 6 data rules](phase-6.md#test-data-requirement)

| Case | Required measurements |
| --- | --- |
| Real translation control from 6A | Baseline connected pairs, source-pixel shifts, landmarks and repeatability, valid coverage, and independently reopened output. This protects the existing aligner and saved translations. |
| PA4 masked ground group | Review all 15 pair outcomes. Mark verified shared terrain on plausible overlaps where it exists. Annotate near, far and masked areas as applicable. Compare fits only on observed correspondences, and record whether each omission follows from support, ambiguity, geometry or parallax. |
| Independently captured rolled or panned sequence | Select a rectilinear sequence with genuine overlap and known optics. Use three or more frames with a redundant overlap where practical to measure loop drift. A fixed viewpoint and widely distributed landmarks make the rotation comparison interpretable. |
| Independent nightscape with overlapping terrain | Obtain a positive holdout sequence with real sky and ground, stable landmarks and comparable masks. Include varying brightness or narrow usable ground where the captures support it. Measure automatic matching and the manual recovery path independently. |
| Disconnected, repetitive or low-texture terrain and depth-change case | Include a real negative overlap and a real change of viewpoint with separated near and far landmarks. Measure false accepted edges, misalignment by depth, exposed gaps, and the quality of the rejection explanation. |

For a controlled capture, photograph adjacent frames of the same scene with fixed focal length and focus and with landmarks at several distances. Record one sequence rotated around a near-fixed lens entrance pupil and a second sequence with a real camera position change. Record sufficient two-dimensional overlap to compare camera models, then use a separate nightscape for field validation. [PTGui capture guidance](https://www.ptgui.com/faq)

Keep the same manual point pairs and split for comparing models. Reserve whole landmarks and spatial regions for validation so repeated observations of the same landmark cannot enter both sets. Freeze the annotation method, the supported overlap, and tolerances in 7A. For well-sampled points, a starting target is held-out P95 at or below 2 source pixels if repeated marking can resolve that error. Record a dataset-specific bound before tuning. Report median, RMS and P95 of forward and reverse pixel transfer, valid support and its spatial spread, graph connectivity and loop error where present, and results by real case. Require zero accepted links between known disconnected groups in the frozen negative controls. A new model must improve beyond the repeated annotation uncertainty and meet the frozen absolute bound. Record fitted errors separately from held-out errors.

## 7A Freeze the Reference and Diagnose PA4

1. Load the [6A–6B evidence](phase-6.md#handoff-to-phase-7a). Use the recorded source hashes, capture information, mask variants, expected connectivity, and pair outcomes for the shared cases. Add the independently captured cases needed for model comparison and holdout evaluation.
2. Extend the landmark annotations across the full usable overlap, with points at different heights and depths where visible. Freeze the fitting and held-out landmark sets and record repeated annotation error. Review the `FOREGROUND` coverage at those points and the spatial leverage available for rotation or scale. Preserve the original mask and compare any edited copy explicitly.
3. Use the recorded translation results for matching inputs and settings. Run the current aligner on new cases or revised inputs to establish their baseline. Fit translation and similarity to the same training points with the same reference anchor, then compare held-out residual fields. For meaningful PA4 edges, record which observations support a mask, overlap, camera direction or depth explanation. Carry unresolved camera and depth hypotheses to the geometry checks in 7D.

**Acceptance** The same real inputs, annotations, commands, thresholds and split can be replayed. Each PA4 case has measured support or a documented open cause. Real evidence identifies the first geometry experiment and a positive case with genuine overlap. [Q-003](../questions_open_topics.md#q-003---reference-datasets-and-frozen-acceptance-thresholds) · [Q-010](../questions_open_topics.md#q-010---foreground-recognition-masks-and-composition)

### Initial 7A measurements

The local run checked the six PA4 TIFF hashes, original mask labels and sky fingerprints against 6A, and the reduced labels against 6B. Both mask variants rejected all 15 pairs at the 0.72 correlation gate. The peak sample counts describe the matcher's trial shifts. Physical overlap was reviewed using recognizable structures in the original captures.

| PA4 pair | Original / reduced peak | Terrain review |
| --- | ---: | --- |
| 02–03 | 0.478 / 0.484 | One repeatable pale twig confirmed physical overlap. The corresponding pixel is unclassified in 03. Remaining candidates lacked repeatable or distributed support. |
| 02–04 | 0.379 / 0.408 | Physical overlap unresolved. |
| 02–05 | 0.236 / 0.286 | Physical overlap unresolved. |
| 02–06 | 0.297 / 0.353 | Physical overlap unresolved. |
| 02–07 | 0.331 / 0.375 | Physical overlap unresolved. |
| 03–04 | 0.429 / 0.477 | Physical overlap unresolved. |
| 03–05 | 0.417 / 0.435 | Physical overlap unresolved. |
| 03–06 | 0.377 / 0.387 | Physical overlap unresolved. |
| 03–07 | 0.335 / 0.468 | Physical overlap unresolved. |
| 04–05 | 0.465 / 0.515 | Matching branches measured. Incomplete ground labels and residual geometric error are both documented. |
| 04–06 | 0.407 / 0.428 | Physical overlap unresolved. |
| 04–07 | 0.480 / 0.561 | Physical overlap unresolved. |
| 05–06 | 0.340 / 0.386 | Seven repeatable landmarks confirmed overlap. Four have joint original ground support and the similarity residual exceeds the 2 px target. |
| 05–07 | 0.522 / 0.637 | Physical overlap unresolved despite the strongest correlation peak in both variants. |
| 06–07 | 0.429 / 0.534 | Illuminated branches are visually ambiguous. Physical overlap unresolved. |

For 04–05, a local image warp helped locate the same tree structures in each view. Points were selected by visible structure and assigned to fitting or held-out regions before model fitting. Two source-pixel patch measurements used different color channels and window sizes. The provisional quality floor was 0.65 normalized correlation in both measurements and at most 3 px between them. An independent reverse-direction refinement in the blue channel returned all ten retained points within 1.84 px of their original reference positions. The results measure image-based repeatability on the selected structures.

Ten of 27 candidates met those image-based checks. Two had four ground-labeled bilinear neighbors in both original masks, and each lost joint support under the reduced masks. The other eight had unclassified pixels in at least one original mask. The original masks support no fitting points among these candidates. The exploratory geometry comparison uses all ten visually identified terrain points regardless of the saved label. It anchors on panel 04 and uses the same three fitting and seven held-out landmarks for both models. Fitting points span 381 × 1621 source px. The two patch measurements have 1.28 px P95 disagreement.

| Real pair | Fit / held-out points | Translation held-out P95 forward / reverse | Similarity held-out P95 forward / reverse |
| --- | ---: | ---: | ---: |
| PA4-04/05 visible terrain | 3 / 7 | 306.08 / 306.08 px | 72.11 / 69.30 px |
| ESO ALPACA A/B original ground | 5 / 4 | 1.43 / 1.43 px | 1.51 / 1.51 px |

Both PA4 models exceed the provisional 2 px target. The similarity fit reduces error and motivates a later calibrated camera-rotation comparison. The present points do not distinguish changing camera orientation from depth-dependent motion. The ALPACA comparison uses the existing Phase 6 landmarks and five added enclosure measurements from the same two independent exposures. Translation recovered (+47.97, +17.20) px against the Phase 6 control (+48, +16) px, and the disconnected A/C control retained two groups. The four existing foreground regressions passed.

#### Replay the initial measurements

The ignored `output/application-tests/phase7a/` folder contains local images, point selections, the discovery guide, the measurement scripts and the per-point data. The discovery probe used an isolated OpenCV wheel in this folder. The two replay scripts use the existing locked environment.

```powershell
$Phase7Evidence = 'output/application-tests/phase7a'
$Phase7Replay = New-Item -ItemType Directory -Path (
    'output/application-tests/phase7a-replay-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
)
foreach ($name in @(
    'patch-candidates.json', 'measure_landmarks_extended.py', 'compare_landmarks_extended.py'
)) {
    Copy-Item -LiteralPath (Join-Path $Phase7Evidence $name) -Destination $Phase7Replay.FullName
}
$env:OPENBLAS_NUM_THREADS = '1'
.venv/Scripts/python.exe (Join-Path $Phase7Replay.FullName 'measure_landmarks_extended.py')
.venv/Scripts/python.exe (Join-Path $Phase7Replay.FullName 'compare_landmarks_extended.py')
```

The two JSON reports repeated byte-for-byte in a fresh run folder. `landmark-comparison-checked.json` contains both mask checks and forward and inverse error vectors. The follow-up below records the other measured PA4 overlaps and the independent reference captures. [Phase 6 handoff](phase-6.md#handoff-to-phase-7a)

### Frozen 7A references

For PA4-02/03, only one of ten independently selected structures passed the patch quality and repeatability checks. Neither mask revision supplies joint ground support at that point. For PA4-05/06, seven of ten passed, with 0.46 px P95 disagreement between measurements. Four had four ground-labeled bilinear neighbors in both original masks. Three kept that support under the reduced masks. The original masks supplied only two fitting points. The visible-terrain fit used four points spanning 133 × 597 source px and three held-out points. The two measured PA4 fits use points on shared vegetation. Available landmarks leave the depth and camera-orientation effects unresolved.

| Reference | Fit / held-out points | Translation held-out P95 forward / reverse | Similarity held-out P95 forward / reverse |
| --- | ---: | ---: | ---: |
| PA4-05/06 visible terrain | 4 / 3 | 65.82 / 65.82 px | 42.48 / 41.05 px |
| Oxford Boat 1/2 | 10 / 8 | 64.01 / 64.01 px | 1.02 / 1.16 px |
| La Silla nightscape 300/600 | 6 / 7 | 0.94 / 0.94 px | 0.75 / 0.75 px |

- **Oxford Boat** The archive documents separate captures at different optical zoom settings. The first two Boat images provide the 7B positive similarity case. The fit recovered scale 0.88191 and rotation −14.01° from image 1 to image 2. Patch repeatability was 0.27 px P95. The independently published homography agreed with the local measures within 1.17 px P95. The existing translation aligner returned two disconnected groups. [Oxford VGG data and paper](https://www.robots.ox.ac.uk/~vgg/research/affine/) · [Acquisition description](https://thor.robots.ox.ac.uk/datasets/affine/DataREADME)
- **La Silla** Frame indices 300 and 600 of the published 1280 × 720 HD video decode at 12 and 24 seconds, with differently lit terrain and different visible star positions. The saved project masks exclude the telescope skyline from the ground fit. Patch repeatability was 0.49 px P95 and the existing aligner returned zero shift at a 0.962 correlation peak. The fixed-viewpoint case is an independent mixed-scene holdout for 7C and 7F. Its video-raster coordinates and decoded values are for geometric checks. Credit ESO/José Francisco Salgado (josefrancisco.org). [ESO source and credit](https://www.eso.org/public/videos/lasillatimelapsegeneralview/) · [ESO use terms](https://www.eso.org/public/copyright/)
- **Middlebury Adirondack** The calibrated rectified views have a 176.252 mm camera baseline. Measured ground shifts group around −170.64 px at 1.93 m and −48.33 px at 2.85 m. The measurements agreed with the archive disparity to 1.03 px P95. A similarity fit to farther points had 142.72 px near-region held-out P95. The current aligner returned two groups after a thumbnail ambiguity rejection. This is the changed-viewpoint negative control for a single global pose. [Adirondack data](https://vision.middlebury.edu/stereo/data/scenes2014/datasets/Adirondack-perfect/) · [Scharstein et al., GCPR 2014](https://www.cs.middlebury.edu/~schar/papers/datasets-gcpr2014.pdf)

#### PASSTA camera-rotation experiment

The Lunch Room captures `img01.jpg`, `img03.jpg`, and `img05.jpg` have common room features at different distances. The calibration uses a landscape sensor grid and the archive JPEGs are stored in portrait orientation. The 90° clockwise sensor-to-raster mapping `(x, y) → (3647 - y, x)` had lower training and held-out errors on every pair than the counterclockwise mapping. Both fits applied the same published Brown distortion coefficients and held out whole structures. Twenty shared landmarks provided redundant overlap, with 0.90 px P95 difference between the direct and two-edge measurements. Independently fitted camera rotations closed the loop to 0.0041°. The existing translation aligner rejected the three pairs as ambiguous. [PASSTA capture method](https://isy.gitlab-pages.liu.se/cvl/en/datasets/passta/) · [CC BY 4.0 archive](https://zenodo.org/records/19663081)

| Frame pair | Fit / held-out points | Fitted angle | Clockwise calibration P95 forward / reverse | Counterclockwise calibration P95 forward / reverse |
| --- | ---: | ---: | ---: | ---: |
| 01–03 | 13 / 9 | 10.25° | 4.09 / 4.09 px | 19.45 / 17.54 px |
| 03–05 | 12 / 8 | 9.97° | 3.68 / 3.22 px | 19.68 / 17.13 px |
| 01–05 | 12 / 8 | 20.22° | 6.90 / 5.91 px | 38.37 / 30.64 px |

Carry the clockwise mapping into 7D as the measured calibration convention for these files. The fixed-intrinsics rotation comparison exceeds the 2 px target. The independent roll/zoom case supports the simpler similarity implementation in 7B.

#### Acceptance and replay

Freeze the selected source pixels, masked support, and fit/held-out assignments before 7B. Keep the 2 px bidirectional P95 target for the positive controls and require model improvement beyond measured repeatability. Preserve ALPACA's existing 1.5 px per-axis translation bound and zero accepted links for the disjoint ALPACA pair. Require an explicit unsupported result when a single pose fails the held-out depth groups. The current PA4 project remains six singleton groups. Neither of the measured PA4 visible-terrain fits meets the 2 px target.

Keep all captures and numeric artifacts local. `output/application-tests/phase7a/reference-lock.json` records the report and script hashes and the source fixtures in ignored `data/application-tests/phase7a/`. The public image conversions preserve decoded sample values and pixel centers. The local scripts and reports retain the landmark coordinates, mask revisions, per-point quality checks and model residuals. Use the isolated OpenCV 4.13.0.92 probe for PASSTA and video decoding.

| Local script | Reproduced report |
| --- | --- |
| `measure_pa4_followup.py` | `pa4-followup.json` |
| `measure_passta_orientation.py` | `passta-orientation.json` |
| `measure_depth_control.py` | `middlebury-depth.json` |
| `measure_lasilla_nightscape.py` | `lasilla-nightscape.json` |
| `measure_current_aligner_controls.py` | `indoor-control-baselines.json` |
| `measure_oxford_boat.py` | `oxford-boat.json` |

From the checkout root, replay with `OPENBLAS_NUM_THREADS=1` and `.venv/Scripts/python.exe -X utf8 output/application-tests/phase7a/<script>`. Save stdout to a separate report and compare its SHA-256 with the recorded local run. All six reports reproduced byte-for-byte under this environment. The four existing foreground integration tests passed.

## 7B Fit and Review Manual Control Points

1. Add a Qt-free fit that consumes panel identifiers and source-pixel control-point pairs from the real case inventory. Validate finite in-frame positions against each panel's active ground mask and validity. Track user-selected points and rejected points separately from the fitted pose. Retain the existing correlation path for compatible translations.
2. Solve the simplest supported transform first. Initialize the panel graph from reliable pair fits and anchor one panel. Refine all active poses together with robust residuals. For similarity, bound scale and require sufficient point spread. Use the existing graph utilities where their contracts apply. Reject disconnected, ill-conditioned or geometrically inconsistent fits with their measured cause. Compare any optimizer option with the existing SciPy stack, which supplies bounded robust least squares. [SciPy least squares](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html)
3. Return each point's residual and the accepted fit, rejected connections, and supported components. Exercise the manual points through a repeatable headless entry point. Make recalculation atomic so a failed or cancelled trial leaves the previous verified alignment available.

**Acceptance** The real translation and independent local-rotation or scale controls meet the frozen bounds. An underconstrained or conflicting real case returns an actionable rejection. The same manual inputs reproduce the transform and diagnostics within the specified numeric tolerances.

### Run a manual terrain fit

`project fit-foreground` reads a saved project's active ground masks and a versioned JSON file. It reports a candidate pose for each panel in the selected anchor's pixel grid. Add `--output` to save an accepted fit for [foreground rendering](#save-and-render-a-terrain-fit). [Project and headless CLI](guide.md#run-the-headless-cli)

```powershell
astromosaic project fit-foreground scene.astromosaic --points terrain.json --model auto --anchor 1 --json
```

A version 1 document contains a `points` array. This row comes from the ALPACA control file. A fitted connection needs at least three distinct training correspondences.

```json
{
  "schema_version": 1,
  "points": [
    {
      "id": "enclosure-2",
      "panels": [1, 2],
      "left_xy": [515.0, 60.0],
      "right_xy": [467.02396195185656, 43.05510754125703],
      "held_out": false
    }
  ]
}
```

Panel numbers follow the saved project and start at one. Positions use zero-based source pixel centers in `[x, y]` order. Use unique string IDs and use `held_out: true` for independent validation points. The command verifies the referenced source and checks valid ground at the sampled position. The lowest active ground panel is the default anchor. Automatic selection tries translation before similarity. An explicit `--model` runs that model alone.

Pair initialization uses median translation or a bounded, deterministic similarity search. A pair needs at least 75% of its training points within 2 source px in both directions. Similarity requires at least 8 px RMS spread along the narrower dimension of both point sets. The accepted scale range is 0.5 to 2 for a pair and for each pose relative to the anchor. The fit initializes the graph from those edges and robustly refines the panel poses together. Each edge reports the P95 of the larger of the two directional point errors. Held-out points never enter the solve. Each pose applies `scale × rotation × source position + shift`. Positive angles turn clockwise with image Y increasing downward.

A successful JSON report has exit code 0 and includes poses, per-point residuals, rejected links, and groups. Point errors use the input panel order. The residual basis identifies an independent pair fit or the anchored graph fit. A rejected fit returns code 1 and includes available diagnostics. Cancellation returns 130. Without `--output`, the command only reports the fit.

### 7B real-observation results

| Reference | Result | Held-out P95 |
| --- | --- | ---: |
| ALPACA A/B | Translation (+47.97, +17.20) px against the frozen (+48, +16) px control | 1.43 px |
| Oxford Boat 1/2 | Similarity maps image 2 to the anchor at scale 1.13389 and rotation +14.01° | 1.15 px |
| Oxford Boat 1/2/3 | 54 correspondences, three edges, panel 2 fixed | 1.10 px maximum across edges |
| La Silla 300/600 | Translation (+0.07, −0.18) px | 0.94 px |
| Adirondack | Two groups and no accepted pose. The far-point fit failed on held-out depth regions. | 140.32 px |

The Oxford three-image check adds the separately captured `img3.pgm` from the same archive. Independent local patch measurements use the published mappings as search guides. The tests also cover a wrong training correspondence, an inconsistent three-panel cycle, invalid masks, underconstrained input, cancellation, identical retry, and access to the previously saved correlation alignment. The headless test prohibits Qt imports.

The local `output/application-tests/phase7b/` stores version 1 point inputs and their fit reports. Run `prepare_control_cases.py` there from the checkout root to rebuild the two-panel input JSON from the 7A evidence. Run `prepare_boat_three.py` from the checkout root and redirect stdout to `boat-three-points.json` for the redundant graph. Use the project paths recorded in the fit reports. Run the focused verification in the locked environment with `python -m pytest -q tests/integration/test_ground_control_points.py`. All five CLI reports repeated byte-for-byte and the saved project hashes matched. The full suite passed 199 tests. Two opt-in OpenGL checks were skipped. The final targeted replay passed 26 tests with the same OpenGL skips. The reference paths and replay hashes are in the local `verification.json`.

## 7C Generate Terrain Control Points Automatically

1. Build bounded grayscale matching views with `read_thumbnail()` or windowed source reads. Use only valid `FOREGROUND` support. Exclude keypoints close to mask boundaries when their descriptor footprint would mix sky or unclassified cells. Apply any robust contrast scaling to the matching view. Keep exact back-mapping from pixel centers in that view to original pixels.
2. Compare a first SIFT candidate with the current correlation baseline and the manually annotated pairs. Limit features per spatial cell and per panel. Check mutual matches and descriptor ambiguity, then use bounded RANSAC and residual filtering with the model under test. Require spatially distributed inliers, reject duplicate or isolated support, and refine representative correspondences in source-resolution windows where measurable. Record candidate, match and inlier counts, exclusion reasons and source-pixel residuals. [OpenCV SIFT API](https://docs.opencv.org/4.x/d7/d60/classcv_1_1SIFT.html) · [Hugin feature and matching controls](https://hugin.sourceforge.io/docs/manual/Cpfind.html)
3. Compare manual and automatic points with the same global fit and held-out references. Reuse descriptors within a bounded job and record peak process memory and tracked reservations, including native allocations. If ordered overlap hints save time on a larger set, keep a bounded search for missing graph links and exercise unordered input. Expose the manual path for low-texture or unstable overlaps.
4. Evaluate the headless OpenCV wheel as a feature-extraction candidate on the locked Python/NumPy stack. Adopt it only after measured accuracy, runtime, footprint and packaging checks pass. Pin the selected version and review the exact wheel's native contents and notices under Q-005. Use Hugin as an optional local benchmark with authorized real data when a comparable mask and reference can be applied. [OpenCV headless packaging](https://github.com/opencv/opencv-python#installation-and-usage) · [OpenCV licensing](https://opencv.org/license/) · [Distribution tracking](../questions_open_topics.md#q-005---application-licensing-and-distribution-model)

**Acceptance** Candidate matching produces a validated graph on the independent textured positive case within the measured CPU budget. The report explains unavailable connections and records zero accepted links between known disconnected groups. Manual points can recover a verified overlap when the automatic match is too weak. Keep the backend optional until portable verification passes.

### Run the automatic terrain fit

The source CLI can use the optional headless OpenCV SIFT backend. For the Windows replay, install the measured wheel into an ignored output folder and make it available only to the experimental Python process. The example uses the project's locked Poetry environment and the local three-view reference.

~~~powershell
poetry run python -m pip install --no-deps --only-binary=:all: --target output/application-tests/phase7a/probe-deps opencv-python-headless==4.13.0.92
$env:PYTHONPATH = 'output/application-tests/phase7a/probe-deps'
$env:OPENBLAS_NUM_THREADS = '1'
poetry run astromosaic project fit-foreground data/application-tests/phase7a/oxford-affine/foreground-three.astromosaic --automatic --anchor 2 --json
~~~

The local experimental Windows CLI also includes the measured wheel. Use its `astromosaic-cli.exe` in place of `poetry run astromosaic` in the command above. [Local development builds](windows-release.md#verification-status)

Add `--holdout PATH` to score independent correspondences using the [version 1 point format](#run-a-manual-terrain-fit). Each audit row must have `held_out: true`. The matcher reserves a 24-source-pixel neighborhood around every audit observation and checks the refined points against the same exclusion. An audited fit requires an anchored residual for every audit point. Add `--output` to save the accepted pose and the observations used by the fit. [SIFT API](https://docs.opencv.org/4.13.0/d7/d60/classcv_1_1SIFT.html) · [Measured headless wheel](https://pypi.org/project/opencv-python-headless/4.13.0.92/)

The `matching` result adds the backend version, peak working reservation, per-panel support and feature counts, per-pair filtering and patch counts, and the submitted source coordinates. It also reports unavailable pairs when nothing reaches the shared fitter. Use `--progress` to send fit progress to stderr. Use `--points` to fit independent manual correspondences or review and edit the returned coordinates in the manual input format. Point IDs starting with `auto:` identify automatic proposals and are reserved for the matcher in audit files.

The matcher uses fully valid `FOREGROUND` bins and maps each thumbnail center to its exact source-bin center. It guards the rotated descriptor, gradients and blur against masked and exterior cells before computing descriptors. A single SIFT worker extracts up to 512 retained descriptors per panel and 12 per 64 × 64 view cell. The job tries all pairs for 2–16 active panels in any order. A mutual 0.78 ratio test filters ambiguous matches. Bounded similarity hypotheses or a translation median must agree with at least 60% of mutual matches. Each submitted edge passes up to 64 source-patch trials with bidirectional verification, supplies up to 32 correspondences, and retains at least eight spatially distributed inliers across at least four cells per image in the anchored fit. The shared 2 px residual limit continues to apply. [SIFT descriptor implementation](https://github.com/opencv/opencv/blob/4.13.0/modules/features2d/src/sift.simd.hpp)

### 7C real-observation results

The comparison uses the frozen 7A–7B landmarks. P95 is taken over the worse pixel-transfer direction for each held-out correspondence. The three-panel row reports the largest pair P95. The direct column uses the existing masked correlation path and its full-resolution translation.

| Control | Direct correlation | 7B manual P95 | 7C automatic result |
| --- | --- | ---: | --- |
| Oxford Boat 1–2 | Disconnected | 1.15 px | Similarity, 0.47 px. 125 mutual matches, 120 coarse inliers, 32 submitted. |
| Oxford Boat 1–2–3 | Disconnected | 1.10 px | Similarity, 0.97 px maximum. All three edges passed, including with reordered inputs in the regression. |
| La Silla 300–600 | Zero shift, 1.01 px | 0.94 px | Translation, 0.98 px. All 13 mutual matches survived patch refinement. |
| ALPACA A–B | (+48, +16) px, 2.56 px | 1.43 px | Explicit translation rejected at 2.06 px. Model selection returned similarity at 1.96 px with nine submitted points. Its Y offset of +18.14 px exceeds the 1.5 px legacy shift tolerance. Keep the direct translation for the legacy control and the manual fit for the independent landmark tolerance. |
| ALPACA disconnected group | Disconnected | — | Zero cross-group edges. The A/B/C graph kept A–B as its only accepted link. |
| Adirondack | Disconnected | 140.32 px, rejected | Rejected before source patches. Only 64 of 167 mutual matches agreed with one similarity. |
| PA4, original and reduced masks | Six singleton groups for each mask | Visible-terrain P95 above 2 px | All 15 edges rejected in each replay. At most one mutual candidate per pair survived descriptor filtering. |
| PASSTA Lunch Room | Disconnected | Calibrated rotation pilot above 2 px | All three similarity edges rejected. Coherent subsets contained 19–30 of 63–87 mutual matches. Carry the calibrated case into 7D. |

The sparse-support recovery replay kept only small portions of the saved ALPACA ground masks around the existing real measurements. The automatic fit reported insufficient features. The manual fit recovered the 1.43 px translation on the same restricted masks. Oxford passed after cancellation, retry and a separate panel reorder. All ten CLI cases repeated their JSON byte-for-byte and retained their project hashes. Qt imports were blocked during the CLI replays.

The Windows 11 x64 development host used an Intel Core i5-14600K, one SIFT worker and one OpenBLAS thread. Measurements are fresh-process and same-process repeat times with the normal Windows file cache. Oxford's three-panel run took 1.04/1.24 s wall time and 0.98/1.19 s CPU time, with a 63.4 MiB tracked reservation and a 188.0 MiB process peak. La Silla took 0.38/0.31 s wall time with a 62.5 MiB reservation and a 184.1 MiB process peak. PA4 took 12.14–13.15 s per replay across the two mask variants, with a 112.1 MiB reservation and a 230.3 MiB maximum process peak. The process peaks include the already loaded runtime and native libraries; PSAPI reported 125–126 MiB resident before the optional backend loaded. The matching reservations include the SIFT image pyramids, scratch space, descriptor cache and fit buffers. They stayed below the respective 64 or 128 MiB job limits.

The Windows wheel was 40,070,414 bytes compressed and 113,745,942 bytes unpacked. It contains a 74,492,416-byte `cv2.pyd`, a 28,578,304-byte FFmpeg DLL, and the OpenCV and third-party notices. The measured wheel SHA-256 is `77a82fe35ddcec0f62c15f2ba8a12ecc2ed4207c17b0902c7a3151ae29f37fb6`. Its portable packaging and corresponding-source review remain under Q-005. Hugin was unavailable on the test host. The locked application dependencies retain their existing versions. [Windows wheel](https://pypi.org/project/opencv-python-headless/4.13.0.92/) · [Distribution review](../questions_open_topics.md#q-005---application-licensing-and-distribution-model)

The ignored `output/application-tests/phase7c/` directory contains `verify_ground_features.py`, `verification.json`, the separate audit files and per-case JSON reports. Run the replay script with the same Poetry Python, `PYTHONPATH` and thread setting as in the [command above](#run-the-automatic-terrain-fit).

## 7D Validate Camera Rotation and Lens Geometry

1. Where 7A shows that the simple model leaves directional errors, use the existing focal-length, pixel-pitch and image-size metadata to initialize rectilinear intrinsics. Preserve distinction between a known calibration and a metadata estimate. Account for crop and pixel-scale changes. Start with calibrated intrinsics held fixed, then estimate a relative rotation from matched unit rays.
2. Anchor the orientation graph. Initialize from reliable edges and optimize all participating camera rotations against source-pixel reprojection residuals. Require finite, well-conditioned transforms and sufficient coverage. Consider a shared focal length or one bounded radial term only if the spatial residuals, grouped lens identity and out-of-fit improvement support that parameter. Freeze the supported field of view and constraints from real observations.
3. Compare translation, similarity and rotation on the exact same landmarks. Report near/far disagreement and spot-check extremal footprints and inverse mapping. For depth-dependent misalignment, report the failing region and prefer a verified masked subset when it meets the same acceptance rules. Keep a planar experiment local to its supported surface and record findings before proposing additional models.

**Acceptance** Promote rotation only when a real rotated or panned case passes the frozen held-out and geometry limits with measurable improvement. Verify loop behavior on the multi-panel control and correct rejection on the depth-change control. Record the supported optics and model limits in the result. If evidence is insufficient, document the unsupported capture geometry and deliver the validated simpler model.

### 7D real-observation results

The replay used the saved `FOREGROUND` masks and the frozen training and held-out landmarks. PASSTA used the supplied Canon EOS 70D calibration, matching the three original JPEGs and their 3648 × 5472 raster dimensions. The archive focal lengths are 2569.31 and 2566.96 px in its landscape sensor coordinates. The replay kept the clockwise mapping and the supplied principal point and Brown coefficients. It initialized each edge from matched unit rays, ranked the fitted edges for initialization, fixed frame 01, and then optimized all poses against forward and reverse source-pixel residuals. The focal and radial trials each varied one quantity shared by the three captures. The focal multiplier was limited to ±2%, and the change in the first radial coefficient to ±0.02. Held-out landmarks stayed outside all solves. [PASSTA acquisition and calibration](https://isy.gitlab-pages.liu.se/cvl/en/datasets/passta/)

| PASSTA frame pair | Translation | Similarity | Fixed calibration rotation | Shared focal adjustment | Shared radial adjustment |
| --- | ---: | ---: | ---: | ---: | ---: |
| 01–03 | 57.90 px | 122.29 px | 4.18 px | 3.19 px | 3.06 px |
| 01–05 | 132.58 px | 230.94 px | 6.90 px | 5.54 px | 4.13 px |
| 03–05 | 95.92 px | 133.62 px | 3.69 px | 2.41 px | 1.61 px |

The table uses the P95 of the larger forward or reverse residual for each held-out landmark. The planar columns show diagnostic least-squares fits on the same training observations. All three rotation variants miss the 2 px requirement on at least one edge. For the best variant, the shared change in the first radial coefficient was +0.00941. The longest edge still had 4.25 px P95 at the near table mat, 3.76 px at the chair and 3.32 px at the wall-mounted art frame. Separate leave-one-training-zone-out checks reached 5.24 px with the radial term and 6.20 px with the focal adjustment. The focal solve hit its lower bound when excluding the skylight. A soft-L1 sensitivity run produced a maximum P95 of 4.16 px with the radial term.

The fixed-calibration poses give relative rotations of 10.25°, 9.97° and 20.22°. Independently fitted edges closed the loop to 0.0041°. Re-anchoring to frame 03 changed the pair residual vectors by at most 0.000001 px. The published full-raster calibration measured 72.02° horizontal, 96.20° vertical and a maximum 107.13° diagonal field in portrait orientation. A 17 × 17 raster grid kept positive Brown Jacobian determinants. The six directed pair checks sampled 128 points per image perimeter and found 55–61 falling inside the target raster for the fixed calibration. Overlapping boundary samples round-tripped within 0.001 px, as did an offset and anisotropic resize of the real landmark coordinates. These checks cover the sampled domain of the measured optics.

**Adirondack depth control.** The calibrated rotation fit used the frozen far landmarks for training. The held-out farther and nearer groups gave 15.70 px and 167.06 px P95, respectively. Similarity reached 6.03 px and 143.11 px on those same groups. Both the global pose and the restricted far subset miss the 2 px bound. The published 176.252 mm baseline and the frozen disparity-supported depth separation remain the independent depth evidence. [Middlebury data and calibration](https://vision.middlebury.edu/stereo/data/scenes2014/datasets/Adirondack-perfect/)

**PA4 metadata estimate.** The source metadata and project overrides resolve to 24 mm focal length and 3.908 µm effective pitch, or 6140.74 px on both axes. The diagnostic used a centered rectilinear model with zero distortion coefficients. Its held-out P95 was 8.34 px for 04–05 and 3.07 px for 05–06, versus 72.11 px and 42.48 px for similarity on the same visible-terrain points. Only two and four quality-checked correspondences respectively had joint ground support in the saved original masks. PA4 retains its six singleton groups. Assess real calibration and mask coverage before adding any of these links.

**Decision.** Carry translation and similarity into 7E. Keep camera rotation and the shared lens adjustments experimental pending a calibrated real capture that meets the frozen limit. The larger PASSTA residuals across several depth regions leave the relative contributions of calibration error and viewpoint shift unresolved. Preserve the PA4 masks and source data while those hypotheses are open.

### Replay the 7D comparison

Run from the project root with the locked Python environment. The default command checks the public PASSTA and Adirondack controls. The optional `--pa4` argument includes the local PA4 metadata probe with its frozen observations. The tool verifies the reference hashes and reports per-point residual vectors, fit and audit statistics, pose loop, pixel-domain checks and gate outcomes. The optional OpenCV probe was used separately to cross-check the NumPy Brown model on the PASSTA raster grid and projected boundaries.

~~~powershell
$env:OPENBLAS_NUM_THREADS = '1'
poetry run python tools/phase7d_rotation_check.py
poetry run python tools/phase7d_rotation_check.py --pa4
~~~

The local full report is stored in ignored `output/application-tests/phase7d/rotation-comparison.json`. Two fresh processes produced identical JSON. [Replay tool](../tools/phase7d_rotation_check.py) · [Real-data regression](../tests/integration/test_phase7d_rotation_check.py)

## 7E Integrate Geometry, Rendering and Persistence

1. Extend the shared foreground geometry to convert between original pixels and the selected ground grid in both directions. Start with the anchor's pixel grid for similarity. For a validated rotation model, choose a ground projection and scale supported by the repeatable capture set. Evaluate a wider cylindrical grid only if the required view exceeds the safe rectilinear domain. Preserve float64 transforms and existing output bounds.
2. In `ForegroundLayer.try_tile()` and `_footprint()`, compose the inverse ground mapping with any existing layer placement and sample original masked pixels in bounded tiles. Use conservative transformed bounds, with full candidate traversal when needed. Compare selected tiles against unpruned sampling. Require finite invertible mappings on the accepted domain, valid coverage and geometry at edges, and cleanup on cancellation. Retain the existing blend for already aligned ground observations. Assess seam or exposure improvements later against accepted geometry and actual overlap.
3. Update `propose_composition()` to map shared horizon points through the ground transform and the independent sky WCS. Keep the user-editable layer placement and score the shared support when proposing it. Check the sky-only WCS, sample values and coverage before and after terrain realignment. Independently reopen the foreground and visual composition and verify contributions where applicable. [Layer renderer](../src/astromosaic/pipeline/layers.py) · [Existing composition design](adr/0015-independent-layer-rendering.md)
4. Save the selected model, point and mask revisions, source references, camera assumptions, anchor, fit status and transform with explicit schema compatibility. Read earlier translation records with their original interpretation. Invalidate derived geometry when relevant inputs change. Keep provisional or rejected fits from replacing the last good project alignment and preserve source hashes. [Project persistence](../src/astromosaic/storage/project.py)

**Acceptance** Source and portable readers reproduce the accepted geometry, independent coverage and applicable WCS. Older saved translations render within their existing bounds. Changed point and mask inputs invalidate the appropriate geometry, and cancelled or failed attempts preserve previous verified state and leave clean destinations for retry.

### Save and render a terrain fit

```powershell
astromosaic project fit-foreground scene.astromosaic --points terrain.json --anchor 2 --output aligned.astromosaic --json
astromosaic project export aligned.astromosaic --layer foreground --output foreground.tiff --json
```

`--output` requires a new project filename. Open that project in the desktop and select **Foreground** to preview or export the saved fit. For mixed scenes, propose or set the composition placement again after changing the terrain geometry. The usual brightness requirements apply at render time.

Project manifest version 7 stores the anchor, model, poses, accepted fit status, provider, source references, and a snapshot of control-point observations. It stores the maximum available held-out P95 across accepted edges. The fit key binds the snapshot to the active ground masks and source fingerprints. To use an updated point file, run the fit again. Both models assume a planar image-space mapping. The solver uses source-pixel landmarks without lens calibration or celestial WCS. Earlier translation records retain their original canvas and schema when saved.

### 7E source results

- **Oxford Boat** The accepted similarity with panel 2 fixed reopened from a version 7 manifest and rendered masked float32 FITS. CFITSIO coverage and samples agreed with an independent original-pixel bilinear comparison. Footprint selection and complete traversal produced identical FITS bytes.
- **ALPACA** CFITSIO reopened the legacy 80,158-sample coverage byte for byte after a version 4 save and reopen. The version 7 landmark translation also reopened and exported. Rejected and cancelled attempts preserved the existing project and a retry produced the intended new project.
- **Paranal** Control points on the two real panorama crops used their known crop offset. Shared-horizon placement and TIFF composition reopened with the expected contribution codes. The sky TIFF bytes, including WCS, samples and coverage, agreed before and after realignment. This is a pipeline control from one panorama. Oxford and ALPACA supply the independent exposure checks.

Run the real replay with `python -m pytest -q tests/integration/test_ground_control_points.py`. The regressions also verify that editing the saved point snapshot or ground mask invalidates the cached pose.

## 7F Ship the Review Workflow and Verify Windows

1. Extend **Align Foreground** with a view of panel links, point overlays and residuals. Let users add, move, disable or remove point pairs and repeat the fit. Show the active model, anchor, missing connections and expected remedy. Keep all matching and optimization in the shared CPU core and run long operations in cancellable background jobs.
2. Repeat the same real positives, PA4 and negative controls through headless checks and native source desktop. Check manual edits, reopen, preview and foreground and composition exports, cancellation, retry and visible diagnostics. Verify sky-only output after edits. Record cold and warm timings, peak memory, panel count, feature and worker caps on Windows 11 x64.
3. Verify portable console and desktop packages built with the Phase 7 changes. Apply the 6E procedure to the new geometry and reuse the legacy translation references. Check CPU and OpenGL preview, independently reopen exports, and record the actual display configuration. Use the shared clean-machine session when both phases ship in the same candidate. Follow the existing clean-machine and distribution requirements for the intended public binaries. [Windows packaging](windows-release.md) · [Phase 6E Windows checks](phase-6.md#6e-verify-native-lifecycle-and-windows-packages)

**Phase exit** At least one real capture sequence with verified shared terrain that the old translation approach could not align meets its frozen bounds with the new workflow. The independent nightscape, legacy translation and real rejection controls pass. PA4 has recorded outcomes by verified overlap, with unsupported panels identified. Publish reproducible evidence summaries and record remaining geometry limits and release checks in the progress log.
