# ADR-0005: Use a fully offline solver chain

- **Date:** 2026-11-15
- **Status:** Accepted by the project owner.

**Phase 3.6 update (2026-11-17):** [ADR-0017](0017-astap-first-validated-solving.md) supersedes the order below for planned new solves: existing WCS, ASTAP hinted/blind recovery, then Gaia. The implemented Phase 2/3.5 order and its evidence remain historical. Offline-only operation, cancellation and source preservation remain in effect; implementation of the revised order is pending.

## Decision

Validate existing WCS first. If needed, attempt local Gaia DR3, then ASTAP with approximate pointing, then blind ASTAP. Skip hinted ASTAP when pointing hints are absent. Stop on the first validated WCS or when the job is cancelled. Report an unsolved panel when the local chain is exhausted.

Astrometry.net web and local tools are excluded. Preserve input pixels and headers, and store the solved WCS separately. [ADR-0010](0010-seiza-gaia-backend.md) records the local Gaia backend and catalog decision.

[Phase 0 evidence](../phase-0.md) covers the hinted ASTAP probe. The [active plan](../../astro_mosaic_python_first_architecture_en.md) defines the full chain and its acceptance checks.
