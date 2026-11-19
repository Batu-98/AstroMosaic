# ADR-0021 - Use ZEA for the first additional sky grid

- **Date:** 2026-11-18
- **Status:** Accepted for Phase 5B.

## Context

Wide mosaics benefit from an equal-area projection with an arbitrary sky reference position. TAN remains the established default. Projection selection affects sky sampling, exported WCS, and the fit between the sky and foreground grids. [FITS WCS projection definition](https://www.aanda.org/articles/aa/pdf/2002/45/aah3860.pdf)

## Decision

Build TAN and ZEA output grids with the same Astropy/WCSLIB adapter. Use the selected WCS for both preview and export and keep the TAN corner-footprint optimization for geometries where its proof applies. Reject the non-unique antipode and its numerical neighborhood in ZEA forward and inverse transforms.

Store the explicit ZEA choice in project manifest version 5 so an older reader fails with a version error. Use version 4 for TAN and interpret earlier manifests as TAN. Let the desktop clear the composition placement when the user selects a different projection. The independent foreground fit remains usable when establishing the new placement.

## Consequences

Sky FITS, TIFF and XISF carry the selected FITS WCS projection. Composition contributions and geometric support remain independently testable. [ADR-0024](0024-conservative-zea-footprints.md) records the later conservative bound for curved ZEA panel footprints.
