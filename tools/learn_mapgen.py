"""Uczy generator map Clash z oryginalnych zapisow (.DAT).

Wynik: clash_mapgen_data.json z
  - tabela: uklad materialow 3x3 -> kafelki (tex, overlay) z czestosciami
  - formacje lasow i skal wyciete z map (do "stemplowania")

Uzycie:  python tools/learn_mapgen.py SAVE/3.DAT SAVE/4.DAT ... -o clash_mapgen_data.json
"""
import argparse
import json
import struct
from collections import Counter, defaultdict

NONE = 0xFFFF
N = 100

# --- materialy (etykiety komorek) ---------------------------------------
OCEAN = {587}
WATER = set([595, 596, 597, 598, 599, 600, 601, 602, 651, 667])
MARSH = set([603, 604, 605, 606, 607, 608, 609]) | set(range(611, 641))
SAND = set([4, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15]) | set(range(32, 45)) \
    | set(range(223, 235)) | set(range(417, 423)) | {771}
DIRT = set([7, 28, 29, 30, 31])
FOREST = set(range(45, 68))
ROCK = set(range(161, 221)) | set(range(746, 751))
# obiekty specjalne / nieznane - nigdy nie wybierane przez generator
EXCLUDE = {2, 0xFFFF} | set(range(699, 746)) | set(range(751, 760)) | {780}


def label(tex):
    if tex in OCEAN:
        return "O"
    if tex in WATER:
        return "W"
    if tex in MARSH:
        return "M"
    if tex in SAND:
        return "S"
    if tex in DIRT:
        return "D"
    if tex in FOREST:
        return "F"
    if tex in ROCK:
        return "R"
    if tex == NONE:
        return "X"
    return "G"


def load(path):
    d = open(path, "rb").read()
    return [[struct.unpack_from("<3H", d, 16 + (x * N + y) * 14) for y in range(N)]
            for x in range(N)]


NB8 = [(-1, -1), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0)]  # NW N NE E SE S SW W
NB4_IDX = [1, 3, 5, 7]


def key8(lab, x, y):
    c = lab[x][y]
    nb = []
    for dx, dy in NB8:
        nx, ny = x + dx, y + dy
        nb.append(lab[nx][ny] if 0 <= nx < N and 0 <= ny < N else c)
    return c + "".join(nb)


def components(lab, want, maps_tiles):
    """Spojne obszary danego materialu (4-sasiedztwo)."""
    seen = set()
    out = []
    for x in range(N):
        for y in range(N):
            if lab[x][y] != want or (x, y) in seen:
                continue
            stack = [(x, y)]
            seen.add((x, y))
            cells = []
            while stack:
                cx, cy = stack.pop()
                cells.append((cx, cy))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < N and 0 <= ny < N and (nx, ny) not in seen \
                            and lab[nx][ny] == want:
                        seen.add((nx, ny))
                        stack.append((nx, ny))
            out.append(cells)
    return out


def extract_stamp(grid, lab, cells, want, ground):
    """Wycina formacje z obwodka 1 pola (zeby zlapac nakladki typu 'czubki skal')."""
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    x0, x1 = min(xs) - 1, max(xs) + 1
    y0, y1 = min(ys) - 1, max(ys) + 1
    if x0 < 0 or y0 < 0 or x1 >= N or y1 >= N:
        return None
    cellset = set(cells)
    tiles = []
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            t, o, _ = grid[x][y]
            if (x, y) in cellset:
                tiles.append([x - x0, y - y0, t, o])
            else:
                # obwodka: dozwolony tylko "czysty" teren bazowy, ewentualnie z nakladka
                if lab[x][y] != ground:
                    return None
                if o != NONE:
                    tiles.append([x - x0, y - y0, t, o])
    return {"w": x1 - x0 + 1, "h": y1 - y0 + 1, "ground": ground, "tiles": tiles,
            "size": len(cells)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("saves", nargs="+")
    ap.add_argument("-o", "--out", default="clash_mapgen_data.json")
    args = ap.parse_args()

    table8 = defaultdict(Counter)
    table4 = defaultdict(Counter)
    table1 = defaultdict(Counter)
    stamps = {"F": [], "R": []}
    seen_maps = set()
    for path in args.saves:
        grid = load(path)
        sig = tuple(grid[x][y][:2] for x in range(N) for y in range(N))
        if sig in seen_maps:
            continue
        seen_maps.add(sig)
        lab = [[label(grid[x][y][0]) for y in range(N)] for x in range(N)]
        for x in range(N):
            for y in range(N):
                t, o, _ = grid[x][y]
                if t in EXCLUDE or (o != NONE and o in EXCLUDE) or lab[x][y] in "FRX":
                    continue
                k = key8(lab, x, y)
                if "X" in k:
                    continue
                tile = f"{t},{o}"
                table8[k][tile] += 1
                table4[k[0] + "".join(k[1 + i] for i in NB4_IDX)][tile] += 1
                table1[k[0]][tile] += 1
        for mat, ground in (("F", "G"), ("R", "G"), ("F", "S"), ("R", "S")):
            for comp in components(lab, mat, grid):
                if len(comp) < 4:
                    continue
                st = extract_stamp(grid, lab, comp, mat, ground)
                if st:
                    st["material"] = mat
                    stamps[mat].append(st)

    # tabela 1: tylko kafelki "wnetrza" (wszyscy sasiedzi ten sam material)
    interior = defaultdict(Counter)
    for k, cnt in table8.items():
        if len(set(k)) == 1:
            interior[k[0]].update(cnt)

    data = {
        "version": 1,
        "maps": len(seen_maps),
        "table8": {k: dict(v) for k, v in table8.items()},
        "table4": {k: dict(v) for k, v in table4.items()},
        "interior": {k: dict(v) for k, v in interior.items()},
        "stamps": stamps,
    }
    with open(args.out, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"maps={len(seen_maps)} patterns8={len(table8)} patterns4={len(table4)} "
          f"forest stamps={len(stamps['F'])} rock stamps={len(stamps['R'])}")
    for m, c in interior.items():
        print(m, c.most_common(8))


if __name__ == "__main__":
    main()
