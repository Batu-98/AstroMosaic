# ADR-0029 Photo matrix color and overlap matching

- **Date** 2026-11-22
- **Status** Accepted for the first Phase 8C implementation.

## Decision

Resolve photo color from a panel assignment, then the project assignment, then the embedded ICC or supported EXIF/XMP declaration. An explicit assumption can qualify an untagged RGB UInt16 TIFF. Save assigned ICC files as local relative references with SHA-256 in manifest version 10. Convert qualified RGB v2/v4 matrix profiles through Little CMS into float32 linear sRGB using relative colorimetric intent with black point compensation off. Keep the canonical analytic transfer for recognized sRGB. [ICC matrix profiles](https://www.color.org/v4spec/) · [EXIF/XMP color space](https://cipa.jp/std/documents/e/DC-X010-2017.pdf) · [Frozen controls](../phase-8.md#8c-frozen-color-and-exposure-references)

Apply manual linked EV or eligible camera metadata gain before measuring brightness. Sample bounded, spatially split blocks on the full resolved sky grid. Test a robust pedestal offset and the linked affine Standard fit on reserved blocks. Select an accepted result based on its held-out RGB residual and retain an identity correction where support is insufficient. Resolve a deterministic reference from the selected band and allow connections through accepted overlaps. Reuse one compact report keyed by the settings, grid, source and mask fingerprints, geometry, effective profile and exposure metadata.

## Consequences

Preview, detail and photo export share the working colors and fitting policy. Cropping uses the full-grid fit. The Command Panel, JSON export result and photo TIFF history expose effective choices and fallback reasons. The Windows bundles include the Little CMS extension from the locked imagecodecs wheel. [Photo workflow](../phase-8.md#8c-photo-color-and-exposure-workflow) · [Distribution tracking](../../questions_open_topics.md#q-005---application-licensing-and-distribution-model)
