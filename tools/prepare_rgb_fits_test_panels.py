"""Convert the Nocturne Float32 RGB FITS masters to AstroMosaic TIFF panels."""

from __future__ import annotations

import argparse
import json
from hashlib import file_digest
from pathlib import Path

import numpy as np
import tifffile
from astropy.io import fits

from astromosaic.core import Region, Tile
from astromosaic.io.atomic import atomic_binary_file
from astromosaic.io.tiff_export import open_tiff_mosaic

_ROWS = 128


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def convert(source: Path, target: Path) -> dict[str, object]:
    fingerprint = _digest(source)
    with fits.open(source, mode="readonly", memmap=True, do_not_scale_image_data=True) as opened:
        primary = opened[0]
        header = primary.header
        if (
            len(opened) != 1
            or len(primary.shape) != 3
            or primary.shape[0] != 3
            or min(primary.shape) < 1
            or header["BITPIX"] != -32
            or header.get("BSCALE", 1) != 1
            or header.get("BZERO", 0) != 0
        ):
            raise ValueError(f"Expected one unscaled Float32 RGB cube in {source.name}.")
        _, height, width = primary.shape
        data = primary.data
        with open_tiff_mosaic(target, width, height, 3, header.copy(strip=True), 1024**3) as output:
            for y in range(0, height, _ROWS):
                size = min(_ROWS, height - y)
                rgb = np.moveaxis(data[:, y : y + size, :], 0, -1)
                coverage = np.isfinite(rgb).all(axis=-1)
                output.write(Tile(Region(0, y, width, size), rgb, coverage))

        valid_count = 0
        with tifffile.TiffFile(target) as opened_tiff:
            page = opened_tiff.pages[0]
            if not isinstance(page, tifffile.TiffPage) or page.pages is None:
                raise ValueError(f"Missing the TIFF coverage raster in {target.name}.")
            mask_page = page.pages[0]
            rgb_tiff = tifffile.memmap(target, mode="r", page=0)
            mask = np.memmap(
                target,
                mode="r",
                offset=mask_page.dataoffsets[0],
                dtype=np.uint8,
                shape=(height, width),
            )
            for y in range(0, height, _ROWS):
                expected = np.moveaxis(data[:, y : y + _ROWS, :], 0, -1)
                covered = np.isfinite(expected).all(axis=-1)
                np.testing.assert_array_equal(rgb_tiff[y : y + _ROWS][covered], expected[covered])
                np.testing.assert_array_equal(mask[y : y + _ROWS], covered)
                valid_count += int(covered.sum())
            del rgb_tiff, mask
        del rgb, expected, data
    if _digest(source) != fingerprint:
        raise ValueError(f"The original FITS file changed: {source.name}")
    return dict(
        source=source.name,
        source_sha256=fingerprint,
        tiff=target.name,
        tiff_sha256=_digest(target),
        size_xy=[width, height],
        covered_samples=valid_count,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Directory of original Nocturne FITS masters.")
    parser.add_argument("destination", type=Path, help="New directory for the verified TIFFs.")
    args = parser.parse_args()
    sources = sorted(args.source.glob("*.fits"))
    if not sources:
        parser.error("The source directory has no FITS masters.")
    args.destination.mkdir(parents=True)
    reports = []
    for source in sources:
        target = args.destination / source.with_suffix(".tiff").name
        report = convert(source, target)
        print(f"Verified {target.name}: {report['covered_samples']} RGB samples", flush=True)
        reports.append(report)
    with atomic_binary_file(args.destination / "preparation.json") as stream:
        stream.write((json.dumps(reports, indent=2, allow_nan=False) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
