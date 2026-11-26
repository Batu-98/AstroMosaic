# Development Progress

Use this file for concise development history and handoff state. Detailed technical decisions belong in `docs/adr/`; unresolved work belongs in [questions_open_topics.md](questions_open_topics.md).

## Current State

- **Last updated:** 2026-11-26
- **Active baseline:** Python-first architecture revision 3.12 adds [Phase 7 delivery stages](astro_mosaic_python_first_architecture_en.md#105-phase-7-delivery-stages). [ADR-0023](docs/adr/0023-terrain-control-point-registration.md) records the translation and similarity decision. [ADR-0017](docs/adr/0017-astap-first-validated-solving.md) records the solver policy. See [ADR-0003](docs/adr/0003-windows-first-platform-scope.md) for Windows scope, [ADR-0006](docs/adr/0006-dual-fits-and-tiff-workflow.md) for formats, and [ADR-0007](docs/adr/0007-sky-and-foreground-mosaics.md) for mixed panels.
- **Current stage** Phase 8 closed on 2026-11-26 with the locally verified beta 15 photo workflow and Standard stellar gain safeguard. [Delivered scope and deferred criteria](docs/phase-8.md#phase-8-closure)
- **Available artifacts** The verified beta 16 desktop and console are in `dist/AstroMosaic-0.1.0b16-windows-x64/` and `dist/astromosaic-cli-0.1.0b16-windows-x64/` with their build records. The [application test guide](docs/application-tests.md) and [extended cases](docs/application-tests-extension.md) describe the ignored real-observation fixtures. [Release guide](docs/windows-release.md#verification-status)
- **8C implementation and verification** Manifest version 10 saves photo profile, exposure and brightness choices. The copied desktop CPU and OpenGL paths and console matched on the mixed ICC control. The full original photo and nine scientific products matched their references. The source suite passed 248 checks with two offscreen OpenGL skips. Native preview, export, Ruff, scoped mypy and Poetry lock validation passed. [8C results](docs/phase-8.md#8c-local-windows-package-results)
- **Version control** The current development version and published source pre-release are `0.1.0b16`. Annotated tag `v0.1.0b16` identifies the source and local Windows builds. [Beta 16 pre-release](https://github.com/Batu-98/AstroMosaic/releases/tag/v0.1.0b16)
- **8D checkpoint** Beta 15 verified the Standard stellar gain check. Six wide-dither NIRCam F200W exposures matched the archive's detector science, masks and two variance planes exactly. One flat application reduced the final aperture P95 on all four overlaps with a fitted exposure scale. Each had three to seven final apertures. The F150W reference still replays byte for byte. [8D Standard results](docs/phase-8d.md#standard-local-windows-results) · [F200W results](docs/phase-8d.md#nircam-f200w-large-dither-flat-reference)
- **8D Advanced evidence** The linked-offset bound ruled out the plane margin at unity gain on 125 of the 216 SDSS M2 sky-only RGB cycles. The Bath M51 intake passed 13 of 24 strict catalog solves. The three accepted red exposures missed the 0.5 px native geometry gate at 1.036–1.243 px P95. The positive full-scene RGB case remains open. [Linked offset results](docs/phase-8d.md#linked-additive-correction-limits) · [M51 geometry intake](docs/phase-8d.md#bath-m51-geometry-intake)
- **Public test data** Five sources provide 389 independent exposures, 22 calibration files and seven integrated masters. The library includes native 20 mm and 35 mm linear TIFFs and the multi-session MOANA Lagoon mosaic. Original hashes, credits, reproducible preparation and local intake results are recorded. [Public observation library](docs/public-test-data.md)
- **8D public RGB observations** The Lagoon Standard and M33 stellar-veto reports replayed byte for byte. The new Pleiades network passed final native geometry at 0.135–0.149 px. Its linked spatial variation stayed within 1.48 times the RGB color floor across all five groups. The fixed-gain plane missed the improvement margin and the free-gain fits lacked rank. [Pleiades results](docs/phase-8d.md#independent-pleiades-spatial-background-screen)
- **8D independent Lagoon 300 s observations** Four stacks from 35 disjoint lights supply a geometry-qualified triplet at 0.137–0.250 px P95. All four Advanced fits have sufficient rank. Standard passes the stellar guard and reduces the final mean RGB P95 by 13.80% versus Off. Every Advanced variant scores higher than Standard. The final masks and replay agree. [Long-exposure Lagoon results](docs/phase-8d.md#separate-300-s-lagoon-observations)
- **8D Bat and Wing screen** Five independent 60 s RGB stacks supply ten selection-geometry links at 0.104–0.162 native px P95. The largest shared span is 1.064 times the color floor. No triplet meets the coherence requirement on two links. The selection-only diagnostic retains Off on the best rejected triplet, and the final reserve stays sealed. The five TIFFs, selection report and three controls replay exactly. [Bat and Wing results](docs/phase-8d.md#independent-bat-and-wing-selection-screen)
- **8D ZTF and M51 archive intake** ZTF fields 730 and 768 provide 18 frozen exposure IDs. Repeated HTTP 503 leaves five of 36 products. The four independent ACS M51 panels give at most 96 of 128 required selection samples and zero usable native geometry links. The HST panels and selection replay exactly in reversed order. Final blocks stay sealed. [Archive intake and fallback](docs/phase-8d.md#ztf-archive-intake-and-hst-m51-fallback)
- **8D recovered ZTF network** All 36 products for the 18 frozen exposures are available. Retaining source-detection mask bits restores all 15 geometry links at 0.051–0.088 native px P95. The strongest shared RGB variation is 0.180 times the color floor. The rejected triplet retains Standard on selection, and the final reserve stays sealed. The corrected preparation and reversed-order reports replay exactly. [ZTF source comparison](docs/phase-8d.md#recovered-ztf-north-america-nebula-network)
- **8D Orion OSC screen** Four broadband pointings supply four overlap links at 0.098–0.138 native px P95 after catalog astrometry. The best supported spatial-to-color ratio is 0.620 and the flat-bias check reaches 0.708. Standard leads on selection and final blocks remain reserved. Reversed-order preparation and comparison replay exactly. [Orion evidence](docs/phase-8d.md#orion-simultaneous-broadband-rgb-screen)
- **8D Elephant Trunk intake** The observer's capture record supports broadband OSC. Across 120 flats and 120 short darks, the nearest temperature match is 9.1 °C apart. The candidate remains at calibration intake and both scoring reserves stay closed. The independent retrieval matches both audit receipts. [Elephant Trunk evidence](docs/phase-8d.md#elephant-trunk-broadband-and-calibration-intake)
- **8D public broadband archive search** Nine 3AM and MILAN observing ZIPs contain 4,677 FITS images and zero named calibration companions. Broadband M31 is a single light folder. The tested MILAN sessions lack optical flat-field provenance. The independent archive audit replays exactly, and scoring remains closed. [Public archive evidence](docs/phase-8d.md#public-broadband-calibration-archive-search)
- **8D GROND RGB selection** The calibrated 2XMMJ1745-2902 triplet passes relative r′ geometry and all six cross-channel checks. Its three selection spatial-to-color ratios are 0.609, 0.374 and 0.491. Each link has a negative channel-pair correlation. Standard leads under the frozen margins, zero links meet coherence admission, and the final reserve stays sealed. Registered images, masks and selection reports replay exactly in reverse order. [GROND evidence](docs/phase-8d.md#grond-rgb-coherence-and-selection)
- **8D Canon Whirlpool OSC selection** The same-session triplet passes all three relative links at 0.429–0.479 native px P95. All RGB channel-pair correlations are positive, with spatial-to-color ratios of 0.980, 0.999 and 0.611. Standard leads on selection and the final reserve stays sealed. The independent reverse replay matches calibrated RGB, masks and reports. [Canon evidence](docs/phase-8d.md#same-session-canon-whirlpool-osc-screen)
- **8D Jellyfish ISO 100 calibration** The full 45-header Jellyfish inventory and five companion archives supply zero ISO 100 bias or dark matches. The 17 ISO 100 flats are 2.5 s at 21–22 °C. All 132 distinct calibration headers, byte ranges and the project descriptor replay exactly. RGB selection remains closed. [Jellyfish evidence](docs/phase-8d.md#jellyfish-iso-100-calibration-audit)
- **8D Jellyfish shielded pedestal** Across all 17 ISO 100 flats, the disjoint masked strips agree to 0.386 DN P95. The same-frame phase estimator leads the held-strip comparison at 0.959 DN P95. G1 varies by 1.021 DN between frames. The other phases vary by at most 0.156 DN. The warm active-area additive term remains unverified and both RGB reserves stay sealed. [Pedestal evidence](docs/phase-8d.md#jellyfish-shielded-pedestal-repeatability)
- **8D Jellyfish active-area fit** The free-intercept prediction lowers the reserved flat mean P95 from 9.667 to 7.484 DN. Independent training-half intercept maps differ by 492–920 DN at P95. The full-training and reserve maps share spatial structure and differ by 105–200 DN. The absolute additive correction remains unresolved and RGB reserves stay sealed. The independent reverse replay matches the two receipts. [Flat leverage evidence](docs/phase-8d.md#jellyfish-active-area-additive-identifiability)
- **8D Jellyfish zero-light search** All 677 remaining CR2s across the six public archives match the original camera body and have ISO 640, 800 or 1600. Across 809 distinct CR2s, the 17 illuminated flats alone match the full capture settings. The reversed archive replay agrees and both RGB reserves stay sealed. [Archive and local results](docs/phase-8d.md#jellyfish-same-detector-zero-light-search)
- **8D SkyMapper intake** Nine independent Rho Ophiuchi exposures supply three linear RGB panels from native SkyMapper DR4 CCDs. Zero links qualify on native stellar geometry, and the strongest shared spatial variation is 0.0400 times the RGB color floor. Numeric selection, stable source headers and decoded arrays reproduce. Final blocks stay sealed. [SkyMapper evidence](docs/phase-8d.md#skymapper-rho-ophiuchi-selection-screen)
- **8D CFHT MegaCam M13** Nine short Elixir exposures provide three CCD 12 links at 0.270–0.331 native px P95 after a training-only affine refinement. The strongest RGB spatial-to-color ratio is 1.712. Advanced offset improves selection mean P95 by 1.202%, below both thresholds. Off ties Standard and final blocks stay sealed. Independent reverse replay verifies. [CFHT results](docs/phase-8d.md#cfht-megacam-m13-short-exposure-selection)
- **8D completion checkpoint** Both M13 CCDs now cover all five dither groups. Nineteen of 20 geometry links pass and zero qualify on RGB coherence. The matched visible red flat yields seven selection memberships crossing 2% and zero crossing 3%. Both NIRCam references, 259 source tests, six documented skips, Ruff and Poetry verify. Advanced, visible optics and portable acceptance remain open. [Closure evidence](docs/phase-8d.md#phase-8d-completion-evidence)
- **8D wide-field observations** The prior masked SIP WCS solutions passed catalog holdouts at both focal lengths. A centroid blend selected on the 35 mm training and selection sample failed to improve the larger held-out overlaps under fixed WCS. Its training-only refits failed the overall Gaia limit on two frames at each focal length. Only the 35 mm 2–3 SEP control passed 0.5 px on the primary stars. No pair passed on both holdouts. [Centroid validation](docs/phase-8d.md#nightscape-validation-of-elongated-star-centers)
- **8D visible flat evidence** MOANA's RGB masters have unresolved bias provenance. Three documented HST F606W dithers preserve native coverage and qualify two overlaps at 0.072 and 0.106 px. Once-applied absolute aperture P95 is 2.784% and 4.484% on those overlaps. F606W supplies one supported test star crossing at least 2% response. [Visible flat results](docs/phase-8d.md#visible-band-flat-field-validation)
- **8D visible RAW follow-up** Three 47 Tuc F438W dithers supply 44 and 15 distinct reserved stars across 2% and 3% measured response. A CALWF3 bias- and dark-corrected RAW replay matches the archive's Once samples within tolerance on all 50,225,160 valid pixels. Final native geometry passes at 0.054–0.086 px, with identical coverage in all modes. On the strongest link, the five reserved ≥3% stars with S/N ≥ 300 reach 0.666% Once P95. The complete held-out samples reach 3.887%–7.062%, above 1%. [F438W results](docs/phase-8d.md#f438w-wide-dithers-from-raw)
- **8D F438W CTE follow-up** The three RAW-derived Once images match all 50,187,153 valid FLC samples within tolerance. The 122 reserved memberships from 102 stars use common valid support. Pooled Once P95 changes from 6.664% to 6.619% with CTE and every pair exceeds 1%. The largest corrected-centroid geometry P95 is 0.109 px. Fainter stars show larger corrections and the residual tails have weak transfer-distance associations. The replay reproduced the measurements, masks and CTE detector planes. [F438W CTE results](docs/phase-8d.md#f438w-pixel-cte-follow-up)
- **8D independent F606W flat evidence** Four LMC dithers and a same-configuration 47 Tuc repeat match all 100,351,695 valid FLC samples after one flat division. All six LMC overlaps meet native geometry at 0.052–0.093 px P95. The complete test Once P95 of 1.464%–7.792% misses 1% on every overlap. The repeat has 0.166% median response change and 1.871% Once flux P95. Coverage stays identical across modes. [Independent F606W results](docs/phase-8d.md#independent-lmc-f606w-flat-replay)
- **8D independent F606W repeatability** Three 348 s GO-12379 FLCs pass both native geometry directions at 0.019–0.035 px P95. Selection retains the 10 px annulus median. Across 95–102 test stars in 42–43 blocks per link, full-sample flux P95 is 3.952%–5.107%, above 1%. [F606W repeatability](docs/phase-8d.md#independent-f606w-repeatability-control)
- **8D F606W profile follow-up** Three newly frozen Visit 07 exposures give 78–92 test stars per link in 42–45 blocks. Both native geometry directions pass at 0.017–0.026 px. Selection retains 10 px, with test P95 of 2.350%–4.337%. The 3–10 px neighbor-axis wing asymmetry is the strongest measured correlate of the absolute 10 px error (Spearman ρ 0.539, 95% sky-block interval 0.408–0.644). [F606W profile and holdout](docs/phase-8d.md#f606w-aperture-profile-repeatability)
- **8D F606W native residuals** The opened `obq` peak does not recur at the separate sky and detector positions in three other visits. The independent test has 62 stars across 34 blocks. Both geometry directions pass at 0.049–0.063 px, while each full-test flux P95 is 4.680%–6.049%. A fresh star's residual includes an exposure-local peak and a distributed wing contribution. [Native results and rerun](docs/phase-8d.md#native-residual-follow-up)
- **8D F606W local PSF** Three short, independent FLCs give 117 held-out memberships. The training-only PSF predicts 3–5 px changes on two links. No overlap supports the 5–10 px ring and the inner gains outside the 3 × 3 patches have intervals spanning zero. The three 10 px P95 values are 1.752%–2.403% with geometry qualified. [Local PSF experiment](docs/phase-8d.md#independent-local-f606w-psf-test)
- **8D F606W within-pixel PSF** A fresh four-exposure group supplies 357 test memberships. Local x/y slopes raise 5–10 px mean absolute prediction error against both comparisons on all six links. Each link has 4–8 well-signed stars, below ten. The unchanged 10 px aperture P95 is 2.455%–6.828% with geometry qualified. [Within-pixel PSF experiment](docs/phase-8d.md#independent-f606w-within-pixel-psf-test)
- **8D F606W half-pixel intake** The GO-11680 610 s pair verifies both axes at median fractions 0.570 and 0.543 px. The blind common-pixel and donor checks leave no admissible test stars. [Two-axis archive screen](docs/phase-8d.md#f606w-two-axis-half-pixel-archive-screen)
- **8D F606W richer-field follow-up** None of 109 new links meets the joint half-pixel gate. The M5 nominal pair has seven of 206 matches in range on both axes with about 0.90° field rotation. [Richer-field intake and diagnosis](docs/phase-8d.md#richer-field-f606w-follow-up)
- **8D F606W compact same-visit screen** Two of 18 new planned links measure half-pixel shifts in both axes with verified guiding. Each GO-16361 link supplies one fresh UVIS1 match and zero eligible test stars. [Compact dither screen](docs/phase-8d.md#compact-same-visit-f606w-dither-screen)
- **8D F606W stellar field preflight** Seven new links in the targeted 99-visit intake lack a shutter-A command in both half-pixel intervals. The NGC 1835 preflight supplies zero reciprocal and precision-qualified stars in the two same-acquisition 408 s shutter-A exposures. [Stellar field preflight](docs/phase-8d.md#same-orbit-f606w-stellar-field-preflight)
- **8D F606W M5 acquisition** No public M5 visit supplies two long shutter-A FLCs at the required positions. The Visit 13 pointing diagnostic reaches both measured phase limits with 138/270 matches, using one B and one A exposure. A four-exposure worksheet covers both starting blades. [M5 acquisition evidence](docs/phase-8d.md#m5-f606w-acquisition-check)
- **8D F606W M5 APT feasibility** Four 350 s exposures fit in one non-interruptible local orbit with zero overruns. Visit Planner returns three potential visibility windows. Guide-star selection and observing allocation remain pending. [APT feasibility](docs/phase-8d.md#m5-apt-feasibility-check)
- **Next planned milestone** [Phase 9 desktop undo and redo](docs/phase-9.md) starts with the edit inventory and panel add/remove/relink workflow in 9A. Deferred Phase 8 experiments retain their [revisit conditions](questions_open_topics.md#q-029---configurable-color-photometry-and-optics).
- **Open dependencies:** Q-003 tracks reference data and frozen criteria. Q-010 tracks real-scene diagnostics and the proposed terrain models. Q-016 tracks astrometry. Q-005, Q-009 and Q-020 track distribution and format work. Q-008 tracks deferred platforms and Q-011 deferred visual fill. Resolved Q-022 and Q-023 record the Windows lifecycle and ZEA results.

## Phase Overview

The table is a status summary, not a replacement for the full exit gates in Section 10 of the active architecture. Update it when evidence changes. Keep partial or unavailable validation visible.

| Phase | Status | Required exit evidence |
| --- | --- | --- |
| Preparation | Complete | Agent instructions, English documentation, tracking conventions, active-plan identification, and next task established. |
| 0 - Compatibility and scope | Complete | Locked environment, initial fixtures/contracts, solver and PySide float-texture experiments, packaged skeleton, and a small job verified on Windows 11 x64. |
| 1 - Headless reference | Complete | Correct two-panel FITS geometry, values, and coverage, independent reopening, bounded access, and a Qt-free CLI. The deferred TIFF checkpoint passed in Phase 3A. |
| 2 - Robust astronomy engine | Original gate passed | Verified local Gaia/ASTAP fallback, supplied sky masks, anchored overlap registration and stellar gains, offset/plane selection, held-out and injected-signal gates, and weak/disconnected diagnostics on Windows. |
| 3A - Linear TIFF | Complete | Mono/RGB input and output verified on Windows for samples, channels, WCS, and coverage. |
| 3B - Projects and jobs | Complete | Project save/reopen, panel relinking, responsive progress, and cancellation verified on native Windows Qt. |
| 3C - Preview and export | Complete | Verified shared preview/export geometry, automatic sky framing, sRGB visual previews, pan and zoom, display stretch, and GPU/CPU fallback on Windows. |
| 3D - Sky masks | Complete | Verified automatic proposals, manual tag and mask edits after reopening, and sky-only solving and fitting. |
| 3E - Foreground and composition | Complete | Verified WCS-independent foreground alignment, separate layer exports, and saved placement, seam, and crop edits on Windows. |
| 3F - Windows acceptance | Local checks passed | Packaged workflows, recovery, cancellation cleanup, and CPU fallback passed on the development host. Clean-machine validation remains open. |
| 3.1A - Panel WCS and optical metadata | Complete | Per-panel WCS status, embedded and edited optical hints, scale derivation, and older project compatibility verified on Windows. |
| 3.1B - Local plate solve settings | Complete | Gaia DR3 and ASTAP paths and database choice restored across restarts. Source and packaged Windows checks verified actionable diagnostics. |
| 3.1C - Desktop plate solve job | Complete | Packaged Windows CPU and OpenGL checks verified eligible panels, Gaia and ASTAP fallback, WCS sidecars, cancellation and retry, and project reopen and export. |
| 3.5A - Phase 2 review | Complete | Phase 2 criteria mapped and rerun on Windows, with added cases, reproduction steps, and regression thresholds recorded. |
| 3.5B - Revision | Complete | Focused tests protect the frozen narrow-overlap, saturation, and masked WCS reuse cases on Windows. |
| 3.5C - Verification | Complete | Windows source, portable CLI, and desktop results cover the frozen criteria, M42 plate solves, and the M31 20% overlap merge. |
| 3.6A - Capabilities and contract freeze | Complete | Native D05 Auto/SIP/manual-fallback evidence, bounded ASTAP-only quality query, owner TIFF/EXIF checks, and frozen fixture/numerical/budget/schema contracts recorded. |
| 3.6B - ASTAP priority and catalogs | Complete | ASTAP priority, real single and mixed D-series sets, native Automatic and explicit resolution, manual pinning, missing/incomplete catalogs, Unicode paths and ASTAP-only qualification verified on Windows. |
| 3.6C - Total solve deadlines | Local checks passed | Shared deadline, late rejection, source prep exhaustion, native worker and ASTAP cancellation/cleanup, and preserved partial results checked. |
| 3.6D - Quality and scale recovery | Local checks passed | Match/RMS limits, Gaia confidence, false-match controls, ASTAP-only FOV recovery and Gaia recovery from wrong pointing and both scale factors. The narrow blind M42 and cross-catalog quality results are recorded. |
| 3.6E - SIP and full-field diagnostics | Local checks passed | Synthetic truth, TAN/SIP selection, map and support diagnostics, both real TIFFs and independent reopened export. |
| 3.6F - Integration and acceptance | Local checks passed | Qt-free portable CLI, desktop CPU/OpenGL, settings and v1/v2 migration, cancellation/retry, preview and independent exports. Full external acceptance remains open. |
| 4A - Headless project automation | Complete | Creation, sky preflight, saved-layer export, desktop parity and scripted FITS/TIFF batch, progress, failure and cancellation checks passed on Windows. |
| 4B - Large mosaics and improved blends | Complete | Full FITS, RGB TIFF and mixed Windows runs matched the reference after conservative candidate selection. Resource, halo, cancellation and output-limit checks passed. Optional multiband evaluation is deferred. |
| 4C - Desktop command panel | Complete | Standalone CLI parity, live progress, history, cancellation, and window-close cleanup verified on Windows. |
| 5A - XISF interchange | Complete | Bounded mono and RGB attachments, WCS, units, coverage and contribution masks verified through independent reopening and copied Windows workflows. |
| 5B - ZEA sky projection | Complete | Saved projection, longitude wrap, projection domain, preview and export agreement, and copied Windows workflows passed. |
| 5C - Per-band output | Complete | Saved membership, band-local units and channels, common geometry, independent exports, and Windows desktop, CLI and batch checks passed. |
| 6 - Real-observation reliability | Local 6A–6E checks passed | The real references, native lifecycle, and source and portable product comparison are recorded. Fresh Windows acceptance remains open for the named 6E build. |
| 7 - Terrain panorama registration | 7A–7F local checks passed | Repeat the intended portable candidate on a fresh Windows 11 x64 installation. PA4 and the unsupported rotation models retain their recorded outcomes. |
| 8A - Photo export contract | Frozen for 8B | Record supported inputs, method compatibility, profile provenance, the real owner pair, and sample, WCS, cancellation and memory gates before implementation. |
| 8B - Full-resolution photo TIFF | Local checks passed | The native CPU and OpenGL desktops and Qt-free CLI produced the same real photo. Independent reopening, scientific parity, cancellation and retry passed. |
| 8B follow-up - Adaptive preview and crop | Local checks passed | Per-field locks, live update, area sampling, 1:1 inspection and interactive crop passed. The real crop matched the standalone export and the full reference region. |
| 8C - Photo color and exposure matching | Local checks passed | The matrix ramps, held-out brightness controls, real owner photo and native CPU, OpenGL and CLI products passed. Clean-machine acceptance remains open. |
| 8D - Advanced brightness and measured optics | Closed with deferred criteria | Standard gain safeguard verified locally. Advanced and optical qualification and integration deferred. [8D evidence](docs/phase-8d.md) |
| 8E and 8F - Additional models and acceptance | Deferred work | Additional optical and seam methods, bracket and HDR research and clean-machine acceptance are recorded in the [closure summary](docs/phase-8.md#phase-8-closure). |
| 9 - Desktop undo and redo | Planned | Verify project and editor history, save checkpoints, worker results, bounded memory and export parity in source and packaged Windows. [Stage gates](docs/phase-9.md#delivery-stages) |

## Journal Rules

- Append an entry after each meaningful completed, partial, failed, or decision step and before handoff. Do not log every tool call.
- Keep older entries intact; append corrections. The current-state summary and phase table may be edited in place.
- Use a dated heading and three to five short bullets: change, verification, related topics/decisions, and next action.
- Distinguish implementation completion from phase acceptance. Record checks that could not run and do not imply they passed.
- Dates use ISO format. Optional timestamps use `Europe/Istanbul` with an explicit UTC offset.

## Journal

### 2026-11-15 - Preparation - Completed: development workflow established

- **Changed:** Added `AGENTS.md`, `README.md`, `questions_open_topics.md`, this journal, and ADR-0001. Established English project language, bounded development steps, scientific safeguards, and mandatory issue/progress updates.
- **Verified:** Reviewed both supplied plans and confirmed revision 3.0 explicitly supersedes the earlier infrastructure. Initial workspace inspection found only those plans and no Git repository; application tests were not applicable.
- **Related:** ADR-0001 identifies the existing Python/PySide6 baseline. Q-001 through Q-007 capture compatibility, units, fixtures, budgets, licensing, solving, and FITS validation decisions.
- **Next:** Validate the new documents, then hand off the Phase 0 package/CLI and compatibility work. No application implementation is claimed by this preparation step.

### 2026-11-15 - Preparation - Completed: documentation checks passed

- **Changed:** Finalized the five new guidance/tracking documents and the initial Phase 0 handoff; retained both supplied architecture documents unchanged.
- **Verified:** Local-link and nonempty-file checks passed across all seven Markdown files; code fences are balanced and all seven seeded topic IDs are unique. Reviewed the new text for English language and consistency with revision 3.0. No application tests were run because no implementation exists yet.
- **Related:** Q-001 through Q-007 remain open with explicit actions and closure conditions; ADR-0001 records baseline selection without claiming platform compatibility.
- **Next:** Start Phase 0 with local version control, the minimal package/headless CLI, dependency checks, and numerical contracts. The development preparation request is complete.

### 2026-11-15 - Preparation - Completed: simplified agent instructions

- **Changed:** Shortened `AGENTS.md` by about two thirds, removed repeated technical detail, and reduced Section 7 to four practical completion checks. Detailed feature and phase requirements remain in the architecture plan.
- **Verified:** Reviewed the English text and preserved the baseline, data-protection rules, and tracking duties. Local links passed; application tests were not needed for this documentation edit.
- **Related:** No new open topics or architecture decisions.
- **Next:** Use the simplified instructions for Phase 0 development.

### 2026-11-15 - Phase 0 - Started: local runtime and headless scaffold

- **Changed:** Initialized local Git and added repository ignore rules, a Python 3.13 Poetry manifest, a headless CLI, and an initial bounded FITS cutout job.
- **Verified:** Installed CPython 3.13.18 and Poetry 2.5.1 in workspace-local tooling on Windows x64. Local WSL has no Linux distribution. Dependency and application checks follow the lock installation.
- **Related:** Q-001, Q-003, Q-004, Q-007.
- **Next:** Exercise the synthetic job and numerical contracts, then run the independent desktop and offline-solver experiments.

### 2026-11-15 - Phase 0 - Partial: headless checks and first ASTAP solve

- **Changed:** Locked the scientific stack and verified read-only primary FITS access with raw scaling, validity, bounded sections, and an analytic TAN reference. Added a D05 ASTAP probe that isolates source files from solver writes.
- **Verified:** The first 12 tests and the synthetic CLI job passed on Windows x64, including a real spawned worker in an installation without Qt. ASTAP solved a public DSS cutout. Filtering legacy DSS plate keywords and cross-checking ASTAP's two output files recovered the solved WCS.
- **Related:** The initial all-wheel-only install exposed the `pims` source build. Packaging with pytest installed caused the Astropy hook to abort in optional visualization discovery. The build group allows a clean retry without the test toolchain. Q-001, Q-003, Q-006, Q-007.
- **Next:** Verify the packaged CLI, exercise the signed-texture desktop probe and CPU path, and record the remaining platform gates.

### 2026-11-15 - Phase 0 - Partial: Windows compatibility experiments passed

- **Changed:** Added the signed R32F/TAN desktop probe with a CPU raster path, documented the first numerical and resource contracts, and recorded the surface-brightness decision in [ADR-0002](docs/adr/0002-surface-brightness-reference.md).
- **Verified:** 14 tests, Ruff, mypy, and Poetry lock validation passed. The frozen CLI inspected a synthetic FITS file and ran the cutout in a spawned worker. The frozen viewport passed context recreation, 1× and 2× framebuffer checks, and automatic CPU fallback. ASTAP matched the DSS reference to 0.36 arcseconds with unchanged input and verified timeout cleanup.
- **Related:** The initial Windows desktop bundle selected a foreign ICU DLL from `PATH`. A clean-path rebuild and rerun passed. [Phase 0 evidence](docs/phase-0.md) records the build steps, the measured smoke job, licenses, and target matrix. Local link and ignore-rule checks passed. The superseded, ignored `.tooling/venv-qt-meta` environment remains on disk because the tooling policy blocked recursive cleanup.
- **Next:** Collect native Ubuntu and macOS results before closing Phase 0. The separate Phase 1 gate still requires a bounded two-panel render and independent FITS export checks.

### 2026-11-15 - Phase 0 - Completed: Windows-first development gate

- **Changed:** Revised the active plan to 3.1 and recorded the owner's Windows 11 x64 scope in [ADR-0003](docs/adr/0003-windows-first-platform-scope.md). Deferred Linux and macOS support.
- **Verified:** Reviewed the revised gate against the existing Windows job, dependency lock, ASTAP and viewport experiments, and packaged runs. Reviewed the affected documents and local links. Application tests were not repeated for this documentation change.
- **Related:** Q-001 is resolved for Phase 0 and Q-008 tracks later platform support. Reviewed Mosaic Master's local Gaia and web fallback paths alongside the general solver chain.
- **Next:** Define the two-panel Phase 1 reference fixture.

### 2026-11-15 - Scope update - Open-source TIFF workflow and camera RAW

- **Changed:** Recorded open-source distribution and components, the 12-panel 6000 × 4000 TIFF target, and camera RAW priority in revision 3.2 and [ADR-0004](docs/adr/0004-open-source-image-workflow.md).
- **Verified:** Reviewed milestone and topic consistency and checked local links. This documentation change required no application tests.
- **Related:** Q-004 tracks resource measurements, Q-005 tracks the exact license and notices, and Q-009 tracks the camera RAW input contract.
- **Next:** Define the two-panel FITS reference and use its numerical contracts for the TIFF workflow.

### 2026-11-15 - Scope update - Offline solver chain and deferred camera RAW

- **Changed:** Revised the plan to 3.3. Recorded WCS reuse, local Gaia DR3, hinted ASTAP, and blind ASTAP in order. Deferred camera RAW as an import-only option.
- **Verified:** Reviewed milestone scope and checked local links. The hinted ASTAP probe remains the existing runtime evidence. This documentation update did not implement the chain.
- **Related:** [ADR-0005](docs/adr/0005-offline-solver-chain.md), Q-006, and Q-009.
- **Next:** Continue with the Phase 1 FITS reference fixture. Implement and validate the full local chain in Phase 2.

### 2026-11-15 - Scope update - Dual first-class FITS and TIFF workflows

- **Changed:** Revised the plan to 3.4 and recorded first-class status for both FITS and linear TIFF panels in [ADR-0006](docs/adr/0006-dual-fits-and-tiff-workflow.md), amending [ADR-0004](docs/adr/0004-open-source-image-workflow.md). Updated 12-panel 6000 × 4000 benchmark targets to cover both formats.
- **Verified:** Reviewed consistency across `astro_mosaic_python_first_architecture_en.md`, `README.md`, `questions_open_topics.md`, and `AGENTS.md`. Checked local markdown links.
- **Related:** [ADR-0004](docs/adr/0004-open-source-image-workflow.md), [ADR-0006](docs/adr/0006-dual-fits-and-tiff-workflow.md), Q-004, and Q-009.
- **Next:** Define the Phase 1 deterministic two-panel FITS fixture and proceed with reference headless mosaic engine development.

### 2026-11-15 - Scope update - Mixed sky and foreground mosaics

- **Changed:** Revised the plan to 3.5. Added foreground tagging, editable masks, independent sky and foreground stitching, and composition controls for placement, seam overlap, and sky-edge crop.
- **Verified:** Reviewed scope and milestone consistency, checked local document links, and recorded the requirements in [ADR-0007](docs/adr/0007-sky-and-foreground-mosaics.md). This was a documentation update.
- **Related:** Q-010 tracks mixed-panel validation. Q-011 tracks optional generative fill for visual seam gaps.
- **Next:** Define the Phase 1 two-panel FITS reference fixture. Introduce supplied sky masks in Phase 2 and the mixed-panel desktop workflow in Phase 3.

### 2026-11-15 - Phase 1 - Started: two-panel FITS reference

- **Changed:** Defined the scaled-integer and float FITS fixtures, weighted overlap, expected pixels and mask, and analytic TAN checks. Locked CFITSIO-backed `fitsio` in the development group for independent reopening.
- **Verified:** The 14 baseline tests passed. Generated both panels and checked their dimensions, sample decoding, and selected values against the [fixture manifest](docs/phase-1.md#two-panel-fixture). The reference has 65 covered pixels.
- **Related:** Q-003, Q-004, Q-007, and ADR-0002.
- **Next:** Implement the renderer, incremental export, and CLI against the frozen reference.

### 2026-11-15 - Phase 1 - Implemented: tiled FITS mosaic and export

- **Changed:** Added the Qt-free `mosaic` command, validated WCS reuse, per-tile masked sampling and weighted blending, and atomic float32 FITS export with binary `COVERAGE`.
- **Verified:** The two-panel demonstration reopened through CFITSIO with all 65 covered pixels and the full mask matching the independent reference. Astropy also verified the FITS structure.
- **Related:** Q-003, Q-004, Q-007, and ADR-0002.
- **Next:** Run the full tests, measure a larger two-panel render and cancellation, and exercise the Windows CLI bundle.

### 2026-11-15 - Phase 1 - Verified: bounded FITS reference on Windows

- **Changed:** Defaulted the mosaic CLI to one OpenBLAS thread after measuring library import commit. Documented the bounded sampler decision, export contract, and Windows measurements.
- **Verified:** 28 tests, Ruff, mypy, and lock validation passed. CFITSIO verified all 5,111,808 pixels and coverage values with two tile reservations. The 64 MiB budget case used 89.0 MiB peak working set and 101.5 MiB peak commit. Cancellation cleaned up at the next tile boundary. The new headless Windows bundle passed the reference mosaic, inspection, and spawned smoke checks from an unrelated directory. The local DSS geometry comparison also passed.
- **Related:** [Phase 1 evidence](docs/phase-1.md), [ADR-0008](docs/adr/0008-bounded-fits-sampling.md), and Q-003, Q-004, Q-007, Q-009. Q-007 is resolved for the FITS output contract.
- **Next:** Define the TIFF metadata and sample contract before desktop acceptance. Phase 2 solver, registration, and photometric acceptance cases remain open.

### 2026-11-15 - Repository setup - Prepared initial GitHub snapshot

- **Changed:** Created the private GitHub repository and prepared the source code, tests, dependency lock, and documentation for the initial commit.
- **Verified:** Reviewed the file list against the ignore rules for local tooling, images, catalogs, caches, and build outputs.
- **Published:** Pushed `main` and verified the remote initial commit `7faa650`.
- **Next:** Continue with the linear TIFF contract.

### 2026-11-15 - Licensing - Adopted GPL version 3

- **Changed:** Added the GPL v3 text and declared `GPL-3.0-only` in the README and Python package metadata.
- **Verified:** Compared the license text with the reference project and checked the lock and built wheel metadata.
- **Related:** [ADR-0009](docs/adr/0009-gpl-v3-application-license.md) records the decision. Q-005 remains open for third-party release notices and data terms.
- **Next:** Continue the TIFF contract and review bundled materials during release preparation.

### 2026-11-15 - Phase 2 - Started: astronomy acceptance cases

- **Changed:** Set the reference thresholds for held-out alignment, relative stellar gain, faint emission, supplied sky masks, and offline solver evidence.
- **Verified:** Reviewed the cases against the Phase 2 gate and the Phase 1 FITS input and memory contracts.
- **Related:** [Phase 2 fixture criteria](docs/phase-2.md#acceptance-fixtures), Q-003, Q-006, and Q-010.
- **Next:** Connect the solver adapters and build the deterministic masked FITS fixtures.

### 2026-11-15 - Phase 2 - Implemented: masked offline solving and relative refinement

- **Changed:** Added local Gaia and ASTAP stages, WCS sidecars, supplied sky FITS masks, and opt-in stellar and background refinement.
- **Verified:** Windows M13 solves passed in hinted and blind modes with both backends. The full local fallback order, native ASTAP cancellation, and masked staging passed. Synthetic and DSS refinement checks passed, including the stellar and faint-emission gates.
- **Related:** [ADR-0010](docs/adr/0010-seiza-gaia-backend.md), [Phase 2 evidence](docs/phase-2.md), Q-003, Q-006, and Q-010.
- **Next:** Verify the updated headless Windows bundle and finish the phase handoff.

### 2026-11-15 - Phase 2 - Completed: Windows astronomy gate

- **Changed:** Recorded the solver matrix, catalog installation and update policy, and relative refinement results. Built the local headless Windows CLI with the optional Gaia binding.
- **Verified:** 37 tests, Ruff, mypy, and lock validation passed. The bundle passed native Gaia and ASTAP solves, masked sidecar reimport, refinement, independent FITS reopening, and the spawned smoke case. Measured native Gaia index memory separately from render buffers.
- **Related:** Q-006 is resolved for the offline solver and catalog deployment. [Phase 2 evidence](docs/phase-2.md) records Q-003 and Q-010 checks, with later format and desktop work still tracked.
- **Next:** Validate linear mono/RGB TIFF input and output before Phase 3 desktop acceptance.

### 2026-11-15 - Repository update - Phase 2 snapshot

- **Changed:** Recorded the Phase 2 source, tests, lock, and documentation in the GitHub snapshot.
- **Verified:** All 37 tests, Ruff, mypy, and Poetry lock checks passed before publication.
- **Next:** Validate the linear TIFF workflow.

### 2026-11-15 - Dependencies - Completed: imagecodecs added for TIFF codecs

- **Changed:** Added `imagecodecs` to `pyproject.toml` and updated `poetry.lock` to provide fast C decoders (LZW, Deflate, ZSTD) for the linear TIFF workflow.
- **Verified:** Verified `imagecodecs` 2026.11.11 import and codec availability (LZW, ZSTD). All 37 existing tests, Ruff, mypy, and `poetry check --lock` passed cleanly.
- **Related:** [ADR-0006](docs/adr/0006-dual-fits-and-tiff-workflow.md), Q-009.
- **Next:** Define and verify the linear mono/RGB TIFF input/output contract.

### 2026-11-15 - Phase 3 - Planned A–F delivery stages

- **Changed:** Updated the architecture to revision 3.6 with separate acceptance gates for TIFF, projects and jobs, preview and export, masks, composition, and Windows acceptance.
- **Verified:** Reviewed the stages against the existing Phase 3 requirements and checked the documentation links.
- **Next:** Begin Phase 3A with the linear TIFF contract and fixtures.

### 2026-11-15 - Phase 3A - Implemented the headless TIFF path

- **Changed:** Defined the [linear TIFF contract](docs/phase-3a.md) and added bounded mono/RGB source windows, shared rendering, and single-file float32 TIFF export with embedded WCS and coverage.
- **Verified:** The existing 37-test FITS regression suite, mypy, and lock validation passed after integration. A TIFF writer probe reopened interleaved float32 science samples through libtiff and located the coverage SubIFD through tifffile.
- **Related:** [ADR-0011](docs/adr/0011-linear-tiff-interchange.md), Q-003, Q-004, and Q-009.
- **Next:** Run the mono and RGB acceptance fixtures on Windows, including output reopen, resource limits, and cancellation.

### 2026-11-15 - Phase 3A - Completed: linear TIFF Windows verification

- **Changed:** Added deterministic mono and RGB TIFF fixtures, including exact two-panel blends, crop and rotation, compressed and raw windows, mixed mono input formats, bounded failure, and cancellation cleanup.
- **Verified:** All 51 tests, lint, format, mypy, and lock validation passed. libtiff reopened both TIFF science layouts. The Windows M13 RGB TIFF matched the FITS Gaia solution. With a sky mask, Gaia exhausted its match search and hinted ASTAP produced the WCS used for a successful TIFF export.
- **Related:** [Windows evidence](docs/phase-3a.md#windows-evidence), [ADR-0011](docs/adr/0011-linear-tiff-interchange.md), Q-003 through Q-005, and Q-009.
- **Next:** Start Phase 3B. Verify packaged interoperability in Phase 3F and the representative TIFF resource workload in Phase 4.

### 2026-11-15 - Phase 3B - Implemented project persistence and desktop job controls

- **Changed:** Added versioned project manifests with file fingerprints, relative paths, mosaic settings, and atomic saves. Added the PySide6 project window and a cancellable render thread.
- **Verified:** The new window launched with the Windows PySide6 installation using the offscreen platform plugin. The empty project disables rendering and cancellation.
- **Next:** Exercise reopen, relinking, responsive progress, cancellation, retry, and cleanup with generated panels.

### 2026-11-15 - Phase 3B - Completed: project and render workflow

- **Changed:** Finished the desktop entry point, project and panel settings, file relinking, and a background worker with progress and cancellation. Closing during a job now defers window teardown until cleanup.
- **Verified:** All 58 tests passed on native Windows Qt. The desktop test saved and reopened a mixed-format project, relinked a moved panel, and rendered with its saved WCS and sky mask. A GUI timer fired during the live job. Cancellation and closing removed partial output, and the cancelled render could be retried successfully.
- **Related:** [Phase 3B evidence](docs/phase-3b.md), [ADR-0012](docs/adr/0012-project-manifest-and-render-worker.md), Q-004, and Q-009.
- **Next:** Add the interactive sky preview and compare its geometry with export in Phase 3C.

### 2026-11-15 - Repository update - Published the Phase 3A and 3B snapshot

- **Changed:** Committed the linear TIFF workflow, project manifests, desktop jobs, and their documentation as `1e3a05d`.
- **Verified:** All 58 tests, Ruff lint and format checks, mypy, and Poetry lock validation passed. `git ls-remote` confirmed that `origin/main` points to `1e3a05d`.
- **Next:** Implement the Phase 3C sky preview against the cropped export grid.

### 2026-11-16 - Phase 3C - Implemented the sky preview and export workflow

- **Changed:** Shared the cropped TAN sampling path between export and the preview worker. Added a progressive viewport with pan, cursor-centered zoom, and a display-only stretch on OpenGL and CPU.
- **Verified:** Reopened the cropped FITS and RGB TIFF outputs and compared their linear samples and coverage with the matching preview samples. Both display paths agreed within one 8-bit level on the native Windows framebuffer fixture. Using typed OpenGL uniform functions corrected a float uniform dispatch error exposed by that check.
- **Related:** Q-003, Q-004, and Q-009.
- **Next:** Run the full Windows regression suite and record the desktop memory and fallback checks.

### 2026-11-16 - Phase 3C - Completed: Windows sky preview and export gate

- **Changed:** Documented the viewport and shared export geometry. Set the preview's longest edge to 512 pixels, with a 160-pixel first pass for larger grids.
- **Verified:** All 62 tests passed on Windows 11 x64 with native OpenGL enabled. Focused checks passed at 2× device scale and on the offscreen CPU path. Ruff, mypy, Poetry lock validation, and local documentation links passed. Reviewed the native desktop capture and measured both display backends on the two-panel FITS workload.
- **Related:** [Phase 3C evidence](docs/phase-3c.md), [ADR-0013](docs/adr/0013-shared-preview-grid.md), Q-003, Q-004, and Q-009. Packaged acceptance remains in Phase 3F.
- **Next:** Start Phase 3D with foreground tags, source-coordinate masks, and tests for editing, reopening, and sky processing.

### 2026-11-16 - Repository update - Prepared the Phase 3C publication

- **Changed:** Prepared the shared sky preview and export snapshot for `main`.
- **Verified:** Re-ran all 62 tests on native Windows Qt with OpenGL required. Ruff lint and format checks, mypy, and Poetry lock validation passed.
- **Next:** Confirm the remote revision, then implement Phase 3D foreground tags and sky masks.

### 2026-11-16 - Repository update - Published Phase 3C

- **Changed:** Pushed the Phase 3C sky preview and export snapshot `e60d4a9` to `origin/main`.
- **Verified:** GitHub accepted the fast-forward from `1e3a05d`. The local `main` and remote-tracking `origin/main` both resolved to `e60d4a9` after the push.
- **Next:** Continue Phase 3D with foreground checks and mask editing.

### 2026-11-16 - Phase 3D - Implemented mask proposals and editing

- **Changed:** Added local thumbnail checks, a cancellable mask job, an overlay editor, and manifest persistence for foreground overrides and source-coordinate masks. Preview, export, refinement, and project-panel solving use the effective sky mask.
- **Verified:** The initial Phase 2 M13 trial recognized the synthetic foreground in the mixed copy and found no horizon in the original. The proposal on the mixed copy did not label any injected ground pixels as sky.
- **Related:** Q-010.
- **Next:** Exercise interactive edits, bounds, cancellation, and the full solver and refinement paths on Windows.

### 2026-11-16 - Phase 3D - Completed: saved sky mask workflow

- **Changed:** Rejected short horizon candidates caused by isolated stars and narrowed the unclassified band around strong edges. Saved the edited grid and foreground override in manifest version 2, with version 1 read support.
- **Verified:** All 68 native Windows tests passed. Focused 2× and CPU desktop checks, Ruff, mypy, Poetry lock validation, and local links passed. FITS and RGB TIFF fixtures verified the mask labels. ASTAP solved the mixed M13 project panel using the proposed mask. Hinted Gaia exhausted its match search on the same masked sample.
- **Related:** [Phase 3D evidence](docs/phase-3d.md), [ADR-0014](docs/adr/0014-source-coordinate-mask-grid.md), and Q-010.
- **Next:** Start Phase 3E with an independent foreground registration fixture and preserve the sky layer geometry for composition.

### 2026-11-16 - Repository update - Published Phase 3D

- **Changed:** Committed the foreground tags and editable sky masks as `1e682b1` and pushed the snapshot to `origin/main`.
- **Verified:** All 68 native Windows tests, Ruff, mypy, Poetry lock validation, and 97 local documentation links passed. `git ls-remote` confirmed the published commit.
- **Next:** Build and test image-space foreground alignment on panels without WCS.

### 2026-11-16 - Phase 3E - Implemented independent layers and composition

- **Changed:** Added masked foreground translation, a shared horizon placement proposal, and saved composition controls. Preview and export sample the original panels and record the actual layer contributions.
- **Verified:** FITS and RGB TIFF fixtures matched known terrestrial shifts. The larger case refined its result at source resolution. The native desktop workflow on the secondary monitor proposed placement, reopened the edited composition, showed common coverage, and exported a FITS composite.
- **Related:** [Phase 3E workflow](docs/phase-3e.md), [ADR-0015](docs/adr/0015-independent-layer-rendering.md), and Q-010.
- **Next:** Run the full native regression suite and focused CPU and high-DPI checks.

### 2026-11-16 - Phase 3E - Completed: Windows layer and composition gate

- **Changed:** Documented the common-raster translation model, contribution map formats, and composition workflow. The overlap display shows common coverage independently of the feathering band.
- **Verified:** All 74 native Windows tests passed with OpenGL enabled. The focused viewport and composition workflows passed at 2× device scale, and the offscreen CPU checks passed. Ruff, mypy, Poetry lock validation, and documentation links passed. Native test dialogs opened on the secondary monitor.
- **Related:** [Phase 3E evidence](docs/phase-3e.md), [ADR-0015](docs/adr/0015-independent-layer-rendering.md), Q-004, Q-009, and Q-010. Real terrestrial captures and the 12-panel workload remain follow-up checks.
- **Next:** Begin Phase 3F with a packaged Windows build and rerun the mixed-panel workflow, recovery, cancellation, and CPU fallback checks.

### 2026-11-16 - Repository update - Published Phase 3E and test guidance

- **Changed:** Added the secondary-monitor instruction for test windows and dialogs to `AGENTS.md`. Published it with the Phase 3E source and evidence.
- **Verified:** All 74 native Windows tests, Ruff, mypy, and Poetry lock validation passed. The test runner observed dialogs on the secondary monitor. The remote points to `f236a3a`.
- **Next:** Build and verify the Windows desktop and CLI packages for Phase 3F.

### 2026-11-16 - Phase 3F - Built the Windows packages

- **Changed:** Added a repeatable PyInstaller build for the desktop and Qt-free CLI with the required TIFF codecs. Added a launcher option for visible tests on the secondary monitor.
- **Verified:** The regular desktop launcher opened a native file chooser, relinked a moved TIFF, and drew the foreground in OpenGL on the second monitor. The frozen CLI passed spawned-worker, FITS, compressed TIFF, and local solver checks.
- **Next:** Verify the remaining desktop acceptance paths in the background.

### 2026-11-16 - Phase 3F - Passed local background acceptance

- **Changed:** Added a separate frozen desktop checker that runs with the portable bundle's native libraries and supplies paths to the normal project and export entry points.
- **Verified:** Offscreen CPU and hidden OpenGL passed the mixed-layer preview and export checks, relinking, simulated save failure recovery, running-job cancellation, and retry. The offscreen source suite passed 73 tests and skipped one native viewport test. Ruff, mypy, Poetry lock validation, and documentation links passed.
- **Related:** [Phase 3F evidence](docs/phase-3f.md), Q-001, Q-004, Q-005, Q-009, and Q-010.
- **Next:** Repeat the portable check on a clean Windows 11 x64 installation. The host provided no enabled Windows Sandbox or Hyper-V instance.

### 2026-11-16 - Phase 4 planning - Added local automation and desktop terminal stages

- **Changed:** Updated the plan to revision 3.7. Scheduled the scriptable project CLI in 4A, large-mosaic checks in 4B, and the desktop terminal panel in 4C.
- **Verified:** Reviewed the plan against the current CLI, headless project loader and layer renderer, and Windows package evidence. Checked local documentation links, stage and revision references, topic IDs, and patch whitespace. This was a documentation update.
- **Related:** [Phase 4 stages](astro_mosaic_python_first_architecture_en.md#102-phase-4-delivery-stages), [ADR-0016](docs/adr/0016-local-automation.md), and Q-012.
- **Next:** Define the 4A project validation and export commands and their JSON results. Repeat the portable bundle check when a clean Windows 11 x64 installation is available.

### 2026-11-16 - Phase 3.1 planning - Scheduled astronomy engine revalidation

- **Changed:** Updated the plan to revision 3.8. Added 3.1A review, 3.1B revision, and 3.1C verification of the Phase 2 engine before Phase 4A.
- **Verified:** Reviewed the sequence and exit criteria against the original Phase 2 fixtures, solver evidence, and current Windows workflows. Checked stage and revision references, local links, and patch whitespace.
- **Related** [Astronomy engine revalidation gates](astro_mosaic_python_first_architecture_en.md#phase-35-astronomy-engine-revalidation), [Phase 2 baseline](docs/phase-2.md#acceptance-fixtures), and Q-003.
- **Next:** Start 3.1A with the Phase 2 criteria-to-evidence review and baseline rerun.

### 2026-11-16 - Phase 3.1 planning - Scheduled desktop plate solving

- **Changed:** Updated the plan to revision 3.9. Added per-panel WCS and optical metadata, local solver settings, and the desktop solve job in 3.1A–3.1C. Renumbered the Phase 2 revalidation to 3.5A–3.5C and kept its verification as the entry condition for 4A.
- **Verified:** Reviewed the plan against the FITS and TIFF metadata readers, current Gaia and ASTAP adapters, and project job and WCS sidecar contracts. Checked the phase order, cross-references, local links, and patch whitespace.
- **Related:** [Desktop plate solving](astro_mosaic_python_first_architecture_en.md#phase-31-desktop-plate-solving), [Phase 3.5 revalidation](astro_mosaic_python_first_architecture_en.md#phase-35-astronomy-engine-revalidation), Q-003, and Q-013.
- **Next:** Start 3.1A by choosing representative metadata fixtures and mapping the effective WCS states.

### 2026-11-16 - Repository update - Published Windows bundles and planning snapshot

- **Changed:** Published the Phase 3F package scripts and local acceptance evidence with architecture revision 3.9 as `6685e0f`.
- **Verified:** The staged patch passed the whitespace check, and the remote main ref resolved to `6685e0f` after the push.
- **Next:** Implement Phase 3.1A with the existing Qt-free solver and project WCS contract.

### 2026-11-16 - Phase 3.1A - Completed panel WCS and optical hints

- **Changed:** Added background WCS inspection, embedded FITS and TIFF optical hints, editable overrides in manifest version 4, and shared scale derivation for the Qt-free solver. Existing project versions reopen directly.
- **Verified:** All 79 native Windows tests passed on the secondary monitor. Rebuilt desktop packages passed CPU and OpenGL checks, including WCS refresh after relinking. The CLI passed worker and export checks. Source and packaged CLIs solved the M13 reference copy using optical hints with both Gaia and ASTAP. Ruff, mypy, lock validation, and local documentation links passed.
- **Related:** [Panel workflow and Windows evidence](docs/phase-3b.md#panel-wcs-and-plate-solve-hints) and Q-013.
- **Next:** Implement Phase 3.1B local solver settings. The pending Phase 3F clean-machine check remains tracked separately.

### 2026-11-17 - Repository update - Published Phase 3.1A

- **Changed:** Published the completed Phase 3.1A code, Windows evidence, and project records as `2534333`.
- **Verified:** The staged patch passed the whitespace check. The remote main ref resolved to `2534333` after the push.
- **Next:** Implement and verify Phase 3.1B local solver settings.

### 2026-11-17 - Phase 3.1B - Completed local solver settings

- **Changed:** Added Tools → Plate Solve Settings, per-user path storage, and a cancellable background check for Gaia DR3 and ASTAP. The dialog reports the backend prerequisites and keeps path choices available when data moves.
- **Verified:** All 84 native Windows tests passed on the session's sole active display. Separate processes checked and restored real Gaia DR3 and ASTAP D05 settings. Rebuilt CPU and OpenGL desktop checks verified diagnostics and saving. The rebuilt CLI passed worker and export checks and solved M13 with both backends. Ruff, mypy, lock validation, and local links passed.
- **Related:** [Settings workflow and evidence](docs/phase-3b.md#local-plate-solve-settings) and Q-006.
- **Next:** Implement the 3.1C background desktop solve job with per-panel progress and sidecar attachment.

### 2026-11-17 - Development guidance - Added phase drafting rule

- **Changed:** Updated [AGENTS.md](AGENTS.md#1-language-and-plan) to cover phase scope, project impact, and potential improvements during drafting.
- **Verified:** Reviewed the wording against the owner’s instruction and checked the local link and patch whitespace.
- **Next:** Apply the rule when drafting or revising phase content.

### 2026-11-17 - Repository update - Published Phase 3.1B

- **Changed:** Published the local solver settings and phase drafting guidance as `31839b2`.
- **Verified:** The staged patch passed the whitespace check and the remote main ref resolved to `31839b2`.
- **Next:** Implement Phase 3.1C on the published settings and WCS contracts.

### 2026-11-17 - Phase 3.1C - Completed desktop plate solving

- **Changed:** Added the background Plate Solve job, per-panel reports, and atomic sidecar publication. Completed solutions are attached after cancellation or failure of another panel.
- **Verified:** All 85 native Windows tests passed. The session exposed one active display. Both desktop bundles passed the real Gaia DR3 and ASTAP D05 cases, including fallback, ASTAP process and staging cleanup, retry, project reopen and export, and unchanged source hashes. The packaged CLI, Ruff, mypy, lock validation, and local links passed.
- **Related:** [Desktop workflow and evidence](docs/phase-3b.md#desktop-plate-solving) and Q-006.
- **Next:** Start Phase 3.5A with the Phase 2 evidence map and baseline rerun.

### 2026-11-17 - Repository update - Published Phase 3.1C

- **Changed:** Published the desktop plate solve job, project handoff, and packaged Windows checks as `5c4bb68`.
- **Verified:** The staged patch passed the whitespace check and the remote main ref resolved to `5c4bb68`.
- **Next:** Review and rerun the Phase 2 baseline in Phase 3.5A.

### 2026-11-17 - Phase 3.5A - Completed Phase 2 baseline review

- **Changed:** Mapped every Phase 2 criterion to the current implementation and results. Recorded fixture recipes and thresholds for narrow sky support, saturation, masked WCS reuse, and real M13 crops.
- **Verified:** The 85 Windows tests, the offline solver matrix, and both packaged desktop modes passed. The held-out synthetic P95 was 0.000558 px. CFITSIO verified masked export coverage and geometry. The exploratory embedded-to-sidecar comparison found a maximum one-ULP brightness difference within the fixture tolerance. Ruff, mypy, and lock validation passed.
- **Related:** [Phase 3.5A evidence](docs/phase-35.md), Q-003, Q-006, and Q-014.
- **Next:** Add the focused regression tests in 3.5B and use the exact M13 crop recipe during 3.5C.

### 2026-11-17 - Phase 3.5B - Completed focused regression coverage

- **Changed:** Added deterministic tests for background plane rejection in narrow overlaps, saturated-star handling, and masked WCS reuse through the CLI.
- **Verified:** All 88 native Windows tests passed. Each new test detected a deliberately bypassed check in memory. The masked FITS retained its expected science samples, coverage, WCS, and sidecar provenance. Ruff, mypy, and lock validation passed.
- **Related:** [Phase 3.5B regression results](docs/phase-35.md#phase-35b-regression-results), Q-003, and Q-014.
- **Next:** Run 3.5C with the frozen synthetic and real fixtures through the source and portable Windows CLI.

### 2026-11-17 - Phase 3.5C - Completed Windows astronomy engine verification

- **Changed:** Recorded the frozen regression rerun, new M42 offline astrometry and Documents catalog format checks, and the saved M31 project and FITS mosaic with 20% panel overlap.
- **Verified:** All 88 tests and the packaged CLI and OpenGL checks passed. CFITSIO confirmed the masked reference and exact M31 reconstruction. M42 solved with hints on the 40′ field and blind on the 55′ field. A regional conversion of the Documents XPSD catalog yielded a separate validated M42 FITS with 115 Gaia matches. The narrower blind failure is recorded in Q-015. Ruff, mypy, and lock validation passed.
- **Related:** [Phase 3.5C evidence](docs/phase-35.md#phase-35c-windows-verification), Q-003, Q-006, Q-014, and Q-015.
- **Next:** Start Phase 4A. Repeat the separate 3F clean-machine check when a clean Windows host is available.

### 2026-11-17 - Local setup - Saved Gaia paths and verified portable ASTAP

- **Changed:** Saved the verified Seiza deep Gaia DR3 catalog and matching blind index in the current Windows user's Plate Solve settings.
- **Verified:** A fresh settings dialog loaded both paths and Seiza opened both files. Five settings tests passed. The portable ASTAP CLI 2026.11.01 and D05 catalog solved the M13 reference through the packaged CLI.
- **Related:** Q-006. The ASTAP check used explicit CLI paths. The desktop ASTAP fields are currently empty.
- **Next:** Start Phase 4A from the verified 3.5C baseline.

### 2026-11-17 - Local setup - Saved ASTAP paths

- **Changed:** Saved the verified portable ASTAP executable, local catalog folder, and D05 database in the current Windows user's Plate Solve settings.
- **Verified:** A separate process opened a fresh settings dialog with both the ASTAP and Gaia paths. Both backend path checks passed.
- **Related:** Q-006.
- **Next:** Start Phase 4A from the verified 3.5C baseline.

### 2026-11-17 - Research - Compared Mosaic Master and AstroMosaic plate solving

- **Changed:** Added a [source-based comparison](docs/plate-solve-comparison.md) separating Mosaic Master's Gaia/web panel route, SetiSuite's general four-pass solver, finished-canvas Gaia solving, and AstroMosaic's offline chain. Preserved existing working-tree changes and application code.
- **Verified:** Eleven existing AstroMosaic solver/setup/desktop tests passed. Isolated actual SetiSuite methods confirmed fallback routing, approximate quad-seed acceptance, fixed-parity TAN reconstruction, and the existing stale-SIP writer regression. A mocked Seiza probe confirmed confidence rejection and retained blind scale bounds; installed 0.48.2 signatures confirmed default SIP order zero. Full SetiSuite integration and comparative real-image timing were not run.
- **Related:** Q-016 records wrong-scale recovery and distortion validation; Q-015 retains the existing M42 coverage issue. ADR-0005 and ADR-0010 remain unchanged.
- **Next:** Use the report to scope a controlled solver benchmark; Phase 4A remains the active development next step.

### 2026-11-17 - Phase 3.6 - Planned ASTAP priority and reliable solving

- **Changed:** Revised the active architecture to 3.10 and added the [detailed 3.6A–3.6F plan](docs/phase-36.md) before Phase 4A. Defined ASTAP-first solving, Automatic/manual local catalogs, 15-match evidence, proposed RMS and total-budget values, bad-scale recovery, supported SIP/edge gates, migration and downstream impacts. ADR-0017 records the priority change; application code and earlier evidence remain unchanged.
- **Verified:** Reviewed the current adapters/settings/CLI, Phase 3.5 evidence and official ASTAP sources. A hidden help-only call confirmed installed CLI-2026.11.01 options; native auto selection, match/RMS extraction and SIP solving remain 3.6A checks. Content review, all 330 local file/directory links and anchors across 34 repository Markdown files, new-file whitespace/fences, unique topic IDs and `git diff --check` passed. No application tests were needed for this planning-only change.
- **Related:** Updated Q-003/Q-004/Q-015/Q-016 and added Q-017 for ASTAP automation/quality evidence and Q-018 for deadlines/migration. Existing user working-tree changes were preserved.
- **Next:** Start 3.6A capability probes and fixture/threshold freeze; do not claim implementation or 3.6 acceptance from the plan.

### 2026-11-17 - Phase 3.6 - Clarified full-field skew and distortion diagnostics

- **Changed:** Expanded 3.6E to quantify center/interior/edge geometry with a bounded model grid and regional measured-error/support views. Separated global linear skew, nonlinear WCS displacement, local scale/shear and actual star residuals. Unsupported/model-only regions cannot be presented as measured zero distortion.
- **Verified:** Reviewed the requirement against the existing SIP, source/mask identity, shared geometry and total-budget contracts. All 330 local links/anchors across 34 Markdown files, affected code fences and `git diff --check` passed; application code and tests are unchanged.
- **Related:** Q-016 now includes the full-field diagnostic and support requirement. The current phase remains planned, with implementation starting at 3.6A.
- **Next:** Freeze grid/reference definitions, regional sample support and synthetic skew/distortion truth cases in 3.6A.

### 2026-11-17 - Phase 3.6A - Started capability probes and owner TIFF validation

- **Changed:** Added reproducible local native probes and an original bounded ASTAP D-series cone decoder. Added TIFF EXIF/XMP optical hints to panel inspection, with camera display, unit/precedence checks and preserved manual overrides. Included the owner's ignored `20.TIF`/`21.TIF` as optional local regression inputs.
- **Verified:** Baseline tests passed 87 cases with the native OpenGL case skipped. Twenty-seven focused catalog/metadata/owner/inspection tests passed, and Ruff/mypy passed before subsequent probe refinements. ASTAP CLI-2026.11.01 solved M13 with omitted/explicit Auto and produced SIP-3 with `-sip`. Independent D05 checking found 168 TAN matches at 0.629 arcsec RMS; native SIP was slightly worse at 0.683 arcsec. After EXIF scale extraction, local Gaia solved both owner TIFFs with 890/894 matches in about 5–6 seconds. Original image hashes were unchanged.
- **Related:** Q-016/Q-017/Q-018 remain active. The owner TIFFs expose wide-field support and regional validation costs, tracked under Q-019. No new backend order or complete Phase 3.6 quality policy is claimed yet.
- **Next:** Finish capability evidence, spatial validation and frozen reference thresholds, then proceed to 3.6B. Keep expensive wide-field validation inside the eventual total deadline.

### 2026-11-18 - Phase 3.6A - Completed capability/reference freeze and TIFF metadata import

- **Changed:** Recorded [3.6A evidence](docs/phase-36a.md) and the [frozen manifest](tests/fixtures/plate_solve_v36.json). Added original bounded local catalog querying, native/reproducible probes and TIFF EXIF/XMP optics/camera loading with preserved overrides. Frozen broad Gaia recovery is now 0.1–120 arcsec/pixel to include the owner wide-field images; production dispatch/quality/SIP/deadline integration is still pending.
- **Verified:** All 117 source tests passed on native Windows, including OpenGL; dialogs/windows used the second monitor. Ruff, format, mypy and lock checks passed. Actual ASTAP Auto/SIP, missing manual-catalog fallback, independent M13 associations, owner TIFF staging/metadata and broad native Gaia/SIP experiments were recorded. All original image hashes were unchanged; all three Seiza files matched bundle SHA-256/size. Final documentation checks are recorded after the handoff review.
- **Related:** Q-016–Q-019 remain implementation/acceptance topics. Independent owner SIP checking improved RMS from about 50 to 13 arcsec, but fine-grid cells without enough stars remain unvalidated. W08 is absent; no catalog was installed implicitly. Earlier user changes and evidence were preserved.
- **Next:** Start 3.6B. Keep the experimental native fits distinct from final model acceptance, and retain the full Phase 3.6F portable/desktop gates.

### 2026-11-18 - Phase 3.6B - ASTAP first and catalog selection in source

- **Changed:** Existing WCS still wins. New candidates try the configured ASTAP CLI before Gaia. Fresh settings use Automatic and explicit D-series choices remain pinned. The adapter inventories complete tile sets and records actual native database identity.
- **Verified:** Twelve focused tests passed. The pinned CLI solved M13 with native Auto/D05. A real catalog path with spaces and a character outside the Windows code page required an ASCII scratch alias, then solved with the same CLI and data. Catalog files were read through links.
- **Next:** Apply one deadline around preparation, the native backends and publication. The 15-match gate and the supported SIP decision follow in 3.6D/E.

### 2026-11-18 - Phases 3.6C–3.6E - Integrated deadline, quality gate and spatial validation

- **Changed:** Source and desktop entry points share one deadline per panel. Gaia native search and validation run in bounded Windows spawn workers. Published sidecars use the version 2 quality report and retain version 1 reading.
- **Changed:** Production acceptance checks unique local catalog associations and comparable RMS, removes rejected position/scale hints during recovery, and compares TAN and SIP with a shared spatial holdout. The new panel details view separates model displacement from measured errors.
- **Verified:** Twenty-six focused numerical, workflow and deadline tests passed. Real M13 ASTAP-only and Gaia-only runs accepted TAN. Both owner TIFFs recovered SIP-3 from incorrect 0.5× scale and pointing in the initial source run, with held-out edge P95 below 0.9 px.
- **Next:** Complete native desktop and portable checks, repeat the frozen archive comparisons, and record unsupported catalogs and any remaining numerical or deployment gates.

### 2026-11-18 - Phase 3.6F - Portable Windows and owner-image checks passed

- **Changed:** Built the updated local portable package from the locked Windows environment. Added a TIFF codec prerequisite check after the first build failed LZW verification.
- **Verified:** All 138 source tests passed. The portable CLI passed independent FITS and compressed TIFF checks. Desktop CPU and OpenGL passed the plate-solve, cancellation/retry, save/reopen and export checks. A measured live ASTAP cancellation reaped its process and cleared scratch in about 0.025 seconds.
- **Verified:** Both owner files recovered SIP-3 in the portable CLI under 45 seconds. Held-out outer P95 was 0.837 and 0.874 px. Independent D05 outer P95 was 0.895 and 0.985 px. Original hashes were unchanged and both RGB exports reopened.
- **Next:** Keep [the Windows evidence](docs/phase-36-results.md) with the package. Real dense ASTAP combinations, the narrow M42 blind limit and the separate clean-machine run remain visible.

### 2026-11-18 - Phase 3.6F - Clean native timeout reporting

- **Changed:** A supplemental blind M42 deadline test found a child result colliding with the closed parent pipe. The worker now treats that closure as expected during timeout or cancellation.
- **Verified:** Added a targeted regression. The native suite passed all 139 tests. The rebuilt CLI reported timeouts with empty stderr and withheld sidecars at both 2.5- and 6-second attempt limits. The independent compressed TIFF and FITS checks and rebuilt desktop CPU/OpenGL runs passed again.
- **Verified:** Documentation review covered 36 Markdown files, 380 local links and anchors, 19 unique topic IDs and the frozen fixture manifest.
- **Next:** Retain the verified local package and the open real-catalog/clean-machine gates.

### 2026-11-18 - Phases 3.5–3.6 - Published the local Windows baseline

- **Changed:** Pushed the existing Phase 3.5 verification, solver comparison and Phase 3.6 implementation to `origin/main` as `ebb0095`.
- **Verified:** Reran all 139 native Windows source tests with OpenGL. Ruff, format, mypy, lock and staged patch checks passed. The remote branch advertises the published commit.
- **Related:** Q-015 through Q-017 and the separate clean-machine check still track the outstanding acceptance work.
- **Next:** Started Phase 4A from the verified local baseline at the owner's direction.

### 2026-11-18 - Phase 4A - Added sky project creation and preflight

- **Changed:** Added `project create` and `project validate` with version 1 JSON results and diagnostics. Creation uses the shared project writer. Validation uses the existing sky render preparation with metadata checks and an optional output path.
- **Verified:** All 143 native Windows source tests passed, including OpenGL on the second monitor. Installed and copied Qt-free CLI checks passed. The portable checker also reopened independent FITS and compressed TIFF exports. Ruff, format, mypy and lock checks passed.
- **Related:** [Phase 4A workflow and acceptance](docs/phase-4a.md) and [ADR-0016](docs/adr/0016-local-automation.md) record the CLI contract and its use in the later automation stages.
- **Next:** Add saved-layer export with progress and cancellation, then verify mixed-project parity and scripted batches.

### 2026-11-18 - Phase 4A - Verified saved-layer CLI export

- **Changed:** Added `project export` for the saved sky, foreground and composition layers through the shared project renderer. The CLI reports bounded tile progress and handles console interrupts through the job context. FITS and TIFF check cancellation at atomic publication.
- **Verified:** All 147 native Windows source tests passed, including OpenGL on the second monitor. Installed and copied portable CLI checks passed. An active Windows console break returned exit code 130 and removed scratch files in the Python module and portable launcher. Both retried at the same destination.
- **Verified:** The portable CLI and desktop produced identical pixels, coverage and contribution masks from the saved mixed FITS/TIFF project, with matching sky WCS. The copied bundle also passed independent FITS and RGB TIFF project exports.
- **Next:** Add PowerShell and Python batch examples and run the scripted success, failure and cancellation checks for Phase 4A acceptance.

### 2026-11-18 - Phase 4A - Completed Windows batch acceptance

- **Changed:** Added Python and PowerShell 7 examples using the same JSON job list and CLI output contract. The PowerShell example handles Windows console breaks while the active CLI completes its cancellation cleanup.
- **Verified:** Both examples passed against the installed CLI and a copied Qt-free portable CLI. All four cases reproduced independent FITS and TIFF results, continued past missing inputs and occupied targets, preserved completed exports during interruption, and retried at the same destination.
- **Verified:** All 147 native Windows source tests passed, including OpenGL on the second monitor. Ruff, format, mypy, PowerShell syntax and lock checks passed.
- **Next:** Start Phase 4B resource and large-mosaic checks through the verified CLI. The separate Phase 3.6 and clean-machine checks remain open.

### 2026-11-18 - Phase 4B - Verified the full-size Windows render baseline

- **Changed:** Added the [full-size generator, runner and verifier](tools/phase4b_benchmark.py) for twelve 6000 × 4000 mono FITS, RGB TIFF and mixed sources per case. Recorded the layout, limits and acceptance checks in [Phase 4B](docs/phase-4b.md).
- **Verified:** All three full outputs passed independent sample, coverage and applicable WCS checks. Peak reservations stayed from 17.125 to 20.211 MiB. The 6 MiB halo crop matched the full RGB result, the 2 GiB output cap rejected the oversized RGB job, and console cancellation cleaned up before a full FITS retry. All 147 native Windows tests and static checks passed.
- **Verified:** The FITS crop profile recorded twelve coordinate mappings and four source reads per tile. Mapping consumed 6.888 of 10.137 seconds of the profiled render.
- **Next:** Use conservative tile candidate bounds and compare the results and timings against these fixtures before changing the blending path.

### 2026-11-18 - Phase 4B - Completed conservative tile candidate selection

- **Changed:** Added output-plane footprints for ordinary TAN and placed foreground panels, with the full path for uncertain projections. The WCS check examines serialized projection cards to catch TPV normalization. The working reservation includes the cached bounds. [ADR-0018](docs/adr/0018-conservative-panel-footprints.md)
- **Verified:** The final portable CLI produced byte-identical FITS, RGB TIFF and mixed exports with 68.0–74.0% shorter elapsed times. The matching crop used 448 mappings instead of 1,344. Tight halo, output-limit rejection, cancellation and retry passed.
- **Verified:** All 154 native Windows tests, copied CLI checks and the four installed/portable batch runs passed. Q-004 records the verified resource contract.
- **Next:** Start the Phase 4C desktop command panel with the shared CLI report and cancellation contracts.

### 2026-11-18 - Phase 4C - Connected the desktop panel to the shared CLI

- **Changed:** Added the command panel and a spawned worker using the existing CLI parser, result formats, render callbacks, and cancellation context. Recorded the working-folder and session-history behavior. [Phase 4C](docs/phase-4c.md) · [ADR-0019](docs/adr/0019-desktop-command-worker.md)
- **Verified:** All seven focused desktop and project CLI tests passed. The panel's validation and exported FITS matched standalone CLI results. A cancelled export and an export interrupted by window close removed their temporary files. The test also covered Windows pipe closure after command exit.
- **Next:** Run the full native suite and the copied Windows desktop and CLI checks.

### 2026-11-18 - Phase 4C - Completed Windows command panel acceptance

- **Changed:** Extended the copied Windows desktop checker with validation, nested worker spawning, live cancellation, and sky and composition export comparisons.
- **Verified:** All 155 native Windows tests passed with OpenGL on the second display. The windowed application and portable console produced identical validation JSON and FITS bytes. The copied desktop CPU/OpenGL checks and Qt-free portable console check passed, along with Ruff, format, mypy, and the lock check. [Windows results](docs/phase-4c.md#local-windows-results)
- **Related:** Closed Q-012. The clean-machine distribution check remains open.
- **Next:** Define the first Phase 5 extended workflow and freeze its acceptance fixture.

### 2026-11-18 - Phase 4 - Verified the publication baseline

- **Changed:** Collected the Phase 4A–4C implementation, packaging checks, examples, and evidence in one baseline commit.
- **Verified:** Reran all 155 Windows tests with native OpenGL on the second display. Ruff lint and format, mypy, and the Poetry lock check passed. Reviewed the changed paths for repository scope.
- **Next:** Publish the baseline on `main`, then define the first extended format workflow for Phase 5.

### 2026-11-18 - Phase 5A - Published Phase 4 and selected XISF

- **Changed:** Pushed Phase 4A–4C as `e0a3a39` and defined the first Phase 5 workflow and fixture criteria.
- **Verified:** Queried the remote `main` reference and confirmed that it points to the published commit. Reviewed the format contract and the shared panel and export paths.
- **Related:** [Phase 5A](docs/phase-5a.md) and [ADR-0020](docs/adr/0020-bounded-xisf-interchange.md).
- **Next:** Implement the bounded reader and atomic export and run the acceptance checks.

### 2026-11-18 - Phase 5A - Implemented bounded XISF interchange

- **Changed:** Added tiled mono and RGB XISF imports, FITS-compatible WCS and calibration metadata, and atomic sky, foreground and composition exports through the CLI and desktop.
- **Verified:** The 24 focused source tests passed, including rotated RGB comparison, both byte orders, composition contribution codes, cancellation, and exact output-byte refusal. An independent `xisf` 1.0.1 RGB fixture round trip preserved 71 covered positions, sample values, and metadata.
- **Related:** Q-020 tracks broader XISF variants.
- **Next:** Finish the native Windows suite and copied-bundle checks.

### 2026-11-18 - Phase 5A - Completed local Windows acceptance

- **Changed:** Extended the copied Windows CLI and desktop checkers with XISF project, export and preview workflows. Updated the format and workflow documentation.
- **Verified:** All 165 native Windows tests passed with OpenGL on the second display. The copied Qt-free CLI and desktop CPU/OpenGL checks passed. Independent decoding matched the RGB sky export and both composition references, including coverage and contribution codes.
- **Verified:** Ruff lint and format, mypy, the Poetry lock check, and the added documentation links passed. The clean-machine distribution check remains open.
- **Next:** Define and verify the first additional sky projection.

### 2026-11-18 - Phase 5B - Selected ZEA and froze the geometry cases

- **Changed:** Defined the first additional sky grid, its manifest compatibility, and the acceptance fixtures for wide fields, the antipode, and cropped exports.
- **Verified:** The installed WCSLIB handled oblique and polar ZEA. A nominal antipodal coordinate serialized through FITS could round-trip at the rim because of floating-point rounding, so the projection needs an explicit validity guard.
- **Related:** [Phase 5B](docs/phase-5b.md) and [ADR-0021](docs/adr/0021-zea-sky-grid.md). Q-021 tracks the limiter check.
- **Next:** Wire the projection through saved settings, the tile mapper, and both entry points.

### 2026-11-18 - Phase 5B - Implemented the shared ZEA grid

- **Changed:** Added a projection setting to the CLI and desktop and persisted ZEA in manifest version 5. Preview and export share the selected geometry. Projection changes clear the desktop composition placement.
- **Verified:** The initial geometry tests passed for the oblique grid across RA zero, equivalent FITS, TIFF and XISF exports, and coverage and reimport at the polar rim. Legacy project and TAN preview tests passed.
- **Related:** Q-021 and ADR-0021.
- **Next:** Finish the native Windows suite and copied-bundle checks.

### 2026-11-18 - Phase 5B - Completed local Windows acceptance

- **Changed:** Added copied-package checks for saved ZEA projects and desktop projection selection, preview and export. Updated the workflow documentation.
- **Verified:** All 169 native Windows tests passed on the second display. The Qt-free console and CPU and OpenGL desktop package checks passed. The independently reopened wide-field exports matched preview pixels and coverage, and the tight-budget run matched the reference.
- **Related:** Closed Q-021. The clean-machine distribution check remains open.
- **Next:** Define per-band output with an explicit filter and unit contract on the saved sky grid.

### 2026-11-18 - Phase 5C - Defined saved band selection

- **Changed:** Defined band discovery, saved panel assignments, a single-band render, and the batch job selector on the existing sky grid.
- **Verified:** Reviewed the common-filter and brightness-scale checks, mask and sidecar handling, and the shared preview and export jobs.
- **Related:** [Phase 5C](docs/phase-5c.md) and [ADR-0022](docs/adr/0022-per-band-sky-products.md).
- **Next:** Add the selection through the project reader, renderer and both entry points.

### 2026-11-18 - Phase 5C - Implemented selected-band rendering

- **Changed:** Added saved panel band assignments, discovery, band-local validation, and selection in preview, export, and both batch runners.
- **Verified:** Focused source tests exercised independent mono and RGB products on the same ZEA grid, remapped masks, rejected incompatible units and layouts, and verified cancellation, retry, and CLI reports.
- **Next:** Run the full native test suite and the copied Windows and batch acceptance cases.

### 2026-11-18 - Phase 5C - Completed local Windows acceptance

- **Changed:** Added copied-package band selection checks and verified batch jobs that export multiple bands from one saved project.
- **Verified:** All 173 native Windows tests passed on the second display. Independent FITS, TIFF and XISF comparisons matched the per-band samples, coverage, units and ZEA grid. Copied CLI and desktop CPU/OpenGL checks passed. Both batch runners passed on both launchers, including cancellation and retry.
- **Related:** [Phase 5C results](docs/phase-5c.md#local-windows-results) and ADR-0022. The clean-machine distribution check remains open.
- **Next:** Complete the outstanding distribution and real catalog acceptance checks as the required test environments become available.

### 2026-11-18 - Panel import - Filled optical metadata across all supported formats

- **Changed:** Panel settings now fills available focal length and pixel size fields during background inspection. Added native XISF instrument properties, primary-directory TIFF optics, and producer-aware FITS pitch. The CLI `inspect` command now reports optical metadata and scales. Saved panel edits override the corresponding embedded values.
- **Verified:** All 33 focused tests passed for TIFF, FITS, and XISF inspection, solver hints, numeric units, missing metadata, and panel edits. Ruff, format, mypy, and Poetry lock checks passed.
- **Related:** Q-013 and [Panel WCS and plate solve hints](docs/phase-3b.md#panel-wcs-and-plate-solve-hints).
- **Next:** Run the full native Windows suite and verify the rebuilt Windows bundles.

### 2026-11-18 - Panel import - Verified Windows optical metadata workflows

- **Changed:** Rebuilt the desktop and console launchers in `.tooling/metadata-windows/dist/windows/`.
- **Verified:** All 178 source tests passed on Windows 11 x64. The native desktop import and panel settings check filled the synthetic FITS, TIFF, and XISF fields and the fields for both owner TIFFs. Both owner files returned 24 mm and about 3.9083 µm per axis. The packaged `inspect` command agreed across the formats. The copied console and desktop CPU/OpenGL acceptance checks passed.
- **Related:** Q-013, Q-019, and [Panel WCS and plate solve hints](docs/phase-3b.md#panel-wcs-and-plate-solve-hints).
- **Next:** Run the separate clean-machine Windows check and remaining catalog acceptance cases when their test environments are available.

### 2026-11-18 - Desktop - Introduced the panel control table and application themes

- **Changed:** Added a Qt table model with four property views, editable sky inclusion, weight, band and optics, and the existing panel actions. Placed the preview below the table. Added per-user dark and light themes with dark as the default.
- **Verified:** Native Windows tests covered editing, clearing overrides, saving, relinking, solving, and theme persistence. Inspected both themes in an M13 example. Fixed stale widget colors when switching to light. Ruff, format and mypy passed.
- **Related:** [Panel control table](docs/phase-3b.md#panel-control-table) and [desktop regression](tests/integration/test_panel_table.py).
- **Next:** Verify the full Windows test suite and copied desktop workflows.

### 2026-11-18 - Desktop - Verified the panel table and theme packages

- **Changed:** Built the updated Windows launchers in `.tooling/panel-table-windows/dist/windows/`.
- **Verified:** All 179 native Windows tests passed. A second desktop process loaded the saved light theme. Copied desktop bundles passed the table, theme, preview, and export workflows with CPU and OpenGL. The copied console passed its regression suite.
- **Related:** [Panel control table](docs/phase-3b.md#panel-control-table) and [packaged desktop checks](packaging/check-windows-desktop.py).
- **Next:** Run the separate clean-machine distribution check when a fresh Windows environment is available.

### 2026-11-18 - Version control - Consolidated the verified Phase 5 and desktop changes

- **Changed:** Consolidated XISF, ZEA, per-band exports, optical metadata import, the panel control table, and desktop themes into the next commit on `main`.
- **Verified:** The remote contained one branch at the Phase 4 baseline. Ruff, mypy, and whitespace checks passed before publication. The preceding desktop verification recorded 179 passing native Windows tests.
- **Next:** Run the outstanding clean-machine and catalog checks when their environments are available.

### 2026-11-18 - Phase 3.6 - Verified real dense ASTAP catalogs on Windows

- **Changed:** Recorded D20, D50 and D80 archive identities, real Windows selection and quality results, and the measured hint requirements for the 40′ Orion field.
- **Verified:** Source and copied console runs confirmed D20/D50 successes, the D80 quality rejection, incomplete-catalog handling and blind timeout. A native desktop solve with D50 passed settings, save and independent FITS export checks with the window and dialog on the second display. All source and archive hashes matched and 42 targeted tests passed.
- **Related:** Resolved Q-015 and Q-017. Q-016 retains the cross-catalog quality findings. [Dense catalog results](docs/phase-36-results.md#dense-astap-catalog-verification)
- **Next:** Inventory Windows bundle notices. The separate clean-machine check awaits a fresh Windows environment. Windows Sandbox and Hyper-V remain disabled on the development host.

### 2026-11-19 - Release - Prepared 0.1.0 source publication and Windows candidates

- **Changed:** Added a public-facing release guide and generated component notices for the desktop and CLI. The bundles carry the application license, runtime notices, upstream supplements and a native-file inventory.
- **Verified:** Both locked Windows x64 builds completed. Checked the two ZIP layouts and their 33 desktop and 31 CLI component entries, documentation links, Poetry lock and packaging code style. Application tests were deferred at the owner's request.
- **Related:** Q-005 tracks remaining binary redistribution work. [Release guide](docs/windows-release.md) · [GitHub repository](https://github.com/Batu-98/AstroMosaic)
- **Next:** Review native corresponding sources and redistribution terms before publishing the portable binaries. The clean-machine acceptance check remains open.

### 2026-11-19 - Application tests - Prepared five merge-ready image pairs

- **Changed:** Added an [agent runbook](docs/application-tests.md) and a fixture generator for real M17 tiles, narrow skewed and wide RGB skies, and synthetic and Paranal nightscapes. The local pack includes labeled panels, masks, saved projects, hashes and a contact sheet.
- **Verified:** All pairs exceeded 10% measured support overlap. Five preflights, ten source exports, independent FITS/TIFF/XISF checks, two native CPU previews and a packaged Paranal comparison passed. Qt reported one display. All 16 focused regression tests passed, and a fresh download and rebuild reproduced the fixture hashes.
- **Related:** Q-010 tracks independently acquired foreground frames. The Paranal case uses two adapted crops of one credited panorama.
- **Next:** Use the runbook for desktop and portable acceptance on a fresh Windows installation when available.

### 2026-11-19 - Application tests - Prepared a local wide-angle capture sequence

- **Changed:** Prepared a local owner-supplied case with an accepted multi-panel sky mosaic, a quick sky pair, editable masks and a foreground diagnostic. Added an optional case entry to the local fixture index.
- **Verified:** Both ready sky projects exceeded 10% overlap on their connecting edges and passed preflight, export, independent TIFF checks and desktop CPU preview. The desktop reproduced the foreground rejection. Original input hashes matched after the run.
- **Related:** Q-010 tracks the disconnected foreground alignment and Q-016 tracks the horizon-row solve failures and quality rejections.
- **Next:** Inspect shared foreground features and refine the horizon masks before retrying the excluded frames.

### 2026-11-19 - Application tests - Verified the five source and portable CLI cases

- **Changed:** Ran SKY-01 through MIX-02 through both CLI launchers. Recorded stdout JSON, progress, elapsed time and input fingerprints under `output/application-tests/20261119-110157-116/`.
- **Verified:** Both launchers passed five preflights and ten exports. Independent FITS, TIFF and XISF reads matched across launchers. All 27 prepared files retained their SHA-256 hashes.
- **Related:** Q-003 and Q-010. Full-resolution previews confirmed 17,857 and 22,579 common pixels for MIX-01 and MIX-02 respectively.
- **Next:** Finish native renderer and visual checks and summarize the run.

### 2026-11-19 - Application tests - Completed the five native desktop cases

- **Changed:** Tested all five fixture pairs on native Windows with CPU and OpenGL previews. The local `output/application-tests/20261119-110157-116/test-report.md` links the timings, logs, screenshots and independent checks. [Recorded findings](docs/application-test-findings.md#what-the-tests-established)
- **Verified:** Both renderers passed all five cases. Desktop exports matched CLI samples and masks, and display stretch left export values unchanged. The two foreground fits recovered (+454, +8) and (+510, 0) pixels. All 13 focused regressions passed with native OpenGL enabled.
- **Related:** Q-022 tracks early automation exits. Isolated runs passed, and both renderers also opened, previewed and exported the five sky projects in one window.
- **Next:** Use a fresh Windows installation for the clean-machine check. Second-monitor placement remains unverified on the single-display host.

### 2026-11-19 - Application tests - Prepared and verified ten extended cases

- **Changed:** Added a labeled pack with three separate atlas tiles, scaled FITS, polar and skewed views, wide SIP imagery, XISF validity, per-band products, and three wide nightscapes. The [extended guide](docs/application-tests-extension.md) covers overlap, expected values, and repeat runs.
- **Verified:** All ten cases passed the source and portable CLI and native CPU and OpenGL desktop. Each entry point produced 18 exports with identical samples, coverage, contribution masks, and applicable WCS metadata. Fresh public downloads reproduced the inputs and overlap geometry. The XISF input records a new creation timestamp per build. All 26 focused existing numerical tests passed.
- **Related:** Q-003 and Q-010. The single-window desktop run also provides evidence for Q-022. The local report is `output/application-tests/extended-20261119/test-report.md`. [Extended results](docs/application-tests-extension.md#native-desktop-pass)
- **Next:** Use the extended fixtures during clean Windows distribution acceptance. Qt reported one display on this host.

### 2026-11-19 - Application tests - Repeated the local owner sequence

- **Changed:** Repeated the two ready sky projects, masked plate solves and foreground checks. Saved 60 individual test logs in the local run directory.
- **Verified:** CLI and CPU desktop TIFFs matched exactly. Native CPU and OpenGL previews passed on one display. Gaia repeated 15 accepted solutions. ASTAP D05 found one additional TAN candidate under the standard gate, and mandatory edge validation rejected it. The foreground checks reproduced the expected disconnected-overlap diagnostic. All source hashes matched.
- **Related:** Q-010 and Q-016. The local report is `output/application-tests/pa4-retest-20261119-1145/test-report.md`. [PA4 findings](docs/application-test-findings.md#local-evidence)
- **Next:** Check outer-field star support and shared terrain control points before attempting another mixed mosaic.

### 2026-11-19 - Application tests - Reviewed results and proposed follow-up work

- **Changed:** Wrote the [application test findings](docs/application-test-findings.md) with priorities and measurable checks for foreground diagnostics, masked plate solving, wide ZEA preview performance and native window lifecycle.
- **Verified:** Cross-checked the three run reports, relevant logs, current code and frozen criteria. Reviewed report and guide links.
- **Related:** Q-010, Q-016 and Q-022 track existing behavior. Q-023 records the wide ZEA warning and profiling work.
- **Next:** Collect per-pair foreground rejection details and per-region catalog measurements. Clean-machine acceptance remains open.

### 2026-11-19 - Documentation - README quick starts and project support

- **Changed:** Added a Buy Me a Coffee section, moved the source quick starts ahead of the development references, and clarified supported formats and Windows release status.
- **Verified:** README link and heading checks, the support URL (HTTP 200), the Poetry lock check, and both dependency sync dry runs passed.
- **Related:** Q-005 tracks Windows distribution.
- **Next:** Continue the Windows redistribution review and clean-machine validation.

### 2026-11-19 - Documentation - Simplified the repository README

- **Changed:** Moved setup, command examples, and technical references to the [AstroMosaic guide](docs/guide.md). Put project support and licensing directly below the README introduction and updated the Windows release guide link.
- **Verified:** All five command examples were preserved. The revised Markdown links and headings resolved, the support URL returned HTTP 200, and `poetry check --lock` passed.
- **Related:** Q-005 tracks Windows distribution.
- **Next:** Continue the Windows redistribution review and clean-machine validation.

### 2026-11-19 - Release - Recorded AstroMosaic 0.1.0 Beta 1

- **Changed:** Set the installed version to `0.1.0b1`, show it with a Beta label in the desktop title, and document the source pre-release and verification process. [Release process](docs/windows-release.md)
- **Verified:** The Windows test suite passed 178 tests with the native Qt platform. The opt-in OpenGL test passed separately. The desktop title, CLI version, Poetry lock, wheel metadata, and documentation links were checked.
- **Related:** Q-005 tracks Windows binary distribution. [GitHub pre-release](https://github.com/Batu-98/AstroMosaic/releases/tag/v0.1.0b1)
- **Next:** Complete the redistribution review and clean Windows 11 x64 acceptance before publishing portable packages.

### 2026-11-19 - Documentation - Updated the GitHub repository description

- **Changed:** Updated the GitHub About description to identify AstroMosaic as Windows astrophotography mosaic software and name its supported panel formats and offline plate solving.
- **Verified:** The full description appears in the public repository page and API response.
- **Related:** [AstroMosaic GitHub repository](https://github.com/Batu-98/AstroMosaic)
- **Next:** Review search visibility after the updated description is crawled.

### 2026-11-19 - Application tests - Verified rejection stages and prioritized follow-up

- **Changed** Reviewed the application test matrix and recorded the foreground and inverse replays in the [test findings](docs/application-test-findings.md).
- **Verified** All 37 focused layer, ZEA, solve-quality, ASTAP catalog and solve-budget tests passed. The saved six-panel PA4 group rejected all 15 pairs at the thumbnail correlation gate. A synthetic TAN-SIP inverse reproduced the all-NaN warning for invalid input and for finite directions outside the projection domain.
- **Related** Q-010, Q-016, Q-022 and Q-023. Clean-machine acceptance for the intended Windows release bundles remains open.
- **Next** Add pairwise foreground diagnostic results and verify PA4 terrain correspondences. Measure D50 catalog resource rejections separately from association and edge quality.

### 2026-11-19 - Phase 6 - Planned real-observation reliability and Windows acceptance

- **Changed** Raised the architecture to revision 3.11 and defined [6A–6E](docs/phase-6.md) for reference preparation, terrain diagnostics, masked solving, ZEA preview and native Windows verification. Specified real observational data for every test in the phase.
- **Verified** Reviewed planned datasets and gates against PA4, the real archive and wide-field references, and the Windows release procedure. Reviewed Markdown content and links for this planning change.
- **Related** Q-003, Q-005, Q-010, Q-016, Q-022 and Q-023.
- **Next** Freeze the PA4 and archive references, select the independent positive and negative mixed captures, and record the baseline before tuning.

### 2026-11-19 - Mixed panels - Traced the current processing path

- **Reviewed** Followed the desktop import, mask editing, sky solving, ground alignment, placement, and shared rendering entry points in source.
- **Verified** The import job proposes a foreground tag. Defined mask labels select the sky and ground samples. Ground alignment estimates translations, and composition placement fits a similarity transform between the two layers.
- **Related** [Mask workflow](docs/phase-3d.md#desktop-workflow), [layer workflow](docs/phase-3e.md#desktop-workflow), and Q-010.
- **Next** Use the traced foreground and sky paths when freezing real-observation references in [Phase 6A](docs/phase-6.md#6a-freeze-the-real-data-baseline).

### 2026-11-19 - Phase 7 - Researched and planned terrain panorama registration

- **Changed** Added [Phase 7A–7F](docs/phase-7.md) in revision 3.12. Planned manual terrain points first, bounded automatic matching, measured camera-model selection, and shared rendering and Windows acceptance on real captures.
- **Verified** Compared PTGui and Hugin documentation and the original panorama literature with the PA4 measurements, translation matcher, persistence and composition paths. Reviewed the phase gates and documentation links.
- **Related** Q-003, Q-005, Q-010 and [proposed ADR-0023](docs/adr/0023-terrain-control-point-registration.md).
- **Next** Prepare the Phase 6A–6B real terrain references, annotate verified overlaps, and compare the candidate models using the Phase 7A split.

### 2026-11-19 - Phases 6 and 7 - Clarified foreground responsibilities and handoff

- **Changed** Assigned the current translation baseline and PA4 diagnostics to 6A–6B. Assigned expanded control points, holdout preparation and model comparison to 7A. Documented the handoff records and the Windows build covered by each acceptance run.
- **Verified** Reviewed the updated phase scope, acceptance gates and links against the existing translation matcher, mixed export workflow and Windows release procedure.
- **Related** Q-003 and Q-010. [Handoff to Phase 7A](docs/phase-6.md#handoff-to-phase-7a)
- **Next** Freeze the real translation and rejection controls and record the 6B pair evidence before the 7A model comparison.

### 2026-11-19 - Phase 6A - Recorded the first real-observation baseline

- **Changed** Added individual case selection to the application checker. Recorded the input and catalog hashes, projects, mask versions, exports, commands and diagnostics in `output/application-tests/phase6a-20261119-155643-651/`.
- **Verified** Independently reopened four sky exports and one foreground export. The eight PA4 horizon replays matched earlier outcomes. Five real solve controls met their quality limits. All 23 PA4 source hashes matched, and all 15 foreground comparisons reproduced their correlation rejections. Rebuilding the ESO control reproduced its reference manifest byte for byte. Ruff and the new documentation links passed.
- **Related** The real ESO ALPACA pair recovered (+48, +16) source px against the landmark reference (+47.98, +16.23) px. The disjoint control returned two singleton groups. Q-003, Q-010, Q-016 and Q-023. [Phase 6A measurements](docs/phase-6.md#local-baseline-measurements)
- **Next** Complete the mixed control's sky geometry and use the saved pair results for 6B. The ALPACA sky probe produced insufficient catalog matches, so its composition remains pending.

### 2026-11-19 - Phase 6A - Verified the independent mixed reference

- **Changed** Calibrated the two real ALPACA crops against Gaia DR3 and saved source- and mask-bound sidecars and a visual composition placement.
- **Verified** Held-out P95 was 0.363 and 0.410 source px. The independently reopened sky, foreground and composition FITS files passed the coverage, sample and contribution checks. The reference files and calibration evidence are in `output/application-tests/phase6b-work/`.
- **Related** Q-003 and Q-010. [Mixed reference](docs/phase-6.md#calibrated-alpaca-mixed-reference)
- **Next** Use the mixed project for the foreground diagnostics replay and later native Windows acceptance.

### 2026-11-19 - Phase 6B - Verified foreground alignment diagnostics

- **Changed** Added pairwise support, correlation and refinement outcomes to the shared alignment operation. The desktop details dialog lists the pairs and groups and opens either selected mask.
- **Verified** All 15 PA4 scores matched the original baseline. The reduced-mask variant saved and reopened and still gave six isolated groups. The ALPACA positive, negative, support and cancellation/retry checks passed. Native CPU and OpenGL mixed previews and exports, four focused real-data regressions, Ruff and mypy passed.
- **Related** Q-003 and Q-010. [6B results](docs/phase-6.md#local-foreground-diagnostics-results)
- **Next** Instrument the PA4 horizon solves in 6C and use the recorded terrain results to prepare the 7A landmark review.

### 2026-11-19 - Phase 6C - Measured catalog limits in the real horizon row

- **Changed** Added attempt gates, effective hints and regional ASTAP read diagnostics to the source CLI and desktop details. Verified the installed CLI and complete D05 and D20 catalogs.
- **Verified** Replayed the original three D50 failures from captured native candidates. Smaller detection-bearing cones still hit 100,000 retained stars. Identified the existing bright-subset selection and validated bounded early filtering against the full D05 reference.
- **Related** Q-016 and [Phase 6C measurements](docs/phase-6.md#local-masked-solve-results). The regional records and commands are in `output/application-tests/phase6c/`.
- **Next** Verify the bounded reader across all eight PA4 horizon frames and the real solve controls.

### 2026-11-19 - Phase 6C - Verified bounded validation and protected PA4 admission

- **Changed** Adopted bright-first filtering in wide ASTAP validation. The three previously resource-limited candidates reached association at 17.69–23.92 MiB per candidate.
- **Verified** All eight horizon frames retained explicit rejection reasons. The six real solve controls passed and the D50 Orion sidecar drove an independently verified FITS export. The real desktop rejection details, mask identity, source hashes, cancellation, late publication and retry checks passed. Fifteen targeted real-data tests, Ruff, mypy and local documentation links passed.
- **Related** Q-016 and [Phase 6C measurements](docs/phase-6.md#local-masked-solve-results). The ready PA4 sky mosaic retains 15 qualified panels.
- **Next** Capture the exact real PA4 ZEA warning for 6D.

### 2026-11-19 - Phase 6D - Isolated the PA4 inverse warning

- **Changed** Screened the core projection before the shared iterative inverse. The reduced replay uses PA4-10 and the first 128 × 128 tile of the recorded ZEA grid.
- **Verified** All 16,384 directions are finite in ZEA and outside PA4-10's TAN hemisphere. The baseline hit Astropy's all-NaN reduction. The corrected real tile, mixed batches, near-rim sample and singular WCS checks passed.
- **Related** Q-023 and [6D acceptance](docs/phase-6.md#6d-reproduce-the-zea-warning-and-measure-preview-cost).
- **Next** Compare conservative ZEA panel selection with all-panel renders and finish the native timing runs.

### 2026-11-19 - Phase 6D - Verified ZEA output and adopted conservative panel selection

- **Changed** Added conservative ZEA candidate bounds for ordinary ICRS TAN and TAN-SIP sources. Documented the bound and the full traversal fallback in [ADR-0024](docs/adr/0024-conservative-zea-footprints.md).
- **Verified** The full PA4 export matched the guarded all-panel and 6A TIFF references for samples, 3,238,763 covered pixels and WCS. Profiled export time fell from 83.91 to 38.25 s. The 24 native CPU and OpenGL previews matched at both resolutions. Independent cropped, rim, FITS and XISF checks, ALPACA layer parity, PA4 hashes, 15 real-data regressions, Ruff and mypy passed.
- **Related** Resolved Q-023. [6D evidence](docs/phase-6.md#local-zea-geometry-and-performance-results) records the cold and warm timings, inverse work, TIFF reads, candidate counts and reservations.
- **Next** Investigate native close, reopen and cancellation in 6E, then check the intended portable build on a clean Windows 11 x64 environment.

### 2026-11-19 - Phase 6E - Reproduced both Windows lifecycle failures

- **Changed** Added a real-data native replay with Qt messages and window and worker lifecycle events. Release OpenGL preview resources before closing an accepted project window.
- **Verified** Replacing a window while its real export was still cancelling reproduced `0xc0000409` on CPU and OpenGL. Qt reported a running `QThread` being destroyed. The orderly close waited for cancellation and removed the temporary export. The initial orderly OpenGL run exposed a separate texture destructor running during a later worker's Python garbage collection.
- **Related** Q-022 and [6E requirements](docs/phase-6.md#6e-verify-native-lifecycle-and-windows-packages). Initial traces are in `output/application-tests/phase6e/`.
- **Next** Rerun the native transitions with the OpenGL cleanup and verify packages built from the updated source.

### 2026-11-19 - Phase 6E - Verified the local Windows candidate

- **Changed** Built and inventoried the desktop and CLI packages from the same source snapshot. Recorded their ZIP and executable hashes and resolved Q-022.
- **Verified** Eight normal native lifecycle sequences passed with clean cancellation and same-name retry. The nine real products matched on all six source and portable entry points. The regular packaged launcher exported the M17 TIFF and exited normally. CLI solve admission, desktop M13 and PA4-07 checks, the frozen input hashes, 20 real-observation tests, Ruff and mypy passed.
- **Related** [6E evidence](docs/phase-6.md#local-windows-lifecycle-and-package-results), Q-022 and Q-005. Candidate files are in `.tooling/phase6e-20261119/artifacts/`.
- **Next** Record fresh Windows 11 x64 acceptance for the exact candidate and finish the redistribution review. The development host has Windows Sandbox and Hyper-V disabled.

### 2026-11-19 - Phase 6 - Prepared the source checkpoint

- **Changed** Collected the Phase 6 implementation, real-observation tests and updated architecture and test guides for `main`.
- **Verified** Matched all changed Python files to the verified 6E snapshot. Ruff, mypy and the repository link checks passed.
- **Related** [6E evidence](docs/phase-6.md#local-windows-lifecycle-and-package-results) and Q-005.
- **Next** Run fresh Windows acceptance for the recorded 6E archives.

### 2026-11-19 - Documentation - Recorded version control and release rules

- **Changed** Added the Git workflow, application and schema version rules, beta tags, and release verification to [AGENTS.md](AGENTS.md#10-version-control-and-releases).
- **Verified** Reviewed the rules against the current package version and release procedure. Checked all links in `AGENTS.md` and ran `git diff --check` for the documentation edits.
- **Related** [Release procedure](docs/windows-release.md#record-a-release) and Q-005.
- **Next** Apply the rules when preparing the next release.

### 2026-11-19 - Phase 6 - Advanced the development beta

- **Changed** Set the application version to `0.1.0b2` and recorded the version of the earlier Phase 6E build.
- **Verified** `poetry check --lock`, the wheel metadata, CLI version, and desktop title passed. The real M17 project validated and reopened after saving with the new application version.
- **Related** [Version control and releases](AGENTS.md#10-version-control-and-releases) and [Phase 6E evidence](docs/phase-6.md#local-windows-lifecycle-and-package-results).
- **Next** Build matching `0.1.0b2` Windows packages and complete the fresh-installation checks for that build.

### 2026-11-20 - Phase 7A - Measured the first PA4 terrain overlap

- **Changed** Reviewed 15 PA4 pair outcomes against both saved mask variants. Measured corresponding branches on 04–05 and compared translation and similarity on the same held-out landmarks. Extended the ALPACA translation reference and inventoried three real PASSTA panning captures.
- **Verified** Six PA4 source hashes and both sets of mask labels matched the Phase 6 inventory. PA4 held-out forward P95 fell from 306.08 to 72.11 px on visible terrain. Only two of ten quality-checked landmarks had joint ground support in the original masks. ALPACA translation reached 1.43 px held-out P95. Four foreground regressions passed, both local reports replayed byte-for-byte, and the PASSTA archive passed ZIP integrity and three image opens.
- **Related** Q-003 and Q-010. The [7A measurements](docs/phase-7.md#initial-7a-measurements) describe the open pair diagnoses and replay procedure.
- **Next** Independently re-mark the plausible overlaps and review the ground masks. Resolve the PASSTA calibration orientation and qualify the independent nightscape and depth-change cases.

### 2026-11-20 - Phase 7A - Froze the real reference set

- **Changed** Measured PA4-02/03 and 05/06 and reverse-refined the 04/05 points. Added Oxford Boat, La Silla, PASSTA and Adirondack controls with recorded source identity and fit/held-out assignments.
- **Verified** Boat similarity reached 1.02/1.16 px forward/reverse held-out P95 and La Silla translation reached 0.94 px in both directions. PASSTA's clockwise sensor orientation won on all three edges and the pairwise rotation loop closed to 0.0041°. Adirondack had about 122 px difference between near and far shifts. The six follow-up reports replayed byte-for-byte and four foreground tests passed.
- **Related** Q-003 and Q-010. [Frozen 7A references](docs/phase-7.md#frozen-7a-references)
- **Next** Implement and verify 7B with the fixed ALPACA and Oxford point cases. Keep PA4 ground-mask and depth hypotheses for terrain review and further model validation.

### 2026-11-20 - Phase 7B - Verified the headless manual terrain fit

- **Changed** Added the Qt-free manual control-point fit and `project fit-foreground`. It reports validation, anchored translation or similarity, per-point errors and rejected links. Project geometry persistence remains scheduled for 7E.
- **Verified** ALPACA, the two- and three-view Oxford cases, and La Silla passed the held-out limit. Adirondack, an inconsistent real-data cycle and underconstrained inputs returned rejection diagnostics. Cancellation and retry preserved the previous saved alignment. The full suite passed 199 tests with two opt-in OpenGL skips. The final focused replay passed 26 tests with the same skips. Five CLI control replays, Ruff and mypy passed.
- **Related** Q-003, Q-010 and ADR-0023. [7B command and results](docs/phase-7.md#run-a-manual-terrain-fit)
- **Next** Start the 7C bounded feature matching comparison with the 7B point sets and preserve the public negative controls.

### 2026-11-21 - Phase 7C - Evaluated bounded automatic terrain matching

- **Changed** Added optional SIFT point proposals and independent audits to the read-only foreground CLI. Added full-support thumbnails, mutual feature checks, source-patch refinement and spatial inlier requirements to the shared anchored fit.
- **Verified** The audited three-view Oxford graph reached 0.97 px maximum edge P95 and La Silla reached 0.98 px. The disconnected ALPACA group and Adirondack produced zero false links. Manual points recovered sparse ALPACA mask support at 1.43 px. The automatic ALPACA translation missed its frozen tolerance. Both PA4 mask variants and PASSTA remained disconnected. The full suite passed 204 tests with two opt-in OpenGL skips. Seven manual and missing-backend checks passed separately without OpenCV on the Python path. Ruff, mypy and the documentation link checks passed.
- **Related** Q-003, Q-005, Q-010 and [7C results](docs/phase-7.md#7c-real-observation-results). Ten Qt-free CLI reports repeated byte-for-byte with matching project hashes. Oxford and PA4 reservations peaked at 63.4 and 112.1 MiB respectively.
- **Next** Carry the frozen PASSTA calibration and landmarks into 7D. Review the local wheel inventory before any portable adoption.

### 2026-11-21 - Phase 7D - Evaluated rotation and retained translation and similarity

- **Changed** Added an offline replay for anchored rotation, one shared focal adjustment, one shared radial adjustment and the planar baselines. The replay uses the frozen observations and verifies calibration, crops, pixel scale, inverse maps and boundary samples.
- **Verified** PASSTA's independent loop closed to 0.0041°. The worst held-out P95 was 6.90 px with fixed calibration and 4.13 px with the best radial candidate. Adirondack rejected both a global pose and the far subset. The PA4 metadata estimate reached 8.34 and 3.07 px on visible terrain and kept the masked links unsupported. The report replayed byte-for-byte and the NumPy geometry agreed with the separate OpenCV probe. The full suite passed 205 tests with two opt-in OpenGL skips. Seven focused tests passed without OpenCV on the Python path. Ruff, mypy and the documentation link checks passed.
- **Related** ADR-0023, Q-003, Q-010 and [7D measurements](docs/phase-7.md#7d-real-observation-results).
- **Next** Integrate the verified translation and similarity models in 7E and check legacy saved translations, tile sampling, and scientific sky independence.

### 2026-11-21 - Desktop Plate Solve - Start directly in untitled projects

- **Changed** Removed the sidecar folder prompt from Plate Solve and Revalidate Plate Solution. Untitled projects use the local application data directory. Saved projects use their sibling WCS directory.
- **Verified** Five native Windows desktop tests passed. An untitled real M13 panel solved from the Plate Solve button with ASTAP D05 and zero folder requests. The saved project reopened with the generated sidecar and its input hash was preserved. The new 0.1.0b2 desktop executable started and closed cleanly.
- **Related** [Desktop plate solving](docs/phase-3b.md#desktop-plate-solving).
- **Next** Verify the packaged Phase 7 CLI and inventory the local development bundles.

### 2026-11-21 - Windows - Built local 0.1.0b2 with the Phase 7 CLI

- **Changed** Built the desktop and CLI from a hashed working-tree snapshot and the Poetry lock. Built a separate optional SIFT CLI with the measured OpenCV wheel. Archived the complete bundles with their notices and SHA-256 hashes.
- **Verified** The desktop reported 0.1.0b2, contained the corrected Plate Solve handler, and exited cleanly. Both CLIs reported 0.1.0b2. The standard CLI fit Oxford's three-view manual control at 1.10 px P95. The SIFT CLI reached 0.97 px on Oxford and 0.98 px on La Silla and rejected the disconnected ALPACA, Adirondack and PA4 controls. The suite passed 205 tests with two opt-in OpenGL skips. Ruff, mypy and documentation link checks passed.
- **Related** [Local release verification](docs/windows-release.md#verification-status), Q-005 and [Phase 7 commands](docs/phase-7.md#run-the-automatic-terrain-fit). Local replay reports are stored in `output/application-tests/plate-solve-phase7-20261121/`.
- **Next** Integrate Phase 7 geometry into rendering and project persistence. Use the local bundles for development, and verify an exact tagged build on a fresh Windows host before public distribution.

### 2026-11-21 - Phase 7 - Reviewed readiness for 7E

- Reviewed the working tree against the 7A–7F gates. The headless fit reports candidate poses. The foreground tile sampler and its footprint calculation still use saved panel shifts.
- Reran the 12 focused real-observation regressions for control points, automatic matching and the camera-model comparison. All 12 passed with the isolated OpenCV provider. In the standard environment, eight passed and the four provider-dependent checks skipped.
- Start 7E by saving and reopening Oxford's three-panel similarity fit and checking rendered samples and coverage. Keep ALPACA as the saved-translation control and verify sky-only samples, coverage and WCS for a mixed scene. [7E criteria](docs/phase-7.md#7e-integrate-geometry-rendering-and-persistence)

### 2026-11-21 - Desktop command panel - Opened at startup and recorded operation summaries

- **Changed** Opened the Command Panel at startup at its minimum dock height. Added project, panel and settings summaries and desktop job outcomes to the bounded session log, including while hidden.
- **Verified** All 207 tests passed on native Windows with OpenGL and the optional SIFT provider. Six focused desktop tests passed on native Windows and with Qt offscreen. Ruff, mypy, the Poetry lock check and the documentation link review passed.
- **Related** Q-012 and the [command panel workflow](docs/phase-4c.md#desktop-workflow).
- **Next** Include the updated command panel checks in the next Windows package verification.

### 2026-11-21 - Desktop sky preview - Recovered the two-panel TIFF project

- **Changed** Added desktop and Command Panel guidance for missing sky metadata and empty sky previews. Prepared a separate project with relative linear sRGB copies, the verified WCS and a TAN grid that encloses both panels.
- **Verified** The original project reproduced the missing filter and brightness diagnostics. The old grid covered one panel. The reopened preview covered 120,324 samples, including 25,786 shared by both panels. Native Windows CPU and OpenGL previewed it on the second display. Both CLIs validated the project, all 28 focused tests passed, and Ruff and mypy passed. The original project, images and sidecar hashes matched.
- **Related** Q-024 and [sky preview setup](docs/phase-3c.md#desktop-workflow).
- **Next** Carry the diagnostic checks into the next desktop package verification.

### 2026-11-21 - Source integration - Verified terrain and desktop changes for main

- **Changed** Prepared the Phase 7 terrain work, desktop solving, command panel, sky preview diagnostics and their records as separate source commits for `main`.
- **Verified** All 207 tests passed on native Windows with OpenGL and the isolated SIFT provider. The desktop checks used the second display. The standard environment passed seven terrain checks with four optional provider checks skipped. Ruff, mypy, the Poetry lock check and local documentation link checks passed.
- **Related** Q-003, Q-010, Q-012 and Q-024.
- **Next** Use the verified translation and similarity controls for Phase 7E. Include the desktop diagnostic checks in the next Windows package verification.

### 2026-11-21 - Windows build - Assigned beta 3 to the merged desktop fixes

- **Changed** Set the development version to `0.1.0b3` for a new local Windows build from the merged source.
- **Verified** The older `0.1.0b2` executable matches its archived launcher. Its source snapshot precedes the Command Panel startup and sky preview diagnostic changes.
- **Related** Q-012, Q-024 and the [Windows build workflow](docs/windows-release.md#build-portable-windows-packages).
- **Next** Build from this source revision and verify the title, Command Panel and Build Preview in the resulting Windows package.

### 2026-11-21 - Windows build - Verified the beta 3 desktop package

- **Changed** Built the desktop and standard CLI from clean commit `900dba19dc7de1c326c8c17878e812d64085a963` using the Poetry lock. Placed the desktop runtime and provenance in a versioned local folder.
- **Verified** The production EXE title and bundled CLI both reported `0.1.0b3`. On the second display, CPU and OpenGL reopened the copied package runtime, verified the default Command Panel and hidden history, reproduced both missing metadata diagnostics and built the recovered two-panel preview with 120,324 covered samples. The test used the same embedded desktop and preview modules as the launcher. The original project, images and sidecar hashes matched.
- **Related** Q-024, Q-025 and [Windows build verification](docs/windows-release.md#verification-status).
- **Next** Use this local beta for the combined desktop fixes. Record fresh Windows acceptance for a future tagged package.

### 2026-11-21 - Development workflow - Recorded Windows build handoff rules

- **Changed** Added instructions to `AGENTS.md` for delivering versioned Windows builds, recording their source commit and verifying the changed workflow in the packaged runtime.
- **Verified** Reviewed the rules against the release procedure and beta 3 evidence. Checked the document links and diff.
- **Related** Q-025 and [Local Windows Build Handoff](AGENTS.md#local-windows-build-handoff).
- **Next** Apply the handoff checks to the next Windows executable delivery.

### 2026-11-21 - Sky preview - Defaulted unlabeled panels to Unspecified

- **Changed** Shared the `Unspecified` fallback between desktop band selection, CLI project discovery and sky rendering. Assigned version `0.1.0b4` for the Windows handoff.
- **Verified** Fifteen focused tests passed. The saved two-panel project lists both panels in `Unspecified` and reaches brightness validation. Explicit labels still form their own groups. Ruff, mypy and the Poetry lock check passed.
- **Related** Q-024 and [sky band selection](docs/phase-5c.md).
- **Next** Verify the automatic label and a successful two-panel preview in the beta 4 desktop package.

### 2026-11-21 - Windows build - Verified the default sky band in beta 4

- **Changed** Built beta 4 from clean source commit `6ca71f54f89c7474ffe8376ddb18fa70f65d7aa5` with the Poetry lock. Saved the desktop runtime and build record in a versioned local folder.
- **Verified** All 208 tests passed on native Windows with OpenGL and the isolated SIFT provider. The packaged CLI listed both original panels in `Unspecified`. The production EXE reported beta 4. Native CPU and OpenGL on the second display previewed the unlabeled real linear TIFF copies with 120,324 covered samples. Source TIFF and project hashes matched, and the original display TIFFs reached brightness validation.
- **Related** Q-024, Q-025 and [Windows build verification](docs/windows-release.md#verification-status).
- **Next** Use beta 4 for the automatic band workflow and retain the real TIFF check for subsequent Windows packaging.

### 2026-11-21 - Plate Solve - Show activity while solving a panel

- **Changed** Enabled a busy progress bar during eligibility checks and solving. The status names the active panel in the batch and advances at every panel boundary. Assigned version `0.1.0b5` for the Windows handoff.
- **Verified** The new assertion reproduced the earlier bar staying at 0%. After the fix, 19 targeted tests passed, including cancellation with partial outcomes and a retry. Ruff, mypy and the Poetry lock check passed.
- **Related** Q-026 and [desktop plate solving](docs/phase-3b.md#desktop-plate-solving).
- **Next** Verify the animation during a real solve in the portable Windows runtime.

### 2026-11-21 - Windows build - Verified plate solve progress in beta 5

- **Changed** Built the beta from clean source commit `1c787b56176ccd9bf58befe1bb397f189301a825` with the Poetry lock. Saved the desktop and its build record in the versioned local folder.
- **Verified** All 208 source tests passed across offscreen and native OpenGL runs. The desktop title and bundled CLI reported `0.1.0b5`. On the second display, the packaged runtime animated through a single M13 DSS solve, a batch, cancellation and retry, and revalidation with either preview backend active. ASTAP D05 solved the real panels. Cancellation retained the completed WCS. The observational fixture and its staged copies kept their hashes.
- **Related** Q-026 and [Windows build verification](docs/windows-release.md#verification-status).
- **Next** Retain the active-panel and cancellation checks for subsequent desktop builds.

### 2026-11-21 - Phase 4 follow-up - Add dialog-free project operations

- **Changed** Audited file dialogs and the saved-project CLI boundary. Added Command Panel `session` commands for the live project and headless preparation for moved sources, plate solving, labeled masks, foreground alignment and composition placement. Assigned version `0.1.0b6` for the Windows handoff.
- **Verified** Source regressions exercised first save, occupied filenames, unsaved changes, export from the active project, relink and close without a dialog. CLI regressions covered reopen, WCS reuse, successful publication, failure and cancellation cleanup, label import and composition export.
- **Related** Q-027, [headless preparation](docs/phase-4a.md#prepare-a-project-without-the-desktop) and [live desktop commands](docs/phase-4c.md#control-the-active-project-without-dialogs).
- **Next** Run the complete source suite and verify the new CLI and session workflows in portable Windows builds.

### 2026-11-21 - Windows build - Verified beta 6 project automation

- **Changed** Built both launchers from clean source commit `a4ad3825adbf816c8a70246ecb24740998938d63` with the Poetry lock. Saved each runtime with its version and launcher checksum.
- **Verified** All 215 source tests passed across offscreen and native OpenGL. Ruff, mypy and the Poetry lock check passed. The second-display desktop run used real M13 data for first save, overwrite refusal, solve, preview, export from unsaved state, relink and close with zero dialogs. The Qt-free CLI recovered from a solve deadline and reopened an M13 FITS with 16,384 covered samples. It imported the two real Paranal editor-grid masks, aligned the foreground, checked both placement paths and reopened the composition TIFF with 1,434,510 covered samples. The original files and manifests kept their hashes.
- **Related** Q-027 and [Windows build verification](docs/windows-release.md#verification-status).
- **Next** Retain the dialog and atomic publication regressions. Continue the planned terrain pose persistence and rendering in [Phase 7E](docs/phase-7.md#7e-integrate-geometry-rendering-and-persistence).

### 2026-11-21 - Sky preview - Recovered a saved sRGB project

- **Changed** Prepared a separate visual preview project for the most recently saved copy of the two-panel TIFF project. It references the existing float32 linear-light conversions and uses a sky grid that covers both fields.
- **Verified** Reproduced the brightness-unit failure with the beta 6 CLI. Both original TIFFs have sRGB profiles and no `BUNIT`. The current WCS sidecars and the linear copies agree on a 33 × 33 sample grid per panel. The beta 6 CLI accepted the new project, and the native second-display OpenGL preview covered 120,324 samples, including 25,786 shared by the two panels. The inputs, current manifest and attached WCS files kept their hashes.
- **Related** Q-024 and [desktop sky preview](docs/phase-3c.md#desktop-workflow).
- **Next** Use the prepared project for the relative visual preview.

### 2026-11-21 - Documentation - Map the current application workflows

- **Changed** Added a [workflow reference](docs/workflows.md) for desktop, CLI and batch use, including the panel, solver, layer, preview, export and recovery branches. Linked it from the guide.
- **Verified** Parsed nine Mermaid flowcharts, checked 64 relative file and section links, and compared the documented commands and desktop controls with the beta 6 source.
- **Related** Q-024, Q-026 and Q-027.
- **Next** Update the reference when the implemented workflows change.

### 2026-11-21 - Sky preview - Implemented automatic framing and sRGB preview

- **Changed** Added WCS framing, a visual sRGB sky preview and explicit export grid adoption to the desktop and session commands.
- **Verified** The initial focused source suite passed 21 tests. The original TIFFs with their existing solved WCS covered 109,331 preview samples, including 23,020 shared samples. Science preflight rejected the encoded inputs even with a common-scale declaration.
- **Related** Q-028 and [ADR-0025](docs/adr/0025-automatic-sky-preview.md).
- **Next** Run the fresh solve workflow and verify the locked beta 7 Windows package.

### 2026-11-21 - Sky preview - Rechecked the PA4 ZEA case

- **Changed** The PA4 crop regression exercises the visual preview with the original sRGB TIFFs and checks that scientific export rejects them.
- **Verified** All four real PA4 ZEA tests passed. The 384 × 384 preview retains 4,869 covered samples. Pruned and all-panel sampling agree byte for byte, with identical coverage and WCS.
- **Related** Q-028 and [Phase 6D results](docs/phase-6.md#local-zea-geometry-and-performance-results).
- **Next** Finish the complete source and packaged preview checks.

### 2026-11-21 - Windows build - Verified beta 7 sky previews

- **Changed** Built the desktop and CLI from clean source commit `023595ec62f4d634da64ebb7f37e0f0744a0021d` using the locked dependencies. Recorded both launcher hashes and the build time in their versioned directories.
- **Verified** Source OpenGL and packaged CPU and OpenGL each solved the original TIFFs and previewed both panels in an untitled project. The packaged runs matched 109,331 valid samples and 23,020 shared samples on the second display. Both launchers report beta 7. Source checks passed 217 offscreen tests and two native OpenGL tests. Ruff, mypy and the Poetry lock check passed.
- **Related** Resolved Q-028. [Windows build record](docs/windows-release.md#verification-status) · [Preview workflow](docs/phase-3c.md#desktop-workflow).
- **Next** Retain the preview and export boundary regressions. The planned terrain work continues in Phase 7E, with clean-machine and public distribution checks tracked separately.

### 2026-11-21 - Phase 8 - Proposed configurable color photometry and optics

- **Changed** Added a method catalog and staged acceptance for photo export, profile conversion, exposure and brightness matching, lens geometry and vignetting. Linked the proposal from the active architecture.
- **Verified** Reviewed the proposed methods against the current beta 7 processing contract, published PTGui behavior, Mosaic Master source and the ICC and lens references. Checked the outline and document links.
- **Related** Q-029 and [proposed ADR-0026](docs/adr/0026-configurable-color-photometry-and-optics.md).
- **Next** Freeze the 8A contracts and reference data when the owner schedules Phase 8. Use the two original sRGB TIFFs for the 8B photo export acceptance.

### 2026-11-21 - Phase 7E - Integrated saved terrain poses and tile rendering

- **Changed** Added an output option to the terrain-fit command and integrated accepted translations and similarities with the shared foreground renderer, horizon placement and version 7 manifests. Assigned version `0.1.0b8` for the Windows handoff.
- **Verified** The nine real control-point checks passed. The independent Oxford Boat bilinear comparison, unpruned render, legacy ALPACA coverage, invalidation and cancellation, and Paranal sky parity and composition passed. The focused project and layer checks and scoped mypy checks passed.
- **Related** Q-003, Q-010 and [7E source results](docs/phase-7.md#7e-source-results).
- **Next** Build the locked beta and repeat the saved alignment workflow with the Windows launchers.

### 2026-11-21 - Windows build - Verified beta 8 terrain geometry

- **Changed** Built both launchers from clean commit `3ab8e3eb8f899da31722316ec06002d0e74a4c0f` using the Poetry lock. Recorded the build time and launcher hashes in the versioned directories.
- **Verified** The console saved and exported Oxford and ALPACA, rejected the Adirondack fit, and reopened the Paranal composition with sky bytes preserved. The bundled desktop on the secondary display matched the Oxford console export with both CPU and OpenGL. Source passed 220 offscreen and two native tests. The isolated SIFT save, Ruff, scoped mypy and Poetry lock checks passed. Full-tree mypy still reports an existing missing return annotation in the real ZEA regression.
- **Related** Q-003, Q-005, Q-010 and [beta 8 package results](docs/phase-7.md#7e-local-windows-package-results).
- **Next** Add the 7F desktop point-review workflow and run the remaining clean-machine checks on its candidate.

### 2026-11-21 - Phase 7F - Implemented desktop terrain point review

- **Changed** Added masked panel comparisons, original-pixel detail, point editing and fit diagnostics to the Align Foreground submenu. Accepted fits are applied separately from the draft. Manifest version 8 preserves disabled points. Assigned version `0.1.0b9` for the local Windows handoff.
- **Verified** Nine native tests passed with the second display and OpenGL, including the six editor regressions. Oxford passed manual edits and retry. ALPACA and La Silla passed the fit gates. Adirondack and PA4 remained disconnected. Paranal composition and sky parity passed. Ruff, scoped mypy and the lock check passed.
- **Related** Q-003, Q-010 and [desktop point review](docs/phase-7.md#review-and-edit-control-points-in-the-desktop).
- **Next** Build the locked beta and repeat the desktop lifecycle, exports and frozen CLI controls in the copied Windows runtimes.

### 2026-11-21 - Windows build - Verified beta 9 terrain review locally

- **Changed** Built both launchers from clean commit `ba8d217ed22688f6f4c48296cc040a6bc18d5eda` using the Poetry lock. Recorded build time, launcher hashes and real-data results in the versioned directories.
- **Verified** The copied native CPU and OpenGL runtimes on the second display passed point review, save and reopen, cancellation, close during render and retry. Oxford produced 588,078 covered foreground samples at 1.23 px held-out P95. Paranal sky and composition matched the console, ALPACA legacy export retained 80,158 samples, and the La Silla, Adirondack and six-panel PA4 outcomes matched the source checks. The full offscreen and opt-in native suites passed.
- **Related** Q-003, Q-005, Q-010 and [7F local results](docs/phase-7.md#7f-local-windows-results).
- **Next** Run the shared 6E and 7F matrix on a fresh Windows installation. No separate Windows test environment was available on the development host.

### 2026-11-21 - Documentation - Completed: expanded README with structured project details

- **Changed:** Expanded `README.md` while preserving existing header, support, license, and quick-start links. Added structured sections covering processing highlights, pipeline design, codebase layout, astronomical data/solvers, dependency specs, developer setup, and binary packaging using alternative terminology and an organized sequence.
- **Verified:** Validated markdown formatting and confirmed all relative documentation, decision record, license, and phase links resolve to existing paths. Application tests were not required for this documentation-only edit.
- **Related:** None.
- **Next:** Proceed with the scheduled Phase 8 scoping or clean-machine acceptance validation when requested.

### 2026-11-21 - Plate Solve - Show stage progress and a larger job bar

- **Changed** Added progress at WCS eligibility, solver preparation, search, validation and sidecar publication. The desktop shows a wide bar, numeric percentage, active panel and backend, and elapsed time. Assigned version `0.1.0b10` for the local Windows handoff.
- **Verified** The 29 targeted source checks passed, including monotonic displayed progress, cancellation and retry, offline solve policy and budgets, rendering and the headless project workflow. Ruff, scoped mypy and the Poetry lock check passed.
- **Related** Q-026 and [desktop plate solving](docs/phase-3b.md#desktop-plate-solving).
- **Next** Verify real solves, the wider layout, and cancellation in the locked beta 10 Windows runtime.

### 2026-11-21 - Windows build - Verified beta 10 Plate Solve progress

- **Changed** Hid the Command Panel's idle progress indicator. Built both beta 10 launchers from clean source commit `ca0238003f8631ff1eb93ceb0e5def27c4ee2be4` using the Poetry lock.
- **Verified** Real M13 solves showed intermediate percentages and stable elapsed updates on the second display in the copied CPU and OpenGL runtimes. Both themes and the compact layout passed. Batch cancellation at 68% retained the first solution and retry completed the remaining panel. Standalone ASTAP solving and input preservation passed. Source passed 227 offscreen tests and the two opt-in native checks.
- **Related** Q-026 and [beta 10 progress results](docs/phase-3b.md#beta-10-progress-verification).
- **Next** Retain the real single, batch and cancellation checks for future Windows packaging.

### 2026-11-21 - Phase 8A - Froze the first photo export contract

- **Changed** Scheduled Phase 8 and fixed the accepted photo inputs, tone modes, TIFF layout, geometry, and science parity controls for 8B.
- **Verified** Both original TIFF hashes and their shared ICC fingerprint matched. Their saved Gaia solutions reproduced the 8917 × 10259 grid and 109,331 covered preview samples. Little CMS read the exact ICC registry profile and reported the expected colorants.
- **Related** Q-029 and [8A acceptance limits](docs/phase-8.md#8a-frozen-photo-export-contract).
- **Next** Add the shared photo export path and verify it against the real pair and independent sample references.

### 2026-11-21 - Phase 8B - Implemented full-resolution sky photo export

- **Changed** Added 16-bit sRGB TIFF export with binary coverage, the resolved sky WCS, two tone modes and profile provenance. The desktop and dialog-free commands use the shared tiled renderer. Assigned version `0.1.0b11` for the local handoff.
- **Verified** The initial 43 focused source checks and three native viewport and lifecycle checks passed. The full-size Preserve Tone product had 43,897,047 covered pixels. LibTIFF and an independent interpolation and transfer check measured a maximum error of one UInt16 code over 4,966 covered locations.
- **Related** Q-029 and [desktop and CLI workflow](docs/phase-8.md#8b-export-a-photo-mosaic).
- **Next** Complete the source suite and replay the original owner TIFF workflow and scientific parity checks in the locked Windows package.

### 2026-11-21 - Phase 8B - Checked full-size outputs and corrected compact layout

- **Changed** Moved the band selector to the preview header and show it for multi-band sky projects. The export and settings buttons keep their labels readable at the compact Windows width.
- **Verified** The first bundled CPU, OpenGL and CLI photo exports matched byte for byte. Independent sampling found at most one UInt16 code of error. The Windows compact-layout check passed with a multi-band project, and the two real panels confirmed the corrected single-band layout.
- **Related** [8B workflow](docs/phase-8.md#8b-export-a-photo-mosaic).
- **Next** Rebuild the corrected source and verify the final beta 11 launchers.

### 2026-11-21 - Windows build - Verified beta 11 photo export

- **Changed** Built both launchers from clean commit `e644768177da5013d9aa909621bc38a3d45756ce` using the Poetry lock. Recorded the build time and launcher hashes in the versioned folders.
- **Verified** Both copied native desktops solved the real pair on the second display, built the preview, cancelled and retried the photo export. Their final TIFFs matched the packaged CLI byte for byte and independently reopened. Nine real scientific products matched their reference pixels and masks. The complete source and opt-in native tests passed.
- **Related** Q-029 and [8B local Windows results](docs/phase-8.md#8b-local-windows-package-results).
- **Next** Prepare independent profile and exposure references for 8C. Keep fresh Windows acceptance and redistribution review open.

### 2026-11-22 - Phase 8B follow-up - Implemented adaptive framing and crop editing

- **Changed** Added framing locks, automatic mono fit settings, live sky refresh, masked area subsampling, visible detail and a draggable crop. Manifest version 9 stores adaptive settings when selected. Assigned version `0.1.0b12` for the local Windows handoff.
- **Verified** The focused numerical and native checks covered validity-weighted overview samples, exact detail, crop handles and OpenGL drawing. The existing scientific and project controls passed their focused runs.
- **Related** Q-030 and [ADR-0027](docs/adr/0027-adaptive-sky-preview.md).
- **Next** Verify the original TIFF pair, finish the source suite, and build and check the portable runtime from a clean commit.

### 2026-11-22 - Windows build - Verified beta 12 adaptive preview and crop

- **Changed** Built the versioned Windows launchers from clean commit `99491ad34bbd6cb6469c0f8f7d8bcdf35793baa8` using the lockfile.
- **Verified** The real pair passed native CPU and OpenGL overview, 1:1 detail, crop editing and cancellation on the secondary display. Both desktops and the copied CLI exported the same crop. Its WCS, coverage and preserved-tone codes matched the full reference region. All nine real scientific products matched their references.
- **Related** Q-030 and [beta 12 verification](docs/phase-8.md#8b-adaptive-preview-follow-up).
- **Next** Prepare the 8C profile and exposure references and retain clean-machine acceptance for the release candidate.

### 2026-11-22 - Documentation - Investigated Phase 8B photo export quality, opacity, and seams

- **Changed:** Authored `docs/phase-8-photo-mosaic-findings-and-recommendations.md` detailing the empirical root causes behind the three issues reported by the owner on `GHGH.tiff` (SubIFD coverage mask 1 vs 255 opacity bug in external viewers, severe contrast/color loss from default astronomical preview stretch on pre-processed sRGB files, and hard rectangular seam lines from lack of distance feathering/vignetting correction). Outlined immediate workarounds and an architectural roadmap for Stages 8.1–8.4.
- **Verified:** Validated quantitative metrics across `tests/20.TIF`, `tests/21.TIF`, and `tests/GHGH.tiff` (identifying the +380% background luminance surge under `Use Preview Tone` vs exact preservation under `Preserve Tone`, and the SubIFD binary 1 value causing 0.39% opacity in Photoshop). Verified documentation links and formatting.
- **Related:** Q-029, [ADR-0026](docs/adr/0026-configurable-color-photometry-and-optics.md), and [Investigation Report](docs/phase-8-photo-mosaic-findings-and-recommendations.md).
- **Next:** Implement Stage 8.1 fixes (SubIFD mask 255 opacity and Preserve Tone default) and prototype distance-transform feathering in the tile pipeline.

### 2026-11-22 - Phase 8B - Verified opaque TIFF opening in Photoshop

- **Changed** Recorded the owner's Photoshop verification and revised the photo export priorities in [Q-029](questions_open_topics.md#q-029---configurable-color-photometry-and-optics).
- **Verified** `GHGH.tiff` opened at 100% layer opacity with the RGB channels. The screenshot shows black outside the panel footprints and visible overlap boundaries. With identical WCS and coverage, sampled median code values were 33,410 DN for `Use Preview Tone` and 7,878 DN for `Preserve Tone`.
- **Related** The [8A photo contract](docs/phase-8.md#8a-frozen-photo-export-contract) defines the binary coverage SubIFD. The [initial investigation](docs/phase-8-photo-mosaic-findings-and-recommendations.md) records the opacity hypothesis.
- **Next** Qualify the photo tone default and measure the real overlap before evaluating distance feathering.

### 2026-11-22 - Phase 8B - Implemented preserved tone and transparent photo canvas

- **Changed** Made Preserve Tone the desktop and CLI photo default. Added 16-bit associated alpha derived from coverage and retained beta 11 and 12 photo reopening.
- **Verified** Passed 27 focused source checks, three native Windows checks and the Poetry lock check. Photoshop 27.7 opened a 16-bit RGBA probe and exported a PNG with transparent uncovered pixels and opaque covered black.
- **Related** [ADR-0028](docs/adr/0028-transparent-photo-tiff.md), Q-029 and the owner's full-resolution tone comparison.
- **Next** Verify the clean beta 13 packages with the original TIFFs.

### 2026-11-22 - Windows build - Verified beta 13 transparent photo export

- **Changed** Built and staged the two local Windows launchers from clean commit `7083c6f3b9947ff73c2fda67c7acd3364d10179a` using the Poetry lock. Recorded the build time and launcher hashes in the versioned folders.
- **Verified** The full owner photo matched all earlier Preserve Tone RGB codes and binary coverage through alpha. Photoshop 27.7 opened it with transparency. The copied CPU, OpenGL and console runtimes matched byte for byte on a real footprint crop. The nine scientific products matched their reference samples and masks. The source suite passed 235 checks and three native checks passed separately.
- **Related** [8B beta 13 photo results](docs/phase-8.md#8b-photo-tone-and-transparency-follow-up), [Windows launchers](docs/windows-release.md#verification-status) and Q-029.
- **Next** Establish stellar alignment and background residuals on the real overlap. Use those measurements to evaluate distance feathering.

### 2026-11-22 - Documentation - Reconciled the photo mosaic findings with beta 13

- **Changed** Updated the [investigation report](docs/phase-8-photo-mosaic-findings-and-recommendations.md) with the beta 12 and 13 comparison, current export workflow, and overlap recommendations aligned with the Phase 8 delivery stages.
- **Verified** Checked both TIFF headers, the recorded build and comparison values, and all 15 local links in the report.
- **Related** Q-029 and [ADR-0028](docs/adr/0028-transparent-photo-tiff.md).
- **Next** Measure stellar alignment and background residuals on the original pair before testing distance feathering.

### 2026-11-22 - Phase 8 - Measured the real photo overlap baseline

- **Changed** Added a source diagnostic for held-out stellar alignment, masked sky differences and panel-edge steps. The diagnostic compares the weighted mean with the existing Preserve Tone export.
- **Verified** On the original pair, the reference grid and sampled coverage matched and RGB agreed within one UInt16 code. The held-out P95 was 0.751 px with the saved WCS and 0.662 px with a trial translation. The 32 MiB replay matched the 64 MiB results. The source suite passed 236 checks with two native OpenGL skips. Ruff, scoped mypy, Poetry lock validation and Markdown link checks passed.
- **Related** [Owner overlap baseline](docs/phase-8.md#8b-owner-overlap-baseline) and Q-029.
- **Next** Check spatially distributed residuals against an independent alignment control and prepare the 8C photometry controls.

### 2026-11-22 - Phase 8 - Compared regional stellar alignment on real controls

- **Changed** Added whole-region holdout diagnostics to the overlap tool. The project-only mode reuses a saved sky grid to test geometry without requiring a photo export.
- **Verified** The saved WCS, translation and similarity gave 0.692, 0.713 and 0.757 px P95 on the owner pair. The same-camera PA4 control reached 0.919 px with similarity. The independent ALPACA control gave 0.179 px with the saved WCS, and an independent calculation reproduced its fold results. The owner TIFF retained its sampled coverage and one-code RGB agreement. The project-only replay reproduced the block counts and P95 values. The source suite passed 237 checks with two offscreen OpenGL skips. Ruff, scoped mypy, Poetry lock validation and Markdown links passed.
- **Related** [Spatial holdout and alignment controls](docs/phase-8.md#8b-spatial-holdout-and-alignment-controls) and Q-029.
- **Next** Evaluate candidate WCS against independent catalog stars across both detectors and retain the whole-region comparison before testing a seam blend.

### 2026-11-22 - Phase 8 - Compared WCS candidates with a separate Gaia holdout

- **Changed** Added a source diagnostic for TAN, SIP-2 and SIP-3 with detector-wide Gaia stars held out of the candidate fits. Compare the same fixed overlap positions with the saved WCS.
- **Verified** The native replay reproduced the four saved SIP-3 headers. The SIP-3 refits improved the reserved catalog P95 on all panels and reached 0.700 px and 1.200 px P95 on the two independent overlaps. Both remain above the 0.5 px overlap target. Recorded per-panel and per-region results and checked the original fingerprints. The source suite passed 238 tests with two offscreen OpenGL skips. Ruff, scoped mypy, Poetry lock validation and Markdown links passed.
- **Related** [Gaia holdout for WCS candidates](docs/phase-8.md#8b-gaia-holdout-for-wcs-candidates) and Q-029.
- **Next** Prepare the independent ICC and exposure references for 8C. Reuse the saved geometry comparison when a measured candidate optical calibration is available.

### 2026-11-22 - Phase 8C - Froze color and exposure controls

- **Changed** Added independent matrix ICC patches, profile-assignment cases, and controlled exposure changes on a registered crop of a real TIFF. The exposure fixture keeps original codes, coverage, fit samples and reserved regions available for replay.
- **Verified** Display P3 and Adobe RGB compatible conversions passed the full neutral-ramp and color checks. A separate packaged Windows probe matched the source report. The known gain and offset were verified on 61,057 held-out pixels. The exposure arrays reproduced byte for byte, and an occupied output path preserved the frozen reference. The source suite passed 241 tests with two offscreen OpenGL skips. Ruff, scoped mypy, Poetry lock validation and Markdown links passed.
- **Related** Q-005, Q-029 and [8C frozen references](docs/phase-8.md#8c-frozen-color-and-exposure-references).
- **Next** Wire profile resolution and the matrix path into the shared photo workflow. Retain the exposure controls for the following correction methods.

### 2026-11-22 - Phase 8C - Integrated photo profiles and exposure matching

- **Changed** Added version 10 photo settings, bounded matrix ICC conversion, manual EV, camera metadata normalization and held-out overlap matching to the shared preview and export workflow.
- **Verified** The focused profile, matching and assignment controls passed. The existing preview, desktop, project and CLI regression selection passed 37 checks.
- **Related** [ADR-0029](docs/adr/0029-photo-matrix-color-and-overlap-fit.md) and Q-029.
- **Next** Replay the real exposure controls, verify scientific products, and exercise the beta 14 Windows bundles.

### 2026-11-22 - Phase 8C - Verified beta 14 on local Windows

- **Changed** Built the desktop and console from clean commit `2e39e7908b3f45d5e6258346571a57f45f3aedad` and recorded both launcher hashes. Corrected redirected console output for Unicode panel names.
- **Verified** The source suite passed 248 checks with two offscreen OpenGL skips. CPU and OpenGL on the secondary display and the copied console matched on the matrix ICC control. The full owner photo and nine scientific products matched their references. Ruff, scoped mypy, Poetry lock validation and the launcher checksum checks passed.
- **Related** [8C package results](docs/phase-8.md#8c-local-windows-package-results), Q-005 and Q-029.
- **Next** Prepare the 8D Advanced and optics controls. Track fresh Windows acceptance and native distribution review.

### 2026-11-22 - Phase 8D - Froze the Advanced matching references

- **Changed** Added a reproducible offline comparison of sequential and global fits on a controlled real crop and the PA4 multi-panel chain. Recorded training, selection and final test splits, disconnected behavior and optical calibration intake.
- **Verified** The chain selected Standard, the cycle selected the global plane, and PA4 retained Off. A separate replay produced the same JSON bytes. The 13 focused tests, Ruff, scoped mypy and Poetry lock validation passed.
- **Related** [8D reference results](docs/phase-8d.md), Q-029 and the native-scale Gaia holdout.
- **Next** Qualify a positive independent network for the production fit and obtain detector-matched optical calibration.

### 2026-11-22 - Phase 8D - Screened independent mosaic exposures

- **Changed** Added a saved-project input to the offline comparison. Prepared four public Nocturne M31 exposures with local SIP-3 solutions and three native-size RGB TIFFs.
- **Verified** M31 raw B–C and B–D overlap P95 passed 0.5 px. All three native-size RGB overlaps exceeded 0.5 px. Both global candidates lacked rank and the comparison retained Off. The 15-panel PA4 screen found no qualifying link. The RGB pilot and frozen PA4 report reproduced. Eight focused tests, Ruff, scoped mypy and Poetry lock validation passed.
- **Related** [Independent M31 candidate](docs/phase-8d.md#independent-m31-candidate) and Q-029.
- **Next** Evaluate separate pointing stacks for better geometry and photometric support, then qualify the positive Advanced case.

### 2026-11-22 - Phase 8D - Prepared three independent M31 pointing groups

- **Changed** Selected eight exposures per pointing and saved the source and WCS evidence under `output/phase8d-candidates/nocturne/stacks/`.
- **Verified** The 24 distinct exposures passed catalog and field-edge validation. The selection records their archive CRC32 and source SHA-256. Eight focused regression tests passed.
- **Related** [Separate pointing stacks](docs/phase-8d.md#separate-m31-pointing-stacks) and Q-029.
- **Next** Check the three stack products and replay the frozen overlap comparison.

### 2026-11-22 - Phase 8D - Verified three independent M31 stacks

- **Changed** Published three local RGB stacks with coverage masks and a comparison project. Each uses eight unique validated exposures.
- **Verified** All three overlaps passed the geometry target. The final mean RGB P95 was 0.00072324 with Off and 0.00068827 with Standard. The frozen selection retained Off. Input checksums, independent TIFF verification, the exact comparison replay and eight focused regression tests passed.
- **Related** [M31 pointing-stack results](docs/phase-8d.md#separate-m31-pointing-stacks) and Q-029.
- **Next** Find calibrated, independently exposed RGB panels with a measurable photometric difference and comparable stellar flux for the positive Advanced case.

### 2026-11-22 - Phase 8D - Compared independent calibrated SDSS scans

- **Changed** Prepared three independently calibrated RGB panels each for M2 and M77. Added an optional comparison of global backgrounds at fixed unity gain.
- **Verified** All M2 overlaps passed geometry. The free-gain fit improved the final overlap P95 at the cost of stellar flux. Fixed-gain fits selected Off in both fields. The current Standard CLI reproduced a low inferred gain on M2. Nine focused tests, the frozen PA4 replay, Ruff, scoped mypy and Poetry lock validation passed.
- **Related** [Calibrated SDSS results](docs/phase-8d.md#independent-calibrated-sdss-panels) and Q-029.
- **Next** Qualify stellar constraints on gains before integrating Advanced. Use the calibrated network as a regression for sky-only gain bias.

### 2026-11-22 - Phase 8D - Qualified an offline stellar gain check

- **Changed** Added an optional guard that screens gains with matched stellar apertures on selection blocks and reports separate final stellar scores. It can audit gains from a current Standard CLI export.
- **Verified** SDSS M2 rejected the Standard and global gain candidates. M31 retained Off. The wider owner crop recovered both injected gain cases with final stellar median errors within 1%. The M2 replay and frozen PA4 report matched byte for byte. Sixteen focused tests, Ruff, scoped mypy and Poetry lock validation passed.
- **Related** [Stellar gain qualification](docs/phase-8d.md#independent-stellar-gain-qualification) and Q-029.
- **Next** Integrate the guard with bounded independent sampling and verify the shared Standard fallback. Advanced still needs a positive independently exposed network and measured optics.

### 2026-11-22 - Phase 8D - Integrated stellar gain validation into Standard

- **Changed** Standard now checks independent detector apertures after its RGB residual check. It retains an accepted offset or identity after a stellar veto and reports rejected gains even when another peer supplies the final correction.
- **Verified** The source M2 export kept unity gains and the matched owner crop recovered 1.25 with embedded sRGB, a matrix ICC profile and the masked contamination control. The 8 MiB source check retained Off when the star scan could not fit. The full suite passed 254 tests offscreen and the two OpenGL skips passed in a separate native run. Ruff, scoped mypy and Poetry lock checks passed. The clean beta 15 build matched source output on copied console and native CPU and OpenGL desktop checks. The version and launcher checksums matched both build records.
- **Related** [Production Standard integration](docs/phase-8d.md#standard-photo-gain-integration), ADR-0030 and Q-029.
- **Next** Run a positive independent-exposure Advanced comparison with stellar, diffuse and coverage acceptance. Measured optical calibration remains open.

### 2026-11-23 - Phase 8D - Measured the original background differences on SDSS scans

- **Changed** Added an offline diagnostic that restores the archived sky on the calibrated M2 and M77 scans. It applies the frozen overlap comparison and audits sampled coverage, relative diffuse residuals and reserved stellar apertures against the sky-subtracted frames.
- **Verified** Both reports and the frozen PA4 report replayed byte for byte. M2's final mean RGB P95 fell 43.5% with Standard and another 0.036% with the unity-gain global plane. The sampled coverage masks matched and the largest per-panel stellar aperture error P95 was 0.741% across 233 apertures. The offscreen source suite passed 250 tests with six skips. The new interpolation test passed in the seven-test focused run. Ruff, scoped mypy and the Poetry lock check passed.
- **Related** [Restored SDSS sky results](docs/phase-8d.md#restored-sdss-sky-backgrounds) and Q-029.
- **Next** Find independently exposed data with compatible sky colors and stronger spatial variation for the linked Advanced check. Measured optical calibration remains open.

### 2026-11-23 - Phase 8D - Screened Origin exposures and a measured detector flat

- **Changed** Acquired the public M51 and M37 OriginStack sessions. Validated seven independent exposures per session and compared two time-spaced triplets. Prepared the M37 detector flat with two pedestal assumptions and retained the signed dark-subtracted sample scale.
- **Verified** Both triplets retained Standard. The global plane improved final mean RGB P95 by 0.20% and 0.26%, below the frozen margin. M37 preserved the binary detector masks and WCS and matched 1,003 CFA samples per variant within one code. Two to three final apertures per edge crossed at least a 1% measured response difference and the resulting flux changes were mixed. All four overlap reports and the detector audit replayed byte for byte. Seven focused tests, Ruff, Poetry lock validation and local Markdown links passed.
- **Related** [Origin controls](docs/phase-8d.md#origin-broadband-exposures-and-detector-flat) and Q-029.
- **Next** Find an independently exposed network with more spatial sky variation and obtain a measured flat reference with larger detector shifts and matched additive calibration.

### 2026-11-23 - Phase 8D - Replayed three dithered NIRCam detector flats

- **Changed** Added a bounded offline reference for three NRCB2 F150W rate/cal pairs and their matched CRDS flat. The diagnostic includes independent archive parity, native geometry and reserved aperture measurements for one and two flat applications.
- **Verified** All 12,327,893 valid samples, three masks and both propagated variance planes matched the archive exactly. The stellar geometry P95 was 0.206–0.313 px at median detector shifts of 340–680 px. The largest-shift edge improved P95 from 7.70% to 5.54% for eight stars with at least 1% measured response contrast. The full-aperture result was mixed across edges. A separate replay matched the report byte for byte. Eight focused tests, Ruff, scoped mypy, Poetry lock and local Markdown links passed.
- **Related** [NIRCam flat reference](docs/phase-8d.md#nircam-dithered-detector-flat-reference) and Q-029.
- **Next** Retain the exact detector replay and qualify on-sky repeatability with higher-signal broadband apertures and stronger measured response contrast. Advanced still needs a positive independent-exposure network.

### 2026-11-23 - Phase 8D - Measured the flat across six NIRCam F200W dithers

- **Changed** Pinned six NRCB4 F200W rate/cal pairs and their detector flat. Added an aperture S/N check using the rate uncertainty plane and report counts for weak photometric overlaps.
- **Verified** All 24,940,290 valid samples, six masks and both variance planes matched the archive exactly. Ten overlaps passed the geometry target. One flat application reduced final flux P95 on all four overlaps with a supported scale to 0.82%–2.58%. The F150W and F200W reports replayed byte for byte. The offscreen suite passed 253 tests with six skips. The final 8D selection passed ten focused tests. Ruff, scoped mypy, Poetry lock and local Markdown checks passed.
- **Related** [F200W dither results](docs/phase-8d.md#nircam-f200w-large-dither-flat-reference) and Q-029.
- **Next** Obtain a matched visible-band flat and more reserved high-signal stars crossing strong response differences. The F200W pairs supplied three to seven final apertures each. Continue screening for a positive independent Advanced network.

### 2026-11-23 - Phase 8D - Screened calibrated M8–M20 stacks and twelve SDSS scans

- **Changed** Calibrated 15 public OSC exposures and built three disjoint time-ordered stacks. Added optional spatial and color diagnostics for the frozen overlap comparison. Screened the observed sky models from 12 separate SDSS scans with the existing fit and selection limits.
- **Verified** The three stacks passed native geometry at 0.079–0.110 px P95 and retained Off. The best SDSS RGB sky-only plane improved 4.15%, below the 15% gate. The r-band check met the sky-only gate on 217 cycles and still fell short on the full scene. TIFF samples, masks and corner coordinates checked out. Both SDSS screens, the M8–M20 report and frozen PA4 report replayed byte for byte. The source suite passed 255 tests with six skips. Ruff, scoped mypy and Poetry lock validation passed.
- **Related** [M8–M20 results](docs/phase-8d.md#calibrated-m8m20-exposure-sequence), [expanded SDSS screen](docs/phase-8d.md#expanded-sdss-m2-sky-screen) and Q-029.
- **Next** Screen a wider or multi-session RGB network with stronger measured near-neutral spatial variation and comparable stellar profiles.

### 2026-11-23 - Phase 8D - Bounded linked RGB corrections and screened M51 geometry

- **Changed** Added an opt-in pooled RGB P95 lower bound to the offline overlap and restored-sky diagnostics. Applied it to the M8–M20 stacks and restored SDSS sky controls. Screened fixed groups of public Bath M51 red and green exposures with the existing Gaia and native overlap gates.
- **Verified** The bound excluded 125 of 216 SDSS M2 sky-only cycles at the frozen plane margin. The M51 red triplet reached 1.036–1.243 px native overlap P95 and missed the 0.5 px target. The five new reports and the frozen PA4 report replayed byte for byte. The offscreen source suite passed 257 checks. Four OpenCV-dependent and two native OpenGL checks skipped. Ruff, scoped mypy and Poetry lock validation passed.
- **Related** [Linked offset results](docs/phase-8d.md#linked-additive-correction-limits), [M51 geometry intake](docs/phase-8d.md#bath-m51-geometry-intake) and Q-029.
- **Next** Screen a wider or multi-session RGB network at native scale and compare the accepted cases on reserved stellar, diffuse and coverage measurements.

### 2026-11-23 - Phase 8D - Acquired and documented a reusable public observation library

- **Changed** Downloaded 6.35 GiB of original captures, calibration and integrated masters from five providers. Added a pinned manifest and restore command, two wide-angle TIFF sequences, and sample-preserving TIFF derivatives of the four Nocturne RGB FITS cubes. Recorded the eligibility of documented processed panels for Phase 8D.
- **Verified** All 20 original hashes, ten ZIP CRC checks and four publisher hashes passed. Seven nightscape and four Nocturne derived TIFF checksums reproduced. Fourteen RGB center tiles reopened. The compressed Tulip read passed at 128 MiB. Two downloader tests, Ruff, scoped mypy and Poetry lock validation passed.
- **Related** [Public observation library](docs/public-test-data.md), Q-009 and Q-029. The unmasked wide-angle solve returned one rejected candidate and six timeouts.
- **Next** Prepare independent MOANA RGB stacks for geometry and brightness screening. Recheck nightscapes with sky masks and pointing hints.

### 2026-11-23 - Phase 8D - Tested independent MOANA RGB and masked Nightscape panels

- **Changed** Verified the 20 original archive files and reused the seven Nightscape TIFFs. Prepared four disjoint linear Float32 RGB stacks from 35 separate 120 s MOANA exposures with the supplied RGB flats and 120 s dark. Retained the observed sky levels. Retried the wide-field solves with sky masks and directions from smaller sky windows.
- **Verified** All MOANA edges met the 0.5 px geometry gate. The Standard-style fit improved mean RGB P95 by 6.13% in selection and 10.06% in final blocks. The Advanced plane improved final P95 by 0.085% over Standard and missed its selection margin. The stellar guard supported Standard. Coverage stayed identical on the comparison lattice. One Nightscape crop passed, and the seven full-field candidates failed at 2.58–6.87 px P95 overall. Provisional same-series overlap P95 was 2.91–4.73 nominal native px. Fourteen focused archive, photometry and geometry tests passed. Both MOANA reports replayed byte for byte. All original archive hashes verified again afterward.
- **Related** Q-009, Q-016 and Q-029. Preparation settings, source hashes, runnable commands and reports are in `output/phase8d-public-validation-20261123/README.md`.
- **Next** Retain MOANA as an independent Standard control. Qualify Advanced on another geometry-approved RGB network. Revisit wide-angle catalog validation with measured lens geometry or seeds distributed across the masked detector.

### 2026-11-23 - Phase 8D - Replayed the MOANA Standard control

- **Changed** Reused the four saved 120 s Lagoon Nebula stacks in a new follow-up output directory.
- **Verified** Both native geometry and photometry reports matched the earlier run byte for byte. All six edges passed at 0.193–0.408 native px P95. Standard passed the stellar guard and improved final mean RGB P95 by 10.06%. The 14 focused tests passed.
- **Related** Q-029. The replay is in `output/phase8d-validation-followup-20261123/moana-standard/`.
- **Next** Use the same frozen thresholds for the separate M33 observations and continue the 35 mm Nightscape evaluation under Q-016.

### 2026-11-23 - Phase 8D - Refit the full 35 mm Nightscape geometry

- **Changed** Built regional Gaia correspondences on all three masked TIFFs, compared the measured Sigma Lensfun profile and fit regularized detector-wide SIP models from training stars.
- **Verified** All three selected mappings passed catalog validation at 0.490–0.591 px overall and 0.489–0.537 px at the edge. The additional Gaia audit passed the per-frame gates. Pair 2–3 reached 0.482 native px on the primary final stars. All three pairs exceeded 0.5 px on the extra stars. The measured profile fell short of the catalog limits.
- **Related** Q-016 and the [35 mm measurements](docs/phase-8d.md#35-mm-nightscape-field-wide-gaia-refit).
- **Next** Investigate the overlap residuals on the wider star sample and repeat the regional checks on the 20 mm sequence.

### 2026-11-23 - Phase 8D - Measured independent M33 RGB networks

- **Changed** Prepared five signed Float32 RGB panels from 45 catalog-validated 60 s exposures across two pointings and four UTC nights. Checked legacy orientation against dark hot pixels and kept the measured sky.
- **Verified** M33 pointing 2 met native geometry at 0.196–0.237 px P95 on 103–116 high-signal final stars per edge. Both networks advanced past the linked offset bound and retained Off after the frozen checks. The free-gain cycle offset improved final RGB P95 by 13.74% versus Standard and failed stellar support. Final diffuse measurements and coverage were recorded. Both photometry reports replayed byte for byte.
- **Related** Q-009 and Q-029. [M33 source and audit notes](docs/phase-8d.md#moana-standard-replay-and-independent-m33-observations). The local run is in `output/phase8d-validation-followup-20261123/`.
- **Next** Retain M33 as a stellar-veto control and find a positive Advanced case. Keep the visible-band optical calibration and Windows delivery gates open.

### 2026-11-23 - Phase 8D - Audited Nightscape overlap tails at both focal lengths

- **Changed** Retained the accepted 35 mm WCS and measured flux, native stellar shape and detector-position associations on disjoint Gaia matches. Applied regional training and selection to all four 20 mm frames.
- **Verified** At 35 mm the outer radius stratum gave 1.045–1.349 px P95, higher than the 0.692–0.876 px middle stratum. More elongated stellar pairs had larger tails on all three overlaps. At 20 mm all four WCS fits passed the two masked Gaia holdouts. Their overlap P95 was 0.606–0.896 px and 0.742–0.966 px on the two samples. The audits and WCS outputs reproduced.
- **Related** Q-016. [35 mm residual audit](docs/phase-8d.md#35-mm-overlap-tails-on-independent-gaia-stars) · [20 mm validations](docs/phase-8d.md#20-mm-nightscape-regional-gaia-validation)
- **Next** Investigate repeatability across detector radii and centroid estimation for the elongated profiles before treating either series as a robust native overlap control.

### 2026-11-23 - Phase 8D - Screened an independent Pleiades RGB network

- **Changed** Froze the stellar quality and spatial splits before new final scores. Prepared five disjoint native stacks from 30 validated Seestar exposures and selected the geometry-qualified triplet from training and selection data.
- **Verified** Three final edges reached 0.135–0.149 px P95. The linked-offset pre-screen admitted both fixed-gain fits. The plane improved selection by 0.56% versus Off and missed its 15% gate. Both free-gain models missed the 0.015 rank limit. Off was retained. The diffuse, stellar and coverage reports, Lagoon Standard control and M33 stellar veto replayed byte for byte.
- **Archive screen** The NGC 1087 Stripe 82 screen reached a maximum spatial-span to color-floor ratio of 0.260 across 91 pairs. The sky-only screen replayed byte for byte. Fifteen focused tests and the Poetry lock check passed. [Archive screen](docs/phase-8d.md#stripe-82-gradient-intake)
- **Related** Q-029 and the [Pleiades measurements](docs/phase-8d.md#independent-pleiades-spatial-background-screen).
- **Next** Retain the five-stack spatial screen and the independent native geometry reference. The positive Advanced gate remains open.

### 2026-11-23 - Phase 8D - Validated Nightscape centroids against SEP

- **Changed** Compared alternative centers on the same Gaia identities with fixed WCS and sky masks. Froze the 35 mm elliptical moment blend on selection stars and refit both focal lengths using training stars only.
- **Verified** The 35 mm larger holdout's fixed-WCS mean pair P95 increased by 0.05054 px. Refitted whole-mask Gaia P95 exceeded 1.0 px on two frames at each focal length. All edge scores met 1.5 px. The 35 mm SEP 2–3 pair reached 0.482/0.459 native px on the primary stars and 0.930 px in the larger direction on the additional sample. No alternative pair met 0.5 px.
- **Evidence** Replayed all 7,790 held-out frame measurements, verified unchanged source and reference inputs, and passed 32 targeted tests and the Poetry lock check. The run is in `output/phase8d-nightscape-centroids-20261123/`. [Phase 8D notes](docs/phase-8d.md#nightscape-validation-of-elongated-star-centers)
- **Next** Keep Q-016 open for low-S/N and elongated profiles, measured lens geometry and a repeatable overlap result.

### 2026-11-23 - Phase 8D - Measured visible-band flat repeatability

- **Changed** Audited twelve fixed-WCS MOANA Lagoon exposures and their 120 s dark and RGB flats. Compared zero, one and two flat applications on MOANA and three documented HST F606W dithers using training-only exposure scales.
- **Verified** Ten of eighteen MOANA pairs and two of three HST pairs passed native geometry and sample support. Both series preserved their native masks and sampled footprints. No supported full-sample aperture P95 met 1%. Single-application diffuse differences improved on eleven MOANA pairs and two HST pairs.
- **Evidence** Both measurement reports replayed byte for byte. Seventeen focused source tests and the Poetry lock check passed. The sources and commands are in `output/phase8d-visible-flat-20261123/`. [Phase 8D results](docs/phase-8d.md#visible-band-flat-field-validation)
- **Next** Track MOANA's unresolved bias history and obtain stronger documented visible response support under Q-029.

### 2026-11-24 - Phase 8D - Screened visible dithers before raw calibration

- **Changed** Screened nine F438W exposures of 47 Tuc and nine F621M exposures of Omega Centauri with archive WCS and the applicable measured CRDS flat. Selected three F438W exposures using training response support. The Omega Centauri sequence supplied no apertures that met the frozen quality filters.
- **Verified** The selected pairs cover 48.13%–56.99% of the smaller WCS footprint and reach training geometry P95 of 0.065–0.085 px. The strongest link moves same-chip stars by 2,051 px on median. It has 99 of 135 common high-signal stars crossing 2% response and 54 crossing 3%. The reserved counts are 25 and 12.
- **Related** Q-029. The pre-calibration selection and per-pair counts are in `output/phase8d-visible-flat-20261124/screen/prescreen.json`.
- **Next** Replay bias and dark subtraction from the three RAW products and measure the fixed reserved sample across zero, one and two flat applications.

### 2026-11-24 - Phase 8D - Measured the F438W flat from bias- and dark-corrected RAW

- **Changed** Produced pre-flat detector images for the selected triplet with the archive's CALWF3 3.7.3 and CRDS bias and dark references. Applied zero, one and two flat divisions with fixed WCS, masks and training-only exposure scales.
- **Verified** Once matches the archive on all 50,225,160 valid detector samples within tolerance. All three held-out pairs pass geometry at 0.054–0.086 px P95 and preserve native and sampled coverage. The strongest ≥3% response subset improves from 1.388% to 1.112% and its five S/N ≥ 300 stars reach 0.666%. Complete test sets miss 1%. Once changes diffuse contrast by −7.50% to +1.62% and improves peer P95 on two pairs.
- **Evidence** The PowerShell replay matched 113 JSON files, nine masks and 18 pre-flat detector planes. It recomputed the flux scores on 122 reserved memberships. Prior F606W and MOANA hashes, thirteen focused source tests and the Poetry lock check passed.
- **Related** Q-029 and the [F438W RAW results](docs/phase-8d.md#f438w-wide-dithers-from-raw). The source identities, detector masks, aperture and diffuse measurements and reproduction are in `output/phase8d-visible-flat-20261124/`.
- **Next** Retain the previous F606W and MOANA references. Probe the full-sample aperture tails on a documented CTE-corrected or separate visible sequence. The production optics gate remains open.

### 2026-11-24 - Phase 8D - Matched the F438W CTE archive products

- **Changed** Matched all three 47 Tuc exposures to the public CALWF3 FLC entries in MAST and downloaded their detector products and the named CTE references to a separate run directory.
- **Verified** The FLC headers record `PCTECORR=COMPLETE`, CALWF3 3.7.3 and the same F438W flat as the FLT counterparts. The observation identities, archive object metadata and source hashes are recorded in `output/phase8d-visible-flat-cte-20261124/archive-lookup.json`.
- **Related** Q-029 and the [earlier F438W RAW check](docs/phase-8d.md#f438w-wide-dithers-from-raw).
- **Next** Replay pixel CTE and additive calibration from RAW, then compare the fixed held-out stars and diffuse regions across the flat modes.

### 2026-11-24 - Phase 8D - Replayed F438W pixel CTE from RAW

- **Changed** Produced CTE-corrected pre-flat detector files from the three original RAW exposures using the archive CALWF3 version and CRDS references. Reused the frozen stellar split and compared both calibration branches across Off, Once and Twice on common valid native support.
- **Verified** Once matches every valid FLC detector sample within tolerance. Both geometry checks pass the 0.5 px gate on all three pairs. Pooled Once P95 moves from 6.664% to 6.619% with CTE and all full pair samples miss 1%. The clear-core sample also misses 1%. All modes preserve common native and sampled sky support.
- **Evidence** The repeat fetch and replay matched four numerical JSON files, 15 mask files and 18 CTE pre-flat planes. The verification recovered training scales and scores on all 122 test memberships and confirmed hashes of 135 earlier files. Thirteen focused Phase 8D tests and Ruff passed.
- **Related** Q-029 and the [F438W CTE results](docs/phase-8d.md#f438w-pixel-cte-follow-up). The [run report](output/phase8d-visible-flat-cte-20261124/README.md) records aperture tails, diffuse measurements and repeat commands.
- **Next** Keep the full-sample visible flat gate open and recheck it on an independently calibrated sequence with stronger common aperture support.

### 2026-11-24 - Phase 8D - Locked an independent F606W flat comparison

- **Changed** Screened 34 public WFC3/UVIS FLCs with their native WCS and named pixel flats. Chose the 11444 LMC visit from selection-block geometry, response counts and enrollment. Locked four wide-dither exposures, a same-configuration 47 Tuc repeat pair, and all star memberships before final scoring.
- **Verified** The largest retained dither has 43 common S/N ≥ 100 stars, with 21 crossing 2% response and seven crossing 3%. The small-shift pair has 18 selection stars, 17 crossing no more than 0.5% response. The 300 S/N pilot did not provide the 15-star test floor on the LMC pairs.
- **Related** Q-029. The [prescreen](output/phase8d-visible-flat-independent-20261124/final-screen/prescreen.json) and [locked selection](output/phase8d-visible-flat-independent-20261124/locked/selection.json) record the comparison.
- **Next** Replay bias, dark and pixel CTE from the selected RAW products and score all six LMC overlaps and the repeat.

### 2026-11-24 - Phase 8D - Measured the independent F606W flat control

- **Changed** Replayed pixel CTE, overscan, bias and dark from six 11444 RAW files. Compared Off, Once and Twice on the frozen stars and common detector and sky support.
- **Verified** Once matches all 100,351,695 valid archive samples within tolerance. All six LMC pairs pass native geometry and preserve coverage. Every full-sample Once P95 exceeds 1%, and four pairs fall below the stellar support floor. The same-configuration repeat gives 1.871% Once P95 with a 0.166% median response change. Diffuse brightness and contrast were measured in the fixed source-masked regions.
- **Evidence** The numerical replay matches eight JSON reports and 19 masks. The F438W CTE regression reproduces four reports and 15 masks, and all 177 protected evidence hashes match. Thirteen focused tests, Ruff and the Poetry lock check passed.
- **Related** Q-029 and the [F606W results](docs/phase-8d.md#independent-lmc-f606w-flat-replay). The [run folder](output/phase8d-visible-flat-independent-20261124/README.md) records sources, commands and measurements.
- **Next** Retain F606W as an independent visible detector and repeatability reference. Keep the full-sample flat qualification open.

### 2026-11-24 - Phase 8D - Reproduced the 47 Tuc F606W repeatability tail

- **Changed** Replayed the frozen 14 test and 73 training apertures on the `zxq–zzq` detector pair. Recorded local annulus, neighbors, profile width and the effect of the training scale for each test star.
- **Verified** The Once errors above 1% are −1.045%, −2.785% and −1.379%. The training ratio changes absolute P95 from 1.709% to 1.871%. The largest error has a high S/N and ordinary annular scatter. A different tail star has the strongest annular asymmetry near a bright neighbor.
- **Related** Q-029 and the [per-star diagnosis](output/phase8d-f606w-repeatability-20261124/diagnosis.json).
- **Next** Complete the blind small-shift FLC archive screen. Freeze the independent exposures and memberships before comparing the annulus median and one robust sky plane in selection blocks.

### 2026-11-24 - Phase 8D - Froze an independent F606W repeat

- **Changed** Screened public FLCs from the GO-12379 47 Tuc CTE monitor. The complete-tap pilot could enroll only 5–11 stars per matching visit 07 exposure. Before flux scoring, applied the 10 px aperture to paired valid native offsets with clear 3 px cores, at least 98% aperture weight and 90% annulus taps.
- **Verified** Three independent 348 s exposures supply 96, 102 and 95 test stars over 42, 43 and 43 spatial blocks on the three links. Selection native P95 is 0.018–0.019 px. Source hashes, rules and all spatial memberships were locked before selection flux or test scoring.
- **Related** Q-029 and the [frozen repeat](output/phase8d-f606w-repeatability-20261124/frozen/lock.json).
- **Next** Fit the per-pair scales using training stars. Make the sky-method decision on selection blocks before scoring the frozen test apertures.

### 2026-11-24 - Phase 8D - Measured the independent F606W repeat

- **Changed** Used the three frozen FLCs to compare the 10 px annulus median and one robust sky plane on paired valid native taps. Each scale uses training stars only. Selection retained the median.
- **Verified** The three links pass geometry at 0.019–0.035 px P95 in both directions. Their median-method flux P95s are 3.952%, 5.107% and 4.086%, with 26, 30 and 22 stars above 1%. The prescreen, memberships and individual measurements replay exactly. An independent audit recomputed all 293 test memberships. Four earlier F606W and F438W numerical references reproduced, and 13 focused tests and the Poetry lock check passed.
- **Related** Q-029 and the [measurement, source and replay record](output/phase8d-f606w-repeatability-20261124/README.md).
- **Next** Investigate the small-shift flux tail before the conditional 2% and 3% wide-dither prescreen. Use the complete held-out flux P95 as the gate.

### 2026-11-24 - Phase 8D - Measured aperture profiles on the opened F606W controls

- **Changed** Measured cumulative 3, 5, 7 and 10 px apertures on the fixed centers and common valid pixels of the 47 Tuc pair and the GO-12379 triangle. Recorded ERR, sky quadrant sensitivity and directional wing changes.
- **Verified** The 47 Tuc 10 px error replay agrees within 0.000002 percentage points and the triangle agrees within 1e-12. T09 shifts by +1.819 percentage points in the 5/10 flux fraction. Eighteen distinct triangle stars also meet the frozen profile evidence rule. The prior F606W and F438W numerical replays pass.
- **Related** Q-029 and the [aperture profile diagnosis](output/phase8d-f606w-profiles-20261124/diagnostic/summary.json).
- **Next** Freeze the separate visit 07 group and train the one position-dependent 5-to-10 px correction for selection.

### 2026-11-24 - Phase 8D - Froze the separate Visit 07 profile repeat and decided the method

- **Changed** Screened all 21 pairs from seven unscored Visit 07 FLCs. Excluded the previously opened test stars by archive sky position and froze `ibnh07nvq`, `ibnh07nzq` and `ibnh07obq` with separate training, selection and test blocks.
- **Verified** Each frozen link contains 78–92 test stars in 42–45 blocks. The nearest new test appearance is 0.777 arcsec from any earlier exclusion, against the 0.30 arcsec limit. The 5-to-10 px fit reduced pooled selection P95 from 3.406% to 2.036%. It raised P95 on `nvq–nzq` from 3.450% to 3.471%, so selection retained 10 px before test scoring.
- **Related** Q-029, the [exposure and membership lock](output/phase8d-f606w-profiles-20261124/frozen/lock.json) and the [selection decision](output/phase8d-f606w-profiles-20261124/method-selection/method.json).
- **Next** Apply the frozen decision to all test blocks and compare the flux tails with ERR, local sky and directional wing changes.

### 2026-11-24 - Phase 8D - Scored the independent F606W profile repeat

- **Changed** Opened all 258 fixed test memberships after selection. Compared the retained 10 px measurement with the one spatial 5-to-10 px candidate and measured the profile, sky and ERR contributions on common support.
- **Verified** All three links pass both geometry directions at 0.017–0.026 px P95. Full-sample 10 px flux P95 is 2.350%–4.337% and the corrected 5 px scores are 1.764%–2.531%. Wing asymmetry has Spearman ρ 0.539 with a 95% sky-block interval of 0.408–0.644. The main and tail-pixel reports replayed, as did the earlier F606W and F438W references. Thirteen focused tests, Ruff, Poetry lock validation and local Markdown links passed.
- **Related** Q-029 and the [profile repeat, measurements and commands](output/phase8d-f606w-profiles-20261124/README.md).
- **Next** Inspect repeated asymmetric wings and localized flagged or unflagged signal on independent native data. The wider-shift prescreen remains deferred until every held-out link passes the full-sample 1% flux gate.

### 2026-11-24 - Phase 8D - Reviewed the next F606W investigation

- **Checked** Compared the Visit 07 per-link scores with the [profile repeatability record](docs/phase-8d.md#f606w-aperture-profile-repeatability). The selected 10 px aperture exceeds the 1% target on all three links.
- **Next** Under Q-029, check whether the localized wing signal follows the star, a neighbor or detector coordinates on independent small-shift F606W observations. Keep the existing test memberships for diagnosis and reserve fresh stars for validation.

### 2026-11-24 - Phase 8D - Replayed and localized the Visit 07 F606W residual

- **Changed** Recorded the native SCI, ERR, science DQ, flat DQ and neighbor locations for the target and two comparison stars. The first archival candidate triangle failed the charge-injection check. The replacement uses no-injection GO-12379 observations from Visits 08, 11 and 13.
- **Verified** The fresh replay audits all 258 Visit 07 test memberships and reproduces the native tail-pixel report byte for byte. The offset (−3, +1) supplies +13.43 and +13.50 percentage points in the two links to `ibnh07obq`. The sky and detector predictions round to the same pixel in both peers.
- **Related** Q-029, the [Visit 07 replay audit](output/phase8d-f606w-profiles-q029-replay-20261124/verification.json) and the [independent measurement protocol](output/phase8d-f606w-native-20261124/protocol.md).
- **Next** Freeze the independent memberships and exact common support before fitting training scales and opening the test fluxes.

### 2026-11-24 - Phase 8D - Tested F606W residuals across independent visits

- **Changed** Locked the three archive FLCs, sky exclusions, paired native masks and block roles before photometry. Fitted scales on training stars and measured all 95 test memberships. Traced the opened target on UVIS1 and the original pixel on UVIS2 as a separate diagnostic.
- **Verified** All three pairs pass both geometry directions at 0.049–0.063 px P95. Their 10 px P95 values are 6.049%, 5.932% and 4.680%, with 13, 9 and 10 stars above 1%. The original excess is exposure-specific at the measured amplitude. One fresh star has an exposure-local impulse in a post-score check and significant residual wings outside its patch. The wider-dither screen remains deferred. The independent replay reproduces nine files byte for byte and matches the numerical summaries and native trace. The earlier reference replays, 13 focused tests, Ruff and Poetry lock validation pass.
- **Related** Q-029 and the [native evidence, audit and repeat commands](output/phase8d-f606w-native-20261124/README.md).
- **Next** Test whether a local F606W PSF fitted on training stars predicts the distributed wing residual on a separate same-configuration repeat.

### 2026-11-24 - Phase 8D - Froze the local F606W PSF experiment

- **Changed** Froze the unscored 30 s no-injection GO-12379 FLCs `ibnh08hrq`, `ibnh11c0q` and `ibnh13hgq`. Excluded earlier test stars and locked the matched centers, native support, block roles and same-chip PSF neighbors.
- **Verified** All three prescreened links have 36–45 test stars in 25–29 blocks after local support cuts. The six training libraries contain 100–123 distinct detections per exposure and chip. Before test scoring, selection fixed the 700 px PSF challenger and the train-only scales. The zero-change reference had lower mean relative error on selection.
- **Related** Q-029, the [frozen rules](output/phase8d-f606w-local-psf-20261124/protocol.md) and the [selection decision](output/phase8d-f606w-local-psf-20261124/primary/selected/decision.json).
- **Next** Score both rings and the unchanged 10 px aperture on every fixed test star.

### 2026-11-24 - Phase 8D - Scored the independent local F606W PSF

- **Changed** Compared the frozen train-only PSF with a zero-change reference on all 117 test memberships. Repeated the comparison outside the native 3 × 3 peak patches and retained the existing full-sample 10 px aperture score.
- **Verified** The 3–5 px magnitude and direction criteria pass on two links. No pair supports the 5–10 px ring. The first two outside-patch inner-ring MAE gains are 28.6% and 24.3%, with intervals spanning zero. Both geometry directions pass on every pair, with aperture P95s of 2.403%, 1.752% and 2.325%. The fresh replay matches 13 evidence files and both numerical summaries. Thirteen focused tests, Ruff and the Poetry lock check pass.
- **Related** Q-029 and the [results, data identities and rerun](output/phase8d-f606w-local-psf-20261124/README.md).
- **Next** Test a phase-resolved empirical PSF in the 5–10 px ring on one independent no-injection F606W repeat with enough bright reserved stars.

### 2026-11-24 - Phase 8D - Froze the F606W within-pixel PSF comparison

- **Changed** Sealed four unscored 348 s Visit 07 frames, six pairs, common masks, sky-block roles and same-chip donor support. Fixed the previous local model at 700 px and added only the fitted within-pixel x/y slopes to the challenger.
- **Verified** The reserved samples contain 32–41 stars per pair that meet the 0.50-point outer-ring precision proxy, against a floor of 15. The nearest test appearance to previously opened stars is 1.305 arcsec. The final freeze removed an extra precision requirement on the descriptive selection blocks before any selection or test wing difference was calculated. All six membership files and the donor bank match the initial screen byte for byte.
- **Related** Q-029 and the [protocol and initial screen](output/phase8d-f606w-phase-psf-20261124/protocol.md).
- **Next** Check both PSFs and the unchanged 10 px aperture across all six test pairs and reproduce the evidence in a second destination.

### 2026-11-24 - Phase 8D - Scored the independent F606W within-pixel PSF

- **Changed** Compared the previous local PSF, its within-pixel x/y-slope extension and zero change on all 357 frozen memberships. Scored both rings, the sensitivity outside the native 3 × 3 patch and the unchanged 10 px aperture.
- **Verified** On all six links the x/y slopes increase 5–10 px MAE against both comparisons, with paired 95% gain intervals below zero. Well-signed counts are 4–8 per pair. Both geometry directions pass, and all full-sample aperture P95 values exceed 1%. The separate rerun matches 21 evidence files and both numerical summaries. The previous local PSF replay, 16 focused tests, Ruff and Poetry lock validation pass.
- **Related** Q-029 and the [pair tables, source manifest and rerun](output/phase8d-f606w-phase-psf-20261124/README.md).
- **Next** Qualify one long, same-configuration no-injection F606W repeat with deliberate offsets near half a native pixel in both axes. This cohort's median shifts stay below 0.20 px and its directional sample is sparse. The wider-shift flat screen remains deferred.

### 2026-11-24 - Phase 8D - Registered a two-axis F606W intake

- **Changed** Fixed the acceptable centroid fraction at 0.40–0.60 native pixels per axis, with both axes inside the interval for at least half of same-chip matches. Kept the previous stellar, common-pixel and PSF precision rules.
- **Verified** Recorded the protocol checksum before inspecting candidate FITS headers or archive results. Matched the local inventory and public MAST records against STScI's observing listings.
- **Related** Q-029 and the [frozen intake protocol](output/phase8d-f606w-half-pixel-20261124/protocol.md).
- **Next** Finish the native centroid and blind stellar-support checks before any PSF or aperture scoring.

### 2026-11-24 - Phase 8D - Verified a two-axis half-pixel shift and its support limit

- **Changed** Screened 559 FLC roots from the local inventory and MAST. Recorded both centroid fractions and their distributions for 99 putative pairs. GO-11680 Visit 02 supplies the one pair inside the registered two-axis interval.
- **Verified** All six same-chip stars on the 610 s pair fall inside the interval on both axes. Common pixels retain one of two proposed test stars. Same-chip donor checks leave zero qualified test stars, so PSF and full-sample aperture scoring stayed closed. Ordered and visit-only replays agree on the passing pair, and sixteen focused tests, Ruff and the Poetry lock check pass.
- **Related** Q-029 and the [observations, pair table and replay command](output/phase8d-f606w-half-pixel-20261124/README.md).
- **Next** Obtain a configuration-matched long F606W series with a documented two-axis half-pixel shift and enough isolated bright stars to retain at least 15 precision-qualified test stars across three blocks after the frozen checks.

### 2026-11-24 - Phase 8D - Tested the richer-field F606W dither candidates

- **Changed** Registered and evaluated 109 new links across the GO-12517 and GO-13410 coordinated visits and a GO-15594 Omega Centauri parallel pair.
- **Verified** None of the 34 nominal half-pixel links passes the measured two-axis gate. The M5 link gives seven of 206 stars in both intervals with about 0.90° relative rotation. Eight evidence files replay byte for byte. Sixteen focused tests, Ruff and the Poetry lock check pass. PSF and 10 px photometry remain unevaluated on the new links.
- **Related** Q-029 and the [richer-field measurements and replay](output/phase8d-f606w-half-pixel-followup-20261124/README.md).
- **Next** Obtain one same-visit long F606W series with guide-star continuity, a compact documented diagonal half-pixel step and enough isolated stars to pass the reserved precision gate.

### 2026-11-24 - Phase 8D - Checked compact same-visit F606W dithers

- **Changed** Registered the same-visit compact-diagonal intake, checked 1,065 FLC roots from 258 Phase II candidate visits and measured all 18 new matched links.
- **Verified** Two GO-16361 links reach 0.40–0.60 px on both axes with the same guide-star acquisition per pair. Each has one fresh match and zero common-aperture test stars. The blind screen leaves PSF and flux acceptance open. Twenty-seven blind evidence files and both plan inventories replay byte for byte. Sixteen focused tests, Ruff and Poetry lock validation pass.
- **Related** Q-029 and the [observation records, results and replay](output/phase8d-f606w-compact-dither-20261124/README.md).
- **Next** Qualify one deliberately dithered stellar calibration field with an intra-orbit F606W diagonal and enough isolated bright stars for the common-pixel, same-chip donor and reserved precision checks.

### 2026-11-24 - Phase 8D - Preflighted the NGC 1835 F606W field

- **Changed** Extended the compact intake to FLC command offsets for 99 targeted stellar visits and ran the unchanged blind enrollment, common-pixel, donor phase and precision checks on the same-acquisition NGC 1835 shutter-A pair.
- **Verified** The NGC 1835 nominal diagonal uses shutter B. Its two 408 s shutter-A exposures have one and six eligible catalog stars and no reciprocal pair. All seven fresh configuration-matched links lack a planned two-axis half-pixel command. Four evidence files replay byte for byte. Sixteen focused numerical tests, Ruff and Poetry lock validation pass.
- **Related** Q-029 and the [intake, blind results and reproduction](output/phase8d-f606w-stellar-preflight-20261124/README.md).
- **Next** Obtain a dedicated same-acquisition M5 F606W sequence with actual long shutter-A coverage at both diagonal positions.

### 2026-11-24 - Phase 8D - Checked M5 F606W acquisition feasibility

- **Changed** Resolved all 12 public individual FLCs in the targeted archive and provided a single-orbit worksheet with four 350 s exposures at two diagonal positions.
- **Verified** GO-11615 has only 150 s individual exposures. The four GO-12517 visits have one shutter-A exposure each. The mixed-shutter Visit 13 diagnostic has 138/270 same-chip matches within both phase limits. The shutter-A PSF and photometry gates remain open. The worksheet covers both initial blades and its planning estimate fits the generic visibility allowance. Six evidence files replay byte for byte and sixteen focused numerical tests pass.
- **Related** Q-029 and the [archive census, phase distributions, worksheet and replay](output/phase8d-f606w-m5-acquisition-20261124/README.md).
- **Next** Obtain an allocated HST visit for the M5 worksheet and validate the exact orbit and guide-star availability in APT.

### 2026-11-25 - Phase 8D - Ran the local M5 APT planners

- **Changed** Built an unallocated APT test visit for the frozen M5 worksheet and ran Orbit Planner and Visit Planner in APT 2026.5.1.
- **Verified** All four 350 s exposures remain in orbit 1 with one acquisition, one dither and zero overruns. The single-gyro Visit Planner output has three positive visibility windows. A fresh run reproduces the audited summary byte for byte. The real guide-star selection remains open.
- **Related** Q-029 and the [planner reports, local APT model and repeat command](output/phase8d-f606w-m5-apt-20261125/README.md).
- **Next** Obtain an allocated HST program that can execute the M5 visit and confirm guide stars for its scheduled orientation and date.

### 2026-11-25 - Phase 8D - Froze a separate Lagoon 300 s RGB intake

- **Changed** Fixed four disjoint three-light-per-filter groups from the two MOANA Lagoon pointings. The intake uses the archived 300 s dark, native green anchors and the existing spatial holdout rules.
- **Verified** The FITS header inventory supplies six or more eligible lights in each tile/filter group. The protocol checksum was recorded before any new WCS or brightness scoring.
- **Related** Q-029 and the [frozen long-exposure intake protocol](output/phase8d-moana-300s-20261125/protocol.md).
- **Next** Verify the individual catalog solutions, rank the prepared triplets using selection blocks and open the reserved measurements only for the frozen choice.

### 2026-11-25 - Phase 8D - Qualified the Lagoon 300 s source groups

- **Changed** Retained the blind start and end groups through strict catalog validation. The primary rejected one tile-1 red light and the only unused red reserve failed the same gate. The affected red stack now requires both of its two validated lights at every covered pixel.
- **Verified** The primary intake solved 35 of 36 lights. The reserve measured 1.295 px overall catalog P95 against 1.0 px. The two-light minimum was recorded before stack preparation and overlap scoring. Both earlier Lagoon 120 s reports reproduced byte for byte.
- **Related** Q-029 and the [catalog support decision](output/phase8d-moana-300s-20261125/catalog-minimum.md).
- **Next** Rank the geometry-qualified triplets using the existing selection partitions.

### 2026-11-25 - Phase 8D - Froze the Lagoon long-exposure triplet

- **Changed** Prepared four native RGB stacks and fixed `t1-late`, `t2-early` and `t2-late` using the existing selection-only ranking.
- **Verified** All six candidate edges meet selection geometry at 0.159–0.223 px P95. The strongest selected edge has linked spatial span 2.282 times the RGB color floor, with positive rank correlations for all three channel pairs.
- **Related** Q-029 and the [selection-only report](output/phase8d-moana-300s-20261125/selection.json).
- **Next** Compare the frozen triplet on the reserved geometry and photometry samples and reproduce the reports.

### 2026-11-25 - Phase 8D - Verified the independent Lagoon 300 s Standard control

- **Changed** Scored the reserved geometry, matched stars and diffuse blocks on the frozen triplet. Retained the long-exposure network as an independent Standard reference.
- **Verified** The three native edges pass at 0.137–0.250 px P95. Standard passes the stellar guard and lowers final mean RGB P95 by 13.80% versus Off. Every Advanced variant scores above Standard and all masks agree. Four TIFFs and the selection and final reports reproduce byte for byte. Independent calibrated RGB, mask, corner WCS and prior 120 s Lagoon checks pass. Sixteen focused source tests, Ruff, scoped mypy and Poetry lock validation pass.
- **Related** Q-029 and the [full measurement and replay](output/phase8d-moana-300s-20261125/README.md). This is source-side reference work.
- **Next** Screen another real RGB network for coherent spatial differences across several overlaps. The positive Advanced gate stays open.

## Entry Template

Copy this format into a new entry immediately above this template, preserving chronological order:

```markdown
### YYYY-MM-DD - Phase N - Status: short outcome

- **Changed:** Brief summary of useful work, or the attempted step if incomplete.
- **Verified:** Relevant commands/checks and their result; identify unavailable checks.
- **Related:** Question IDs, ADRs, or evidence paths; use "None" when appropriate.
- **Next:** One concrete next step and any blocker that affects it.
```

### 2026-11-25 - Phase 8D - Started: independent Bat and Wing RGB intake

- **Changed** Inventoried the local public library and Phase 8D candidates. Registered the fresh MOANA NGC 6995 Bat and Wing archives for a selection-only screen.
- **Verified** The three downloaded ZIPs have recorded SHA-256 values. Filesystem extraction uses .NET Deflate64 support. The initial FITS headers identify 60 s exposures at gain 90 and −14 °C.
- **Next** Qualify disjoint calibrated stacks, freeze the masks and spatial grids, and check whether at least two overlaps support the linked background comparison.

### 2026-11-25 - Phase 8D - Completed: Bat and Wing selection screen

- **Changed** Prepared five calibrated RGB stacks from 45 disjoint MOANA exposures and froze the candidate and model screen on training and selection blocks.
- **Measured** All ten links pass selection geometry at 0.104–0.162 native px P95. The maximum shared variation is 1.064 times the color floor. No triplet passes the coherence screen. On the best rejected triplet, the lowest Advanced selection error improves only 0.118% over Standard, below the documented margins. The final reserve stays sealed.
- **Verified** The separate build of all five stacks, reversed-order selection and both Lagoon and M33 reference controls match byte for byte. Fifteen focused tests, Ruff, scoped mypy and Poetry lock validation pass. [Evidence and replay](output/phase8d-rgb-network-20261125/README.md)
- **Next** Obtain a fresh calibrated RGB mosaic with coherent spatial variation across several overlaps. Q-029 remains open.

### 2026-11-25 - Phase 8D - Started: ZTF broadband archive intake

- **Changed** Queried the public IRSA ZTF archive at eight fixed diffuse fields. Registered the North America Nebula candidate on two telescope fields and three UTC dates before retrieving images.
- **Verified** The fixed metadata screen identified 18 separate i, r and g exposure IDs, three per panel. The two median footprint envelopes overlap by 17.87% before detector masks.
- **Next** Verify the archival science and mask products, make six native-r-scale panels and measure selection-only spatial coherence.

### 2026-11-25 - Phase 8D - Completed: ZTF and HST archive intake

- **Changed** Froze the six-panel ZTF metadata candidate from 28,188 index rows. Five of 36 FITS products were retrieved after direct and cutout attempts. Prepared four alternative ACS M51 RGB panels from twelve independent FLCs.
- **Measured** The ACS links have at most 96 of 128 required selection RGB samples and insufficient native stellar support. The largest measured shared span is 1.249 times the color floor, with a negative R–B correlation. The final reserve stays sealed.
- **Verified** The ZTF metadata choice, four rebuilt ACS TIFFs and reversed-order selection reproduce exactly. Fifteen focused tests, Ruff, scoped mypy and Poetry lock validation pass. [Archive results and replay](docs/phase-8d.md#ztf-archive-intake-and-hst-m51-fallback)
- **Next** Complete retrieval of the frozen ZTF science images and masks. Q-029 remains open.

### 2026-11-25 - Phase 8D - Started: frozen ZTF product recovery

- **Changed** Rechecked the five prior products against their recorded checksums and consolidated them in a new recovery directory. Retained all 18 frozen exposure identities.
- **Verified** Recovered the missing May 23 field 730 i-band mask. All three science and mask pairs now agree exactly at four corners and the center, with gain 6 e−/ADU. The first RGB panel is ready for preparation.
- **Next** Continue archive recovery for the remaining exposures and prepare the six-panel network if the complete data become available.

### 2026-11-25 - Phase 8D - Completed: ZTF acquisition restored

- **Changed** Recovered the 31 missing science and mask products from IRSA while preserving the frozen 18-exposure set. A sequential transfer pass and two longer retries completed the acquisition.
- **Verified** All 36 full detector rasters passed the recorded identity and file-size checks. The prior 70-second transfer limit had truncated two otherwise successful science responses. The final receipt identifies all six complete panels. [Source products and hashes](output/phase8d-ztf-recovery-20261125/verified-pass.json)
- **Next** Rebuild all six panels in two destinations and run the frozen selection screen.

### 2026-11-25 - Phase 8D - Completed: recovered ZTF RGB selection

- **Changed** Rebuilt the six frozen panels with source-detection mask bits 1 and 11 retained. All old covered RGB values remain exact. The initial zero-mask run is preserved for diagnosis.
- **Measured** All 15 links pass selection geometry at 0.051–0.088 native px P95. The largest shared variation is 0.180 times the color floor, so no triplet advances. Standard is the selection-only choice on the highest-ranked rejected triplet. The final reserve stays sealed.
- **Verified** The revised preparation and selection, both Lagoon controls and the M33 veto replay byte for byte. All 54,123,707 covered green anchor samples agree with their original rasters. Fifteen focused tests, Ruff, scoped mypy and Poetry lock validation pass. [ZTF evidence and replay](docs/phase-8d.md#recovered-ztf-north-america-nebula-network)
- **Next** Screen a calibrated one-shot-color mosaic with simultaneous broadband RGB and shared spatial support. Q-029 remains open.

### 2026-11-25 - Phase 8D - Orion OSC archive intake

- Verified the public JF1960 Orion 2 × 2 archive and its updated single-channel Bayer master files. Identified 233 independent 90 s science records and froze 28 for four native-grid stacks. The shared flat's bias treatment is undocumented, so the protocol reserves a selection-only bias-subtraction sensitivity check. [Frozen protocol and archive identities](output/phase8d-osc-intake-20261125/protocol.md)

### 2026-11-25 - Phase 8D - Completed: Orion OSC network screen

- **Changed** Rebuilt the same 28 observations with strict edge-supported catalog solutions. Retained the raw archive WCS preparation and replay for comparison.
- **Measured** Four overlaps qualify at 0.098–0.138 native px P95. The largest qualified shared span is 0.620 times the RGB color floor, rising to 0.708 in the flat-bias check. Both fall below 2.0. The four-link selection retains Standard at mean RGB P95 `5.35829e-4`. The closest Advanced model raises the mean by 0.25% and worsens the p21 / p22 link by 2.48%. The final reserves stay sealed.
- **Verified** The four TIFFs and masks, metadata, star catalogs and model reports match the separate reversed-order replay. Both Lagoon Standard controls and the M33 stellar veto reproduce byte for byte. Fifteen focused tests, Ruff, scoped mypy and Poetry lock validation pass. [Orion evidence and repeat command](output/phase8d-osc-intake-20261125/README.md)
- **Next** Verify the broadband optical configuration and matched calibration of Corsec's four-panel Elephant Trunk observations. Q-029 remains open.

### 2026-11-25 - Phase 8D - Completed: Elephant Trunk archive intake

- **Changed** Recorded Corsec's linked AstroBin capture details and inventoried four independently exposed pointings with 960 listed 120 s lights. The published record supports broadband OSC and leaves the per-exposure filter state unspecified.
- **Measured** Checked all 240 calibration headers. The 120 s master dark supports the cold detector setup. The closest flat and short dark differ by 9.1 °C, leaving the warm additive correction unverified. Selection and final scoring remain closed.
- **Verified** Independently retrieved and verified 37 complete FITS files, 240 calibration header ranges and both receipts. The frozen Lagoon Standard and M33 stellar-veto controls verify. Eleven focused tests, intake lint and documentation link checks passed. [Intake and repeat command](output/phase8d-corsec-intake-20261125/README.md)
- **Next** Find a public broadband OSC dataset with a documented flat additive correction. Q-029 remains open.

### 2026-11-25 - Phase 8D - Completed: public broadband calibration archive search

- **Changed** Inventoried 12 MILAN release packages and checked nine archive directories and FITS members across the 3AM and MILAN sources.
- **Measured** The nine audited observation ZIPs list 4,677 FITS images and zero named calibration companions. The five tested 3AM nebular samples use the LP dual-band mode. The broadband M31 example has a single light folder. MILAN's three nearby sessions provide no verified optical flat calibration. No candidate advances to selection or final scoring.
- **Verified** The second destination reproduces the archive receipt and all 27 retrieved byte ranges. The two Lagoon controls and M33 veto match their frozen reports. Eleven focused tests and the intake lint and link checks pass. [Results, source identities and repeat command](output/phase8d-broadband-calibration-intake-20261125/README.md)
- **Next** Find a public GROND run with traceable optical flats and overlapping simultaneous g′, r′ and i′ observations. The OB #8 feasibility check found a nearest indexed flat 169.4 days later. Q-029 remains open. [GROND preflight](output/phase8d-broadband-calibration-intake-20261125/README.md#grond-optical-follow-up)

### 2026-11-25 - Phase 8D - Completed: GROND optical calibration and geometry intake

- **Changed** Retrieved two independently exposed GROND triplets with same-night optical calibrations. J1016+0419 supplied only four selection stars on its best link. The flat-first archive shortlist of 3,949 rows supplied the dense 2XMMJ1745-2902 retry.
- **Measured** All 28 dense-field FITS files match the optical detector configuration. The calibration retains 10 g′, 10 r′ and 11 i′ flats. The three native r′ links pass at 0.1029–0.1315 px P95 on 49–56 selection stars each. RGB model selection and final blocks remain reserved.
- **Verified** Both original and reversed replays match the raw source files, decompressed FITS, signed calibrated channels, binary masks and geometry results. Both Lagoon controls and the M33 stellar veto verify. Eleven focused tests and experiment lint and link checks pass. [GROND source manifests, table and replay](output/phase8d-grond-flat-first-20261125/README.md)
- **Next** Register the simultaneous g′ and i′ channels onto r′ and measure the training and selection RGB coherence of the dense triplet. Q-029 remains open.

### 2026-11-25 - Phase 8D - Completed GROND RGB selection screen

- **Changed** Registered the three simultaneous optical channels of the dense GROND field and froze the common relative reference, coverage, source masks and spatial split. The inter-panel r′ and cross-channel geometry pass all nine checks at 0.086–0.177 native px P95.
- **Measured** Zero links meet the RGB coherence intake. The shared spans reach 0.374–0.609 times the color floor, with a negative channel-pair correlation on every link. Standard survives the selection diagnostic. The unity-gain offset reduces the mean by 0.0096% and worsens two links. The free-gain fits lack rank. The final reserve stays sealed.
- **Verified** Image arrays, coverage masks, geometry and selection receipts replay byte for byte in reversed panel order. The two Lagoon Standard controls and the M33 stellar veto verify. Eleven focused tests and experiment lint pass. [Source identities, per-link table and repeat commands](output/phase8d-grond-rgb-20261125/README.md)
- **Next** Screen a fresh same-session broadband OSC mosaic with matched calibration for coherent RGB background variation on at least two overlaps. Q-029 remains open.

### 2026-11-25 - Phase 8D - Completed Canon Whirlpool OSC selection

- **Changed** Audited nine Canon archives and sampled 24 independent CR2 lights and 18 calibration frames. Froze the same-session Whirlpool triplet after the Jellyfish samples left an ISO 100 flat additive reference unverified. Used the same-frame shielded pedestal for the warmer Whirlpool flats.
- **Measured** The strict absolute solve for the middle panel misses 1.0 px. A training-only relative retry qualifies all three native links at 0.429–0.479 px P95. The shared spans reach 0.611–0.999 times the color floor. Standard survives selection, the unity-gain plane raises the mean by 0.482%, and final blocks stay sealed.
- **Verified** The independent second destination reproduces all 42 source frames, calibrated arrays, masks and receipts. Both Lagoon Standard controls, the M33 veto, 11 focused tests and Ruff pass. [Canon measurements and rerun](output/phase8d-osc-session-20261125/README.md)
- **Next** Inspect the remaining Jellyfish calibration headers for an ISO 100 additive reference. Q-029 remains open.

### 2026-11-25 - Phase 8D - Completed Jellyfish ISO 100 calibration audit

- **Changed** Read the full Jellyfish CR2 calibration inventory and five companion archive inventories. Verified the PixInsight project descriptor and retained only its process classes and FITS keyword names in the receipt.
- **Measured** The 17 Jellyfish flats are ISO 100 at 2.5 s and 21–22 °C. Its 28 additive files are ISO 800 at 11 °C. The other unique additive files are ISO 1600. The 132 distinct calibration identities yield zero ISO 100 matches. Both RGB reserves stay sealed.
- **Verified** The reversed independent fetch matches all ZIP tails, compressed ranges, decoded prefixes, the project descriptor and the report. Nine complete earlier CR2 hashes and metadata agree. Both Lagoon Standard controls, the M33 veto, 11 focused tests and Ruff pass. [Sources, measurements and repeat command](output/phase8d-jellyfish-calibration-20261125/README.md)
- **Next** Measure same-frame pedestal repeatability in the shielded detector border of the original ISO 100 flats. Q-029 remains open.

### 2026-11-25 - Phase 8D - Completed Jellyfish shielded pedestal repeatability

- **Changed** Recovered all 17 original ISO 100 flats in two destinations. Froze native Bayer phases and two independent strips in the Canon 40D optical-black margin.
- **Measured** The strip agreement is 0.386 DN P95. The preferred same-frame phase estimator predicts the held row bands at 0.959 DN P95. The G1 frame-to-frame span is 1.021 DN and the other phase spans are 0.125–0.156 DN. The active-area additive term remains unverified and both RGB reserves stay sealed.
- **Verified** The reversed independent replay matches all complete CR2 hashes and measurement receipts. The two Lagoon Standard controls, M33 veto, 11 focused tests and Ruff pass. [Measurements, source identities and repeat command](output/phase8d-jellyfish-pedestal-20261125/README.md)
- **Next** Test whether the observed illumination span constrains a residual active-area additive term on reserved calibration frames. Q-029 remains open.

### 2026-11-25 - Phase 8D - Completed Jellyfish active-area fit check

- **Changed** Froze disjoint 9/4/4 flat assignments and 591 detector tiles. Fit zero-intercept and free-intercept responses after the measured shielded pedestal.
- **Measured** The free intercept reduces reserve mean frame P95 from 9.667 to 7.484 DN and worsens one reserved frame. The independent training-half map differences reach 492–920 DN P95. The independent reserve fit agrees in spatial ranking with the full-training fit and differs by 105–200 DN P95. Shifting the illumination zero changes the inferred additive map without a measurable prediction change. Both RGB reserves stay sealed.
- **Verified** Two independent source directories and reverse decode reproduce both receipts and all 17 complete CR2 hashes. Both Lagoon controls, the M33 veto, 11 focused tests and Ruff pass. [Method scores and reproduction](output/phase8d-jellyfish-flat-leverage-20261125/README.md)
- **Next** Obtain and assess an independent ISO 100, 2.5 s zero-light sequence at 21–22 °C from the original detector. Q-029 remains open.

### 2026-11-25 - Phase 8D - Completed Jellyfish zero-light archive search

- **Changed** Verified Canon MakerNote body identity across the remaining 677 CR2 headers in the six public archives and checked the project's local CR2 and ZIP inventory.
- **Measured** All 809 distinct archive identities share the reference body. The only ISO 100, 2.5 s and 21–22 °C files are the 17 illuminated flats. No verified matched zero-light sequence is available in the checked sources. Jellyfish stays at calibration intake and both RGB reserves stay sealed.
- **Verified** The independent reverse fetch reproduces the six ZIP tails, 677 source ranges, decoded prefixes and the search receipt. Both Lagoon Standard controls, the M33 stellar gain veto, 11 focused tests and Ruff pass. [Results and repeat commands](output/phase8d-jellyfish-zero-light-20261125/README.md)
- **Next** Obtain an independent series of capped CR2s from the original Jellyfish camera at the flat settings. Q-029 remains open.

### 2026-11-26 - Phase 8D - Screened independent SkyMapper DR4 RGB observations

- **Changed** Switched to a different public source. Froze nine independent SkyMapper g/r/i exposures around Rho Ophiuchi and prepared three linear RGB CCD footprints with separate archive-derived masks. The optional Jellyfish receipt checker rejects its two real controls as expected.
- **Measured** Three SkyMapper links supply 272–305 selection sky samples each. Zero qualify on native stellar geometry. Shared spatial-to-color ratios range from 0.02530 to 0.03999. The free-gain designs lack rank and final samples stay sealed.
- **Verified** Reverse retrieval matches the decoded FITS and mask arrays, stable FITS metadata, TIFFs, masks and selection measurements. File hashes differ with download timestamps and the source science header checksums are invalid. Both Lagoon controls, the M33 veto, 11 focused tests and Ruff pass. [Input identities, results and repeat commands](output/phase8d-skymapper-intake-20261125/README.md)
- **Next** Screen larger public CFHT MegaCam Elixir g′/r′/i′ footprints with retained sky for a qualified independent network. Q-029 remains open.

### 2026-11-26 - Phase 8D - Screened CFHT MegaCam M13 short exposures

- **Changed** Queried ten CADC fields and froze nine disjoint g/r/i exposures across three M13 CCD 12 dither groups. Applied the documented linear photometric conversion and retained separate binary coverage. Repaired two nominal p2 WCS seeds and fit one relative affine map per non-reference panel from training stars.
- **Measured** All three links pass native selection geometry at 0.270–0.331 px P95. The largest common background span is 1.712 times the color floor. Off ties Standard. The Advanced offset improves the mean by 1.202% and `5.034e-7`, below both gates. The reserves stay sealed.
- **Verified** Ten queries, nine detector arrays, stable FITS headers, native TIFFs, masks, relative fit and selection measures reproduce independently in reverse order. Both Lagoon controls, the M33 veto, 11 focused source tests and Ruff pass. [CFHT source identities, scores and rerun](output/phase8d-cfht-elixir-20261126/README.md)
- **Next** Screen adjacent CCD 13 of the short M13 dither sequence for coherent RGB links. Q-029 remains open.

### 2026-11-26 - Phase 8D - Verified M13 detector extension and closure evidence

- **Changed** Screened adjacent CCD 13 and all five dither groups on each of CCDs 12 and 13. Retrieved both red flat cutouts from the exact Elixir master. Replayed the two frozen NIRCam references and checked the existing beta 15 launchers.
- **Measured** Adjacent CCD 13 qualifies three geometry links and zero coherent RGB links. The five-dither screens qualify 19 of 20 geometry links and zero coherent RGB links. Off ties Standard in the diagnostics. Across 618 visible flat selection memberships, seven reach 2% and zero reach 3%. Final blocks stay sealed.
- **Verified** Independent replay matches 30 distinct science cutouts, both flat arrays, panel and mask outputs, affine fits and selection metrics. Both Lagoon controls and the M33 veto pass. The offscreen suite passes 259 with six skips. Both NIRCam report hashes match. Ruff, Poetry lock and beta 15 launcher hashes pass. [Evidence and outstanding gates](output/phase8d-completion-20261126/README.md)
- **Next** Qualify a fresh calibrated RGB network with two coherent links. Visible optical qualification and clean Windows acceptance also remain open.

### 2026-11-26 - Phase 8 - Closed on the verified beta 15 scope

- **Changed** Recorded the closure decision and the disposition of all six stages. Moved deferred Q-029 into the active topic register with revisit conditions.
- **Checked** Reviewed stage criteria against the recorded package and reference results and checked closure links. The last recorded source run passed 259 tests with six skips.
- **Next** Select the next milestone. Clean Windows acceptance and native redistribution review remain outstanding before portable publication.

### 2026-11-26 - Architecture review - Prepared refactoring candidates

- **Changed** Reviewed production hot spots across 65 commits. Prepared a temporary HTML report comparing plate-solve batch policy, photo preparation, live preview state, and sky preflight.
- **Checked** Traced current call paths against the relevant ADRs and regression tests. Checked the report's links and desktop and narrow layouts. This review did not require an application test run.
- **Next** Select a candidate through [Q-031](questions_open_topics.md#q-031---architecture-review-follow-up). The first recommendation is to consolidate shared plate-solve batch policy while preserving desktop partial results and CLI atomic publication.

### 2026-11-26 - Architecture review - Selected plate-solve batch policy

- **Changed** Recorded the owner's selection of the shared plate-solve batch candidate.
- **Checked** Traced the two batch entry points, the Phase 3.6 deadline contract, and existing desktop and CLI publication tests. The CLI currently checks reusable WCS on unselected panels before filtering explicit panel selections.
- **Next** Settle the targeted CLI scan scope in [Q-031](questions_open_topics.md#q-031---architecture-review-follow-up) before designing the shared module.

### 2026-11-26 - Architecture maintenance - Shared project plate-solve batch

- **Changed** Moved ordered solve execution, cancellation checks and job-budget stop handling into the Qt-free project module. The CLI checks reusable WCS only for explicitly selected panels. The desktop applies completed outcomes and the CLI publishes complete project copies atomically.
- **Verified** Reproduced the selected-panel failure before the fix. The regression passes after the fix. All 36 focused Windows source tests pass, including real solve diagnostics, desktop progress and retry, and CLI budget, cancellation and publication checks. Scoped Ruff and mypy pass.
- **Next** Run the full source suite and close [Q-031](questions_open_topics.md#q-031---architecture-review-follow-up).

### 2026-11-26 - Architecture maintenance - Verified plate-solve source changes

- **Verified** The full Windows offscreen source suite passed 261 tests with six skips. Four require optional OpenCV and two require a native OpenGL desktop. Ruff passed across source, tests and tools. Scoped mypy passed on all four changed Python files.
- **Resolved** Closed [Q-031](questions_open_topics.md#q-031---architecture-review-follow-up) and clarified the [CLI panel-selection contract](docs/phase-4a.md#prepare-a-project-without-the-desktop).
- **Handoff** Verification covers the source checkout. A portable build can be verified when this change is included in the next Windows package.

### 2026-11-26 - Phase 9 - Planned desktop undo and redo

- **Changed** Added the [four-stage development plan](docs/phase-9.md) and tracked the history budget in [Q-032](questions_open_topics.md#q-032---desktop-edit-history-budget).
- **Checked** Reviewed project mutations, session commands, editor resets, saved-state comparisons and partial solve publication. Checked the new plan links and milestone references.
- **Next** Begin 9A with the edit inventory and a panel-edit round trip through save, undo, redo and branch replacement.

### 2026-11-26 - Published the beta 16 source pre-release

- **Changed** Committed the shared plate-solve batch handling, selected-panel WCS inspection, Phase 8 records and reproduction tools, and Phase 9 plan. Published the source ZIP and its SHA-256 receipt from annotated tag `v0.1.0b16`. [GitHub pre-release](https://github.com/Batu-98/AstroMosaic/releases/tag/v0.1.0b16)
- **Verified** The Windows source suite passed 261 tests with six documented skips. Poetry lock validation, Ruff, scoped mypy, and the local Markdown link check passed. The downloaded source ZIP matched the published checksum.
- **Handoff** The desktop and CLI were built from the clean tagged source. Native desktop CPU and OpenGL checks and the packaged CLI passed the M13 plate-solve workflow. Confirmed launcher versions and SHA-256 hashes. [Release and build records](docs/windows-release.md#verification-status)
- **Next** Complete clean-machine acceptance and native redistribution review before publishing portable Windows downloads. Continue with Phase 9A. [Distribution tracking](questions_open_topics.md#q-005---application-licensing-and-distribution-model)

### 2026-11-26 - Architecture maintenance - Consolidated sky photo preparation

- **Changed** Moved photo eligibility, profile resolution, ICC reservations and full-grid correction fitting into [photo preparation](src/astromosaic/pipeline/photo_preparation.py). The sky renderer keeps source and WCS validation, framing, tile sampling and output publication.
- **Checked** The mixed-ICC control and SDSS M2 reproduced TIFF bytes, preview and detail samples and masks, WCS, peak reservations and fit diagnostics before and after the refactor. The M17 scientific FITS crop matched byte for byte. All 21 focused photo and preview tests passed, including aggregate ICC limits and cropped detail parity. Ruff and scoped mypy passed.
- **Next** Complete the full Windows source suite. [Photo workflow](docs/phase-8.md#8c-photo-color-and-exposure-workflow)

### 2026-11-26 - Architecture maintenance - Verified sky photo preparation

- **Verified** The full Windows offscreen source suite passed 263 tests with six documented skips. Four require optional OpenCV and two require a native OpenGL desktop. Ruff across source, tests and tools and scoped mypy passed.
- **Handoff** Verification covers the source checkout. The exact-output controls and the [photo workflow guide](docs/phase-8.md#8c-photo-color-and-exposure-workflow) document the shared preparation.

### 2026-11-26 - Architecture maintenance - Unified live preview state

- **Changed** Bound completed overviews to the project, layer, band and effective grid. Pending workers publish only to their own request. Detail follows the active overview identity. Crop Cancel restores its original overview and panel mutations are disabled during the draft.
- **Fixed** Retained the selected sky band across transient panel inspection. The live preview rebuilds when that band is still available.
- **Checked** All 21 focused offscreen tests and all four native Windows preview and viewport checks passed. Scoped mypy and Ruff passed. The existing composition highlight redraw issue is recorded in [Q-033](questions_open_topics.md#q-033---composition-overlap-highlight-at-detail-zoom).
- **Next** Finish the full source suite and replay the real SDSS M2 detail, crop and photo workflow.

### 2026-11-26 - Architecture maintenance - Verified live preview lifecycle

- **Verified** The Windows offscreen source suite passed 266 tests and skipped four optional OpenCV cases and two native OpenGL cases. The native Windows run passed all four selected CPU and OpenGL tests, including both OpenGL skips. Ruff and scoped mypy passed. Preview state also ran with Qt imports blocked.
- **Replayed** The native CPU view of real SDSS M2 data matched the resolved grid and tone at 1:1. A completed detail result was discarded after switching layers. Crop Cancel restored the original overview and the desktop photo TIFF matched the source reference byte for byte over 1,224,736 covered pixels.
- **Handoff** Verification covers the Windows source checkout. The [live preview and crop guide](docs/phase-3c.md#adaptive-framing-and-interactive-crop) records the updated workflow. The composition highlight follow-up remains in [Q-033](questions_open_topics.md#q-033---composition-overlap-highlight-at-detail-zoom).

### 2026-11-26 - Architecture maintenance - Separated sky preflight from render planning

- **Changed** Shared input, WCS, layout and destination validation between sky preflight and rendering. Preflight returns panel count, crop dimensions and channel count after scientific metadata and refinement eligibility checks.
- **Fixed** Preflight and export share the FITS suffix check for proposed scientific sky output. [Q-034](questions_open_topics.md#q-034---sky-preflight-output-suffix)
- **Checked** Reproduced both the unsupported-suffix mismatch and the unnecessary footprint work. All 55 focused source tests passed after the change. The real M17 FITS and wide RGB ZEA/TIFF cases returned identical CLI JSON before and after.
- **Next** Finish the full Windows source suite and the real photo and science output comparison.

### 2026-11-26 - Architecture maintenance - Verified sky preflight and render parity

- **Verified** The complete Windows offscreen source suite passed 266 tests with six skips. The native Windows run passed all four selected CPU and OpenGL tests, including both OpenGL skips. Four optional OpenCV cases were skipped. Ruff and scoped mypy passed.
- **Replayed** M17 and wide RGB ZEA returned identical preflight JSON without creating output. The mixed-ICC and SDSS M2 photo exports and the M17 scientific FITS control matched their prior files byte for byte.
- **Handoff** Verification covers the Windows source checkout. The [preflight documentation](docs/phase-4a.md#create-and-validate) and resolved [Q-034](questions_open_topics.md#q-034---sky-preflight-output-suffix) record the shared checks.

### 2026-11-26 - Desktop maintenance - Fixed overlap highlighting at 1:1

- **Changed** Applied the active overlap highlight to the overview and detail redraws in the viewport. The detail worker now delivers the original display frame. The viewport retains the displayed region and 1:1 label during either toggle.
- **Verified** The framebuffer regression failed before the fix on CPU and OpenGL and passed after it. The Windows source run passed 27 focused tests with two OpenGL skips and five native CPU and OpenGL tests, including both skips. Ruff and scoped mypy passed.
- **Replayed** The real Paranal composition matched the expected detail colors and coverage on native CPU and OpenGL in both toggle directions. A new detail computed while highlighting was enabled also restored the original colors on toggle off. The previous and current tint calculations matched in 273 tone cases.
- **Handoff** Closed [Q-033](questions_open_topics.md#q-033---composition-overlap-highlight-at-detail-zoom). Verification covers the Windows source checkout.

### 2026-11-26 - Desktop diagnosis - Measured panel import and sky preview latency

- **Measured** On Windows 11 with an i5-14600K and RTX 4070, the current source opened the saved two-panel TIFF project and finished panel inspection in about 20–26 ms. Adding those two real 6000 × 4000 RGB TIFFs from an empty project took 2.53 s. The foreground check scanned all 48 million source pixels and spent 1.74 s in TIFF tile reads and conversion.
- **Replayed** The native CPU viewport delivered its first proxy in 2.97–9.09 s and completed three previews in 11.13–18.29 s. The native OpenGL viewport delivered its first proxy in 2.60–2.95 s and completed two previews in 11.27–11.41 s. Each trial requested 232,030,391 source pixel positions across 240 TIFF windows, counting repeats. TIFF tile reads and conversion took 6.00–12.81 s. The three CPU M17 FITS control previews delivered a proxy in 71–115 ms. The OS file cache was managed by Windows throughout.
- **Located** The compositor reads a bounding rectangle of source pixels for each output tile. Its coarse, tone-reference, and adaptive passes repeat this work. OpenGL uploads and draws the resulting raster. [Earlier PA4 measurements](docs/phase-6.md#local-zea-geometry-and-performance-results) · [Adaptive preview design](docs/adr/0027-adaptive-sky-preview.md)
- **Next** Track bounded source reuse and separate first-frame and import timing in [Q-035](questions_open_topics.md#q-035---desktop-panel-import-and-sky-preview-latency). The local probe is `output/preview-load-diagnostic-20261126.py`. The comparison with PTGui uses the vendor's description of its OpenCL preview. [PTGui Panorama Editor](https://www.ptgui.com/whatsnew/110000)

### 2026-11-26 - Desktop preview - Accelerated sky sampling with OpenGL compute

- **Changed** Added worker-thread GPU interpolation for the sky overview, crop and 1:1 detail. Compatible contiguous TIFFs supply the requested source neighbors directly from the original file. No image cache is added. CPU interpolation remains available, and the scientific and photo export sampling continue through the CPU reference. [ADR-0031](docs/adr/0031-gpu-sky-preview-sampling.md)
- **Measured** On the same RTX 4070, the two linear TIFFs took 2.43–2.70 s for the complete GPU overview and 0.11–0.30 s for the first proxy over three runs. They supplied 2.98 million neighboring source samples per run. The previous warmed OpenGL runs took 11.27–11.41 s. The original UInt16 TIFF pair took 14.45 s on the first measured run and 2.35 s on repeat. Windows managed the file cache in every run.
- **Checked** The native Windows source matched CPU coverage and tone levels exactly for M17 FITS and the original PA4 TIFFs at overview and detail scales. Normalized RGB matched within `2e-7`. The real OpenGL close regression passed.
- **Next** Verify the local beta 17 executable and track cold-read and foreground import latency separately in [Q-035](questions_open_topics.md#q-035---desktop-panel-import-and-sky-preview-latency).
