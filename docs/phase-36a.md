# Phase 3.6A: Capabilities and Frozen Reference Contracts

- **Completed:** 2026-11-18, Windows 11 x64 source environment.
- **Scope:** Native ASTAP capabilities, an ASTAP-only validation route, optical metadata import, private owner TIFF fixtures and the numerical/time/schema contracts for 3.6B–3.6F.
- **Frozen reference:** [Version 1 manifest](../tests/fixtures/plate_solve_v36.json). This report captures the Gaia-first baseline. See the [Phase 3.6 plan](phase-36.md) and [implementation evidence](phase-36-results.md) for the subsequent dispatch, quality, SIP and deadline work.

## Native capability evidence

Tested the local ASTAP CLI-2026.11.01 executable, SHA-256 `805c5b352dfa9e57eeeacffa4d64eec63e8729099fdfc3f2a3b351ec9a917b46`. The separate D05 archive matches `39d59b73cb960fa0956c35162e70b09a8af10ef20a1e8f5cae7b77d48be5ce31`. The installed folder contains all 1,476 D05 tiles and no D20/D50/D80. Data are read locally, not downloaded by a solve or copied into version control.

The M13 primary-only fixture is 3267 × 3274, with the [retained identity and archive](phase-35.md#offline-solver-rerun). Used pointing `(250.42, 36.46)` degrees and nominal `1.0069 arcsec/pixel`. Correct vertical small-angle FOV is `0.9157196111` degrees for this height. An initial exploratory probe mistakenly used `0.6488` degrees and failed; it is not counted as successful capability evidence. The reusable probe now calculates FOV from the actual height and explicit scale.

| Probe | Observed outcome | Wall time, one thread |
| --- | --- | ---: |
| Explicit D05, TAN | Solved; no SIP terms | 0.474 s |
| Omit `-D` | Solved; log identifies D05; same linear WCS | 0.470 s |
| `-D auto` | Solved; log identifies D05; same linear WCS | 0.472 s |
| D05 with `-sip` | Solved; forward and inverse SIP order 3 | 0.473 s |
| `-extract2 5` | Solved; detection CSV; also enables SIP-3 | 1.512 s |
| Auto FOV with known pointing | Solved | 3.397 s |
| Half the correct FOV | No solution, exit 1 | 0.304 s |
| Explicit empty catalog folder | No solution; `.ini` reports missing database | 0.073 s |
| Request uninstalled D20 in D05 folder | **Solved using D05**; native fallback changes the request | 0.477 s |

Timings include process startup and image load. These are fresh processes with previously accessed local files; OS cold-cache performance is not asserted. Both original and staged M13 file hashes remained unchanged. Raw commands, stdout, `.ini`, `.wcs` and a manifest are in ignored `.tooling/phase36a/native-matrix/`.

### Frozen adapter decisions

- For this pinned CLI, fresh Automatic mode delegates with `-D auto` and an explicit local `-d` directory, capturing the actual selected database from native progress output. Omission of `-D` also worked, but an explicit Auto request is clearer in diagnostics. Inventory and reject missing manual choices before launching; do not rely on native `-D d20` to pin a missing catalog.
- Parse chosen-database output as a versioned capability, not arbitrary success text. Validate the actual data and candidate WCS as well. Multi-D-catalog selection and another executable version remain 3.6B cases, not a capability proven by the D05-only experiment.
- Native `.ini` contains success and WCS geometry, not a matched-star count/RMS contract. The log's reference count refers to quads. `-extract2` returns detections with WCS-derived sky coordinates; it does not supply independent catalog associations. Do not turn these fields into 15-star acceptance evidence.
- The supported command-line executable is the initial implementation target. The installed graphical application's command-line behavior is unverified and is not silently substituted. Keep user GUI settings out of the dependency chain.
- Request and inspect SIP explicitly. Native ASTAP supplies its own degree-3 fit. A Boolean SIP flag does not provide degree-2 control or independent fit validation.

These outcomes refine the [ASTAP-first decision](adr/0017-astap-first-validated-solving.md); they do not change its offline/source-preservation rules.

## ASTAP-only catalog validation route

Added an original [read-only D-series decoder](../src/astromosaic/astrometry/astap_catalog.py) and [focused tests](../tests/integration/test_astap_catalog.py). It reads the documented HNSKY 1476/5 layout: 110-byte header, five-byte records, 24-bit RA, sectioned signed declination and magnitude. It verifies selected density, record layout, required tiles and consistent epochs, retains record-based identities, and bounds I/O and retained stars. Cancellation is checked between 20 KiB record blocks; section state survives block boundaries. A modified/truncated tile or exceeded budget fails without a partial result.

The D05 header explicitly records **epoch 2025**. The compact file has no per-star proper-motion vectors, so validation must report that epoch and must not claim a fresh epoch propagation. RA/Dec quantization is approximately 0.077/0.039 arcsec. No Seiza import is needed for this query.

The [validation probe](../tools/phase36_validation.py) measures masked/valid SEP sources and performs unique mutual nearest associations within three source pixels of a candidate. Wide fields are subdivided into bounded local cones. To avoid chance matches against numerous faint catalog stars, their catalog candidates are limited to the brightest `max(30, 3 * measured sources)` in each query cell. Both angular and source-pixel residuals and regional support are reported. Production integration must retain the backend's identification/confidence evidence and test unrelated fields; this diagnostic alone is not a universal false-match probability estimator.

| M13 candidate | Independent D05 matches | RMS | P95 |
| --- | ---: | ---: | ---: |
| Native ASTAP TAN / Auto TAN | 168 | 0.629 arcsec | 1.203 arcsec |
| Native ASTAP SIP-3 | 168 | 0.683 arcsec | 1.343 arcsec |

The worse SIP result is retained as a model-selection control. A native SIP success cannot automatically replace TAN. D05 and Seiza both derive from Gaia DR3; the check is independent of the native residual computation, not a claim of unrelated catalog provenance. Native fit membership is unknown, so these numbers are **not held-out** errors. A controlled training/validation split remains required for new application-controlled models in 3.6E.

Format review used [official ASTAP source](https://github.com/han-k59/astap/tree/ca272460a1f2ec9b0201de9942693b496182ae39), particularly the catalog format description and CLI output writer, at the recorded commit. The reviewed source identifies MPL-2.0; no Pascal source or implementation was copied into the Python decoder. The separately installed Gaia-derived data retain upstream ESA/Gaia/DPAC acknowledgment requirements. This does not resolve all release redistribution work under Q-005.

## TIFF metadata at panel import

The owner supplied `tests/20.TIF` and `tests/21.TIF`. Both are 6000 × 4000, 16-bit RGB without embedded celestial WCS. The application previously read only FITS-style AstroMosaic TIFF metadata and therefore missed their camera EXIF optics.

Added [standard EXIF/XMP optical reading](../src/astromosaic/io/tiff_metadata.py) in the TIFF I/O adapter. The existing background panel inspection now receives camera model, physical focal length and nominal sensor pixel pitch. Panel Settings displays the camera and embedded optical hints while preserving explicit overrides. Both CLI solving and desktop jobs use the same read-only header translation.

| Field | Both owner files |
| --- | --- |
| Camera | Nikon D5300 |
| Physical focal length | 24 mm |
| Focal-plane X/Y resolution | `83841555 / 32768` pixels per centimeter |
| Nominal X/Y pitch | 3.90832445796 micrometers |
| Nominal central scale | 33.5895744211 arcsec/pixel |
| Rectilinear vertical angular extent from these optics | About 36.08 degrees |

The earlier linear-height approximation gives 37.32 degrees. For future broad-field ASTAP hints, use the angular extent from known rectilinear optics (`2 * atan(tangent height / 2)`) instead of treating a central tangent-plane scale as a constant sky angle across the whole frame. Optical numbers remain hints; they do not establish actual calibrated WCS or physical lens distortion.

The metadata adapter accepts standard inch/centimeter focal-plane units, handles rational numbers and standard XMP fallback, and preserves existing FITS-style values. It does not infer pixel pitch from print DPI, use 35 mm equivalent focal length as the physical lens value, or guess a camera sensor size from its name. A declared reference-size mismatch, digital zoom or invalid units leaves inferred pitch unset. Without reference dimensions, EXIF pitch is explicitly nominal and resampling should be checked. Malformed XMP and invalid optional camera text do not invalidate readable science pixels. It does not apply Adobe lens profiles or copy serial/GPS metadata into reports.

Unit conventions were checked against [CIPA's Exif/XMP mapping](https://www.cipa.jp/std/documents/e/DC-X010-2017.pdf) and the [Adobe EXIF namespace](https://developer.adobe.com/xmp/docs/xmp-namespaces/exif/). New [metadata tests](../tests/integration/test_tiff_optics.py) cover units, rational values, unsupported hints, precedence, resampling ambiguity and the actual dialog display. The [owner fixture tests](../tests/integration/test_owner_tiff.py) pin source hashes, load metadata through panel inspection and independently verify staged green-channel samples with CFITSIO. These private rendered-camera inputs are astrometry/I/O fixtures, not calibrated linear photometric truth.

## Owner wide-field results

Initial ASTAP FOV-auto probes timed out at 25 seconds; unhinted Gaia under the old 0.1–20 arcsec/pixel wrapper range timed out at 30 seconds. That interval excluded the files' nominal scale. Once EXIF optics entered the existing solve path, both solved blind in about 5–6 seconds including source measurement. Original hashes remained unchanged.

| File | Legacy TAN matches | Native TAN RMS | Broad blind SIP-3 matches | Native SIP-3 RMS |
| --- | ---: | ---: | ---: | ---: |
| 20.TIF | 890 | 53.797 arcsec | 992 | 9.926 arcsec |
| 21.TIF | 894 | 53.906 arcsec | 1009 | 10.318 arcsec |

The broad SIP probes used native Seiza directly with **0.1–120 arcsec/pixel**, no pointing or scale seed, and a 30-second search limit. Native false-match probabilities were about `1.45e-71` and `4.63e-94`. These are experimental candidates, not adoption of native SIP into the production UI policy. The recovered central scale was about 34.59 arcsec/pixel, consistent with approximate metadata rather than an exact physical calibration.

Independent D05 checking found:

| File / model | Unique matches | Angular RMS | Other recorded evidence |
| --- | ---: | ---: | --- |
| 20.TIF / TAN | 1178 | 50.235 arcsec | Regional residuals retained |
| 21.TIF / TAN | 1206 | 50.745 arcsec | Regional residuals retained |
| 20.TIF / SIP-3 | 1425 | 13.116 arcsec | Regional residuals retained |
| 21.TIF / SIP-3 | 1461 | 13.227 arcsec | RMS 0.429 source px, P95 0.843 px, outer P95 0.960 px |

The fine 9 × 9 support map for 21.TIF has insufficient-star cells, especially toward the lower-right field. Those cells retain null residual summaries; passing coarse/global metrics is not a whole-field accuracy certificate. Final SIP promotion still needs the frozen coverage, no-fold/inverse and controlled out-of-fit criteria in 3.6E. Q-019 tracks this acceptance work.

With correct wide-field hints and a Gaia-derived pointing, another ASTAP probe explicitly recommended **W08**, fell back to D05 and cropped internally. Hinted and full-sky searches returned no solution in 0.18/0.71 seconds. No W08 data were installed or downloaded. Do not promise that D05 alone covers these wide images; keep the tested Gaia fallback available and report the actual native catalog/crop behavior.

### Measured validation cost

The first broad-field validation took about 46 seconds. Profiling identified Python-list inputs to Astropy coordinate construction as the main cost, rather than the catalog decoder. Converting coordinate columns to float64 arrays reduced the SIP validation to about 11 seconds including repeated source measurement, with about 32–33 MiB catalog reads. The production contract therefore reuses one measured star field and uses array inputs; a ten-second dispatch reserve is not a fresh independent budget and must be verified under the total deadline in 3.6C. The 124-second profiled control has instrumentation overhead and is not presented as an ordinary timing.

## Frozen implementation contracts

The [manifest](../tests/fixtures/plate_solve_v36.json) fixes the 15-match floor, RMS formula, native confidence, 9 × 9 sampling/support, low-order SIP training/held-out requirements, error tolerances, recovery caps, 120-second panel budget and cleanup/cancellation targets. They are requirements for implementation and verification, not a claim that the current solver enforces them.

Changes from initial proposals are:

- Broaden the explicit blind recovery interval from 0.1–20 to **0.1–120 arcsec/pixel**, supported by both owner images. Keep one bounded search rather than an unbounded sequence of increasing ranges. Fields outside the supported interval remain explicit failures.
- Use native ASTAP Auto on the pinned CLI, retain a manual preflight and record the actual selected data. Other native versions and catalog combinations require their own capability evidence.
- Use an original bounded D-series catalog query for the ASTAP-only match/RMS path. Preserve catalog epoch/precision and label native versus independent versus genuinely held-out metrics correctly.
- Use version 2 for new sidecar quality/timing metadata when integrated; keep reading v1 as geometry-only evidence and preserve old files. Separate edge status from the ordinary catalog qualification grade.
- Use angular FOV from geometry/rectilinear optics for broad-field selection. Keep EXIF physical units and source provenance explicit; no print-resolution or camera-model lookup shortcut.

Frozen synthetic recipes include a known TAN field, linear skew without SIP, SIP-2/3 with 1/3/8-pixel corner vector displacement, mirrored parity, RA wrap, unrelated catalog/duplicate associations, and center-only support. The seed, grid, coordinate and coefficient definitions are recorded before implementing the new fitting/acceptance behavior. Phase 3.6D/E will materialize these recipes in focused algorithm tests; a recipe is not a passed numerical solve.

## Reproduction and checks

Use the existing locked environment with the optional Gaia and desktop extras when those checks are required. Keep all external data and generated output ignored. Development probes make no network requests and refuse an existing output folder.

```powershell
.venv/Scripts/python.exe tools/phase36_capabilities.py --astap .tooling/astap/cli/astap_cli.exe --catalog .tooling/astap/catalog --image .tooling/phase2-solve-evidence/m13-primary.fits --output .tooling/phase36a/reproduce-native
.venv/Scripts/python.exe tools/phase36_tiff_probe.py tests/20.TIF tests/21.TIF --astap .tooling/astap/cli/astap_cli.exe --catalog .tooling/astap/catalog --gaia-catalog .tooling/phase2-gaia/stars-deep-gaia17.bin --gaia-index .tooling/phase2-gaia/blind-gaia16.idx --skip-astap --direct-gaia --gaia-sip 3 --output .tooling/phase36a/reproduce-tiffs
.venv/Scripts/python.exe -m pytest -q tests/integration/test_astap_catalog.py tests/integration/test_tiff_optics.py tests/integration/test_owner_tiff.py
```

- A normal source checkpoint passed **112 tests**, with native OpenGL skipped by default. After additional malformed/zero-zoom cases, the final native run passed **all 117 tests**, including OpenGL and the new metadata/owner cases. Visible test windows/dialogs were placed on the second monitor (`LS24DG30X`).
- Ruff, formatting checks, strict mypy and Poetry lock validation passed. Final documentation checks are recorded in the handoff journal.
- SHA-256 and size of all three installed Seiza catalog/index files matched the versioned bundle manifest. Original TIFF hashes and green-channel staging checks passed. Both owner images are ignored by Git; they are optional and skipped when absent elsewhere.
- No source image, earlier sidecar, user solver preference, private image upload or native ASTAP GUI setting was changed. Portable application acceptance is still part of 3.6F; no updated frozen desktop bundle is claimed by this source-stage completion.

Phase 3.6A's capability/reference contract is complete. Continue with 3.6B ASTAP priority/catalog integration, then C–F enforcement, model validation and packaged acceptance. Q-015–Q-019 remain open for the applicable implementation/acceptance work; native success and the metadata fix alone do not complete Phase 3.6.
