# Phase 5C Per-Band Sky Products

## Scope

Create one independent sky product for a selected filter band of a saved project. Use the same TAN or ZEA grid, rotation, crop, masks, weights, and resource limits for every band. Discover labels with `project bands`, check a selection with `project validate --band`, and render it with `project export --band`. The desktop Sky band selector applies to both Build Preview and Export Mosaic. The existing batch scripts accept an optional `band` for each job.

Use a panel's saved Sky band override when present, then its embedded `FILTER`, then the project's explicit Common filter fallback. Use `Unspecified` when none is present. Match labels exactly after trimming surrounding whitespace. This gives unlabeled panels a selectable band alongside panels with known labels. Store explicit assignments in manifest version 6. Source files are read-only during every render. [ADR-0022](adr/0022-per-band-sky-products.md)

Validate unit scale, channel layout, and optional mono refinement within each band. Export the resulting label and unit with that band's WCS and coverage. Use FITS for mono and TIFF or XISF for mono or RGB. RGB panels retain their three channels as one labeled product. Keep foreground and visual composition on the ordinary layer workflow.

## Acceptance Cases

| Case | Required result |
| --- | --- |
| Saved membership | Resolve an interleaved mono H-alpha and RGB OIII project, including a saved assignment for missing metadata, a project-level fallback, and an excluded unlabeled panel. Reopen explicit assignments, verify legacy projects use embedded labels, and select the `Unspecified` band for remaining unlabeled panels. Report unknown band selections. |
| Scientific channels and units | Preserve independent `MJy/sr` and `Jy/sr` bands. Compare signed float32 data, valid zeros, values above one, and coverage against deterministic truth. Reject incompatible unit scales, mixed layouts within one band, and RGB FITS. |
| Common grid | Reopen mono FITS and RGB TIFF and XISF with identical cropped, rotated ZEA WCS. Verify that coverage and channel order match their own previews and that one band's missing data does not change another band's product. |
| Runtime and publication | Verify Qt-free reports, bounded rendering, cancellation after tile progress, temporary-file cleanup, and retry. Pass named bands through the Python and PowerShell batch runners, each using an explicit output path. |
| Windows packages | List and export a selected band from the copied console bundle. Select, preview and export one of two bands from the copied desktop with CPU and OpenGL. |

## Commands

```text
astromosaic project create Ha.fits OIII.tiff -o Field.astromosaic --panel-band 2=OIII --center 359.999 20 --size 1600 1200 --scale 2
astromosaic project bands Field.astromosaic --json
astromosaic project validate Field.astromosaic --band OIII -o OIII-mosaic.tiff --json
astromosaic project export Field.astromosaic --band OIII -o OIII-mosaic.tiff --json --progress
```

Use **Panel Settings → Sky band override** to assign a label with printable FITS characters. Select **Sky** and the desired **Sky band** to preview or export from the desktop.

For a batch, put one job per band in the list and give each job its destination. [Batch commands](phase-4a.md#run-a-batch)

```json
[
  {"project": "Field.astromosaic", "output": "Ha-mosaic.fits", "band": "H-alpha"},
  {"project": "Field.astromosaic", "output": "OIII-mosaic.tiff", "band": "OIII"}
]
```

## Local Windows Results

- The mixed fixture reopened with H-alpha panels 1 and 3 and O III panel 2. The H-alpha FITS retained `MJy/sr`, the weighted mono result and its attached mask. Both O III exports retained `Jy/sr` and their RGB order. All three products matched their previews exactly and used the same rotated and cropped ZEA grid. Each band covered 98 of 99 positions with a different uncovered position. The independent `xisf` decoder confirmed the RGB samples, coverage, and metadata. [Numerical tests](../tests/numerical/test_project_bands.py)
- The initial band preflight rejected absent and unknown labels, incompatible unit scales, mixed layouts within one band, and RGB FITS output. A cancelled band export removed its scratch file and retried at the same path. The test also verified source-file integrity and recognition of manifest version 6. Current regressions verify selection and export of the `Unspecified` default. [Numerical tests](../tests/numerical/test_project_bands.py) · [CLI tests](../tests/portability/test_project_cli.py)
- All 173 native Windows tests passed with OpenGL and test windows on the second display. Ruff, format, mypy, the lock check, and PowerShell syntax passed.
- The copied Qt-free CLI listed, validated and exported from a saved two-band project. The copied desktop used Panel Settings to assign O III, saved and reopened the project, and matched the preview and reopened export at 191 covered positions with CPU and OpenGL. The rebuilt launchers are in ignored `.tooling/phase5c-windows/dist/windows/`. [CLI checker](../packaging/check-windows-cli.py) · [Desktop checker](../packaging/check-windows-desktop.py)
- Python and PowerShell each passed against the installed and copied CLI. Both runners kept completed files after console interruption, stopped the active band job, cleaned its temporary output, and successfully retried with the original path. [Batch checker](../packaging/check-windows-batch.py)

Phase 5 meets the local Windows acceptance cases. The clean-machine launch and export check remains part of distribution acceptance. [Distribution acceptance](phase-3f.md#pending-clean-machine-check)
