# ADR-0030 Independent stellar support for photo gains

- **Date** 2026-11-22
- **Status** Accepted for Standard photo brightness matching.

## Decision

Check Standard gain candidates that change the relative scale by more than a factor of 1.01 in either direction after they pass the existing held-out RGB check. Match isolated stars through the shared WCS and measure the original linear working RGB with a fixed aperture and local annulus. Exclude the detector support used for the pair's sky fit and RGB validation, including interpolation and mask halos. Require eight matches in at least three spatial cells and comparable detector pixel scales. Apply the same block-level stellar criteria as the offline comparison. Include the current reference and moving exposure gains in the aperture comparison.

When the stellar check rejects the proposal or lacks support, use the independently qualified pedestal offset or identity. Try other connected peers under the same policy. Keep the first vetoed gain and its evidence even when a different peer supplies the final correction. Workers check cancellation during the stellar scan and use a bounded reservation with no image-sized buffer.

## Consequences

Preview, detail and photo export use the same correction and diagnostics. The project keeps its requested Standard setting and derives the effective correction each time its inputs change. The evidence appears in the export JSON, Command Panel and photo TIFF history. [Phase 8D reference and production checks](../phase-8d.md#standard-photo-gain-integration) · [Photo color and overlap matching](0029-photo-matrix-color-and-overlap-fit.md)
