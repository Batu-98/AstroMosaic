# Phase 9 - Desktop undo and redo

**Status** In progress. Stages 9A through 9C have local Windows verification. The 9D export and portable acceptance gate is next.

## Starting point

The desktop already compared the current `MosaicProject` with its saved state for discard prompts. Panel edits, accepted dialogs and worker completions supplied new project values. Phase 9A uses those same values for the session history cursor and retains the saved-value comparison. [Project window](../src/astromosaic/ui/project_window.py) · [Project model](../src/astromosaic/storage/project.py) · [History decision](adr/0032-desktop-project-history.md)

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

## 9A desktop edit inventory

| Entry point | History behavior |
| --- | --- |
| `_add_paths` from Add Panels or `session add` | One **Add Panels** entry for all new files. The automatic foreground check completes that entry. Duplicate and failed adds preserve redo. |
| `_remove` and `_relink_panel`, including `session relink` | **Remove Panel** and **Relink Panel** retain panel order, metadata, saved foreground and placement values. |
| `_update_panel` from table edits, Panel Settings or `_finish_mask_editor` | **Change Panel Settings** for a table edit or accepted settings dialog. **Edit Sky Mask** for applying or removing an attachment. Brush and horizon gestures stay in the mask dialog. |
| `_settings`, `_set_auto_frame`, `_adopt_preview_grid`, `_apply_crop` | **Change Mosaic Settings**, **Change Sky Framing**, **Use Preview Grid** or **Apply Crop**. Session preview grid and grid adoption commands use the same handlers. |
| `_review_terrain_points` and `_composition_settings` | **Apply Terrain Alignment** for an accepted fit and **Change Composition Settings** for accepted placement or seam parameters. Point operations stay in the terrain dialog. |
| `_finish_foreground_check`, `_finish_plate_solve`, `_finish_layer_job` | **Check Foreground**, **Apply Plate Solve**, **Align Foreground** or **Apply Placement Proposal** for changes that reach the active project. Worker revision and reference replay acceptance is tracked in 9C. |
| `_new_project`, `_open_project`, `_save_project`, `closeEvent` | Lifecycle and saved checkpoint. Successful New, Open and Close clear the old history. Save retains it. Failed reads or writes and rejected discard prompts preserve the active session. |
| View and job controls, application settings, and export commands | Selection, pan, zoom, display stretch, overlap highlighting, preview resolution and draft movement affect the view. Inspection and render jobs supply transient results. Preferences and terminal recall have their own lifetime. Export writes a file and adds no project entry. |

All committed project changes use the same history path so a later undo restores a complete earlier value. The desktop regression covers the 9A panel gate, including the foreground result, saved checkpoint, rejected discard prompts, failed open and save, alternative redo shortcut and native text editing. [History regression](../tests/integration/test_desktop_project_history.py)

## 9B editor history verification

- The Sky Mask dialog groups a brush drag or horizon trace into one step. Undo and Redo restore the three label values and preserve the corresponding sky fingerprint. Reset Edits restores the starting labels and can itself be undone. Cancel discards the draft while keeping any project redo available. In the attached FITS control, project Undo restores the external mask reference and its validated WCS sidecar. Redo restores the authored labels and the sidecar's invalid status. The source image, external mask and sidecar bytes match throughout. [Mask and external WCS regression](../tests/integration/test_desktop_project_history.py) · [Horizon replay](../tests/integration/test_desktop_project.py)
- The terrain editor restores point coordinates, order and flags. It records a new pair once both observations are present. Oxford's real similarity workflow reconstructs the same accepted fit after redo. On the real Paranal project, undo restores the prior terrain evidence and composition placement and re-enables composition export. Redo restores the new alignment and requires a new placement. [Terrain editor regressions](../tests/integration/test_terrain_editor.py)
- The sky photo test checks an interactive crop and one accepted profile, exposure and brightness edit against the captured project values. History navigation clears the outdated crop overlay and rebuilds the preview at the restored dimensions. Preview and export wait for current inspection metadata and band availability. [Crop and photo settings replay](../tests/integration/test_desktop_project.py)

## 9C worker and retention verification

Each project value change and session transition advances a revision counter. Undo and Redo also advance it. Inspection, preview and detail completions require their launch revision. Mutating jobs hold history controls until their UI-thread completion. A normal preview can be cancelled by history navigation. A partial plate solve attaches its completed results once, and replay uses those saved file references.

The Windows regression cancels after one accepted WCS, verifies both sidecar identity and bytes through Undo and Redo, and checks solver call counts. Cancelling an attempt that produces zero attachments preserves the redo branch. Removing a recorded sidecar before Redo produces the existing Link and WCS diagnostics and disables sky preview and export. Returning the file allows a fresh inspection to recover the controls. [Plate solve regression](../tests/integration/test_desktop_plate_solve.py)

Each history retains up to **100 steps** or **8 MiB** of accounted immutable values. The project and an open editor each use this limit. Accounting counts shared values once, including masks, and includes the active value in the history. The saved checkpoint remains independently available for dirty-state comparison. History evicts the oldest steps first. If even the newest pair exceeds the budget, the edit applies and the Undo control displays **history limit reached**. A single active value can exceed the budget.

| Windows workload | Accepted edits | Steps retained | Accounted bytes | Python allocation peak |
| --- | ---: | ---: | ---: | ---: |
| Six PA4 panels, cycling manual EV | 240 | 100 | 637,226 | 174,328 B |
| Mask draft on a 384 × 384 label grid | 160 | 55 | 8,262,589 | 8,568,146 B |
| Applied labels on a real Paranal panel, 384 × 323 grid | 80 | 65 | 8,342,834 | 8,509,956 B |

The draft retained 23,754,814 accounted bytes with an unrestricted cursor. Python allocation peaks were measured with tracemalloc after opening the real project manifests. Windows reported a 159,358,976-byte process working-set high water across both bounded and unrestricted workloads. Releasing the bounded mask draft left 360 B of traced allocations. The tests cover entry and byte eviction, branch replacement, oversized edits, failed save, dirty recovery and closing before renaming a source. [Cursor tests](../tests/integration/test_edit_history.py) · [Desktop history regression](../tests/integration/test_desktop_project_history.py)
