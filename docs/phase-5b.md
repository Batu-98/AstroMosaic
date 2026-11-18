# Phase 5B ZEA Sky Projection

## Scope

Add ICRS zenithal equal area (ZEA) for wide-field sky mosaics. Choose **ZEA** in Mosaic Settings or pass `--projection ZEA` to `mosaic` or `project create`. Use the same reference sky position, square projected pixel scale, rotation, and zero-based crop conventions as TAN. The FITS WCS projection code identifies the grid in FITS, TIFF, and XISF sky exports. [FITS WCS projection definition](https://www.aanda.org/articles/aa/pdf/2002/45/aah3860.pdf) · [ADR-0021](adr/0021-zea-sky-grid.md)

Use TAN as the default for existing projects. Manifest version 5 introduced the explicit projection. Projects with band overrides use version 6 and include the projection. TAN projects without overrides use version 4, and ZEA projects without overrides use version 5. The shared tile mapper applies the selected WCS to both preview and export. ZEA uses full coordinate mapping with the existing tile and memory limits. A projection change in Mosaic Settings clears the composition placement tied to the prior sky grid. [Band persistence](phase-5c.md#scope)

ZEA maps equal areas on the sky to equal projected areas. The renderer continues to sample surface brightness in the declared units. Samples whose coordinates are outside the projection or within 0.0001° of the native antipode have no coverage. The guard accounts for floating-point rounding in serialized WCS and prevents the non-unique rim from producing artificial samples. An export with no valid coverage fails before publication. [Surface-brightness contract](adr/0002-surface-brightness-reference.md)

## Acceptance Cases

| Case | Required result |
| --- | --- |
| Wide field and longitude wrap | Use an ICRS reference at RA 359.4° and Dec 23°, a 63 × 39 grid at 0.8° per pixel, rotation 21°, and crop (5, 9, 51, 27). Compare output sky positions with the independent spherical Lambert formula within 1e-9 degrees across the 0° meridian and round-trip within 1e-7 pixels. |
| Projection domain and reimport | Use a 13 × 11 polar grid at 0.5 radians per pixel. Match the analytic open disk of radius four pixels, including its exact rim and outside corners. Check the rim with a fitted panel shift. Preserve the valid part of a crop whose center lies on the rim, allow a saved crop with coverage to be reimported, and remove temporary output when a crop lies entirely outside. |
| Preview and scientific export | Compare a bounded preview with the rotated and cropped output at coincident samples. Independently reopen FITS, TIFF, and XISF, verify projection, units, filter, float32 samples and coverage, and retain valid zero, negative and above-one values. Exercise a tightly budgeted tile split against the same sky result. |
| Persistence and desktop | Load legacy manifests as TAN. Save and reopen the explicit ZEA grid, reject invalid projection records, and show the saved choice in Mosaic Settings and the grid summary. Changing the projection clears the prior composition placement while keeping the independent foreground alignment available. |
| CLI and packages | Create, validate, and export a saved ZEA project in the Qt-free CLI. Exercise ZEA selection, preview, and export in the copied Windows desktop bundle with CPU and OpenGL. Verify the saved projection through a normal project reopen. |

## Local Windows Results

- The oblique wide-field grid covered 1,329 of 1,377 positions from two TAN panels. FITS, TIFF and XISF samples and coverage matched the full-resolution preview exactly. The independently calculated coordinates agreed within 6e-14 degrees, with a maximum inverse error of 1.5e-13 pixels. The independent `xisf` 1.0.1 decoder reopened the ZEA samples, mask, projection codes, units and filter. [Numerical fixture](../tests/numerical/test_zea.py) · [Independent XISF reader](https://github.com/sergio-dr/xisf)
- The polar case matched the open disk, including the rim after FITS serialization and after a fitted sampling shift. The rim-centered crop reopened with 12 of 55 positions covered. A fully outside crop left its destination available. The 256 KiB run split the wide field into 11 tiles with a 255.5 KiB peak reservation and matched the regular output.
- All 169 source tests passed on Windows 11 x64 with native OpenGL and test windows on the second display. Ruff, format, mypy, and Poetry lock checks passed. The legacy TAN manifest checks, ZEA save and reopen, and direct versus saved-project CLI export passed. [Manifest tests](../tests/integration/test_project.py) · [CLI tests](../tests/portability/test_project_cli.py)
- The copied Qt-free CLI created, validated, and exported a saved ZEA project. The copied desktop passed both CPU and native OpenGL checks with 3,338 covered ZEA pixels. Both desktop runs selected ZEA, saved and reopened the project, cleared the prior composition placement, and matched preview and FITS output. The rebuilt launchers are in ignored `.tooling/phase5b-windows/dist/windows/`. [CLI package checker](../packaging/check-windows-cli.py) · [Desktop package checker](../packaging/check-windows-desktop.py)

The per-band workflow uses the same saved sky grid with explicit filter membership and compatible units within each band. The separate clean-machine distribution check remains open. [Phase 5C](phase-5c.md) · [Distribution acceptance](phase-3f.md#pending-clean-machine-check)
