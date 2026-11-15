# ADR-0003: Target Windows First

- **Date:** 2026-11-15
- **Status:** Accepted by the project owner.

## Decision

Use Windows 11 x64 for initial development, testing, and packaging. Defer Linux and macOS validation until the owner requests it and native test resources are available. Keep platform-specific process, path, graphics, and packaging behavior in adapters. The headless engine remains independent of Qt and the GPU.

## Consequences

The [revised plan](../../astro_mosaic_python_first_architecture_en.md) applies Windows validation to the initial milestone gates. The [Phase 0 evidence](../phase-0.md) meets the revised development gate. Clean-machine release validation remains separate. Q-008 in the [topic register](../../questions_open_topics.md) tracks additional platforms.
