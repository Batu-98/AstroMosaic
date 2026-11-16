# ADR-0013 - Share the cropped TAN grid between preview and export

- **Date:** 2026-11-16
- **Status:** Accepted for Phase 3C.

## Decision

Prepare the same panel sources, WCS, masks, and optional relative corrections for both jobs. Sample a preview raster at cell centers on the cropped export grid and pass the original output geometry into the tile sampler. An image that fits within the preview limit uses one sample per output pixel. Larger images use a bounded screen proxy. Registration shifts stay in export pixels at every preview resolution.

Build and normalize the preview on the desktop job thread. The viewport owns the immutable display buffer. Both display paths use a common fit, pan, and zoom mapping. OpenGL applies the midtone transfer to a float texture with coverage-aware mip levels. The CPU surface paints a cached raster and recomputes its display values when the stretch changes. Export samples the original image data with the project settings.

[Desktop workflow and acceptance evidence](../phase-3c.md)
