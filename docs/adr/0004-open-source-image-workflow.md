# ADR-0004: Open-source distribution and the TIFF-first workflow

- **Date:** 2026-11-15
- **Status:** Accepted for Windows product scope.

## Decision

Distribute AstroMosaic as open source and use open-source libraries, codecs, and solver executables for supported workflows. Track the exact application license, dependency notices, and data redistribution terms in [Q-005](../../questions_open_topics.md).

Make TIFF the main user workflow and retain the two-panel FITS job as the numerical reference. Verify linear TIFF interoperability before desktop workflow acceptance. Benchmark 12 TIFF panels at 6000 × 4000 including RGB on Windows. Defer camera RAW. If requested later, scope it to import with tested camera coverage and an open-source decode path. [Q-009](../../questions_open_topics.md) records the revisit trigger.

The [active plan](../../astro_mosaic_python_first_architecture_en.md) defines the revised milestone gates.
