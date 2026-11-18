# Mosaic Master and AstroMosaic Plate Solve Comparison

Review date: 2026-11-17. The owner confirmed that “AstroMerge” means this AstroMosaic workspace.

**Follow-up:** The owner subsequently requested the [Phase 3.6 plan](phase-36.md), including ASTAP priority and automatic catalog selection. [ADR-0017](adr/0017-astap-first-validated-solving.md) records that planned direction. This comparison describes the inspected pre-3.6 implementation and remains unchanged as evidence; the new plan is not implemented yet.

## Scope and evidence

This review compares the local Seti Astro Suite Pro snapshot at `C:/Software/setiastrosuitepro-main` with the current AstroMosaic working tree. SetiSuite's manifest identifies version 1.24.3; that folder has no Git metadata, so no upstream commit is asserted. AstroMosaic HEAD is `5c4bb68`, with existing uncommitted Phase 3.5 changes included in the review. Those changes were preserved.

Evidence consists of source inspection, installed Seiza 0.48.2 Python signatures, 11 existing AstroMosaic tests, isolated source-method probes, and previously recorded real-field results. No comparative speed benchmark or real-image SetiSuite solve was performed. The complete SetiSuite test suite was not run: the active AstroMosaic environment does not contain PyQt6. No user image was uploaded and no production image header was modified by this review.

The most important distinction is between **Mosaic Master's panel solver**, **SetiSuite's general Plate Solver**, and **Mosaic Master's optional finished-canvas solve**. They use different entry points and fallback rules.

## Actual call chains

### Mosaic Master: panels

```text
Loaded panel WCS
  -> reuse when present, unless Force Blind is selected
  -> perform_blind_solve
     -> _blind_solve_inhouse
        -> _solve_with_GAIA_threaded(force_blind=True)
           -> local quad identification
           -> local Gaia matching, refinement and optional SIP
           -> possibly return approximate quad-seed WCS as success
     -> on failure only: _blind_solve_astrometry
        -> login -> image upload -> submission/job polling
        -> calibration JSON -> reconstructed linear TAN WCS
  -> attach WCS in memory
  -> update the original FITS header when the on-disk dimensions match
  -> mosaic the panels that have WCS
```

The panel route discards pointing but can retain a scale hint. It directly calls the Gaia worker, bypassing `_solve_numpy_with_fallback_impl` and its solver-preference dispatcher. Therefore the general solver preference does not select this panel fallback chain. `attempt_astap_solve` exists in `mosaic_master.py`, but repository-wide call-site search found only its definition. It is not the ASTAP stage of the active panel route. The bundled HTML still describes ASTAP/Astrometry fallback, so the executable code is the stronger evidence.

Source: `mosaic_master.py`, lines 3291–3349, 5638–5814, and 5933 onward.

### SetiSuite: general Plate Solver

```text
Default combined preference
  -> Gaia seeded or blind according to settings and available metadata
     -> seeded failure can retry blind after dropping pointing AND scale
  -> hinted ASTAP when seed data are considered available
  -> blind ASTAP
  -> Astrometry.net: configured local solve-field, then web
```

The general solver also offers Gaia-only, ASTAP-only and Astrometry-only preferences. This broader chain must not be attributed to Mosaic Master's direct panel entry point.

Source: `plate_solver.py`, `_gaia_pass` at line 1741 and `_solve_numpy_with_fallback_impl` at line 1821.

### Mosaic Master: finished canvas

After mosaic assembly, a separate checkbox, defaulting to enabled, calls `_gaia_solve_final_mosaic`. It uses the geometric mosaic WCS as a seed, retries blind if the seeded Gaia call fails, and adopts the returned header. A center displacement above one degree causes rejection when both WCS objects can be compared. A failure retains the geometric header.

This is an absolute astrometric refit of the blended canvas. It does not realign the constituent panels or repair stars already distorted by inconsistent panel geometry. The implementation does not compare old and new catalog residuals; its claim that a worse solution never replaces a good one is stronger than the checks. In particular, the Gaia worker can return a `quad-seed` success here too, and the adoption path has no explicit rejection of that grade.

Source: `mosaic_master.py`, lines 1932–1944 and 3884–4038.

### AstroMosaic

```text
Desktop project eligibility
  -> skip foreground-only panels and validated embedded/sidecar WCS
  -> background PlateSolveJob -> solve_project_panel -> solve_panel

solve_panel
  -> existing celestial WCS geometry validation
  -> local Gaia DR3 through Seiza
     -> hinted when pointing AND scale are available
     -> blind index retry when available and time remains
     -> confidence and geometry validation
  -> hinted local ASTAP, skipped without pointing
  -> blind local ASTAP
  -> unsolved with ordered attempt diagnostics

Successful new solution
  -> atomic JSON WCS sidecar bound to source and sky-mask identity
  -> project attachment -> shared preview/export geometry
```

Sidecar reuse happens in the project/pipeline layer; it is not a fifth backend inside `solve_panel`. Astrometry.net, both local and web, is deliberately excluded by [ADR-0005](adr/0005-offline-solver-chain.md). Seiza selection is documented in [ADR-0010](adr/0010-seiza-gaia-backend.md).

Sources: [solver](../src/astromosaic/astrometry/solve.py), [project integration](../src/astromosaic/storage/project.py), [background job](../src/astromosaic/ui/mosaic_job.py).

## Behavioral comparison

| Aspect | Mosaic Master panel path | AstroMosaic |
| --- | --- | --- |
| Local Gaia implementation | In-house Python quad identification, catalog matching and refinement | Seiza 0.48.2 native backend supplied with measured centroids |
| Pointing hints on an unsolved panel | Forced blind; position ignored | Uses valid pointing plus scale for hinted Gaia; pointing for hinted ASTAP |
| Bad scale recovery | Blind seed retries all built layers without scale after a hinted search fails | Gaia blind search retains 0.8–1.2 times the supplied scale; no scale-free retry |
| No scale | Searches installed quad layers, coarsest first | Blind Gaia searches 0.1–20 arcsec/pixel by wrapper default |
| Local fallback after Gaia | None in active panel route | Hinted ASTAP then blind ASTAP |
| Online fallback | Astrometry.net upload; request sets `publicly_visible="y"` | None |
| New Gaia distortion fit | Adaptive TAN/SIP, up to degree 5 unless pointing-only mode | Seiza calls omit `sip_order`; installed default is 0 |
| Existing SIP | Retained for source reprojection; stale terms removed when replacing a solution | Read and used by shared geometry; ASTAP SIP cards accepted if returned |
| Approximate solve accepted | Verified quad identification can be returned as successful seed-grade TAN | Gaia result must pass explicit confidence checks |
| Original FITS header | Written in place when dimensions match | Preserved; new WCS stored separately |
| Masked sky | No explicit validity/sky-mask argument on this panel solver entry | Both SEP extraction and staged ASTAP input respect effective sky validity |
| Workload management | Full image normalization/detection; Gaia worker coupled to Qt | Tiled star measurement and staged FITS writes; numerical solver independent of Qt |
| Final mosaic catalog refit | Separate optional Gaia solve | No equivalent final-canvas solve currently implemented |
| Failure reporting | Logs, status text and dialogs; failed panels can be omitted from WCS mosaic | Typed per-stage attempts and per-panel outcomes; failed panels remain retryable |

The resource distinction concerns wrapper behavior. AstroMosaic's tile budget does not cap all native catalog mappings or all internal Seiza allocations.

## Quality, validation and numerical limits

### SetiSuite

The blind core verifies candidates against the local catalog using a log-odds threshold of `ln(1e9)` and a default minimum of 12 matches. The refined Gaia path uses triangle matching, Hough fallback, iterative catalog rematching, and TAN/SIP selection. The normal refined-result gate requires at least 20 matched pairs and RMS no larger than `max(3 arcsec, 2 * solved arcsec/pixel)`. Degree-5 SIP requires at least 300 pairs. SIP complexity is penalized; a step up must earn an improvement. These are substantive capabilities, rather than just a larger list of backend names.

However, `_quad_seed_solution` can turn a failed refinement into `ok=True`. It marks `SOLVSRC='quad-seed'`, omits fitted residual cards and retains blind-identification metadata. Mosaic Master accepts that successful celestial WCS and stops its fallback. Thus “solved” can mean a catalog-refined solution or only a statistically identified approximate field placement. The approximate result has evidence behind it, but does not meet the refined-result gate.

Sources: `gaia_blind_solver.py`, lines 45, 197–210 and 368 onward; `plate_solver.py`, lines 3771–3789, 3909–3957, 4282 onward and 4600–4614.

### AstroMosaic

The Gaia wrapper requires:

- At least eight matched stars.
- False-match probability in `[0, 1e-3]`.
- Nonnegative RMS at most twice the returned pixel scale.
- A usable celestial WCS that passes the shared geometry validation.

These values do not prove superior astrometry to SetiSuite. The minimum counts differ, the statistical tests are not interchangeable, and neither an internal fit RMS nor an inverse round trip substitutes for independent sky truth.

`read_panel_geometry` checks explicit reference/scale cards, two celestial dimensions and a center round trip within `1e-4` pixel. Rendering additionally checks per-sample inversion consistency. Reusing a geometrically consistent but incorrectly pointed header can still give the wrong sky position. This limitation also applies to SetiSuite's existing-WCS usability check. Neither reuse path re-verifies the existing header against Gaia.

AstroMosaic accepts existing SIP but does not currently request a new SIP fit from Seiza. Both installed solve signatures expose `sip_order=0`; the wrapper leaves it unset. Distorted new fields therefore need representative edge tests before claiming coverage equivalent to SetiSuite's adaptive SIP branch. ASTAP staging requests `-wcs`, without explicitly requesting `-sip`; its WCS reader can preserve SIP terms when supplied, but this is not evidence that the configured command generates them.

Sources: [Gaia wrapper](../src/astromosaic/astrometry/solve.py), [geometry](../src/astromosaic/geometry/__init__.py), [ASTAP adapter](../src/astromosaic/astrometry/astap_probe.py).

## Concrete weaknesses and follow-up

1. **Approximate grade can stop Mosaic Master fallback.** The isolated routing probe confirmed that a header labeled `quad-seed` prevents the web call just like a refined result. A quality grade should be an explicit downstream contract. AstroMosaic should preserve its strict scientific result policy if approximate placement is ever added.
2. **Mosaic Master's web WCS reconstruction loses information.** It builds a TAN header from calibration JSON rather than consuming the server WCS file. The function does not read returned parity and its CD determinant is always positive: `scale^2`. Synthetic orientations 0, 30 and 90 degrees confirmed this. It also hardcodes CRPIX to `(width/2, height/2)` without requesting a centered server reference. This is a demonstrated limitation in representing arbitrary server WCS, not a measured failure rate on real images. Full WCS download and known-parity/center fixtures would be the appropriate validation.
3. **AstroMosaic retains a possibly wrong scale.** A mocked weak hinted result caused blind retry over `[0.8, 1.2]` for a 1 arcsec/pixel hint; no unrestricted retry followed. Blind ASTAP also retains the derived vertical FOV when one exists. It is blind in position, not necessarily in scale. Consider one bounded scale-free recovery attempt, with diagnostics and a total deadline.
4. **AstroMosaic has no new Gaia SIP fit.** Validate controlled distortion and held-out edge stars before selecting a bounded SIP policy. Simply raising polynomial order without evidence could overfit.
5. **Timeouts are stage limits, not an end-to-end panel limit.** AstroMosaic defaults to 60 seconds per backend stage. Gaia's deadline is established after star measurement/catalog open; ASTAP's process timeout follows staging. Multiple attempts plus preparation can exceed 60 seconds overall. SetiSuite's Gaia core has bounded candidate counts but no explicit elapsed-time deadline in this route. Its web requests each allow 600 seconds, while two polling loops each have 90 iterations and ten-second intervals. The comments estimating 15 minutes per loop do not include request duration.
6. **Cancellation has different granularity.** AstroMosaic checks tiled work and gives Seiza a cancellation callback; ASTAP polling checks cancellation at up to 0.2-second communication intervals and kills/reaps the child on failure. This is not a guarantee of 0.2-second end-to-end cancellation during all preparation/native work. SetiSuite's Gaia cancellation is checked at status callbacks; web cancellation is checked between requests and polls, so a blocking request may delay it.
7. **Source and mask protection should remain.** Mosaic Master guards against writing cropped geometry onto a differently sized source and removes stale SIP when replacing WCS. Those are useful safeguards, but equal dimensions alone do not establish pixel identity. AstroMosaic's separate source/mask-bound sidecar is the stronger reproducibility contract.

The Astrometry.net API explicitly distinguishes parity and reference-center options: [official API documentation](https://astrometry.net/doc/net/api.html). The upstream Seiza project identifies the native solver implementation and license: [official repository](https://github.com/theatrus/seiza). Version-specific behavior above was checked against the installed 0.48.2 bindings, rather than inferred from current upstream defaults.

## Catalog compatibility

SetiSuite reads its own magnitude-banded Gaia astrometric SQLite library, falling back to its XP spectral SQLite library when needed. Its locally built quad layers use the SASQ format (`.saq`). AstroMosaic expects Seiza star tiles and the matching Seiza blind index. ASTAP uses a separate selected D05/D20/D50/D80 database. The common label “Gaia DR3” does not make those files interchangeable.

The earlier [M42 verification](phase-35.md#m42-offline-astrometry-and-documents-catalogs) explicitly rejected PixInsight XPSD files as Seiza inputs. Its regional conversion experiment required PixInsight to query positions and magnitudes, followed by an in-memory Seiza catalog; this is not native XPSD support in AstroMosaic or evidence that SetiSuite's SQLite files can be opened directly. Conversion/distribution terms would need their own review before adding a supported importer.

## Real-field evidence and limits

The following numbers are **previously recorded AstroMosaic Windows results**, reviewed here but not rerun in this comparison. Error columns compare against the archive WCS at the center and four corners, rather than an independent all-star astrometric truth catalog.

| Fixture/mode | Matches | Internal RMS | Maximum center/corner error |
| --- | ---: | ---: | ---: |
| M13 Gaia hinted | 132 | 0.469 arcsec | 0.356 arcsec |
| M13 Gaia blind | 482 | 0.413 arcsec | 0.387 arcsec |
| M13 ASTAP hinted D05 | — | — | 0.800 arcsec |
| M13 ASTAP blind D05 | — | — | 0.835 arcsec |
| M42 40 arcmin Gaia hinted | 114 | 0.567 arcsec | 0.276 arcsec |
| M42 55 arcmin Gaia blind | 575 | 0.335 arcsec | 0.512 arcsec |

The 40-arcminute M42 blind Gaia case exhausted 400 hypotheses; hinted D05 failed and blind D05 timed out. [Q-015](../questions_open_topics.md#q-015---offline-solver-coverage-on-the-40-orion-field) already tracks this. There is no equivalent matched SetiSuite run here, so these numbers cannot establish a comparative success rate or speed advantage.

Source: [Phase 3.5 evidence](phase-35.md#offline-solver-rerun).

## Verification performed for this review

- `pytest -q tests/integration/test_offline_solve.py tests/integration/test_solver_setup.py tests/integration/test_desktop_solver_settings.py tests/integration/test_desktop_plate_solve.py`: **11 passed** on the current Windows environment.
- Executed Mosaic Master's actual `perform_blind_solve` method in isolation with controlled collaborators: failed Gaia reached web; `quad-seed` success stopped fallback; cancellation stopped fallback.
- Executed its actual `construct_wcs_header` with synthetic calibration records: positive determinant at all three tested orientations and CRPIX fixed to half-width/half-height, irrespective of supplied parity.
- Executed the existing SetiSuite `test_writing_a_tan_solution_removes_the_old_sip` with the actual source writer methods isolated from unavailable Qt imports: **passed**. This was not a full import/integration run of SetiSuite.
- Mocked native Seiza responses through AstroMosaic's actual `_solve_gaia`: weak confidence was rejected and the retained blind scale bounds were verified.
- Inspected installed native function signatures: Seiza 0.48.2 has `sip_order=0` for both hinted and blind calls.
- Reviewed local report links and balanced code fences, checked topic ID uniqueness, and ran `git diff --check`: passed. Existing unrelated CRLF conversion warnings were reported by Git.

## Recommended direction

Retain AstroMosaic's local chain, source immutability, mask-bound sidecars and Qt-free processing. Prioritize bad-scale recovery and distortion/edge validation before adding backend breadth. Borrow SetiSuite's strategy of removing an untrusted scale and its explicit distinction between approximate field placement and refined astrometry. Evaluate a finished-mosaic Gaia check first as a diagnostic; adopting a refitted output WCS must keep preview/export geometry and project provenance consistent. A final header refit alone cannot fix panel registration.

A future comparative benchmark should use identical pixel arrays and mask policy, declared catalog depth and versions, known parity and distortion, and cases with correct, missing and deliberately incorrect hints. Record cold/warm timings, full wall-clock time, peak memory, cancellation latency, refined versus approximate results, and independent held-out sky errors. Include M13, both M42 fields, sparse fields, rotated/mirrored images and distorted wide fields. No change to the accepted architecture is implied by this review.
