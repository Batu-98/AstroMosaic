# ADR-0017: Prioritize Local ASTAP for Qualified Plate Solving

- **Date:** 2026-11-17
- **Status:** Accepted and implemented. Windows acceptance is tracked in the [Phase 3.6 results](../phase-36-results.md).
- **Supersedes:** The Gaia-before-ASTAP order in [ADR-0005](0005-offline-solver-chain.md) and the order referenced by [ADR-0010](0010-seiza-gaia-backend.md). Their offline, source-preservation and Seiza-backend decisions remain in effect.

## Context

The owner requested a Phase 3.6 after the [Mosaic Master comparison](../plate-solve-comparison.md). The current implementation has an eight-match Gaia floor, fixed manual D05 selection, no requested Gaia SIP and per-stage timeouts. The ASTAP adapter already runs the actual local executable but does not expose matched-star quality metrics.

## Decision

For new Phase 3.6 solves, reuse usable effective WCS first, then attempt local ASTAP with hints and a bounded blind/FOV-free recovery, followed by Seiza/Gaia with hinted and scale-free recovery where available. Stop only on an applicable validated candidate, cancellation or exhausted total budget. Missing ASTAP must not disable a configured Gaia backend. Keep Astrometry.net excluded.

Require at least 15 unique accepted image/catalog matches for newly qualified ASTAP and Gaia results. Define comparable RMS and spatial validation, retaining Gaia false-match checks. Do not accept approximate placement as a qualified solution or manufacture missing ASTAP metrics. Preserve existing WCS with an honest evidence grade and support explicit revalidation.

Provide Automatic ASTAP catalog selection and preserve a manual D-series override. Prefer tested native automatic selection when its result is reproducible and identifiable; otherwise resolve locally and pass an explicit catalog. Use the tested command-line interface, keeping GUI automation outside normal solving. Freeze the native capabilities and an ASTAP-only quality-evidence path before implementing the new gate.

Use bounded low-order TAN/SIP model validation and one monotonic panel deadline covering preparation through publication, with optional job-wide budgeting. Exact numerical defaults, catalog-selection mechanism and migration details are frozen in Phase 3.6A from the proposals in the [detailed phase plan](../phase-36.md). Keep source/mask-bound atomic sidecars, Qt-free processing and shared preview/export geometry.

The measured ASTAP-only fallback retains a supplied pointing for FOV-auto recovery when both position and scale were supplied. With neither hint, it can borrow up to 60 seconds for full-sky recovery while preserving the per-attempt and panel deadlines. An available Gaia catalog restores the unrestricted 25-second ASTAP recovery cap and Gaia's independent scale-free fallback. [Implementation evidence](../phase-36-results.md#real-field-source-checks)

## Consequences

The new order changes the selected backend when both are available. Compare per-backend numerical evidence against the scientific gates. Older projects remain readable and retain their original solution provenance. The owner authorized [Phase 4A](../phase-4a.md) to start from the locally verified Phase 3.6F baseline, with full Phase 3.6 acceptance pending. Earlier Phase 2 and 3.5 results remain historical reference points.
