# ADR-0026 Configurable Color Photometry and Optics

- **Date** 2026-11-21
- **Status** Accepted for the 8A export intent and initial sRGB contract. Later correction methods remain candidates.

## Context

Beta 7 supports visual previews of recognized sRGB TIFFs and a calibrated linear scientific export. A complete photo workflow needs a full-resolution export with a defined color profile. Panel matching also needs configurable exposure, geometry and illumination corrections with different inputs and failure conditions. [Current sky workflow](../phase-3c.md#desktop-workflow)

## Decision

Select the initial output intent per export. The photo path uses the shared CPU renderer, applies a fixed or preserved tone, and writes tagged sRGB. The scientific path uses qualified linear samples and the existing surface-brightness contract. Persist independently selectable processing methods with the project as those methods are qualified. [8A photo contract](../phase-8.md#8a-frozen-photo-export-contract) · [Surface brightness reference](0002-surface-brightness-reference.md)

Bind every geometric solution to a specific source coordinate frame and compose it with the source mapping for tiled reads. Bind fitted brightness and optics records to their data, profiles, masks and method settings. Keep a single effective illumination correction for each panel. Log selected methods and support, including the reason for a simpler eligible result when automatic fitting is used.

## Consequences

The first implementation focuses on known sRGB photo export. Additional ICC, normalization and optics choices require independent numerical checks, real reference data and Windows delivery evidence. The settings must preserve earlier project behavior and support both live and unattended use. [Detailed method catalog and delivery gates](../phase-8.md)
