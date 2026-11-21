# ADR-0022 - Select bands on the saved sky grid

- **Date:** 2026-11-18
- **Status:** Accepted for Phase 5C.

## Decision

Resolve sky membership from explicit panel assignments, embedded filter labels, the declared common fallback, and finally the `Unspecified` default. Discovery verifies the included source references. Save explicit assignments in project manifest version 6 and record the assignment in sky export history. Validate units, layout, masks, and geometry for the selected band and render its members on the saved grid. A band can carry mono or RGB data at its own declared brightness scale.

Use explicit destinations and the existing batch result and cancellation behavior for jobs that need several bands. Each completed file is independently usable. The ordinary layer renderer still applies the common-filter sky contract when a band is unspecified.

## Consequences

The CLI, desktop preview, and desktop export use the same band resolution and validation. Future cross-band color composition or integrated-flux conversion needs a separate calibration contract. [Phase 5C](../phase-5c.md)
