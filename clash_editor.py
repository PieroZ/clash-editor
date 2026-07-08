import math
import os
import sys

from PySide6.QtWidgets import (
    QApplication, QStyleFactory, QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsSimpleTextItem,
    QDockWidget, QListWidget, QListWidgetItem,
    QLabel, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QMainWindow, QToolBar, QSpinBox, QLineEdit, QCheckBox, QPushButton,
    QGroupBox, QFileDialog, QComboBox, QTabWidget
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

BUILDING_TEX_DIR = "res/minimum"
BUILDING_SCAN_START = 0x028000
BUILDING_TABLE_BASE = 0x7C6FA
BUILDING_REC_SIZE = 467
BUILDING_EMPTY_TYPE = 0xFF
CASTLE_TYPE = 2
CASTLE_SIZE = 2
CASTLE_BASE_TEX = 237
CASTLE_OWNER_TEX_STRIDE = 40



BUILDING_TYPE_TEX = {
    0: (1, 12, 1), # wieza
    1: (2, 93, 4), # twierdza
    2: (2, 237, 40), # zamek
}

BUILDING_DEFAULT_TEX = (2, 237, 40)

UNIT_TYPES = {
    0: "PEON",   1: "INFL",   2: "INFH",   3: "SPRL",   4: "SPRH",
    5: "CAVL",   6: "CAVH",   7: "RYC",    8: "DRAG",    9: "ARCH",
    10: "KUSZA", 11: "MUSZK", 12: "KATAP", 13: "TARAN",  14: "ARMAT",
    15: "LESN",  16: "GORAL", 17: "BUDOW", 18: "WORM",  19: "SLON",
    20: "CYKL",  21: "TROL",  22: "SCORP", 23: "SZK",  24: "MAG",
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

UNIT_HP_MAX = 100
UNIT_STATS = {
    0:  {"move": 24, "morale": 10, "attack": 1,  "armor": 1,  "ranged": 0},
    1:  {"move": 20, "morale": 10, "attack": 5,  "armor": 4,  "ranged": 0},
    2:  {"move": 20, "morale": 10, "attack": 9,  "armor": 6,  "ranged": 0},
    3:  {"move": 24, "morale": 10, "attack": 3,  "armor": 5,  "ranged": 0},
    4:  {"move": 22, "morale": 10, "attack": 5,  "armor": 5,  "ranged": 0},
    5:  {"move": 36, "morale": 10, "attack": 8,  "armor": 5,  "ranged": 0},
    6:  {"move": 32, "morale": 10, "attack": 14, "armor": 8,  "ranged": 0},
    7:  {"move": 30, "morale": 10, "attack": 12, "armor": 7,  "ranged": 0},
    8:  {"move": 32, "morale": 10, "attack": 10, "armor": 4,  "ranged": 6},
    9:  {"move": 24, "morale": 10, "attack": 3,  "armor": 1,  "ranged": 6},
    10: {"move": 20, "morale": 10, "attack": 5,  "armor": 2,  "ranged": 8},
    11: {"move": 24, "morale": 10, "attack": 4,  "armor": 3,  "ranged": 11},
    12: {"move": 20, "morale": 10, "attack": 0,  "armor": 1,  "ranged": 16},
    13: {"move": 20, "morale": 10, "attack": 20, "armor": 10, "ranged": 0},
    14: {"move": 16, "morale": 10, "attack": 0,  "armor": 1,  "ranged": 20},
    15: {"move": 24, "morale": 10, "attack": 8,  "armor": 4,  "ranged": 11},
    16: {"move": 26, "morale": 10, "attack": 8,  "armor": 6,  "ranged": 0},
    17: {"move": 26, "morale": 10, "attack": 1,  "armor": 1,  "ranged": 0},
    18: {"move": 18, "morale": 6,  "attack": 14, "armor": 9,  "ranged": 0},
    19: {"move": 20, "morale": 6,  "attack": 14, "armor": 10, "ranged": 0},
    20: {"move": 26, "morale": 6,  "attack": 10, "armor": 6,  "ranged": 10},
    21: {"move": 22, "morale": 6,  "attack": 13, "armor": 10, "ranged": 0},
    22: {"move": 26, "morale": 6,  "attack": 12, "armor": 8,  "ranged": 0},
    23: {"move": 22, "morale": 6,  "attack": 13, "armor": 10, "ranged": 0},
    24: {"move": 40, "morale": 6,  "attack": 10, "armor": 10, "ranged": 15},
    25: {"move": 24, "morale": 6,  "attack": 10, "armor": 8,  "ranged": 0},
    26: {"move": 34, "morale": 6,  "attack": 9,  "armor": 6,  "ranged": 0},
    27: {"move": 30, "morale": 6,  "attack": 12, "armor": 8,  "ranged": 0},
    28: {"move": 24, "morale": 6,  "attack": 14, "armor": 10, "ranged": 10},
    29: {"move": 32, "morale": 6,  "attack": 8,  "armor": 5,  "ranged": 0},
    30: {"move": 36, "morale": 6,  "attack": 18, "armor": 15, "ranged": 15},
    31: {"move": 30, "morale": 10, "attack": 0,  "armor": 0,  "ranged": 0},
    32: {"move": 30, "morale": 10, "attack": 0,  "armor": 2,  "ranged": 0},
    33: {"move": 36, "morale": 10, "attack": 0,  "armor": 2,  "ranged": 0},
    34: {"move": 36, "morale": 10, "attack": 0,  "armor": 2,  "ranged": 0},
}

M_TYPE = 0
M_OWNER = 2
M_MOVE = 8
M_HP = 9
M_FATIGUE = 10
M_MORALE = 11
M_ADV = 12

FOG_BASE = 140084
FOG_PLAYER_STRIDE = 1423
FOG_COL_STRIDE = 13
FOG_VISION_RADIUS = 6

# occupancy grid
UNIT_INDEX_BASE = 556390
UNIT_INDEX_COL_STRIDE = 200
UNIT_INDEX_EMPTY = 0xFFFF


def set_unit_index_cell(data, x, y, value):
    return
    if data is None or not ( 0 <= x < GRID_W and 0 <= y < GRID_H ):
        return
    off = UNIT_INDEX_BASE + x * UNIT_INDEX_COL_STRIDE + y * 2
    if 0 <= off < len(data)-1:
        data[off] = value & 0xFF
        data[off + 1] = (value >> 8) & 0xFF


def reveal_fog_area(data, x, y, owner, radius=FOG_VISION_RADIUS):
    if data is None or not (0 <= owner <= MAX_OWNER):
        return 0
    base = FOG_BASE + owner * FOG_PLAYER_STRIDE
    revealed = 0
    r2 = radius * radius + radius
    for dy in range(-radius, radius + 1):
        ty = y + dy
        if not (0 <= ty < GRID_H):
            continue
        for dx in range(-radius, radius + 1):
            tx = x + dx
            if not (0 <= tx < GRID_W):
                continue
            if dx * dx + dy * dy > r2:
                continue
            off = base + tx * FOG_COL_STRIDE + (ty >> 3)
            if 0 <= off < len(data):
                bit = 1 << (ty & 7)
                if not (data[off] & bit):
                    data[off] |= bit
                    revealed += 1
    return revealed


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
        if x>= GRID_W or y >= GRID_H or (x==0 and y==0):
            continue
        members = []
        for j in range(MAX_UNITS_PER_TILE):
            o = b + 12 + SQUAD_MEMBER_STRIDE * j
            lo, hi = data[o], data[o + 1]
            if hi != 0 or lo not in UNIT_VALID_TYPES:
                break
            if data[o + M_OWNER] != owner:
                break
            members.append({
                "type": lo,
                "offset": o,
                "move": data[o + M_MOVE],
                "hp": data[o + M_HP],
                "fatigue": data[o + M_FATIGUE],
                "morale": data[o + M_MORALE],
                "adv": data[o + M_ADV] & 0x0F,
            })
        if members:
            squads.append({
                "x" : x, "y": y, "offset": b, "owner": owner,
                "color": owner + 1, "members": members,
            })
    return squads

def find_buildings_in_data(data):
    # byte0=x
    # byte1=y (1..99)
    # byte2=owner
    # byte3=color
    # byte4=type
    out = []
    n = len(data)
    k = 0
    while True:
        o = BUILDING_TABLE_BASE + k * BUILDING_REC_SIZE
        if o + 5 > n:
            break
        k +=1
        t= data[o+4]
        if t ==BUILDING_EMPTY_TYPE:
            continue
        x, y = data[o], data[o+1]
        if not (1 <= x < GRID_W and 1 <= y < GRID_H):
            continue
        owner = data[o+2]
        color = data[o+3]
        if owner > MAX_OWNER or color > MAX_OWNER:
            continue
        name = []
        for b in data[o+5:o+25]:
            if 32<=b < 127:
                name.append(chr(b))
            else:
                break
        out.append({
            "x": x, "y": y, "type": t, "owner": owner,
            "offset": 0, "name": "".join(name),
        })
    return out

    # for o in range(BUILDING_SCAN_START,n - 8):
    #     x, y = data[o], data[o + 1]
    #     if not (1 <= x < GRID_W and 1 <= y < GRID_H):
    #         continue
    #     owner = data[o + 2]
    #     if owner > MAX_OWNER or data[o + 3] !=owner:
    #         continue
    #     if data[o + 4] != CASTLE_TYPE:
    #         continue
    #     if not (65 <= data[o + 5] < 123):  # nazwa powinna zaczynac sie litera
    #         continue
    #     name = []
    #     for b in  data[o + 5: o + 25]:
    #         if 32 <= b < 127:
    #             name.append(chr(b))
    #         else:
    #             break
    #         if len(name) < 3:
    #             continue
    #         out.append({
    #             "x": x, "y": y, "type": CASTLE_TYPE,"owner": owner,
    #             "offset": 0, "name": "".join(name),
    #         })
    # return out


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
        self.unit_editor = None
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
        self.raw_data = None
        self.unit_tex_cache = {}
        self.sel_rect = None

        self.buildings = []
        self.building_tex_cache = {}

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
        self._draw_buildings()
        self._draw_units()

        self.sel_rect.setPen(QPen(QColor(255,0,0), 3))
        self.sel_rect.setZValue(1000)
        self.sel_rect.setVisible(False)
        self.scene.addItem(self.sel_rect)
        self._update_sel_rect()

    def _building_variant(self):
        """Numer warantu BUILDIN (1/2/3) wynikajacy z aktywnej palety."""
        for ch in self.palette:
            if ch.isdigit():
                return ch
        return "1"

    def _building_pixmap(self, tex_id):
        variant = self._building_variant()
        key = (variant, tex_id)
        if key in self.building_tex_cache:
            return self.building_tex_cache[key]
        folder = f"BUILDIN{variant}_S32"
        path = os.path.join(BUILDING_TEX_DIR, folder, f"{folder}_{tex_id}.png")
        pix = None
        if os.path.exists(path):
            p = QPixmap(path)
            if not p.isNull():
                pix = p
        self.building_tex_cache[key] = pix
        return pix

    def _draw_buildings(self):
        for b in self.buildings:
            self._draw_building(b)

    def _draw_building(self, building):
        bx, by = building["x"], building["y"]
        base = CASTLE_BASE_TEX + CASTLE_OWNER_TEX_STRIDE * building.get("owner", 0)
        owner = building.get("owner", 0)
        btype = building.get("type", 2)
        size, base0, stride = BUILDING_TYPE_TEX.get(btype, BUILDING_DEFAULT_TEX)
        base = base0 + stride * owner
        for dy in range(size):
            for dx in range(size):
                x, y = bx + dx, by + dy
                if x >= self.width or y >= self.height:
                    continue
                pix = self._building_pixmap(base + dx + size * dy)
                if pix is None:
                    continue
                item = self.scene.addPixmap(pix)
                item.setOffset(x * TILE_SIZE, y * TILE_SIZE)
                item.setZValue(100)


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
        leader = members[0]["type"]
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


    def update_member(self, squad, idx, type_id=None, hp=None, move=None,
                      morale=None, fatigue=None, adv=None):
        """Zapisuje zmiany statystyki członka oddziału do bufora pliku."""

        if self.raw_data is None:
            return

        m = squad["members"][idx]
        o = m["offset"]

        if type_id is not None:
            self.raw_data[o + M_TYPE] = type_id & 0xFF
            self.raw_data[o + M_TYPE + 1] = 0
            m["type"] = type_id

        if move is not None:
            self.raw_data[o + M_MOVE] = move & 0xFF
            m["move"] = move & 0xFF

        if hp is not None:
            self.raw_data[o + M_HP] = hp & 0xFF
            m["hp"] = hp & 0xFF

        if fatigue is not None:
            self.raw_data[o + M_FATIGUE] = fatigue & 0xFF
            m["fatigue"] = fatigue & 0xFF

        if morale is not None:
            self.raw_data[o + M_MORALE] = morale & 0xFF
            m["morale"] = morale & 0xFF

        if adv is not None:
            self.raw_data[o + M_ADV] = (self.raw_data[o + M_ADV] & 0xF0) | (adv & 0x0F)
            m["adv"] = adv & 0x0F

        self.draw_map()

    def add_member(self, squad, type_id):
        """Dodaje nową jednostkę do istniejącego oddziału (max 10)."""

        # Jako szablon 31-bajtowego rekordu kopiujemy blok dowódcy
        # (poprawna struktura), a następnie nadpisujemy typ, właściciela
        # i statystyki domyślne dla wybranego typu

        if self.raw_data is None:
            return None

        members = squad["members"]
        n = len(members)

        if n >= MAX_UNITS_PER_TILE:
            return None

        b = squad["offset"]
        o = b + 12 + SQUAD_MEMBER_STRIDE * n

        leader_o = members[0]["offset"]

        self.raw_data[o:o + SQUAD_MEMBER_STRIDE] = \
            self.raw_data[leader_o:leader_o + SQUAD_MEMBER_STRIDE]

        st = UNIT_STATS.get(type_id, {})

        self.raw_data[o + M_TYPE] = type_id & 0xFF
        self.raw_data[o + M_TYPE + 1] = 0
        self.raw_data[o + M_OWNER] = squad["owner"]

        self.raw_data[o + M_MOVE] = st.get("move", 20) & 0xFF
        self.raw_data[o + M_HP] = UNIT_HP_MAX
        self.raw_data[o + M_FATIGUE] = 0
        self.raw_data[o + M_MORALE] = st.get("morale", 10) & 0xFF
        self.raw_data[o + M_ADV] = self.raw_data[o + M_ADV] & 0xF0

        # Znacznik końca listy członków w kolejnym slocie (jeśli się mieści)
        if n + 1 < MAX_UNITS_PER_TILE:
            term = b + 12 + SQUAD_MEMBER_STRIDE * (n + 1)
            self.raw_data[term] = 0xFF
            self.raw_data[term + 1] = 0xFF

        new_m = {
            "type": type_id,
            "offset": o,
            "move": self.raw_data[o + M_MOVE],
            "hp": UNIT_HP_MAX,
            "fatigue": 0,
            "morale": self.raw_data[o + M_MORALE],
            "adv": self.raw_data[o + M_ADV] & 0x0F,
        }

        members.append(new_m)
        self.draw_map()

        return new_m

    def create_squad(self, x, y, owner, type_id):
        """Tworzy nowy oddział na pustym polu (x,y) dla danego koloru.

        Kopiuje slot-szablon tego samego właściciela (poprawna struktura
        nagłówka i danych pomocniczych), po czym ustawia pozycje, właściciela
        i jedną jednostkę z domyślnymi statystykami.
        """
        if self.raw_data is None:
            return None
        if not (0 <= x < self.width and 0 <= y < self.height):
            return None
        if self.squad_at(x, y) is not None:
            return None

        b = self._find_free_slot()
        if b is None:
            return None

        template = self._template_slot(owner)
        if template is not None:
            self.raw_data[b:b + SQUAD_SLOT] = \
                self.raw_data[template:template + SQUAD_SLOT]
        else:
            for i in range(SQUAD_SLOT):
                self.raw_data[b + i] = 0

        # Nagłówek oddziału.
        self.raw_data[b + 6] = x & 0xFF
        self.raw_data[b + 7] = (x >> 8) & 0xFF
        self.raw_data[b + 8] = y & 0xFF
        self.raw_data[b + 9] = (y >> 8) & 0xFF
        self.raw_data[b + 10] = owner
        self.raw_data[b + 11] = 0

        # Pierwsza (i jedyna) jednostka.
        o = b + 12
        st = UNIT_STATS.get(type_id, {})
        self.raw_data[o + M_TYPE] = type_id & 0xFF
        self.raw_data[o + M_TYPE + 1] = 0
        self.raw_data[o + M_OWNER] = owner
        self.raw_data[o + M_MOVE] = st.get("move", 20) & 0xFF
        self.raw_data[o + M_HP] = UNIT_HP_MAX
        self.raw_data[o + M_FATIGUE] = 0
        self.raw_data[o + M_MORALE] = st.get("morale", 10) & 0xFF
        self.raw_data[o + M_ADV] = self.raw_data[o + M_ADV] & 0xFF

        # Znacznik końca listy członków po pierwszej jednostce.
        term = b + 12 + SQUAD_MEMBER_STRIDE
        self.raw_data[term] = 0xFF
        self.raw_data[term + 1] = 0xFF

        reveal_fog_area(self.raw_data, x, y, owner)

        k = (b - SQUAD_SLOT) // SQUAD_SLOT
        set_unit_index_cell(self.raw_data,x,y,k)

        squad = {
            "x": x,
            "y": y,
            "offset": b,
            "owner": owner,
            "color": owner + 1,
            "members": [{
                "type": type_id,
                "offset": o,
                "move": self.raw_data[o + M_MOVE],
                "hp": UNIT_HP_MAX,
                "fatigue": 0,
                "morale": self.raw_data[o + M_MORALE],
                "adv": self.raw_data[o + M_ADV] & 0xFF,
            }],
        }
        self.units.append(squad)
        self.draw_map()
        return squad

    def _template_slot(self, owner):
        """Zwraca offset aktywnego oddziału jako szablon (preferuje tego samego
        właściciela), albo None jeśli nie ma żadnego."""
        same = [s["offset"] for s in self.units if s["owner"] == owner]
        if same:
            return same[0]
        if self.units:
            return self.units[0]["offset"]
        return None

    def _find_free_slot(self):
        """Znajduje pierwszy wolny slot w siatce oddziałów (nieaktywny)."""
        n = len(self.raw_data)
        used = [s["offset"] for s in self.units]
        kmax = (n - UNIT_REC_SIZE - SQUAD_ANCHOR) // SQUAD_SLOT
        for k in range(kmax + 1):
            b = SQUAD_ANCHOR + k * SQUAD_SLOT
            if b < UNIT_SECTION_OFFSET:
                continue
            if b + SQUAD_SLOT > n:
                break
            if b in used:
                continue
            return b
        return None

    def remove_member(self, squad, idx):
        """Usuwa jednostkę o indeksie idx z oddziału. Jeśli była ostatnia,
        cały oddział jest kasowany (slot oznaczany jako pusty)."""
        if self.raw_data is None:
            return
        members = squad["members"]
        if idx < 0 or idx >= len(members):
            return
        n = len(members)
        if n <= 1:
            self.remove_squad(squad)
            return

        b = squad["offset"]
        # Przesuwamy rekordy za usuwanym o jeden slot (31 B) w górę.
        first = b + 12 + SQUAD_MEMBER_STRIDE * idx
        src = b + 12 + SQUAD_MEMBER_STRIDE * (idx + 1)
        end = b + 12 + SQUAD_MEMBER_STRIDE * n
        self.raw_data[first:first + (end - src)] = self.raw_data[src:end]

        # Nowy ostatni slot -> znacznik końca listy.
        term = b + 12 + SQUAD_MEMBER_STRIDE * (n - 1)
        self.raw_data[term] = 0xFF
        self.raw_data[term + 1] = 0xFF

        del members[idx]
        for j, m in enumerate(members):
            m["offset"] = b + 12 + SQUAD_MEMBER_STRIDE * j
        self.draw_map()

    def remove_squad(self, squad):
        """Kasuje oddział - oznacza slot jako pusty (FFFF + pozycja 0,0)."""
        if self.raw_data is None:
            return
        b = squad["offset"]
        self.raw_data[b + 6] = 0
        self.raw_data[b + 7] = 0
        self.raw_data[b + 8] = 0
        self.raw_data[b + 9] = 0
        self.raw_data[b + 12] = 0xFF
        self.raw_data[b + 13] = 0xFF
        set_unit_index_cell(self.raw_data, squad["x"], squad["y"], UNIT_INDEX_EMPTY)
        if squad in self.units:
            self.units.remove(squad)
            self.draw_map()

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
            self.raw_data = bytearray(f.read())
        self.units = find_units_in_data(self.raw_data)
        self.buildings = find_buildings_in_data(self.raw_data)
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
        if self.unit_editor:
            self.unit_editor.load_squad(x, y, self.squad_at(x, y))

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
    def save_dat_patch(self, output_path):
        if self.raw_data is not None:
            data = bytearray(self.raw_data)
        else:
            with open(self.current_path, "rb") as f:
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
        for i, m in enumerate(members):
            type_id = m["type"]
            name = UNIT_NAMES.get(type_id, f"typ {type_id}")
            role = "dowodca" if i == 0 else f"jednostka { i + 1}"
            item = QListWidgetItem(f"{name} {role}")
            pix = self.editor._unit_pixmap(type_id, color, 0)
            if pix is not None:
                item.setIcon(QIcon(pix))
            self.list.addItem(item)


class UnitEditorPanel(QDockWidget):
    def __init__(self, editor):
        super().__init__("Edytor jednostek")
        self.editor = editor
        editor.unit_editor = self
        self.squad = None
        self.cell = None
        self._loading = False

        widget = QWidget()
        root = QVBoxLayout(widget)

        self.header = QLabel("Brak zaznaczenia")
        self.header.setWordWrap(True)
        root.addWidget(self.header)

        self.list = QListWidget()
        self.list.setIconSize(QSize(32, 32))
        self.list.currentRowChanged.connect(self._on_row_changed)
        root.addWidget(self.list)

        form_box = QGroupBox("Statystyki jednostki")
        form = QFormLayout(form_box)

        self.type_combo = QComboBox()
        for tid in sorted(UNIT_TYPES.keys()):
            self.type_combo.addItem(UNIT_NAMES.get(tid, f"typ {tid}"), tid)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        form.addRow("Typ", self.type_combo)

        self.hp_spin = QSpinBox()
        self.hp_spin.setRange(0, 100)
        form.addRow("HP", self.hp_spin)

        self.move_spin = QSpinBox()
        self.move_spin.setRange(0, 255)
        form.addRow("Ruch (PA)", self.move_spin)

        self.morale_spin = QSpinBox()
        self.morale_spin.setRange(0, 255)
        form.addRow("Morale", self.morale_spin)

        self.fatigue_spin = QSpinBox()
        self.fatigue_spin.setRange(0, 255)
        form.addRow("Zmęczenie", self.fatigue_spin)

        self.adv_spin = QSpinBox()
        self.adv_spin.setRange(0, 15)
        form.addRow("Zaawansowanie", self.adv_spin)

        root.addWidget(form_box)

        self.base_label = QLabel("")
        self.base_label.setWordWrap(True)
        root.addWidget(self.base_label)

        btns = QHBoxLayout()
        self.apply_btn = QPushButton("Zastosuj")
        self.apply_btn.clicked.connect(self._apply)
        btns.addWidget(self.apply_btn)

        self.default_btn = QPushButton("Domyślne statystyki")
        self.default_btn.clicked.connect(self._fill_defaults)
        btns.addWidget(self.default_btn)
        self.remove_btn = QPushButton("Usun jednostke")
        self.remove_btn.clicked.connect(self._remove)
        btns.addWidget(self.remove_btn)
        root.addLayout(btns)

        add_box = QHBoxLayout()
        self.add_type = QComboBox()
        for tid in sorted(UNIT_TYPES.keys()):
            self.add_type.addItem(UNIT_NAMES.get(tid, f"typ {tid}"), tid)
        add_box.addWidget(self.add_type)

        self.add_btn = QPushButton("Dodaj jednostkę")
        self.add_btn.clicked.connect(self._add)
        add_box.addWidget(self.add_btn)
        root.addLayout(add_box)

        self.create_box = QGroupBox("Nowy oddzial (na pustym polu)")
        create_form = QFormLayout(self.create_box)
        self.owner_combo = QComboBox()
        for i, oname in enumerate(OWNER_NAMES):
            self.owner_combo.addItem(oname, i)
        create_form.addRow("Kolor", self.owner_combo)
        self.new_type_combo = QComboBox()
        for tid in sorted(UNIT_TYPES.keys()):
            self.new_type_combo.addItem(UNIT_NAMES.get(tid, f"typ {tid}"), tid)
        create_form.addRow("Typ", self.new_type_combo)
        self.create_btn = QPushButton("Utworz oddzial tutaj")
        self.create_btn.clicked.connect(self._create)
        create_form.addRow(self.create_btn)
        root.addWidget(self.create_box)

        root.addStretch(1)
        self.setWidget(widget)
        self._set_form_enabled(False)

    def _set_form_enabled(self, on):
        for w in (self.type_combo, self.hp_spin, self.move_spin,
                  self.morale_spin, self.fatigue_spin, self.adv_spin,
                  self.apply_btn, self.default_btn, self.remove_btn):
            w.setEnabled(on)

    def load_squad(self, x, y, squad):
        self.cell = (x, y)
        self.squad = squad
        self._loading = True
        self.list.clear()
        has_cell = 0 <=x < GRID_W and 0 <= y < GRID_H
        if squad is None:
            self.header.setText(f"Kafelek({x},{y}): brak oddziału")
            self.base_label.setText("")
            self.add_btn.setEnabled(False)
            self.add_type.setEnabled(False)
            self._set_form_enabled(False)
            self._set_create_enabled(has_cell)
            self._loading = False
            return
        self._set_create_enabled(False)
        owner = squad["owner"]
        owner_name = OWNER_NAMES[owner] if owner < len(OWNER_NAMES) else str(owner)
        self.header.setText(
            f"Kafelek({x},{y}) - {owner_name}, "
            f"{len(squad['members'])} jednostek"
        )

        color = squad.get("color", DEFAULT_UNIT_COLOR)
        for i, m in enumerate(squad["members"]):
            name = UNIT_NAMES.get(m["type"], f"typ {m['type']}")
            role = "dowodca" if i == 0 else f"jednostka {i + 1}"
            item = QListWidgetItem(f"{name} ({role})")
            pix = self.editor._unit_pixmap(m["type"], color, 0)
            if pix is not None:
                item.setIcon(QIcon(pix))
            self.list.addItem(item)

        can_add = len(squad["members"]) < MAX_UNITS_PER_TILE
        self.add_type.setEnabled(can_add)
        self.add_btn.setEnabled(can_add)
        self._loading = False

        if squad["members"]:
            self.list.setCurrentRow(0)
        else:
            self._set_form_enabled(False)

    def _set_create_enabled(self, on):
        self.owner_combo.setEnabled(on)
        self.new_type_combo.setEnabled(on)
        self.create_btn.setEnabled(on)

    def _on_row_changed(self, row):
        if self._loading:
            return
        if self.squad is None or row < 0 or row >= len(self.squad["members"]):
            self._set_form_enabled(False)
            return

        self._set_form_enabled(True)
        m = self.squad["members"][row]
        self._loading = True
        self.type_combo.setCurrentIndex(self.type_combo.findData(m["type"]))
        self.hp_spin.setValue(m["hp"])
        self.move_spin.setValue(m["move"])
        self.morale_spin.setValue(m["morale"])
        self.fatigue_spin.setValue(m["fatigue"])
        self.adv_spin.setValue(m["adv"])
        self._loading = False
        self._update_base_label(m["type"])

    def _update_base_label(self, type_id):
        st = UNIT_STATS.get(type_id)
        if not st:
            self.base_label.setText("")
            return
        self.base_label.setText(
            f"Bazowo (wg strony): atak {st['attack']}, pancerz {st['armor']}, "
            f"dystans {st['ranged']}. Atak/pancerz/dystans wynikają z typu i "
            f"zaawansowania - nie są zapisywane osobno na jednostce."
        )

    def _on_type_changed(self, _idx):
        tid = self.type_combo.currentData()
        if tid is not None:
            self._update_base_label(tid)

    def _fill_defaults(self):
        tid = self.type_combo.currentData()
        st = UNIT_STATS.get(tid, {})
        self.hp_spin.setValue(UNIT_HP_MAX)
        self.move_spin.setValue(st.get("move", 20))
        self.morale_spin.setValue(st.get("morale", 10))
        self.fatigue_spin.setValue(0)
        self.adv_spin.setValue(0)

    def _apply(self):
        row = self.list.currentRow()
        if self.squad is None or row < 0:
            return
        type_id = self.type_combo.currentData()
        self.editor.update_member(
            self.squad, row,
            type_id=type_id,
            hp=self.hp_spin.value(),
            move=self.move_spin.value(),
            morale=self.morale_spin.value(),
            fatigue=self.fatigue_spin.value(),
            adv=self.adv_spin.value(),
        )

    def _add(self):
        if self.squad is None:
            return
        tid = self.add_type.currentData()
        m = self.editor.add_member(self.squad, tid)
        if m is None:
            return
        self.load_squad(self.cell[0], self.cell[1], self.squad)
        self.list.setCurrentRow(len(self.squad["members"]) - 1)

    def _remove(self):
        row = self.list.currentRow()
        if self.squad is None or row < 0:
            return
        x, y = self.cell
        self.editor.remove_member(self.squad, row)
        self.editor.select_cell(x,y)

    def _create(self):
        if self.cell is None:
            return
        x, y = self.cell
        owner = self.owner_combo.currentData()
        tid = self.new_type_combo.currentData()
        squad = self.editor.create_squad(x, y, owner, tid)
        if squad is None:
            return
        self.editor.select_cell(x,y)


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

        self.unit_editor = UnitEditorPanel(editor)
        self.addDockWidget(Qt.RightDockWidgetArea, self.unit_editor)

        self.tabifyDockWidget(self.inspector, self.squad_panel)
        self.tabifyDockWidget(self.squad_panel, self.unit_editor)

        locked = QDockWidget.DockWidgetFeature.NoDockWidgetFeatures
        for dock in (panel, self.inspector, self.squad_panel, self.unit_editor):
            dock.setFeatures(locked)

        self.setTabPosition(Qt.RightDockWidgetArea, QTabWidget.North)
        self.inspector.raise_()

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
        self.setWindowTitle(f"Clash Map Editor - {os.path.basename(path)}")

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
        self.editor.save_dat_patch(out)
        print(f"PATCH SAVED -> {out}")


# ---------------- MAIN ----------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("windows11"))

    textures = load_textures(palette_folder(DEFAULT_PALETTE))

    editor = MapEditor(GRID_W, GRID_H, textures)
    editor.load_file("1.DAT")

    panel = TexturePanel(textures, editor.set_selected_texture)

    window = MainWindow(editor, panel)
    window.resize(1400, 900)
    window.show()

    sys.exit(app.exec())