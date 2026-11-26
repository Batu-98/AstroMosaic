"""Prepare Richard Tatti's public panorama exposures as linear RGB test TIFFs."""

from __future__ import annotations

import argparse
import json
from hashlib import file_digest
from pathlib import Path
from shutil import copyfileobj
from typing import cast
from zipfile import ZipExtFile, ZipFile

import numpy as np
import tifffile
from astropy.io import fits

from astromosaic.io.atomic import atomic_binary_file

_FRAMES = range(8, 12)
_ARCHIVE = "tree_vertical_panorama_raw_files.zip"
_SETS = {
    "milky-way-tree": tuple(f"milky_way_tree_{number}.nef" for number in range(1, 4)),
    "dead-tree": tuple(f"tree_vertical_{number:03d}.nef" for number in _FRAMES),
}


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def _dead_tree_sources(root: Path) -> None:
    with ZipFile(root / _ARCHIVE) as archive:
        for number, name in zip(_FRAMES, _SETS["dead-tree"], strict=True):
            member = (
                f"Tree Vertical Panorama Raw files/Panoramas Tree Rostrata etc Z6 20mm {number:03d}.NEF"
            )
            path = root / name
            with archive.open(member) as source:
                if path.is_file():
                    if file_digest(cast(ZipExtFile, source), "sha256").hexdigest() != _digest(path):
                        raise ValueError(f"Extracted file differs from the archive: {path.name}")
                else:
                    with atomic_binary_file(path) as output:
                        copyfileobj(source, output, length=1024**2)


def _camera_metadata(path: Path) -> tuple[str, float, float, int, str]:
    with tifffile.TiffFile(path) as source:
        page = source.pages[0]
        if not isinstance(page, tifffile.TiffPage):
            raise ValueError(f"Missing camera metadata for {path.name}.")
        tags = page.tags
        exif = tags.valueof("ExifTag")
        exposure = exif["ExposureTime"]
        focal = exif["FocalLength"]
        return (
            str(tags.valueof("Model")),
            focal[0] / focal[1],
            exposure[0] / exposure[1],
            int(exif["ISOSpeedRatings"]),
            str(exif["DateTimeOriginal"]),
        )


def prepare(root: Path, destination: Path) -> None:
    import rawpy

    _dead_tree_sources(root)
    destination.mkdir(parents=True)
    cases = {}
    for name, files in _SETS.items():
        target = destination / name
        target.mkdir()
        with rawpy.imread(str(root / files[0])) as raw:
            white = list(map(float, raw.daylight_whitebalance))
            saturation = int(raw.white_level)
        if len(white) != 4:
            raise ValueError(f"Missing daylight white balance for {name}.")
        if white[3] <= 0:
            white[3] = white[1]
        if any(not np.isfinite(value) or value <= 0 for value in white):
            raise ValueError(f"Missing daylight white balance for {name}.")
        panels = []
        for filename in files:
            path = root / filename
            fingerprint = _digest(path)
            camera, focal, exposure, iso, captured = _camera_metadata(path)
            with rawpy.imread(str(path)) as raw:
                if raw.white_level != saturation:
                    raise ValueError(f"Different sensor white level in {filename}.")
                pixels = raw.postprocess(
                    demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD,
                    user_wb=white,
                    output_color=rawpy.ColorSpace.sRGB,
                    output_bps=16,
                    gamma=(1, 1),
                    no_auto_bright=True,
                    adjust_maximum_thr=0,
                    user_sat=saturation,
                    user_flip=0,
                )
            height, width, channels = pixels.shape
            if channels != 3 or pixels.dtype != np.uint16:
                raise ValueError(f"Expected three linear UInt16 channels for {filename}.")
            header = fits.Header()
            header["INSTRUME"] = camera
            header["FOCALLEN"] = focal
            header["EXPTIME"] = exposure
            header["ISO"] = iso
            output = target / path.with_suffix(".tiff").name
            with atomic_binary_file(output) as stream:
                tifffile.imwrite(
                    stream,
                    pixels,
                    photometric="rgb",
                    metadata=None,
                    description="AstroMosaic TIFF 1\n" + header.tostring(sep="\n"),
                )
            with tifffile.TiffFile(output) as reopened:
                page = reopened.pages[0]
                if page.shape != pixels.shape or page.dtype != pixels.dtype:
                    raise ValueError(f"Reopened TIFF layout differs for {output.name}.")
            sampled = tifffile.memmap(output, mode="r")[::131, ::127]
            np.testing.assert_array_equal(sampled, pixels[::131, ::127])
            del sampled, pixels
            if _digest(path) != fingerprint:
                raise ValueError(f"The original capture changed: {filename}")
            panels.append(
                dict(
                    source=filename,
                    source_sha256=fingerprint,
                    camera=camera,
                    focal_length_mm=focal,
                    exposure_s=exposure,
                    iso=iso,
                    local_capture_time=captured,
                    output=output.name,
                    output_sha256=_digest(output),
                    size_xy=[width, height],
                )
            )
            print(f"{output.name}: {width} x {height}, RGB UInt16", flush=True)
        cases[name] = dict(raw_white_level=saturation, white_balance=white, panels=panels)
    report = dict(
        rawpy_version=rawpy.__version__,
        libraw_version=rawpy.libraw_version,
        profile_assignment="linear-srgb",
        archive_sha256=_digest(root / _ARCHIVE),
        cases=cases,
    )
    with atomic_binary_file(destination / "preparation.json") as stream:
        stream.write((json.dumps(report, indent=2, allow_nan=False) + "\n").encode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Directory containing the public NEFs and ZIP.")
    parser.add_argument("destination", type=Path, help="New directory for the linear test TIFFs.")
    args = parser.parse_args()
    prepare(args.source, args.destination)


if __name__ == "__main__":
    main()
