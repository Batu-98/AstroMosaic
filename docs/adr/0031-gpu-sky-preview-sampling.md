# ADR-0031 GPU sampling for desktop sky preview

- **Date** 2026-11-26
- **Status** Accepted for the local Windows desktop.

## Context

Preparing a preview of two 6000 × 4000 linear TIFFs requested 232 million source pixel positions, counting repeated regions. Drawing the completed raster on OpenGL still took about 11 seconds end to end. The owner requested GPU acceleration and ruled out adding an application preview cache. [Source measurements](../../progression.md#2026-11-26---desktop-diagnosis---measured-panel-import-and-sky-preview-latency)

## Decision

Use an OpenGL 4.3 compute shader on the sky preview worker for bilinear interpolation with separate coverage. Keep WCS mapping, color conversion, panel corrections, weighted blending, and tone selection in the shared CPU path. Use float64 interpolation weights and accumulation, and keep the existing validity threshold. Scientific and photo export sampling retain the CPU reference. Both preview and export use the same geometry.

Read the requested neighbors directly from read-only file mappings for eligible contiguous TIFFs. Keep mappings only while the source is open for a job. Use the bounded tile reader for other inputs, including sources with external masks or coverage subimages. Limit each GPU dispatch to 16,384 samples and about 1.75 MiB of shader buffer payload. Release worker graphics resources and mapped source files at job completion or cancellation. Fall back to CPU interpolation when hardware OpenGL compute is unavailable or fails.

## Consequences

The GPU path needs no additional runtime dependency and no application image cache. File access and GPU transfer cost now depend on the selected samples on the direct TIFF path. Cold file reads can still dominate first-frame time. Panel import, which separately scans source files for foreground, continues through the CPU path. [Desktop workflow](../phase-3c.md#desktop-workflow) · [Performance tracking](../../questions_open_topics.md#q-035---desktop-panel-import-and-sky-preview-latency)
