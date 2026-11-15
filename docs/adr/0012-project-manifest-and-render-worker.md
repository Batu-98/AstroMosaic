# ADR-0012 - Persist project inputs and render a snapshot

- **Date:** 2026-11-15
- **Status:** Accepted for Phase 3B.

## Decision

Use a UTF-8 JSON `.astromosaic` manifest with an explicit schema version. Store the ordered source paths and fingerprints, optional WCS and mask references, blend weights, calibration declarations, and render and refinement settings. Express paths relative to the manifest when the filesystem permits it. Keep the original images, masks, and solutions in their respective files. A relink must match the saved byte size and modification time, which are also used by the WCS sidecar contract.

Flush a sibling temporary manifest before atomic publication. A first save refuses to replace an existing file, and an explicit save to an existing project uses atomic replacement. Loading a missing input keeps its stored reference available for relinking.

Run each desktop render from an immutable project snapshot on a dedicated Qt thread. Progress crosses to the UI as signals. An ordinary thread-safe event feeds the existing engine cancellation checks. Closing a busy window requests cancellation and lets the event loop continue until the job has released its handles and cleaned up.

See the [desktop workflow](../phase-3b.md) for usage and verification.
