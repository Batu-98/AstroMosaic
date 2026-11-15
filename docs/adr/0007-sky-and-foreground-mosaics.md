# ADR-0007: Stitch Sky and Foreground Separately

- **Date:** 2026-11-15
- **Status:** Accepted as a product requirement. Detector, segmentation, and registration backends remain open.

## Decision

Support images with sky and terrestrial foreground in both first-class input formats. Run a quick foreground check on thumbnails and allow manual tag overrides. Use a separate local job to propose an editable sky mask for tagged images. Store masks in source coordinates, with validity and content selection tracked independently.

Apply celestial WCS, plate solving, and astronomical registration to the selected sky. Stitch the foreground by matching terrestrial features in image space. Share compatible tile rendering and blending code. Keep both stitched layers available as separate outputs.

Compose the two layers with a placement proposal derived from a shared mixed panel when available. Let the user adjust the placement, seam overlap, and sky-edge crop without altering the stitched sky layer. Keep uncovered regions explicit and keep the scientific sky export separate from the visual composition. Local generative fill may be evaluated later for uncovered visual seam gaps, with a separate synthetic-pixel mask if implemented.

## Delivery

Phase 2 verifies masked sky processing using supplied masks. Phase 3 delivers detection, mask editing, foreground stitching, and composition controls. Phase 4 checks the mixed workflow at the project's 12-panel scale. [Architecture and acceptance gates](../../astro_mosaic_python_first_architecture_en.md#67-mixed-sky-and-foreground-panels)

Q-010 tracks detection, seams, and validation fixtures. Q-011 tracks the deferred fill option. [Topic register](../../questions_open_topics.md)
