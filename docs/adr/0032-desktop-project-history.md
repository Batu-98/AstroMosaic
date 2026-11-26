# ADR-0032 - Use immutable project values for desktop edit history

- **Date** 2026-11-26
- **Status** Accepted for Phases 9A through 9C.

## Decision

The main window reads its current `MosaicProject` from a Qt-free history cursor. Every accepted project change records an operation label and a new value. Unchanged panels, masks and settings are shared between values. The routine foreground check for newly added panels completes the Add Panels entry from its original job input. An explicit foreground check records its own entry when it changes the project.

Save and Save As advance the existing saved-value checkpoint after successful publication. Dirty state compares project values so that navigation can return to a clean checkpoint. New, Open and Close start with empty history when the transition succeeds. The history records project metadata and references in memory. The manifest stays at its existing schema version.

Restoring a project refreshes the main window and requests fresh panel inspection. The renderer and export code continue to consume project values through their existing interfaces. [Delivery stages](../phase-9.md#delivery-stages) · [Project persistence](0012-project-manifest-and-render-worker.md)

## Editor drafts

The mask and terrain dialogs each use a local cursor over immutable values. A mask entry stores the labels of the bounded source grid when a stroke ends or Reset Edits changes the draft. A terrain entry stores a tuple of observations after a completed pair, move, removal or flag change. The next fit derives new residuals and acceptance from the current tuple, model and anchor. Restoring points clears the previous fit and disables Apply until the next accepted fit.

Applying the draft passes one result to the project cursor. Closing or rejecting the editor discards its draft. The dialog owns its shortcut actions so project history is independent of mask and point edits in progress. [Mask geometry](0014-source-coordinate-mask-grid.md) · [Terrain registration](0023-terrain-control-point-registration.md)

## Worker results and retention

The window advances a revision counter for a new session, accepted project change or history movement. Workers use the captured revision at delivery, even when navigation returns to an equal project. Mutating jobs hold history controls and publish only their accepted values. File references are checked when the UI refreshes and again by readers before use.

Each cursor counts immutable values by identity and keeps up to 100 steps or 8 MiB. The latter includes the active value while the saved checkpoint is kept independently. Oldest steps are evicted first. A change whose before and after values together exceed the remaining limit still applies. The Undo control reports the limit if that change cannot be retained. [Measurements and replay](../phase-9.md#9c-worker-and-retention-verification)
