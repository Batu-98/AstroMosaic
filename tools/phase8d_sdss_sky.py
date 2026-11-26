"""Test linked photo corrections against the calibrated backgrounds archived by SDSS."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import numpy as np
from astropy.coordinates import ICRS
from astropy.io import fits
from numpy.typing import NDArray
from scipy.ndimage import map_coordinates

from astromosaic.astrometry.stars import measure_stars
from astromosaic.core import Region, Tile
from astromosaic.core.job import DEFAULT_JOB_CONTEXT
from astromosaic.geometry import PanelGeometry, TileSky, read_panel_geometry
from astromosaic.io import open_panel
from astromosaic.io.atomic import atomic_binary_file
from astromosaic.photometry.stellar_gain import (
    LUMINANCE,
    aperture_flux,
    aperture_masks,
    aperture_region,
)
from astromosaic.pipeline.photo_color import PhotoTileSource, resolve_photo_profile
from astromosaic.storage.project import load_project
from tools.phase8d_overlap_reference import Indices, PanelSamples, Values, _digest, measure
from tools.phase8d_stellar_gain import Coefficients, measure_apertures

_BUDGET = 64 * 1024**2
_PEDESTAL = 0.04
_SCALE = 4.0


@dataclass(frozen=True)
class Band:
    pixels: NDArray[np.float32]
    sky_counts: NDArray[np.float32]
    x_interp: NDArray[np.float32]
    y_interp: NDArray[np.float32]
    calibration: NDArray[np.float32]
    geometry: PanelGeometry

    def sample(self, sky: TileSky) -> tuple[Values, Values]:
        x, y, inside = sky.in_panel(self.geometry, (0, 0))
        height, width = self.pixels.shape
        inside &= (x >= 0) & (x <= width - 1) & (y >= 0) & (y <= height - 1)
        x, y = x[inside], y[inside]
        col, row = np.floor(x).astype(np.intp), np.floor(y).astype(np.intp)
        flux, background = np.full(inside.shape, np.nan), np.full(inside.shape, np.nan)
        flux[inside] = map_coordinates(self.pixels, [y, x], order=1, output=np.float64)
        # Calibrate each detector sample before interpolating onto the sky grid.
        restored = np.zeros_like(x)
        for dy, wy in ((0, 1 - (y - row)), (1, y - row)):
            for dx, wx in ((0, 1 - (x - col)), (1, x - col)):
                cy, cx = np.minimum(row + dy, height - 1), np.minimum(col + dx, width - 1)
                counts = map_coordinates(
                    self.sky_counts,
                    [self.y_interp[cy], self.x_interp[cx]],
                    order=1,
                    mode="nearest",
                    output=np.float64,
                )
                restored += wy * wx * counts * self.calibration[cx]
        background[inside] = restored
        return flux, background


def _read_band(hdus: fits.HDUList) -> Band:
    pixels = hdus[0].data
    height, width = pixels.shape
    sky = hdus[2].data[0]
    return Band(
        pixels,
        sky["ALLSKY"],
        sky["XINTERP"],
        sky["YINTERP"],
        hdus[1].data,
        read_panel_geometry(hdus[0].header, width, height),
    )


def _sample_rgb(bands: Sequence[Band], sky: TileSky) -> tuple[Values, Values]:
    flux, background = zip(*(band.sample(sky) for band in bands), strict=True)
    return _PEDESTAL + np.column_stack(flux) / _SCALE, np.column_stack(background) / _SCALE


def _apply(rgb: Values, xy: Values, terms: Sequence[float]) -> Values:
    gain, offset, dx, dy = terms
    return gain * rgb + (offset + dx * xy[:, 0] + dy * xy[:, 1])[:, None]


def _p95(values: Values) -> float:
    return float(np.percentile(np.abs(values), 95))


def _diffuse_metrics(
    panels: dict[str, tuple[PanelSamples, Values]],
    edges: Sequence[Sequence[str]],
    models: dict[str, Coefficients],
    x: Indices,
    y: Indices,
) -> dict[str, object]:
    block = np.column_stack((x // 64, y // 64))
    final = (block[:, 1] + 2 * block[:, 0]) % 5 == 0
    result: dict[str, object] = {}
    for left, right in edges:
        a, truth_a = panels[left]
        b, truth_b = panels[right]
        valid = final & np.isfinite(a.rgb).all(axis=1) & np.isfinite(b.rgb).all(axis=1)
        # Each scan's same-pixel archive signal is the reference. Subtract the two errors
        # to evaluate relative backgrounds without imposing an absolute mosaic pedestal.
        truth = truth_a[valid] - truth_b[valid]
        background = a.rgb[valid] - b.rgb[valid] - truth
        # A scalar correction can move all three channels equally. Even its best
        # possible value leaves at least half the channel range in one channel.
        linked_floor = float(np.median(np.ptp(background, axis=1) / 2))
        scores = {}
        for name, coefficients in models.items():
            corrected = _apply(a.rgb[valid], a.xy[valid], coefficients[left])
            corrected -= _apply(b.rgb[valid], b.xy[valid], coefficients[right])
            scores[name] = _p95(corrected - truth)
        result[f"{left}/{right}"] = {
            "samples": int(valid.sum()),
            "relative_sky_rgb_p95": scores,
            "median_linked_unity_gain_error_floor": linked_floor,
        }
    return result


def _stellar_errors(
    source: PhotoTileSource,
    bands: Sequence[Band],
    target: PanelGeometry,
    size: tuple[int, int],
    models: dict[str, Coefficients],
    name: str,
) -> dict[str, object]:
    reference = bands[1].geometry
    height, width = bands[1].pixels.shape
    errors: dict[str, list[float]] = {key: [] for key in models}
    bounds = Region(0, 0, width, height)
    for star in measure_stars(source, _BUDGET, DEFAULT_JOB_CONTEXT).stars:
        region = aperture_region(star.x, star.y)
        if not bounds.contains(region):
            continue
        y, x = np.mgrid[region.slices].reshape(2, -1).astype(np.float64)
        sky = TileSky.from_pixels(reference, x, y)
        output = target.inverse(sky.sky)
        if not np.all((output >= 0) & (output < size)):
            continue
        blocks = np.floor(output / 64)
        block = blocks[0]
        if not np.all(blocks == block) or (block[1] + 2 * block[0]) % 5 != 0:
            continue
        rgb, bg = _sample_rgb(bands, sky)
        valid = np.isfinite(rgb + bg).all(axis=1) & ((rgb >= 0) & (rgb < 1)).all(axis=1)
        tile = Tile(
            region,
            rgb.reshape(region.height, region.width, 3).astype(np.float32),
            valid.reshape(region.height, region.width),
        )
        expected = aperture_flux(tile, star.x, star.y)
        if expected is None:
            continue
        core, annulus = (mask.ravel() for mask in aperture_masks(region, star.x, star.y))
        restored = rgb + bg
        xy = np.column_stack((2 * x / (width - 1) - 1, 2 * y / (height - 1) - 1))
        for model, coefficients in models.items():
            adjusted = _apply(restored, xy, coefficients[name])
            measured = float(
                (adjusted[core] - np.median(adjusted[annulus], axis=0)).sum(0) @ LUMINANCE
            )
            errors[model].append(measured / expected - 1)
    return {
        model: {"apertures": len(values), "abs_fractional_error_p95": _p95(np.asarray(values))}
        if values
        else {"apertures": 0}
        for model, values in errors.items()
    }


def compare(
    project_path: Path, manifest_path: Path, archive: Path, *, linked_offset_bound: bool = False
) -> dict[str, object]:
    project = load_project(project_path)
    region = project.render.output_region()
    size = (region.width, region.height)
    inputs = {project_path: _digest(project_path), manifest_path: _digest(manifest_path)}
    rows = json.loads(manifest_path.read_bytes())
    paths = {row["filename"]: archive / row["filename"] for row in rows}
    for row in rows:
        path = paths[row["filename"]]
        if _digest(path) != row["sha256"]:
            raise ValueError(f"SDSS archive checksum mismatch: {path.name}")
        inputs[path] = row["sha256"]

    records = sorted(project.panels, key=lambda record: record.source.path.name)
    count = ((size[0] + 3) // 8) * ((size[1] + 3) // 8)
    if len(records) != 3 or not count or 384 * count * len(records) > _BUDGET:
        raise ValueError("Use a bounded, saved SDSS comparison grid with three RGB panels.")
    target = PanelGeometry(project.render.output_wcs(), ICRS())
    y, x = np.mgrid[4 : size[1] : 8, 4 : size[0] : 8].reshape(2, -1)
    sky = TileSky.from_pixels(target, x.astype(np.float64), y.astype(np.float64))
    sampled, observed, coverage, apertures = {}, {}, {}, {}
    with ExitStack() as opened:
        audit = {}
        for record in records:
            path = record.source.path
            if record.source.status() != "Ready":
                raise ValueError(f"SDSS project reference is unavailable or changed: {path.name}")
            inputs[path] = _digest(path)
            selected = [row for row in rows if path.stem == f"{row['run']:06d}-{row['field']:04d}"]
            files = {row["band"]: paths[row["filename"]] for row in selected}
            if len(selected) != 3 or set(files) != set("irg"):
                raise ValueError(f"Expected a separate i, r and g frame for {path.name}.")
            bands = [
                _read_band(
                    opened.enter_context(fits.open(files[band], mode="readonly", memmap=True))
                )
                for band in "irg"
            ]
            reference = bands[1]
            sx, sy, _ = sky.in_panel(reference.geometry, (0, 0))
            height, width = reference.pixels.shape
            xy = np.column_stack((2 * sx / (width - 1) - 1, 2 * sy / (height - 1) - 1))
            truth, bg = _sample_rgb(bands, sky)
            restored = truth + bg
            usable = np.isfinite(truth).all(axis=1) & ((truth >= 0) & (truth < 1)).all(axis=1)
            observed[path.name] = (restored, xy, usable)
            fit = np.where((usable & ((truth @ LUMINANCE) <= 0.075))[:, None], restored, np.nan)
            sampled[path.name] = (PanelSamples(path.name, fit, xy), truth)
            source = opened.enter_context(open_panel(path, max_tile_bytes=_BUDGET))
            profile = resolve_photo_profile(
                source, record.photo_profile, project.photo_settings.profile
            )
            linear = PhotoTileSource(source, profile, _BUDGET)
            apertures[path.name] = measure_apertures(
                linear, reference.geometry, target, size, _BUDGET
            )
            audit[path.name] = (linear, bands)

        panels = [row[0] for row in sampled.values()]
        result = measure(
            panels,
            x,
            y,
            preserve_calibrated_scale=True,
            stellar_apertures=apertures,
            linked_offset_bound=linked_offset_bound,
        )
        if result != measure(
            panels[::-1],
            x,
            y,
            preserve_calibrated_scale=True,
            stellar_apertures=apertures,
            linked_offset_bound=linked_offset_bound,
        ):
            raise ValueError("Reversing the SDSS panels changed the overlap result.")
        models = cast(dict[str, Coefficients], result["coefficients"])
        edges = cast(Sequence[Sequence[str]], result["scored_edges"])
        if len(edges) != 3:
            raise ValueError("The frozen SDSS comparison requires all three overlaps.")
        for name, (restored, xy, usable) in observed.items():
            restored[~usable] = np.nan
            candidate_masks = [
                np.isfinite(_apply(restored, xy, terms[name])).all(axis=1)
                for terms in models.values()
            ]
            if any(not np.array_equal(usable, mask) for mask in candidate_masks):
                raise ValueError(f"The candidate corrections changed sample coverage: {name}")
            coverage[name] = int(usable.sum())
        diffuse = _diffuse_metrics(sampled, edges, models, x, y)
        stellar = {
            name: _stellar_errors(linear, bands, target, size, models, name)
            for name, (linear, bands) in audit.items()
        }
    if any(_digest(path) != expected for path, expected in inputs.items()):
        raise ValueError("A diagnostic input changed during sampling.")
    return dict(
        schema_version=1,
        input_sha256={path.name: checksum for path, checksum in inputs.items()},
        grid_size=size,
        sample_step=8,
        covered_samples=coverage,
        verified_sample_coverage=True,
        verified_order_independence=True,
        comparison=result,
        final_diffuse=diffuse,
        final_apertures=stellar,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Saved comparison project for the SDSS scene.")
    parser.add_argument(
        "manifest", type=Path, help="Local source FITS provenance JSON for the scene."
    )
    parser.add_argument(
        "archive", type=Path, help="Folder with the original decompressed FITS files."
    )
    parser.add_argument(
        "--linked-offset-bound",
        action="store_true",
        help="Bound overlap RGB P95 after any linked additive correction at unity gain.",
    )
    parser.add_argument(
        "-o", "--output", type=Path, required=True, help="New JSON result to write."
    )
    args = parser.parse_args()
    with atomic_binary_file(args.output) as stream:
        report = compare(
            args.project, args.manifest, args.archive, linked_offset_bound=args.linked_offset_bound
        )
        stream.write((json.dumps(report, indent=2, allow_nan=False) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
