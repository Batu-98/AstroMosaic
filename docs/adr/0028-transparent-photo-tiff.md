# ADR-0028 Transparent photo TIFF and preserved tone

- **Date** 2026-11-22
- **Status** Accepted for the Phase 8B follow-up.

## Context

The owner reopened a beta 12 photo mosaic as opaque RGB in Photoshop. The preview stretch lifted the sky background and clipped highlights, and uncovered canvas appeared black. The photo workflow needs a natural default tone and transparent canvas for editing.

## Decision

Default to **Preserve Tone** in the desktop and CLI. Keep **Use Preview Tone** available. The existing CLI `--midtones` shorthand selects preview tone.

Write a contiguous UInt16 RGBA photo TIFF with TIFF `ExtraSamples` set to associated alpha. Map the render validity to 65,535 for covered pixels and 0 for uncovered pixels. Binary alpha preserves the covered RGB codes and requires zero RGB at transparent positions. Store coverage once in the alpha sample. Use the shared tile renderer, embedded sRGB profile, WCS, and atomic writer. [TIFF 6.0 alpha specification](https://image-js.github.io/tiff/media/TIFF6.pdf#page=79)

## Consequences

The photo payload is eight bytes per pixel. The reader accepts the tagged binary alpha photo format and the earlier RGB photo format with a coverage SubIFD. Verify the 16-bit RGB codes, alpha, coverage including black, WCS, profile, Photoshop opening and cancellation on the supported workflow. [Phase 8B follow-up](../phase-8.md#8b-photo-tone-and-transparency-follow-up)
