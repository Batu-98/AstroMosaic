# Phase 10A Desktop Reference Baseline

Measured on 2026-11-27 with AstroMosaic `0.1.0b28`, source commit `1126dc02ea8985fbc73789157bb34de6b85055d0`, PySide6 6.12.0 and Windows 11 Pro x64 build 26200. The test workstation has an Intel Core i5-14600K and an NVIDIA GeForce RTX 4070. The native probes used the secondary Windows display, which reported 1920 × 1080 at 100%. Higher scales used `QT_SCALE_FACTOR` on the same display. The large-text case supplied a 14 pt system font to the existing theme code. [Phase 10 acceptance plan](phase-10.md#10a-reference-layout-and-baseline)

## Workspace measurements

The reference outer window covers 1920 × 1032 physical pixels, allowing 48 physical pixels for the taskbar. All dimensions in the table are Qt logical pixels. Preview dimensions refer to the canvas, including its letterbox area. The table column count includes only columns visible in full.

| Scale and canvas DPR | Logical work area | Logical client | M17 canvas, command open | M17 canvas, command hidden | Overview columns |
| --- | --- | --- | --- | --- | ---: |
| 100%, 1.0 | 1920 × 1032 | 1920 × 1001 | 884 × 598 | 884 × 793 | 9 |
| 125% simulated, 1.25 | 1536 × 826 | 1536 × 801 | 702 × 391 | 702 × 587 | 7 |
| 150% simulated, 1.5 | 1280 × 688 | 1280 × 667 | 581 × 245 | 581 × 441 | 6 |

Full HD used 12 pt body text at all three scales. CPU crop editing retained the corresponding canvas size at each scale. At 100%, the expanded command dock occupied 189 logical px and hiding it recovered 195 logical px of canvas height. The native OpenGL canvas matched CPU for the settled M17 preview at 100%. The matching portable launcher checksum passed. Its Windows UI Automation record covers all three scales and maximize-on-launch. A new portable CPU replay at simulated 125% reproduced the 875 × 485 physical px preview surface, crop editing and compact reflow. Use the source probe above for exact 10B size and timing comparisons because it uses the same window setup and measures the canvas. [Portable results](windows-release.md#verification-status)

| Compact client | Scale and body text | M17 canvas with command open | Fully visible Overview columns | PA4 scroll reached |
| --- | --- | --- | --- | --- |
| 630 × 650 | 100% or simulated 125%, 12 pt | 586 × 100 | Panel, Sky, WCS, Solve result, Weight, Band | 23 of 23 rows |
| 800 × 650 | Simulated 150%, 14 pt | 756 × 100 | Panel, Sky, WCS, Solve result, Weight, Band | 23 of 23 rows |

Each compact layout showed one complete M17 panel row. The empty workspace prompted for source panels. With a preview job active, the status, progress and **Cancel Job** were visible. The crop preview showed the editable rectangle and the **Use Auto Crop**, **Apply Crop** and **Cancel** controls. PA4 used its unaligned manifest to exercise table scrolling. M17 used the saved 1024 × 1320 TAN grid and two real 2MASS FITS tiles with embedded WCS. [M17 fixture](application-tests.md#fixtures) · [PA4 fixture](phase-7.md#real-data-and-acceptance-measurements)

With a settled M17 preview, hiding and showing the dock started two adaptive preview jobs at each scale. The Full HD to compact and back sequence started two at 100% and zero at 125% and 150%. Each resize settled before the next. These counts exclude the explicit Build Preview and Edit Crop actions. For 10B, a same-size view round trip with a valid settled image starts zero jobs. A size change can start one adaptive refresh after a burst if the current preview crosses the existing size threshold.

## Keyboard and response

The M17 forward Tab cycle entered the table from **More**, then reached **Auto Frame**, **Edit Crop**, the mosaic canvas, preview controls, layer and export actions, the command transcript and entry, the working folder and the panel controls before returning to the table. Reverse traversal completed the same cycle in reverse. **=** zoomed the canvas, **Home** returned to Fit View, and **Esc** cancelled crop editing. Space activated the focused **Cancel Job** button on all eight busy trials per run. A temporary `Ctrl+Shift+F` shortcut received the key from the panel table, the command entry and the active crop canvas without conflicts. Use it for **Preview Focus Mode** in 10B.

| Native source run | Idle zoom, max of 12 | Busy cancellation feedback, max of 8 | First Build Preview feedback |
| --- | ---: | ---: | ---: |
| CPU, 100% | 2.06 ms | 9.04 ms | 13.96 ms |
| CPU, 125% simulated | 2.89 ms | 13.75 ms | 13.65 ms |
| CPU, 150% simulated | 1.38 ms | 14.27 ms | 15.77 ms |
| OpenGL, 100% | 3.00 ms | 40.67 ms | 192.00 ms |

Timing starts at input dispatch or button activation and ends when Qt first delivers a paint event to the changed canvas or status label. It measures application feedback up to paint dispatch. OS compositor latency, display scanout, and worker completion are outside that interval. The initial OpenGL feedback includes backend setup. An earlier OpenGL capture on this workstation took 350 ms to reach the same feedback.

**10B response gate.** Use the same workstation and fixture with the expanded Command Panel and at 100% plus both compact sizes. After two warm-up attempts, record 20 alternating pointer or keyboard view switches and focus-mode toggles, first idle, then while a real preview or solve job is active. Measure the first paint showing the selected view, focus mode or action feedback. Require P95 at or below 50 ms idle and 100 ms busy, with no sample above 200 ms. Opening or collapsing the Command Panel uses the same idle target. Record job counts, selection, crop draft validity and the number of attempts that changed the project revision or Undo history. Track first feedback for new work separately using a 400 ms target and report completion times separately.

## Dedicated view sketches

Full HD uses a labeled left menu and one content view at a time. At 100% scaling, a 120 px menu and up to 48 px for the gap and content margins leave 1752 px, or 91% of the 1920 px workspace, for the preview canvas. Treat these as layout budgets. Measure the final canvas and dock against the 10B acceptance criteria.

```text
Panels at Full HD                      Preview at Full HD
┌─────────┬──────────────────────┐    ┌─────────┬──────────────────────┐
│ Panels  │ Add  Settings  Solve │    │ Panels  │ Layer  Band  Build   │
│ Preview │ Panel table          │    │ Preview │ Mosaic canvas        │
│         │                      │    │         │ Fit  Crop  Export    │
├─────────┴──────────────────────┤    ├─────────┴──────────────────────┤
│ Expand command  Status  Cancel │    │ Expand command  Status  Cancel │
└────────────────────────────────┘    └────────────────────────────────┘
```

At both compact sizes, the left menu can use a slimmer labeled rail. Size it to the selected font. Keep **Add Panels**, **Plate Solve**, **Build Preview** and job cancellation in view when applicable. Put secondary actions under **More** or on a second row. Keep one complete table row and horizontal scrolling at both sizes. Use the six priority columns as the first columns after reflow. Put crop actions beside the canvas and keep active crop guidance reachable without the command transcript.

```text
Panels at 630 / 800                    Preview at 630 / 800
┌───────┬────────────────────┐        ┌───────┬────────────────────┐
│Panels │ Add  Solve  More   │        │Panels │ Layer  Band         │
│Preview│ Scrollable table   │        │Preview│ Build  Crop  More   │
│       │                    │        │       │ Canvas and Fit     │
├───────┴────────────────────┤        ├───────┴────────────────────┤
│ Command toggle  Cancel    │        │ Command toggle  Cancel    │
│ Status or progress text   │        │ Status or progress text   │
└───────────────────────────┘        └───────────────────────────┘
```

Use Up and Down to move between the two navigation items, Enter or Space to switch, and Tab to reach the last valid control in the selected view. Shift+Tab returns to the menu. The selected item retains a visible non-color cue and an accessible selected state.

```text
Preview Focus Mode
┌───────┬─────────────────────────────────┐
│Panels │ Layer  Band         Exit focus  │
│Preview│                                 │
│       │          Mosaic canvas          │
│       │                                 │
│       │ Fit  Crop                       │
├───────┴─────────────────────────────────┤
│ Job status and progress      Cancel Job │
└─────────────────────────────────────────┘
```

Preview Focus Mode uses the same controls at compact widths and wraps the toolbar when needed. It hides the command dock and restores its preceding state on exit. Select **Panels**, open **Command Panel**, or use **Ctrl+Shift+F** to exit. Verify the path from the compact expanded transcript to Cancel during work, including a keyboard-only pass and both themes in 10B.

## Outline accuracy and resource limits

The probe used detector boundaries at −0.5 through size −0.5 in zero-based pixel-center coordinates and compared candidate segments with 4097 projected samples per edge. The dense reference calls Astropy's high-level WCS API independently. Keep M17 for the TAN control, the real PA4 pair with two SIP sidecars on a ZEA grid for the larger case, and SKY-07 as the controlled SIP and RA-wrap case. PA4 uses its saved 1460 × 1531 grid with the projection explicitly set to ZEA for this probe. SKY-07 uses its saved 1260 × 750 ZEA grid. [PA4 SIP verification](phase-36-results.md#owner-wide-field-tiffs) · [SKY-07 fixture](application-tests-extension.md#acceptance-by-case)

| Case | Maximum output-pixel deviation, 17 / 33 / 65 samples per edge | Max projection time at 33 samples per edge | Peak Python-traced allocation at 33 |
| --- | --- | ---: | ---: |
| M17 TAN | 0.000003 / 0.000001 / <0.000001 | 2.24 ms | 31.2 kB |
| PA4 SIP to ZEA | 0.138537 / 0.034657 / 0.008665 | 1.07 ms | 28.0 kB |
| SKY-07 SIP to ZEA | 0.062056 / 0.015519 / 0.003880 | 1.11 ms | 28.0 kB |

**10F accuracy gate.** Use 33 samples per edge as the starting density. Compare the displayed polyline with dense reference points in the same view transform. Require a maximum of 1 device px in Fit View at all three reference scales and in the visible portion at 1:1. Run the independent reference with a nonzero crop origin, rotated output, fitted source shifts and an RA-wrap crossing. Apply clipping at the grid edges before hit testing. Check that a nonfinite or singular edge is reported as unavailable and leaves the other panels selectable.

**10F resource gate.** Cap each outline at 1024 vertices and each request at 32,768 vertices and 8 MiB of incremental working memory, bounded further by the project working limit. Require the prepared-geometry part to finish within 100 ms in each two-panel reference and within 200 ms on a replay with at least 20 valid panel mappings using the same real WCS inputs. Use a 200 ms work budget and check cancellation between bounded batches. Report outlines that cannot meet accuracy within the cap. Measure the production allocations and end-to-end work separately from this Python-only, already-open WCS probe. Apply the 10B response gate to selection, pan and zoom. These inputs and limits are fixed for 10F verification. [Outline topic](../questions_open_topics.md#q-037---sky-panel-outline-accuracy-and-resource-bounds)

## Reproduce

Use the pinned local fixtures and the locked environment at the baseline commit. When replaying from a newer checkout, set `$Phase10Python` to an interpreter with beta 28 source installed from the recorded commit. The native probe writes `baseline.json` and captures the empty, busy, M17, crop, compact and scrolled states in each fresh output directory. Use the second monitor when present. The outline probe prints the candidate metrics without rendering or editing inputs.

```powershell
$Phase10Python = (Resolve-Path '.venv/Scripts/python.exe').Path
$env:OPENBLAS_NUM_THREADS = '1'
$env:QT_SCALE_FACTOR = '1'
& $Phase10Python tools/phase10_workspace_baseline.py --cpu --output output/phase10a/replay-cpu-100
& $Phase10Python tools/phase10_workspace_baseline.py --output output/phase10a/replay-gl-100
$env:QT_SCALE_FACTOR = '1.25'
& $Phase10Python tools/phase10_workspace_baseline.py --cpu --output output/phase10a/replay-cpu-125
$env:QT_SCALE_FACTOR = '1.5'
& $Phase10Python tools/phase10_workspace_baseline.py --cpu --compact-text 14 --output output/phase10a/replay-cpu-150
& $Phase10Python tools/phase10_outline_baseline.py data/application-tests/sky01-m17-atlas/project.astromosaic
& $Phase10Python tools/phase10_outline_baseline.py data/application-tests/owner01-pa4/pair-20-21.astromosaic --zea
& $Phase10Python tools/phase10_outline_baseline.py data/application-tests/extended/sky07-wide-sip/project.astromosaic
```

For a manual replay, open M17 with the dock expanded, build the preview, enter and cancel crop edit, hide and reopen the dock, then resize to compact and back. Reopen the unaligned PA4 manifest at compact width and scroll to the last row. Watch the active status and try Space on **Cancel Job** during a new M17 preview. Compare the dedicated views with these actions in both themes and in the portable workflow. [Phase 10 acceptance](phase-10.md#10h-windows-acceptance-and-handoff)
