#!/usr/bin/env python3
"""Round 3 — "THE SKY UNZIPS".

A giant zipper tears the night sky open and a blazing sunrise pours out
of the rip. An impossible object, drawn fully procedurally: no stock
explosion, no firework — just the sky coming undone, a sun where the
stars used to be, and birds escaping through the tear.

Pure Python 3 stdlib (math / os / random / struct / zlib). Deterministic:
fixed seed, no wall clock, no network. Two runs -> byte-identical PNG.
"""
import math
import os
import random
import struct
import zlib

W = H = 1024
SEED = 20261116
rng = random.Random(SEED)


# ---------------------------------------------------------------- palette
def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def grad(stops, t):
    """stops: list of (pos, rgb). Interpolate."""
    if t <= stops[0][0]:
        return stops[0][1]
    for i in range(1, len(stops)):
        if t <= stops[i][0]:
            p0, c0 = stops[i - 1]
            p1, c1 = stops[i]
            return lerp(c0, c1, (t - p0) / (p1 - p0))
    return stops[-1][1]


NIGHT = [(0.0, (7, 9, 44)), (0.45, (24, 16, 72)),
         (0.75, (56, 22, 96)), (1.0, (94, 30, 108))]
SUNRISE = [(0.0, (255, 44, 138)), (0.40, (255, 104, 38)),
           (0.70, (255, 186, 58)), (1.0, (255, 232, 122))]

# Tear centreline: from top-left to bottom-right, gently wobbling.
X0, Y0, X1, Y1 = 150.0, 10.0, 800.0, 850.0


def tear_cx(y):
    t = y / H
    return X0 + (X1 - X0) * t + 20.0 * math.sin(y * 0.013)


def tear_half(y):
    return 118.0 + 34.0 * math.sin(y * 0.011 + 1.2) + 18.0 * math.sin(y * 0.031)


SUN_C = (640.0, 760.0)   # sun disc centre, sitting in the tear
SUN_R = 96.0


# ---------------------------------------------------------------- canvas
rows = []
for y in range(H):
    c = grad(NIGHT, y / H)
    rows.append(bytearray(bytes(c) * W))


def set_px(x, y, col):
    if 0 <= x < W and 0 <= y < H:
        r = rows[y]
        i = x * 3
        r[i], r[i + 1], r[i + 2] = col


def blend_px(x, y, col, a):
    """Alpha-blend col over the pixel (a in 0..1)."""
    if 0 <= x < W and 0 <= y < H:
        r = rows[y]
        i = x * 3
        r[i] = int(r[i] + (col[0] - r[i]) * a)
        r[i + 1] = int(r[i + 1] + (col[1] - r[i + 1]) * a)
        r[i + 2] = int(r[i + 2] + (col[2] - r[i + 2]) * a)


def fill_rect(x0, y0, x1, y1, col):
    x0 = max(0, int(x0)); y0 = max(0, int(y0))
    x1 = min(W, int(x1)); y1 = min(H, int(y1))
    if x1 <= x0 or y1 <= y0:
        return
    seg = bytes(col) * (x1 - x0)
    for y in range(y0, y1):
        rows[y][x0 * 3:x1 * 3] = seg


def line(x0, y0, x1, y1, col, a=1.0):
    """Simple DDA line, with optional alpha."""
    dx = x1 - x0
    dy = y1 - y0
    n = int(max(abs(dx), abs(dy))) + 1
    for i in range(n + 1):
        t = i / n
        if a >= 1.0:
            set_px(int(x0 + dx * t), int(y0 + dy * t), col)
        else:
            blend_px(int(x0 + dx * t), int(y0 + dy * t), col, a)


# ---------------------------------------------------------------- stars
for _ in range(420):
    sx = rng.randrange(W)
    sy = rng.randrange(700)
    b = rng.choice([150, 190, 220, 255])
    col = (b, b, min(255, b + 20))
    set_px(sx, sy, col)
    if rng.random() < 0.22:  # a few brighter stars get a cross sparkle
        set_px(sx - 1, sy, col)
        set_px(sx + 1, sy, col)
        set_px(sx, sy - 1, col)
        set_px(sx, sy + 1, col)
    if rng.random() < 0.10:  # tiny 2x2 star
        set_px(sx + 1, sy + 1, col)

# ---------------------------------------------------------------- moon (crescent, top right)
MC = (872.0, 128.0)
MR = 62.0
OC = (898.0, 110.0)   # occluder circle -> crescent
OR = 56.0
for yy in range(int(MC[1] - MR - 2), int(MC[1] + MR + 3)):
    for xx in range(int(MC[0] - MR - 2), int(MC[0] + MR + 3)):
        d1 = (xx - MC[0]) ** 2 + (yy - MC[1]) ** 2
        d2 = (xx - OC[0]) ** 2 + (yy - OC[1]) ** 2
        if d1 <= MR * MR and d2 > OR * OR:
            t = max(0.0, min(1.0, (yy - (MC[1] - MR)) / (2 * MR)))
            set_px(xx, yy, lerp((250, 238, 190), (214, 196, 140), t))

# ---------------------------------------------------------------- sun glow spilling past the tear
for yy in range(int(SUN_C[1] - 330), int(SUN_C[1] + 331)):
    for xx in range(int(SUN_C[0] - 330), int(SUN_C[0] + 331)):
        d = math.hypot(xx - SUN_C[0], yy - SUN_C[1])
        if d < 330.0:
            a = (1.0 - d / 330.0) ** 2 * 0.55
            blend_px(xx, yy, (255, 170, 60), a)

# ---------------------------------------------------------------- the tear: sunrise inside
for y in range(H):
    cx = tear_cx(y)
    hw = tear_half(y)
    left = int(cx - hw)
    right = int(cx + hw)
    v = y / H
    span = max(1, right - left)
    for x in range(max(0, left), min(W, right)):
        u = (x - left) / span
        col = grad(SUNRISE, v * 0.72 + u * 0.28)
        # bright core down the middle of the rip
        core = (1.0 - abs(u - 0.5) * 2.0)
        if core > 0.25:
            col = lerp(col, (255, 246, 214), (core - 0.25) * 0.55)
        # faint horizontal heat shimmer
        sh = int(10.0 * math.sin(x * 0.045 + y * 0.021))
        rows[y][x * 3] = max(0, min(255, col[0] + sh))
        rows[y][x * 3 + 1] = max(0, min(255, col[1] + sh))
        rows[y][x * 3 + 2] = max(0, min(255, col[2] + sh))

# ---------------------------------------------------------------- sun disc
for yy in range(int(SUN_C[1] - SUN_R - 1), int(SUN_C[1] + SUN_R + 2)):
    for xx in range(int(SUN_C[0] - SUN_R - 1), int(SUN_C[0] + SUN_R + 2)):
        d = math.hypot(xx - SUN_C[0], yy - SUN_C[1])
        if d <= SUN_R:
            t = d / SUN_R
            if t < 0.5:
                col = lerp((255, 252, 230), (255, 214, 110), t * 2.0)
            else:
                col = lerp((255, 214, 110), (255, 158, 40), (t - 0.5) * 2.0)
            set_px(xx, yy, col)
# sun rays: short spokes just outside the disc
for k in range(16):
    ang = k * math.pi / 8.0 + 0.19
    r0 = SUN_R + 12.0
    r1 = SUN_R + 34.0 + (26.0 if k % 2 == 0 else 0.0)
    line(SUN_C[0] + r0 * math.cos(ang), SUN_C[1] + r0 * math.sin(ang),
         SUN_C[0] + r1 * math.cos(ang), SUN_C[1] + r1 * math.sin(ang),
         (255, 214, 110), 0.85)

# ---------------------------------------------------------------- zipper teeth along both edges
SILVER = (206, 214, 230)
DARK = (120, 128, 150)
for y in range(28, H - 60, 26):
    cx = tear_cx(y)
    hw = tear_half(y)
    for ex, sgn in ((cx - hw, -1), (cx + hw, 1)):
        tx = int(ex)
        # tooth: small block straddling the edge, tilted by the tear slope
        fill_rect(tx - 7 if sgn < 0 else tx - 3, y - 5,
                  tx + 3 if sgn < 0 else tx + 7, y + 5, SILVER)
        fill_rect(tx - 7 if sgn < 0 else tx - 3, y + 3,
                  tx + 3 if sgn < 0 else tx + 7, y + 5, DARK)

# ---------------------------------------------------------------- zipper slider + pull tab at the tear tip
TIP = (X1, Y1)  # (800, 850) — where the rip is still opening
# slider body: small block hugging the tip
fill_rect(TIP[0] - 26, TIP[1] - 34, TIP[0] + 30, TIP[1] + 6, (168, 178, 198))
fill_rect(TIP[0] - 18, TIP[1] - 26, TIP[0] + 22, TIP[1] - 2, (206, 214, 230))
# pull tab: polygon along the tear direction, hanging below the slider
dx, dy = 0.56, 0.83          # tear direction (normalised-ish)
px, py = 0.83, -0.56         # perpendicular
CC = (TIP[0] + 30 * dx, TIP[1] + 30 * dy)
L, Wd = 100.0, 58.0
corners = []
for s1, s2 in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
    corners.append((CC[0] + s1 * L / 2 * dx + s2 * Wd / 2 * px,
                    CC[1] + s1 * L / 2 * dy + s2 * Wd / 2 * py))
# scanline fill of the tab polygon
edges = []
n = len(corners)
for i in range(n):
    x0, y0 = corners[i]
    x1, y1 = corners[(i + 1) % n]
    edges.append((x0, y0, x1, y1))
ymin = int(min(c[1] for c in corners))
ymax = int(max(c[1] for c in corners))
for yy in range(ymin, ymax + 1):
    xs = []
    for x0, y0, x1, y1 in edges:
        if y0 == y1:
            continue
        if min(y0, y1) <= yy < max(y0, y1):
            xs.append(x0 + (yy - y0) * (x1 - x0) / (y1 - y0))
    xs.sort()
    for i in range(0, len(xs) - 1, 2):
        fill_rect(xs[i], yy, xs[i + 1], yy + 1, (196, 204, 222))
# tab outline + ring hole + grip slot
for x0, y0, x1, y1 in edges:
    line(x0, y0, x1, y1, (110, 118, 142))
ring_c = (CC[0] - 34 * dx, CC[1] - 34 * dy)
for k in range(64):
    a = k * math.pi * 2 / 64
    set_px(int(ring_c[0] + 24 * math.cos(a)), int(ring_c[1] + 24 * math.sin(a)),
           (110, 118, 142))
    set_px(int(ring_c[0] + 19 * math.cos(a)), int(ring_c[1] + 19 * math.sin(a)),
           (110, 118, 142))
# motion streaks trailing the pull — the rip is still moving
for k in range(9):
    bx = TIP[0] + 44 + k * 20
    by = TIP[1] - 30 - k * 14
    line(bx, by, bx + 38, by - 24, (255, 255, 255), 0.5 - k * 0.04)

# ---------------------------------------------------------------- birds escaping through the tear
BIRD = (18, 16, 52)
birds = [(300, 300, 32), (388, 218, 24), (252, 428, 36), (486, 336, 22),
         (560, 178, 18), (196, 528, 28), (430, 470, 20)]
for bx, by, s in birds:
    line(bx - s, by - s * 0.45, bx, by, BIRD)
    line(bx, by, bx + s, by - s * 0.45, BIRD)
    line(bx - s, by - s * 0.45, bx - s + 3, by - s * 0.45 + 3, BIRD)
    line(bx + s, by - s * 0.45, bx + s - 3, by - s * 0.45 + 3, BIRD)

# speed streaks ripping along the tear edges in the night sky
for k in range(14):
    y = 120 + k * 62
    cx = tear_cx(y)
    hw = tear_half(y)
    side = -1 if k % 2 == 0 else 1
    x0 = cx + side * (hw + 26 + (k % 3) * 18)
    line(x0, y, x0 + 54 * side, y - 40, (255, 255, 255), 0.35)

# ---------------------------------------------------------------- text (5x7 bitmap font, my own glyphs)
FONT = {
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "G": (".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    ",": (".....", ".....", ".....", ".....", ".....", ".##..", ".#..."),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "-": (".....", ".....", ".....", "#####", ".....", ".....", "....."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    "I": (".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    ".": (".....", ".....", ".....", ".....", ".....", ".....", ".##.."),
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
}


def draw_text(x, y, s, text, col):
    cx = x
    for ch in text:
        g = FONT.get(ch, FONT[" "])
        for gy in range(7):
            for gx in range(5):
                if g[gy][gx] == "#":
                    fill_rect(cx + gx * s, y + gy * s,
                              cx + (gx + 1) * s, y + (gy + 1) * s, col)
        cx += 6 * s


SHADOW = (30, 14, 66)
draw_text(44, 868, 9, "JUDGE, LOOK -", SHADOW)
draw_text(40, 864, 9, "JUDGE, LOOK -", (255, 255, 255))
draw_text(44, 944, 9, "THE SKY UNZIPS.", SHADOW)
draw_text(40, 940, 9, "THE SKY UNZIPS.", (255, 210, 63))

# ---------------------------------------------------------------- PNG encode (stdlib only, filter 0)
raw = b"".join(b"\x00" + bytes(r) for r in rows)


def chunk(typ, data):
    out = struct.pack(">I", len(data)) + typ + data
    return out + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)


png = (b"\x89PNG\r\n\x1a\n"
       + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
       + chunk(b"IDAT", zlib.compress(raw, 6))
       + chunk(b"IEND", b""))

out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
os.makedirs(out_dir, exist_ok=True)
with open(os.path.join(out_dir, "entry.png"), "wb") as f:
    f.write(png)
print("wrote", os.path.join(out_dir, "entry.png"), len(png), "bytes")
