"""Local solver options shared by the panel and project commands."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from astromosaic.astrometry.solve import SolveOptions


def add_solve_options(parser: ArgumentParser) -> None:
    parser.add_argument("--gaia-catalog", type=Path, help="Local Seiza Gaia DR3 catalog file.")
    parser.add_argument("--gaia-index", type=Path, help="Matching local Gaia DR3 blind index.")
    parser.add_argument("--astap", type=Path, help="Local ASTAP executable.")
    parser.add_argument("--astap-catalog", type=Path, help="Local ASTAP star catalog directory.")
    parser.add_argument(
        "--astap-database",
        default="auto",
        choices=("auto", "d05", "d20", "d50", "d80"),
        help="Use Automatic selection or pin an installed D-series catalog.",
    )
    parser.add_argument(
        "--timeout", type=float, default=60, help="Upper limit per native attempt, in seconds."
    )
    parser.add_argument(
        "--total-budget",
        type=float,
        default=120,
        metavar="SECONDS",
        help="Panel time budget including preparation, validation and sidecar publication (120).",
    )
    parser.add_argument(
        "--job-budget",
        type=float,
        metavar="SECONDS",
        help="Optional overall job deadline. Takes precedence if it expires first.",
    )
    parser.add_argument(
        "--revalidate", action="store_true", help="Require a new catalog-validated WCS."
    )
    parser.add_argument(
        "--require-edge-validation",
        action="store_true",
        help="Require a new WCS with supported held-out field-edge accuracy.",
    )
    parser.add_argument("--memory-mib", type=int, default=64, help="Working buffer budget in MiB.")
    parser.add_argument("--scratch-mib", type=int, default=1024, help="ASTAP staging limit in MiB.")


def solve_options(arguments: Namespace) -> SolveOptions:
    from astromosaic.astrometry.solve import SolveOptions

    return SolveOptions(
        gaia_catalog=arguments.gaia_catalog,
        gaia_index=arguments.gaia_index,
        astap=arguments.astap,
        astap_catalog=arguments.astap_catalog,
        astap_database=arguments.astap_database,
        timeout_seconds=arguments.timeout,
        total_seconds=arguments.total_budget,
        job_seconds=arguments.job_budget,
        revalidate=arguments.revalidate,
        strict_edges=arguments.require_edge_validation,
        max_working_bytes=arguments.memory_mib * 1024**2,
        max_scratch_bytes=arguments.scratch_mib * 1024**2,
    )
