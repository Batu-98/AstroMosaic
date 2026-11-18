"""Exercise owner-provided TIFF fixtures entirely offline on staged copies."""

import argparse
import json
import os
import subprocess
from pathlib import Path
from time import perf_counter

from astropy.io import fits
from phase36_capabilities import fingerprint
from phase36_validation import validate_candidate

from astromosaic.astrometry.solve import SolveOptions, _pointing, _stage_astap_input, solve_panel
from astromosaic.astrometry.stars import measure_stars
from astromosaic.core.job import JobContext
from astromosaic.io import open_panel


def direct_gaia(
    source: Path, args: argparse.Namespace
) -> tuple[fits.Header | None, dict[str, object]]:
    """Probe broad blind/native SIP independently of the production dispatch."""
    import seiza

    with open_panel(source) as panel:
        stars = measure_stars(panel, 64 * 1024**2, JobContext()).stars
        width, height = panel.descriptor.width, panel.descriptor.height
    catalog = seiza.StarCatalog.open(args.gaia_catalog)
    index = seiza.BlindIndex.open(args.gaia_index)
    try:
        result = seiza.solve_blind(
            [(star.x, star.y, star.flux) for star in stars],
            catalog,
            index,
            width,
            height,
            min_scale_arcsec_px=args.scale_range[0],
            max_scale_arcsec_px=args.scale_range[1],
            sip_order=args.gaia_sip,
            time_limit=30,
        )
    except seiza.SolveError as error:
        return None, {"native_status": "failed", "detail": str(error)}
    return fits.Header(result.fits_header_cards()), {
        "native_status": "candidate",
        "scale_range_arcsec_px": args.scale_range,
        "requested_sip_order": args.gaia_sip,
        "matched_stars": result.matched_stars,
        "rms_arcsec": result.rms_arcsec,
        "scale_arcsec_px": result.scale_arcsec_px,
        "false_match_probability": result.false_match_probability,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", nargs="+", type=Path)
    parser.add_argument("--astap", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--gaia-catalog", type=Path, required=True)
    parser.add_argument("--gaia-index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--skip-astap", action="store_true", help="Reuse the recorded ASTAP failure."
    )
    parser.add_argument(
        "--direct-gaia", action="store_true", help="Probe native broad blind/SIP behavior."
    )
    parser.add_argument("--gaia-sip", type=int, choices=(0, 2, 3), default=0)
    parser.add_argument("--scale-range", type=float, nargs=2, default=(0.1, 120))
    parser.add_argument("--skip-validation", action="store_true", help="Run validation separately.")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    records: list[dict[str, object]] = []
    for index, source in enumerate(args.images):
        before = fingerprint(source)
        work = args.output / f"panel-{index + 1}"
        work.mkdir()
        start = perf_counter()
        record: dict[str, object] = {"source": before}
        with open_panel(source) as panel:
            record["dimensions"] = [panel.descriptor.width, panel.descriptor.height]
            record["channels"] = panel.descriptor.channel_layout
            _, _, vertical_scale = _pointing(panel, SolveOptions())
            record["scale_hint_arcsec"] = vertical_scale
            field_height = panel.descriptor.height * vertical_scale / 3600 if vertical_scale else 0
            record["field_height_hint_deg"] = field_height
            _stage_astap_input(panel, work / "input.fits", SolveOptions(), JobContext())
        record["staging_seconds"] = perf_counter() - start
        print(f"Staged {source.name}: {record['staging_seconds']:.2f} s", flush=True)
        command = [
            str(args.astap.resolve()),
            "-f",
            "input.fits",
            "-d",
            str(args.catalog.resolve()),
            "-D",
            "auto",
            "-fov",
            str(field_height),
            "-r",
            "180",
            "-threads",
            "1",
            "-z",
            "0",
            "-wcs",
            "-o",
            "result",
            "-log",
            "-progress",
        ]
        search = perf_counter()
        if args.skip_astap:
            record["astap_returncode"] = None
            record["astap_outcome"] = "skipped-recorded-failure"
        else:
            try:
                result = subprocess.run(
                    command,
                    cwd=work,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=25,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                record["astap_returncode"] = result.returncode
                (work / "stdout.txt").write_text(result.stdout, encoding="utf-8")
            except subprocess.TimeoutExpired as error:
                record["astap_returncode"] = None
                record["astap_outcome"] = "25-second-probe-timeout"
                if error.stdout:
                    raw = (
                        error.stdout.decode("utf-8", errors="replace")
                        if isinstance(error.stdout, bytes)
                        else error.stdout
                    )
                    (work / "stdout.txt").write_text(raw, encoding="utf-8")
        record["astap_search_seconds"] = perf_counter() - search
        candidate = work / "result.wcs"
        if not candidate.is_file():
            print(f"Trying local Gaia for {source.name}", flush=True)
            gaia_start = perf_counter()
            gaia_header = None
            if args.direct_gaia:
                gaia_header, record["gaia_native_report"] = direct_gaia(source, args)
            else:
                with open_panel(source) as panel:
                    solved = solve_panel(
                        panel,
                        SolveOptions(
                            gaia_catalog=args.gaia_catalog,
                            gaia_index=args.gaia_index,
                            timeout_seconds=30,
                        ),
                    )
                record["gaia_legacy_report"] = solved.report()
                if solved.geometry is not None:
                    gaia_header = solved.geometry.wcs.to_header(relax=True)
            record["gaia_seconds"] = perf_counter() - gaia_start
            if gaia_header is not None:
                candidate = work / "gaia.wcs"
                candidate.write_text(gaia_header.tostring(), "ascii")
        if candidate.is_file() and not args.skip_validation:
            try:
                record["validation"] = validate_candidate(source, candidate, args.catalog, "d05")
            except ValueError as error:
                record["validation_error"] = str(error)
        record["total_seconds"] = perf_counter() - start
        record["source_unchanged"] = before == fingerprint(source)
        if not record["source_unchanged"]:
            raise RuntimeError("An original TIFF fixture changed during verification.")
        records.append(record)
        print(json.dumps(record, allow_nan=False), flush=True)
        (args.output / "manifest.json").write_text(
            json.dumps({"schema_version": 1, "panels": records}, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
