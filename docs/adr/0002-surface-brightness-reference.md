# ADR-0002: Use Surface-Brightness Semantics for the Reference Reprojection

- **Date:** 2026-11-15
- **Status:** Accepted for the Phase 1 reference design.
- **Basis:** Section 6.5 of the [active architecture](../../astro_mosaic_python_first_architecture_en.md) and the analytic scale-change fixture in [Phase 0 evidence](../phase-0.md#numerical-contracts-and-fixtures).

## Decision

For the initial reprojection, sample values declared to represent surface brightness, such as `MJy/sr`, and preserve their physical unit. A uniform field retains its brightness when the output pixel scale changes. When evaluating integrated aperture flux on the output, multiply each brightness sample by its own output pixel solid angle before summing.

The FITS reader retains the source `BUNIT` label and applies `BSCALE` and `BZERO` on read. An unknown or ambiguous unit remains available for inspection. Reprojection in this convention requires a known surface-brightness unit or a recorded declaration of the intended semantics. Integrated-flux-per-pixel support requires a separate area-aware conversion and validation across projections.

## Validation and Consequences

The compatibility fixture reprojects a uniform field and an isolated, well-sampled Gaussian from 2 to 1 arcseconds per pixel. It checks field brightness to `1e-10` and compares the solid-angle-weighted sum with analytic flux to 1%. Phase 1 must check the implementation against these tests and verify its own two-panel export, including crop, rotation, units, and coverage. Registration and photometry tolerances for real panels depend on their own fixtures.
