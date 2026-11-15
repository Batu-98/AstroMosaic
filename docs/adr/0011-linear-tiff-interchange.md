# ADR-0011 - Store TIFF celestial WCS and coverage in one file

- **Date:** 2026-11-15
- **Status:** Accepted for Phase 3A interoperability under [ADR-0006](0006-dual-fits-and-tiff-workflow.md).

## Decision

Read linear 16-bit integer and float32 TIFF samples at their stored numerical scale. Use one spatial validity mask for mono and RGB. For RGB, all three channels need valid samples and share the same reprojection and blend weights. Write little-endian float32 mosaics with conventional mono or interleaved RGB tags.

Store newline-separated FITS header cards after the version line `AstroMosaic TIFF 1` in the primary TIFF `ImageDescription`. Include fresh output celestial WCS, common filter and units when available, and processing history. Store binary coverage in the primary image's single byte grayscale SubIFD. Publish both rasters and their metadata in one atomic file operation.

Ordinary linear TIFF imports can be inspected without WCS and solved offline. A source-bound JSON sidecar remains available for a solved input. TIFF masks and WCS use the same top-left zero-based pixel convention as the engine.

See the [Phase 3A interoperability contract](../phase-3a.md) for the supported layouts and acceptance fixtures.
