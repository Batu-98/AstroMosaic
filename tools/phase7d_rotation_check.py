"""Replay the 7D camera-model comparison on the frozen real observations."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, replace
from hashlib import file_digest, sha256
from itertools import combinations
from pathlib import Path
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

from astromosaic.astrometry.hints import read_optics
from astromosaic.core import Region
from astromosaic.io import open_panel
from astromosaic.storage.project import load_project

type Array = NDArray[np.float64]
type Mask = NDArray[np.bool_]
type Lens = Literal["fixed", "focal", "radial"]
type Pixels = tuple[float, float]
type Pair = tuple[int, int]

_ROOT = Path(__file__).resolve().parents[1]
_FROZEN = _ROOT / "output/application-tests/phase7a"
_DATA = _ROOT / "data/application-tests/phase7a"
_LIMIT_PX = 2.0
_INVERSE_LIMIT_PX = 0.001
_LENS_LIMITS = {"focal": 0.02, "radial": 0.02}


@dataclass(frozen=True)
class Camera:
    """Rectilinear intrinsics in the calibration raster and an exact raster mapping."""

    sensor_size: tuple[int, int]
    focal: Pixels
    center: Pixels
    brown: tuple[float, float, float, float, float] = (0, 0, 0, 0, 0)
    clockwise: bool = False
    crop: Pixels = (0, 0)
    scale: Pixels = (1, 1)

    @property
    def size(self) -> tuple[int, int]:
        return self.sensor_size[::-1] if self.clockwise else self.sensor_size

    def adjusted(self, lens: Lens, value: float) -> Camera:
        if lens == "focal":
            return replace(self, focal=(self.focal[0] * (1 + value), self.focal[1] * (1 + value)))
        if lens == "radial":
            k1, k2, p1, p2, k3 = self.brown
            return replace(self, brown=(k1 + value, k2, p1, p2, k3))
        return self

    def to_sensor(self, xy: Array) -> Array:
        raster = (xy + 0.5) / self.scale - 0.5 + self.crop
        if not self.clockwise:
            return raster
        x, y = raster.T
        return np.column_stack((y, self.sensor_size[1] - 1 - x))

    def from_sensor(self, xy: Array) -> Array:
        if self.clockwise:
            x, y = xy.T
            xy = np.column_stack((self.sensor_size[1] - 1 - y, x))
        return ((xy - self.crop) + 0.5) * self.scale - 0.5

    def distortion(self, xy: Array) -> tuple[Array, Array]:
        x, y = xy.T
        k1, k2, p1, p2, k3 = self.brown
        r2 = x * x + y * y
        radial = 1 + r2 * (k1 + r2 * (k2 + r2 * k3))
        slope = 2 * (k1 + r2 * (2 * k2 + r2 * 3 * k3))
        points = np.column_stack(
            (
                x * radial + 2 * p1 * x * y + p2 * (r2 + 2 * x * x),
                y * radial + p1 * (r2 + 2 * y * y) + 2 * p2 * x * y,
            )
        )
        cross = x * y * slope + 2 * (p1 * x + p2 * y)
        jacobian = np.stack(
            (
                np.column_stack((radial + x * x * slope + 2 * p1 * y + 6 * p2 * x, cross)),
                np.column_stack((cross, radial + y * y * slope + 6 * p1 * y + 2 * p2 * x)),
            ),
            axis=1,
        )
        return points, jacobian

    def rays(self, pixels: Array) -> Array:
        distorted = (self.to_sensor(pixels) - self.center) / self.focal
        xy = distorted.copy()
        if any(self.brown):
            for _ in range(12):
                model, jacobian = self.distortion(xy)
                delta = np.linalg.solve(jacobian, (model - distorted)[..., None])[..., 0]
                xy -= delta
                if np.max(np.abs(delta)) < 1e-12:
                    break
            else:
                raise ValueError("Brown distortion inverse did not converge.")
        result = np.column_stack((xy, np.ones(len(xy))))
        return result / np.linalg.norm(result, axis=1, keepdims=True)

    def project(self, rays: Array) -> Array:
        if not np.isfinite(rays).all() or np.any(rays[:, 2] <= 1e-8):
            raise ValueError("A projected ray is outside the front-facing rectilinear domain.")
        plane = rays[:, :2] / rays[:, 2, None]
        distorted = self.distortion(plane)[0]
        return self.from_sensor(distorted * self.focal + self.center)


@dataclass(frozen=True)
class Edge:
    left: Array
    right: Array
    names: tuple[str, ...]
    zones: NDArray[np.str_]
    training: Mask
    repeat: Array


def _read_json(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _sha(path: Path) -> str:
    with path.open("rb") as source:
        return file_digest(source, "sha256").hexdigest()


def _verified_inputs(include_pa4: bool) -> dict[str, str]:
    lock = _read_json(_FROZEN / "reference-lock.json")
    expected = {}
    for group in ("passta-calibrated-panning", "middlebury-depth-change"):
        expected.update(lock["controls"][group])
    for file in ("passta-orientation.json", "middlebury-depth.json"):
        expected[(_FROZEN / file).relative_to(_ROOT).as_posix()] = lock["measurement_reports"][
            file
        ]["sha256"]
    if include_pa4:
        expected.update(lock["controls"]["pa4-ground"])
        for file, digest in (
            ("pa4-followup.json", lock["measurement_reports"]["pa4-followup.json"]["sha256"]),
            (
                "landmark-comparison-checked.json",
                lock["prior_reports"]["landmark-comparison-checked.json"],
            ),
        ):
            expected[(_FROZEN / file).relative_to(_ROOT).as_posix()] = digest
    for name, digest in expected.items():
        if _sha(_ROOT / name) != digest:
            raise ValueError(f"Frozen input changed: {name}")
    return expected


def _passta() -> tuple[dict[Pair, Edge], dict[int, Camera]]:
    directory = _DATA / "passta-lunch-room"
    # Use the archived calibration in its 5472 × 3648 sensor coordinates.
    # Its checksum is checked before fitting.
    calibration_text = (directory / "Calibration.txt").read_text(encoding="ascii")
    values = {
        key: float(value)
        for key, value in re.findall(
            r"\b(Fx|Fy|Cx|Cy|K[123]|P[12]):\s*(-?\d+(?:\.\d+)?)", calibration_text
        )
    }
    camera = Camera(
        (5472, 3648),
        (values["Fx"], values["Fy"]),
        (values["Cx"], values["Cy"]),
        (values["K1"], values["K2"], values["P1"], values["P2"], values["K3"]),
        clockwise=True,
    )
    report = _read_json(_FROZEN / "passta-orientation.json")
    edges = {}
    frames = ("01", "03", "05")
    for a, b in combinations(range(3), 2):
        key = f"{frames[a]}-{frames[b]}"
        rows = [r for r in report["measured"] if r[key] and r[key]["passes"]]
        edges[a, b] = Edge(
            np.asarray(
                [r["01_xy"] if a == 0 else r["01-03"]["primary"]["moving_xy"] for r in rows]
            ),
            np.asarray([r[key]["primary"]["moving_xy"] for r in rows]),
            tuple(r["landmark"] for r in rows),
            np.asarray([r["zone"] for r in rows]),
            np.asarray([r["split"] == "fit" for r in rows]),
            np.asarray([r[key]["repeat_px"] for r in rows]),
        )
    return edges, {i: camera for i in range(3)}


def _point_edge(rows: list[Any], left_key: str, zone_key: str, repeat_key: str) -> Edge:
    return Edge(
        np.asarray([r[left_key] for r in rows]),
        np.asarray([r["primary"]["moving_xy"] for r in rows]),
        tuple(r["id"] for r in rows),
        np.asarray([r[zone_key] for r in rows]),
        np.asarray([r["split"] == "fit" for r in rows]),
        np.asarray([r[repeat_key] for r in rows]),
    )


def _adirondack() -> tuple[dict[Pair, Edge], dict[int, Camera]]:
    text = (_DATA / "middlebury-adirondack/calib.txt").read_text(encoding="ascii")
    params = dict(line.split("=", 1) for line in text.splitlines() if line)
    size = (int(params["width"]), int(params["height"]))
    cameras = {}
    for i in range(2):
        k = [float(v) for v in params[f"cam{i}"].strip("[]").replace(";", " ").split()]
        cameras[i] = Camera(size, (k[0], k[4]), (k[2], k[5]))
    rows = [r for r in _read_json(_FROZEN / "middlebury-depth.json")["marks"] if r.get("used")]
    return {(0, 1): _point_edge(rows, "left_xy", "depth_group", "repeat_px")}, cameras


def _transfer(rotation: Rotation, left: Camera, right: Camera, a: Array, b: Array) -> Array:
    return np.stack(
        (
            right.project(rotation.apply(left.rays(a))) - b,
            left.project(rotation.inv().apply(right.rays(b))) - a,
        ),
        axis=1,
    )


def _spread(points: Array) -> float:
    return float(
        np.linalg.svd(points - points.mean(axis=0), compute_uv=False)[-1] / len(points) ** 0.5
    )


def _relative_fits(
    edges: dict[Pair, Edge], cameras: dict[int, Camera], selected: dict[Pair, Mask], loss: str
) -> dict[Pair, tuple[float, Rotation]]:
    relative = {}
    for (i, j), edge in edges.items():
        train = selected[i, j]
        a, b = edge.left[train], edge.right[train]
        if len(a) < 3 or min(_spread(a), _spread(b)) < 8:
            raise ValueError(f"Edge {i}-{j} has insufficient two-dimensional training support.")
        left, right = cameras[i], cameras[j]
        seed = Rotation.align_vectors(right.rays(b), left.rays(a))[0]

        def objective(
            vector: Array, left: Camera = left, right: Camera = right, a: Array = a, b: Array = b
        ) -> Array:
            return _transfer(Rotation.from_rotvec(vector), left, right, a, b).ravel()

        fit = least_squares(objective, seed.as_rotvec(), loss=loss, f_scale=_LIMIT_PX, max_nfev=80)
        if not fit.success:
            raise ValueError(f"Edge {i}-{j} did not converge.")
        relative[i, j] = (
            float(np.percentile(np.linalg.norm(fit.fun.reshape(-1, 2), axis=1), 95)),
            Rotation.from_rotvec(fit.x),
        )
    return relative


def _seed_poses(relative: dict[Pair, tuple[float, Rotation]], anchor: int) -> dict[int, Rotation]:
    links: dict[int, list[tuple[int, Rotation]]] = defaultdict(list)
    for (a, b), (_, rotation) in sorted(relative.items(), key=lambda item: item[1][0]):
        links[a].append((b, rotation.inv()))
        links[b].append((a, rotation))
    poses = {anchor: Rotation.identity()}
    pending = deque([anchor])
    while pending:
        parent = pending.popleft()
        for child, to_parent in links[parent]:
            if child not in poses:
                poses[child] = poses[parent] * to_parent
                pending.append(child)
    return poses


def _loss_stats(values: Array) -> dict[str, float]:
    return {
        "median_px": float(np.median(values)),
        "rms_px": float(np.sqrt(np.mean(values**2))),
        "p95_px": float(np.percentile(values, 95)),
    }


def _direction_stats(vectors: Array) -> dict[str, Any]:
    errors = np.linalg.norm(vectors, axis=2)
    return {
        "count": len(errors),
        "forward": _loss_stats(errors[:, 0]),
        "reverse": _loss_stats(errors[:, 1]),
        "bidirectional": _loss_stats(errors.max(axis=1)),
    }


def _rotation_fit(
    edges: dict[Pair, Edge],
    cameras: dict[int, Camera],
    lens: Lens = "fixed",
    *,
    anchor: int = 0,
    omitted_zone: str | None = None,
    loss: str = "linear",
) -> tuple[dict[Pair, Array], dict[int, Rotation], dict[int, Camera], dict[str, Any]]:
    train = {pair: edge.training & (edge.zones != omitted_zone) for pair, edge in edges.items()}
    relative = _relative_fits(edges, cameras, train, loss)
    seeds = _seed_poses(relative, anchor)
    if seeds.keys() != cameras.keys():
        raise ValueError("The rotation graph is disconnected.")
    free = sorted(cameras.keys() - {anchor})
    start = np.concatenate([seeds[i].as_rotvec() for i in free])
    pose_count = len(start)
    margin = np.full(pose_count, np.deg2rad(15))
    low, high = start - margin, start + margin
    if lens != "fixed":
        start, low, high = np.r_[start, 0], np.r_[low, -1], np.r_[high, 1]

    def state(x: Array) -> tuple[dict[int, Rotation], dict[int, Camera], float]:
        poses = {anchor: Rotation.identity()} | {
            i: Rotation.from_rotvec(vector)
            for i, vector in zip(free, x[:pose_count].reshape(-1, 3), strict=True)
        }
        value = float(x[-1] * _LENS_LIMITS[lens]) if lens != "fixed" else 0.0
        return poses, {i: camera.adjusted(lens, value) for i, camera in cameras.items()}, value

    def objective(x: Array) -> Array:
        poses, lenses, _ = state(x)
        return np.concatenate(
            [
                _transfer(
                    poses[j].inv() * poses[i],
                    lenses[i],
                    lenses[j],
                    edge.left[train[i, j]],
                    edge.right[train[i, j]],
                ).ravel()
                for (i, j), edge in edges.items()
            ]
        )

    fit = least_squares(
        objective, start, bounds=(low, high), loss=loss, f_scale=_LIMIT_PX, max_nfev=100
    )
    singular = np.linalg.svd(fit.jac, compute_uv=False)
    if not fit.success or singular[-1] <= singular[0] * 1e-5:
        raise ValueError(
            "The anchored camera fit did not converge with a well-conditioned Jacobian."
        )
    poses, lenses, value = state(fit.x)
    vectors = {
        (i, j): _transfer(poses[j].inv() * poses[i], lenses[i], lenses[j], edge.left, edge.right)
        for (i, j), edge in edges.items()
    }
    loops = [
        float(
            np.degrees(
                (relative[a, c][1].inv() * relative[b, c][1] * relative[a, b][1]).magnitude()
            )
        )
        for a, b, c in combinations(sorted(cameras), 3)
        if all(pair in relative for pair in ((a, b), (a, c), (b, c)))
    ]
    info = {
        "anchor": anchor,
        "loss": loss,
        "adjustment": value,
        "at_adjustment_bound": bool(lens != "fixed" and abs(fit.x[-1]) > 0.999),
        "jacobian_condition": float(singular[0] / singular[-1]),
        "independent_loop_degrees": loops,
        "pair_degrees": {
            f"{a}-{b}": float(np.degrees((poses[b].inv() * poses[a]).magnitude())) for a, b in edges
        },
    }
    return vectors, poses, lenses, info


def _planar_fit(edges: dict[Pair, Edge], panel_count: int, similarity: bool) -> dict[Pair, Array]:
    # Diagnostic least squares on the same training landmarks, even where
    # the normal 7B admission gate rejects a link before graph refinement.
    basis = 2 if similarity else 1
    size = sum(np.count_nonzero(edge.training) for edge in edges.values())
    matrix = np.zeros((size, basis * (panel_count - 1)), dtype=np.complex128)
    target = np.zeros(size, dtype=np.complex128)
    start = 0
    for (a, b), edge in edges.items():
        left = edge.left[edge.training] @ np.array((1, 1j))
        right = edge.right[edge.training] @ np.array((1, 1j))
        rows = slice(start, start + len(left))
        start += len(left)
        for panel, sign, xy in ((a, 1, left), (b, -1, right)):
            if panel:
                col = basis * (panel - 1)
                matrix[rows, col] = sign
                if similarity:
                    matrix[rows, col + 1] = sign * xy
        target[rows] = right - left
    solve, _, rank, _ = np.linalg.lstsq(matrix, target, rcond=None)
    if rank != matrix.shape[1]:
        raise ValueError("The planar diagnostic graph is rank deficient.")
    offsets = np.r_[0j, solve[::basis]]
    scales = np.r_[1 + 0j, solve[1::basis] + 1] if similarity else np.ones(panel_count)
    result = {}
    for (a, b), edge in edges.items():
        left, right = (xy @ np.array((1, 1j)) for xy in (edge.left, edge.right))
        delta = scales[a] * left + offsets[a] - scales[b] * right - offsets[b]
        forward, reverse = delta / scales[b], -delta / scales[a]
        result[a, b] = np.stack(
            (
                np.column_stack((forward.real, forward.imag)),
                np.column_stack((reverse.real, reverse.imag)),
            ),
            axis=1,
        )
    return result


def _validate_ground(name: str, edges: dict[Pair, Edge], cameras: dict[int, Camera]) -> None:
    project = load_project(_DATA / name / "foreground.astromosaic")
    masks = dict(project.foreground_inputs())
    for index, camera in cameras.items():
        points = np.unique(
            np.concatenate(
                [
                    edge.left if i == index else edge.right
                    for (i, j), edge in edges.items()
                    if index in (i, j)
                ]
            ),
            axis=0,
        )
        source = project.panels[index].source
        with open_panel(source.path, foreground_mask=masks[index]) as reader:
            size = reader.descriptor.width, reader.descriptor.height
            if reader.descriptor.fingerprint != source.fingerprint or size != camera.size:
                raise ValueError(f"Panel {index + 1} differs from the frozen project.")
            for x, y in points:
                x0, y0 = int(np.floor(x)), int(np.floor(y))
                if not reader.read_tile(
                    Region(x0, y0, int(np.ceil(x)) - x0 + 1, int(np.ceil(y)) - y0 + 1)
                ).valid.all():
                    raise ValueError(f"Panel {index + 1} contains a landmark outside valid ground.")


def _maximum_distance(a: Array, b: Array) -> float:
    return float(np.max(np.linalg.norm(a - b, axis=1)))


def _frame_grid(camera: Camera, count: int) -> Array:
    width, height = camera.size
    x, y = np.meshgrid(np.linspace(0, width - 1, count), np.linspace(0, height - 1, count))
    return np.column_stack((x.ravel(), y.ravel()))


def _boundary(camera: Camera, count: int = 33) -> Array:
    pixels = _frame_grid(camera, count).reshape(count, count, 2)
    return np.concatenate((pixels[0], pixels[-1], pixels[1:-1, 0], pixels[1:-1, -1]))


def _camera_checks(camera: Camera) -> dict[str, Any]:
    width, height = camera.size
    grid = _frame_grid(camera, 17)
    rays = camera.rays(grid)
    jacobian = camera.distortion(rays[:, :2] / rays[:, 2, None])[1]
    extrema = np.array(
        [
            (0, (height - 1) / 2),
            (width - 1, (height - 1) / 2),
            ((width - 1) / 2, 0),
            ((width - 1) / 2, height - 1),
            (0, 0),
            (width - 1, height - 1),
            (0, height - 1),
            (width - 1, 0),
        ]
    )
    sides = camera.rays(extrema)
    angles = np.degrees(np.arccos(np.clip((sides[::2] * sides[1::2]).sum(axis=1), -1, 1)))
    return {
        "raster_horizontal_fov_deg": float(angles[0]),
        "raster_vertical_fov_deg": float(angles[1]),
        "max_diagonal_fov_deg": float(max(angles[2:])),
        "min_brown_jacobian_determinant": float(np.min(np.linalg.det(jacobian))),
        "sensor_inverse_max_px": _maximum_distance(camera.project(rays), grid),
    }


def _edge_checks(source: Camera, target: Camera, rotation: Rotation) -> dict[str, Any]:
    boundary = _boundary(source)
    rotated = rotation.apply(source.rays(boundary))
    front = rotated[:, 2] > 1e-8
    sampled = target.project(rotated[front])
    inside = np.all((sampled >= -1e-8) & (sampled <= np.array(target.size) - 1 + 1e-8), axis=1)
    source_xy = boundary[front][inside]
    maximum = None
    if len(source_xy):
        roundtrip = source.project(rotation.inv().apply(target.rays(sampled[inside])))
        maximum = _maximum_distance(roundtrip, source_xy)
    return {
        "sampled_boundary_pixels": len(boundary),
        "outside_front_domain": int((~front).sum()),
        "inside_target": int(inside.sum()),
        "overlapping_boundary_roundtrip_max_px": maximum,
    }


def _crop_check(camera: Camera, observations: Array) -> dict[str, float]:
    crop, scale = (64.0, 32.0), (0.5, 0.75)
    reduced = replace(camera, crop=crop, scale=scale)
    derived = (observations - crop + 0.5) * scale - 0.5
    reference = camera.rays(observations)
    return {
        "unit_ray_max_error": _maximum_distance(reduced.rays(derived), reference),
        "derived_raster_roundtrip_max_px": _maximum_distance(reduced.project(reference), derived),
    }


def _edge_name(pair: Pair) -> str:
    return f"{pair[0] + 1}-{pair[1] + 1}"


def _summarize(edges: dict[Pair, Edge], residuals: dict[Pair, Array]) -> dict[str, Any]:
    result = {}
    for pair, edge in edges.items():
        vectors = residuals[pair]
        result[_edge_name(pair)] = {
            "training": _direction_stats(vectors[edge.training]),
            "held_out": _direction_stats(vectors[~edge.training]),
            "repeat_p95_px": float(np.percentile(edge.repeat, 95)),
            "training_min_axis_rms_px": min(
                _spread(edge.left[edge.training]), _spread(edge.right[edge.training])
            ),
            "held_out_zones": {
                str(zone): _direction_stats(vectors[(edge.zones == zone) & ~edge.training])
                for zone in np.unique(edge.zones[~edge.training])
            },
            "points": [
                {
                    "landmark": name,
                    "zone": str(zone),
                    "training": bool(training),
                    "forward_xy": vector[0].tolist(),
                    "reverse_xy": vector[1].tolist(),
                }
                for name, zone, training, vector in zip(
                    edge.names, edge.zones, edge.training, vectors, strict=True
                )
            ],
        }
    return result


def _max_held_out(summary: dict[str, Any]) -> float:
    return float(max(pair["held_out"]["bidirectional"]["p95_px"] for pair in summary.values()))


def _passta_report() -> dict[str, Any]:
    edges, cameras = _passta()
    _validate_ground("passta-lunch-room", edges, cameras)
    results = {
        name: _summarize(edges, _planar_fit(edges, len(cameras), name == "similarity"))
        for name in ("translation", "similarity")
    }
    zones = sorted(set().union(*(set(e.zones[e.training]) for e in edges.values())))
    fits = {}
    choices: tuple[Lens, ...] = ("fixed", "focal", "radial")
    for lens in choices:
        vectors, poses, fitted, fit = _rotation_fit(edges, cameras, lens)
        validation = {}
        for zone in zones:
            vectors_without, _, _, cross = _rotation_fit(
                edges, cameras, lens, omitted_zone=str(zone)
            )
            validation[str(zone)] = {
                "adjustment": cross["adjustment"],
                "at_adjustment_bound": cross["at_adjustment_bound"],
                "omitted_training_zone": {
                    _edge_name(pair): _direction_stats(vectors_without[pair][edge.zones == zone])
                    for pair, edge in edges.items()
                    if np.any(edge.zones == zone)
                },
            }
        geometry = {
            _edge_name((source, target)): _edge_checks(
                fitted[source], fitted[target], poses[target].inv() * poses[source]
            )
            for i, j in edges
            for source, target in ((i, j), (j, i))
        }
        fit["calibration"] = asdict(fitted[0])
        fit["camera_checks"] = _camera_checks(fitted[0])
        fit["boundary_checks"] = geometry
        fit["crop_check"] = _crop_check(fitted[0], edges[0, 1].left)
        fit["leave_one_training_zone_out"] = validation
        fit["edges"] = summary = _summarize(edges, vectors)
        fit["held_out_p95_max_px"] = _max_held_out(summary)
        fit["within_pixel_gate"] = fit["held_out_p95_max_px"] <= _LIMIT_PX
        robust, _, _, _ = _rotation_fit(edges, cameras, lens, loss="soft_l1")
        fit["robust_held_out_p95_max_px"] = _max_held_out(_summarize(edges, robust))
        fit["within_geometry_gate"] = (
            fit["camera_checks"]["min_brown_jacobian_determinant"] > 0
            and fit["camera_checks"]["sensor_inverse_max_px"] <= _INVERSE_LIMIT_PX
            and fit["crop_check"]["derived_raster_roundtrip_max_px"] <= _INVERSE_LIMIT_PX
            and all(
                row["overlapping_boundary_roundtrip_max_px"] is not None
                and row["overlapping_boundary_roundtrip_max_px"] <= _INVERSE_LIMIT_PX
                for row in geometry.values()
            )
        )
        if lens == "fixed":
            alternate, _, _, _ = _rotation_fit(edges, cameras, anchor=1)
            fit["alternate_anchor_max_residual_delta_px"] = max(
                _maximum_distance(alternate[pair].reshape(-1, 2), vector.reshape(-1, 2))
                for pair, vector in vectors.items()
            )
        fits[lens] = fit
    return {
        "capture_ids": ["01", "03", "05"],
        "planar": results,
        "rotation": fits,
        "rotation_passed_pixel_and_geometry_gates": any(
            r["within_pixel_gate"] and r["within_geometry_gate"] for r in fits.values()
        ),
    }


def _adirondack_report() -> dict[str, Any]:
    edges, cameras = _adirondack()
    _validate_ground("middlebury-adirondack", edges, cameras)
    vectors, _, _, fit = _rotation_fit(edges, cameras)
    results = {
        name: _summarize(edges, _planar_fit(edges, len(cameras), name == "similarity"))
        for name in ("translation", "similarity")
    }
    results["rotation"] = _summarize(edges, vectors)
    return {
        "rotation_fit": fit,
        "published_depth_groups": _read_json(_FROZEN / "middlebury-depth.json")["depth_groups"],
        "models": results,
        "global_pose_supported": any(
            _max_held_out(summary) <= _LIMIT_PX for summary in results.values()
        ),
        "far_subset_supported": any(
            summary["1-2"]["held_out_zones"]["far"]["bidirectional"]["p95_px"] <= _LIMIT_PX
            for summary in results.values()
        ),
    }


def _pa4_report() -> dict[str, Any]:
    root = _ROOT / "data/application-tests/owner01-pa4"
    project = load_project(root / "foreground-check.astromosaic")
    measured = _read_json(_FROZEN / "landmark-comparison-checked.json")
    provenance = {r["panel"]: r for r in measured["provenance"]}
    followup = _read_json(_FROZEN / "pa4-followup.json")
    cameras = {}
    for panel in project.panels:
        name = panel.source.path.stem
        if name not in ("04", "05", "06"):
            continue
        if panel.source_mask is None:
            raise ValueError(f"PA4 panel {name} is missing its frozen source mask.")
        if (
            _sha(panel.source.path) != provenance[name]["source"]
            or sha256(panel.source_mask.labels).hexdigest() != provenance[name]["original_mask"]
        ):
            raise ValueError(f"PA4 panel {name} or its mask changed.")
        with open_panel(panel.source.path) as reader:
            metadata = read_optics(reader.header).with_overrides(panel.optics)
            length, px, py = (
                metadata.focal_length_mm,
                metadata.pixel_size_x_um,
                metadata.pixel_size_y_um,
            )
            if length is None or px is None or py is None:
                raise ValueError(
                    f"PA4 panel {name} is missing focal length or effective pixel pitch."
                )
            width, height = reader.descriptor.width, reader.descriptor.height
        cameras[name] = Camera(
            (width, height),
            (1000 * length / px, 1000 * length / py),
            ((width - 1) / 2, (height - 1) / 2),
        )

    results = {}
    sets = {
        "04-05": measured["measurements"]["pa4-04-05-visible-terrain"],
        "05-06": followup["05-06"]["measurements"],
    }
    for pair, raw in sets.items():
        a, b = pair.split("-")
        used = [row for row in raw if row["usable"]]
        edge = _point_edge(used, "reference_xy", "region", "repeat_distance_px")
        vectors, _, _, fit = _rotation_fit({(0, 1): edge}, {0: cameras[a], 1: cameras[b]})
        models = {
            name: _summarize({(0, 1): edge}, _planar_fit({(0, 1): edge}, 2, name == "similarity"))
            for name in ("translation", "similarity")
        }
        models["rotation"] = _summarize({(0, 1): edge}, vectors)
        results[pair] = {
            "metadata_intrinsics": asdict(cameras[a]),
            "joint_original_ground_count": sum(
                all(side["ground_2x2"] for side in row["original_support"]) for row in used
            ),
            "rotation_fit": fit,
            "models": {model: summary["1-2"] for model, summary in models.items()},
        }
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pa4", action="store_true", help="Include the local PA4 metadata probe.")
    args = parser.parse_args()
    inputs = _verified_inputs(args.pa4)
    result = {
        "held_out_limit_source_px": _LIMIT_PX,
        "inverse_limit_source_px": _INVERSE_LIMIT_PX,
        "input_sha256": inputs,
        "passta": _passta_report(),
        "adirondack": _adirondack_report(),
    }
    if args.pa4:
        result["pa4_metadata_probe"] = _pa4_report()
    if _verified_inputs(args.pa4) != inputs:
        raise ValueError("Frozen inputs changed while running the camera-model experiment.")
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
