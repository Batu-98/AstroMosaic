# ADR-0027 Adaptive sky preview and interactive crop

- **Date** 2026-11-22
- **Status** Accepted for the Phase 8B follow-up.

## Decision

Keep automatic preview framing separate from the saved render grid. Let users lock the center, projection, size, scale and crop independently. Preserve the entered rotation and offer a footprint-based recommendation. Editing a crop on the canvas opens the full effective grid. Applying a crop adopts that grid and rectangle together so later framing cannot move the selected area. Resetting the crop in the editor restores the coverage-based recommendation. The source coordinate frame and masks remain the inputs to each render.

Render the overview progressively with bounded area subsampling in linear light. Use a display-sized raster with a fixed sampling budget. At close zoom, sample a bounded visible rectangle at full output resolution on a background worker. Share tone statistics across the overview and detail. The photo tone reference retains the fixed 512-edge sample convention so export is reproducible across window sizes and between the desktop and CLI. [Shared sky geometry](0013-shared-preview-grid.md) · [Photo export contract](../phase-8.md#8a-frozen-photo-export-contract)

## Verification

Check partial locks, manifest reopen, the crop overlay and keyboard-accessible apply/reset/cancel actions. Compare full-resolution detail and cropped WCS with the export grid. Verify area samples against an independent validity-weighted reference. Repeat the real owner TIFF preview, visible detail, crop export and cancellation on native CPU and OpenGL and in the portable Windows runtime. The linked tone and scientific controls retain their existing semantics.
