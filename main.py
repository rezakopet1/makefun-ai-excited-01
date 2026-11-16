#!/usr/bin/env python3
"""Make the AI judge excited -- make.fun ai-excited-01 entry.

A procedural poster drawn with the Python standard library only.
A radiant whale smashes out of a dull grey gallery painting, glass
shards flying, and shouts straight at the judge: "SURPRISE, JUDGE!"

No assets, no network, no timestamps, no unseeded randomness: two
runs write byte-identical PNGs. Run with:
    mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import math
import os
import struct
import zlib

W = 1024
H = 1024

# ---- palette -------------------------------------------------------------
SKY_TOP = (13, 16, 48)
SKY_BOT = (38, 24, 78)
GOLD = (245, 179, 1)
GOLD_LT = (255, 215, 106)
GOLD_DK = (184, 134, 11)
GREY_SKY = (154, 163, 178)
GREY_SEA = (125, 133, 151)
GREY_DK = (107, 114, 128)
GREY_LINE = (110, 118, 136)
CYAN = (0, 229, 255)
VIOLET = (123, 92, 255)
MAGENTA = (255, 45, 149)
WHITE = (255, 255, 255)
PALE = (191, 246, 255)
FIN = (194, 24, 91)
DARK = (16, 23, 58)
SHADOW = (5, 7, 15)


def lerp(a, b, t):
    return a + (b - a) * t


def lerp3(c0, c1, t):
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return (int(round(lerp(c0[0], c1[0], t))),
            int(round(lerp(c0[1], c1[1], t))),
            int(round(lerp(c0[2], c1[2], t))))


# ---- deterministic random (fixed seed LCG) --------------------------------
# Seed 20261116 is a hardcoded constant: no wall clock, no OS entropy,
# so every run of this file draws the exact same picture.
class Rng:
    def __init__(self, seed=20261116):
        self.s = seed & 0x7FFFFFFF

    def next(self):
        self.s = (1103515245 * self.s + 12345) & 0x7FFFFFFF
        return self.s

    def rand(self):
        return self.next() / 2147483648.0

    def range(self, lo, hi):
        return lo + self.rand() * (hi - lo)

    def pick(self, seq):
        return seq[int(self.rand() * len(seq)) % len(seq)]


# ---- canvas ---------------------------------------------------------------
class Canvas:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = color[0]
            self.px[i + 1] = color[1]
            self.px[i + 2] = color[2]

    def fill_rect(self, x, y, w, h, color):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1 - x0)
        for yy in range(y0, y1):
            base = (yy * self.w + x0) * 3
            self.px[base:base + len(row)] = row

    def disc(self, cx, cy, r, color):
        if r <= 0:
            return
        r2 = r * r
        for y in range(max(0, cy - r), min(self.h, cy + r + 1)):
            dy = y - cy
            dx = int(math.sqrt(max(0, r2 - dy * dy)))
            x0 = max(0, cx - dx)
            x1 = min(self.w - 1, cx + dx)
            row = bytes(color) * (x1 - x0 + 1)
            base = (y * self.w + x0) * 3
            self.px[base:base + len(row)] = row

    def polygon(self, pts, color=None, color_fn=None):
        pts = [(int(round(x)), int(round(y))) for (x, y) in pts]
        ys = [p[1] for p in pts]
        ymin = max(0, min(ys))
        ymax = min(self.h - 1, max(ys))
        n = len(pts)
        for y in range(ymin, ymax + 1):
            xs = []
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    t = (y - y0) / (y1 - y0)
                    xs.append(x0 + t * (x1 - x0))
            if len(xs) < 2:
                continue
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                xa = max(0, int(math.ceil(xs[k])))
                xb = min(self.w - 1, int(math.floor(xs[k + 1])))
                if xb < xa:
                    continue
                if color is not None:
                    row = bytes(color) * (xb - xa + 1)
                    base = (y * self.w + xa) * 3
                    self.px[base:base + len(row)] = row
                else:
                    for x in range(xa, xb + 1):
                        self.set(x, y, color_fn(x, y))

    def thick_line(self, x0, y0, x1, y1, w, color):
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        if length == 0:
            self.disc(int(x0), int(y0), max(1, w // 2), color)
            return
        nx, ny = -dy / length * w / 2.0, dx / length * w / 2.0
        self.polygon([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
                      (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], color)
        self.disc(int(x0), int(y0), max(1, w // 2), color)
        self.disc(int(x1), int(y1), max(1, w // 2), color)


# ---- transforms -----------------------------------------------------------
def rot_pts(pts, ang_deg, cx, cy):
    a = math.radians(ang_deg)
    ca, sa = math.cos(a), math.sin(a)
    out = []
    for (x, y) in pts:
        dx, dy = x - cx, y - cy
        out.append((cx + dx * ca - dy * sa, cy + dx * sa + dy * ca))
    return out


def move_pts(pts, dx, dy):
    return [(x + dx, y + dy) for (x, y) in pts]


# ---- 5x7 bitmap font (hand-written glyphs) --------------------------------
FONT = {
    'A': (0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    'B': (0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E),
    'C': (0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E),
    'D': (0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E),
    'E': (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F),
    'G': (0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F),
    'H': (0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    'I': (0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E),
    'J': (0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C),
    'L': (0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F),
    'M': (0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11),
    'N': (0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11),
    'O': (0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    'P': (0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10),
    'R': (0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11),
    'S': (0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E),
    'T': (0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    'U': (0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    'V': (0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04),
    'W': (0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11),
    'Y': (0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04),
    ',': (0x00, 0x00, 0x00, 0x00, 0x0C, 0x04, 0x08),
    '!': (0x04, 0x04, 0x04, 0x04, 0x04, 0x00, 0x04),
    '.': (0x00, 0x00, 0x00, 0x00, 0x00, 0x0C, 0x0C),
    '-': (0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00),
    ' ': (0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00),
}


def text_width(s, scale):
    return max(0, len(s) * 6 * scale - scale)


def draw_text(cv, s, x, y, scale, color):
    cx = x
    for ch in s:
        g = FONT.get(ch)
        if g is not None:
            for r, bits in enumerate(g):
                for c in range(5):
                    if bits & (1 << (4 - c)):
                        cv.fill_rect(cx + c * scale, y + r * scale,
                                     scale, scale, color)
        cx += 6 * scale


def draw_text_outlined(cv, s, x, y, scale, color, outline, off):
    for dx, dy in ((-off, -off), (off, -off), (-off, off), (off, off)):
        draw_text(cv, s, x + dx, y + dy, scale, outline)
    draw_text(cv, s, x, y, scale, color)



# ---- whale geometry (local coords: +x toward the head, +y down) ------------
WHALE_BODY = [
    (368, -25), (360, 15), (330, 45), (260, 60), (170, 105),
    (60, 132), (-50, 125), (-150, 85), (-240, 30), (-300, 95),
    (-250, -5), (-295, -125), (-210, -85), (-130, -125),
    (-10, -155), (110, -165), (220, -150), (300, -115),
    (335, -95), (360, -60),
]
WHALE_BELLY_EDGE = [(-240, 30), (-150, 85), (-50, 125), (60, 132),
                    (170, 105), (260, 60), (330, 45)]
WHALE_FIN = [(50, 115), (160, 195), (195, 100)]
WHALE_EYE = (280, -60)
WHALE_SPOUT_BASE = (305, -105)
WHALE_C = (590, 350)
WHALE_ROT = -30
WHALE_SCALE = 0.88


def whale_transform(pts):
    """Local whale points -> global canvas points."""
    out = []
    for (x, y) in pts:
        x *= WHALE_SCALE
        y *= WHALE_SCALE
        a = math.radians(WHALE_ROT)
        ca, sa = math.cos(a), math.sin(a)
        rx = x * ca - y * sa
        ry = x * sa + y * ca
        out.append((WHALE_C[0] + rx, WHALE_C[1] + ry))
    return out


def whale_point(local):
    return whale_transform([local])[0]


# ---- scene ----------------------------------------------------------------
def draw_scene(cv):
    rng = Rng(20261116)

    # 1. night-sky gradient background
    for y in range(H):
        c = lerp3(SKY_TOP, SKY_BOT, y / (H - 1))
        row = bytes(c) * W
        cv.px[y * W * 3:(y + 1) * W * 3] = row

    # 2. star field
    for _ in range(140):
        x = int(rng.range(0, W))
        y = int(rng.range(0, H))
        r = 1 if rng.rand() < 0.8 else 2
        cv.disc(x, y, r, rng.pick([WHITE, (205, 215, 255),
                                   (255, 233, 168)]))

    # 3. gallery frame, tilted -6 degrees about (420, 420)
    FC = (420, 420)

    def frame_pts(local):
        return move_pts(rot_pts(local, -6, 0, 0), FC[0], FC[1])

    outer = [(-280, -220), (280, -220), (280, 220), (-280, 220)]
    inner = [(-252, -192), (252, -192), (252, 192), (-252, 192)]
    cv.polygon(frame_pts(move_pts(outer, 14, 16)), SHADOW)
    cv.polygon(frame_pts(outer), GOLD)
    # dull painting: flat grey sky over flat grey sea
    cv.polygon(frame_pts([(-252, -192), (252, -192), (252, 10),
                          (-252, 10)]), GREY_SKY)
    cv.polygon(frame_pts([(-252, 10), (252, 10), (252, 192),
                          (-252, 192)]), GREY_SEA)
    cv.polygon(frame_pts([(-252, 6), (252, 6), (252, 14),
                          (-252, 14)]), GREY_LINE)
    # a deliberately boring grey sun, cloud and sailboat
    sun = frame_pts([(-180, -110)])[0]
    cv.disc(int(sun[0]), int(sun[1]), 26, (178, 184, 196))
    cv.polygon(frame_pts([(-40, -165), (60, -165), (60, -135),
                          (-40, -135)]), (168, 174, 188))
    cv.polygon(frame_pts([(-60, 40), (-60, -8), (-22, 40)]),
               (200, 204, 212))
    cv.polygon(frame_pts([(-76, 44), (-44, 44), (-50, 58), (-70, 58)]),
               GREY_DK)
    # inner gold bevel
    for a, b in [((-252, -192), (252, -192)), ((252, -192), (252, 192)),
                 ((252, 192), (-252, 192)), ((-252, 192), (-252, -192))]:
        pa = frame_pts([a])[0]
        pb = frame_pts([b])[0]
        cv.thick_line(pa[0], pa[1], pb[0], pb[1], 5, GOLD_DK)
    # cracks radiating from the breach points (frame-local)
    for (ox, oy) in ((240, -60), (250, 60)):
        for k in range(5):
            ang = math.radians(-70 + k * 35)
            ln = 70 + k * 12
            ex, ey = ox + math.cos(ang) * ln, oy + math.sin(ang) * ln
            pa = frame_pts([(ox, oy)])[0]
            pb = frame_pts([(ex, ey)])[0]
            cv.thick_line(pa[0], pa[1], pb[0], pb[1], 4, (90, 96, 112))

    # 4. speed lines trailing the tail, inside the frame
    for _ in range(8):
        sx = rng.range(240, 400)
        sy = rng.range(480, 580)
        ln = rng.range(60, 170)
        dx, dy = -0.85, 0.5
        cv.thick_line(sx, sy, sx + dx * ln, sy + dy * ln,
                      int(rng.range(3, 6)),
                      rng.pick([PALE, WHITE, CYAN]))

    # 5. starburst rays fanning from behind the whale's head
    head = whale_point((368, -25))
    for k in range(9):
        ang = math.radians(-100 + k * 13)
        ln = rng.range(110, 200)
        tip = (head[0] + math.cos(ang) * ln, head[1] + math.sin(ang) * ln)
        perp = ang + math.pi / 2
        hw = rng.range(5, 9)
        base1 = (head[0] + math.cos(perp) * hw,
                 head[1] + math.sin(perp) * hw)
        base2 = (head[0] - math.cos(perp) * hw,
                 head[1] - math.sin(perp) * hw)
        cv.polygon([base1, tip, base2],
                   GOLD if k % 2 == 0 else WHITE)

    # 6. the whale: gradient from magenta tail to cyan head, along its axis
    tail = whale_point((-300, 0))
    headp = whale_point((360, 0))
    ax, ay = headp[0] - tail[0], headp[1] - tail[1]
    alen2 = ax * ax + ay * ay

    def whale_color(x, y):
        t = ((x - tail[0]) * ax + (y - tail[1]) * ay) / alen2
        return lerp3(MAGENTA, CYAN, t)

    cv.polygon(whale_transform(WHALE_BODY), color_fn=whale_color)
    # pectoral fin
    cv.polygon(whale_transform(WHALE_FIN), FIN)
    # pale belly stripe hugging the belly edge
    top = [(x, y - 18) for (x, y) in WHALE_BELLY_EDGE]
    bot = [(x, y - 3) for (x, y) in reversed(WHALE_BELLY_EDGE)]
    cv.polygon(whale_transform(top + bot), PALE)
    # smile line along the jaw + eye
    m0 = whale_point((225, 30))
    m1 = whale_point((335, 10))
    cv.thick_line(m0[0], m0[1], m1[0], m1[1], 9, DARK)
    eye = whale_point(WHALE_EYE)
    cv.disc(int(eye[0]), int(eye[1]), 20, WHITE)
    cv.disc(int(eye[0] + 4), int(eye[1] + 3), 9, (11, 16, 38))
    cv.disc(int(eye[0] - 5), int(eye[1] - 5), 4, WHITE)

    # 7. water spout bursting from the head
    spout = whale_point(WHALE_SPOUT_BASE)
    for i in range(9):
        ang = math.radians(-115 + i * 11)
        d = 18 + i * 14
        px = spout[0] + math.cos(ang) * d
        py = spout[1] + math.sin(ang) * d
        cv.disc(int(px), int(py), 4 + int(i * 1.2),
                WHITE if i % 2 == 0 else PALE)

    # 8. glass shards flying out of the frame (kept clear of the head)
    zones = [(690, 380, 800, 560, 5), (870, 300, 1010, 520, 4),
             (600, 40, 680, 110, 3), (640, 150, 720, 240, 2)]
    for (x0, y0, x1, y1, count) in zones:
        for _ in range(count):
            cx = rng.range(x0, x1)
            cy = rng.range(y0, y1)
            s = rng.range(12, 40)
            a = rng.range(0, 360)
            tri = [(0, -s), (-0.6 * s, 0.7 * s), (0.6 * s, 0.5 * s)]
            cv.polygon(move_pts(rot_pts(tri, a, 0, 0), cx, cy),
                       rng.pick([WHITE, GOLD_LT, PALE]))

    # 8b. water dripping from the breach, falling toward the shout
    for i in range(7):
        t = i / 6.0
        px = 700 + t * 130
        py = 660 + t * t * 130
        cv.disc(int(px), int(py), 4 + int((1 - t) * 5),
                WHITE if i % 2 == 0 else PALE)

    # 9. the shout, straight at the judge
    scale = 11
    line1 = "SURPRISE,"
    line2 = "JUDGE!"
    x1 = (W - text_width(line1, scale)) // 2
    x2 = (W - text_width(line2, scale)) // 2
    draw_text_outlined(cv, line1, x1, 812, scale, WHITE, MAGENTA, 7)
    draw_text_outlined(cv, line2, x2, 902, scale, WHITE, MAGENTA, 7)
    cv.fill_rect(x2, 992, text_width(line2, scale), 8, GOLD)


# ---- PNG writer (stdlib only) ---------------------------------------------
def _chunk(typ, data):
    out = struct.pack(">I", len(data)) + typ + data
    out += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
    return out


def write_png(path, cv):
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        raw += cv.px[y * W * 3:(y + 1) * W * 3]
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) +
           _chunk(b"IDAT", zlib.compress(bytes(raw), 9)) +
           _chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    cv = Canvas(W, H)
    draw_scene(cv)
    path = os.path.join(out_dir, "entry.png")
    write_png(path, cv)
    print("wrote", path)


if __name__ == "__main__":
    main()
