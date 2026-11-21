# Phase 3A Linear TIFF Interoperability

## Sample and Metadata Contract

- Input is a single top-left (`Orientation=1` or omitted) linear raster in TIFF or BigTIFF. Use grayscale `MINISBLACK` or three-sample `RGB`, without alpha. Import accepts unsigned or signed 16-bit integers and 32-bit floating point, both byte orders, interleaved or separate RGB planes, and strips or tiles. Supported compression is uncompressed, LZW, Deflate, and PackBits.
- Unsigned integers keep their `0..65535` codes. Signed integers keep their `−32768..32767` codes. The engine converts these exactly to float32. Float32 values keep their stored scale, including negative, zero, and above-one values. Supply already-linear data with one common brightness and color calibration. No gamma, ICC, per-image normalization, or color conversion is applied.
- Mono is YX. RGB is YXC in red, green, blue order. An RGB pixel is eligible only when all three channels are finite and the spatial masks permit it. The same valid bilinear support and panel weights apply to each channel. Any finite sample value, including zero, remains eligible. Export uses NaN in all channels at an uncovered pixel.
- AstroMosaic's version 1 `ImageDescription` starts with `AstroMosaic TIFF 1` followed by a newline and newline-delimited ASCII FITS header cards. WCS uses the same zero-based pixel centers in array access and FITS `CRPIX` convention in the cards. The header also carries the common `FILTER`, `BUNIT` if known, and processing history.
- The AstroMosaic description can be used without coverage on input. If it has a SubIFD, the SubIFD must be a same-size unscaled byte grayscale raster with 1 for covered and 0 for excluded. The first and only top-level image always holds the science pixels. Export writes the description and coverage SubIFD together so success leaves one complete file.
- TIFFs without this description can be inspected and solved locally. Existing source-bound `solve -o` sidecars work with `mosaic --wcs`. RGB solving uses its green plane as the astrometry signal, with the shared masks. A supplied binary FITS `--sky-mask` uses the original panel coordinates and intersects the TIFF coverage.
- Mono TIFF and mono FITS can share a job when their brightness scales and filter labels agree. Files with no filter label use `Unspecified` by default. Use `--filter` to assign a known common label and `--assume-surface-brightness` to declare a shared brightness scale for compatible linear inputs. Relative photometric refinement accepts mono panels. RGB jobs use resolved WCS and export to TIFF. Output TIFF uses uncompressed little-endian float32 and interleaved RGB when applicable.
- Uncompressed reads fetch row fragments from the intersecting strips or tiles. Compressed reads reserve scratch for one decoded segment plus the requested window. If a single encoded segment exceeds the budget even for a one-pixel request, use a larger working budget or a source with smaller strips or tiles.

Example for two already-solved RGB panels with no embedded filter or brightness label:

```shell
astromosaic mosaic data/panel-a.tif data/panel-b.tif --wcs 1=output/panel-a.wcs.json --wcs 2=output/panel-b.wcs.json --assume-surface-brightness --center 359.999 20 --scale 7.2 --size 1500 900 --progress -o output/mosaic.tiff
astromosaic inspect output/mosaic.tiff
```

## Acceptance Fixtures

Generate fixtures in temporary directories. Require exact equality for integer conversion, aligned science samples, channel order, and spatial coverage. Require sampled WCS coordinates to agree with analytic TAN within `1e-9` degrees. For the rotated and cropped RGB grid, check each interpolated channel against an analytic affine field within `2e-6` brightness units.

- The mono and RGB two-panel references share the [Phase 1 field](phase-1.md#two-panel-fixture), footprint, holes, and weights of 1 and 3. The first panel uses TIFF integers with binary coverage at finite missing samples. The second uses float32 with nonfinite samples. The RGB vector for brightness `v` is `(-2v, v, v + 64)`. In the second RGB panel, a single nonfinite channel invalidates the pixel. The expected grid still has 65 covered pixels.
- Reader fixtures cross strip and tile boundaries and check both TIFF byte orders, separate and interleaved RGB, and nontrivial signed and high unsigned codes. Reopen the exports through the application and through libtiff for independent science sample and channel checks.

## Windows Evidence

- Windows 11 Pro x64 build 26200 with CPython 3.13.18 passed all 51 tests, including 14 TIFF cases. The two-panel mono and RGB mosaics reopened with all finite samples and 65 covered pixels matching exactly. libtiff 4.7.2 independently read the primary science rasters. AstroMosaic and tifffile reopened the binary coverage, and the exported WCS and rotated crop met the analytic tolerances. The suite also checks mixed-format mono output, resource rejection, input preservation, and cancellation followed by retry. [TIFF tests](../tests/numerical/test_tiff.py)
- For a real local solve, an unstretched 3267 × 3274 RGB TIFF was generated from the [M13 DSS fixture](phase-0.md#offline-astap-experiment). Its green channel held the archive samples, and red and blue used fixed affine scales. Hinted Gaia matched the same 132 stars as the mono FITS source, with 0.469 arcseconds internal RMS and at most 0.374 arcseconds separation from the archive WCS at five samples.
- With a supplied sky mask, Gaia found too few matches and the normal chain continued to hinted ASTAP. Its solution was within 0.721 arcseconds at the same five samples. The CLI rendered a 160 × 112 RGB TIFF from that saved WCS and mask. Independent libtiff reopening verified the three channel relationships, and the coverage SubIFD matched finite support for all 17,920 pixels. The TIFF source SHA-256 and modification time stayed unchanged. [Local solver versions and catalogs](phase-2.md#windows-solver-evidence)
- Packaged desktop interoperability enters acceptance in Phase 3F. Large-mosaic resource measurements and RGB photometric refinement remain tracked in the [open topics](../questions_open_topics.md).
