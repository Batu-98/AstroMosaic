"""Check local solver prerequisites without opening a project or image."""

import subprocess
from pathlib import Path

from astromosaic.astrometry.astap_probe import check_astap_setup
from astromosaic.astrometry.solve import SolveOptions
from astromosaic.core.job import DEFAULT_JOB_CONTEXT, JobContext


def check_solver_paths(
    options: SolveOptions, context: JobContext = DEFAULT_JOB_CONTEXT
) -> tuple[str, str]:
    context.check_cancelled()
    gaia = _gaia_status(options.gaia_catalog, options.gaia_index, context)
    context.check_cancelled()
    astap = _astap_status(options, context)
    context.check_cancelled()
    return gaia, astap


def _gaia_status(catalog: Path | None, index: Path | None, context: JobContext) -> str:
    if catalog is None:
        return "Choose a local Seiza Gaia DR3 star catalog."
    try:
        import seiza
    except ImportError:
        return "Gaia DR3 support is unavailable. Use a build with Seiza or install the gaia extra."

    try:
        if not catalog.is_file():
            return "Gaia DR3 catalog is missing. Browse to its current file location."
        if seiza.StarCatalog.open(catalog).star_count() == 0:
            return "The Gaia DR3 catalog is empty. Select a populated Seiza star catalog."
    except OSError:
        return "Could not open the Gaia DR3 catalog. Select a readable Seiza star catalog file."

    hinted = "Catalog opens. Hinted solving requires panel pointing and plate scale."
    if index is None:
        return f"{hinted} Add the matching blind index for panels without those hints."
    context.check_cancelled()
    try:
        if not index.is_file():
            return f"{hinted} Blind index is missing. Browse to its current file location."
        if seiza.BlindIndex.open(index).pattern_count() == 0:
            return f"{hinted} The blind index has no patterns. Select the matching index."
    except OSError:
        return f"{hinted} Could not open the blind index. Select a readable matching Seiza index."

    return (
        "Catalog and blind index open. Use a matching pair from the same Seiza bundle "
        "for blind solving."
    )


def _astap_status(options: SolveOptions, context: JobContext) -> str:
    if options.astap is None or options.astap_catalog is None:
        return "Choose the ASTAP CLI executable and the folder containing its catalog tiles."
    try:
        version = check_astap_setup(
            options.astap, options.astap_catalog, options.astap_database, context
        )
    except subprocess.TimeoutExpired:
        return "ASTAP did not answer the help check in time. Select a working ASTAP CLI executable."
    except OSError:
        return "Could not run ASTAP or read the catalog tile. Check the executable and folder."
    except ValueError as error:
        return str(error)
    return f"ASTAP {version} responds and a {options.astap_database.upper()} catalog tile opens."
