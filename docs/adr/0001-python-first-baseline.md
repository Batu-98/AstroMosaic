# ADR-0001: Use the Python-First Development Baseline

- **Date:** 2026-11-15
- **Status:** Accepted for development guidance; compatibility choices remain subject to Phase 0 evidence.
- **Basis:** The explicit supersession statement in the supplied revision 3.0 plan. This record identifies the existing baseline; it does not claim a new owner decision or completed implementation.

## Context

The workspace contains a revision 2.0 .NET/Avalonia design and a revision 3.0 Python-first design. Leaving their relationship implicit could cause development agents to select incompatible stacks or implement both.

## Decision

Use [astro_mosaic_python_first_architecture_en.md](../../astro_mosaic_python_first_architecture_en.md) as the active architecture. Build a headless Python scientific engine with a separate PySide6 desktop layer, following its first-preference choices and phase gates.

The earlier `astro_mosaic_revised_architecture_en.md` is historical design context. Do not activate its .NET/Avalonia stack alongside Python/PySide6.

Use root-level `AGENTS.md` for agent working rules, `questions_open_topics.md` for unresolved topics, and `progression.md` for concise work/verification history. All project Markdown is English.

## Alternatives

- **Continue the .NET/Avalonia baseline:** Not selected because revision 3.0 explicitly replaces its infrastructure choices.
- **Maintain both stacks:** Not selected; it conflicts with the focused v1 implementation strategy.

## Consequences

- The initial scope remains monochrome, same-filter linear FITS mosaics with Gnomonic output and a CPU reference path.
- Exact Python/dependency versions, runtime compatibility, numerical semantics, solver deployment, and distribution details are still open; see [the topic register](../../questions_open_topics.md).
- A later material architectural change receives a new ADR that states what it supersedes and updates affected current guidance. Historical documents remain traceable.

## Validation

The supplied revision 3.0 document's metadata, Sections 1 and 4.1, and milestone table were inspected during preparation. No application runtime, scientific accuracy, packaging, or performance validation was performed for this ADR.
