# Agent Instructions

These rules apply to the whole AstroMosaic project. Keep development focused, understandable, and easy to continue.

## 1. Language and Plan

- Write all project Markdown, code identifiers, comments, logs, and default UI text in English. Conversation may follow the user's language.
- Follow [the Python-first plan](astro_mosaic_python_first_architecture_en.md), revision 3.9. The earlier .NET/Avalonia plan is historical.
- Use the plan for detailed technical requirements and phase acceptance criteria. Follow explicit owner instructions and keep affected documentation consistent.

## 2. Before Starting

- Read this file, the latest state in [progression.md](progression.md), and relevant entries in [questions_open_topics.md](questions_open_topics.md).
- Check the relevant plan sections, decisions in `docs/adr/`, and actual project files. Preserve existing user changes.
- Choose a small, clear task within the requested scope and identify how to check its result.

## 3. Working Style

- Follow the planned phases and build useful functionality in small steps.
- Prefer simple solutions. Add abstractions, dependencies, and optimizations only when needed.
- Make routine, reversible decisions independently. Ask when a missing decision materially affects scope or behavior; continue unaffected work.
- Investigate errors instead of hiding them. Record unresolved problems and assumptions promptly.

## 4. Code Structure

- Use the plan's Python scientific stack and PySide6 UI. Keep dependency versions in one authoritative configuration and lock file.
- Keep processing and CLI code independent of Qt and the GPU. The UI calls the processing pipeline; numerical algorithms do not belong in widgets.
- Use clear names, small functions, type hints, and explicit error handling. Avoid side effects such as starting workers or downloading data during imports.
- Keep long operations off the UI thread. Add acceleration only after measuring a real need.

## 5. Image Data and Accuracy

- Preserve original input files. Store corrections and solved WCS separately until export.
- Use float32 image data and float64 geometry where specified by the plan. Preserve valid zero, negative, and above-one values; keep validity masks separate from intensity.
- Keep display stretch separate from scientific processing and export. Respect FITS scaling, units, and metadata.
- Use consistent WCS and coordinate conventions for preview and output. Final rendering samples original data using the composed transformation.
- Apply conservative registration and background corrections that protect stars and faint structures. Follow the plan's numerical and export requirements when implementing these features.

## 6. Resources and Reliability

- Process large images in tiles with explicit memory and worker limits. Avoid full output-sized buffers for every panel.
- Keep CPU processing available. Support progress reporting, cancellation, and cleanup of files, buffers, and workers.
- Target Windows 11 x64 for the initial release. Keep platform-specific behavior in adapters and report support only when tested.
- Save projects safely, keep caches rebuildable, and report failures clearly. Incomplete exports must not appear successful.

## 7. Simple Completion Checks

- Check that the change does what was requested and run the relevant existing tests, if available.
- Open test windows and dialogs on the second monitor when one is available.
- Add a focused test when new behavior or a bug fix needs one. Documentation-only edits need a content and link review, not application tests.
- Report what passed and what could not be checked. Fix failures or record the remaining issue; do not claim unverified success.
- Apply detailed numerical and platform checks when the relevant feature or phase requires them. Mark a phase complete only when its planned criteria are met.

## 8. Keep Records Current

- After each meaningful step and before handoff, append a short entry to `progression.md`: what changed, what was checked, and what comes next. Keep history intact; update the current-state summary as needed.
- Add problems, uncertainties, and missing decisions to `questions_open_topics.md`. Use its existing format and IDs, state the next action, and record the resolution when closed.
- Record significant architecture changes in a short decision record under `docs/adr/`. Routine edits do not need one.
- Finish with a brief summary of changes, checks, and remaining work. Keep records concise and in English.

## 9. Workspace Care

- Keep source images, catalogs, caches, generated output, environments, and secrets out of version control.
- Use open-source software dependencies for supported workflows. Check compatibility and notices before copying third-party code or distributing dependencies, catalogs, and fixtures.
- Do not upload user images implicitly, overwrite unrelated work, or include private data in logs.
