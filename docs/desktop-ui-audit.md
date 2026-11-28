# AstroMosaic desktop UI audit

November 27, 2026. The first pass covers the main workspace, panel table, mosaic viewport, Mosaic Settings, Panel Settings and Plate Solve Settings. The populated panel table's Tab loop was the first repair target. The audit also found pointer-only viewport operations, unnamed settings fields and a height constraint when the Command Panel is open. [Qt UI Design audit criteria](https://doc.qt.io/agentictools/skills/qt-ui-design/#5-audit-instructions) · [Desktop workflow](guide.md#run-the-desktop-app)

Beta 21 fixed the table's Tab loop and added keyboard pan, zoom and fit. Beta 22 gave the ICC, WCS and FITS mask controls specific accessible names and matched the visual group order in Plate Solve Settings. Beta 23 added keyboard movement and resizing for the live crop. Beta 24 fits the workspace into an 800 × 650 logical px window with the Command Panel open under the tested conditions. Beta 25 makes disabled controls, selected panel rows and the workspace divider distinguishable by shape. Beta 26 scales desktop text and brings Solve result next to WCS in Overview. Beta 27 localizes decimals, guides the empty workspace and completes the Narrator walkthrough. [Desktop controls](guide.md#run-the-desktop-app) · [Windows verification](windows-release.md#verification-status) · [Q-036](../questions_open_topics.md#q-036---desktop-keyboard-access-and-compact-layout)

## Critical findings

### Tab navigation wraps inside the panel table

On the two-panel M17 project, Tab on the last Overview cell returned to the first cell. Shift+Tab from the first cell returned to the last. Ctrl+Tab also stayed in the table. This interrupts keyboard traversal from the panel controls to the preview. In a temporary widget probe, `setTabKeyNavigation(False)` let Tab move to **Auto Frame** and Shift+Tab move to **More panel actions**. Arrow navigation, Space on **Sky**, and F2 on **Weight** still worked. The probe restored the project with Undo. [Panel table initialization](../src/astromosaic/ui/panel_table.py) · [Qt tab navigation property](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QAbstractItemView.html#PySide6.QtWidgets.QAbstractItemView.tabKeyNavigation) · [Keyboard trap criterion](https://www.w3.org/WAI/WCAG22/Understanding/no-keyboard-trap.html)

### Preview pan and zoom require a pointer

The CPU and OpenGL canvases had `NoFocus`. Mouse wheel zoom and drag pan changed the image rectangle. Arrow and plus/minus keys had no corresponding action, while Space on **Fit View** reset the view. The interactive crop uses pointer handles as well. **Mosaic Settings → Crop (x, y, width, height)** accepts numeric bounds through the keyboard, and the draft's **Cancel** button works with Space. Add focus and shared keyboard controls for viewport movement and zoom. Consider exposing the numeric bounds in the crop draft for adjustment against the live preview. [Viewport controls](../src/astromosaic/ui/sky_viewport.py) · [Crop workflow](phase-3c.md#adaptive-framing-and-interactive-crop) · [Keyboard criterion](https://www.w3.org/WAI/WCAG22/Understanding/keyboard.html)

### Attachment and profile controls have incomplete accessible names

Qt's accessibility interface returned empty names for **WCS sidecar** and **FITS sky mask** in Panel Settings and for the enabled **ICC file** path in both Photo tabs. The two attachment rows also expose identical **Browse…** and **Clear** button names. Standard single-widget form rows exposed their labels, and Plate Solve Settings exposed distinct names for its equivalent path controls. Use that existing path-row convention for the fields and buttons, then check the names through Windows Narrator. [Settings path rows](../src/astromosaic/ui/project_settings.py) · [Solver path rows](../src/astromosaic/ui/plate_solve_settings.py) · [Accessible name criterion](https://www.w3.org/WAI/WCAG22/Understanding/name-role-value.html)

## Warnings

### The Command Panel limits the workspace on short displays

In the initial audit, the test requested a 14 pt application font at 150% simulated Qt scaling. An `800 × 650` logical px resize produced an `800 × 761` window with the dock open. Closing the dock through **Tools → Command Panel** allowed `800 × 650`, with a minimum height of 536 logical px. At 100% scale in a fixed `1140 × 794` window, closing the dock increased the canvas height from 188 to 309 logical px. A 1920 × 1080 screen at 150% offers at most 720 logical px of height before the taskbar. [Workspace and dock creation](../src/astromosaic/ui/project_window.py) · [Command Panel sizing](../src/astromosaic/ui/command_panel.py) · [Qt high DPI](https://doc.qt.io/qtforpython-6/overviews/qtdoc-highdpi.html)

For the beta 24 comparison, the native Qt check explicitly verified that each command input used a 14 pt font. At 150% simulated Qt scaling, beta 23 needed 842 logical px idle, 884 while building the preview and 874 during crop editing. Beta 24 held the requested 800 × 650 in all three states on the M17 project. The preview canvas, two transcript lines, command entry and job controls remained visible. [Compact workspace verification](../progression.md#2026-11-27---desktop-accessibility---fit-the-command-panel-on-short-displays)

### Plate Solve Settings tab order skips the visible Gaia group

From **ASTAP → Database**, Tab went to **Solve Limits → Per panel**. **Gaia DR3** appeared in the focus sequence after the footer's **Cancel**, although its group appears between ASTAP and Solve Limits. Escape dismissed the dialog. Build the groups in visual order or set an explicit tab order. [Solver settings layout](../src/astromosaic/ui/plate_solve_settings.py) · [Focus order criterion](https://www.w3.org/WAI/WCAG22/Understanding/focus-order.html)

### Some control states are difficult to distinguish

Enabled **Add Panels…** and disabled **Panel Settings…** and **Build Preview** used the same button fill and matching text color samples in both empty-state captures. The selected-row fill against the table base measured 2.19:1 in dark and 1.31:1 in light. A simulated deuteranopia transform on those palette pairs gave 2.13:1 and 1.33:1. The 3 px splitter handle measured 1.71:1 and 1.46:1 against the window. Enabled button text exceeded 10:1 in both themes, and the focused **Fit View** button showed a visible outline. Add a distinct disabled presentation, a shape or outline for row selection, and a clearer splitter grip. [Shared palette and styles](../src/astromosaic/ui/appearance.py) · [Non-text contrast criterion](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html) · [Color vision simulation, Table A.1](https://www.inf.ufrgs.br/~oliveira/students_dissertations/Masters/Gustavo_Machado_Masters_thesis_UFRGS_2010.pdf#page=74)

Beta 25 gives disabled buttons and selectors dashed borders, marks the selected panel row with two lines, and adds a three-mark grip between the panel table and preview. In native M17 captures at simulated Qt scales of 100% and 150%, the lines followed arrow-key selection and the divider continued to resize both panes. The table reports the lower score when a line touches both the selected fill and the adjacent row. [Shared styles](../src/astromosaic/ui/appearance.py) · [Panel delegate](../src/astromosaic/ui/panel_table.py) · [Deuteranopia simulation method](https://profs.ic.uff.br/~laffernandes/content/publications/journal/2009_tvcg_15%286%29/machado_oliveira_fernandes-tvcg-15%286%29-2009-corrected.pdf)

| Sample | Dark | Light | Dark with simulated deuteranopia | Light with simulated deuteranopia |
| --- | ---: | ---: | ---: | ---: |
| Disabled Build Preview label against fill | 4.98:1 | 5.57:1 | 4.95:1 | 5.63:1 |
| Selected row line | 4.05:1 | 4.98:1 | 3.99:1 | 5.17:1 |
| Divider grip against divider fill | 4.73:1 | 4.06:1 | 4.55:1 | 4.26:1 |

### Desktop readability falls below the skill's body text guideline

The standard Segoe UI setting was 10 pt, approximately 13.3 logical px at 96 DPI. Section headings use a fixed 16 px style and stayed at that size when the app font was raised to 14 pt. At 630 logical px width, five of the nine Overview columns fit fully before scrolling, and **Solve result** sat at the far right. At 1140 logical px width all nine fit. Review type scaling and the columns needed to understand a panel's current state at narrow widths. [Theme font settings](../src/astromosaic/ui/appearance.py) · [Table views and widths](../src/astromosaic/ui/panel_table.py) · [Qt UI Design typography](https://doc.qt.io/agentictools/skills/qt-ui-design/#12-typography-scale-desktopweb)

Beta 26 uses a 12 pt minimum for body text, including table cells and the command transcript. The headings and job percentage follow a 1.125 ratio and measured 13.5 pt with the 12 pt body and 15.75 pt with the 14 pt body. At both 630 × 650 with 12 pt and 800 × 650 with 14 pt at 150% simulated Qt scaling, **Panel**, **Sky**, **WCS**, **Solve result**, **Weight**, and **Band** fit without horizontal scrolling, with one complete row visible. All nine Overview columns fit at 1140 logical px in the tested setup. Long panel filenames can still use ellipsis and the existing full-path tooltip. [Qt font sizing](https://doc.qt.io/qt-6/qfont.html) · [Typography verification](../progression.md#2026-11-27---desktop-accessibility---scaled-text-and-prioritized-panel-status)

### Decimal input assumes an English decimal point

Setting Qt's default locale to `tr_TR` and entering `1,5` in **Pixel scale** raised Python's float conversion error. The visible labels are English and the field gives no input-format hint. Decide whether numeric entry should follow the OS locale. If it does, keep that parsing at the UI boundary and retain the current project serialization format. [Mosaic Settings parsing](../src/astromosaic/ui/project_settings.py) · [Qt locale API](https://doc.qt.io/qt-6/qlocale.html)

Beta 27 formats and parses editable decimals with the Qt locale in Mosaic Settings, Panel Settings, Composition Settings and the panel table. The M17 replay accepted `1,5` and `2,25` in Turkish and `1.5` and `2.25` in English. Both saved the same JSON numbers. Grouped amounts are rejected with an example using the correct decimal separator. [Desktop number input](guide.md#run-the-desktop-app)

## Opportunity

The empty canvas says **Build a sky preview.** while **Build Preview** is disabled. The footer already gives the correct prerequisite. Give the canvas the same next step and visibly emphasize **Add Panels…** while the project is empty. Once preview input is ready, make the next available action clear. [Empty canvas](../src/astromosaic/ui/sky_viewport.py) · [Workspace status and actions](../src/astromosaic/ui/project_window.py)

Beta 27 starts with the **Add Panels…** prompt and button highlight. The prompt follows metadata checks and available preview actions. The highlight moves to **Build Preview** when the inputs are ready and to **Export** after a preview is available. The empty canvas uses a readable text control. [Windows workflow results](../progression.md#2026-11-27---windows-handoff---verified-beta-27-desktop-audit-workflows)

## Verification and first repair

- The official `qt-ui-design` skill version 1.1 and its BSD 3-Clause notice matched upstream revision `dce029506599e3a01bd628d106b005b37c17f525` byte for byte. A fresh Codex skill scan reported it enabled at user scope. [Pinned skill](https://github.com/TheQtCompanyRnD/agent-skills/blob/dce029506599e3a01bd628d106b005b37c17f525/skills/qt-ui-design/SKILL.md) · [Codex skill locations](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)
- Native source checks used Windows 11 Pro x64, Qt 6.12.0, one display, CPU and OpenGL previews of the public 2MASS M17 fixture, both appearance themes, and simulated 100% and 150% Qt scaling. The source and dependency files matched the beta 20 build commit. The local development environment supplied beta 19 title metadata. The manifest and referenced images retained their SHA-256 digests. [M17 fixture](application-tests.md#source-credits-and-fixture-limits) · [Beta 20 build verification](phase-9.md#9d-windows-acceptance-results)
- Build Preview showed a status message, progress and Cancel Job at launch. Escape closed all three inspected settings dialogs. The three settings dialogs were inspected at the standard size and with 14 pt app text. The scoped source suite passed eight existing checks covering panel editing, theme persistence, preview resolution, GPU settings, solver settings and crop state. The audited source has no custom UI animations or AI interactions in these surfaces. Physical display transitions, Windows text scaling and Narrator remain outside this source pass.
- Beta 21 confirmed traversal from **More** through the table to **Auto Frame** and back, with arrow navigation, Space and F2 available. Beta 22 verified settings names and bidirectional focus order. Beta 23 verified editing the crop with the keyboard and applying or discarding the draft. Beta 24 verified the compact layout at 800 × 650 with simulated scaling. Beta 25 checked control shapes and contrast in both themes. Beta 26 verified text scaling and keyboard access to the key columns in both narrow layouts. Beta 27 verified locale-aware decimals and closed Q-036. [Resolved topic Q-036](../questions_open_topics.md#q-036---desktop-keyboard-access-and-compact-layout)

### Windows Narrator walkthrough

The beta 27 production launcher was tested with Windows Narrator on Windows 11 25H2. The check compared actual Narrator utterances obtained using its copy-last-phrase command with the focused control names. [Microsoft Narrator speech recap and copy commands](https://support.microsoft.com/en-us/accessibility/windows/narrator/complete-guide-to-narrator)

- Narrator announced Add Panels, the selected M17 file when Tab entered the table, Auto Frame when Tab left it, and Mosaic preview after building the preview. The preview accepted arrow and Home input with Narrator running.
- In Panel Settings, Narrator announced the WCS sidecar and FITS sky mask fields and their named Browse and Clear buttons. It read ICC file and Browse for ICC file in both Photo tabs and Pixel scale in Mosaic Settings.
- Tab moved from Database through Star catalog and Blind index to Per panel in Plate Solve Settings. Shift+Tab returned through the same controls. Narrator announced the focused field or button at each step. Escape closed Plate Solve Settings, Panel Settings and Mosaic Settings. [Beta 27 handoff](../progression.md#2026-11-27---windows-handoff---verified-beta-27-desktop-audit-workflows)
