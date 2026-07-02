import struct
import os
import sys

from PySide6.QtWidgets import (
    QApplication, QGraphicsView, QGraphicsScene,
    QDockWidget, QListWidget, QListWidgetItem,
    QLabel, QWidget, QVBoxLayout, QMainWindow,
    QToolBar
)
from PySide6.QtGui import QPixmap, QIcon, QAction
from PySide6.QtCore import Qt

TILE_SIZE = 64


# ---------------- TILE ----------------
class Tile:
    def __init__(self, tex_id=0):
        self.tex_id = tex_id


# ---------------- MAP VIEW ----------------
class MapEditor(QGraphicsView):
    def __init__(self, width, height, textures):
        super().__init__()

        self.width = width
        self.height = height
        self.textures = textures
        self.selected_tex = 0

        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        self.map = [
            [Tile(0) for _ in range(height)]
            for _ in range(width)
        ]

        self.setMouseTracking(True)
        self.draw_map()

    def draw_map(self):
        self.scene.clear()

        for x in range(self.width):
            for y in range(self.height):
                tile = self.map[x][y]
                pix = self.textures.get(tile.tex_id)

                if pix:
                    item = self.scene.addPixmap(pix)
                    item.setOffset(x * TILE_SIZE, y * TILE_SIZE)

    def paint_tile(self, event):
        pos = self.mapToScene(event.pos())

        x = int(pos.x() // TILE_SIZE)
        y = int(pos.y() // TILE_SIZE)

        if 0 <= x < self.width and 0 <= y < self.height:
            self.map[x][y].tex_id = self.selected_tex
            self.draw_map()

    def mousePressEvent(self, event):
        self.paint_tile(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self.paint_tile(event)

    def set_selected_texture(self, tex_id):
        self.selected_tex = tex_id

    # ---------------- LOAD (READ ONLY tex_id) ----------------
    def load_dat(self, path):
        HEADER_SIZE = 16
        TILE_SIZE_BYTES = 14

        with open(path, "rb") as f:
            f.seek(HEADER_SIZE)

            for x in range(self.width):
                for y in range(self.height):
                    data = f.read(TILE_SIZE_BYTES)
                    if not data:
                        return

                    tex_id = struct.unpack("<H", data[0:2])[0]
                    self.map[x][y].tex_id = tex_id

    # ---------------- PATCH SAVE (ONLY tex_id CHANGE) ----------------
    def save_dat_patch(self, input_path, output_path):
        HEADER_SIZE = 16
        TILE_SIZE_BYTES = 14

        with open(input_path, "rb") as f:
            data = bytearray(f.read())

        for x in range(self.width):
            for y in range(self.height):
                idx = x * self.height + y
                offset = HEADER_SIZE + idx * TILE_SIZE_BYTES

                # ONLY overwrite first 2 bytes (tex_id)
                new_tex = struct.pack("<H", self.map[x][y].tex_id)

                data[offset:offset + 2] = new_tex

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
        for tex_id, pix in self.textures.items():
            item = QListWidgetItem(f"Texture {tex_id}")
            item.setData(Qt.UserRole, tex_id)
            item.setIcon(QIcon(pix.scaled(64, 64)))
            self.list.addItem(item)

    def pick(self, item):
        tex_id = item.data(Qt.UserRole)
        self.preview.setText(f"Selected: {tex_id}")
        self.on_select(tex_id)


# ---------------- MAIN WINDOW ----------------
class MainWindow(QMainWindow):
    def __init__(self, editor, panel):
        super().__init__()

        self.editor = editor
        self.setWindowTitle("Clash Map Editor")

        self.setCentralWidget(editor)
        self.addDockWidget(Qt.LeftDockWidgetArea, panel)

        self.create_toolbar()

    def create_toolbar(self):
        tb = QToolBar("Main")
        self.addToolBar(tb)

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

    editor = MapEditor(100, 100, textures)
    editor.load_dat("1.DAT")

    panel = TexturePanel(textures, editor.set_selected_texture)

    window = MainWindow(editor, panel)
    window.resize(1400, 900)
    window.show()

    sys.exit(app.exec())