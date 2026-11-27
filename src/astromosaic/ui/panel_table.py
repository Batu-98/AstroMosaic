"""Project panel properties and edits for the desktop table."""

from dataclasses import dataclass, replace
from math import isfinite
from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QDateTime,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
    Signal,
)
from PySide6.QtGui import QPainter, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLineEdit,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QWidget,
)

from astromosaic.astrometry.hints import PanelOptics
from astromosaic.storage.project import PanelInspection, PanelSolveOutcome, ProjectPanel

_WIDTHS = {
    "Panel": 180,
    "Sky": 46,
    "WCS": 94,
    "Weight": 68,
    "Band": 75,
    "Focal length (mm)": 133,
    "Camera": 146,
    "Size (px)": 112,
    "Foreground": 125,
    "Sky mask": 110,
    "Link": 115,
    "Solve result": 143,
    "Telescope": 150,
    "Pixel X (µm)": 105,
    "Pixel Y (µm)": 105,
    "Optical X (″/px)": 121,
    "Optical Y (″/px)": 121,
    "Embedded scale (″/px)": 154,
    "File type": 80,
    "Channels": 83,
    "Unit": 90,
    "BITPIX": 70,
    "BSCALE": 75,
    "BZERO": 75,
    "BLANK": 75,
    "Embedded band": 120,
    "Embedded focal (mm)": 149,
    "Embedded X (µm)": 129,
    "Embedded Y (µm)": 129,
    "Suggested foreground": 148,
    "Mask sources": 160,
    "WCS source": 145,
    "Source path": 365,
    "WCS sidecar": 260,
    "Mask file": 260,
    "Bytes": 108,
    "Modified": 160,
}
COLUMNS = tuple(_WIDTHS)
VIEWS = {
    "Overview": (
        "Panel",
        "Sky",
        "WCS",
        "Weight",
        "Band",
        "Focal length (mm)",
        "Camera",
        "Size (px)",
        "Solve result",
    ),
    "Optics": (
        "Panel",
        "Camera",
        "Telescope",
        "Focal length (mm)",
        "Pixel X (µm)",
        "Pixel Y (µm)",
        "Optical X (″/px)",
        "Optical Y (″/px)",
        "Embedded scale (″/px)",
        "Embedded focal (mm)",
        "Embedded X (µm)",
        "Embedded Y (µm)",
    ),
    "Files": (
        "Panel",
        "Link",
        "File type",
        "Size (px)",
        "Channels",
        "Unit",
        "Source path",
        "WCS sidecar",
        "Mask file",
        "Bytes",
        "Modified",
    ),
    "All properties": COLUMNS,
}
_OPTICS = {
    "Focal length (mm)": "focal_length_mm",
    "Pixel X (µm)": "pixel_size_x_um",
    "Pixel Y (µm)": "pixel_size_y_um",
}
_EDITABLE = {"Weight", "Band", *_OPTICS}
_STAGES = {
    "existing-wcs": "Existing WCS",
    "gaia-dr3": "Gaia DR3",
    "astap-hinted": "ASTAP hinted",
    "astap-blind": "ASTAP recovery",
}
_Role = Qt.ItemDataRole
_Index = QModelIndex | QPersistentModelIndex
_ROOT = QModelIndex()


@dataclass
class PanelRow:
    panel: ProjectPanel
    values: dict[str, object]
    detail: str
    linked: bool
    source_linked: bool


def panel_row(
    panel: ProjectPanel,
    info: PanelInspection | None,
    outcome: PanelSolveOutcome | None,
    project_band: str | None,
) -> PanelRow:
    references = panel.references()
    statuses = {role: ref.status() for role, ref in references}
    attention = [f"{role} {value.lower()}" for role, value in statuses.items() if value != "Ready"]
    detail = [f"{role}: {ref.path}" for role, ref in references]
    wcs = info.wcs_status if info else "Checking…"
    if statuses["Source"] != "Ready":
        wcs = "Unavailable"
        info = None
    elif statuses.get("WCS sidecar", "Ready") != "Ready":
        wcs = "Invalid"
    if info:
        detail.append(info.detail)
    result = None
    if outcome:
        result = (
            _STAGES[outcome.stage]
            if outcome.sidecar and outcome.stage
            else outcome.status.replace("-", " ").capitalize()
        )
        if outcome.error:
            detail.append(outcome.error)
        for attempt in outcome.attempts:
            message = f"{_STAGES[attempt.stage]} {attempt.outcome}. {attempt.detail}"
            if attempt.catalog:
                message += f" Catalog {attempt.catalog}."
            if attempt.matched_stars is not None and attempt.rms_arcsec is not None:
                message += f" {attempt.matched_stars} matches, RMS {attempt.rms_arcsec:.2f}″."
            detail.append(message)

    embedded = info.embedded_optics if info else PanelOptics()
    optics = embedded.with_overrides(panel.optics)
    scale_x, scale_y = optics.scales_arcsec()
    descriptor = info.descriptor if info else None
    band = info.filter_name if info else None
    tag = panel.foreground_tag
    foreground = tag.replace("-", " ").capitalize() if tag else "Unchecked"
    if panel.foreground_override:
        foreground += " (manual)"
    mask = "Edited" if panel.source_mask else "Attached" if panel.sky_mask else None
    if mask is None and tag in ("mixed", "uncertain"):
        mask = "Needed"
    source = panel.source
    values: dict[str, object] = {
        "Panel": source.path.name,
        "WCS": wcs,
        "Weight": panel.weight,
        "Band": panel.sky_band(band, project_band),
        "Camera": info.camera_model if info else None,
        "Telescope": info.telescope_model if info else None,
        "Foreground": foreground,
        "Suggested foreground": panel.foreground_suggestion,
        "Sky mask": mask,
        "Link": ", ".join(attention) or "Linked",
        "Solve result": result,
        "Focal length (mm)": optics.focal_length_mm,
        "Pixel X (µm)": optics.pixel_size_x_um,
        "Pixel Y (µm)": optics.pixel_size_y_um,
        "Optical X (″/px)": scale_x,
        "Optical Y (″/px)": scale_y,
        "Embedded scale (″/px)": info.embedded_scale_arcsec if info else None,
        "Embedded band": band,
        "Embedded focal (mm)": embedded.focal_length_mm,
        "Embedded X (µm)": embedded.pixel_size_x_um,
        "Embedded Y (µm)": embedded.pixel_size_y_um,
        "File type": source.path.suffix.lstrip(".").upper(),
        "Source path": str(source.path),
        "WCS sidecar": str(panel.wcs_sidecar.path) if panel.wcs_sidecar else None,
        "Mask file": str(panel.sky_mask.path) if panel.sky_mask else None,
        "Bytes": source.fingerprint.size_bytes,
        "Modified": QDateTime.fromMSecsSinceEpoch(
            source.fingerprint.modified_ns // 1_000_000
        ).toString("yyyy-MM-dd HH:mm:ss"),
    }
    if descriptor:
        values.update(
            {
                "Size (px)": f"{descriptor.width} × {descriptor.height}",
                "Channels": descriptor.channel_layout.upper(),
                "Unit": descriptor.unit,
                "BITPIX": descriptor.bitpix,
                "BSCALE": descriptor.bscale,
                "BZERO": descriptor.bzero,
                "BLANK": descriptor.blank,
                "WCS source": descriptor.wcs_provenance,
                "Mask sources": ", ".join(descriptor.mask_provenance) or None,
            }
        )
    return PanelRow(panel, values, "\n".join(detail), not attention, statuses["Source"] == "Ready")


class PanelTableModel(QAbstractTableModel):
    panelEdited = Signal(int, object)
    invalidEdit = Signal(str)

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.rows: list[PanelRow] = []

    def refresh(self, rows: list[PanelRow]) -> None:
        if [r.panel.source for r in rows] != [r.panel.source for r in self.rows]:
            self.beginResetModel()
            self.rows = rows
            self.endResetModel()
        else:
            for i, row in enumerate(rows):
                if self.rows[i] != row:
                    self.rows[i] = row
                    self.dataChanged.emit(self.index(i, 0), self.index(i, len(COLUMNS) - 1))

    def rowCount(self, parent: _Index = _ROOT) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent: _Index = _ROOT) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = _Role.DisplayRole
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == _Role.DisplayRole:
            return COLUMNS[section]
        return super().headerData(section, orientation, role)

    def flags(self, index: _Index) -> Qt.ItemFlag:
        flags = super().flags(index)
        if index.isValid():
            name = COLUMNS[index.column()]
            if name in _EDITABLE:
                flags |= Qt.ItemFlag.ItemIsEditable
            elif name == "Sky":
                flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def data(self, index: _Index, role: int = _Role.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row, key = self.rows[index.row()], COLUMNS[index.column()]
        value = row.values.get(key)
        if role == _Role.CheckStateRole and key == "Sky":
            return Qt.CheckState.Checked if row.panel.include_sky else Qt.CheckState.Unchecked
        if role == _Role.EditRole:
            return "" if value is None else str(value)
        if role == _Role.DisplayRole:
            if key == "Sky":
                return None
            if isinstance(value, float):
                return format(value, ".9g")
            return "—" if value is None else str(value)
        if role == _Role.ToolTipRole:
            if key in ("Panel", "WCS", "Link", "Solve result"):
                return row.detail
            if key in _OPTICS or key == "Band":
                override = (
                    row.panel.band_override
                    if key == "Band"
                    else getattr(row.panel.optics, _OPTICS[key])
                )
                origin = "Panel override" if override is not None else "Inherited"
                return f"{origin}. Edit to override, or clear to inherit."
            if key == "Sky":
                return "Include this panel in the sky layer"
            return str(value) if value is not None else None
        if role == _Role.TextAlignmentRole and isinstance(value, int | float):
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        return None

    def setData(self, index: _Index, value: Any, role: int = _Role.EditRole) -> bool:
        if not index.isValid():
            return False
        panel, key = self.rows[index.row()].panel, COLUMNS[index.column()]
        try:
            if key == "Sky" and role == _Role.CheckStateRole:
                updated = replace(panel, include_sky=Qt.CheckState(value) == Qt.CheckState.Checked)
            elif key in _EDITABLE and role == _Role.EditRole:
                entered = str(value).strip()
                if entered == self.data(index, _Role.EditRole):
                    return True
                if key == "Band":
                    updated = replace(panel, band_override=entered or None)
                elif key == "Weight":
                    number = float(entered)
                    if not isfinite(number) or number <= 0:
                        raise ValueError("Enter a positive finite blend weight.")
                    updated = replace(panel, weight=number)
                else:
                    optics = replace(
                        panel.optics, **{_OPTICS[key]: float(entered) if entered else None}
                    )
                    updated = replace(panel, optics=optics)
            else:
                return False
        except ValueError as error:
            self.invalidEdit.emit(f"{key}: {error}")
            return False
        if updated != panel:
            self.panelEdited.emit(index.row(), updated)
        return True


class _PanelDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: _Index) -> None:
        super().paint(painter, option, index)
        if option.state & QStyle.StateFlag.State_Selected:
            cell = option.rect
            outline = option.palette.color(QPalette.ColorRole.Accent)
            painter.fillRect(cell.left(), cell.top(), cell.width(), 1, outline)
            painter.fillRect(cell.left(), cell.bottom(), cell.width(), 1, outline)

    def setEditorData(self, editor: QWidget, index: _Index) -> None:
        # Background inspection can finish while the user is typing.
        if not isinstance(editor, QLineEdit) or not editor.isModified():
            super().setEditorData(editor, index)


class PanelTable(QTableView):
    def __init__(self) -> None:
        super().__init__()
        self.properties = PanelTableModel(self)
        self.setModel(self.properties)
        self.setItemDelegate(_PanelDelegate(self))
        self.setAccessibleName("Panel control table")
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setTabKeyNavigation(False)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.setShowGrid(True)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(32)
        self.horizontalHeader().setHighlightSections(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        for i, width in enumerate(_WIDTHS.values()):
            self.setColumnWidth(i, width)
        self.show_view("Overview")

    def show_view(self, name: str) -> None:
        for column, key in enumerate(COLUMNS):
            self.setColumnHidden(column, key not in VIEWS[name])
        self.horizontalScrollBar().setValue(0)

    def cell(self, row: int, name: str) -> QModelIndex:
        return self.properties.index(row, COLUMNS.index(name))
