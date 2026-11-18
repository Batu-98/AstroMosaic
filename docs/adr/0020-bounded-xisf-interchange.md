# ADR-0020 - Use bounded XISF attachments for interchange

- **Date:** 2026-11-18
- **Status:** Accepted for Phase 5A.

## Context

XISF provides an additional interchange workflow for linear astronomical images. The renderer requires bounded random access to source windows and atomic output publication. FITS-compatible metadata already provides the geometry and calibration conventions used by the core.

## Decision

Implement the monolithic XISF attachment subset using the existing NumPy and Astropy stack. Bound XML metadata and read raw row fragments within the tile reservation. Interpret FITS keywords as metadata for the stored grid, with sample type and scaling determined by the XISF raster.

Write little-endian Float32 samples and named UInt8 coverage and contribution images to aligned attachments in the same file. Use the existing tile writer and atomic publication path. Set the declared floating-point range from the rendered samples, including the conventional zero-to-one range. Retain the shared FITS-compatible WCS and calibration metadata.

## Consequences

Projects can use the same source fingerprints, masks, and render settings with XISF. External readers can read the science and mask images as standard image blocks. Compressed input and native astrometry need separate fixtures and resource and geometry contracts. [Phase 5A](../phase-5a.md)
