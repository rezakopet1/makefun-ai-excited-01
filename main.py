#!/usr/bin/env python3
"""ai-excited-01 ROUND 4 — "HEY JUDGE! THE MOON IS DANCING"

A giant disco-ball moon hangs over a night city. Its mirror tiles throw
beams of magenta, cyan and gold across the sky while tiny people dance on
a rooftop below. The twist: the moon — the calmest thing in the sky —
is the party. Pure Python stdlib, fully deterministic, no network.
"""
import math
import os
import struct
import zlib

W = H = 1024

# ---------------------------------------------------------------- RNG (fixed)
_state = 20261116


def rnd():
    global _state
    _state = (_state * 1103515245 + 12345) & 0x7FFFFFFF
    return _state / 0x7FFFFFFF


def rint(a, b):
    return a + int(rnd() * (b - a + 1))


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self):
        self.px = bytearray(W * H * 3)

    def set(self, x, y, c):
        if 0 <= x < W and 0 <= y < H:
            i = (y * W + x) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = c

    def blend(self, x, y, c, a):
        """Blend colour c over pixel with alpha a (0..255)."""
        if 0 <= x < W and 0 <= y < H:
            i = (y * W + x) * 3
            self.px[i] = (c[0] * a + self.px[i] * (255 - a)) // 255
            self.px[i + 1] = (c[1] * a + self.px[i + 1] * (255 - a)) // 255
            self.px[i + 2] = (c[2] * a + self.px[i + 2] * (255 - a)) // 255

    def rect(self, x0, y0, x1, y1, c):
        x0 = max(0, x0); y0 = max(0, y0)
        x1 = min(W - 1, x1); y1 = min(H - 1, y1)
        for y in range(y0, y1 + 1):
            i = (y * W + x0) * 3
            for x in range(x0, x1 + 1):
                self.px[i], self.px[i + 1], self.px[i + 2] = c
                i += 3

    def hline(self, x0, x1, y, c):
        if y < 0 or y >= H:
            return
        x0 = max(0, x0); x1 = min(W - 1, x1)
        i = (y * W + x0) * 3
        for _ in range(x0, x1 + 1):
            self.px[i], self.px[i + 1], self.px[i + 2] = c
            i += 3

    def disc(self, cx, cy, r, c):
        for dy in range(-r, r + 1):
            dx = int(math.sqrt(max(0, r * r - dy * dy)))
            self.hline(cx - dx, cx + dx, cy + dy, c)

    def ring(self, cx, cy, r, thick, c):
        for dy in range(-r - thick, r + thick + 1):
            d2 = dy * dy
            outer = int(math.sqrt(max(0, (r + thick) ** 2 - d2)))
            inner = int(math.sqrt(max(0, r * r - d2))) if abs(dy) <= r else -1
            if inner >= 0:
                self.hline(cx - outer, cx - inner - 1, cy + dy, c)
                self.hline(cx + inner + 1, cx + outer, cy + dy, c)
            else:
                self.hline(cx - outer, cx + outer, cy + dy, c)

    def line(self, x0, y0, x1, y1, c, w=1):
        dx = abs(x1 - x0); dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            for oy in range(-(w // 2), w // 2 + 1):
                for ox in range(-(w // 2), w // 2 + 1):
                    self.set(x0 + ox, y0 + oy, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy; x0 += sx
            if e2 <= dx:
                err += dx; y0 += sy

    def poly(self, pts, c, alpha=255):
        """Scanline fill of a simple polygon."""
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(H - 1, max(ys)) + 1):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    t = (y - y0) / (y1 - y0)
                    xs.append(int(x0 + t * (x1 - x0)))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                if alpha == 255:
                    self.hline(xs[k], xs[k + 1], y, c)
                else:
                    for x in range(max(0, xs[k]), min(W - 1, xs[k + 1]) + 1):
                        self.blend(x, y, c, alpha)


# ---------------------------------------------------------------- 5x7 font
FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "C": ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "G": ["01110", "10001", "10000", "10111", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
    "J": ["00111", "00010", "00010", "00010", "00010", "10010", "01100"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "!": ["00100", "00100", "00100", "00100", "00100", "00000", "00100"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
}


def draw_text(cv, text, cx, y, scale, colour, outline):
    widths = [5 * scale + scale for _ in text]
    total = sum(widths) - scale
    x = cx - total // 2
    for ch in text:
        g = FONT.get(ch, FONT[" "])
        for row in range(7):
            for col in range(5):
                if g[row][col] == "1":
                    # outline: stamp the scaled block shifted in 8 dirs
                    for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2),
                                   (-2, -2), (2, -2), (-2, 2), (2, 2)):
                        cv.rect(x + col * scale + ox, y + row * scale + oy,
                                x + col * scale + scale - 1 + ox,
                                y + row * scale + scale - 1 + oy, outline)
                    cv.rect(x + col * scale, y + row * scale,
                            x + col * scale + scale - 1,
                            y + row * scale + scale - 1, colour)
        x += 6 * scale


# ---------------------------------------------------------------- palette
NAVY_TOP = (8, 12, 48)
VIOLET_BOT = (52, 16, 74)
SILVER = (196, 205, 220)
SILVER_DK = (120, 130, 155)
GOLD = (255, 210, 63)
MAGENTA = (255, 60, 180)
CYAN = (45, 220, 255)
WHITE = (255, 255, 255)
INK = (10, 8, 26)
BUILDING = (16, 12, 38)
WINDOW = (255, 214, 120)

MOON_CX, MOON_CY, MOON_R = 512, 505, 268


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def draw(cv):
    # 1. sky gradient
    for y in range(H):
        c = lerp(NAVY_TOP, VIOLET_BOT, y / (H - 1))
        cv.hline(0, W - 1, y, c)

    # 2. stars
    for _ in range(260):
        x = rint(0, W - 1); y = rint(0, 700)
        b = rint(140, 255)
        cv.set(x, y, (b, b, min(255, b + 20)))
        if rnd() < 0.12:
            cv.set(x + 1, y, (b, b, b)); cv.set(x, y + 1, (b, b, b))

    # 3. light beams fanning down from behind the moon.
    # Screen coords: y grows downward, so a downward fan spans
    # angles ~25..155 deg from the +x axis (90 deg = straight down).
    beam_cols = [MAGENTA, CYAN, GOLD, MAGENTA, CYAN, GOLD, MAGENTA]
    for k, col in enumerate(beam_cols):
        ang = math.radians(25 + k * 21.6)
        x0 = MOON_CX + int(150 * math.cos(ang))
        y0 = MOON_CY + int(150 * math.sin(ang))
        x1 = MOON_CX + int(1150 * math.cos(ang - 0.045))
        y1 = MOON_CY + int(1150 * math.sin(ang - 0.045))
        x2 = MOON_CX + int(1150 * math.cos(ang + 0.045))
        y2 = MOON_CY + int(1150 * math.sin(ang + 0.045))
        cv.poly([(x0, y0), (x1, y1), (x2, y2)], col, alpha=64)

    # 3b. shooting star streaking past the moon (momentum).
    # Kept in the empty left sky (x < 220, clear of text and moon).
    cv.line(60, 260, 200, 340, WHITE, 3)
    cv.line(60, 260, 170, 325, (255, 210, 63), 2)
    cv.disc(60, 260, 6, WHITE)
    cv.disc(200, 340, 3, WHITE)

    # 4. glow halo behind the moon
    for r, a in ((MOON_R + 90, 14), (MOON_R + 55, 22), (MOON_R + 25, 30)):
        for dy in range(-r, r + 1):
            dx = int(math.sqrt(max(0, r * r - dy * dy)))
            for x in range(MOON_CX - dx, MOON_CX + dx + 1):
                cv.blend(x, MOON_CY + dy, (150, 190, 255), a)

    # 5. disco-ball moon: mirror tiles
    cv.disc(MOON_CX, MOON_CY, MOON_R, SILVER_DK)
    tile = 26
    palette = [SILVER, (168, 178, 205), (140, 200, 225), (225, 150, 205),
               (235, 205, 130), (110, 120, 148), (210, 220, 240)]
    gx0 = MOON_CX - MOON_R
    gy0 = MOON_CY - MOON_R
    for gy in range(gy0, MOON_CY + MOON_R, tile):
        for gx in range(gx0, MOON_CX + MOON_R, tile):
            cx = gx + tile // 2; cy = gy + tile // 2
            if (cx - MOON_CX) ** 2 + (cy - MOON_CY) ** 2 > (MOON_R - 6) ** 2:
                continue
            col = palette[rint(0, len(palette) - 1)]
            # shade by position: upper-left tiles brighter (light source)
            shade = 1.0 - 0.35 * ((cx - MOON_CX + MOON_R) / (2 * MOON_R)
                                 + (cy - MOON_CY + MOON_R) / (2 * MOON_R)) / 2
            col = tuple(max(0, min(255, int(v * shade))) for v in col)
            cv.rect(gx + 2, gy + 2, gx + tile - 2, gy + tile - 2, col)
            if rnd() < 0.06:  # mirror glint
                cv.rect(gx + 4, gy + 4, gx + tile - 4, gy + tile - 4, WHITE)
    cv.ring(MOON_CX, MOON_CY, MOON_R - 2, 4, (235, 240, 255))
    # crescent highlight on the upper-left rim
    for t in range(0, 101):
        ang = math.radians(150 + t * 1.1)
        x = MOON_CX + int((MOON_R - 8) * math.cos(ang))
        y = MOON_CY + int((MOON_R - 8) * math.sin(ang))
        cv.disc(x, y, 5, (255, 255, 255))

    # 6. sparkle glints on the rim
    for ang_deg, ln in ((35, 46), (125, 38), (215, 40), (305, 52)):
        ang = math.radians(ang_deg)
        x = MOON_CX + int((MOON_R + 6) * math.cos(ang))
        y = MOON_CY + int((MOON_R + 6) * math.sin(ang))
        cv.line(x - ln, y, x + ln, y, WHITE, 3)
        cv.line(x, y - ln, x, y + ln, WHITE, 3)

    # 7. confetti drifting down from the moon
    conf = [MAGENTA, CYAN, GOLD, WHITE, (120, 255, 170)]
    for _ in range(150):
        x = rint(20, W - 20); y = rint(200, 980)
        c = conf[rint(0, len(conf) - 1)]
        s = rint(3, 7)
        if rnd() < 0.5:
            cv.rect(x, y, x + s, y + s // 2, c)
        else:
            cv.disc(x, y, s // 2 + 1, c)

    # 8. city skyline
    bx = 0
    while bx < W:
        bw = rint(52, 110)
        bh = rint(90, 240)
        top = 1024 - bh
        cv.rect(bx, top, bx + bw, 1023, BUILDING)
        # antenna on some towers
        if rnd() < 0.3:
            cv.line(bx + bw // 2, top, bx + bw // 2, top - 26, BUILDING, 3)
            cv.set(bx + bw // 2, top - 28, (255, 80, 80))
        # lit windows
        for wy in range(top + 12, 1010, 26):
            for wx in range(bx + 8, bx + bw - 8, 20):
                if rnd() < 0.42:
                    wc = WINDOW if rnd() < 0.75 else (CYAN if rnd() < 0.5 else MAGENTA)
                    cv.rect(wx, wy, wx + 8, wy + 12, wc)
        bx += bw + rint(2, 14)

    # 9. rooftop party: one flat roof in the middle foreground
    roof_y = 800
    cv.rect(392, roof_y, 632, 1023, (24, 18, 52))
    cv.rect(392, roof_y, 632, roof_y + 6, (40, 30, 80))
    # string lights across the roof
    for i in range(13):
        x = 400 + i * 19
        y = roof_y - 14 + int(10 * math.sin(i * 0.9))
        cv.disc(x, y, 4, [GOLD, MAGENTA, CYAN, (120, 255, 170)][i % 4])
    # tiny dancing figures, arms up
    dancers = [(420, MAGENTA), (470, CYAN), (512, GOLD),
               (556, (120, 255, 170)), (600, WHITE)]
    for i, (dx, col) in enumerate(dancers):
        dy = roof_y - 26 - (6 if i % 2 else 0)
        cv.disc(dx, dy - 26, 7, col)                      # head
        cv.line(dx, dy - 19, dx, dy + 2, col, 4)          # body
        cv.line(dx, dy - 14, dx - 13, dy - 30, col, 3)    # arm L up
        cv.line(dx, dy - 14, dx + 13, dy - 30, col, 3)    # arm R up
        cv.line(dx, dy + 2, dx - 9, dy + 22, col, 3)      # leg L
        cv.line(dx, dy + 2, dx + 9, dy + 22, col, 3)      # leg R

    # 10. text to the judge
    draw_text(cv, "HEY JUDGE!", 512, 44, 11, GOLD, INK)
    draw_text(cv, "THE MOON IS DANCING", 512, 168, 5, WHITE, INK)


# ---------------------------------------------------------------- PNG writer
def chunk(typ, data):
    c = struct.pack(">I", len(data)) + typ + data
    return c + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)


def write_png(cv, path):
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        raw += cv.px[y * W * 3:(y + 1) * W * 3]
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


def main():
    cv = Canvas()
    draw(cv)
    out = os.environ.get("MAKEFUN_OUTPUT_DIR", "out")
    os.makedirs(out, exist_ok=True)
    write_png(cv, os.path.join(out, "entry.png"))


if __name__ == "__main__":
    main()
