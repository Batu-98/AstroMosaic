# ADR-0008: Sample Bounded Source Windows for FITS Mosaics

- **Date:** 2026-11-15
- **Status:** Accepted for the Phase 1 FITS reference.

## Decision

Use `reproject_interp` as the small-array numerical reference. Its output block and output array options bound output processing. The interpolation API still takes a source array and does not provide a window reader or per-sample SIP nonconvergence flags. Tiling a full-source invocation would retain the source storage or require staging it first. [Reproject performance guide](https://docs.astropy.org/projects/reproject/en/stable/performance.html)

Use the plan's bounded mapper for rendering. Invert the full source WCS with Astropy, discard failed round trips, and derive a source window from the actual output samples. Include all bilinear taps in the window. Use SciPy for interpolation with explicit validity support, and split the output tile if the combined reservation exceeds the configured budget. Write each finished tile directly to a temporary FITS file.

## Validation

Compare finite samples with the small-array `reproject_interp` reference and separately check the exact two-panel truth, mask behavior, and SIP crop/rotation against analytic expectations. [Phase 1 fixtures and evidence](../phase-1.md)
