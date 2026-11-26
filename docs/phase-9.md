# Phase 9 - Desktop undo and redo

**Status** Planned. A user should be able to try a crop, correct a mask or apply a solve, then step backward and forward to the exact project they were editing. History belongs to the open desktop project and lasts for that session.

## Starting point

The desktop already compares the current `MosaicProject` with its saved state for discard prompts. Panel edits, accepted dialogs and worker completions assign new project values in several handlers. Mask reset, crop reset and terminal command recall each serve a narrower purpose. The inspected source has no project-wide history or Undo and Redo actions. Start with these existing mutation paths and the immutable render snapshot contract. [Project window](../src/astromosaic/ui/project_window.py) · [Project model](../src/astromosaic/storage/project.py) · [Project persistence and workers](adr/0012-project-manifest-and-render-worker.md)

## What counts as one edit

| User action | Unit of undo and redo |
| --- | --- |
| Add a selection of panels, remove a panel or relink a source | One action per invocation. Restore panel order, file fingerprints, per-panel settings and the prior relationships to terrain and composition. |
| Accept panel or mosaic settings | One accepted dialog, including all changed fields. Cover sky inclusion, filter, optics, weights, refinement, framing locks, profile, exposure and brightness where the control edits the project. |
| Edit sky labels or terrain points | Within the editor, undo one completed brush stroke, horizon gesture or point operation at a time. Apply commits the resulting mask or accepted terrain fit and its evidence as one project edit. Cancel discards the draft and preserves project redo. |
| Change framing, apply a crop or adjust composition | One edit per committed change. Applying a crop includes its effective grid and locks. Accepting placement or seam settings restores all associated geometry together. |
| Apply computed results | One edit for the changes actually attached by a foreground check, alignment, placement proposal or plate-solve batch. A stopped solve can attach completed panels. Record just those changes, including the previous WCS references. |
| Use desktop session commands | Commands that edit the active project use the same history as their GUI equivalents. For example, selecting a saved framing mode through a preview command counts if it changes the project. |

Pan, zoom, display stretch, selection, draft crop movement, progress and terminal recall stay outside project history. Preferences such as catalog paths retain their application-wide lifetime. Save and Export keep their filesystem semantics. Undoing a project edit never modifies source images, previously written exports or published WCS sidecars. Standalone CLI invocations continue to operate on explicit inputs and saved manifests.

## Delivery stages

### 9A - Project history and first desktop workflow

- Inventory each assignment to the active project, including table edits, session commands and background results. Map it to an action above, a lifecycle transition or a documented exclusion. Use this list to check coverage in 9B and 9C.
- Introduce one Qt-free history model over existing project values with a cursor and an operation label. Route panel add, remove and relink through one desktop commit path first. A rejected, failed or value-identical edit preserves the cursor and redo branch. A successful new edit after undo discards only the abandoned redo branch.
- Provide **Edit → Undo** and **Edit → Redo** with the next operation in the label, for example **Undo Add Panels**. Disable unavailable actions. On Windows support Ctrl+Z, Ctrl+Y and Ctrl+Shift+Z. A focused text field retains its native text editing shortcuts.
- Keep the saved project value as the clean reference. Successful Save or Save As updates that reference and retains history. A failed save leaves the path, reference, cursor and redo availability intact. Successful New, Open and Close release the old session. Cancelling a discard prompt or failing to open a file preserves it.
- **Gate** Add two panels together, save, remove one, undo to the saved state and redo to the dirty state. Undo again, relink through the desktop terminal and confirm Redo is unavailable. Check the title, discard prompt and session status against the same saved value. Reopen the saved file with both actions disabled.

### 9B - Editor gestures and dependent state

- Route remaining synchronous changes through the same commit path. Keep draft history local to the mask and terrain dialogs. Group press-to-release painting and completed point pairs into single steps. A reset that changes the draft is also reversible. Recompute or invalidate terrain fit evidence when restored points change. [Mask editor](../src/astromosaic/ui/mask_editor.py) · [Terrain editor](../src/astromosaic/ui/terrain_editor.py)
- Refresh affected panel rows, band choices, WCS eligibility, foreground validity, crop overlay and export availability after every undo and redo. Reuse the mask fingerprint and the existing preview/export grid rules. Restore a previous external mask reference when undoing its replacement by an authored mask. [Mask grid contract](adr/0014-source-coordinate-mask-grid.md) · [Crop and preview contract](adr/0027-adaptive-sky-preview.md)
- **Gate** Paint two strokes, undo one in the dialog, apply, undo in the main window and redo. Compare the three-label grid and sky fingerprint at each step. Exercise Cancel with an existing project redo branch. Repeat with a terrain point edit and fit, then a crop and multi-field photo settings change. Check the restored point coordinates, fit validity, grid, crop and profile values against captured before/after values.

### 9C - Worker results, references and resource limits

- Apply worker changes once on the UI thread to the session and revision that launched them. Disable project history navigation while a mutating job is active. Discard late inspection, preview and detail results after a revision or session change, including a return to an earlier cursor position. Keep cancellation and window close responsive.
- Store the references and accepted parameters needed to replay an edit. Redoing a solve restores the recorded attachments without running the solver again. Recheck file identity before use. If a referenced file has moved or changed, show the existing missing or stale diagnostic and keep dependent operations ineligible until recovery.
- Share unaffected project values. Count retained history entries and bytes, including editor drafts and mask payloads. Exclude decoded panels, full preview frames, output rasters and open file handles. Measure a multi-panel edit session and a mask-heavy session to set entry and byte limits. Evict the oldest reachable steps at the boundary. Define visible handling for an individual edit larger than the budget and preserve correct save/dirty behavior across eviction. [History budget follow-up](../questions_open_topics.md#q-032---desktop-edit-history-budget)
- **Gate** Cancel a solve after one attachment is available. Undo and redo the resulting batch, compare sidecar identities, verify original file hashes and count solver invocations. Exercise cancellation with zero changes, an obsolete preview completion, a missing sidecar and a failed save. Cross both history limits, branch after eviction and close the project. Record peak memory, retained payloads, released handles and clean-state results.

### 9D - End-to-end Windows acceptance

- Replay a saved real sky project through crop and photo edits, and a mixed project through mask, terrain and composition edits. Capture project fields and independently reopen representative exports at baseline, after editing, after undo and after redo. Compare WCS, coverage and scientific samples with the existing workflow tolerances. Compare photo pixels and profile at matching states. [Application tests](application-tests.md) · [Extended export checks](application-tests-extension.md)
- Verify current and supported older manifests open with empty history. Saving the current state uses the existing manifest schema. Check that a standalone CLI export of the saved state agrees with the desktop export. Exercise shortcuts with main-window, modal-editor, text-field and terminal focus.
- **Gate** Record focused history tests, the existing regression suite, the native Windows CPU and OpenGL replays, and the same changed workflow in the versioned portable build. Report source and packaged results separately. Update the user guide with shortcuts, session lifetime and the measured retention limit before marking the phase complete. [Windows build and verification](windows-release.md)
