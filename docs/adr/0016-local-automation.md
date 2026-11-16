# ADR-0016 - Use the CLI for local automation

- **Date:** 2026-11-16
- **Status:** Proposed for Phase 4.

## Context

The Windows console package already provides image inspection, offline solving, and sky mosaic export. Saved projects contain the settings and layer state that agents and scripts need to reproduce a desktop export. The engine already exposes headless project loading and rendering.

## Decision

Use the existing CLI as the supported interface for local agents and scripts. Reuse the `.astromosaic` manifest and the headless project job operations. Give scripts a versioned output contract and keep the engine's resource budgets, cancellation, and atomic publication in effect.

Use the CLI workflow for the large-mosaic acceptance cases before adding the desktop terminal panel. The panel exposes the same AstroMosaic commands and job results. [Phase 4 stages](../../astro_mosaic_python_first_architecture_en.md#102-phase-4-delivery-stages) · [Terminal scope](../../questions_open_topics.md#q-012---desktop-terminal-scope)
