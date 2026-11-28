"""Compare candidate detector-edge sampling with a dense WCS reference."""

import argparse
import json
import tracemalloc
from dataclasses import replace
from pathlib import Path
from statistics import median
from time import perf_counter

import numpy as np
from astropy.wcs import WCS
from astropy.wcs.utils import wcs_to_celestial_frame
from numpy.typing import NDArray

from astromosaic.astrometry.solve import load_solution
from astromosaic.core.job import JobContext
from astromosaic.geometry import PanelGeometry, read_panel_geometry
from astromosaic.storage.project import load_project, open_project_sky_panel

SAMPLES_PER_EDGE = (17, 33, 65)
REFERENCE_SAMPLES = 4097


def detector_edges(width: int, height: int, count: int) -> NDArray[np.float64]:
    x = np.linspace(-0.5, width - 0.5, count)
    y = np.linspace(-0.5, height - 0.5, count)
    top, bottom = np.full(count, y[0]), np.full(count, y[-1])
    left, right = np.full(count, x[0]), np.full(count, x[-1])
    return np.stack(((x, top), (right, y), (x, bottom), (left, y))).transpose(0, 2, 1)


def project_edges(
    source: PanelGeometry, target: PanelGeometry, size: tuple[int, int], count: int
) -> NDArray[np.float64]:
    edges = detector_edges(*size, count).reshape(-1, 2)
    return target.inverse(source.forward(edges[:, 0], edges[:, 1])).reshape(4, count, 2)


def reference_edges(source: WCS, target: WCS, size: tuple[int, int]) -> NDArray[np.float64]:
    edges = detector_edges(*size, REFERENCE_SAMPLES)
    sky = source.pixel_to_world(*edges.transpose(2, 0, 1))
    return np.stack(target.world_to_pixel(sky), axis=-1)


def maximum_deviation(samples: NDArray[np.float64], reference: NDArray[np.float64]) -> float:
    intervals = samples.shape[1] - 1
    segment = np.minimum(
        np.arange(REFERENCE_SAMPLES) * intervals // (REFERENCE_SAMPLES - 1), intervals - 1
    )
    start = samples[:, segment]
    delta = samples[:, segment + 1] - start
    relative = reference - start
    fraction = np.sum(relative * delta, axis=-1) / np.sum(delta * delta, axis=-1)
    return float(
        np.linalg.norm(relative - np.clip(fraction, 0, 1)[..., None] * delta, axis=-1).max()
    )


def measure(path: Path, *, zea: bool) -> dict[str, object]:
    project = load_project(path)
    grid = replace(project.render, projection="ZEA") if zea else project.render
    output_wcs = grid.output_wcs()
    target = PanelGeometry(output_wcs, wcs_to_celestial_frame(output_wcs))
    context = JobContext()
    inputs = []
    for index in project.sky_indices():
        panel = project.panels[index]
        with open_project_sky_panel(panel, grid.max_working_bytes, context) as source:
            size = (source.descriptor.width, source.descriptor.height)
            if panel.wcs_sidecar is not None:
                if panel.wcs_sidecar.status() != "Ready":
                    raise ValueError(f"Unavailable WCS for panel {index + 1}.")
                geometry, _ = load_solution(panel.wcs_sidecar.path, source)
            else:
                geometry = read_panel_geometry(source.header, *size)
        reference = reference_edges(geometry.wcs, target.wcs, size)
        if not np.isfinite(reference).all():
            raise ValueError(f"Projection contains an unsafe edge for panel {index + 1}.")
        inputs.append((geometry, size, reference))
    measurements = []
    for count in SAMPLES_PER_EDGE:

        def sample_all(count: int = count) -> list[NDArray[np.float64]]:
            return [project_edges(source, target, size, count) for source, size, _ in inputs]

        samples = sample_all()
        errors = [
            maximum_deviation(sample, data[2]) for sample, data in zip(samples, inputs, strict=True)
        ]
        timings = []
        for _ in range(12):
            start = perf_counter()
            sample_all()
            timings.append((perf_counter() - start) * 1000)
        tracemalloc.start()
        try:
            sample_all()
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        measurements.append(
            {
                "vertices_per_panel": count * 4,
                "max_error_output_px": round(max(errors), 6),
                "median_ms": round(median(timings), 3),
                "max_ms": round(max(timings), 3),
                "peak_traced_bytes": peak,
            }
        )
    return {
        "projection": grid.projection,
        "size": grid.size,
        "source_sizes": [size for _, size, _ in inputs],
        "distorted_panels": sum(source.wcs.has_distortion for source, _, _ in inputs),
        "reference_samples_per_edge": REFERENCE_SAMPLES,
        "measurements": measurements,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--zea", action="store_true", help="Project onto ZEA using the saved grid.")
    args = parser.parse_args()
    print(json.dumps(measure(args.project.resolve(), zea=args.zea), indent=2))


if __name__ == "__main__":
    main()
