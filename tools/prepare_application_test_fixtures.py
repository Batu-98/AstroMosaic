"""Prepare labeled AstroMosaic application fixtures with independently measured overlap."""

import argparse
import gzip
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from functools import partial
from hashlib import file_digest, sha256
from itertools import combinations
from pathlib import Path
from urllib.request import urlopen

import numpy as np
import tifffile
from astropy.io import fits
from astropy.wcs import WCS
from astropy.wcs.utils import wcs_to_celestial_frame
from numpy.typing import NDArray
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter, map_coordinates

from astromosaic.core import Region
from astromosaic.core.job import JobContext
from astromosaic.core.masks import (
    FOREGROUND,
    MASK_EDGE,
    SKY,
    UNCLASSIFIED,
    SourceMask,
    bounded_grid,
)
from astromosaic.pipeline.mosaic import RenderSpec
from astromosaic.storage.project import (
    FileReference,
    MosaicProject,
    ProjectPanel,
    align_project_foreground,
    propose_project_composition,
    save_project,
)

IRSA = "https://irsa.ipac.caltech.edu/cgi-bin/2MASS/IM/nph-im?ds=asky&atdir=/ti05&dh=990502s"
ARCHIVES = {
    "ki1350080.fits": (
        IRSA + "&scan=135&name=ki1350080.fits",
        "73564f04f783f0dec6c6e8edbd2db2398d00da239ea79f93844d5952822bc8cc",
    ),
    "ki1420198.fits": (
        IRSA + "&scan=142&name=ki1420198.fits",
        "7657f42211075326df65aa3d2d13b2916a666e027f2bddcf61551f7d05ef64b8",
    ),
    "eso-vlt-mw-potw-4k.tif": (
        "https://cdn.eso.org/images/publicationtiff/vlt-mw-potw.tif",
        "a35b17f33466f1b6b191d3666358eda26090f9ac433312cb4aef6f46c422a664",
    ),
}
ESO_CREDIT = "ESO/H.H. Heyer"
type Size = tuple[int, int]
type Pixels = NDArray[np.float32]
type Matrix = NDArray[np.float64]


@dataclass(frozen=True)
class Panel:
    path: Path
    pixels: Pixels
    wcs: WCS
    mask: SourceMask | None = None

    @property
    def size(self) -> Size:
        return self.pixels.shape[1], self.pixels.shape[0]

    def support(self, label: int) -> NDArray[np.bool_]:
        valid = np.isfinite(self.pixels)
        if valid.ndim == 3:
            valid = valid.all(axis=2)
        if self.mask is not None:
            valid &= self.mask.read_labels(Region(0, 0, *self.size)) == label
        return valid


type SkyFixture = tuple[list[Panel], RenderSpec, dict[str, object]]
type MixedFixture = tuple[list[Panel], RenderSpec, Size, int]


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def prepare_sources(
    directory: Path, download: bool, archives: Mapping[str, tuple[str, str]] = ARCHIVES
) -> None:
    for name, (url, expected) in archives.items():
        path = directory / name
        if not path.exists():
            if not download:
                raise FileNotFoundError(
                    f"Missing {path}. Use --download to obtain the public source."
                )
            with urlopen(url, timeout=30) as response:
                payload = response.read(20 * 1024**2)
            if payload.startswith(b"\x1f\x8b"):
                payload = gzip.decompress(payload)
            if sha256(payload).hexdigest() != expected:
                raise ValueError(f"The downloaded source did not match the pinned hash: {name}")
            directory.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(payload)
        if digest(path) != expected:
            raise ValueError(f"The cached source did not match the pinned hash: {path}")


def render_spec(center: tuple[float, float], size: Size, scale: float) -> RenderSpec:
    return RenderSpec(center, size, scale, tile_size=128, max_working_bytes=128 * 1024**2)


def fixture_grid(spec: RenderSpec) -> WCS:
    grid = WCS(naxis=2)
    grid.wcs.ctype = [f"RA---{spec.projection}", f"DEC--{spec.projection}"]
    grid.wcs.radesys = "ICRS"
    grid.wcs.crval = spec.center
    origin = (0, 0) if spec.crop is None else (spec.crop.x, spec.crop.y)
    grid.wcs.crpix = [(axis + 1) / 2 - start for axis, start in zip(spec.size, origin, strict=True)]
    grid.wcs.cdelt = [-spec.scale_arcsec / 3600, spec.scale_arcsec / 3600]
    angle = np.deg2rad(spec.rotation_deg)
    grid.wcs.pc = [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
    return grid


def panel_grid(parent: WCS, offset: tuple[float, float], transform: Matrix | None = None) -> WCS:
    # Map zero-based panel pixels to the common tangent plane, then apply FITS origin.
    matrix = np.eye(2) if transform is None else transform
    grid = parent.deepcopy()
    grid.wcs.pc = np.diag(1 / grid.wcs.cdelt) @ parent.pixel_scale_matrix @ matrix
    grid.wcs.crpix = 1 + np.linalg.solve(matrix, parent.wcs.crpix - 1 - offset)
    return grid


def write_panel(panel: Panel, *, band: str = "L", unit: str = "MJy/sr", origin: str = "") -> None:
    header = panel.wcs.to_header(relax=panel.wcs.sip is not None)
    header["FILTER"], header["BUNIT"] = band, unit
    if origin:
        header.add_history(origin)
    if panel.path.suffix == ".fits":
        fits.writeto(panel.path, panel.pixels, header)
    else:
        tifffile.imwrite(
            panel.path,
            panel.pixels,
            photometric="rgb",
            tile=(128, 128),
            compression="deflate",
            predictor=3,
            metadata=None,
            description="AstroMosaic TIFF 1\n" + header.tostring(sep="\n", padding=False),
        )
    if panel.mask is not None:
        header = fits.Header({"MASK0": "Unclassified", "MASK1": "Sky", "MASK2": "Foreground"})
        labels = panel.mask.read_labels(Region(0, 0, *panel.size))
        fits.writeto(panel.path.with_suffix(".labels.fits"), labels, header)


def overlap(
    support: Sequence[NDArray[np.bool_]], *, minimum: float = 0.1
) -> dict[str, float | int]:
    count_a, count_b = (int(np.count_nonzero(mask)) for mask in support)
    common = int(np.count_nonzero(support[0] & support[1]))
    smaller = min(count_a, count_b)
    fraction = common / smaller if smaller else 0.0
    if fraction < minimum:
        raise ValueError(f"Expected at least {minimum:.0%} overlap, measured {fraction:.2%}.")
    return {
        "shared_pixels": common,
        "panel_a_pixels": count_a,
        "panel_b_pixels": count_b,
        "percent_of_smaller_support": round(100 * fraction, 3),
    }


def sky_supports(panels: Sequence[Panel], spec: RenderSpec) -> list[NDArray[np.bool_]]:
    output = spec.output_region()
    yy, xx = np.mgrid[: output.height, : output.width]
    world = fixture_grid(spec).pixel_to_world(xx, yy)
    support = []
    for panel in panels:
        wcs = panel.wcs
        if wcs.sip is None:
            x, y = wcs.world_to_pixel(world)
        else:
            sky = world.transform_to(wcs_to_celestial_frame(wcs)).spherical
            lon, lat = sky.lon.deg, sky.lat.deg
            x, y = wcs.all_world2pix(lon, lat, 0, quiet=True, maxiter=40, tolerance=1e-8)
        w, h = panel.size
        inside = (x >= -0.5) & (x < w - 0.5) & (y >= -0.5) & (y < h - 0.5)
        if wcs.sip is not None:
            back_lon, back_lat = wcs.all_pix2world(x[inside], y[inside], 0)
            delta_lon = (back_lon - lon[inside] + 180) % 360 - 180
            inside[inside] &= np.hypot(delta_lon, back_lat - lat[inside]) < 1e-6
        sampled = map_coordinates(panel.support(SKY), (y, x), order=0, mode="nearest")
        support.append(inside & sampled)
    return support


def crop(pixels: Pixels, offset: Size, size: Size) -> Pixels:
    x, y = offset
    width, height = size
    return pixels[y : y + height, x : x + width].copy()


def sky_field(size: Size, seed: int) -> Pixels:
    width, height = size
    rng = np.random.default_rng(seed)
    y, x = np.ogrid[:height, :width]
    ridge = height * (0.30 + 0.25 * np.sin(x / width * 3.1))
    haze = np.exp(-(((y - ridge) / (height * 0.13)) ** 2))
    fine = gaussian_filter(rng.random((height, width)), sigma=10)
    nebula = np.exp(-(((x - width * 0.47) / (width * 0.10)) ** 2) - ((y - ridge) / 58) ** 2)
    stars = np.zeros((height, width), dtype=np.float32)
    count = width * height // 135
    sx, sy = rng.integers(width, size=count), rng.integers(height, size=count)
    strength = 0.14 + 1.8 * rng.power(0.35, count) + 8 * rng.power(0.015, count)
    np.add.at(stars, (sy, sx), strength.astype(np.float32))
    stars = gaussian_filter(stars, 0.95)
    brightness = 0.014 + 0.04 * haze * fine + 0.03 * nebula + stars
    return np.asarray(
        np.stack((brightness * 0.82 + 0.013 * nebula, brightness, brightness * 1.22), axis=-1),
        dtype=np.float32,
    )


def atlas_panels(
    folder: Path, source: Path, tiles: Sequence[str], field: str
) -> tuple[list[Panel], float]:
    panels = []
    reference_zero_point = float(fits.getheader(source / tiles[0])["MAGZP"])
    for index, name in enumerate(tiles):
        label = chr(ord("A") + index)
        samples, header = fits.getdata(source / name, header=True)
        flux_scale = 10 ** (0.4 * (reference_zero_point - float(header["MAGZP"])))
        panel = Panel(
            folder / f"{label}-{field}-{name}",
            np.asarray(samples * flux_scale, dtype=np.float32),
            WCS(header).celestial,
        )
        write_panel(panel, band="Ks", unit="DN", origin=f"2MASS Atlas {name}, common MAGZP.")
        panels.append(panel)
    return panels, reference_zero_point


def real_sky(folder: Path, source: Path) -> SkyFixture:
    spec = render_spec((275.061, -16.276), (1024, 1320), 1.0)
    tiles = ("ki1350080.fits", "ki1420198.fits")
    panels, reference_zero_point = atlas_panels(folder, source, tiles, "m17")
    return panels, spec, {"archive_files": list(tiles), "common_magzp": reference_zero_point}


def narrow_sky(folder: Path) -> SkyFixture:
    spec = render_spec((82.4, -5.2), (1540, 850), 2.15)
    parent = fixture_grid(spec)
    master = np.mean(sky_field(spec.size, seed=20302), axis=2, dtype=np.float32)
    size, first = (780, 540), (70, 150)
    radians = np.deg2rad(16)
    rotation = np.array([[np.cos(radians), -np.sin(radians)], [np.sin(radians), np.cos(radians)]])
    transform = rotation @ np.array([[1.0, 0.16], [0.0, 1.0]])
    second = tuple(np.asarray([1058.0, 424.0]) - transform @ ((np.array(size) - 1) / 2))
    y, x = np.mgrid[: size[1], : size[0]]
    gx = transform[0, 0] * x + transform[0, 1] * y + second[0]
    gy = transform[1, 0] * x + transform[1, 1] * y + second[1]
    panels = [
        Panel(
            folder / "A-narrow-reference.fits", crop(master, first, size), panel_grid(parent, first)
        ),
        Panel(
            folder / "B-narrow-rotated-skewed.fits",
            map_coordinates(master, (gy, gx), order=1),
            panel_grid(parent, second, transform),
        ),
    ]
    for panel in panels:
        write_panel(panel)
    return panels, spec, {"rotation_deg": 16, "x_from_y_shear": 0.16, "seed": 20302}


def wide_sky(folder: Path) -> SkyFixture:
    spec = render_spec((359.2, 9.5), (1620, 680), 196.0)
    grid = fixture_grid(spec)
    field = sky_field(spec.size, seed=20303)
    size, first, second = (960, 560), (40, 55), (620, 70)
    samples = crop(field, first, size)
    samples[13, 20] = (-0.125, 0, 1.5)
    samples[37:52, 42:62] = np.nan
    panels = [
        Panel(folder / "A-wide-west-rgb.tiff", samples, panel_grid(grid, first)),
        Panel(folder / "B-wide-east-rgb.tiff", crop(field, second, size), panel_grid(grid, second)),
    ]
    for panel in panels:
        write_panel(panel)
    return (
        panels,
        spec,
        {
            "seed": 20303,
            "tan_pixel_checks": [
                {"pixel_xy": [60, 68], "rgb": [-0.125, 0, 1.5]},
                {"pixel_xy": [90, 100], "covered": False},
            ],
        },
    )


def scene_mask(horizon: NDArray[np.float64], offset: Size, size: Size, gap: int) -> SourceMask:
    x, y = offset
    width, height = size
    gx, gy = bounded_grid(size, MASK_EDGE)
    columns = x + np.arange(gx) * width // gx
    rows = y + (np.arange(gy) * height // gy)[:, None]
    edge = horizon[columns]
    labels = np.where(
        rows < edge - gap, SKY, np.where(rows >= edge + gap, FOREGROUND, UNCLASSIFIED)
    )
    return SourceMask(size, labels.astype(np.uint8).tobytes())


def synthetic_scene(folder: Path) -> MixedFixture:
    spec = render_spec((351.4, 13.7), (1480, 680), 177.0)
    parent = fixture_grid(spec)
    width, height = spec.size
    sky = sky_field(spec.size, seed=20304)
    rng = np.random.default_rng(20305)
    y, x = np.ogrid[:height, :width]
    horizon = 344 + 29 * np.sin(x[0] / 128) + 21 * np.sin(x[0] / 55) + 5 * np.sin(x[0] / 8)
    texture = gaussian_filter(rng.standard_normal((height, width)), 2.5)
    rock = np.sin(x / 43 + y / 33) * np.sin(y / 37 - x / 61)
    ridge = np.exp(-(((y - horizon - 32) / 18) ** 2))
    lights = sum(
        np.exp(-(((x - cx) / 5) ** 2) - ((y - cy) / 3) ** 2)
        for cx, cy in ((613, 465), (653, 469), (781, 488), (847, 478), (1143, 506))
    )
    shade = 0.02 + 0.055 * (texture + 0.20 * rock) + 0.012 * ridge
    ground = np.asarray(
        np.stack(
            (shade * 0.70 + 0.23 * lights, shade * 0.94 + 0.12 * lights, shade * 0.83), axis=-1
        ),
        dtype=np.float32,
    )
    size = (896, 544)
    ground_origins = ((40, 40), (494, 48))
    sky_origins = ((42, 39), (522, 54))
    panels = []
    for label, ground_origin, sky_origin in zip("AB", ground_origins, sky_origins, strict=True):
        gx, gy = ground_origin
        ground_pixels = gy + np.arange(size[1])[:, None] >= horizon[gx : gx + size[0]]
        samples = np.where(
            ground_pixels[..., None], crop(ground, ground_origin, size), crop(sky, sky_origin, size)
        )
        panel = Panel(
            folder / f"{label}-synthetic-ridge-rgb.tiff",
            samples,
            panel_grid(parent, sky_origin),
            scene_mask(horizon, ground_origin, size, gap=4),
        )
        write_panel(panel)
        panels.append(panel)
    return panels, spec, (454, 8), 23


def photo_scene(folder: Path, source: Path) -> MixedFixture:
    spec = render_spec((350.0, 18.0), (1680, 950), 320.0)
    parent = fixture_grid(spec)
    original = tifffile.imread(source / "eso-vlt-mw-potw-4k.tif")
    srgb = original[180:1105, 600:2280].astype(np.float32) / 255
    photo = np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)
    outline = np.array(
        [
            (600, 940),
            (616, 924),
            (637, 950),
            (722, 950),
            (729, 812),
            (752, 806),
            (865, 808),
            (891, 818),
            (896, 945),
            (981, 947),
            (989, 835),
            (1040, 830),
            (1119, 823),
            (1140, 834),
            (1146, 926),
            (1184, 929),
            (1189, 854),
            (1224, 836),
            (1253, 832),
            (1283, 840),
            (1310, 853),
            (1316, 941),
            (1404, 941),
            (1414, 832),
            (1480, 814),
            (1512, 807),
            (1550, 815),
            (1569, 828),
            (1571, 926),
            (1600, 906),
            (1614, 936),
            (1630, 946),
            (1810, 945),
            (1900, 951),
            (1988, 937),
            (2100, 934),
            (2230, 927),
            (2280, 928),
        ]
    )
    horizon = np.interp(600 + np.arange(photo.shape[1]), outline[:, 0], outline[:, 1]) - 180
    panels = []
    size = (1100, 925)
    for label, offset in zip("AB", ((10, 0), (520, 0)), strict=True):
        panel = Panel(
            folder / f"{label}-paranal-telescopes-rgb.tiff",
            crop(photo, offset, size),
            panel_grid(parent, offset),
            scene_mask(horizon, offset, size, gap=10),
        )
        write_panel(
            panel,
            band="RGB",
            unit="relative",
            origin=f"{ESO_CREDIT}. CC BY 4.0. Display WCS.",
        )
        panels.append(panel)
    return panels, spec, (510, 0), 34


def make_project(panels: Sequence[Panel], spec: RenderSpec, relative: bool) -> MosaicProject:
    entries = tuple(
        ProjectPanel(
            FileReference.capture(panel.path),
            source_mask=panel.mask,
            foreground_override="sky-only" if panel.mask is None else "mixed",
        )
        for panel in panels
    )
    return MosaicProject(entries, render=spec, assume_surface_brightness=relative)


def mixed_project(
    folder: Path,
    project: MosaicProject,
    panels: Sequence[Panel],
    origins: Sequence[Size],
    seam_lift: int,
) -> tuple[MosaicProject, dict[str, object]]:
    save_project(folder / "unaligned.astromosaic", project)
    context = JobContext()
    aligned = align_project_foreground(project, context)
    alignment = aligned.current_foreground()
    assert alignment is not None
    shifts = [(x - origins[0][0], y - origins[0][1]) for x, y in origins]
    actual = [entry.shift for entry in alignment.panels]
    if np.max(np.abs(np.subtract(actual, shifts))) > 0.5:
        raise ValueError(
            f"Incorrect foreground alignment for {folder.name}: {actual} versus {shifts}."
        )
    proposal = propose_project_composition(aligned, context)
    dx, dy = proposal.placement.offset
    settings = replace(
        proposal,
        placement=replace(proposal.placement, offset=(dx, dy - seam_lift)),
        overlap_percent=24.0,
        reference_panel=None,
        placement_rms_px=None,
    )
    width, height = panels[0].size
    left, top = map(min, zip(*origins, strict=True))
    right, bottom = map(max, zip(*origins, strict=True))
    ground = [np.zeros((height + bottom - top, width + right - left), dtype=bool) for _ in panels]
    for stencil, panel, (x, y) in zip(ground, panels, origins, strict=True):
        x, y = x - left, y - top
        stencil[y : y + height, x : x + width] = panel.support(FOREGROUND)
    adjacent = [overlap([a, b]) for a, b in zip(ground[:-1], ground[1:], strict=True)]
    details: dict[str, object] = {
        "foreground_overlap": min(adjacent, key=lambda edge: edge["percent_of_smaller_support"]),
        "expected_foreground_shift_xy": list(shifts[1]),
        "prepared_foreground_shift_xy": list(actual[1]),
        "seam_lift_px": seam_lift,
    }
    if len(ground) > 2:
        details.update(
            expected_foreground_shifts_xy=shifts,
            prepared_foreground_shifts_xy=actual,
            foreground_pairs=[
                {"panels": [a + 1, b + 1], **overlap([ground[a], ground[b]], minimum=0.0)}
                for a, b in combinations(range(len(ground)), 2)
            ],
        )
    return replace(aligned, composition=settings), details


def write_case(
    folder: Path,
    title: str,
    panels: list[Panel],
    project: MosaicProject,
    details: dict[str, object],
    credit_note: str = "",
    *,
    links: Sequence[tuple[int, int]] = ((0, 1),),
) -> tuple[dict[str, object], Image.Image]:
    save_project(folder / "project.astromosaic", project)
    images = []
    for panel in panels:
        w, h = panel.size
        left, right = panel.wcs.pixel_to_world([0, w - 1], [(h - 1) / 2] * 2)
        item = {
            "file": panel.path.name,
            "size_xy": [w, h],
            "channels": 3 if panel.pixels.ndim == 3 else 1,
            "horizontal_wcs_deg": round(float(left.separation(right).deg), 4),
            "sha256": digest(panel.path),
        }
        if panel.mask is not None:
            label_mask = panel.path.with_suffix(".labels.fits")
            item["label_mask"] = label_mask.name
            item["label_sha256"] = digest(label_mask)
        images.append(item)
    spec = project.render
    supports = sky_supports(panels, spec)
    measured = min(
        (overlap([supports[a], supports[b]]) for a, b in links),
        key=lambda edge: edge["percent_of_smaller_support"],
    )
    record = {
        "case": folder.name,
        "title": title,
        "project": "project.astromosaic",
        "images": images,
        "render_grid": {
            "center_deg": spec.center,
            "size_xy": spec.size,
            "scale_arcsec": spec.scale_arcsec,
            "projection": spec.projection,
        },
        "sky_overlap": measured,
        **details,
    }
    if len(panels) > 2:
        record["sky_pairs"] = [
            {
                "panels": [a + 1, b + 1],
                "required": (a, b) in links,
                **overlap([supports[a], supports[b]], minimum=0.0),
            }
            for a, b in combinations(range(len(panels)), 2)
        ]
    if spec.rotation_deg:
        record["render_grid"]["rotation_deg"] = spec.rotation_deg
    if spec.crop is not None:
        record["render_grid"]["crop_xywh"] = [
            spec.crop.x,
            spec.crop.y,
            spec.crop.width,
            spec.crop.height,
        ]
    (folder / "case.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    note = f"{measured['percent_of_smaller_support']:.2f}% measured sky overlap"
    if credit_note:
        note += f"  |  {credit_note}"
    print(f"{folder.name}: {note}", flush=True)
    return record, contact_row(title, panels, note)


def contact_row(title: str, panels: Sequence[Panel], note: str) -> Image.Image:
    row = Image.new("RGB", (1040, 285), "#15212c")
    draw = ImageDraw.Draw(row)
    draw.text((20, 10), title, fill="#f1f5f8", font=ImageFont.load_default(size=19))
    draw.text((20, 34), note, fill="#acd0e3", font=ImageFont.load_default(size=13))
    valid = panels[0].pixels[np.isfinite(panels[0].pixels)]
    black, white = np.percentile(valid, [1, 99.6])
    column_width = 1010 // len(panels)
    image_width = column_width - 20
    for column, panel in enumerate(panels):
        displayed = np.clip(
            (np.nan_to_num(panel.pixels, nan=black) - black) / (white - black), 0, 1
        )
        displayed = np.asarray(255 * np.arcsinh(displayed * 6) / np.arcsinh(6), dtype=np.uint8)
        thumb = Image.fromarray(displayed).convert("RGB")
        thumb.thumbnail((image_width, 193), Image.Resampling.LANCZOS)
        x = 20 + column_width * column
        row.paste(thumb, (x + (image_width - thumb.width) // 2, 57))
        draw.text((x, 255), panel.path.name, fill="#f1f5f8", font=ImageFont.load_default(size=14))
    return row


def prepare_pack(output: Path, source: Path) -> None:
    output.mkdir(parents=True)
    cases = []
    sky_cases: list[tuple[str, str, Callable[[Path], SkyFixture]]] = [
        ("sky01-m17-atlas", "SKY-01 · M17 2MASS atlas tiles", partial(real_sky, source=source)),
        ("sky02-narrow-skew", "SKY-02 · Narrow rotated and skewed sky", narrow_sky),
        ("sky03-wide-rgb", "SKY-03 · Wide RGB sky across RA zero", wide_sky),
    ]
    for name, title, prepare in sky_cases:
        folder = output / name
        folder.mkdir()
        panels, spec, details = prepare(folder)
        real_atlas = name == "sky01-m17-atlas"
        project = make_project(panels, spec, relative=real_atlas)
        if name == "sky03-wide-rgb":
            save_project(
                folder / "project-zea.astromosaic",
                replace(project, render=replace(spec, projection="ZEA")),
            )
            details["zea_project"] = "project-zea.astromosaic"
        credit = "2MASS · UMass and IPAC/Caltech · NASA and NSF" if real_atlas else ""
        cases.append(write_case(folder, title, panels, project, details, credit))

    mixed_cases: list[tuple[str, str, Callable[[Path], MixedFixture]]] = [
        ("mix01-synthetic-ridge", "MIX-01 · Wide synthetic nightscape", synthetic_scene),
        (
            "mix02-paranal",
            "MIX-02 · Real Paranal nightscape crops",
            partial(photo_scene, source=source),
        ),
    ]
    for name, title, prepare_mixed in mixed_cases:
        folder = output / name
        folder.mkdir()
        panels, spec, shift, lift = prepare_mixed(folder)
        photo = name == "mix02-paranal"
        project, details = mixed_project(
            folder, make_project(panels, spec, relative=photo), panels, ((0, 0), shift), lift
        )
        details["unaligned_project"] = "unaligned.astromosaic"
        credit = ""
        if photo:
            details.update(
                credit=ESO_CREDIT, license="CC BY 4.0", display_wcs=True, source_columns_deg=99.0
            )
            credit = f"{ESO_CREDIT} · adapted panorama crops · CC BY 4.0"
        cases.append(write_case(folder, title, panels, project, details, credit))

    (output / "fixtures.json").write_text(
        json.dumps({"cases": [item for item, _ in cases], "public_sources": ARCHIVES}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    contact = Image.new("RGB", (1040, len(cases) * 285))
    for index, (_, row) in enumerate(cases):
        contact.paste(row, (0, index * 285))
    contact.save(output / "contact-sheet.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/application-tests"))
    parser.add_argument("--source-dir", type=Path, default=Path("data/application-test-sources"))
    parser.add_argument(
        "--download", action="store_true", help="Fetch the three pinned public sources."
    )
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new fixture output directory.")
    prepare_sources(args.source_dir, args.download)
    prepare_pack(args.output, args.source_dir)


if __name__ == "__main__":
    main()
