# ADR-0023 - Fit foreground geometry from terrain control points

- **Date** 2026-11-19
- **Status** Accepted for Phase 7E translation and similarity. Camera rotation remains experimental.

## Context

The Phase 3E matcher fits masked X/Y translations on a common pixel scale and orientation. The six-panel PA4 ground replay rejected all 15 pairs at the thumbnail correlation gate. An independently marked overlap is needed to distinguish weak common terrain from geometry that a translation cannot represent. [Current foreground design](0015-independent-layer-rendering.md) · [PA4 measurements](../application-test-findings.md#foreground-alignment-and-mask-feedback)

## Proposed Decision

Use source-pixel control points on valid terrain and fit an anchored graph with robust reprojection residuals. Accept manually marked points through the same fit used for automatic matches. Compare translation and similarity first. Use a lens-aware camera-rotation model for real near-fixed-viewpoint sequences where calibrated optics and held-out measurements support it. Diagnose depth-dependent errors and restrict any planar experiment to a verified planar region.

Keep foreground geometry in the shared CPU processing core. Compose the selected transform with layer placement during tiled sampling from the original source. Use the existing independent celestial WCS branch for sky work. Retain compatibility with saved translation transforms and record the model, originating inputs and fit evidence for new ones.

## Consequences

The plan adds a point review workflow, bounded automatic matching, transform-aware tile bounds, and a compatibility check for saved foreground geometry. New models and dependencies require measured accuracy, memory and Windows packaging evidence. Acceptance uses independently captured real data and preserves explicit rejection of unsupported overlaps. [Detailed Phase 7 plan](../phase-7.md)

The 7C source CLI evaluates headless OpenCV SIFT as an optional point provider. Its matched observations and independently marked points use the same anchored fit. Oxford and La Silla passed the fit checks, and the manual path recovered sparse ALPACA ground support. Portable verification and license review govern adoption of the measured wheel. [7C measurements](../phase-7.md#7c-real-observation-results)

The 7D evaluation compared rotation with fixed calibration and with separate shared focal and radial candidates. The best PASSTA candidate reached 4.13 px P95 against the 2 px limit, and the Adirondack depth control rejected a global pose. Phase 7E integrates translation and similarity. Camera rotation remains an offline measurement until calibrated observations pass the held-out and geometry gates. [7D measurements](../phase-7.md#7d-real-observation-results)

The desktop keeps edits in a draft while one background job reads bounded ground views or fits the graph. Applying the result replaces the project alignment after acceptance. Point observations remain tied to their original source fingerprints; a changed mask invalidates the pose and still allows review of the observations for the same ground panels. Version 8 retains disabled observations alongside enabled fit or audit points. [Desktop review](../phase-7.md#review-and-edit-control-points-in-the-desktop)
