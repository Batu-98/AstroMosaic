# ADR-0006: Dual first-class FITS and TIFF workflows

- **Date:** 2026-11-15
- **Status:** Accepted by the project owner (amends ADR-0004).

## Decision

Treat both FITS and TIFF as primary, first-class image workflows throughout the AstroMosaic architecture, rather than treating TIFF as primary and FITS solely as a numerical stepping stone.

1. **FITS Workflow:** First-class scientific support for calibrated, linear monochrome and multichannel FITS panels, native WCS headers, 32-bit floating point precision, explicit validity/coverage extensions, and standards-compliant FITS export.
2. **TIFF Workflow:** First-class support for linear monochrome and RGB TIFF panels (16-bit integer and 32-bit floating point), preserving sample values without arbitrary clipping, with external WCS and coverage sidecars or embedded tags.
3. **Pipeline and Desktop UI:** Both formats must be first-class options across headless CLI jobs, project manifests, responsive viewport previews, registration, background modeling, and mosaic export.
4. **Benchmarks and Limits:** The representative Windows workload targets 12 panels at 6000 × 4000 pixels in both FITS and TIFF formats (including mono and RGB cases).
5. **Camera RAW:** Remains deferred as an import-only feature under [Q-009](../../questions_open_topics.md).

The [active plan](../../astro_mosaic_python_first_architecture_en.md) (revision 3.4) reflects these updated product and format boundaries.
