"""Build ten additional labeled cases for the AstroMosaic application runbook."""

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from functools import partial
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS, Sip
from PIL import Image
from prepare_application_test_fixtures import (
    IRSA,
    Matrix,
    Panel,
    Pixels,
    Size,
    atlas_panels,
    crop,
    fixture_grid,
    make_project,
    mixed_project,
    panel_grid,
    prepare_sources,
    render_spec,
    scene_mask,
    sky_field,
    write_case,
    write_panel,
)
from scipy.ndimage import gaussian_filter, map_coordinates

from astromosaic.core import Region, Tile
from astromosaic.io.xisf_export import open_xisf_mosaic
from astromosaic.storage.project import MosaicProject, save_project

ARCHIVES = {
    "ki1350092.fits": (
        IRSA + "&scan=135&name=ki1350092.fits",
        "5423804b5e26ce030feb3d3de29308bb5675edadf3604ea2337a555a8a32335e",
    ),
    "ki1420186.fits": (
        IRSA + "&scan=142&name=ki1420186.fits",
        "bb37ab1a0032fa4f8cc6b44575ed9b519a65a7e79dd3b534e1a9fd6670ea7183",
    ),
    "ki1430092.fits": (
        IRSA + "&scan=143&name=ki1430092.fits",
        "bac11ca10347e897b0eedb1ac07e021add3f9e83406a19be0901897dc3a8baa4",
    ),
}
type PreparedCase = tuple[list[Panel], MosaicProject, dict[str, object]]
type PixelChecks = Mapping[Size, float | tuple[float, float, float] | None]


def sample_checks(values: PixelChecks) -> list[dict[str, object]]:
    return [
        {"pixel_xy": list(position), "value": value, "covered": value is not None}
        for position, value in values.items()
    ]


def mono_field(size: Size, seed: int) -> Pixels:
    return np.mean(sky_field(size, seed), axis=2, dtype=np.float32)


def rotation(deg: float) -> Matrix:
    angle = np.deg2rad(deg)
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, -s], [s, c]])


def warped_panel(
    path: Path,
    parent: WCS,
    master: Pixels,
    size: Size,
    center: Size,
    matrix: Matrix,
    *,
    distortion: float = 0.0,
) -> Panel:
    offset = tuple(np.asarray(center) - matrix @ ((np.asarray(size) - 1) / 2))
    wcs = panel_grid(parent, offset, matrix)
    y, x = np.mgrid[: size[1], : size[0]].astype(np.float64)
    if distortion:
        dx, dy = x - (wcs.wcs.crpix[0] - 1), y - (wcs.wcs.crpix[1] - 1)
        squared_radius = dx**2 + dy**2
        x += distortion * dx * squared_radius
        y += distortion * dy * squared_radius
        a, b = np.zeros((4, 4)), np.zeros((4, 4))
        a[3, 0] = a[1, 2] = b[2, 1] = b[0, 3] = distortion
        wcs.wcs.ctype = ["RA---TAN-SIP", "DEC--TAN-SIP"]
        wcs.sip = Sip(a, b, None, None, wcs.wcs.crpix)
    gx = matrix[0, 0] * x + matrix[0, 1] * y + offset[0]
    gy = matrix[1, 0] * x + matrix[1, 1] * y + offset[1]
    channels = [master] if master.ndim == 2 else list(np.moveaxis(master, -1, 0))
    sampled = [
        map_coordinates(channel, (gy, gx), order=1, cval=np.nan, prefilter=False)
        for channel in channels
    ]
    data = sampled[0] if master.ndim == 2 else np.stack(sampled, axis=-1)
    return Panel(path, data, wcs)


def atlas_chain(folder: Path, source: Path) -> PreparedCase:
    spec = render_spec((275.1229, -16.007), (1470, 1330), 1.0)
    panels, zero_point = atlas_panels(folder, source, tuple(ARCHIVES), "atlas")
    return (
        panels,
        make_project(panels, spec, relative=True),
        {
            "archive_files": list(ARCHIVES),
            "common_magzp": zero_point,
            "credit": "2MASS · UMass and IPAC/Caltech · NASA and NSF",
        },
    )


def north_pole(folder: Path) -> PreparedCase:
    spec = replace(render_spec((359.1, 89.76), (976, 650), 5.0), rotation_deg=17.0)
    parent = fixture_grid(spec)
    field = mono_field(spec.size, seed=20405)
    offset, size = (42, 72), (618, 490)
    panels = [
        Panel(
            folder / "A-polar-reference.fits", crop(field, offset, size), panel_grid(parent, offset)
        ),
        warped_panel(
            folder / "B-polar-rotated.fits", parent, field, (540, 442), (682, 336), rotation(26)
        ),
    ]
    for panel in panels:
        write_panel(panel)
    return panels, make_project(panels, spec, relative=False), {"panel_b_rotation_deg": 26}


def mixed_scale(folder: Path) -> PreparedCase:
    spec = render_spec((201.37, 47.20), (1060, 660), 0.92)
    parent = fixture_grid(spec)
    field = mono_field(spec.size, seed=20406)
    offset, size = (88, 126), (565, 392)
    matrix = rotation(-23) @ np.array([[1.52, 0.30], [0, 1.15]])
    panels = [
        Panel(
            folder / "A-narrow-reference.fits",
            crop(field, offset, size),
            panel_grid(parent, offset),
        ),
        warped_panel(
            folder / "B-coarse-skewed.fits", parent, field, (472, 318), (704, 345), matrix
        ),
    ]
    for panel in panels:
        write_panel(panel)
    return (
        panels,
        make_project(panels, spec, relative=False),
        {"panel_b_to_a_matrix": matrix.tolist()},
    )


def wide_distortion(folder: Path) -> PreparedCase:
    spec = render_spec((358.5, 18.0), (1260, 750), 186.0)
    parent = fixture_grid(spec)
    field = sky_field(spec.size, seed=20407)
    offset, size = (41, 82), (746, 550)
    distortion = -1.5e-7
    panels = [
        Panel(folder / "A-wide-TAN.tiff", crop(field, offset, size), panel_grid(parent, offset)),
        warped_panel(
            folder / "B-wide-SIP3.tiff",
            parent,
            field,
            (730, 530),
            (847, 382),
            rotation(9),
            distortion=distortion,
        ),
    ]
    for panel in panels:
        write_panel(panel, band="RGB")
    zea = replace(spec, projection="ZEA")
    return panels, make_project(panels, zea, relative=False), {"sip_radial_coefficient": distortion}


def write_scaled_panel(
    path: Path,
    wcs: WCS,
    raw: np.ndarray,
    scale: float,
    zero: float,
    blank: int,
) -> Panel:
    image = fits.PrimaryHDU(raw, header=wcs.to_header())
    image.header.update(BSCALE=scale, BZERO=zero, BLANK=blank, FILTER="L", BUNIT="MJy/sr")
    image.writeto(path)
    physical = raw.astype(np.float32) * scale + zero
    physical[raw == blank] = np.nan
    return Panel(path, physical, wcs)


def scaled_fits(folder: Path) -> PreparedCase:
    spec = render_spec((271.5, -30.9), (766, 398), 2.0)
    parent = fixture_grid(spec)
    field = mono_field(spec.size, seed=20408) * 780
    size, first, second = (448, 298), (20, 32), (282, 38)
    raw_a = np.rint((crop(field, first, size) - 12) / 0.25).astype(np.int16)
    raw_b = np.rint((crop(field, second, size) + 2) / 0.5).astype(np.int16)
    blank = -32768
    raw_a[18, 20], raw_a[20, 20] = -68, -48
    raw_a[88, 313], raw_b[82, 51] = 8, 30
    raw_a[107, 365], raw_b[101, 103] = blank, 24
    raw_a[250:255, 12:19] = blank
    panels = [
        write_scaled_panel(
            folder / "A-scaled-int16.fits", panel_grid(parent, first), raw_a, 0.25, 12, blank
        ),
        write_scaled_panel(
            folder / "B-scaled-int16.fits", panel_grid(parent, second), raw_b, 0.5, -2, blank
        ),
    ]
    project = make_project(panels, spec, relative=False)
    project = replace(project, panels=(project.panels[0], replace(project.panels[1], weight=3.0)))
    checks = sample_checks(
        {(40, 50): -5, (40, 52): 0, (333, 120): 13.25, (385, 139): 10, (35, 285): None}
    )
    return panels, project, {"weights": [1, 3], "pixel_checks": checks}


def xisf_holes(folder: Path) -> PreparedCase:
    spec = render_spec((316.0, 42.7), (650, 650), 195.0)
    parent = fixture_grid(spec)
    master = sky_field(spec.size, seed=20409)
    size, first, second = (525, 372), (44, 32), (82, 239)
    upper, lower = crop(master, first, size), crop(master, second, size)
    upper[288, 436] = (0, 0.5, 2)
    lower[75:88, 393:411] = 80
    lower[288:310, 58:78] = 80
    lower[316, 233] = (-0.02, 0, 2.45)
    coverage = np.ones(lower.shape[:2], dtype=bool)
    coverage[75:88, 393:411] = False
    coverage[288:310, 58:78] = False
    tiff = Panel(folder / "A-upper-rgb.tiff", upper, panel_grid(parent, first))
    wcs = panel_grid(parent, second)
    xisf = Panel(folder / "B-lower-rgb.xisf", np.where(coverage[..., None], lower, np.nan), wcs)
    write_panel(tiff, band="RGB")
    header = wcs.to_header()
    header.update(FILTER="RGB", BUNIT="MJy/sr")
    with open_xisf_mosaic(xisf.path, *xisf.size, 3, header, 8 * 1024**2) as writer:
        writer.write(Tile(Region(0, 0, *xisf.size), lower, coverage))
    panels = [tiff, xisf]
    checks = sample_checks(
        {(480, 320): (0, 0.5, 2), (150, 539): None, (315, 555): (-0.02, 0, 2.45)}
    )
    return (
        panels,
        make_project(panels, spec, relative=False),
        {
            "pixel_checks": checks,
            "sky_suffix": "xisf",
        },
    )


def bands(folder: Path) -> PreparedCase:
    full = replace(
        render_spec((2.1, -29.0), (858, 492), 3.4),
        projection="ZEA",
        rotation_deg=11.0,
    )
    parent = fixture_grid(full)
    spec = replace(full, crop=Region(22, 24, 806, 436))
    size = (500, 365)
    mono, rgb = mono_field(full.size, 20410), sky_field(full.size, 20411)
    layout = [
        ("A-ha-west.fits", mono, (38, 57), "H-alpha", "MJy/sr"),
        ("B-ha-east.fits", mono, (304, 69), "", "MJy/sr"),
        ("C-oiii-west.tiff", rgb, (54, 75), "O III", "Jy/sr"),
        ("D-oiii-east.tiff", rgb, (327, 103), "O III", "Jy/sr"),
    ]
    panels = []
    for name, field, offset, band, unit in layout:
        panel = Panel(folder / name, crop(field, offset, size), panel_grid(parent, offset))
        write_panel(panel, band=band, unit=unit)
        panels.append(panel)
    project = make_project(panels, spec, relative=False)
    a, b, c, d = project.panels
    project = replace(project, panels=(a, replace(b, band_override="H-alpha"), c, d))
    return (
        panels,
        project,
        {
            "bands": [
                {
                    "label": "H-alpha",
                    "tag": "ha",
                    "panels": [1, 2],
                    "suffix": "fits",
                    "unit": "MJy/sr",
                },
                {
                    "label": "O III",
                    "tag": "oiii",
                    "panels": [3, 4],
                    "suffix": "tiff",
                    "unit": "Jy/sr",
                },
            ],
        },
    )


def nightscape(
    folder: Path,
    *,
    seed: int,
    feature: str,
    frame: Size,
    tile: Size,
    ground_origins: Sequence[Size],
    sky_origins: Sequence[Size],
    lift: int,
    amplitude: float,
) -> PreparedCase:
    spec = render_spec((345.0 + seed % 11, 19.0), frame, 194.0)
    parent = fixture_grid(spec)
    sky = sky_field(frame, seed)
    rng = np.random.default_rng(seed + 1)
    width, height = frame
    y, x = np.ogrid[:height, :width]
    horizon = (
        height * 0.52
        + amplitude * np.sin(x[0] / 109 + seed)
        + 18 * np.cos(x[0] / 49)
        + 5 * np.sin(x[0] / 12)
    )
    relief = np.clip((y - horizon) / 110, 0, 1)
    grain = gaussian_filter(rng.standard_normal((height, width)), 2.4)
    ridges = np.sin(x / 34 + y / 27) * np.cos(x / 66 - y / 39)
    shades = 0.022 + relief * 0.025 + 0.065 * grain + 0.009 * ridges
    lights = np.zeros_like(shades)
    for cx, cy in zip(
        rng.integers(width, size=17), rng.integers(height * 2 // 3, height, size=17), strict=True
    ):
        lights += np.exp(-(((x - cx) / 5) ** 2 + ((y - cy) / 3) ** 2))
    ground = np.stack(
        (0.77 * shades + 0.23 * lights, shades + 0.11 * lights, 0.87 * shades + 0.06 * lights),
        axis=-1,
    ).astype(np.float32)
    panels = []
    for label, g, s in zip("ABC"[: len(ground_origins)], ground_origins, sky_origins, strict=True):
        terrain = g[1] + np.arange(tile[1])[:, None] >= horizon[g[0] : g[0] + tile[0]]
        samples = np.where(terrain[..., None], crop(ground, g, tile), crop(sky, s, tile))
        panel = Panel(
            folder / f"{label}-{feature}.tiff",
            samples,
            panel_grid(parent, s),
            scene_mask(horizon, g, tile, gap=5),
        )
        write_panel(panel, band="RGB")
        panels.append(panel)
    aligned, details = mixed_project(
        folder, make_project(panels, spec, False), panels, ground_origins, lift
    )
    details.update(unaligned_project="unaligned.astromosaic", sky_origins_xy=list(sky_origins))
    return panels, aligned, details


def cropped_seam(folder: Path) -> PreparedCase:
    panels, project, details = nightscape(
        folder,
        seed=20413,
        feature="valley",
        frame=(1150, 667),
        tile=(660, 505),
        ground_origins=((54, 40), (380, 36)),
        sky_origins=((54, 40), (380, 36)),
        lift=23,
        amplitude=42,
    )
    settings = project.composition
    assert settings is not None
    x, y = settings.placement.offset
    gap = replace(
        settings,
        sky_crop_bottom=project.render.size[1] - 249,
        placement=replace(settings.placement, offset=(x, y + 90)),
    )
    save_project(folder / "project-gap.astromosaic", replace(project, composition=gap))
    details["gap_project"] = "project-gap.astromosaic"
    return panels, project, details


def prepare_pack(output: Path, source: Path) -> None:
    builders = [
        (
            "sky04-atlas-chain",
            "SKY-04 · Three 2MASS tiles with narrow overlaps",
            partial(atlas_chain, source=source),
        ),
        ("sky05-polar-rotation", "SKY-05 · North celestial pole and rotated TAN", north_pole),
        ("sky06-mixed-scale", "SKY-06 · Narrow field with unequal scales and skew", mixed_scale),
        ("sky07-wide-sip", "SKY-07 · Wide TAN-SIP to ZEA", wide_distortion),
        ("sky08-scaled-fits", "SKY-08 · Scaled FITS, BLANK and weighted overlap", scaled_fits),
        ("sky09-xisf-holes", "SKY-09 · Vertical TIFF and XISF with coverage holes", xisf_holes),
        ("sky10-filter-bands", "SKY-10 · H-alpha and O III on the same cropped ZEA grid", bands),
        (
            "mix03-diagonal-ground",
            "MIX-03 · Nightscape with diagonal foreground shifts",
            partial(
                nightscape,
                seed=20412,
                feature="ridge",
                frame=(1160, 650),
                tile=(630, 510),
                ground_origins=((388, 97), (100, 52)),
                sky_origins=((428, 90), (146, 61)),
                lift=28,
                amplitude=31,
            ),
        ),
        ("mix04-cropped-seam", "MIX-04 · Nightscape with an adjustable sky crop", cropped_seam),
        (
            "mix05-panel-chain",
            "MIX-05 · Three-panel nightscape chain",
            partial(
                nightscape,
                seed=20414,
                feature="foothills",
                frame=(1450, 655),
                tile=(640, 500),
                ground_origins=((44, 58), (402, 83), (780, 58)),
                sky_origins=((54, 58), (415, 58), (778, 78)),
                lift=23,
                amplitude=41,
            ),
        ),
    ]
    output.mkdir(parents=True)
    contact = Image.new("RGB", (1040, len(builders) * 285))
    records = []
    for index, (name, title, prepare) in enumerate(builders):
        folder = output / name
        folder.mkdir()
        panels, project, details = prepare(folder)
        if len(panels) == 4:
            links = ((0, 1), (2, 3))
        else:
            links = tuple((i, i + 1) for i in range(len(panels) - 1))
        record, row = write_case(
            folder,
            title,
            panels,
            project,
            details,
            str(details.get("credit", "")),
            links=links,
        )
        records.append(record)
        contact.paste(row, (0, index * 285))
    contact.save(output / "contact-sheet.png")
    (output / "fixtures.json").write_text(
        json.dumps({"cases": records, "public_sources": ARCHIVES}, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/application-tests/extended"))
    parser.add_argument("--source-dir", type=Path, default=Path("data/application-test-sources"))
    parser.add_argument(
        "--download", action="store_true", help="Fetch the three pinned 2MASS tiles."
    )
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new fixture output directory.")
    prepare_sources(args.source_dir, args.download, ARCHIVES)
    prepare_pack(args.output, args.source_dir)


if __name__ == "__main__":
    main()
