# ADR-0010 Use Seiza for local Gaia DR3 solving

- **Date:** 2026-11-15
- **Status:** Accepted for the Windows Phase 2 reference.

Use the optional Seiza Python bindings with an explicit local Gaia DR3 catalog. The Windows CPython 3.13 wheel accepts centroids from AstroMosaic's masked SEP measurements. It provides hinted solving and indexed blind solving, with deadlines, cancellation, and match diagnostics. Seiza is Apache-2.0. [Upstream project](https://github.com/theatrus/seiza) · [Locked wheel version](https://pypi.org/project/seiza/0.48.2/)

Catalog setup is explicit. Keep the Gaia catalog and blind index from one verified bundle together and record their provenance. WCS reuse is first in the chain, followed by Gaia DR3, hinted ASTAP, and blind ASTAP. Store successful geometry in a separate sidecar tied to the source and optional mask revision. [Offline solver order](0005-offline-solver-chain.md) · [Windows evidence](../phase-2.md#offline-solvers)
