# ADR-0025 - Fit sky previews and display supported sRGB TIFFs

- **Date** 2026-11-21
- **Status** Accepted for Phase 3C.

## Decision

New desktop projects enable **Auto Frame** for the sky preview. The preview worker samples the chosen band's eligible panel footprints from their effective WCS. Edited sky masks constrain the sampled regions. A spherical mean supplies the ICRS center across the RA wrap, and the median panel pixel scale supplies the grid scale. Use a padded TAN rectangle for ordinary fields and switch to ZEA for a wide field. A near-antipodal set can use the whole ZEA disk. Keep framing work bounded and render with the existing tile sampler. The final raster has at most 512 samples along its longest edge.

The optional manifest field `auto_frame_preview` records the requested preview mode. Older projects default to their saved sky grid. Editing the grid in Mosaic Settings selects the saved mode. **Use Preview Grid** explicitly copies the successful fit to the saved sky settings and clears composition placement when that grid changes. Export, foreground alignment and composition use the saved geometry relevant to their layer. [Shared-grid sampling decision](0013-shared-preview-grid.md)

The desktop accepts a set of unsigned 16-bit RGB TIFFs for **Visual Preview** when all carry embedded ICC profiles with matching standard sRGB colorants and transfer curves. Inspect bounded matrix and curve tags. Apply the canonical sRGB inverse transfer in float32 to each source tile before interpolation and keep the original mask. The tile adapter leaves source files and plate-solving samples untouched. Science validation and rendering require linear inputs and the existing brightness checks. Unsupported ICC profiles and mixtures of sRGB and linear or untagged panels report the affected panel. [ICC profile specification](https://www.color.org/specifications/ICC.1-2022-05.pdf) · [ICC sRGB characterization](https://registry.color.org/rgb-registry/srgb) · [sRGB transfer function](https://www.w3.org/TR/2026/CRD-css-color-4-20261009/#color-conversion-code)

## Verification

Check RA wrap, wide ZEA coverage, saved-grid parity, immutable raw samples, mask propagation, sRGB interpolation and scientific export rejection. Use the two original owner TIFFs to check the fresh desktop workflow with native CPU and OpenGL display. [Phase 3C workflow and checks](../phase-3c.md)
