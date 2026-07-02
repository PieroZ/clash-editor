import os
import sys

from PySide6.QtWidgets import (
    QApplication, QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QDockWidget, QListWidget, QListWidgetItem,
    QLabel, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QMainWindow, QToolBar, QSpinBox, QLineEdit, QCheckBox, QPushButton,
    QGroupBox
)
from PySide6.QtGui import QPixmap, QIcon, QAction, QActionGroup, QPen, QColor
from PySide6.QtCore import Qt
from fontTools.pens.qtPen import QtPen

TILE_SIZE = 64

# ---- File / format constants
HEADER_SIZE = 16
RECORD_SIZE = 14        # bytes per tile
GRID_W = 100
GRID_H = 100

FIELD_NONE = 0xFFFF

# u16 field indices inside a 14-byte record
F_TEX = 0               # bytes 0-1 : base texture id
F_OVERLAY1 = 1          # bytes 2-3 : overlay / transition layer
F_ROAD = 2
F_FLAGS = 3
F_F4 = 4
F_F5 = 5
F_F6 = 6

DEFAULT_ROAD = 0x0362

FIELD_LABELS = [
    "Tekstura (0-1)",
    "Nakladka 1 (2-3)",
    "Droga / obiekt (4-5)",
    "Flagi (6-7)",
    "Pole (8-9)",
    "Pole (10-11)",
    "Pole (12-13)",
]


# ---------------- TILE ----------------
class Tile:
    def __init__(self, raw=None):
        if raw is None:
            self.raw = bytearray(RECORD_SIZE)
        else:
            self.raw = bytearray(raw)

    def u16(self, field):
        o = field * 2
        return self.raw[o] | (self.raw[o + 1] << 8)

    def set_u16(self, field, val):
        val &= 0xFFFF
        o = field * 2
        self.raw[o] = val & 0xFF
        self.raw[o + 1] = (val >> 8) & 0xFF

    @property
    def tex_id(self):
        return self.u16(F_TEX)

    @tex_id.setter
    def tex_id(self, v):
        self.set_u16(F_TEX, v)

    def hex_str(self):
        return " ".join(f"{b:02X}" for b in self.raw)


# ---------------- MAP VIEW ----------------
class MapEditor(QGraphicsView):
    def __init__(self, width, height, textures):
        super().__init__()

        self.width = width
        self.height = height
        self.textures = textures
        self.selected_tex = 0
        self.mode = "select"
        self.inspector = None
        self.selected_cell = None

        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        self.map = [
            [Tile() for _ in range(height)]
            for _ in range(width)
        ]



        self.sel_rect = None

        self.setMouseTracking(True)
        self.draw_map()


    def _add_tex(self, tex_id, x, y):
        pix = self.textures.get(tex_id)
        if pix:
            item = self.scene.addPixmap(pix)
            item.setOffset(x * TILE_SIZE, y * TILE_SIZE)

    def draw_map(self):
        self.scene.clear()

        for x in range(self.width):
            for y in range(self.height):
                tile = self.map[x][y]


                self._add_tex(tile.u16(F_TEX), x, y)


                ov1 = tile.u16(F_OVERLAY1)
                if ov1 != FIELD_NONE:
                    self._add_tex(ov1, x, y)

                road = tile.u16(F_ROAD)
                if road != FIELD_NONE:
                    self._add_tex(road, x, y)

        self.sel_rect = QGraphicsRectItem(0, 0, TILE_SIZE, TILE_SIZE)
        self.sel_rect.setPen(QPen(QColor(255,0,0), 3))
        self.sel_rect.setZValue(1000)
        self.sel_rect.setVisible(False)
        self.scene.addItem(self.sel_rect)
        self._update_sel_rect()

    def _update_sel_rect(self):
        if self.selected_cell is None:
            self.sel_rect.setVisible(False)
            return
        x, y = self.selected_cell
        self.sel_rect.setRect(
            x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE
        )
        self.sel_rect.setVisible(True)


    def _cell_at(self, event):
        pos = self.mapToScene(event.position().toPoint())
        x = int(pos.x() // TILE_SIZE)
        y = int(pos.y() // TILE_SIZE)
        if 0 <= x < self.width and 0 <= y < self.height:
            return x,y
        return None

    def select_cell(self, x, y):
        self.selected_cell = (x, y)
        self._update_sel_rect()
        if self.inspector:
            self.inspector.load_tile(x, y, self.map[x][y])

    def paint_tile(self, x, y):
        self.map[x][y].tex_id = self.selected_tex
        self.draw_map()

    def mousePressEvent(self, event):
        cell = self._cell_at(event)
        if not cell:
            return
        x, y = cell
        if self.mode == "paint":
            self.paint_tile(x, y)
        else:
            self.select_cell(x, y)

    def mouseMoveEvent(self, event):
        if self.mode == "paint" and (event.buttons() & Qt.LeftButton):
            cell = self._cell_at(event)
            if cell:
                self.paint_tile(*cell)

    def set_selected_texture(self, tex_id):
        self.selected_tex = tex_id

    def set_mode(self, mode):
        self.mode = mode


    def tile_changed(self, x, y):
        self.draw_map()

    # ---------------- LOAD (full 14-byte records) ----------------
    def load_dat(self, path):
        with open(path, "rb") as f:
            f.seek(HEADER_SIZE)
            for x in range(self.width):
                for y in range(self.height):
                    data = f.read(RECORD_SIZE)
                    if len(data) < RECORD_SIZE:
                        self.draw_map()
                        return
                    self.map[x][y] = Tile(data)
        self.draw_map()

    # ---------------- PATCH SAVE (full tile records) ----------------
    def save_dat_patch(self, input_path, output_path):
        with open(input_path, "rb") as f:
            data = bytearray(f.read())

        for x in range(self.width):
            for y in range(self.height):
                idx = x * self.height + y
                offset = HEADER_SIZE + idx * RECORD_SIZE
                data[offset:offset + RECORD_SIZE] = self.map[x][y].raw

        with open(output_path, "wb") as f:
            f.write(data)


# ---------------- TEXTURE LOADER ----------------
def load_textures(folder):
    textures = {}

    for file in os.listdir(folder):
        if file.endswith(".png"):
            try:
                tex_id = int(file.split("_")[-1].split(".")[0])
                textures[tex_id] = QPixmap(os.path.join(folder, file))
            except:
                pass

    return textures


# ---------------- TEXTURE PANEL ----------------
class TexturePanel(QDockWidget):
    def __init__(self, textures, on_select):
        super().__init__("Textures")

        self.textures = textures
        self.on_select = on_select

        widget = QWidget()
        layout = QVBoxLayout()

        self.preview = QLabel("Selected: None")
        layout.addWidget(self.preview)

        self.list = QListWidget()
        layout.addWidget(self.list)

        widget.setLayout(layout)
        self.setWidget(widget)

        self.fill()
        self.list.itemClicked.connect(self.pick)

    def fill(self):
        for tex_id in sorted(self.textures.keys()):
            pix = self.textures[tex_id]
            item = QListWidgetItem(f"Texture {tex_id}")
            item.setData(Qt.UserRole, tex_id)
            item.setIcon(QIcon(pix.scaled(64, 64)))
            self.list.addItem(item)

    def pick(self, item):
        tex_id = item.data(Qt.UserRole)
        self.preview.setText(f"Selected: {tex_id}")
        self.on_select(tex_id)


# ---------------- TILE INSPECTOR ---------------
class TileInspector(QDockWidget):
    def __init__(self, editor):
        super().__init__("TileInspector")
        self.editor = editor
        self.tile = None
        self.cell = None
        self._loading = False

        widget = QWidget()
        root = QVBoxLayout(widget)

        self.header = QLabel("Brak zaznaczenia")
        root.addWidget(self.header)


        form_box = QGroupBox("Pola rekordu (u16, little-endian)")
        form = QFormLayout(form_box)
        self.spins = []
        self.hexlabels = []
        for i, label in enumerate(FIELD_LABELS):
            spin = QSpinBox()
            spin.setRange(0, 0xFFFF)
            spin.valueChanged.connect(lambda v, fi=i: self._on_field_changed(fi,v))
            hexlbl = QLabel("0x0000")
            row = QHBoxLayout()
            rw = QWidget()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(spin)
            row.addWidget(hexlbl)
            rw.setLayout(row)
            form.addRow(label, rw)
            self.spins.append(spin)
            self.hexlabels.append(hexlbl)
        root.addWidget(form_box)


        raw_box = QGroupBox("Surowe bajty (hex, 14 x 2)")
        raw_l = QVBoxLayout(raw_box)
        self.raw_edit = QLineEdit()
        self.raw_edit.setPlaceholderText("np. 53 02 FF FF 62 03 00 ...")
        self.raw_edit.editingFinished.connect(self._on_raw_changed)
        raw_l.addWidget(self.raw_edit)
        root.addWidget(raw_box)


        road_box = QGroupBox("Droga / obiekt (bajty 4-5)")
        road_l = QGridLayout(road_box)
        self.road_check = QCheckBox("Zawiera droge / obiekt")
        self.road_check.toggled.connect(self._on_road_toggled)
        road_l.addWidget(self.road_check, 0, 0, 1, 2)

        road_l.addWidget(QLabel("Wartosc:"), 1, 0)
        self.road_value = QSpinBox()
        self.road_value.setRange(0, 0xFFFE)
        self.road_value.setValue(DEFAULT_ROAD)
        self.road_value.valueChanged.connect(self._on_road_value_changed)
        road_l.addWidget(self.road_value, 1, 1)

        btn = QPushButton("Ustaw droge 62 03 (866)")
        btn.clicked.connect(lambda: self._set_road(DEFAULT_ROAD))
        road_l.addWidget(btn, 2,0,1,2)
        root.addWidget(road_box)

        root.addStretch(1)
        self.setWidget(widget)
        self._set_enabled(False)


    def _set_enabled(self, on):
        for s in self.spins:
            s.setEnabled(on)
        self.raw_edit.setEnabled(on)
        self.road_check.setEnabled(on)
        self.road_value.setEnabled(on)

    def load_tile(self, x, y, tile):
        self.tile = tile
        self.cell = (x, y)
        offset = HEADER_SIZE + (x * GRID_H + y) * RECORD_SIZE
        self.header.setText(
            f"Kafelek ({x}, {y}) offset 0x{offset:06X} ({offset})"
        )
        self._set_enabled(True)
        self._refresh()

    def _refresh(self):
        if self.tile is None:
            return
        self._loading = True
        for i, spin in enumerate(self.spins):
            v = self.tile.u16(i)
            spin.setValue(v)
            self.hexlabels[i].setText(f"0x{v:04X}")
        self.raw_edit.setText(self.tile.hex_str())
        road = self.tile.u16(F_ROAD)
        has_road = road != FIELD_NONE
        self.road_check.setChecked(has_road)
        if has_road:
            self.road_value.setValue(road)
        self._loading = False


    def _commit(self):
        self.raw_edit.setText(self.tile.hex_str())
        for i in range(len(self.spins)):
            self.hexlabels[i].setText(f"0x{self.tile.u16(i):04X}")
        if self.cell:
            self.editor.tile_changed(*self.cell)

    def _on_field_changed(self, field, value):
        if self._loading or self.tile is None:
            return
        self.tile.set_u16(field,value)
        if field == F_ROAD:
            self._loading = True
            has_road = value != FIELD_NONE
            self.road_check.setChecked(has_road)
            if has_road:
                self.road_value.setValue(value)
            self._loading = False
        self._commit()

    def _on_raw_changed(self):
        if self._loading or self.tile is None:
            return
        parts = self.raw_edit.text().replace(",", " ").split()
        try:
            vals = [int(p, 16) for p in parts]
        except ValueError:
            self._refresh()
            return
        if len(vals) != RECORD_SIZE or any(v < 0 or v > 0xFF for v in vals):
            self._refresh()
            return
        self.tile.raw = bytearray(vals)
        self._refresh()
        if self.cell:
            self.editor.tile_changed(*self.cell)

    def _set_road(self, value):
        if self.tile is None:
            return
        self.road_value.setValue(value)
        self.tile.set_u16(F_ROAD, value)
        self._loading = True
        self.road_check.setChecked(True)
        self.spins[F_ROAD].setValue(value)
        self._loading = False
        self._commit()

    def _on_road_toggled(self, checked):
        if self._loading or self.tile is None:
            return
        value = self.road_value.value() if checked else FIELD_NONE
        self.tile.set_u16(F_ROAD, value)
        self._loading = True
        self.spins[F_ROAD].setValue(value)
        self._loading = False
        self._commit()

    def _on_road_value_changed(self, value):
        if self._loading or self.tile is None:
            return
        if self.road_check.isChecked():
            self.tile.set_u16(F_ROAD, value)
            self._loading = True
            self.spins[F_ROAD].setValue(value)
            self._loading = False
            self._commit()


# ---------------- MAIN WINDOW ----------------
class MainWindow(QMainWindow):
    def __init__(self, editor, panel):
        super().__init__()

        self.editor = editor
        self.setWindowTitle("Clash Map Editor")

        self.setCentralWidget(editor)
        self.addDockWidget(Qt.LeftDockWidgetArea, panel)

        self.inspector = TileInspector(editor)
        editor.inspector = self.inspector
        self.addDockWidget(Qt.RightDockWidgetArea, self.inspector)

        self.create_toolbar()

    def create_toolbar(self):
        tb = QToolBar("Main")
        self.addToolBar(tb)


        group = QActionGroup(self)
        group.setExclusive(True)

        select_action = QAction("Zaznacz", self, checkable=True)
        select_action.setChecked(True)
        select_action.triggered.connect(lambda: self.editor.set_mode("select"))
        group.addAction(select_action)
        tb.addAction(select_action)

        paint_action = QAction("Maluj", self, checkable=True)
        paint_action.triggered.connect(lambda: self.editor.set_mode("paint"))
        group.addAction(paint_action)
        tb.addAction(paint_action)

        tb.addSeparator()

        save_action = QAction("Save Patch", self)
        save_action.triggered.connect(self.save_patch)

        tb.addAction(save_action)

    def save_patch(self):
        self.editor.save_dat_patch("1.DAT", "1_MOD.DAT")
        print("PATCH SAVED -> 1_MOD.DAT")


# ---------------- MAIN ----------------
if __name__ == "__main__":
    app = QApplication(sys.argv)

    textures = load_textures("textures")

    editor = MapEditor(GRID_W, GRID_H, textures)
    editor.load_dat("1.DAT")

    panel = TexturePanel(textures, editor.set_selected_texture)

    window = MainWindow(editor, panel)
    window.resize(1400, 900)
    window.show()

    sys.exit(app.exec())