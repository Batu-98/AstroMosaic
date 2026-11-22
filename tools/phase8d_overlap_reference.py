"""Freeze the first Advanced photo matching controls and compare offline candidates."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import file_digest, sha256
from itertools import combinations
from math import sqrt
from pathlib import Path

import numpy as np
import tifffile
from astropy.coordinates import ICRS
from numpy.typing import NDArray
from scipy.ndimage import maximum_filter

from astromosaic.astrometry.registration import components, projected_bounds, robust_linear_fit
from astromosaic.astrometry.solve import load_solution
from astromosaic.core.job import DEFAULT_JOB_CONTEXT
from astromosaic.geometry import PanelGeometry, TileSky, read_panel_geometry
from astromosaic.io import open_panel
from astromosaic.io.atomic import atomic_binary_file
from astromosaic.photometry.photo_match import LUMINANCE, fit_brightness
from astromosaic.photometry.stellar_gain import Aperture
from astromosaic.pipeline.photo_color import PhotoTileSource, resolve_photo_profile
from astromosaic.pipeline.photo_fit import PhotoPanel, _sample_panel
from astromosaic.storage.project import load_project
from tools.phase8d_stellar_gain import Coefficients, measure_apertures, qualify_gains

type Values = NDArray[np.float64]
type Indices = NDArray[np.int64]

_JOB = DEFAULT_JOB_CONTEXT
_OWNER_HASH = "c3d7f1bd6264ea489ed62220ef051ffda2911cd9d7c5daef1ce00b9d9983d4db"
_PA4 = ("19.TIF", "20.TIF", "21.TIF", "22.TIF")
_BUDGET = 64 * 1024**2
_MIN_SAMPLES = 128
_MIN_BLOCKS = 2
_P95_MARGIN = 2e-6
_RANK_RATIO = 0.015
_IDENTITY = np.array([1.0, 0.0, 0.0, 0.0])
_TRUTH = np.array(
    [
        [1.0, 0, 0, 0],
        [1.25, -0.005, 0.0025, -0.0015],
        [0.84, -0.004, -0.0015, 0.0015],
        [1.0, 0, 0, 0],
        [1.12, -0.004, 0.001, -0.002],
    ]
)
_APERTURE = (739, 220)


@dataclass(frozen=True)
class PanelSamples:
    name: str
    rgb: Values
    xy: Values


@dataclass(frozen=True)
class Edge:
    indices: tuple[int, int]
    rgb: Values
    xy: Values
    fold: Indices
    counts: tuple[int, ...]
    blocks: tuple[int, ...]

    @property
    def qualified(self) -> bool:
        return min(self.counts) >= _MIN_SAMPLES and min(self.blocks) >= _MIN_BLOCKS


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def _decode(codes: NDArray[np.uint16]) -> Values:
    value = codes.astype(np.float64) / 65535
    return np.where(value < 0.04045, value / 12.92, ((value + 0.055) / 1.055) ** 2.4)


def _encode(linear: Values) -> NDArray[np.uint16]:
    value = np.clip(linear, 0, 1)
    return np.rint(
        np.where(value < 0.0031308, 12.92 * value, 1.055 * value ** (1 / 2.4) - 0.055) * 65535
    ).astype(np.uint16)


def _aperture_flux(crop: Values) -> float:
    distance_squared = np.arange(-12, 13) ** 2 + np.arange(-12, 13)[:, None] ** 2
    values = crop @ LUMINANCE
    sky = np.median(values[(distance_squared >= 64) & (distance_squared <= 144)])
    return float(np.sum(values[distance_squared <= 36] - sky))


def _control_metrics(
    crop: Values,
    panels: Sequence[PanelSamples],
    x: Indices,
    y: Indices,
    truth: Values,
    coefficients: Values,
) -> dict[str, float]:
    test = (y // 64 + 2 * (x // 64)) % 5 == 0
    residuals = []
    for panel, (gain, offset, dx, dy) in zip(panels[:3], coefficients, strict=True):
        valid = test & np.isfinite(panel.rgb).all(axis=1)
        corrected = (
            panel.rgb[valid] * gain + (offset + panel.xy[valid] @ np.array([dx, dy]))[:, None]
        )
        residuals.append(np.abs(corrected - crop[y[valid], x[valid]]).ravel())
    ax, ay = _APERTURE
    yy, xx = np.mgrid[ay - 12 : ay + 13, ax - 12 : ax + 13]
    # C uses the same detector rectangle in both controls. Its aperture is entirely in test.
    assert np.all((yy // 64 + 2 * (xx // 64)) % 5 == 0)
    local_x, local_y = 2 * (xx - 384) / 383 - 1, 2 * yy / 447 - 1
    sample = crop[yy, xx]
    g, b, dx, dy = truth[2]
    encoded = _encode((sample - (b + dx * local_x + dy * local_y)[..., None]) / g)
    gain, offset, sx, sy = coefficients[2]
    restored = _decode(encoded) * gain + (offset + sx * local_x + sy * local_y)[..., None]
    flux = _aperture_flux(sample)
    if not flux > 0:
        raise ValueError("Expected a positive reference stellar aperture flux.")
    return {
        "covered_diffuse_test_rgb_p95": float(np.percentile(np.concatenate(residuals), 95)),
        "stellar_aperture_fractional_error": abs(_aperture_flux(restored) / flux - 1),
    }


def _control(
    crop: Values, *, chain: bool, plane: bool
) -> tuple[list[PanelSamples], Indices, Indices, Values]:
    y, x = np.indices(crop.shape[:2])
    sampled = (x % 3 == 0) & (y % 3 == 0)
    quiet = ~maximum_filter((crop @ LUMINANCE > 0.075) | (crop >= 1).any(axis=2), size=11)
    regions = (
        (0, 0, 384 if chain else 512, 448),
        (192, 0, 640, 448),
        (384, 0, 768, 448),
        (0, 448, 640, 512),
        (128, 448, 768, 512),
    )
    truth = _TRUTH.copy()
    if not plane:
        truth[:, 2:] = 0
    frames = []
    for name, (left, top, right, bottom), (gain, offset, dx, dy) in zip(
        "ABCDE", regions, truth, strict=True
    ):
        xy = np.stack(
            (2 * (x - left) / (right - left - 1) - 1, 2 * (y - top) / (bottom - top - 1) - 1),
            axis=-1,
        )[sampled]
        bias = offset + xy @ np.array([dx, dy])
        valid = (quiet & (x >= left) & (x < right) & (y >= top) & (y < bottom))[sampled]
        observed = _decode(_encode((crop[sampled] - bias[:, None]) / gain))
        observed[~valid] = np.nan
        frames.append(PanelSamples(name, observed, xy))
    return frames, x[sampled], y[sampled], truth


def _edges(panels: Sequence[PanelSamples], x: Indices, y: Indices) -> list[Edge]:
    col, row = x // 64, y // 64
    block = row * (int(col.max()) + 1) + col
    assignment = (row + 2 * col) % 5
    fold = np.where(assignment == 0, 2, np.where(assignment == 1, 1, 0))
    result = []
    for i, j in combinations(range(len(panels)), 2):
        a, b = panels[i], panels[j]
        valid = np.isfinite(a.rgb).all(axis=1) & np.isfinite(b.rgb).all(axis=1)
        if not valid.any():
            continue
        split = fold[valid]
        result.append(
            Edge(
                (i, j),
                np.stack((a.rgb[valid], b.rgb[valid]), axis=1),
                np.stack((a.xy[valid], b.xy[valid]), axis=1),
                split,
                tuple(int(np.sum(split == n)) for n in range(3)),
                tuple(np.unique(block[valid][split == n]).size for n in range(3)),
            )
        )
    return result


def _candidate(
    edges: Sequence[Edge],
    group: tuple[int, ...],
    count: int,
    *,
    plane: bool,
    fixed_gain: bool = False,
) -> tuple[Values | None, str]:
    start_term = int(fixed_gain)
    terms = (4 if plane else 2) - start_term
    coefficients = np.tile(_IDENTITY, (count, 1))
    columns = {panel: (i - 1) * terms for i, panel in enumerate(group) if i}
    train_rows = sum(edge.counts[0] for edge in edges)
    # Reserve dense regression copies and workspace before allocating the design.
    if 64 * train_rows * (len(columns) * terms + 4) > _BUDGET:
        return None, "Fit exceeds the reference memory budget."
    matrix = np.zeros((train_rows, len(columns) * terms))
    weights = np.empty(train_rows)
    rhs = np.empty((train_rows, 1))
    start = 0
    for edge in edges:
        train = edge.fold == 0
        luminance = edge.rgb[train] @ LUMINANCE
        region = slice(start, start + len(luminance))
        rhs[region, 0] = luminance[:, 1] - luminance[:, 0]
        weights[region] = 1 / sqrt(len(luminance))
        for axis, panel in enumerate(edge.indices):
            position = columns.get(panel)
            if position is None:
                continue
            sign = 1 - 2 * axis
            offset = position
            if not fixed_gain:
                matrix[region, position] = sign * luminance[:, axis]
                offset += 1
            matrix[region, offset] = sign
            if plane:
                matrix[region, offset + 1 : offset + 3] = sign * edge.xy[train, axis]
        start = region.stop
    if not matrix.size:
        return None, "No reference-connected fit support."
    # Fixed units preserve the low-signal and conditioning checks across candidates.
    scale = np.tile([0.02, 1.0, 1.0, 1.0][start_term : start_term + terms], len(columns))
    matrix /= scale
    singular = np.linalg.svd(matrix * weights[:, None], compute_uv=False)
    if singular.size < matrix.shape[1] or singular[-1] < _RANK_RATIO * singular[0]:
        return None, "The overlap design lacks independent signal or spatial support."
    adjustment = robust_linear_fit(matrix, rhs, weights).ravel() / scale
    for panel, start in columns.items():
        coefficients[panel, start_term : start_term + terms] += adjustment[start : start + terms]
    if np.any((coefficients[:, 0] < 0.25) | (coefficients[:, 0] > 4.0)) or np.any(
        np.abs(coefficients[:, 1:]).sum(axis=1) > 0.1
    ):
        return None, "At least one panel exceeds the gain or full-field background bounds."
    return coefficients, ""


def _errors(edges: Sequence[Edge], coefficients: Values, fold: int) -> list[float]:
    errors = []
    for edge in edges:
        valid = edge.fold == fold
        terms = coefficients[list(edge.indices)]
        bias = terms[:, 1] + np.sum(edge.xy[valid] * terms[:, 2:], axis=-1)
        corrected = edge.rgb[valid] * terms[:, 0, None] + bias[..., None]
        errors.append(float(np.percentile(np.abs(corrected[:, 0] - corrected[:, 1]), 95)))
    return errors


def _standard(edges: Sequence[Edge], group: tuple[int, ...], count: int) -> Values:
    coefficients = np.tile(_IDENTITY, (count, 1))
    visited = {group[0]}
    for _ in group[1:]:
        for edge in edges:
            left, right = edge.indices
            if (left in visited) == (right in visited):
                continue
            axis = int(right in visited)
            reference, moving = edge.indices[axis], edge.indices[1 - axis]
            pairs = edge.rgb[:, [axis, 1 - axis]].copy()
            pairs[:, 0] *= coefficients[reference, 0]
            pairs[:, 0] += coefficients[reference, 1]
            fit = fit_brightness(
                pairs[edge.fold == 0],
                pairs[edge.fold == 1],
                edge.blocks[0],
                edge.blocks[1],
                "standard",
            )
            if fit.method != "off" or (
                fit.before_p95 is not None and fit.before_p95 <= _P95_MARGIN
            ):
                coefficients[moving, :2] = fit.gain, fit.offset
                visited.add(moving)
                break
        else:
            break
    return coefficients


def _select(validation: dict[str, list[float]], models: Sequence[tuple[str, float]]) -> str:
    selected = "off"
    for name, factor in models:
        previous, current = validation[selected], validation.get(name)
        if (
            current
            and np.mean(current) < factor * np.mean(previous) - _P95_MARGIN
            and all(
                new <= max(1.05 * old, old + _P95_MARGIN)
                for old, new in zip(previous, current, strict=True)
            )
        ):
            selected = name
    return selected


def measure(
    panels: Sequence[PanelSamples],
    x: Indices,
    y: Indices,
    *,
    preserve_calibrated_scale: bool = False,
    stellar_apertures: Mapping[str, Sequence[Aperture]] | None = None,
    additional_gains: Mapping[str, Coefficients] | None = None,
) -> dict[str, object]:
    panels = sorted(panels, key=lambda panel: panel.name)
    names = [panel.name for panel in panels]
    edges = _edges(panels, x, y)
    groups = components(len(names), [edge.indices for edge in edges if edge.qualified])
    reference = groups[0]
    accepted = [e for e in edges if e.qualified and set(e.indices).issubset(reference)]
    count = len(names)
    baseline = np.tile(_IDENTITY, (count, 1))
    models = {"off": baseline, "standard": _standard(accepted, reference, count)}
    rejected = {}
    candidates = [("gain-offset", False, False), ("gain-plane", True, False)]
    if preserve_calibrated_scale:
        candidates.extend([("fixed-gain-offset", False, True), ("fixed-gain-plane", True, True)])
    for name, plane, fixed_gain in candidates:
        proposal, reason = _candidate(
            accepted, reference, count, plane=plane, fixed_gain=fixed_gain
        )
        if proposal is None:
            rejected[name] = reason
        else:
            models[name] = proposal
    validation = {key: _errors(accepted, coeff, 1) for key, coeff in models.items()}
    selected = _select(
        validation, (("standard", 0.95), ("gain-offset", 0.95), ("gain-plane", 0.85))
    )
    hashes = {p.name: sha256(p.rgb.astype("<f8").tobytes()).hexdigest() for p in panels}
    report: dict[str, object] = {
        "components": [[names[i] for i in group] for group in groups],
        "reference": names[reference[0]],
        "edges": [
            dict(
                panels=[names[i] for i in e.indices],
                counts=e.counts,
                blocks=e.blocks,
                qualified=e.qualified,
            )
            for e in edges
        ],
        "scored_edges": [[names[i] for i in edge.indices] for edge in accepted],
        "coefficients": {
            key: dict(zip(names, coeff.tolist(), strict=True)) for key, coeff in models.items()
        },
        "selection_rgb_p95": validation,
        "test_rgb_p95": {key: _errors(accepted, coeff, 2) for key, coeff in models.items()},
        "selected": selected,
        **(
            {
                "fixed_gain_selected": _select(
                    validation, (("fixed-gain-offset", 0.95), ("fixed-gain-plane", 0.85))
                )
            }
            if preserve_calibrated_scale
            else {}
        ),
        "unavailable_candidates": rejected,
        "sample_rgb_sha256": hashes,
    }
    if stellar_apertures is not None:
        stellar = qualify_gains(report, stellar_apertures, additional=additional_gains)
        eligible = stellar["eligible"]
        assert isinstance(eligible, list)
        stellar["selected"] = _select(
            {model: scores for model, scores in validation.items() if model in eligible},
            (
                ("standard", 0.95),
                ("fixed-gain-offset", 0.95),
                ("gain-offset", 0.95),
                ("fixed-gain-plane", 0.85),
                ("gain-plane", 0.85),
            ),
        )
        report["stellar_gain"] = stellar
    return report


def measure_controls(crop: Values) -> dict[str, object]:
    report: dict[str, object] = {}
    for name, chain, plane in (("chain", True, False), ("cycle", False, True)):
        panels, x, y, truth = _control(crop, chain=chain, plane=plane)
        result = measure(panels, x, y)
        reordered = measure([panels[i] for i in (2, 4, 1, 0, 3)], x, y)
        if result != reordered:
            raise ValueError("Reordering panels changed the frozen overlap result.")
        # Keep all fitted variants in the report, including any unselected simpler result.
        candidates = result["coefficients"]
        selected = result["selected"]
        assert isinstance(candidates, dict) and isinstance(selected, str)
        coefficients = np.asarray(list(candidates[selected].values()), dtype=np.float64)
        metrics = _control_metrics(crop, panels, x, y, truth, coefficients[:3])
        report[name] = dict(
            result,
            known_coefficients=truth.tolist(),
            metrics=metrics,
            verified_order_independence=True,
        )
    return report


def measure_project(
    project_path: Path,
    *,
    panel_names: tuple[str, ...] | None = None,
    preserve_calibrated_scale: bool = False,
    stellar_gain: bool = False,
    additional_gains: Mapping[str, Coefficients] | None = None,
) -> dict[str, object]:
    project = load_project(project_path)
    records = sorted(
        (
            p
            for p in project.panels
            if p.include_sky and (panel_names is None or p.source.path.name.upper() in panel_names)
        ),
        key=lambda p: p.source.path.name.upper(),
    )
    names = tuple(p.source.path.name.upper() for p in records)
    if panel_names is not None and names != panel_names:
        raise ValueError("The saved project must include all named sky panels.")
    if len(names) < 3 or len(set(names)) != len(names):
        raise ValueError("Use three or more sky panels with distinct file names.")
    inputs = {"manifest": project_path}
    bands = set()
    for record in records:
        inputs.update(
            {f"{record.source.path.name}/{role}": ref.path for role, ref in record.references()}
        )
        for role, ref in record.references():
            if ref.status() != "Ready":
                raise ValueError(
                    f"{record.source.path.name}: {role} reference is unavailable or changed."
                )
        profile = record.photo_profile or project.photo_settings.profile
        if profile.path is not None:
            inputs[f"{record.source.path.name}/ICC profile"] = profile.path
    hashes = {key: _digest(path) for key, path in inputs.items()}
    target = PanelGeometry(project.render.output_wcs(), ICRS())
    region = project.render.output_region()
    samples = ((region.width + 3) // 8) * ((region.height + 3) // 8)
    if not samples or samples * len(records) * 128 > _BUDGET:
        raise ValueError("Use a saved comparison grid with a bounded sample count.")
    y, x = np.mgrid[4 : region.height : 8, 4 : region.width : 8]
    x, y = x.ravel(), y.ravel()
    panels = []
    apertures: dict[str, list[Aperture]] | None = {} if stellar_gain else None
    # Visit detector windows in shared 64-pixel target blocks to bound each source read.
    block_ids = y // 64 * (int(x.max()) // 64 + 1) + x // 64
    order = np.argsort(block_ids, kind="stable")
    blocks = np.split(order, np.flatnonzero(np.diff(block_ids[order])) + 1)
    for record in records:
        with open_panel(
            record.source.path, max_tile_bytes=_BUDGET, sky_mask=record.sky_input(), keep_icc=True
        ) as source:
            bands.add(record.sky_band(source.descriptor.filter_name, project.filter_name))
            if len(bands) > 1:
                raise ValueError("Compare sky panels from a single band.")
            width, height = source.descriptor.width, source.descriptor.height
            if record.wcs_sidecar is not None:
                geometry, _ = load_solution(record.wcs_sidecar.path, source)
            else:
                geometry = read_panel_geometry(source.header, width, height)
            color = resolve_photo_profile(
                source, record.photo_profile, project.photo_settings.profile
            )
            panel = PhotoPanel(
                record.source.path, PhotoTileSource(source, color, _BUDGET), geometry, color, 0.0
            )
            if apertures is not None:
                apertures[panel.path.name] = measure_apertures(
                    panel.source, geometry, target, (region.width, region.height), _BUDGET
                )
            bounds = projected_bounds(geometry, target, width, height)
            rgb, xy = np.full((len(x), 3), np.nan), np.zeros((len(x), 2))
            for block in blocks:
                bx, by = x[block], y[block]
                if bounds is not None and (
                    bx.max() < bounds[0] - 8
                    or bx.min() > bounds[2] + 8
                    or by.max() < bounds[1] - 8
                    or by.min() > bounds[3] + 8
                ):
                    continue
                sky = TileSky.from_pixels(target, bx.astype(np.float64), by.astype(np.float64))
                sampled = _sample_panel(panel, sky, len(block), _BUDGET // 2)
                if sampled is None:
                    raise ValueError("A sample block exceeds the reference byte budget.")
                sx, sy, _ = sky.in_panel(geometry, (0, 0))
                xy[block] = np.stack((2 * sx / (width - 1) - 1, 2 * sy / (height - 1) - 1), axis=-1)
                rgb[block] = sampled[0]
            rgb[(rgb @ LUMINANCE) > 0.075] = np.nan
            panels.append(PanelSamples(record.source.path.name, rgb, xy))
    if hashes != {key: _digest(path) for key, path in inputs.items()}:
        raise ValueError("A source or project reference changed during sampling.")
    report = measure(
        panels,
        x,
        y,
        preserve_calibrated_scale=preserve_calibrated_scale,
        stellar_apertures=apertures,
        additional_gains=additional_gains,
    )
    reordered = measure(
        panels[::-1],
        x,
        y,
        preserve_calibrated_scale=preserve_calibrated_scale,
        stellar_apertures=apertures,
        additional_gains=additional_gains,
    )
    if report != reordered:
        raise ValueError("Reversing input order changed the reference result.")
    return dict(
        report,
        input_sha256=hashes,
        verified_order_independence=True,
        grid_xy=[region.width, region.height],
        step_pixels=8,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("owner", type=Path, help="Frozen original 20.TIF.")
    real = parser.add_mutually_exclusive_group()
    real.add_argument("--pa4", type=Path, help="Saved PA4 sky project for the real overlap replay.")
    real.add_argument("--project", type=Path, help="Saved independent RGB sky network to compare.")
    parser.add_argument(
        "--preserve-calibrated-scale",
        action="store_true",
        help="Also compare offsets and planes at fixed unity gain on a calibrated project.",
    )
    parser.add_argument(
        "--stellar-gain",
        action="store_true",
        help="Require independent stellar support for inferred relative gains in --project.",
    )
    parser.add_argument(
        "--audit-standard-export",
        type=Path,
        help="Score gains from the current application's Standard JSON export of --project.",
    )
    parser.add_argument("-o", "--output", type=Path, help="Write a new local JSON report.")
    args = parser.parse_args()
    if args.preserve_calibrated_scale and args.project is None:
        parser.error("--preserve-calibrated-scale requires --project.")
    if args.stellar_gain and args.project is None:
        parser.error("--stellar-gain requires --project.")
    if args.audit_standard_export is not None and not args.stellar_gain:
        parser.error("--audit-standard-export requires --stellar-gain.")
    if _digest(args.owner) != _OWNER_HASH:
        raise ValueError("Use the frozen owner original for the 8D controls.")
    image = tifffile.memmap(args.owner, mode="r")
    crop = _decode(image[1408:1920, 2048:2816])
    del image
    report = {"schema_version": 1, "crop_source_sha256": _OWNER_HASH, **measure_controls(crop)}
    if args.pa4 is not None:
        report["pa4"] = measure_project(args.pa4, panel_names=_PA4)
    if args.project is not None:
        additional = None
        if args.audit_standard_export is not None:
            exported = json.loads(args.audit_standard_export.read_bytes())
            photo = exported["photo"]
            if (
                exported["command"] != "project export-photo"
                or exported["status"] != "ok"
                or Path(exported["project"]).resolve() != args.project.resolve()
                or photo["requested_brightness"] != "standard"
                or photo["requested_exposure"] != "off"
                or exported["grid"] != "saved"
            ):
                raise ValueError(
                    "Use a saved-grid Standard export with exposure Off for this project."
                )
            additional = {
                "application-standard": {
                    item["panel"]: (item["brightness"]["gain"],) for item in photo["panels"]
                }
            }
        report["project"] = measure_project(
            args.project,
            preserve_calibrated_scale=args.preserve_calibrated_scale,
            stellar_gain=args.stellar_gain,
            additional_gains=additional,
        )
    if _digest(args.owner) != _OWNER_HASH:
        raise ValueError("The owner original changed during reference sampling.")
    payload = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        with atomic_binary_file(args.output) as stream:
            stream.write(payload.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
