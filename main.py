#!/usr/bin/env python3
"""Round 5 — "THEY FELL UP."

A chain of giant dominoes topples UPWARD, against gravity, along a
diagonal arc into a blazing portal of light in the top-right corner.
The smallest surprise with the biggest momentum: gravity lost.

Pure Python stdlib. Deterministic: fixed seed, no wall clock, no
network. Writes one 1024x1024 PNG to $MAKEFUN_OUTPUT_DIR/entry.png.
"""

import math
import os
import random
import struct
import zlib

W = H = 1024
OUT = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

# ---------------------------------------------------------------- PNG writer
def _chunk(typ, data):
    c = struct.pack(">I", len(data)) + typ + data
    c += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
    return c


def write_png(path, fb):
    raw = bytearray()
    for y in range(H):
        raw.append(0)  # filter: none
        raw += fb[y * W * 3:(y + 1) * W * 3]
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", ihdr)
    png += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += _chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


# ---------------------------------------------------------------- framebuffer
fb = bytearray(W * H * 3)


def blend_px(x, y, r, g, b, a):
    if 0 <= x < W and 0 <= y < H and a > 0.0:
        i = (y * W + x) * 3
        if a >= 1.0:
            fb[i] = r
            fb[i + 1] = g
            fb[i + 2] = b
        else:
            fb[i] = int(fb[i] + (r - fb[i]) * a)
            fb[i + 1] = int(fb[i + 1] + (g - fb[i + 1]) * a)
            fb[i + 2] = int(fb[i + 2] + (b - fb[i + 2]) * a)


def add_px(x, y, r, g, b, a):
    if 0 <= x < W and 0 <= y < H and a > 0.0:
        i = (y * W + x) * 3
        v = fb[i] + int(r * a)
        fb[i] = 255 if v > 255 else v
        v = fb[i + 1] + int(g * a)
        fb[i + 1] = 255 if v > 255 else v
        v = fb[i + 2] + int(b * a)
        fb[i + 2] = 255 if v > 255 else v


def fill_rect(x, y, w, h, color, alpha=1.0):
    x0 = max(0, int(x))
    y0 = max(0, int(y))
    x1 = min(W, int(x + w))
    y1 = min(H, int(y + h))
    if x1 <= x0 or y1 <= y0:
        return
    if alpha >= 1.0:
        row = bytes(color) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * W + x0) * 3
            fb[i:i + (x1 - x0) * 3] = row
    else:
        for yy in range(y0, y1):
            for xx in range(x0, x1):
                blend_px(xx, yy, color[0], color[1], color[2], alpha)


def fill_poly(pts, color, alpha=1.0, additive=False):
    """Convex polygon fill with ~1px antialiased edges."""
    area = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    if area < 0:
        pts = pts[::-1]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0 = max(0, int(math.floor(min(xs))))
    x1 = min(W - 1, int(math.ceil(max(xs))))
    y0 = max(0, int(math.floor(min(ys))))
    y1 = min(H - 1, int(math.ceil(max(ys))))
    edges = []
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        if L > 0:
            edges.append((ax, ay, dx, dy, L))
    if not edges:
        return
    for y in range(y0, y1 + 1):
        cur = [dx * (y - ay) - dy * (x0 - ax) for (ax, ay, dx, dy, L) in edges]
        for x in range(x0, x1 + 1):
            dmin = 1e9
            for k in range(len(edges)):
                d = cur[k] / edges[k][4]
                if d < dmin:
                    dmin = d
                cur[k] -= edges[k][3]  # cross decreases by dy per +1 x
            if dmin > -0.5:
                cov = dmin + 0.5
                if cov > 1.0:
                    cov = 1.0
                cov *= alpha
                if cov > 0.0:
                    if additive:
                        add_px(x, y, color[0], color[1], color[2], cov)
                    else:
                        blend_px(x, y, color[0], color[1], color[2], cov)


def fill_circle(cx, cy, r, color, alpha=1.0, additive=False):
    x0 = max(0, int(cx - r - 1))
    x1 = min(W - 1, int(cx + r + 1))
    y0 = max(0, int(cy - r - 1))
    y1 = min(H - 1, int(cy + r + 1))
    r_in = (r - 0.5) ** 2
    r_out = (r + 0.5) ** 2
    for y in range(y0, y1 + 1):
        dy = y - cy
        for x in range(x0, x1 + 1):
            dx = x - cx
            d2 = dx * dx + dy * dy
            if d2 <= r_in:
                cov = 1.0
            elif d2 >= r_out:
                continue
            else:
                cov = r + 0.5 - math.sqrt(d2)
            cov *= alpha
            if additive:
                add_px(x, y, color[0], color[1], color[2], cov)
            else:
                blend_px(x, y, color[0], color[1], color[2], cov)


def radial_glow(cx, cy, rx, ry, color, peak):
    x0 = max(0, int(cx - rx))
    x1 = min(W - 1, int(cx + rx))
    y0 = max(0, int(cy - ry))
    y1 = min(H - 1, int(cy + ry))
    for y in range(y0, y1 + 1):
        ny = (y - cy) / ry
        ny2 = ny * ny
        for x in range(x0, x1 + 1):
            nx = (x - cx) / rx
            d2 = nx * nx + ny2
            if d2 < 1.0:
                f = 1.0 - d2
                add_px(x, y, color[0], color[1], color[2], peak * f * f)


def sparkle(cx, cy, size, color, alpha=0.9):
    """Four-point star: two thin diamonds crossed."""
    w = size * 0.22
    fill_poly([(cx, cy - size), (cx + w, cy), (cx, cy + size), (cx - w, cy)],
              color, alpha=alpha, additive=True)
    fill_poly([(cx - size, cy), (cx, cy - w), (cx + size, cy), (cx, cy + w)],
              color, alpha=alpha, additive=True)


# ---------------------------------------------------------------- pixel font
# 5x7 glyphs, "#" = on. Only the glyphs the two text lines need.
FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10111", "10001", "10001", "01110"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
    "J": ["00111", "00010", "00010", "00010", "00010", "10010", "01100"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    ",": ["00000", "00000", "00000", "00000", "00100", "00100", "01000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
}


def text_width(s, scale):
    return len(s) * 6 * scale - scale


def _draw_text_raw(x, y, s, scale, color):
    cx = x
    for ch in s:
        g = FONT.get(ch)
        if g is not None:
            for row in range(7):
                bits = g[row]
                for col in range(5):
                    if bits[col] == "1":
                        fill_rect(cx + col * scale, y + row * scale,
                                  scale, scale, color)
        cx += 6 * scale


def draw_text(x, y, s, scale, color, outline=None, outline_off=3):
    if outline is not None:
        for dx, dy in ((-outline_off, 0), (outline_off, 0),
                       (0, -outline_off), (0, outline_off),
                       (-outline_off, -outline_off),
                       (outline_off, -outline_off),
                       (-outline_off, outline_off),
                       (outline_off, outline_off)):
            _draw_text_raw(x + dx, y + dy, s, scale, outline)
    _draw_text_raw(x, y, s, scale, color)


# ---------------------------------------------------------------- dominoes
PIP_PATTERNS = {
    1: [(0, 0)],
    2: [(-1, -1), (1, 1)],
    3: [(-1, -1), (0, 0), (1, 1)],
    4: [(-1, -1), (1, -1), (-1, 1), (1, 1)],
    5: [(-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)],
    6: [(-1, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (1, 1)],
}

FACE = (245, 233, 200)      # warm ivory domino face
RIM = (255, 176, 66)        # gold rim
PIP = (16, 20, 48)          # dark navy pips
SHADOW = (5, 8, 26)


def domino(cx, cy, w, h, angle_deg, top_pips, bot_pips):
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    hw, hh = w / 2.0, h / 2.0

    def corner(lx, ly):
        return (cx + lx * ca - ly * sa, cy + lx * sa + ly * ca)

    def quad(lx0, ly0, lx1, ly1, lx2, ly2, lx3, ly3):
        return [corner(lx0, ly0), corner(lx1, ly1),
                corner(lx2, ly2), corner(lx3, ly3)]

    # soft drop shadow, offset down-right
    sh = quad(-hw - 4, -hh - 4, hw + 4, -hh - 4, hw + 4, hh + 4, -hw - 4, hh + 4)
    sh = [(x + 9, y + 12) for (x, y) in sh]
    fill_poly(sh, SHADOW, alpha=0.40)
    # gold rim, then ivory face
    fill_poly(quad(-hw - 5, -hh - 5, hw + 5, -hh - 5, hw + 5, hh + 5, -hw - 5, hh + 5), RIM)
    fill_poly(quad(-hw, -hh, hw, -hh, hw, hh, -hw, hh), FACE)
    # divider line across the middle
    lw = max(2.5, w * 0.02)
    fill_poly(quad(-hw, -lw, hw, -lw, hw, lw, -hw, lw), (200, 180, 140))
    # pips: two halves, standard dice layouts
    ox, oy = w * 0.22, hh * 0.26
    pr = min(w * 0.055, hh * 0.09)
    for half_cy, count in ((-hh / 2.0, top_pips), (hh / 2.0, bot_pips)):
        for (gx, gy) in PIP_PATTERNS[count]:
            px, py = corner(gx * ox, half_cy + gy * oy)
            fill_circle(px, py, pr, PIP)


def streak(x, y, dx, dy, length, w0, w1, color, alpha):
    px, py = -dy, dx
    ex, ey = x + dx * length, y + dy * length
    fill_poly([(x + px * w0 / 2, y + py * w0 / 2),
               (x - px * w0 / 2, y - py * w0 / 2),
               (ex - px * w1 / 2, ey - py * w1 / 2),
               (ex + px * w1 / 2, ey + py * w1 / 2)],
              color, alpha=alpha, additive=True)


def lerp(c1, c2, t):
    return (int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t))


# ---------------------------------------------------------------- composition
PORTAL = (900, 170)

CHAIN = [  # (t along arc, top pips, bottom pips)
    (0.000, 6, 5),
    (0.143, 4, 6),
    (0.286, 6, 3),
    (0.429, 5, 5),
    (0.571, 2, 6),
    (0.714, 6, 6),
    (0.857, 3, 4),
    (1.000, 6, 6),
]


def chain_pos(t):
    x = 175 + 625 * t
    y = 895 - 600 * t - 55 * math.sin(math.pi * t)
    w = 150 - 68 * t
    h = 300 - 136 * t
    ang = 6 + 72 * t
    return x, y, w, h, ang


def main():
    rng = random.Random(20261116)

    # 1. night-sky gradient
    top = (9, 13, 42)
    mid = (22, 28, 78)
    bot = (7, 9, 30)
    for y in range(H):
        t = y / (H - 1)
        if t < 0.55:
            c = lerp(top, mid, t / 0.55)
        else:
            c = lerp(mid, bot, (t - 0.55) / 0.45)
        row = bytes(c) * W
        fb[y * W * 3:(y + 1) * W * 3] = row

    # 2. stars (fixed seed)
    for _ in range(240):
        sx = rng.uniform(0, W)
        sy = rng.uniform(0, H * 0.85)
        br = rng.uniform(0.25, 1.0)
        r = 1.0 if rng.random() < 0.8 else 2.0
        col = (255, 255, 255) if rng.random() < 0.7 else (170, 220, 255)
        fill_circle(sx, sy, r, col, alpha=br)
    for _ in range(12):
        sx = rng.uniform(40, W - 40)
        sy = rng.uniform(40, H * 0.6)
        sparkle(sx, sy, rng.uniform(5, 11), (255, 240, 200),
                alpha=rng.uniform(0.4, 0.8))

    # 3. portal glow + light rays fanning down-left
    radial_glow(PORTAL[0], PORTAL[1], 380, 380, (255, 140, 60), 0.30)
    radial_glow(PORTAL[0], PORTAL[1], 220, 220, (255, 190, 90), 0.55)
    for (bx1, by1, bx2, by2, a) in [
            (180, 640, 300, 700, 0.09),
            (380, 800, 520, 850, 0.08),
            (600, 880, 760, 920, 0.07)]:
        fill_poly([PORTAL, (bx1, by1), (bx2, by2)], (255, 190, 90),
                  alpha=a, additive=True)

    # 4. warm ground glow under the first domino
    radial_glow(300, 995, 430, 95, (255, 170, 80), 0.22)

    # 4b. dotted flight trail running parallel below-left of the chain:
    #     the path the dominoes are flying along, visible in the dark void
    tt = 0.0
    while tt <= 1.05:
        px, py, _w, _h, _a = chain_pos(tt)
        fill_circle(px - 40, py + 42, 3.5, (255, 200, 110),
                    alpha=0.5, additive=True)
        tt += 0.02

    # 5. portal ring + core (drawn before the dominoes so the last
    #    domino's tip can sink into the light)
    fill_circle(PORTAL[0], PORTAL[1], 118, (255, 176, 66))
    fill_circle(PORTAL[0], PORTAL[1], 104, (255, 240, 200))
    fill_circle(PORTAL[0], PORTAL[1], 86, (255, 252, 238))

    # 6. motion streaks trailing down-left (opposite the upward fall)
    for i, (t, _tp, _bp) in enumerate(CHAIN):
        cx, cy, w, h, ang = chain_pos(t)
        a = math.radians(ang)
        ca, sa = math.cos(a), math.sin(a)
        hw, hh = w / 2.0, h / 2.0
        bx = cx + (-hw) * ca - (hh * 0.6) * sa
        by = cy + (-hw) * sa + (hh * 0.6) * ca
        col = (255, 190, 90) if i % 2 == 0 else (110, 225, 255)
        streak(bx, by, -0.72, 0.69, 70 + 90 * t, 9, 2, col, 0.16)
        streak(bx + 26, by - 8, -0.72, 0.69, 50 + 60 * t, 6, 2, col, 0.11)

    # 7. dominoes, far first so near ones overlap
    for (t, tp, bp) in reversed(CHAIN):
        cx, cy, w, h, ang = chain_pos(t)
        domino(cx, cy, w, h, ang, tp, bp)

    # 8. the tip of the last domino ignites as it enters the portal
    radial_glow(878, 278, 130, 130, (255, 200, 110), 0.50)
    sparkle(852, 236, 16, (255, 244, 210), alpha=0.95)
    sparkle(912, 300, 12, (255, 220, 150), alpha=0.9)
    sparkle(830, 330, 9, (255, 240, 200), alpha=0.85)

    # 9. text addressed to the judge
    title = "THEY FELL UP."
    draw_text(56, 52, title, 9, (255, 246, 216),
              outline=(8, 10, 32), outline_off=4)
    fill_rect(56, 131, text_width(title, 9), 6, (255, 176, 66))
    draw_text(56, 152, "GRAVITY LOST, JUDGE.", 5, (140, 230, 255),
              outline=(8, 10, 32), outline_off=2)

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "entry.png")
    write_png(path, fb)
    print("WROTE %s %d bytes" % (path, os.path.getsize(path)))


if __name__ == "__main__":
    main()
