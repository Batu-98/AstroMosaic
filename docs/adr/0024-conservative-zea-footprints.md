# ADR-0024 - Select ZEA tiles with conservative spherical bounds

- **Date** 2026-11-19
- **Status** Accepted for Phase 6D after comparison with all-panel rendering.

## Context

The fixed PA4 ZEA export spends much of its time mapping every output tile into all fifteen source panels. ZEA can curve a projected detector edge away from its endpoints. PA4 also has forward SIP distortion. [ZEA grid decision](0021-zea-sky-grid.md) · [PA4 measurements](../phase-6.md#local-zea-geometry-and-performance-results)

## Decision

Use a conservative bound for ordinary ICRS TAN or TAN-SIP inputs in a plain ICRS ZEA grid. Enlarge the detector's half-pixel rectangle by the source snap tolerance and bound forward SIP displacement with the sum of absolute polynomial terms over that rectangle. Split the resulting rectangle into a four-by-four grid in the undistorted TAN pixel plane.

For each cell, the greatest plane distance from its center to a corner bounds its angular radius on the sky. Normalizing the gnomonic ray has a derivative with norm at most one. For ZEA at angular distance `d` from its pole, the greatest local scale equals `1 / cos(d / 2)`. Bound each cell's projected radius using that scale at the cell center's separation plus the angular radius. The inverse linear output transform gives a pixel radius. Enclose all projected cells, apply the saved shift and pad the rectangle by one output pixel for the round-trip and numerical tolerances. [FITS projection equations](https://arxiv.org/abs/astro-ph/0207413)

Use the full panel traversal when the bound is unavailable. The ZEA selector uses standard FITS linear cards, degree units, forward SIP through order five, a minimum output singular scale of `1e-8` degrees per pixel, and cell bounds strictly within 150° of the output pole. It limits pixel coordinates, SIP displacements and shifts to the existing `2**32` bound and source linear matrix entries to 150 degrees per pixel. Table distortions, unsupported frames or WCS cards, and tight working budgets use the full path. On TAN targets, the plain TAN bounds use their corner proof. [Tile candidate contract](0018-conservative-panel-footprints.md)

## Consequences

Candidates retain the existing project order, inverse mapping and round-trip checks, sampling, and blending. Preview scale, composition origin, and cropped output WCS participate in the same candidate check. Each accepted bound reserves 256 bytes in the existing render budget. The reported rejected coordinate count covers attempted panel-coordinate mappings. Published coverage counts output pixels.
