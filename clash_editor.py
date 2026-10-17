import math
import os
import sys

from PySide6.QtWidgets import (
    QApplication, QStyleFactory, QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsSimpleTextItem,
    QDockWidget, QListWidget, QListWidgetItem,
    QLabel, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QMainWindow, QToolBar, QSpinBox, QLineEdit, QCheckBox, QPushButton,
    QGroupBox, QFileDialog, QComboBox, QTabWidget, QScrollArea, QPlainTextEdit
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

# ---- Rekord budynku (467 B) - pola ustalone z kodu gry (clash95.exe) ----
# Offsety wzgledem poczatku rekordu.
B_X = 0x00
B_Y = 0x01
B_OWNER = 0x02            # wlasciciel -> kolor
B_STYLE = 0x03            # styl grafiki (klucz cache grafiki, zwykle = wlasciciel)
B_TYPE = 0x04             # 0 = wieza, 1 = twierdza, 2 = zamek, 0xFF = pusty
B_NAME = 0x05             # nazwa ASCII zakonczona 0x00 (do 0x0F)
B_NAME_LEN = 11           # 0x05..0x0F wlacznie z 0x00
B_BUILD = 0x10            # i16: pozostale punkty budowy (0 = gotowy, -1 = brak)
B_GARRISON = 0x12         # 12 jednostek po 31 B; typ 0xFFFF = pusty slot
B_GARRISON_SLOTS = 12
B_UNIT_STATE = 0x186      # 12 B: stan leczenia/szkolenia kazdej jednostki garnizonu
B_LICENCES = 0x192        # 12 B: typy jednostek z licencja produkcji, 0xFF = brak
B_LICENCE_SLOTS = 12
B_PROD_SLOT = 0x19E       # indeks licencji w produkcji, 0xFF = brak
B_PROD_TURNS = 0x19F      # tury do konca produkcji
B_FLAGS = 0x1A0           # bity budynkow w zamku
B_WALL_LEVEL = 0x1A5      # poziom murow 0..2
B_WALL_SEGMENTS = 0x1A6   # 7 B: wytrzymalosc segmentow murow (0..100)
B_WALL_SEG_COUNT = 7
B_WALL_UPGRADE = 0x1AD    # tury do konca rozbudowy murow (0 = brak)
B_PEASANTS = 0x1AE        # u16, mlodsze 12 bitow = liczba chlopow
B_SATISFACTION = 0x1B2    # i8: zadowolenie
B_TAX = 0x1B4             # mlodsze 6 bitow = podatek
B_GOLD = 0x1B6            # u32: zloto w skarbcu
B_LEVEL = 0x1BC           # mlodsze 3 bity = poziom zaawansowania
B_PRISONERS = 0x1BD       # 3 sloty po 6 B; bajt 0 = 0xFF -> pusty
B_PRISONER_SLOTS = 3
B_PRISONER_SIZE = 6

BUILDING_TYPE_NAMES = {0: "Wieża", 1: "Twierdza", 2: "Zamek"}
BUILDING_BUILD_MAX = {0: 100, 1: 300, 2: 300}

# (bit, nazwa) - kolejnosc jak w debugowym wydruku gry
CASTLE_FACILITIES = [
    (0x01, "Szpital"),
    (0x02, "Koszary"),
    (0x04, "Warsztat"),
    (0x08, "Szkoła"),
    (0x10, "Kuźnia"),
]

# Wiezniami moga byc tylko pojmani potomkowie dowodcy (typy 33/34);
# gra umieszcza ich wylacznie w budynkach typu 2.
PRISONER_TYPES = {33: "Syn dowódcy", 34: "Córka dowódcy"}
PRISONER_MAX_TURNS = 10   # gra usuwa wieznia, gdy licznik osiagnie 10

# Wymogi budynkow do produkcji (tablice w clash95.exe)
NEEDS_FORGE = {2, 4, 6, 5, 7, 8, 11, 14}
NEEDS_WORKSHOP = {9, 10, 12, 13, 15}

# Minimalny poziom zaawansowania do produkcji: typ -> (gdy typ budynku != 2,
# gdy typ budynku == 2). 5 = nigdy (poziom maks. to 4). Tabela typow w exe,
# bajty +0x4C / +0x4B rekordu typu jednostki.
UNIT_TECH_REQ = {
    0: (1, 1), 1: (1, 1), 2: (1, 5), 3: (1, 1), 4: (1, 5), 5: (1, 1),
    6: (2, 5), 7: (1, 5), 8: (2, 2), 9: (1, 1), 10: (1, 5), 11: (2, 5),
    12: (2, 2), 13: (1, 1), 14: (2, 2), 15: (1, 1), 16: (1, 1), 17: (1, 1),
    18: (2, 2), 19: (2, 2), 20: (2, 5), 21: (2, 5), 22: (2, 2), 23: (3, 3),
    24: (3, 5), 25: (3, 3), 26: (2, 2), 27: (3, 3), 28: (3, 3), 29: (1, 5),
    30: (3, 5),
}
CASTLE_MAX_LEVEL = 4


def can_produce(castle, type_id):
    """Odtworzenie funkcji gry CanProduce (0x43ED20 w clash95.exe)."""
    t = castle.btype
    if t == 0 or type_id not in UNIT_TECH_REQ:
        return False
    req = UNIT_TECH_REQ[type_id][1 if t == 2 else 0]
    if castle.level < req:
        return False
    if type_id in NEEDS_FORGE and not castle.has_facility(0x10):
        return False
    if type_id in NEEDS_WORKSHOP and not castle.has_facility(0x04):
        return False
    return True

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
        for b in data[o + B_NAME:o + B_NAME + B_NAME_LEN]:
            if 32<=b < 127:
                name.append(chr(b))
            else:
                break
        out.append({
            "x": x, "y": y, "type": t, "owner": owner,
            "offset": o, "index": k - 1, "name": "".join(name),
        })
    return out


def building_size(btype):
    return BUILDING_TYPE_TEX.get(btype, BUILDING_DEFAULT_TEX)[0]


class Castle:
    """Widok na rekord budynku w buforze pliku - wszystkie zapisy ida
    bezposrednio do `data`, wiec zapis pliku nie wymaga dodatkowych krokow."""

    def __init__(self, data, offset):
        self.data = data
        self.o = offset

    # --- prymitywy
    def u8(self, off):
        return self.data[self.o + off]

    def set_u8(self, off, v):
        self.data[self.o + off] = v & 0xFF

    def i8(self, off):
        v = self.u8(off)
        return v - 256 if v >= 128 else v

    def u16(self, off):
        p = self.o + off
        return self.data[p] | (self.data[p + 1] << 8)

    def set_u16(self, off, v):
        p = self.o + off
        v &= 0xFFFF
        self.data[p] = v & 0xFF
        self.data[p + 1] = v >> 8

    def u32(self, off):
        p = self.o + off
        return int.from_bytes(self.data[p:p + 4], "little")

    def set_u32(self, off, v):
        p = self.o + off
        self.data[p:p + 4] = (v & 0xFFFFFFFF).to_bytes(4, "little")

    def set_bits(self, off, mask, v):
        self.set_u8(off, (self.u8(off) & ~mask) | (v & mask))

    def raw(self):
        return bytes(self.data[self.o:self.o + BUILDING_REC_SIZE])

    # --- pola podstawowe
    @property
    def x(self):
        return self.u8(B_X)

    @property
    def y(self):
        return self.u8(B_Y)

    @property
    def btype(self):
        return self.u8(B_TYPE)

    @property
    def name(self):
        raw = self.data[self.o + B_NAME:self.o + B_NAME + B_NAME_LEN]
        return bytes(raw).split(b"\0", 1)[0].decode("latin-1")

    def set_name(self, name):
        enc = name.encode("ascii", "replace")[:B_NAME_LEN - 1]
        buf = enc + b"\0" * (B_NAME_LEN - len(enc))
        p = self.o + B_NAME
        self.data[p:p + B_NAME_LEN] = buf

    def set_owner(self, owner, with_style=True):
        old = self.u8(B_OWNER)
        self.set_u8(B_OWNER, owner)
        if with_style:
            self.set_u8(B_STYLE, owner)
        # jednostki garnizonu naleza do wlasciciela zamku
        for slot in range(B_GARRISON_SLOTS):
            o = self.unit_offset(slot)
            if self.unit_type(slot) is not None and self.data[o + M_OWNER] == old:
                self.data[o + M_OWNER] = owner & 0xFF

    @property
    def build_left(self):
        v = self.u16(B_BUILD)
        return v - 0x10000 if v >= 0x8000 else v

    # --- budynki w zamku
    def has_facility(self, bit):
        return bool(self.u8(B_FLAGS) & bit)

    def set_facility(self, bit, on):
        self.set_bits(B_FLAGS, bit, bit if on else 0)

    # --- gospodarka
    @property
    def gold(self):
        return self.u32(B_GOLD)

    @property
    def peasants(self):
        return self.u16(B_PEASANTS) & 0x0FFF

    def set_peasants(self, n):
        self.set_u16(B_PEASANTS, (self.u16(B_PEASANTS) & 0xF000) | (n & 0x0FFF))

    @property
    def tax(self):
        return self.u8(B_TAX) & 0x3F

    @property
    def level(self):
        return self.u8(B_LEVEL) & 0x07

    def set_level(self, lvl):
        self.set_bits(B_LEVEL, 0x07, lvl)

    def set_wall_level(self, lvl):
        """Ustawia poziom murow; mury >0 dostaja pelna wytrzymalosc segmentow."""
        self.set_u8(B_WALL_LEVEL, lvl)
        self.set_u8(B_WALL_UPGRADE, 0)
        for i in range(B_WALL_SEG_COUNT):
            cur = self.u8(B_WALL_SEGMENTS + i)
            if lvl > 0 and cur == 0:
                self.set_u8(B_WALL_SEGMENTS + i, 100)

    # --- garnizon
    def unit_offset(self, slot):
        return self.o + B_GARRISON + slot * SQUAD_MEMBER_STRIDE

    def unit_type(self, slot):
        o = self.unit_offset(slot)
        if self.data[o + 1] != 0 or self.data[o] not in UNIT_VALID_TYPES:
            return None
        return self.data[o]

    def garrison(self):
        """Lista (slot, dict) dla zajetych slotow (sloty moga byc rzadkie)."""
        out = []
        for slot in range(B_GARRISON_SLOTS):
            t = self.unit_type(slot)
            if t is None:
                continue
            o = self.unit_offset(slot)
            out.append((slot, {
                "type": t, "offset": o,
                "move": self.data[o + M_MOVE], "hp": self.data[o + M_HP],
                "fatigue": self.data[o + M_FATIGUE],
                "morale": self.data[o + M_MORALE],
                "adv": self.data[o + M_ADV] & 0x0F,
            }))
        return out

    def free_slot(self):
        for slot in range(B_GARRISON_SLOTS):
            if self.unit_type(slot) is None:
                return slot
        return None

    def add_unit(self, type_id, template=None):
        slot = self.free_slot()
        if slot is None:
            return None
        o = self.unit_offset(slot)
        if template is None:
            used = self.garrison()
            template = bytes(self.data[used[0][1]["offset"]:used[0][1]["offset"] + SQUAD_MEMBER_STRIDE]) if used else None
        if template is not None:
            self.data[o:o + SQUAD_MEMBER_STRIDE] = template
        else:
            self.data[o:o + SQUAD_MEMBER_STRIDE] = bytes(SQUAD_MEMBER_STRIDE)
        st = UNIT_STATS.get(type_id, {})
        self.data[o + M_TYPE] = type_id & 0xFF
        self.data[o + M_TYPE + 1] = 0
        self.data[o + M_OWNER] = self.u8(B_OWNER)
        self.data[o + M_MOVE] = st.get("move", 20) & 0xFF
        self.data[o + M_HP] = UNIT_HP_MAX
        self.data[o + M_FATIGUE] = 0
        self.data[o + M_MORALE] = st.get("morale", 10) & 0xFF
        self.data[o + M_ADV] = self.data[o + M_ADV] & 0xF0
        self.set_u8(B_UNIT_STATE + slot, 0)
        return slot

    def update_unit(self, slot, type_id, hp, move, morale, fatigue, adv):
        o = self.unit_offset(slot)
        self.data[o + M_TYPE] = type_id & 0xFF
        self.data[o + M_TYPE + 1] = 0
        self.data[o + M_HP] = hp & 0xFF
        self.data[o + M_MOVE] = move & 0xFF
        self.data[o + M_MORALE] = morale & 0xFF
        self.data[o + M_FATIGUE] = fatigue & 0xFF
        self.data[o + M_ADV] = (self.data[o + M_ADV] & 0xF0) | (adv & 0x0F)

    def remove_unit(self, slot):
        o = self.unit_offset(slot)
        self.data[o] = 0xFF
        self.data[o + 1] = 0xFF
        self.set_u8(B_UNIT_STATE + slot, 0)

    def clear_garrison(self):
        for slot in range(B_GARRISON_SLOTS):
            if self.unit_type(slot) is not None:
                self.remove_unit(slot)

    # --- licencje / produkcja
    def licences(self):
        out = []
        for i in range(B_LICENCE_SLOTS):
            v = self.u8(B_LICENCES + i)
            out.append(None if v == 0xFF else v)
        return out

    def set_licences(self, types):
        types = [t for t in types if t is not None][:B_LICENCE_SLOTS]
        old = self.licences()
        prod = self.u8(B_PROD_SLOT)
        prod_type = old[prod] if prod < B_LICENCE_SLOTS else None
        for i in range(B_LICENCE_SLOTS):
            self.set_u8(B_LICENCES + i, types[i] if i < len(types) else 0xFF)
        # produkcja wskazuje indeks licencji - utrzymujemy ten sam typ
        if prod_type is not None and prod_type in types:
            self.set_u8(B_PROD_SLOT, types.index(prod_type))
        else:
            self.set_u8(B_PROD_SLOT, 0xFF)
            self.set_u8(B_PROD_TURNS, 0)

    # --- wiezniowie
    def prisoners(self):
        out = []
        for i in range(B_PRISONER_SLOTS):
            p = B_PRISONERS + i * B_PRISONER_SIZE
            if self.u8(p) == 0xFF:
                out.append(None)
            else:
                out.append({"type": self.u8(p), "owner": self.u8(p + 1),
                             "turns": self.u8(p + 2)})
        return out

    def set_prisoner(self, i, prisoner):
        p = B_PRISONERS + i * B_PRISONER_SIZE
        if prisoner is None:
            self.set_u8(p, 0xFF)
            for k in range(1, B_PRISONER_SIZE):
                self.set_u8(p + k, 0)
            return
        self.set_u8(p, prisoner["type"])
        self.set_u8(p + 1, prisoner["owner"])
        self.set_u8(p + 2, prisoner.get("turns", 0))
        self.set_u8(p + 3, 0)


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
        self.castle_editor = None
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

        # liczba jednostek garnizonu w prawym dolnym rogu budynku
        if self.raw_data is not None and building.get("offset"):
            n = len(Castle(self.raw_data, building["offset"]).garrison())
            if n:
                self._draw_squad_count(bx + size - 1, by + size - 1, n)

    def building_at(self, x, y):
        for b in self.buildings:
            s = building_size(b["type"])
            if b["x"] <= x < b["x"] + s and b["y"] <= y < b["y"] + s:
                return b
        return None

    def castle_changed(self, building):
        """Odswieza dane budynku po edycji w panelu zamku."""
        c = Castle(self.raw_data, building["offset"])
        building["owner"] = c.u8(B_OWNER)
        building["type"] = c.btype
        building["name"] = c.name
        self.draw_map()

    def set_building_owner(self, building, owner, with_style=True):
        c = Castle(self.raw_data, building["offset"])
        c.set_owner(owner, with_style)
        s = building_size(c.btype)
        reveal_fog_area(self.raw_data, c.x + s // 2, c.y + s // 2, owner)
        self.castle_changed(building)


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

        k = (b - SQUAD_ANCHOR) // SQUAD_SLOT
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

    def goto_next_building(self, owner=None):
        blds = [b for b in self.buildings if owner is None or b["owner"] == owner]
        if not blds:
            return None
        blds.sort(key=lambda b: (b["y"], b["x"]))
        if getattr(self, "_bnav_owner", "unset") != owner:
            self._bnav_owner = owner
            self._bnav_index = -1
        self._bnav_index = (getattr(self, "_bnav_index", -1) + 1) % len(blds)
        b = blds[self._bnav_index]
        self.select_cell(b["x"], b["y"])
        self.centerOn((b["x"] + 1) * TILE_SIZE, (b["y"] + 1) * TILE_SIZE)
        return b

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
        if self.castle_editor:
            self.castle_editor.load_building(x, y, self.building_at(x, y))

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


# ---------------- CASTLE EDITOR ---------------
def _unit_combo(include_none=False, none_label="(brak)"):
    cb = QComboBox()
    if include_none:
        cb.addItem(none_label, None)
    for tid in sorted(UNIT_TYPES.keys()):
        cb.addItem(f"{tid:2d} {UNIT_NAMES.get(tid, f'typ {tid}')}", tid)
    return cb


def _owner_combo():
    cb = QComboBox()
    for i, oname in enumerate(OWNER_NAMES):
        cb.addItem(oname, i)
    return cb


class CastleEditorPanel(QDockWidget):
    """Edycja rekordu budynku (zamek / twierdza / wieza)."""

    def __init__(self, editor):
        super().__init__("Zamek")
        self.editor = editor
        editor.castle_editor = self
        self.building = None
        self.castle = None
        self.cell = None
        self._loading = False

        outer = QWidget()
        root = QVBoxLayout(outer)
        self.header = QLabel("Brak zaznaczenia")
        self.header.setWordWrap(True)
        root.addWidget(self.header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_general_tab(), "Ogólne")
        self.tabs.addTab(self._build_garrison_tab(), "Garnizon")
        self.tabs.addTab(self._build_licence_tab(), "Licencje")
        self.tabs.addTab(self._build_prisoner_tab(), "Więźniowie")
        self.tabs.addTab(self._build_raw_tab(), "Surowe")
        root.addWidget(self.tabs)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(outer)
        self.setWidget(scroll)
        self.tabs.setEnabled(False)

    # ---------- budowa zakladek
    def _build_general_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        box = QGroupBox("Budynek")
        f = QFormLayout(box)
        self.name_edit = QLineEdit()
        self.name_edit.setMaxLength(B_NAME_LEN - 1)
        f.addRow("Nazwa", self.name_edit)
        self.type_combo = QComboBox()
        for t, n in BUILDING_TYPE_NAMES.items():
            self.type_combo.addItem(n, t)
        f.addRow("Typ", self.type_combo)
        self.owner_combo = _owner_combo()
        f.addRow("Kolor gracza", self.owner_combo)
        self.style_check = QCheckBox("Zmień też styl grafiki (bajt +3)")
        self.style_check.setChecked(True)
        f.addRow("", self.style_check)
        self.level_spin = QSpinBox()
        self.level_spin.setRange(0, 7)
        self.level_spin.setToolTip(f"W grze 1..{CASTLE_MAX_LEVEL}")
        f.addRow("Poziom zaawansowania", self.level_spin)
        self.build_spin = QSpinBox()
        self.build_spin.setRange(-1, 300)
        self.build_spin.setToolTip("Pozostałe punkty budowy: 0 = budynek ukończony")
        f.addRow("Budowa (pozostało)", self.build_spin)
        lay.addWidget(box)

        fac = QGroupBox("Budynki w zamku")
        g = QGridLayout(fac)
        self.fac_checks = {}
        for i, (bit, name) in enumerate(CASTLE_FACILITIES):
            cb = QCheckBox(name)
            self.fac_checks[bit] = cb
            g.addWidget(cb, i // 2, i % 2)
        lay.addWidget(fac)

        eco = QGroupBox("Gospodarka")
        f2 = QFormLayout(eco)
        self.gold_spin = QSpinBox()
        self.gold_spin.setRange(0, 2_000_000_000)
        self.gold_spin.setSingleStep(100)
        f2.addRow("Złoto", self.gold_spin)
        self.peasant_spin = QSpinBox()
        self.peasant_spin.setRange(0, 0x0FFF)
        f2.addRow("Chłopi", self.peasant_spin)
        self.tax_spin = QSpinBox()
        self.tax_spin.setRange(0, 63)
        f2.addRow("Podatek", self.tax_spin)
        self.satisf_spin = QSpinBox()
        self.satisf_spin.setRange(-128, 127)
        f2.addRow("Zadowolenie", self.satisf_spin)
        lay.addWidget(eco)

        walls = QGroupBox("Mury")
        f3 = QFormLayout(walls)
        self.wall_spin = QSpinBox()
        self.wall_spin.setRange(0, 2)
        self.wall_spin.setToolTip("Gra pozwala rozbudować mury do poziomu min(2, poziom zamku - 1)")
        f3.addRow("Poziom murów", self.wall_spin)
        self.repair_check = QCheckBox("Napraw segmenty murów (100%)")
        f3.addRow("", self.repair_check)
        lay.addWidget(walls)

        self.general_apply = QPushButton("Zastosuj")
        self.general_apply.clicked.connect(self._apply_general)
        lay.addWidget(self.general_apply)
        lay.addStretch(1)
        return w

    def _build_garrison_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        self.gar_info = QLabel("")
        lay.addWidget(self.gar_info)
        self.gar_list = QListWidget()
        self.gar_list.setIconSize(QSize(32, 32))
        self.gar_list.currentRowChanged.connect(self._on_gar_row)
        lay.addWidget(self.gar_list)

        box = QGroupBox("Jednostka")
        f = QFormLayout(box)
        self.g_type = _unit_combo()
        f.addRow("Typ", self.g_type)
        self.g_hp = QSpinBox(); self.g_hp.setRange(0, 100)
        f.addRow("HP", self.g_hp)
        self.g_move = QSpinBox(); self.g_move.setRange(0, 255)
        f.addRow("Ruch (PA)", self.g_move)
        self.g_morale = QSpinBox(); self.g_morale.setRange(0, 255)
        f.addRow("Morale", self.g_morale)
        self.g_fatigue = QSpinBox(); self.g_fatigue.setRange(0, 255)
        f.addRow("Zmęczenie", self.g_fatigue)
        self.g_adv = QSpinBox(); self.g_adv.setRange(0, 15)
        f.addRow("Zaawansowanie", self.g_adv)
        lay.addWidget(box)

        row = QHBoxLayout()
        self.g_apply = QPushButton("Zastosuj")
        self.g_apply.clicked.connect(self._apply_unit)
        row.addWidget(self.g_apply)
        self.g_remove = QPushButton("Usuń")
        self.g_remove.clicked.connect(self._remove_unit)
        row.addWidget(self.g_remove)
        lay.addLayout(row)

        row2 = QHBoxLayout()
        self.g_add_type = _unit_combo()
        row2.addWidget(self.g_add_type)
        self.g_add = QPushButton("Dodaj")
        self.g_add.clicked.connect(self._add_unit)
        row2.addWidget(self.g_add)
        lay.addLayout(row2)

        row3 = QHBoxLayout()
        self.g_fill = QPushButton("Wypełnij do 12")
        self.g_fill.setToolTip("Dodaje jednostki wybranego typu aż do zapełnienia garnizonu")
        self.g_fill.clicked.connect(self._fill_garrison)
        row3.addWidget(self.g_fill)
        self.g_clear = QPushButton("Opróżnij garnizon")
        self.g_clear.clicked.connect(self._clear_garrison)
        row3.addWidget(self.g_clear)
        lay.addLayout(row3)
        lay.addStretch(1)
        return w

    def _build_licence_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("Typy jednostek, które zamek może produkować (maks. 12):"))
        grid = QGridLayout()
        self.lic_combos = []
        for i in range(B_LICENCE_SLOTS):
            cb = _unit_combo(include_none=True)
            cb.currentIndexChanged.connect(self._update_licence_warnings)
            self.lic_combos.append(cb)
            grid.addWidget(QLabel(f"{i + 1}."), i, 0)
            grid.addWidget(cb, i, 1)
        lay.addLayout(grid)
        self.lic_warn = QLabel("")
        self.lic_warn.setWordWrap(True)
        self.lic_warn.setStyleSheet("color: #b36b00;")
        lay.addWidget(self.lic_warn)

        prod = QGroupBox("Produkcja")
        f = QFormLayout(prod)
        self.prod_combo = QComboBox()
        f.addRow("Produkowana jednostka", self.prod_combo)
        self.prod_turns = QSpinBox()
        self.prod_turns.setRange(0, 255)
        f.addRow("Tury do końca", self.prod_turns)
        lay.addWidget(prod)

        row = QHBoxLayout()
        auto = QPushButton("Wszystkie dozwolone")
        auto.setToolTip("Wypełnia licencje typami, które zamek może produkować "
                        "przy obecnym poziomie i budynkach (reguły gry)")
        auto.clicked.connect(self._auto_licences)
        row.addWidget(auto)
        self.lic_apply = QPushButton("Zastosuj")
        self.lic_apply.clicked.connect(self._apply_licences)
        row.addWidget(self.lic_apply)
        lay.addLayout(row)
        lay.addStretch(1)
        return w

    def _build_prisoner_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        info = QLabel("Więźniami mogą być tylko pojmani potomkowie dowódcy. Gra trzyma "
                      "ich wyłącznie w budynkach typu Zamek (maks. 3).")
        info.setWordWrap(True)
        lay.addWidget(info)
        self.pr_rows = []
        for i in range(B_PRISONER_SLOTS):
            box = QGroupBox(f"Cela {i + 1}")
            f = QFormLayout(box)
            on = QCheckBox("Zajęta")
            t = QComboBox()
            for tid, n in PRISONER_TYPES.items():
                t.addItem(n, tid)
            o = _owner_combo()
            turns = QSpinBox()
            turns.setRange(0, PRISONER_MAX_TURNS - 1)
            f.addRow(on)
            f.addRow("Kto", t)
            f.addRow("Z rodu gracza", o)
            f.addRow("Tury w niewoli", turns)
            lay.addWidget(box)
            self.pr_rows.append((on, t, o, turns))
        self.pr_warn = QLabel("")
        self.pr_warn.setWordWrap(True)
        self.pr_warn.setStyleSheet("color: #b36b00;")
        lay.addWidget(self.pr_warn)
        self.pr_apply = QPushButton("Zastosuj")
        self.pr_apply.clicked.connect(self._apply_prisoners)
        lay.addWidget(self.pr_apply)
        lay.addStretch(1)
        return w

    def _build_raw_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        self.raw_view = QPlainTextEdit()
        self.raw_view.setReadOnly(True)
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        self.raw_view.setFont(font)
        lay.addWidget(self.raw_view)
        return w

    # ---------- ladowanie
    def load_building(self, x, y, building):
        self.cell = (x, y)
        self.building = building
        if building is None or self.editor.raw_data is None:
            self.castle = None
            self.header.setText(f"Kafelek ({x}, {y}): brak budynku")
            self.tabs.setEnabled(False)
            return
        self.castle = Castle(self.editor.raw_data, building["offset"])
        self.tabs.setEnabled(True)
        self.refresh()
        if self.editor.mode == "select":
            self.raise_()

    def refresh(self):
        c = self.castle
        if c is None:
            return
        self._loading = True
        tname = BUILDING_TYPE_NAMES.get(c.btype, f"typ {c.btype}")
        self.header.setText(
            f"{tname} „{c.name}” ({c.x}, {c.y}) - rekord #{self.building['index']}, "
            f"offset 0x{c.o:06X}"
        )
        # ogolne
        self.name_edit.setText(c.name)
        self.type_combo.setCurrentIndex(self.type_combo.findData(c.btype))
        # wieza 1x1 vs zamek/twierdza 2x2 - zmiana rozmiaru wymagalaby
        # przebudowy siatki zajetosci, wiec pozwalamy tylko 1 <-> 2
        for i in range(self.type_combo.count()):
            t = self.type_combo.itemData(i)
            item = self.type_combo.model().item(i)
            item.setEnabled(building_size(t) == building_size(c.btype))
        self.owner_combo.setCurrentIndex(self.owner_combo.findData(c.u8(B_OWNER)))
        self.style_check.setChecked(c.u8(B_STYLE) == c.u8(B_OWNER))
        self.level_spin.setValue(c.level)
        self.build_spin.setValue(c.build_left)
        for bit, cb in self.fac_checks.items():
            cb.setChecked(c.has_facility(bit))
        self.gold_spin.setValue(min(c.gold, self.gold_spin.maximum()))
        self.peasant_spin.setValue(c.peasants)
        self.tax_spin.setValue(c.tax)
        self.satisf_spin.setValue(c.i8(B_SATISFACTION))
        self.wall_spin.setValue(min(c.u8(B_WALL_LEVEL), 2))
        self.repair_check.setChecked(False)
        is_castle = c.btype != 0
        for wdg in list(self.fac_checks.values()) + [self.gold_spin, self.peasant_spin,
                                                     self.tax_spin, self.satisf_spin]:
            wdg.setEnabled(is_castle)
        # garnizon, licencje, wiezniowie
        self._refresh_garrison()
        for i, t in enumerate(c.licences()):
            self.lic_combos[i].setCurrentIndex(self.lic_combos[i].findData(t))
        self._refresh_production()
        for i, p in enumerate(c.prisoners()):
            on, t, o, turns = self.pr_rows[i]
            on.setChecked(p is not None)
            if p is not None:
                idx = t.findData(p["type"])
                t.setCurrentIndex(idx if idx >= 0 else 0)
                o.setCurrentIndex(max(0, o.findData(p["owner"])))
                turns.setValue(min(p["turns"], turns.maximum()))
        self.pr_warn.setText("" if c.btype == 2 else
                             "Uwaga: to nie jest Zamek - gra nie trzyma tu więźniów.")
        self._refresh_raw()
        self._loading = False
        self._update_licence_warnings()

    def _refresh_garrison(self, select_slot=None):
        c = self.castle
        self.gar_list.clear()
        self._gar_slots = []
        color = c.u8(B_OWNER) + 1
        for slot, m in c.garrison():
            name = UNIT_NAMES.get(m["type"], f"typ {m['type']}")
            item = QListWidgetItem(f"[{slot + 1:2d}] {name}  HP {m['hp']}  PA {m['move']}")
            pix = self.editor._unit_pixmap(m["type"], color, 0)
            if pix is not None:
                item.setIcon(QIcon(pix))
            self.gar_list.addItem(item)
            self._gar_slots.append((slot, m))
        n = len(self._gar_slots)
        self.gar_info.setText(f"Garnizon: {n} / {B_GARRISON_SLOTS}")
        self.g_add.setEnabled(n < B_GARRISON_SLOTS)
        self.g_fill.setEnabled(n < B_GARRISON_SLOTS)
        if select_slot is not None:
            for row, (slot, _) in enumerate(self._gar_slots):
                if slot == select_slot:
                    self.gar_list.setCurrentRow(row)
        elif self._gar_slots:
            self.gar_list.setCurrentRow(0)
        else:
            self._on_gar_row(-1)

    def _refresh_production(self):
        c = self.castle
        self.prod_combo.clear()
        self.prod_combo.addItem("(brak)", None)
        for i, t in enumerate(c.licences()):
            if t is not None:
                self.prod_combo.addItem(UNIT_NAMES.get(t, f"typ {t}"), i)
        prod = c.u8(B_PROD_SLOT)
        idx = self.prod_combo.findData(prod) if prod != 0xFF else 0
        self.prod_combo.setCurrentIndex(max(idx, 0))
        self.prod_turns.setValue(c.u8(B_PROD_TURNS))

    def _refresh_raw(self):
        raw = self.castle.raw()
        notes = {
            0x00: "x y wł styl typ nazwa", 0x10: "budowa | garnizon od 0x12",
            0x180: "stan jedn. od 0x186, licencje od 0x192", 0x1A0: "flagi, mury, chłopi, zadowolenie, podatek, złoto",
            0x1B0: "poziom 0x1BC, więźniowie od 0x1BD", 0x1C0: "",
        }
        lines = []
        for off in range(0, len(raw), 16):
            chunk = raw[off:off + 16]
            note = notes.get(off, "")
            lines.append(f"+{off:03X}: {chunk.hex(' ').upper():<47}  {note}")
        self.raw_view.setPlainText("\n".join(lines))

    def _after_change(self, select_slot=None):
        self.editor.castle_changed(self.building)
        self.refresh()
        if select_slot is not None:
            self._refresh_garrison(select_slot)

    # ---------- ogolne
    def _apply_general(self):
        c = self.castle
        if c is None:
            return
        c.set_name(self.name_edit.text())
        new_type = self.type_combo.currentData()
        if building_size(new_type) == building_size(c.btype):
            c.set_u8(B_TYPE, new_type)
        c.set_level(self.level_spin.value())
        c.set_u16(B_BUILD, self.build_spin.value())
        for bit, cb in self.fac_checks.items():
            c.set_facility(bit, cb.isChecked())
        c.set_u32(B_GOLD, self.gold_spin.value())
        c.set_peasants(self.peasant_spin.value())
        c.set_bits(B_TAX, 0x3F, self.tax_spin.value())
        c.set_u8(B_SATISFACTION, self.satisf_spin.value())
        if self.wall_spin.value() != c.u8(B_WALL_LEVEL):
            c.set_wall_level(self.wall_spin.value())
        if self.repair_check.isChecked():
            for i in range(B_WALL_SEG_COUNT):
                c.set_u8(B_WALL_SEGMENTS + i, 100)
        owner = self.owner_combo.currentData()
        if owner != c.u8(B_OWNER) or (self.style_check.isChecked() and c.u8(B_STYLE) != owner):
            self.editor.set_building_owner(self.building, owner, self.style_check.isChecked())
        self._after_change()

    # ---------- garnizon
    def _on_gar_row(self, row):
        on = 0 <= row < len(getattr(self, "_gar_slots", []))
        for wdg in (self.g_type, self.g_hp, self.g_move, self.g_morale,
                    self.g_fatigue, self.g_adv, self.g_apply, self.g_remove):
            wdg.setEnabled(on)
        if not on:
            return
        _, m = self._gar_slots[row]
        self.g_type.setCurrentIndex(self.g_type.findData(m["type"]))
        self.g_hp.setValue(m["hp"])
        self.g_move.setValue(m["move"])
        self.g_morale.setValue(m["morale"])
        self.g_fatigue.setValue(m["fatigue"])
        self.g_adv.setValue(m["adv"])

    def _apply_unit(self):
        row = self.gar_list.currentRow()
        if self.castle is None or row < 0:
            return
        slot, _ = self._gar_slots[row]
        self.castle.update_unit(slot, self.g_type.currentData(), self.g_hp.value(),
                                self.g_move.value(), self.g_morale.value(),
                                self.g_fatigue.value(), self.g_adv.value())
        self._after_change(slot)

    def _remove_unit(self):
        row = self.gar_list.currentRow()
        if self.castle is None or row < 0:
            return
        slot, _ = self._gar_slots[row]
        self.castle.remove_unit(slot)
        self._after_change()

    def _add_unit(self):
        if self.castle is None:
            return
        slot = self.castle.add_unit(self.g_add_type.currentData())
        if slot is not None:
            self._after_change(slot)

    def _fill_garrison(self):
        if self.castle is None:
            return
        t = self.g_add_type.currentData()
        while self.castle.add_unit(t) is not None:
            pass
        self._after_change()

    def _clear_garrison(self):
        if self.castle is None:
            return
        self.castle.clear_garrison()
        self._after_change()

    # ---------- licencje
    def _selected_licences(self):
        return [cb.currentData() for cb in self.lic_combos]

    def _update_licence_warnings(self, *_):
        if self._loading or self.castle is None:
            return
        bad = [t for t in self._selected_licences()
               if t is not None and not can_produce(self.castle, t)]
        if bad:
            names = ", ".join(UNIT_NAMES.get(t, str(t)) for t in bad)
            self.lic_warn.setText(
                "Wg reguł gry ten budynek nie mógłby kupić licencji na: " + names +
                " (poziom / kuźnia / warsztat). Zapis jest możliwy, ale efekt nieprzetestowany."
            )
        else:
            self.lic_warn.setText("")

    def _auto_licences(self):
        if self.castle is None:
            return
        # najpierw obecne licencje (np. ta w produkcji), potem reszta dozwolonych
        allowed = [t for t in self._selected_licences() if t is not None]
        for t in sorted(UNIT_TECH_REQ):
            if t not in allowed and can_produce(self.castle, t):
                allowed.append(t)
        allowed = allowed[:B_LICENCE_SLOTS]
        for i, cb in enumerate(self.lic_combos):
            cb.setCurrentIndex(cb.findData(allowed[i] if i < len(allowed) else None))

    def _apply_licences(self):
        c = self.castle
        if c is None:
            return
        chosen = self._selected_licences()
        prod_idx = self.prod_combo.currentData()
        lic_before = c.licences()
        prod_type = lic_before[prod_idx] if prod_idx is not None else None
        c.set_licences(chosen)
        new = [t for t in c.licences()]
        if prod_type is not None and prod_type in new:
            c.set_u8(B_PROD_SLOT, new.index(prod_type))
            c.set_u8(B_PROD_TURNS, self.prod_turns.value())
        else:
            c.set_u8(B_PROD_SLOT, 0xFF)
            c.set_u8(B_PROD_TURNS, 0)
        self._after_change()

    # ---------- wiezniowie
    def _apply_prisoners(self):
        c = self.castle
        if c is None:
            return
        for i, (on, t, o, turns) in enumerate(self.pr_rows):
            if on.isChecked():
                c.set_prisoner(i, {"type": t.currentData(), "owner": o.currentData(),
                                   "turns": turns.value()})
            else:
                c.set_prisoner(i, None)
        self._after_change()


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

        self.castle_editor = CastleEditorPanel(editor)
        self.addDockWidget(Qt.RightDockWidgetArea, self.castle_editor)

        self.tabifyDockWidget(self.inspector, self.squad_panel)
        self.tabifyDockWidget(self.squad_panel, self.unit_editor)
        self.tabifyDockWidget(self.unit_editor, self.castle_editor)

        locked = QDockWidget.DockWidgetFeature.NoDockWidgetFeatures
        for dock in (panel, self.inspector, self.squad_panel, self.unit_editor,
                     self.castle_editor):
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

        next_castle_action = QAction("Nastepny zamek", self)
        next_castle_action.triggered.connect(self.next_castle)
        tb.addAction(next_castle_action)


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



    def next_castle(self):
        idx = self.player_combo.currentIndex()
        owner = None if idx == 0 else idx - 1
        b = self.editor.goto_next_building(owner)
        if b is None:
            who = "zadnego gracza" if owner is None else OWNER_NAMES[owner]
            self.statusBar().showMessage(f"Brak budynkow: {who}", 3000)
        else:
            self.castle_editor.raise_()
            tname = BUILDING_TYPE_NAMES.get(b["type"], "budynek")
            self.statusBar().showMessage(f"{tname} {b['name']} ({b['x']}, {b['y']})")

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