# ADR-0018 - Select Tile Candidates with Conservative Panel Footprints

- **Date:** 2026-11-18
- **Status:** Accepted for Phase 4B.

## Context

The full-size Windows reference spent most FITS crop rendering time mapping coordinates for twelve panels per tile, with four source reads per tile. Bound candidate selection before the shared WCS sampler. [Phase 4B baseline](../phase-4b.md#windows-baseline-results)

## Decision

For undistorted ICRS TAN panels, project the padded source rectangle corners to the cropped output grid and apply the fitted pixel shift. Each coordinate between tangent planes is a ratio of affine functions. If the rectangle stays in the visible hemisphere, the projected extrema occur at its corners. Use an 80° guard in both projection directions, guard extreme pixel scales and coordinates, and expand each output bound by one pixel for numerical tolerance.

Inspect the serialized WCS for ordinary TAN axes and supported cards. WCSLIB can expose TAN internally while retaining a TPV polynomial. On TAN grids, SIP, TPV, alternate frames, unrecognized WCS cards and unstable corner projections use the full mapping path. Foreground bounds use the saved panel translation, the foreground canvas and the composition similarity transform. [ADR-0024](0024-conservative-zea-footprints.md) covers the separate ZEA bound.

Compare each bound with the output tile's pixel edges, including preview scale and composition origin. Traverse candidates in project order. The selected panels still use full geometry, round-trip validation, validity masks, bilinear sampling and linear blending. Each job caches the bounds it can prove and charges up to 256 bytes per panel per layer against its render budget. Very tight budgets use the full panel list. The synchronous renderer keeps one active tile and no queued tiles.

## Consequences

Exports can be compared byte for byte against the unfiltered reference. The `rejected_coordinates` report counts failed mapping or clip checks on evaluated candidates, so removing a provably disjoint candidate can reduce the count. Coverage and layer masks describe the published pixels. [Project report contract](../phase-4a.md#result-contract) · [Phase 4B measurements](../phase-4b.md)
