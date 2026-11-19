"""Collect notices for the distributions present in a frozen Windows bundle."""

import argparse
import re
import shutil
import sys
from importlib.metadata import Distribution, distribution, distributions, packages_distributions
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader

SUPPLEMENTS = Path(__file__).with_name("notices")


def package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def bundled_distributions(bundle: Path) -> list[Distribution]:
    internal = bundle / "_internal"
    archive = CArchiveReader(str(bundle / f"{bundle.name}.exe"))
    pyz = archive.open_embedded_archive("PYZ.pyz")
    roots = {entry.split(".", 1)[0] for entry in pyz.toc}
    roots.update(path.name.split(".", 1)[0] for path in internal.iterdir())
    providers = packages_distributions()
    names = {package_name(name) for root in roots for name in providers.get(root, ())}
    names.update(package_name(dist.name) for dist in distributions(path=[str(internal)]))
    names.discard("astromosaic")
    names.add("pyinstaller")
    return [distribution(name) for name in sorted(names)]


def copy_wheel_notices(dist: Distribution, destination: Path) -> None:
    for entry in dist.files or ():
        if entry.is_absolute() or ".." in entry.parts:
            continue
        if entry.suffix.lower() in {".py", ".pyc", ".pyd"}:
            continue
        directory_names = {parent.lower() for parent in entry.parts[:-1]}
        is_notice = entry.name.lower().startswith(
            ("license", "copying", "notice", "copyright", "authors", "credits")
        )
        if is_notice or "licenses" in directory_names:
            source = Path(dist.locate_file(entry))
            if source.is_file():
                target = destination.joinpath(*entry.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)

    name = package_name(dist.name)
    if name in {"pyside6-essentials", "shiboken6"}:
        name = "qt-for-python"
    extra = SUPPLEMENTS / f"{name}-{dist.version}"
    if extra.is_dir():
        shutil.copytree(extra, destination / "upstream")
    if not destination.is_dir():
        raise ValueError(f"No license or notice files were found for {dist.name} {dist.version}.")


def write_notices(bundle: Path) -> None:
    included = bundled_distributions(bundle)
    destination = bundle / "ThirdParty"
    destination.mkdir()
    python_version = ".".join(map(str, sys.version_info[:3]))
    python_root = Path(sys.base_prefix)
    runtime_notices = destination / "cpython"
    runtime_notices.mkdir()
    shutil.copyfile(python_root / "LICENSE.txt", runtime_notices / "LICENSE.txt")
    for license_file in (python_root / "tcl").glob("*/license.terms"):
        shutil.copyfile(license_file, runtime_notices / f"{license_file.parent.name}-license.terms")
    extra = SUPPLEMENTS / f"cpython-{python_version}"
    if extra.is_dir():
        shutil.copytree(extra, runtime_notices / "upstream")

    rows = [f"| CPython | {python_version} | [Notices](ThirdParty/cpython/) |"]
    for dist in included:
        slug = package_name(dist.name)
        copy_wheel_notices(dist, destination / slug)
        rows.append(f"| {dist.name} | {dist.version} | [Notices](ThirdParty/{slug}/) |")
    (bundle / "THIRD_PARTY_NOTICES.md").write_text(
        "\n".join(
            [
                "# Third-party notices",
                "",
                "AstroMosaic is licensed under GPL-3.0-only. See [LICENSE](LICENSE).",
                "The component directories contain notices from the build environment and",
                "version-matched upstream notices where available.",
                "",
                "| Component | Version | License and attribution files |",
                "| --- | --- | --- |",
                *rows,
                "",
                "See [Windows release documentation](https://github.com/Batu-98/AstroMosaic/blob/main/docs/windows-release.md)",
                "for source links, runtime notices and external catalog terms.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    native_paths = sorted(
        path.relative_to(bundle).as_posix()
        for path in (bundle / "_internal").rglob("*")
        if path.suffix.lower() in {".dll", ".pyd"}
    )
    (destination / "native-files.txt").write_text("\n".join(native_paths) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    write_notices(parser.parse_args().bundle)
