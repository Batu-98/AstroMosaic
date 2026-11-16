# ADR-0015 - Align and render the two layers independently

- **Date:** 2026-11-16
- **Status:** Accepted for Phase 3E.

Fit foreground translations in source pixels from masked terrestrial texture on a common scale and orientation. Anchor the first participating panel. Check weak and ambiguous overlaps before solving the graph. Crop the foreground canvas to the union of the transformed mask bounds. Persist the source and mask selection identity, alignment, and match evidence with the project.

Use the cropped sky output grid as the composition coordinate system. Propose a foreground similarity transform from well-supported horizon samples in a shared panel. Save the editable placement, seam row, overlap percentage, and reversible sky crop in the manifest. Sample each layer directly from its original panels through the composed transforms. Feather where both layers have valid support and keep each layer independently exportable.

The composition embeds its binary coverage and layer contributions in one atomic file. FITS uses `COVERAGE` and `LAYERS` image extensions. Version 2 of the AstroMosaic TIFF description uses two byte SubIFDs in that order. The sky export retains its celestial WCS. A visual composition carries the sky grid and both layers' processing history as provenance.

[Desktop workflow and verification](../phase-3e.md)
