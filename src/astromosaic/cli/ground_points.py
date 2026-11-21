"""Read terrain observations, report the fit, and optionally save the aligned project."""

from __future__ import annotations

import json
from argparse import ArgumentParser, Namespace
from dataclasses import asdict
from math import isfinite
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from astromosaic.core.job import JobContext
    from astromosaic.pipeline.control_points import XY, ControlPointFit, GroundControlPoint

_MAX_POINTS_FILE_BYTES = 4 * 1024**2


def add_fit_command(commands: ArgumentParser) -> None:
    commands.add_argument("path", type=Path, help="Saved .astromosaic project.")
    source = commands.add_mutually_exclusive_group(required=True)
    source.add_argument("--points", type=Path, help="Version 1 manual control point JSON.")
    source.add_argument(
        "--automatic", action="store_true", help="Try the optional SIFT terrain matcher."
    )
    commands.add_argument(
        "--holdout", type=Path, help="Independent version 1 audit points for --automatic."
    )
    commands.add_argument(
        "--model",
        choices=("auto", "translation", "similarity"),
        default="auto",
        help="Geometry model. Automatic selection tries translation first.",
    )
    commands.add_argument("--anchor", type=int, help="One-based project panel to hold fixed.")
    commands.add_argument("--progress", action="store_true", help="Report fit progress to stderr.")
    commands.add_argument(
        "-o", "--output", type=Path, help="Save the accepted fit to a new .astromosaic project."
    )


def _position(value: object, label: str) -> XY:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(type(x) not in (float, int) or not isfinite(x) for x in value)
    ):
        raise ValueError(f"Expected finite [x, y] source-pixel coordinates for {label}.")
    return float(value[0]), float(value[1])


def _load_points(path: Path, context: JobContext, budget: int) -> tuple[GroundControlPoint, ...]:
    from astromosaic.pipeline.control_points import GroundControlPoint

    size_limit = min(_MAX_POINTS_FILE_BYTES, budget // 8)
    with path.open("rb") as stream:
        payload = stream.read(size_limit + 1)
    if len(payload) > size_limit:
        raise ValueError("Control point JSON exceeds the working input limit.")
    data = json.loads(payload)
    if (
        not isinstance(data, dict)
        or type(data.get("schema_version")) is not int
        or data["schema_version"] != 1
        or not isinstance(data.get("points"), list)
    ):
        raise ValueError("Expected a version 1 control point document with a points array.")
    points = []
    for index, row in enumerate(data["points"], 1):
        context.check_cancelled()
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError(f"Control point {index} needs a string ID.")
        name = row["id"]
        panels = row.get("panels")
        if (
            not isinstance(panels, list)
            or len(panels) != 2
            or any(type(panel) is not int or panel < 1 for panel in panels)
        ):
            raise ValueError(f"Expected two one-based panel numbers for control point {name!r}.")
        held_out = row.get("held_out", False)
        if not isinstance(held_out, bool):
            raise ValueError(f"Expected a boolean held_out flag for control point {name!r}.")
        points.append(
            GroundControlPoint(
                name,
                (panels[0] - 1, panels[1] - 1),
                _position(row.get("left_xy"), f"control point {name!r} on the left panel"),
                _position(row.get("right_xy"), f"control point {name!r} on the right panel"),
                held_out,
            )
        )
    return tuple(points)


def _fit_report(fit: ControlPointFit) -> dict[str, object]:
    poses = [asdict(pose) | {"panel": pose.panel + 1} for pose in fit.poses]
    return {
        "model": fit.model,
        "status": fit.status,
        "anchor": fit.anchor + 1,
        "groups": [[panel + 1 for panel in group] for group in fit.groups],
        "poses": poses,
        "edges": [asdict(edge) | {"panels": [p + 1 for p in edge.panels]} for edge in fit.edges],
        "points": [asdict(row) | {"panels": [p + 1 for p in row.panels]} for row in fit.points],
    }


def fit_project_points(arguments: Namespace, result: dict[str, object], context: JobContext) -> str:
    from astromosaic.storage.project import (
        apply_project_ground_fit,
        fit_project_foreground_features,
        fit_project_foreground_points,
        load_project,
        save_project,
    )

    context.check_cancelled()
    destination: Path | None = arguments.output
    if destination is not None:
        result["output"] = str(destination)
        if destination.suffix.lower() != ".astromosaic":
            raise ValueError("The project filename must end in .astromosaic.")
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"The output file already exists: {destination}")
    project = load_project(arguments.path)
    budget = project.render.max_working_bytes
    anchor = arguments.anchor - 1 if arguments.anchor is not None else None
    if arguments.automatic:
        holdouts = _load_points(arguments.holdout, context, budget) if arguments.holdout else ()
        automatic = fit_project_foreground_features(
            project, context, model=arguments.model, anchor=anchor, holdouts=holdouts
        )
        result["matching"] = {
            "backend_version": automatic.backend_version,
            "reserved_peak_bytes": automatic.reserved_peak_bytes,
            "panels": [asdict(row) | {"panel": row.panel + 1} for row in automatic.panels],
            "pairs": [
                asdict(row) | {"panels": [p + 1 for p in row.panels]} for row in automatic.pairs
            ],
            "points": [
                asdict(row) | {"panels": [p + 1 for p in row.panels]} for row in automatic.points
            ],
        }
        fit = automatic.fit
        points = (*automatic.points, *holdouts)
        provider = f"OpenCV SIFT {automatic.backend_version}"
    else:
        if arguments.holdout:
            raise ValueError("--holdout requires --automatic.")
        points = _load_points(arguments.points, context, budget)
        fit = fit_project_foreground_points(
            project, points, context, model=arguments.model, anchor=anchor
        )
        provider = "manual"
    result["fit"] = _fit_report(fit)
    if fit.status != "accepted":
        groups = " | ".join(", ".join(str(panel + 1) for panel in group) for group in fit.groups)
        failures = ", ".join(
            f"{row.panels[0] + 1}-{row.panels[1] + 1} {row.status}"
            for row in fit.edges
            if row.status != "accepted"
        )
        detail = f" Rejected links include {failures}." if failures else ""
        if arguments.automatic:
            detail += " Review matching diagnostics or supply --points for manual recovery."
        raise ValueError(f"Ground point fit {fit.status}. Panel groups {groups}.{detail}")
    message = (
        f"Fitted {fit.model} for {len(fit.poses)} foreground panels "
        f"with panel {fit.anchor + 1} fixed."
    )
    if destination is not None:
        updated = apply_project_ground_fit(project, fit, points, provider, context)
        save_project(destination, updated, context=context, replace_existing=False)
        message += " Saved the aligned project copy."
    return message
