"""Generator losowych map dla Clash.

Jak dziala:
 1. Woda (pola) i teren ladowy (narozniki) z szumu fraktalnego:
    - woda jest zapisywana per pole; jej brzegi wybiera tabela wyuczona z map
      kampanii na podstawie ukladu 3x3 (clash_mapgen_data.json),
    - trawa/piasek/ziemia leza na siatce naroznikow 101x101 - tak jak w grze,
      gdzie kafelek przejscia zalezy od materialu w 4 naroznikach
      (trawa<->piasek: kafelki 8-19, trawa<->ziemia: 20-31).
 2. Lasy jako prostokaty 9-slice (45-57, jak w oryginalnych mapach) i formacje
    skal wyciete z map kampanii.
 3. Opcjonalnie drogi A* laczace budynki - rysuje je edytor swoimi kafelkami.

Modul nie zalezy od Qt - mozna go uzywac i testowac osobno.
"""
import heapq
import json
import math
import os
import random

N = 100
NONE = 0xFFFF
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clash_mapgen_data.json")

NB8 = [(-1, -1), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0)]
NB4 = [(0, -1), (1, 0), (0, 1), (-1, 0)]

# kafelki przejsc wg naroznikow (NW, NE, SE, SW) - odczytane z pikseli tekstur
WANG = {
    # trawa / piasek
    "SSGS": 8, "SSGG": 9, "SSSG": 10, "SGGS": 11, "GSSG": 12, "SGSS": 13,
    "GGSS": 14, "GSSS": 15, "GGSG": 16, "GGGS": 17, "GSGG": 18, "SGGG": 19,
    # trawa / ziemia
    "GGDG": 20, "GGDD": 21, "GGGD": 22, "GDDG": 23, "DGGD": 24, "GDGG": 25,
    "DDGG": 26, "DGGG": 27, "GDDD": 28, "DGDD": 29, "DDDG": 30, "DDGD": 31,
}

# las na trawie - uklad 9-slice odczytany z map kampanii
FOREST_NW, FOREST_N, FOREST_NE = 45, 46, 47
FOREST_W, FOREST_C, FOREST_E = 48, 49, 50
FOREST_SW, FOREST_S, FOREST_SE = 51, 52, 53
FOREST_CLUMP = ((54, 55), (56, 57))   # kepa 2x2 wewnatrz lasu


class GenParams:
    def __init__(self, seed=None, water=0.12, sand=0.12, dirt=0.06,
                 forests=12, rocks=6, roads=True, smoothness=2):
        self.seed = random.randrange(1 << 30) if seed is None else seed
        self.water = water          # udzial wody (0..0.5)
        self.sand = sand            # udzial piasku
        self.dirt = dirt            # udzial ziemi
        self.forests = forests      # liczba lasow
        self.rocks = rocks          # liczba formacji skal
        self.roads = roads          # drogi miedzy budynkami
        self.smoothness = smoothness


# ------------------------------------------------------------------ szum
class ValueNoise:
    def __init__(self, rng, period=256):
        self.p = [rng.random() for _ in range(period * period)]
        self.period = period

    def _v(self, ix, iy):
        P = self.period
        return self.p[(ix % P) * P + (iy % P)]

    def noise(self, x, y):
        ix, iy = math.floor(x), math.floor(y)
        fx, fy = x - ix, y - iy
        sx = fx * fx * (3 - 2 * fx)
        sy = fy * fy * (3 - 2 * fy)
        a = self._v(ix, iy) + (self._v(ix + 1, iy) - self._v(ix, iy)) * sx
        b = self._v(ix, iy + 1) + (self._v(ix + 1, iy + 1) - self._v(ix, iy + 1)) * sx
        return a + (b - a) * sy

    def fbm(self, x, y, octaves=4, scale=24.0):
        total, amp, norm, f = 0.0, 1.0, 0.0, 1.0 / scale
        for _ in range(octaves):
            total += self.noise(x * f, y * f) * amp
            norm += amp
            amp *= 0.5
            f *= 2.0
        return total / norm


def _top_fraction(values, keys, fraction):
    """Zbior kluczy z najwyzszymi wartosciami (zadany ulamek)."""
    if fraction <= 0 or not keys:
        return set()
    ordered = sorted(keys, key=lambda k: values[k], reverse=True)
    return set(ordered[:int(len(ordered) * fraction)])


def _corners(x, y):
    return ((x, y), (x + 1, y), (x + 1, y + 1), (x, y + 1))   # NW NE SE SW


# ------------------------------------------------------------------ generator
class MapGenerator:
    def __init__(self, data_path=DATA_FILE):
        with open(data_path, "r") as f:
            data = json.load(f)
        self.table8 = {k: self._prep(v) for k, v in data["table8"].items()}
        self.table4 = {k: self._prep(v) for k, v in data["table4"].items()}
        # wnetrze materialu: bez nakladek, bez kafelkow przejsc i brzegow morskich
        not_interior = set(WANG.values()) | set(range(223, 235)) | set(range(417, 423))
        self.interior = {}
        for k, v in data["interior"].items():
            clean = {t: n for t, n in v.items()
                     if t.endswith(",65535") and int(t.split(",")[0]) not in not_interior}
            if k == "S":   # warianty piasku (32-44) rzadziej - inaczej widac kwadraty
                clean = {t: (n if t.startswith("4,") else max(1, n // 4)) for t, n in clean.items()}
            self.interior[k] = self._prep(clean or v)
        # brzeg trawa/woda: woda 595 z nakladkami brzegu trawiastego, trawa bez przejsc
        grass_ok = {0, 1, 3} | set(range(74, 97))
        shore_ok = {NONE} | set(range(563, 575)) | set(range(695, 699))
        for table in (self.table8, self.table4):
            for k, (items, total) in list(table.items()):
                if not set(k) <= {"G", "W"}:
                    continue
                if k[0] == "W":
                    keep = [(t, n) for t, n in items if t[0] == 595 and t[1] in shore_ok]
                else:
                    keep = [(t, n) for t, n in items if t[0] in grass_ok and t[1] == NONE]
                if keep:
                    table[k] = (keep, sum(n for _, n in keep))
        self.stamps = data["stamps"]

    @staticmethod
    def _prep(counts):
        items = [(tuple(int(p) for p in k.split(",")), n) for k, n in counts.items()]
        items.sort()
        return items, sum(n for _, n in items)

    @staticmethod
    def _pick(entry, rng):
        items, total = entry
        r = rng.random() * total
        for tile, n in items:
            r -= n
            if r < 0:
                return tile
        return items[-1][0]

    # ---------- 1a. woda (per pole)
    def water_cells(self, p, rng, keep):
        cells = [(x, y) for x in range(N) for y in range(N)]
        nz = ValueNoise(rng)
        depth = {c: -nz.fbm(c[0], c[1], 4, 22.0) for c in cells}
        water = _top_fraction(depth, cells, p.water)
        water -= self._grow(keep, 2)
        for _ in range(p.smoothness):
            water = self._smooth(water, keep)
        # tylko ksztalty z blokow 2x2 (cienkie wypustki wygladaja zle)
        for _ in range(10):
            bad = {c for c in water if not self._in_block(water, c)}
            if not bad:
                break
            water -= bad
        return water

    @staticmethod
    def _grow(cells, r):
        out = set()
        for (x, y) in cells:
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    out.add((x + dx, y + dy))
        return out

    @staticmethod
    def _smooth(cells, keep):
        out = set()
        for x in range(N):
            for y in range(N):
                n = sum((x + dx, y + dy) in cells for dx in (-1, 0, 1) for dy in (-1, 0, 1))
                if n >= 5 and (x, y) not in keep:
                    out.add((x, y))
        return out

    @staticmethod
    def _in_block(cells, c):
        x, y = c
        return any(all((x + ox + a, y + oy + b) in cells for a in (0, 1) for b in (0, 1))
                   for ox in (0, -1) for oy in (0, -1))

    # ---------- 1b. lad (narozniki)
    def land_corners(self, p, rng, water, keep):
        verts = [(x, y) for x in range(N + 1) for y in range(N + 1)]
        ns, nd = ValueNoise(rng), ValueNoise(rng)
        sand = {v: ns.fbm(v[0] + 300, v[1] + 300, 3, 14.0) for v in verts}
        dirt = {v: nd.fbm(v[0] + 600, v[1] + 600, 3, 11.0) for v in verts}
        land_frac = max(1e-6, 1 - p.water)
        corner = {v: "G" for v in verts}
        for v in _top_fraction(sand, verts, p.sand / land_frac):
            corner[v] = "S"
        rest = [v for v in verts if corner[v] == "G"]
        for v in _top_fraction(dirt, rest, p.dirt / land_frac):
            corner[v] = "D"
        # naroznik pola przy wodzie lub zarezerwowanego (budynki, oddzialy) = trawa
        fixed = set()
        for (x, y) in self._grow(water, 1) | set(keep):
            if 0 <= x < N and 0 <= y < N:
                fixed.update(_corners(x, y))
        for v in fixed:
            corner[v] = "G"
        for _ in range(p.smoothness):
            corner = self._smooth_corners(corner, fixed)
        self._fix_corners(corner, fixed)
        return corner

    @staticmethod
    def _smooth_corners(corner, fixed):
        out = dict(corner)
        for (x, y), m in corner.items():
            if (x, y) in fixed:
                continue
            cnt = {}
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = corner.get((x + dx, y + dy), m)
                    cnt[q] = cnt.get(q, 0) + 1
            best, n = max(cnt.items(), key=lambda kv: (kv[1], kv[0] == m))
            if n >= 5:
                out[(x, y)] = best
        return out

    @staticmethod
    def _fix_corners(corner, fixed):
        """Gra nie ma kafelkow na przekatne (SGSG) ani na piasek+ziemia w jednym polu."""
        for _ in range(20):
            changed = False
            for x in range(N):
                for y in range(N):
                    vs = _corners(x, y)
                    ms = [corner[v] for v in vs]
                    kinds = set(ms) - {"G"}
                    if len(kinds) > 1:              # piasek i ziemia w jednym polu
                        for v in vs:
                            if corner[v] == "D" and v not in fixed:
                                corner[v] = "G"
                                changed = True
                        continue
                    if not kinds or len(set(ms)) == 1:
                        continue
                    k = "".join(ms)
                    if k[0] == k[2] and k[1] == k[3] and k[0] != k[1]:   # przekatna
                        for v in (vs[1], vs[3]) if ms[1] != "G" else (vs[0], vs[2]):
                            if v not in fixed:
                                corner[v] = "G"
                                changed = True
            if not changed:
                break

    # ---------- 2. kafelki
    def tiles_for(self, water, corner, rng):
        stats = {"water8": 0, "water4": 0, "wang": 0, "plain": 0, "missing": 0}
        label = {}
        for x in range(N):
            for y in range(N):
                if (x, y) in water:
                    label[(x, y)] = "W"
                else:
                    ms = {corner[v] for v in _corners(x, y)}
                    label[(x, y)] = ms.pop() if len(ms) == 1 else "T"
        tiles = {}
        for x in range(N):
            for y in range(N):
                c = label[(x, y)]
                nb = [label.get((x + dx, y + dy), c) for dx, dy in NB8]
                near_water = "W" in nb or c == "W"
                if c != "T" and all(q == c for q in nb):
                    tiles[(x, y)] = self._pick(self.interior[c], rng)
                    stats["plain"] += 1
                elif c == "T":
                    k = "".join(corner[v] for v in _corners(x, y))
                    tid = WANG.get(k)
                    if tid is None:
                        stats["missing"] += 1
                        tiles[(x, y)] = self._pick(self.interior["G"], rng)
                    else:
                        tiles[(x, y)] = (tid, NONE)
                        stats["wang"] += 1
                elif near_water:
                    k8 = c + "".join(nb)
                    if k8 in self.table8:
                        tiles[(x, y)] = self._pick(self.table8[k8], rng)
                        stats["water8"] += 1
                    else:
                        k4 = c + nb[1] + nb[3] + nb[5] + nb[7]
                        if k4 in self.table4:
                            tiles[(x, y)] = self._pick(self.table4[k4], rng)
                            stats["water4"] += 1
                        else:
                            tiles[(x, y)] = self._pick(self.interior[c], rng)
                            stats["missing"] += 1
                else:
                    tiles[(x, y)] = self._pick(self.interior[c], rng)
                    stats["plain"] += 1
        return tiles, label, stats

    # ---------- 3. lasy i skaly
    @staticmethod
    def _free_rect(label, used, x0, y0, w, h, ground="G", margin=1):
        for x in range(x0 - margin, x0 + w + margin):
            for y in range(y0 - margin, y0 + h + margin):
                if not (0 <= x < N and 0 <= y < N):
                    return False
                if label[(x, y)] != ground or (x, y) in used:
                    return False
        return True

    def place_forests(self, label, tiles, used, rng, count):
        placed = 0
        for _ in range(count * 60):
            if placed >= count:
                break
            w, h = rng.randint(4, 12), rng.randint(4, 10)
            x0, y0 = rng.randint(1, N - w - 2), rng.randint(1, N - h - 2)
            if not self._free_rect(label, used, x0, y0, w, h):
                continue
            for x in range(x0, x0 + w):
                for y in range(y0, y0 + h):
                    left, right = x == x0, x == x0 + w - 1
                    top, bottom = y == y0, y == y0 + h - 1
                    if top:
                        t = FOREST_NW if left else FOREST_NE if right else FOREST_N
                    elif bottom:
                        t = FOREST_SW if left else FOREST_SE if right else FOREST_S
                    else:
                        t = FOREST_W if left else FOREST_E if right else FOREST_C
                    tiles[(x, y)] = (t, NONE)
                    used.add((x, y))
                    label[(x, y)] = "F"
            # kepy 2x2 w srodku, jak w oryginalnych lasach
            for _ in range(max(0, (w - 2) * (h - 2) // 6)):
                if w < 4 or h < 4:
                    break
                cx, cy = rng.randint(x0 + 1, x0 + w - 3), rng.randint(y0 + 1, y0 + h - 3)
                if all(tiles[(cx + a, cy + b)][0] == FOREST_C for a in (0, 1) for b in (0, 1)):
                    for a in (0, 1):
                        for b in (0, 1):
                            tiles[(cx + a, cy + b)] = (FOREST_CLUMP[b][a], NONE)
            placed += 1
        return placed

    def place_rocks(self, label, tiles, used, rng, count):
        stamps = [s for s in self.stamps.get("R", []) if s["ground"] == "G"]
        if not stamps:
            return 0
        placed = 0
        for _ in range(count * 80):
            if placed >= count:
                break
            st = rng.choice(stamps)
            w, h = st["w"], st["h"]
            x0, y0 = rng.randint(0, N - w), rng.randint(0, N - h)
            if not self._free_rect(label, used, x0, y0, w, h, "G", margin=0):
                continue
            for dx, dy, t, o in st["tiles"]:
                if t in (211, 212, 213, 214, 215):   # przezroczysty "czubek" jako baza
                    t, o = 0, t
                tiles[(x0 + dx, y0 + dy)] = (t, o)
            for dx in range(w):
                for dy in range(h):
                    used.add((x0 + dx, y0 + dy))
                    if 0 < dx < w - 1 and 0 < dy < h - 1:
                        label[(x0 + dx, y0 + dy)] = "R"
            placed += 1
        return placed

    # ---------- 4. drogi
    @staticmethod
    def road_paths(label, targets):
        """Laczy cele drzewem najkrotszych drog (A*) po trawie, piasku i ziemi."""
        cost = {"G": 1.0, "S": 1.3, "D": 1.6, "T": 1.3}
        targets = list(dict.fromkeys(targets))
        if len(targets) < 2:
            return []
        rest = list(targets[1:])
        tree = [targets[0]]
        edges = []
        while rest:
            _, a, b = min((abs(a[0] - b[0]) + abs(a[1] - b[1]), a, b) for a in tree for b in rest)
            edges.append((a, b))
            tree.append(b)
            rest.remove(b)
        paths = []
        for a, b in edges:
            path = MapGenerator._astar(label, a, b, cost)
            if path:
                paths.append(path)
        return paths

    @staticmethod
    def _astar(label, a, b, cost):
        openh = [(0, a)]
        came = {a: None}
        g = {a: 0.0}
        while openh:
            _, cur = heapq.heappop(openh)
            if cur == b:
                path = []
                while cur is not None:
                    path.append(cur)
                    cur = came[cur]
                return path[::-1]
            for dx, dy in NB4:
                nxt = (cur[0] + dx, cur[1] + dy)
                m = label.get(nxt)
                if m is None:
                    continue
                step = cost.get(m)
                if step is None:
                    if nxt != b:
                        continue
                    step = 1.0
                ng = g[cur] + step
                if ng < g.get(nxt, 1e18):
                    g[nxt] = ng
                    came[nxt] = cur
                    heapq.heappush(openh, (ng + abs(nxt[0] - b[0]) + abs(nxt[1] - b[1]), nxt))
        return None

    # ---------- calosc
    def generate(self, params, keep_clear=(), road_targets=()):
        """keep_clear: pola, ktore musza zostac trawa (budynki, oddzialy).
        road_targets: pola, ktore maja polaczyc drogi (np. wejscia do zamkow).
        Zwraca dict: tiles {(x,y): (tex, ovl)}, labels, roads [sciezki], stats."""
        rng = random.Random(params.seed)
        keep = {c for c in keep_clear if 0 <= c[0] < N and 0 <= c[1] < N}
        water = self.water_cells(params, rng, keep)
        corner = self.land_corners(params, rng, water, keep)
        tiles, label, stats = self.tiles_for(water, corner, rng)
        used = set(self._grow(keep, 1))
        roads = self.road_paths(label, list(road_targets)) if params.roads else []
        for path in roads:
            used |= self._grow(path, 1)
        stats["forests"] = self.place_forests(label, tiles, used, rng, params.forests)
        stats["rocks"] = self.place_rocks(label, tiles, used, rng, params.rocks)
        return {"tiles": tiles, "labels": label, "roads": roads, "stats": stats}
