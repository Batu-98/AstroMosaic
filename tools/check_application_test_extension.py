"""Run selected application cases and independently reopen their exports."""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import numpy as np
import tifffile
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS
from astropy.wcs.utils import wcs_to_celestial_frame
from prepare_application_test_fixtures import digest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests" / "numerical"))
from xisf_reference import read_xisf_attachments  # noqa: E402


@dataclass(frozen=True)
class Product:
    name: str
    suffix: str
    project: str = "project.astromosaic"
    layer: str = "sky"
    band: str | None = None
    members: tuple[int, ...] = ()


def products(case: dict) -> list[Product]:
    if case.get("bands"):
        return [
            Product(
                f"sky-{item['tag']}",
                item["suffix"],
                band=item["label"],
                members=tuple(item["panels"]),
            )
            for item in case["bands"]
        ]
    suffix = case.get("sky_suffix", "fits" if case["images"][0]["channels"] == 1 else "tiff")
    result = [Product("sky", suffix, members=tuple(range(1, len(case["images"]) + 1)))]
    if case.get("foreground_overlap"):
        result.extend(
            Product(layer, "tiff", layer=layer) for layer in ("foreground", "composition")
        )
    if case.get("gap_project"):
        result.append(Product("composition-gap", "tiff", case["gap_project"], layer="composition"))
    return result


def read_raster(path: Path) -> tuple[np.ndarray, list[np.ndarray], fits.Header]:
    if path.suffix == ".fits":
        with fits.open(path, memmap=False) as hdus:
            return hdus[0].data, [ext.data for ext in hdus[1:]], hdus[0].header
    if path.suffix == ".xisf":
        (pixels, *masks), xml = read_xisf_attachments(path)
        header = fits.Header()
        for element in xml.findall("{http://www.pixinsight.com/xisf}FITSKeyword"):
            name, value = element.attrib["name"], element.attrib["value"]
            if name not in {"HISTORY", "COMMENT"}:
                header.append(fits.Card.fromstring(f"{name:8}= {value}"))
        return pixels, masks, header
    with tifffile.TiffFile(path) as tiff:
        page = tiff.pages[0]
        header = fits.Header.fromstring(page.description.split("\n", 1)[1], sep="\n")
        return page.asarray(), [child.asarray() for child in page.pages or ()], header


def reference_grid(grid: dict) -> WCS:
    wcs = WCS(naxis=2)
    projection = grid["projection"]
    wcs.wcs.ctype = [f"RA---{projection}", f"DEC--{projection}"]
    wcs.wcs.radesys = "ICRS"
    wcs.wcs.crval = grid["center_deg"]
    x, y, *_ = grid.get("crop_xywh", (0, 0))
    wcs.wcs.crpix = (np.asarray(grid["size_xy"]) + 1) / 2 - [x, y]
    wcs.wcs.cdelt = np.array([-1, 1]) * grid["scale_arcsec"] / 3600
    angle = np.deg2rad(grid.get("rotation_deg", 0))
    wcs.wcs.pc = [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
    return wcs


def check_directions(wcs: WCS, coverage: np.ndarray, directions: SkyCoord) -> None:
    x, y = wcs.world_to_pixel(directions)
    xi, yi = np.rint(x).astype(int), np.rint(y).astype(int)
    height, width = coverage.shape
    assert ((xi >= 0) & (xi < width) & (yi >= 0) & (yi < height)).all()
    assert coverage[yi, xi].all()
    assert wcs.pixel_to_world(x, y).separation(directions).deg.max() <= 1e-9


def sample_panel(
    path: Path, labels: Path | None, world: SkyCoord
) -> tuple[np.ndarray, np.ndarray, np.ndarray, WCS]:
    data, masks, header = read_raster(path)
    height, width = data.shape[:2]
    valid = np.isfinite(data)
    if valid.ndim == 3:
        valid = valid.all(axis=-1)
    if masks:
        valid &= masks[0] == 1
    if labels is not None:
        valid &= fits.getdata(labels) == 1
    wcs = WCS(header).celestial
    sky = world.transform_to(wcs_to_celestial_frame(wcs)).spherical
    lon, lat = sky.lon.deg, sky.lat.deg
    x, y = wcs.all_world2pix(lon, lat, 0, quiet=True, maxiter=45, tolerance=1e-8)
    near = np.isfinite(x) & np.isfinite(y) & (x >= -1) & (y >= -1) & (x <= width) & (y <= height)
    backwards_lon, backwards_lat = wcs.all_pix2world(x[near], y[near], 0)
    delta_lon = (backwards_lon - lon[near] + 180) % 360 - 180
    near[near] &= np.hypot(delta_lon, backwards_lat - lat[near]) <= 1e-6
    interior = near & (x > 1) & (y > 1) & (x < width - 2) & (y < height - 2)
    safe = ~near | interior
    positions = np.flatnonzero(interior)
    px, py = x[positions], y[positions]
    x0, y0 = np.floor(px).astype(int), np.floor(py).astype(int)
    corners = ((y0, x0), (y0, x0 + 1), (y0 + 1, x0), (y0 + 1, x0 + 1))
    valid_corners = np.stack([valid[corner] for corner in corners], axis=0)
    safe[positions] = valid_corners.all(axis=0) | ~valid_corners.any(axis=0)
    supported = valid_corners.all(axis=0)
    contributes = np.zeros(x.shape, dtype=bool)
    contributes[positions[supported]] = True

    dx, dy = (px - x0)[supported, None], (py - y0)[supported, None]
    weights = [(1 - dx) * (1 - dy), dx * (1 - dy), (1 - dx) * dy, dx * dy]
    if data.ndim == 2:
        data = data[..., None]
    values = np.zeros((x.size, data.shape[2]), dtype=np.float64)
    values[contributes] = sum(
        weight * data[corner][supported] for weight, corner in zip(weights, corners, strict=True)
    )
    return values, contributes, safe, wcs


def check_sky(
    case: dict,
    product: Product,
    folder: Path,
    pixels: np.ndarray,
    coverage: np.ndarray,
    header: fits.Header,
) -> dict:
    grid = case["render_grid"]
    _, _, width, height = grid.get("crop_xywh", [0, 0, *grid["size_xy"]])
    assert coverage.shape == (height, width)
    wcs, expected_wcs = WCS(header).celestial, reference_grid(grid)
    x = [0, width - 1, 0, width - 1, (width - 1) / 2]
    y = [0, 0, height - 1, height - 1, (height - 1) / 2]
    error = wcs.pixel_to_world(x, y).separation(expected_wcs.pixel_to_world(x, y)).deg.max()
    assert error <= 1e-9
    yy, xx = np.mgrid[6:height:13, 8:width:13]
    yy, xx = yy.ravel(), xx.ravel()
    world = wcs.pixel_to_world(xx, yy)
    expected = np.zeros((xx.size, 1 if pixels.ndim == 2 else 3))
    denominator = np.zeros(xx.size)
    stable = np.ones(xx.size, dtype=bool)
    all_samples = []
    for index in product.members:
        item = case["images"][index - 1]
        labels = folder / item["label_mask"] if "label_mask" in item else None
        values, support, safe, source_wcs = sample_panel(folder / item["file"], labels, world)
        weight = case.get("weights", [1] * len(case["images"]))[index - 1]
        expected += weight * values
        denominator += weight * support
        stable &= safe
        all_samples.append((values, support, source_wcs))
    np.testing.assert_array_equal(coverage[yy[stable], xx[stable]], denominator[stable] > 0)
    match = stable & (denominator > 0)
    assert np.count_nonzero(match) >= 200
    actual = pixels[yy[match], xx[match]].reshape(expected[match].shape)
    expected = expected[match] / denominator[match, None]
    np.testing.assert_allclose(actual, expected, rtol=2e-7, atol=2e-6)
    result = {
        "sample_positions": len(actual),
        "max_sample_error": float(np.max(np.abs(actual - expected))),
        "wcs_error_deg": float(error),
    }
    for sample in case.get("pixel_checks", ()):
        x, y = sample["pixel_xy"]
        assert bool(coverage[y, x]) == sample["covered"]
        if sample["covered"]:
            np.testing.assert_allclose(pixels[y, x], sample["value"], rtol=0, atol=2e-6)
    if case.get("archive_files"):
        assert header["FILTER"] == "Ks" and header["BUNIT"] == "DN"
        correlations = []
        for (a, support_a, _), (b, support_b, _) in zip(
            all_samples[:-1], all_samples[1:], strict=True
        ):
            shared = support_a & support_b
            bright = shared & (a[:, 0] >= np.percentile(a[shared, 0], 85))
            assert bright.sum() >= 20
            correlations.append(float(np.corrcoef(a[bright, 0], b[bright, 0])[0, 1]))
        assert min(correlations) >= 0.8
        result["atlas_bright_overlap_correlations"] = correlations
    if case.get("panel_b_rotation_deg"):
        check_directions(wcs, coverage, SkyCoord([0, 90, 180, 270], [89.98] * 4, unit="deg"))
        result["covered_polar_directions"] = 4
    if matrix := case.get("panel_b_to_a_matrix"):
        a, b = (entry[2].pixel_scale_matrix for entry in all_samples)
        np.testing.assert_allclose(np.linalg.solve(a, b), matrix, rtol=0, atol=1e-10)
    if distortion := case.get("sip_radial_coefficient"):
        sip = all_samples[1][2].sip
        assert sip is not None and sip.a_order == sip.b_order == 3
        np.testing.assert_allclose([sip.a[3, 0], sip.b[0, 3]], distortion, rtol=0, atol=1e-16)
        check_directions(wcs, coverage, SkyCoord([359.8, 0.2], [18.0, 18.0], unit="deg"))
        result["sip_order"] = 3
    if product.band:
        unit = next(item["unit"] for item in case["bands"] if item["label"] == product.band)
        assert header["FILTER"] == product.band and header["BUNIT"] == unit
    return result


def check_export(case: dict, product: Product, folder: Path, output: Path, report: dict) -> dict:
    pixels, masks, header = read_raster(output)
    coverage = masks[0]
    assert pixels.dtype.kind == "f" and pixels.dtype.itemsize == 4
    assert coverage.dtype == np.uint8 and set(np.unique(coverage)) <= {0, 1}
    assert coverage.shape == pixels.shape[:2] == (report["height"], report["width"])
    assert 0 < int(coverage.sum()) == report["covered_pixels"]
    assert np.isfinite(pixels[coverage == 1]).all() and np.isnan(pixels[coverage == 0]).all()
    result = {"covered_pixels": report["covered_pixels"]}
    if product.layer == "sky":
        assert len(masks) == 1
        result.update(check_sky(case, product, folder, pixels, coverage, header))
    elif product.layer == "foreground":
        assert len(masks) == 1 and not header.get("CTYPE1", "").startswith("RA---")
    else:
        contribution = masks[1]
        assert len(masks) == 2 and contribution.dtype == np.uint8
        np.testing.assert_array_equal(coverage, contribution != 0)
        codes = set(np.unique(contribution))
        expected_codes = {0, 1, 2} if product.name == "composition-gap" else {0, 1, 2, 3}
        assert codes == expected_codes, (product.name, codes)
        common = report["common_pixels"]
        assert (common == 0) == (product.name == "composition-gap")
        result.update(
            common_pixels=common,
            contribution_counts=np.bincount(contribution.ravel(), minlength=4).tolist(),
        )
    return result


def invoke(launcher: list[str], args: list[str], logs: Path, name: str) -> dict:
    start = perf_counter()
    result = subprocess.run([*launcher, *args, "--json"], capture_output=True, timeout=90)
    (logs / f"{name}.json").write_bytes(result.stdout)
    (logs / f"{name}.stderr").write_bytes(result.stderr)
    report = json.loads(result.stdout)
    if result.returncode or report["status"] != "ok":
        raise RuntimeError(
            f"{name} failed with exit {result.returncode}. See {logs / (name + '.json')}"
        )
    return report | {"elapsed_seconds": round(perf_counter() - start, 3)}


def check_fixture_hashes(folder: Path, case: dict) -> None:
    for image in case["images"]:
        assert digest(folder / image["file"]) == image["sha256"]
        if "label_mask" in image:
            assert digest(folder / image["label_mask"]) == image["label_sha256"]


def run_cases(launcher: list[str], cases: list[tuple[Path, dict]], output: Path) -> None:
    output.mkdir(parents=True)
    report = []
    for folder, case in cases:
        name = case["case"]
        start = perf_counter()
        here = output / name
        here.mkdir()
        check_fixture_hashes(folder, case)
        required = [entry for entry in case.get("sky_pairs", ()) if entry["required"]]
        assert case["sky_overlap"]["percent_of_smaller_support"] >= 10
        assert all(item["percent_of_smaller_support"] >= 10 for item in required)
        if case.get("foreground_overlap"):
            assert case["foreground_overlap"]["percent_of_smaller_support"] >= 10
        if stored_bands := case.get("bands"):
            saved = invoke(
                launcher, ["project", "bands", str(folder / case["project"])], here, "bands"
            )
            assert saved["bands"] == [
                {"band": b["label"], "panels": b["panels"]} for b in stored_bands
            ]
        results = []
        for product in products(case):
            project = folder / product.project
            destination = here / f"{product.name}.{product.suffix}"
            cli_args = [str(project), "-o", str(destination)]
            if product.band:
                cli_args += ["--band", product.band]
            if product.layer == "sky":
                preflight = invoke(
                    launcher, ["project", "validate", *cli_args], here, f"{product.name}-validate"
                )
                assert preflight["panels"] == len(product.members)
            rendered = invoke(
                launcher,
                ["project", "export", *cli_args, "--layer", product.layer, "--progress"],
                here,
                f"{product.name}-export",
            )
            assert rendered["peak_reserved_bytes"] <= 128 * 1024**2
            result = check_export(case, product, folder, destination, rendered)
            results.append({"product": destination.name, **result})
        check_fixture_hashes(folder, case)
        assert not list(here.glob("*.part"))
        report.append(
            {
                "case": name,
                "status": "pass",
                "seconds": round(perf_counter() - start, 3),
                "products": results,
            }
        )
        (output / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"{name} passed with {len(results)} verified exports.", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--fixtures", type=Path, default=Path("data/application-tests/extended"))
    selection.add_argument(
        "--case-manifest", type=Path, help="Run only the case in this case.json."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--launcher", type=Path, help="Use a built astromosaic-cli executable.")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new results directory.")
    launcher = (
        [str(args.launcher.resolve())] if args.launcher else [sys.executable, "-m", "astromosaic"]
    )
    if args.case_manifest is not None:
        manifest = args.case_manifest.resolve()
        cases = [(manifest.parent, json.loads(manifest.read_bytes()))]
    else:
        fixtures = args.fixtures.resolve()
        pack = json.loads((fixtures / "fixtures.json").read_bytes())["cases"]
        assert len(pack) == 10
        cases = [(fixtures / case["case"], case) for case in pack]
    run_cases(launcher, cases, args.output.resolve())


if __name__ == "__main__":
    main()
