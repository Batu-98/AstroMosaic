# Phase 3.6: ASTAP Priority and Reliable Plate Solving

- **Date:** 2026-11-17
- **Status:** The 3.6A capability freeze is complete. 3.6B–3.6F passed on the local Windows host. Full acceptance still needs the real dense-catalog matrix. [3.6A evidence](phase-36a.md) · [Implementation results](phase-36-results.md)
- **Entry condition:** Phase 3.5C passed on Windows 11 x64. Preserve its fixtures and evidence as the pre-change baseline.
- **Delivery:** The owner authorized [Phase 4A](phase-4a.md) to start from the locally verified 3.6F baseline. Full Phase 3.6 acceptance and the separate Phase 3F clean-machine check remain open.
- **Authority:** The owner requested ASTAP priority, automatic ASTAP catalog selection, at least 15 matches, comparable RMS limits, bad-scale recovery, SIP/edge accuracy, and a total solve budget. [Architecture](../astro_mosaic_python_first_architecture_en.md#phase-36-plate-solve-reliability) · [ADR-0017](adr/0017-astap-first-validated-solving.md)

This is the implementation contract. The prior dispatcher tried Gaia first, defaulted to D05 and accepted eight Gaia matches. The Phase 3.6 dispatcher uses ASTAP first, Automatic catalogs, common catalog validation and a shared deadline. The [reference manifest](../tests/fixtures/plate_solve_v36.json) records the initial frozen targets. The measured ASTAP-only recovery adjustment below preserves the same panel budget.

## 1. Goals and boundaries

Deliver one local, CPU-capable solve policy shared by the headless CLI and desktop. Reuse usable WCS first; prioritize the installed ASTAP program for new solutions; use Seiza/Gaia as the fallback. Stop on the first candidate that passes the applicable quality and geometry checks. Keep scientific inputs immutable and publish only complete, source- and mask-bound sidecars.

Implement this as the existing solver adapters plus small orchestration, validation and catalog-query functions. Do not build another blind solver. Existing NumPy, SciPy, Astropy and SEP cover candidate measurement and low-order fitting; retain optional Seiza for Gaia. No Qt dependency is introduced into processing. Native ASTAP is already called by the current adapter; automating its GUI is not needed for the normal workflow.

The phase does not add online solving, implicit downloads, native PixInsight XPSD support, high-order SIP above degree 3, TPS, RGB photometric calibration, or a finished-mosaic WCS refit. It validates mono and RGB FITS/TIFF astrometry using the existing signal/channel policy. Masks, legitimate negative/zero/above-one intensities and final sampling of original pixels remain unchanged.

## 2. Frozen 3.6A decisions and values

| Item | Planned baseline | Decision/evidence status |
| --- | --- | --- |
| Backend priority | Existing effective WCS → ASTAP hinted → ASTAP blind recovery → Gaia hinted/blind recovery | Owner-directed; replaces the earlier Gaia-first order for new Phase 3.6 runs |
| New-solution match floor | At least 15 unique, accepted image/catalog star pairs after outlier rejection | Required across ASTAP and Gaia; detection or quad counts are insufficient |
| Angular RMS ceiling | `R = max(3.0 arcsec, 2.0 * s)`; `s` is the smaller positive local X/Y plate scale at the solved center, in arcsec/pixel | Frozen future 3.6D policy; boundary recipes are in the reference manifest |
| Gaia false-match probability | Finite and in `[0, 1e-3]` | Retain the existing independent confidence requirement |
| Catalog selection | Automatic for a fresh setup; preserve explicit manual D05/D20/D50/D80 choices | Use verified native `-D auto` on the pinned CLI with actual selection reporting and application preflight; other capabilities need validation |
| Distortion | Compare TAN with supported SIP degree 2/3; accept additional terms only with supported spatial coverage and independent validation | Frozen sample/selection targets; implementation and held-out acceptance are 3.6E work |
| Per-panel total budget | Default 120 seconds; positive configurable value | Frozen for 3.6C implementation; includes preparation, backend work, validation and publication |
| Legacy attempt limit | Keep `--timeout` as a per-attempt upper limit, default 60 seconds | Add a separate total-budget option; do not silently reinterpret existing scripts |
| Cleanup and cancellation | Cleanup allowance 5 seconds beyond the solve deadline; cancellation target at most 2 seconds on named local fixtures | Frozen targets to verify in 3.6C; report a breach as a failure, not a guarantee on all storage |

The RMS ceiling is a rejection limit, not a target accuracy. Its 3-arcsecond floor is looser than the current two-pixel rule for scales below 1.5 arcsec/pixel. Do not describe it as uniformly stricter or use it to relax the existing M13/M42 regression envelopes. Report both angular and source-pixel errors, P95, maximum error, and spatial coverage. Masked/non-square pixels must not gain an artificially generous threshold from the larger axis. None of these ceilings replaces the independent fixture gates in Section 8.

## 3. Ordered local solve policy

1. **Inspect and reuse effective WCS.** In project mode, check source/mask-bound sidecars before the embedded header according to the saved project choice. Validate dimensions, coordinates and inversion. Reuse remains fast and does not require installed catalogs. Label an older or embedded result as geometry-validated when it lacks measured quality evidence; do not invent a match count or claim the new 15-match gate passed. Provide an explicit revalidate/re-solve action for the owner to replace that result with a new qualified sidecar.
2. **ASTAP hinted.** Use available pointing and vertical FOV. A scale-only hint can drive a full-sky search at that FOV. Use FOV auto when scale is unknown. Resolve the installed catalog automatically unless manually pinned. A backend success is a candidate until the quality and geometry checks pass.
3. **ASTAP recovery.** On failure or candidate rejection, use explicit FOV auto (`-fov 0` on the tested CLI) and a staged header without pointing or scale. With Gaia configured, discard pointing and search the full sky. With ASTAP alone and both hints supplied, retain the explicit pointing for a local FOV search, reported as `fov-recovery`. This preserves scale recovery where the full-sky FOV loop exceeded its allowance. With neither hint, go directly to full-sky FOV auto. The local variant requires credible pointing; use a compatible Gaia index for independent bad-pointing recovery.
4. **Gaia hinted.** If a local Seiza catalog and usable original pointing/scale exist, try them with the remaining allowance. ASTAP's failure alone does not prove every original hint is wrong. Validate the Gaia confidence and common quality measures. Cache bounded source measurements within this panel job for retries and validation.
5. **Gaia scale-free blind recovery.** If a compatible local index is installed, remove both position and the failed scale constraint. Use the frozen 0.1–120 arcsec/pixel broad interval and log its limits. The owner TIFF probes demonstrated why the earlier 0.1–20 wrapper interval was insufficient. The retry must not remain within ±20% of a rejected scale. A narrow-scale blind optimization is optional only if it leaves the broad recovery allowance and does not duplicate an earlier call; it is not required for this phase.
6. **Finish with an explicit outcome.** Accept and atomically publish a qualified result, or return unsolved, quality-rejected, unavailable, cancelled or budget-exhausted with ordered attempt details. Do not publish an approximate quad placement as a qualified solve. Missing ASTAP skips its family and leaves Gaia usable; missing Gaia leaves an ASTAP-only installation usable when it can meet the same quality evidence contract.

No stage restarts the panel clock. Do not repeat a missing/corrupt catalog error as another full image search. Manual catalog selection remains pinned across recovery; Automatic may reselect with a recorded reason. At most two ASTAP and two required Gaia searches are planned, excluding bounded model fitting and validation, rather than a catalog-by-FOV-by-model Cartesian search.

## 4. ASTAP executable and automatic catalog policy

### 4.1 What was checked during planning

The installed CLI identifies itself as **ASTAP CLI-2026.11.01**. Its hidden `-h` call reports separate database-path (`-d`), database-name (`-D`), FOV auto, SIP, output-base, progress/log and thread options. The current adapter already invokes that executable with staged input and a single search thread. Following the planning help check, [3.6A real probes](phase-36a.md#native-capability-evidence) verified native Auto and SIP-3, exposed fallback from a missing manual D20 choice, and established the local quality-evidence route.

ASTAP's official documentation describes automatic catalog selection and third-order SIP, including support in the command-line build. The website and the installed CLI differ in the documented SIP argument form, so flags must be capability/version tested. Native auto behavior must not be inferred solely from the GUI's Auto control or an old source snapshot. [Official guide](https://www.hnsky.org/astap.htm#astap_command_line) · [Official source repository](https://github.com/han-k59/astap)

### 4.2 One user-facing Automatic mode

- Discover catalogs only in the user-selected catalog folder, known installation locations associated with the selected executable, and explicitly added local roots. Do not recursively search the whole disk. Prefer an explicit folder and report ambiguous installations.
- Inventory supported installed D05/D20/D50/D80 sets. Validate tile layout and required field coverage or bundle completeness; a single file with the right prefix does not establish a usable full catalog. Cache inventory using catalog identity and invalidate it on file changes.
- **First preference:** delegate selection to ASTAP's native automatic mode when the selected CLI demonstrably supports it, respects the selected folder, and provides an auditable chosen database. Probe the correct syntax; do not assume `-D auto` works. In some versions omission of `-D` may be the route, which must be tested independently of global GUI settings.
- **Second preference:** AstroMosaic resolves Automatic to a supported installed database and passes an explicit `-D`. Freeze a deterministic suitability table in 3.6A. Start by preferring the densest eligible installed D-series catalog, with named FOV applicability and manual override; compare startup/search cost before changing this policy for speed. Unknown FOV must not force D05 or pretend a narrow-field catalog is installed.
- Record requested mode, selection implementation, resolved database, data root, version/fingerprint, FOV assumption and selection reason. An opaque `catalog=auto` alone is insufficient reproducibility evidence.
- Limit reselection to a distinct recovery decision within the existing ASTAP budget. Do not try every installed database indefinitely. Unsupported wide-field catalogs such as G05/W08 are reported as outside this phase's tested D-series matrix, rather than misidentified as supported D catalogs.
- Show `Automatic` and explicit D-series entries in settings. Preserve an old explicit D05 setting on upgrade; offer Automatic as a deliberate change. Fresh settings default to Automatic. Changing selections does not download, move or delete a catalog.

### 4.3 Using the installed ASTAP application

Prefer the tested CLI executable. An installed `astap.exe` may be supported through its command-line interface only after version, process exit, output format, SIP controls, threading and settings-side-effect checks pass. Both variants use the same scratch-file and deadline contract. User GUI preferences must not become hidden dependencies or be permanently changed by an automated solve. Opening ASTAP interactively remains an optional diagnostic step, outside the automatic job.

The pinned CLI uses native Auto when all detected choices are supported and complete. Other versions or mixed-format folders use an explicit complete D-series choice. The Windows adapter can use an ASCII scratch alias for a readable catalog path outside the CLI's code page. The tested D05 data could not solve the owner TIFFs after native cropping; the installed Gaia index identified those fields.

## 5. Common candidate quality and evidence

### 5.1 Match count and RMS

For every newly accepted ASTAP or Gaia solution, establish at least 15 distinct image-star/catalog-star associations after robust rejection, with one-to-one identities. Record matched count, residual units and definition, actual local pixel scale, angular RMS, pixel RMS, P95, maximum and coverage. Use the same finite-coordinate checks and source/mask convention on both backends. Do not count matched quads, duplicated stars, detected stars or WCS-transformed detections as independent catalog matches.

The current ASTAP adapter checks `PLTSOLVD` and agreement of `.ini`/`.wcs` geometry but does not expose match count/RMS. Resolving this is a required 3.6A dependency:

1. Check whether the supported native version exports actual matched correspondences and defined residuals through documented files/logs. Treat version-specific parsing as an adapter contract with fixed fixtures.
2. If native evidence is insufficient, measure source stars with the existing masked SEP path and cross-match against independent local catalog coordinates around the candidate WCS. Use a bounded, read-only query adapter for the installed ASTAP catalog so ASTAP-only configurations remain supported. An installed Gaia catalog can supply verification coordinates when available; Seiza must not become mandatory for an ASTAP-only run.
3. Freeze the ASTAP catalog query format/precision, star identity, epoch treatment, coverage and memory limits before implementing the reader. This is a validation query, not another blind solver. If the required format cannot be supported reliably, record the limitation and keep this gate open; do not silently downgrade acceptance to `PLTSOLVD=T`.

`-extract2` can supply detections with sky positions computed from the solved WCS; those positions alone are not catalog truth. Native summaries may supplement diagnostics, but arbitrary console text and missing metrics must not be interpreted as zero RMS or 15 matches. Gaia retains its false-match check in addition to measured count and geometry. Report catalog quantization/epoch limits; do not copy a Gaia probability into ASTAP diagnostics.

### 5.2 Reuse and quality grades

Distinguish `geometry-only` reuse, `catalog-validated` new solutions and `rejected` candidates in diagnostics. Keep schema naming/version decisions in 3.6A. Legacy WCS can still render after ordinary geometry validation, with its quality evidence marked unavailable. An explicit strict revalidation must satisfy the new gate or leave the earlier attached WCS unchanged. This prevents the 15-match policy from falsely invalidating historical projects or certifying them without evidence.

## 6. SIP and field-edge accuracy

Treat the solve as field localization followed by a bounded model-validation decision. Retain valid source SIP on reuse; remove old distortion when producing a fresh TAN header. Do not mix stale source SIP with a new linear solution.

- Test native ASTAP SIP explicitly on its supported version and inspect actual output coefficients. Test Seiza with an explicit supported `sip_order`; installed defaults are zero. An enabled option is not proof that a model was returned or improved the field.
- Compare TAN, SIP-2 and SIP-3 on the same verified correspondence pool. Native ASTAP exposes its own supported degree; do not claim arbitrary degree control from a Boolean flag. If native correspondence/fit controls cannot support the required comparison, use a small application-controlled Astropy fit around the solved field for model selection. Avoid another global blind search for each degree.
- Freeze a deterministic spatial split before fitting. For application-controlled fits, hold out 20% of pairs, at least 10 for a SIP comparison, across quadrants and outer regions; keep those stars out of the accepted fit. Do not call a native fit's residuals held-out unless its actual fit membership establishes that separation. Label ordinary independent-catalog checks separately from true out-of-fit errors.
- Let `k(d) = (d+1)(d+2)/2 - 3` be the SIP terms per axis. Proposed training floors are `max(30, 5 * 2 * k(d))`: 30 for degree 2 and 70 for degree 3, plus the held-out sample. Require coverage in all four quadrants and at least six of nine grid cells over the usable sky domain. Require at least ten held-out outer-region stars across three outer sectors when making an edge-accuracy claim. Insufficient coverage retains TAN only if TAN meets its applicable edge gate; otherwise return an actionable insufficient-support outcome.
- Promote a more complex model only with at least 10% held-out P95 improvement, no edge P95 worsening beyond the frozen numerical allowance, and the common count/RMS gate. Start the no-worsening allowance at `max(0.05 px, 2% of baseline edge P95)` and freeze it before tuning. Low-order SIP is not added just because training RMS decreases.
- Validate center, corners and a 9 × 9 domain grid for finite transforms, parity consistency, no Jacobian sign reversal/fold and forward/inverse agreement within the existing `1e-4 px` tolerance. A masked field's unsupported boundary is reported as unvalidated; no unsupported whole-frame accuracy claim follows from center-only stars. Longitude wrap, crop/rotation and mirrored parity are explicit cases.
- Keep the chosen WCS in the same sidecar geometry used by preview and export. Invalidate geometry caches after adoption. Final export samples original intensities once through the composed transformation; SIP introduces no preprocessing resample or display stretch into science data.

The 15-match floor is enough to consider a supported TAN candidate; it does not authorize a SIP model with only 15 stars. Real data without adequate outer stars can still have a valid localized solution, but must not be reported as having verified field-edge accuracy. Strict edge validation/re-solve requests cannot be satisfied by that weaker evidence grade.

### 6.1 Full-field skew and distortion diagnostics

The owner clarified that the phase must quantify behavior across the image, including interior regions, rather than report only one RMS or a corner pass/fail. Produce separate model and measured-error layers over the original source-coordinate domain:

- **Global linear geometry:** Report rotation, X/Y plate scale, anisotropy, parity and skew/shear from the linear tangent-plane transformation. Define skew as the departure of the transformed pixel-axis angle from 90 degrees. Record the reference frame and decomposition convention so rotation or unequal pixel scales are not mislabeled as skew.
- **Spatial model displacement:** Compare the adopted full WCS with a defined best-fit linear TAN reference on the same source field and tangent plane. Report `dx`, `dy` and displacement magnitude in source pixels, with angular equivalents. Separate nonlinear SIP displacement from global linear geometry and the known sky-projection effect. This is model-implied displacement relative to the stated reference, not direct proof of physical lens distortion.
- **Local geometry:** Sample the local mapping/Jacobian to report position-dependent scale, anisotropy and shear with an explicit reference/convention. Keep the no-fold/parity and inverse checks. Start with the existing 9 × 9 sample grid spanning center, interiors, edges and corners; the continuous WCS can be evaluated at other positions without storing a full-resolution vector buffer. Grid density and summary resolution remain bounded and are frozen in 3.6A.
- **Measured local astrometric error:** For each spatial cell, report actual verified-star count and available residual RMS/P95/max separately from predicted displacement. Preserve the distinction between in-fit, independently checked and genuinely held-out stars. Start with a five-star minimum for a numerical regional residual summary, to be frozen in 3.6A; mark lower support as insufficient. The image-wide 15-match floor is not a claim that every cell has 15 stars or validated accuracy.
- **Support map:** Label regions as measured/validated, model-only extrapolation, insufficient support or excluded sky mask as applicable. A selected TAN model with zero SIP terms does not establish zero physical distortion. Masked/foreground areas and starless boundaries must not appear as measured zero-error regions. A smooth model prediction outside the measured area remains explicitly unvalidated.
- **Reviewable result:** Store bounded grid/cell diagnostics and reference definitions with the solve report, keyed to the same source/mask/WCS identity. Expose a distortion-vector/magnitude view and an error/support view in the existing solver-details workflow, with units and unsupported regions visible. Compute diagnostics from the accepted geometry without modifying or resampling source pixels, within the same deadline and resource limits.

Acceptance includes an analytic no-distortion field, a known linear skew without SIP, a nonlinear field with edge and interior distortion, and a center-only star distribution. Verify that rotation, skew, predicted distortion and residual error remain distinct; recovered spatial values meet the frozen synthetic truth tolerance; and the center-only case leaves unsupported regions unvalidated. A field-wide accuracy claim requires spatial evidence under the frozen support policy, rather than mere availability of a WCS value at every pixel.

## 7. Total deadline, cancellation and reporting

Use one monotonic per-panel deadline, created before source opening/fingerprinting and preparation for that panel. Include catalog discovery/open, tiled star measurement, scratch creation/write, all native searches, fallback, common validation, SIP comparison and atomic publication. Reusing measurements or staged input is allowed only for identical source/mask/signal settings; retained data remain within the existing memory and scratch budgets.

Frozen initial allocation for implementation and verification:

| Search | Maximum search allowance, additionally capped by remaining panel time |
| --- | ---: |
| ASTAP hinted | 20 seconds |
| ASTAP blind/FOV recovery | 25 seconds |
| Gaia hinted | 20 seconds |
| Gaia broad blind recovery | 30 seconds |

These are caps, not a promise that every attempt receives its maximum. The overall panel budget is 120 seconds. Preparation and validation consume that same budget. Reserve 10 seconds for candidate validation/publication when allocating a new search; shorten or skip a search when its remaining useful allowance is exhausted. Native time limits are `min(stage cap, legacy per-attempt limit, remaining deadline minus reserve)`. Early failures leave time available to later stages, but the ASTAP family does not inherit the whole panel budget while Gaia is available. Phase 3.6A measurements support sharing star measurements and using float64 array inputs for validation; verify cold/warm limits and overrun behavior in 3.6C rather than treating this allocation as a passed enforcement test.

When the configured local Gaia star catalog is absent, a full-sky ASTAP recovery may borrow the unused fallback time up to 60 seconds. It still respects the per-attempt limit, total deadline and reserve. A pointing-assisted FOV recovery retains the 25-second cap.

Check the deadline and cancellation before each stage, after native return and immediately before publication. Late success after the deadline must not publish. Keep user cancellation distinct from search timeout and panel-budget exhaustion. Do not start another backend after cancellation or total exhaustion. Kill/reap ASTAP and clean incomplete scratch files, temporary sidecars and owned buffers. Preserve earlier completed panels and pre-existing outputs.

Seiza's native search already has time/cancel callbacks, but catalog open and other native operations also need measured bounds. If a required operation cannot meet the frozen deadline/cancellation contract cooperatively, use the existing spawn-based isolation approach for that solver work rather than terminating an arbitrary thread. Verify frozen Windows worker startup and cleanup; do not claim the total limit is enforced merely because a native `time_limit` was set. Storage/OS delays and any cleanup overrun remain visible failures in the report.

Add an optional job-wide budget for multi-panel solving, also monotonic and never reset between panels; the effective panel deadline is the earlier job/panel deadline. Queue wait and one-time batch eligibility scans are reported separately and bounded by the job budget when supplied. Without a job budget, describe the per-panel guarantee and cumulative elapsed time accurately. A deliberate user retry is a new job with a new recorded budget.

Diagnostics include policy/version, requested and elapsed total seconds, cleanup time, per-stage preparation/search/validation time, remaining time at dispatch, timeout versus cancellation reason, original/effective hints and their provenance, scale/FOV removal, catalog selection, native versions, candidate rejection metrics and sidecar identity. Keep logs free of image pixels and unrelated private paths.

## 8. Fixtures and acceptance matrix

Phase 3.6A froze fixture identities, seeds, optical/WCS truth recipes, source hashes, catalogs, native versions and target thresholds in the reference manifest. Use deterministic contract tests for branching/budget boundaries and real executables for format, numerical and process claims. The values below are frozen acceptance targets, not already measured capabilities; the evidence identifies fresh-process/warm-file checks and does not assert OS cold-cache results. Record hardware/cache conditions for later performance acceptance.

| Area | Required cases | Acceptance |
| --- | --- | --- |
| Priority and eligibility | Existing embedded/sidecar WCS, unsolved sky, foreground-only, both backends, each backend alone | Reuse skips solving; ASTAP precedes Gaia on new solutions; missing backend gives an explicit skip; a failed/low-quality ASTAP candidate reaches Gaia only with time left |
| Catalog automation | Only D05; only a dense D catalog; multiple D catalogs; unknown/wrong FOV; manual selection; missing/truncated/moved tiles; Unicode/spaced paths | Automatic resolves only a usable installed supported catalog and records why; manual choice persists; recovery removes old FOV assumptions; absent data produce actionable failure without downloads |
| Match and RMS boundaries | 14/15/16 unique matches; duplicates; NaN/negative metrics; just below/equal/above `R`; 0.5/1/3 arcsec pixel scales; non-square pixels | 14 and invalid evidence rejected, 15 accepted only when other gates pass; exactly-on-threshold policy explicit and tested; no inferred match count from detections or quads |
| False-match protection | Wrong field, wrong parity, unrelated catalog patch, misleading four-star/quad placement | No new qualified sidecar; Gaia probability retained and ASTAP independent associations required |
| Bad scale and position | Correct/missing hints, scale factors 0.5 and 2, stale pointing, RA wrap and rotation | Solvable frozen fixtures recover after the bad scale is discarded, with explicit diagnostics and within total budget; unsupported scale ranges fail honestly rather than expand without limit |
| Synthetic SIP/edges | Known TAN and SIP-2/3 with corner displacement about 1, 3 and 8 px, mirrored/rotated fields, sparse and center-clustered stars | Qualified supported solutions: held-out whole-field and outer P95 each ≤0.5 source px, sampled-grid maximum ≤1 px; round trips ≤`1e-4 px`; SIP promoted only when its selection gate passes; insufficient support does not produce a false edge claim |
| Real astrometry | Retained M13, M42 40′ and 55′ plus a named sparse and distorted wide-field sample | Preserve recorded archive-WCS envelopes with frozen numerical repeatability tolerance; start new independent-catalog validation targets at P95 ≤1 source px overall and ≤1.5 px in supported outer regions. Report native/in-fit versus held-out separately; unsupported cases remain visible |
| Time and cancellation | Exhaust during source read, measurement, staging, each backend, validation, SIP fit and pre-publication; missing/corrupt catalogs; user cancellation; optional job budget | No new work/publication after effective deadline; no clock reset; measured completion within budget plus frozen cleanup allowance on local Windows fixtures; cancellation/timeout kills and reaps owned processes and removes incomplete outputs |
| Persistence/geometry | Legacy project and v1 sidecars; new quality metadata; strict revalidation; mask edit; reopened SIP export | Legacy data remain readable with honest evidence grade; stale-mask WCS rejected; successful revalidation produces a new sidecar; no overwrite; preview/export use identical chosen geometry |
| Scientific and platform regression | Mono and RGB FITS/TIFF, supplied masks, negative/zero/above-one pixels, cancellation/retry, Qt-free CLI, CPU/OpenGL desktop bundles | Source/mask hashes unchanged; current registration/photometry/export gates retained; independent CFITSIO reopen verifies pixels/coverage/WCS where applicable; current full suite and relevant portable checks pass |

For the real M13 archive comparison, freeze the prior per-backend center/corner maximum plus an initial 0.1-arcsecond repeatability allowance in 3.6A; report the original numbers alongside new ones. Do not treat archive WCS as exact catalog truth. The M42 40′ blind case is a required investigation of denser installed ASTAP catalogs, not a guarantee that catalog density alone will solve it. Close Q-015 with measured support requirements or a reproduced limitation rather than tuning the case out of the suite.

## 9. Delivery stages

### 3.6A — Freeze contracts, capabilities and reference evidence

**Completed:** 2026-11-18. [Capability/fixture evidence](phase-36a.md) · [Frozen reference manifest](../tests/fixtures/plate_solve_v36.json)

**Scope:** Capture the unchanged Phase 3.5 baseline; verify the exact ASTAP version's native-auto selection, chosen-catalog reporting, actual matched-pair/residual interface, SIP flag/output and CLI versus application behavior. Select the ASTAP-only validation route. Freeze quality definitions, catalog suitability, TAN/SIP sample requirements, numerical cases, supported domains, total/attempt/cleanup budgets and report migration. Keep catalog acquisition explicit and outside solve calls.

**Acceptance:** A versioned capability table, fixture manifest and reproducible commands exist. Native auto and the 15-match ASTAP-only evidence path have either passed a real probe or have a concrete bounded adapter implementation contract; unresolved format/capability blockers stay open. Expected failures are specified. Numeric proposals in this plan are frozen or revised with reasons before solver tuning. Q-016, Q-017 and Q-018 link to the outcome.

### 3.6B — ASTAP priority and catalog automation

**Scope:** Implement Automatic/manual catalog handling and executable capabilities; move the ASTAP family before Gaia; preserve WCS reuse and staged source protection. Validate native outputs consistently, preserve SIP cards when present and report catalog identity. Keep catalog querying separate from solver selection.

**Acceptance:** Priority, skip and catalog-mode cases pass with adapter fixtures and real installed ASTAP. No hardcoded fresh D05 default, GUI automation, implicit catalog install or source mutation is needed. Missing/incompatible ASTAP leaves Gaia usable. Native-auto acceptance names the selected catalog or uses the deterministic explicit-resolution alternative.

### 3.6C — One end-to-end deadline and reliable cleanup

**Scope:** Thread the per-panel and optional job deadlines through source work, adapters and publication. Add dispatch caps/reserve, cancellation outcomes, process cleanup and structured elapsed-time reports. Preserve the existing attempt-limit meaning.

**Acceptance:** Deterministic fake-clock tests and real Windows process cases cover each deadline boundary, including late success and nonresponsive native work. The frozen local cleanup/cancellation targets pass. A rejected or timed-out ASTAP attempt cannot consume an unbounded Gaia wait. Earlier finished panels survive job cancellation or exhaustion.

### 3.6D — Common quality gate and bad-scale recovery

**Scope:** Raise the new Gaia floor to 15 and apply equivalent evidenced associations/RMS checks to ASTAP candidates. Implement the frozen ASTAP-only validation route; keep Gaia probability checks. Add one bounded ASTAP FOV-free and Gaia scale-free recovery path, with original and effective hint provenance.

**Acceptance:** Match/RMS boundary cases, false placements, 0.5×/2× bad hints and each backend alone pass the frozen gates. A recovery result demonstrates that the wrong scale was removed. Candidate success without measurable quality is rejected and never silently published. Fifteen matches are not confused with SIP eligibility.

### 3.6E — Supported SIP and independent edge checks

**Scope:** Implement explicit native/model capability selection, bounded low-order fits, spatial validation, full-field skew/distortion and local-error/support diagnostics, distortion-transition cleanup and sidecar geometry adoption. Reuse already measured sources and bounded local catalog queries. Keep optional degree promotion and diagnostic sampling under the total deadline.

**Acceptance:** TAN/SIP model-selection, sparse/clustered rejection, synthetic true geometry, real independent-catalog checks, parity/RA wrap and inverse-grid gates pass. Full-field diagnostics separate linear skew, nonlinear model displacement and measured local residuals, with unsupported regions visible, as specified in Section 6.1. Native in-fit statistics are not relabeled held-out. A SIP result survives sidecar save/load and gives matching preview/export coordinates and independent reopened WCS. Extra fitting and diagnostics cannot bypass time or memory limits.

### 3.6F — Desktop/CLI migration and Windows acceptance

**Scope:** Expose Automatic/manual catalog settings, total/attempt budgets, revalidation and quality evidence in the existing settings/job workflow. Update CLI help, diagnostic/sidecar versions, old-format loading and documentation. Keep solver configuration and acceptance policy shared across interfaces.

**Acceptance:** Windows source and portable Qt-free CLI reproduce the new solver matrix. CPU and OpenGL desktop runs verify settings restart, eligible panels, responsive progress, cancellation/exhaustion/retry, partial batch results, project reopening and SIP-aware export. Run the full current suite, lint/type/lock checks and appropriate independent FITS/TIFF checks. Record tested source/native/catalog versions, measurements, failures and unsupported conditions. Mark Phase 3.6 complete only after all mandatory gates pass; the separate clean-machine claim still needs its own evidence.

## 10. Integration impact and improvements

| Area | Required impact control |
| --- | --- |
| Earlier ADRs/evidence | ADR-0017 supersedes only the earlier priority for future 3.6 behavior. Preserve Phase 2/3.5 evidence and the comparison as historical observations. Seiza remains the optional Gaia backend. |
| Solver API and tests | Separate discovery, candidate production, validation and accepted result without a generic plugin framework. Keep stage names recognizable for old sidecars; version richer mode/timing/quality data instead of guessing missing values. Update order-sensitive tests intentionally. |
| Catalog/validation scope | ASTAP priority needs actual match evidence, which the present adapter lacks. A minimal read-only catalog query may be the largest addition. Prove it in 3.6A, check data terms under Q-005 and measure catalog mappings separately from tile buffers under Q-004. |
| Projects and sidecars | Keep v1 inputs readable. Version new metadata as needed; do not silently recertify old results or invalidate all saved projects. Record effective policy, backend/catalog, SIP model, validation grade and source/mask identity for a new sidecar. Preserve manual choices and earlier files. |
| Preview/refinement/export | Adopt a single chosen geometry and invalidate derived caches; rerun the existing held-out relative registration and photometry checks. New absolute SIP must not be fitted again inside widgets or applied twice. |
| User workflow | Default fresh catalog selection to Automatic, show selected data and why a candidate failed, distinguish unavailable/unsolved/quality rejection/cancel/budget exhaustion. Preserve completed panels and actionable retry. |
| Phase 4A/4C | Use the shared solve report and budget contract from 3.6 in scripts and in the desktop terminal. |
| Phase 4B | Reuse deadline/resource reporting for scaling; keep the 12-panel FITS/TIFF workload and blend/photometry gates. Phase 3.6 does not establish those performance results. |
| Packaging | Continue explicit external ASTAP/catalog deployment. Verify the optional native worker and clean PATH behavior on Windows. Do not silently switch to an untested installed executable/catalog after discovery. |

Useful improvements within this phase are a cached local inventory, one measured star field per panel job, one reusable staged ASTAP input, and explicit quality provenance. Add these only where identical-input checks and budget measurements support reuse. A final-mosaic Gaia refit, new catalog formats and high-order models remain separate decisions.

## 11. Completion record

Before handoff, append each meaningful stage outcome to [progression](../progression.md), update [Q-015 through Q-018](../questions_open_topics.md), and fill a results table in this document or a linked evidence file. Record pass/fail and unavailable checks individually. A planning document, help output or mocked response is not runtime/numerical acceptance.

Planning checks performed: reviewed the active source, earlier ADRs and 3.5 evidence; consulted the official ASTAP guide/source repository; read installed CLI help in a temporary directory without opening a window. Repository documentation review passed 330 local file/directory links and anchors across 34 Markdown files, new-file whitespace/fences, unique topic IDs and `git diff --check`. No solver implementation, application test or real-field catalog-selection/SIP probe was performed for this planning task.
