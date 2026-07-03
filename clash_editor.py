import math
import os
import sys

from PySide6.QtWidgets import (
    QApplication, QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsSimpleTextItem,
    QDockWidget, QListWidget, QListWidgetItem,
    QLabel, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QMainWindow, QToolBar, QSpinBox, QLineEdit, QCheckBox, QPushButton,
    QGroupBox, QFileDialog, QComboBox
)
from PySide6.QtGui import QPixmap, QIcon, QAction, QActionGroup, QPen, QColor, QFont
from PySide6.QtCore import Qt, QSize, QDir

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



# ---- Units
UNIT_TEX_DIR = "res/normal"
DEFAULT_UNIT_COLOR = 1 #red,blue,yellow,white,green
UNIT_REC_SIZE = 62
SQUAD_MEMBER_STRIDE = 31
MAX_UNITS_PER_TILE = 10

# Oddzialy sa zapisane jako sloty co 725 bajtow (SQUAD_SLOT), poczawszy od
# SUQAD_ANCHOR. Kazdy slot to naglowek oddzialu; wlasciciel (gracz) jest w bajcie +10 (0=czerwony, 1=niebieski,...)

UNIT_SECTION_OFFSET = 140016
SQUAD_ANCHOR = 0x023EF0
SQUAD_SLOT = 0x2D5                  # 725 bajtow na slot oddzialu
MAX_OWNER = 4                       # 0..4 -> 5 kolorow graczy

OWNER_NAMES = ["Czerwony", "Niebieski", "Zolty", "Bialy", "Zielony"]

UNIT_TYPES = {
    0: "PEON",   1: "INFL",   2: "INFH",   3: "SPRL",   4: "SPRH",
    5: "CAVL",   6: "CAVH",   7: "RYC",    8: "DRAG",    9: "ARCH",
    10: "KUSZA", 11: "MUSZK", 12: "KATAP", 13: "TARAN",  14: "ARMAT",
    15: "LESN",  16: "GORAL", 17: "BUDOW", 18: "WORM",  19: "SLON",
    20: "CYKL",  21: "TROL",  22: "SCROP", 23: "SZK",  24: "MAG",
    25: "DUCH",  26: "ORZEL", 27: "PEGAZ", 28: "SKRZ",  29: "WAZKA",
    30: "SMOK",  31: "GOLD",  32: "PEAS",  33: "SPEC", 34: "SPECK",
}


UNIT_NAMES = {
    0: "Pospolite ruszenie",
    1: "Lekka piechota",
    2: "Ciężka piechota",
    3: "Pikinier",
    4: "Halabardnik",

    5: "Lekka jazda",
    6: "Ciężka jazda",
    7: "Rycerstwo",
    8: "Dragon",
    9: "Łucznik",

    10: "Kusznik",
    11: "Muszkieter",
    12: "Katapulta",
    13: "Taran",
    14: "Armata",

    15: "Leśnik",
    16: "Góral",
    17: "Budowniczy",
    18: "Czerw",
    19: "Słoń",

    20: "Cyklop",
    21: "Troll",
    22: "Skorpion",
    23: "Szkielet",
    24: "Mag",

    25: "Duch",
    26: "Orzeł",
    27: "Pegaz",
    28: "Skrzydlak",
    29: "Ważka",

    30: "Smok",
    31: "Złoto",
    32: "Chłopi",
    33: "Dowódca (syn)",
    34: "Dowódca (córka)",
}

UNIT_VALID_TYPES = set(UNIT_TYPES.keys())


def find_units_in_data(data):
    squads = []
    n = len(data)
    if SQUAD_ANCHOR >= n - UNIT_REC_SIZE:
        return squads
    kmax = (n - UNIT_REC_SIZE - SQUAD_ANCHOR) // SQUAD_SLOT
    for k in range(kmax + 1):
        b = SQUAD_ANCHOR + k * SQUAD_SLOT
        if b < UNIT_SECTION_OFFSET:
            continue
        t = data[b + 12]
        if t not in UNIT_VALID_TYPES or data[b + 13] != 0:
            continue
        owner = data[b + 10]
        if owner > MAX_OWNER:
            continue
        x = data[b+6] | (data[b + 7] << 8)
        y = data[b + 8] | (data[b + 9] << 8)
        if x>= GRID_W or y >+ GRID_H or (x==0 and y==0):
            continue
        members = []
        for j in range(MAX_UNITS_PER_TILE):
            o = b + 12 + SQUAD_MEMBER_STRIDE * j
            lo, hi = data[o], data[o + 1]
            if hi != 0 or lo not in UNIT_VALID_TYPES:
                break
            if data[o +2] != owner:
                break
            members.append(lo)
        if members:
            squads.append({
                "x" : x, "y": y, "offset": b, "owner": owner,
                "color": owner + 1, "members": members,
            })
    return squads
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
        self.squad_panel = None
        self.selected_cell = None
        self.current_path = None
        self.palette = DEFAULT_PALETTE
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        self.map = [
            [Tile() for _ in range(height)]
            for _ in range(width)
        ]



        self.units = []
        self.unit_tex_cache = {}
        self.sel_rect = None

        self._nav_index = -1
        self._nav_owner = "unset"

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
        self._draw_units()

        self.sel_rect.setPen(QPen(QColor(255,0,0), 3))
        self.sel_rect.setZValue(1000)
        self.sel_rect.setVisible(False)
        self.scene.addItem(self.sel_rect)
        self._update_sel_rect()


    # ------------- UNITS -------------------
    def _unit_pixmap(self, type_id, color, frame=0):
        prefix = UNIT_TYPES.get(type_id)
        if not prefix:
            return None
        key = (prefix, color, frame)
        if key in self.unit_tex_cache:
            return self.unit_tex_cache[key]
        folder = f"{prefix}{color}_S32"
        path = os.path.join(UNIT_TEX_DIR, folder, f"{folder}_{frame}.png")
        pix = None
        if os.path.exists(path):
            p = QPixmap(path)
            if not p.isNull():
                pix = p
        self.unit_tex_cache[key] = pix
        return pix

    def _draw_units(self):
        for sq in self.units:
            self._draw_squad(sq)

    def _draw_squad(self, squad):
        tx, ty = squad["x"], squad["y"]
        color = squad.get("color", DEFAULT_UNIT_COLOR)
        members = squad["members"]
        if not members:
            return
        leader = members[0]
        pix = self._unit_pixmap(leader, color, 0)
        if pix is None:
            return
        scaled = pix.scaled(
            TILE_SIZE, TILE_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        px = tx * TILE_SIZE  + (TILE_SIZE - scaled.width()) / 2
        py = ty * TILE_SIZE + (TILE_SIZE - scaled.height()) / 2
        item = self.scene.addPixmap(scaled)
        item.setOffset(px, py)
        item.setZValue(500)

        self._draw_squad_count(tx, ty, len(members))

    def _draw_squad_count(self, tx, ty, count):
        font = QFont()
        font.setBold(True)
        font.setPixelSize(18)
        text = QGraphicsSimpleTextItem(str(count))
        text.setFont(font)
        text.setBrush(QColor(255,255,0))
        text.setPen(QPen(QColor(0,0,0),2))
        br = text.boundingRect()
        text.setPos(
            tx * TILE_SIZE + TILE_SIZE - br.width() - 3,
            ty * TILE_SIZE + TILE_SIZE - br.height() - 2,
        )
        text.setZValue(600)
        self.scene.addItem(text)

    def squad_at(self, x,y):
        for sq in self.units:
            if sq["x"] == x and sq["y"] == y:
                return sq
        return None

    def goto_next_squad(self, owner=None):
        squads = [
            s for s in self.units
            if owner is None or s["owner"] == owner
        ]
        if not squads:
            return None
        squads.sort(key=lambda s: (s["y"], s["x"]))
        if self._nav_owner != owner:
            self._nav_owner = owner
            self._nav_index = -1
        self._nav_index = (self._nav_index +1) % len(squads)
        sq = squads[self._nav_index]
        self.select_cell(sq["x"], sq["y"])
        self.centerOn(
            (sq["x"] + 0.5) * TILE_SIZE,
            (sq["y"] + 0.5) * TILE_SIZE,
        )
        return sq

    def load_units(self, path):
        with open(path, "rb") as f:
            data = f.read()
        self.units = find_units_in_data(data)
        self._nav_index = -1
        self._nav_owner = "unset"
        self.draw_map()

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
        if self.squad_panel:
            self.squad_panel.load_squad(x, y, self.squad_at(x, y))

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

    def set_textures(self, textures):
        """Podmienia palete tekstur kafelków i przerysowuje mape."""
        self.textures = textures
        self.draw_map()

    def set_mode(self, mode):
        self.mode = mode


    def tile_changed(self, x, y):
        self.draw_map()

    # ---------------- LOAD (full 14-byte records) ----------------
    def load_dat(self, path):
        self.current_path = path
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

    def load_file(self, path):
        self.load_dat(path)
        self.load_units(path)


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


TILE_TEX_DIR = "res/normal"
TILE_PALETTES = [
    "BACKGR1_S32", "BACKGR2_S32", "BACKGR3_S32",
    "BAT_BKG1_S32", "BAT_BKG2_S32", "BAT_BKG3_S32",
]
DEFAULT_PALETTE = "BACKGR1_S32"

def palette_folder(palette):
    return os.path.join(TILE_TEX_DIR, palette)

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

    def set_textures(self, textures):
        """Odswieza liste pogladow po zmianie palety"""
        self.textures = textures
        self.list.clear()
        self.fill()

    def pick(self, item):
        tex_id = item.data(Qt.UserRole)
        self.preview.setText(f"Selected: {tex_id}")
        self.on_select(tex_id)



# --------------- SQUAD PANEL -------------------
class SquadPanel(QDockWidget):
    def __init__(self, editor):
        super().__init__("Squad")
        self.editor = editor

        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.header = QLabel("Brak zaznaczenia")
        layout.addWidget(self.header)

        self.list = QListWidget()
        self.list.setIconSize(QSize(32, 32))
        layout.addWidget(self.list)

        self.setWidget(widget)

    def load_squad(self, x, y, squad):
        self.list.clear()
        if squad is None:
            self.header.setText(f"Kafelek ({x}, {y}): brak oddzialu")
            return
        members = squad.get("members",[])
        color = squad.get("color", DEFAULT_UNIT_COLOR)
        self.header.setText(f"Kafelek ({x}, {y}): oddzial {len(members)}-osobowy")
        for i, type_id in enumerate(members):
            name = UNIT_NAMES.get(type_id, f"typ {type_id}")
            role = "dowodca" if i == 0 else f"jednostka { i + 1}"
            item = QListWidgetItem(f"{name} {role}")
            pix = self.editor._unit_pixmap(type_id, color, 0)
            if pix is not None:
                item.setIcon(QIcon(pix))
            self.list.addItem(item)

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
        self.panel=panel
        self.setWindowTitle("Clash Map Editor")

        self.setCentralWidget(editor)
        self.addDockWidget(Qt.LeftDockWidgetArea, panel)

        self.inspector = TileInspector(editor)
        editor.inspector = self.inspector
        self.addDockWidget(Qt.RightDockWidgetArea, self.inspector)

        self.squad_panel = SquadPanel(editor)
        editor.squad_panel = self.squad_panel
        self.addDockWidget(Qt.RightDockWidgetArea, self.squad_panel)

        self.create_toolbar()

    def create_toolbar(self):
        tb = QToolBar("Main")
        self.addToolBar(tb)

        open_action = QAction("Wczytaj plik", self)
        open_action.triggered.connect(self.open_file)
        tb.addAction(open_action)

        tb.addSeparator()

        tb.addWidget(QLabel(" Paleta: "))
        self.palette_combo = QComboBox()
        self.palette_combo.addItems(TILE_PALETTES)
        self.palette_combo.setCurrentText(self.editor.palette)
        self.palette_combo.currentTextChanged.connect(self.change_palette)
        tb.addWidget(self.palette_combo)

        tb.addSeparator()

        tb.addWidget(QLabel(" Gracz: "))
        self.player_combo = QComboBox()
        self.player_combo.addItem("Wszyscy")
        self.player_combo.addItems(OWNER_NAMES)
        tb.addWidget(self.player_combo)

        next_squad_action = QAction("Nastepny oddzial", self)
        next_squad_action.triggered.connect(self.next_squad)
        tb.addAction(next_squad_action)


        tb.addSeparator()


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

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Wczytaj plik mapy", "",
                                              "Pliki Clash (*.DAT);;Wszystkie pliki (*.*)"
                                              )
        if not path:
            return
        self.editor.load_file(path)
        self.setWindowTitle("Clash Map Editor - {os.path.basename(path)}")

    def change_palette(self, palette):
        """Przelacza palete tekstur kafelkow i odswieza widok oraz panel."""
        textures = load_textures(palette_folder(palette))
        self.editor.palette = palette
        self.editor.set_textures(textures)
        self.panel.set_textures(textures)

    def next_squad(self):
        idx = self.player_combo.currentIndex()
        owner = None if idx == 0 else idx - 1
        sq = self.editor.goto_next_squad(owner)
        if sq is None:
            who = "zadnego gracza" if owner is None else OWNER_NAMES[owner]
            self.statusBar().showMessage(f"Brak oddzialow: {who}", 3000)
        else:
            self.statusBar().showMessage(
                f"Oddzial ({sq['x']}, {sq['y']}) - {len(sq['members'])} jednostek",
            )



    def save_patch(self):
        src = self.editor.current_path or "1.DAT"
        base, ext = os.path.splitext(src)
        out = f"{base}_MOD{ext or '.DAT'}"
        self.editor.save_dat_patch(src, out)
        print(f"PATCH SAVED -> {out}")


# ---------------- MAIN ----------------
if __name__ == "__main__":
    app = QApplication(sys.argv)

    textures = load_textures(palette_folder(DEFAULT_PALETTE))

    editor = MapEditor(GRID_W, GRID_H, textures)
    editor.load_file("1.DAT")

    panel = TexturePanel(textures, editor.set_selected_texture)

    window = MainWindow(editor, panel)
    window.resize(1400, 900)
    window.show()

    sys.exit(app.exec())