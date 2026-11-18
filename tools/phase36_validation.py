"""Measure independent local-catalog errors of a saved candidate WCS.

Native fit membership is unknown. These are independent catalog checks, not
held-out fit residuals or a replacement for the future production quality gate.
"""

import argparse
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS, NoConvergence
from scipy.spatial import cKDTree

from astromosaic.astrometry.astap_catalog import query_astap_cone
from astromosaic.astrometry.stars import measure_stars
from astromosaic.core.job import JobContext
from astromosaic.io import open_panel


def validate_candidate(
    image: Path, candidate: Path, catalog: Path, database: str
) -> dict[str, object]:
    start = perf_counter()
    with open_panel(image) as panel:
        stars = measure_stars(panel, 64 * 1024**2, JobContext()).stars
        width, height = panel.descriptor.width, panel.descriptor.height
    if not stars:
        raise ValueError("The image has no usable isolated stars for catalog validation.")
    xy = np.array([(star.x, star.y) for star in stars], dtype=np.float64)
    header = fits.Header.fromstring(candidate.read_text("ascii"))
    header["NAXIS"], header["NAXIS1"], header["NAXIS2"] = 2, width, height
    wcs = WCS(header).celestial
    center = SkyCoord(*wcs.all_pix2world((width - 1) / 2, (height - 1) / 2, 0), unit="deg")
    corners = SkyCoord(
        *wcs.all_pix2world([0, width - 1, 0, width - 1], [0, 0, height - 1, height - 1], 0),
        unit="deg",
    )
    radius = float(np.max(center.separation(corners).deg)) + 0.01
    divisions = 9 if radius > 10 else 1
    image_tree = cKDTree(xy)
    pairs: list[tuple[float, int, str, float]] = []
    read_bytes = 0
    epoch: float | None = None
    tile_names: set[str] = set()
    considered = 0
    for row in range(divisions):
        for col in range(divisions):
            left, right = width * col / divisions, width * (col + 1) / divisions
            top, bottom = height * row / divisions, height * (row + 1) / divisions
            indexes = np.flatnonzero(
                (xy[:, 0] >= left) & (xy[:, 0] < right) & (xy[:, 1] >= top) & (xy[:, 1] < bottom)
            )
            if not len(indexes):
                continue
            local_center = SkyCoord(
                *wcs.all_pix2world((left + right) / 2, (top + bottom) / 2, 0), unit="deg"
            )
            local_corners = SkyCoord(
                *wcs.all_pix2world([left, right, left, right], [top, top, bottom, bottom], 0),
                unit="deg",
            )
            local_radius = float(np.max(local_center.separation(local_corners).deg)) + 0.03
            cone = query_astap_cone(
                catalog,
                database,
                (float(local_center.ra.deg), float(local_center.dec.deg)),
                local_radius,
                max_stars=100_000,
                max_read_bytes=64 * 1024**2 - read_bytes,
            )
            read_bytes += cone.read_bytes
            tile_names.update(cone.tiles)
            if epoch is not None and epoch != cone.epoch_year:
                raise ValueError("The regional queries have inconsistent catalog epochs.")
            epoch = cone.epoch_year
            if not cone.stars:
                continue
            coordinates = np.array(
                [(star.ra_deg, star.dec_deg) for star in cone.stars], dtype=np.float64
            )
            sky = SkyCoord(coordinates[:, 0], coordinates[:, 1], unit="deg")
            try:
                cat_xy = np.column_stack(wcs.all_world2pix(sky.ra.deg, sky.dec.deg, 0))
            except NoConvergence as error:
                cat_xy = error.best_solution
                for failed in (error.divergent, error.slow_conv):
                    if failed is not None:
                        cat_xy[failed] = np.nan
            inside = np.flatnonzero(
                np.all(np.isfinite(cat_xy), axis=1)
                & (cat_xy[:, 0] >= max(0, left - 3))
                & (cat_xy[:, 0] < min(width, right + 3))
                & (cat_xy[:, 1] >= max(0, top - 3))
                & (cat_xy[:, 1] < min(height, bottom + 3))
            )
            if divisions > 1:
                # Avoid chance associations with the many faint catalog stars
                # absent from a wide-field list of bright measured sources.
                inside = np.array(
                    sorted(inside, key=lambda i: cone.stars[i].magnitude)[
                        : max(30, 3 * len(indexes))
                    ]
                )
            if not len(inside):
                continue
            considered += len(inside)
            cat_xy = cat_xy[inside]
            distance, nearest = cKDTree(cat_xy).query(xy[indexes], k=1)
            _, reverse = image_tree.query(cat_xy, k=1)
            keep = (distance < 3) & (reverse[nearest] == indexes)
            found = indexes[keep]
            cat_indexes = inside[nearest[keep]]
            predicted = SkyCoord(*wcs.all_pix2world(*xy[found].T, 0), unit="deg")
            separations = np.asarray(predicted.separation(sky[cat_indexes]).arcsec)
            for d, index, ci, error_arcsec in zip(
                distance[keep], found, cat_indexes, separations, strict=True
            ):
                pairs.append((float(d), int(index), cone.stars[ci].identifier, float(error_arcsec)))
    selected_pairs: list[tuple[float, int, str, float]] = []
    used_catalog: set[str] = set()
    for pair in sorted(pairs):
        if pair[2] not in used_catalog:
            selected_pairs.append(pair)
            used_catalog.add(pair[2])
    if not selected_pairs:
        raise ValueError("No unique mutual catalog matches lie within three source pixels.")
    selected = np.array([pair[1] for pair in selected_pairs])
    matched = xy[selected]
    errors = np.array([pair[3] for pair in selected_pairs])
    errors_px = np.array([pair[0] for pair in selected_pairs])
    regions: list[dict[str, object]] = []
    for row in range(3):
        for col in range(3):
            active = (
                (matched[:, 0] >= width * col / 3)
                & (matched[:, 0] < width * (col + 1) / 3)
                & (matched[:, 1] >= height * row / 3)
                & (matched[:, 1] < height * (row + 1) / 3)
            )
            local = errors[active]
            regions.append(
                {
                    "row": row,
                    "column": col,
                    "matches": len(local),
                    "support": "measured" if len(local) >= 5 else "insufficient",
                    "rms_arcsec": float(np.sqrt(np.mean(local**2))) if len(local) >= 5 else None,
                    "p95_arcsec": float(np.percentile(local, 95)) if len(local) >= 5 else None,
                    "rms_source_px": float(np.sqrt(np.mean(errors_px[active] ** 2)))
                    if len(local) >= 5
                    else None,
                    "p95_source_px": float(np.percentile(errors_px[active], 95))
                    if len(local) >= 5
                    else None,
                }
            )
    fine_regions: list[dict[str, object]] = []
    for row in range(9):
        for col in range(9):
            selected_cell = (
                (matched[:, 0] >= width * col / 9)
                & (matched[:, 0] < width * (col + 1) / 9)
                & (matched[:, 1] >= height * row / 9)
                & (matched[:, 1] < height * (row + 1) / 9)
            )
            count = int(np.count_nonzero(selected_cell))
            fine_regions.append(
                {
                    "row": row,
                    "column": col,
                    "matches": count,
                    "support": "measured" if count >= 5 else "insufficient",
                    "p95_source_px": float(np.percentile(errors_px[selected_cell], 95))
                    if count >= 5
                    else None,
                }
            )
    outer = (
        (matched[:, 0] < width * 0.2)
        | (matched[:, 0] > width * 0.8)
        | (matched[:, 1] < height * 0.2)
        | (matched[:, 1] > height * 0.8)
    )
    return {
        "evidence_kind": "independent-catalog-check; native-fit-membership-unknown",
        "measured_stars": len(stars),
        "catalog_candidates_considered": considered,
        "unique_matches": len(selected),
        "rms_arcsec": float(np.sqrt(np.mean(errors**2))),
        "p95_arcsec": float(np.percentile(errors, 95)),
        "max_arcsec": float(np.max(errors)),
        "rms_source_px": float(np.sqrt(np.mean(errors_px**2))),
        "p95_source_px": float(np.percentile(errors_px, 95)),
        "outer_matches": int(np.count_nonzero(outer)),
        "outer_p95_source_px": float(np.percentile(errors_px[outer], 95))
        if np.any(outer)
        else None,
        "catalog_epoch_year": epoch,
        "catalog_tiles": sorted(tile_names),
        "catalog_read_bytes": read_bytes,
        "query_grid_divisions": divisions,
        "wide_field_catalog_selection": "brightest max(30, 3 * detections) per cell"
        if divisions > 1
        else "all projected catalog stars",
        "match_radius_source_px": 3,
        "elapsed_seconds": perf_counter() - start,
        "regions_3x3": regions,
        "regions_9x9": fine_regions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--wcs", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--database", default="d05")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate_candidate(args.image, args.wcs, args.catalog, args.database)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()
