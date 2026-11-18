#!/usr/bin/env python3
"""THE WORLD TODAY - Wednesday 18 November 2026.

A program that draws the day's world news as a one-page newspaper front
page and writes it to /output/entry.png (1024 x 1024, PNG).

Pure Python 3.13 standard library: no network, no installed packages, no
font files at runtime. Text is rendered from bitmap glyphs in font_data.py
(DejaVu Sans, rendered at build time); the PNG is encoded with zlib.
Running the program twice writes identical bytes.

Layout: masthead, one lead story (the Gulf), two second stories (the Kerch
Bridge, the Manila-Shenzhen summits), three third stories (Cyclone Akvan,
Nvidia, Peltola), a sport band (Dhoni), an "also today" strip and a footer.
Every story was verified against reporting published on 18 November 2026.
"""

import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from font_data import BOLD, REGULAR  # noqa: E402

W = 1024
H = 1024

# Palette: newsprint paper, ink, and a restrained red/blue accent set.
PAPER = (247, 243, 234)
PAPER_DIM = (238, 232, 219)
INK = (20, 20, 20)
INK_SOFT = (58, 58, 58)
GREY = (120, 116, 108)
RULE = (30, 30, 30)
RED = (178, 34, 28)
RED_DARK = (140, 24, 20)
NAVY = (18, 38, 66)
NAVY_LIGHT = (32, 62, 102)
SEA = (23, 68, 104)
SEA_LIGHT = (46, 110, 150)
SAND = (214, 196, 158)
GOLD = (198, 148, 44)
SKY = (176, 205, 226)
WHITE = (255, 255, 255)
GREEN = (46, 110, 64)
TEAL = (16, 110, 110)


class Canvas:
    """An RGB raster with the few primitives a front page needs."""

    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(bytes(bg) * (w * h))

    def _idx(self, x, y):
        return (y * self.w + x) * 3

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = self._idx(x, y)
            self.px[i] = color[0]
            self.px[i + 1] = color[1]
            self.px[i + 2] = color[2]

    def blend(self, x, y, color, alpha):
        """Blend color over the pixel with coverage alpha (0-255)."""
        if alpha <= 0 or not (0 <= x < self.w and 0 <= y < self.h):
            return
        if alpha >= 255:
            self.set(x, y, color)
            return
        i = self._idx(x, y)
        a = alpha
        b = 255 - a
        self.px[i] = (color[0] * a + self.px[i] * b) // 255
        self.px[i + 1] = (color[1] * a + self.px[i + 1] * b) // 255
        self.px[i + 2] = (color[2] * a + self.px[i + 2] * b) // 255

    def rect(self, x, y, w, h, color):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1 - x0)
        for yy in range(y0, y1):
            i = self._idx(x0, yy)
            self.px[i:i + len(row)] = row

    def blend_rect(self, x, y, w, h, color, alpha):
        for yy in range(max(0, y), min(self.h, y + h)):
            for xx in range(max(0, x), min(self.w, x + w)):
                self.blend(xx, yy, color, alpha)

    def hline(self, x, y, w, color, thick=1):
        self.rect(x, y, w, thick, color)

    def vline(self, x, y, h, color, thick=1):
        self.rect(x, y, thick, h, color)

    def circle(self, cx, cy, r, color):
        """Filled circle by scanlines."""
        for dy in range(-r, r + 1):
            dx = int((r * r - dy * dy) ** 0.5)
            self.rect(cx - dx, cy + dy, 2 * dx + 1, 1, color)

    def ring(self, cx, cy, r, color, thick=2):
        for dy in range(-r, r + 1):
            dx = int((r * r - dy * dy) ** 0.5)
            inner = int(((r - thick) ** 2 - dy * dy) ** 0.5) if abs(dy) < r - thick else 0
            self.rect(cx - dx, cy + dy, dx - inner, 1, color)
            self.rect(cx + inner + 1, cy + dy, dx - inner, 1, color)

    def line(self, x0, y0, x1, y1, color, thick=1):
        """Thick line: stamp discs along the segment."""
        steps = max(abs(x1 - x0), abs(y1 - y0), 1) + 1
        r = max(1, thick // 2)
        for s in range(steps + 1):
            t = s / steps
            self.circle(int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t),
                        r, color)

    def poly(self, points, color):
        """Filled polygon by scanline."""
        if len(points) < 3:
            return
        ys = [p[1] for p in points]
        for y in range(max(0, min(ys)), min(self.h - 1, max(ys)) + 1):
            xs = []
            n = len(points)
            for i in range(n):
                x0, y0 = points[i]
                x1, y1 = points[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.rect(int(xs[i]), y, int(xs[i + 1]) - int(xs[i]) + 1, 1,
                          color)

    def png_bytes(self):
        """Encode the raster as a deterministic PNG (RGB, 8-bit)."""
        raw = bytearray()
        stride = self.w * 3
        prev = bytes(stride)
        for y in range(self.h):
            row = bytes(self.px[y * stride:(y + 1) * stride])
            # Try filters 0 (None) and 2 (Up); keep the smaller signed sum.
            best = None
            for ftype in (0, 2):
                if ftype == 0:
                    enc = row
                else:
                    enc = bytes(((row[i] - prev[i]) & 0xFF)
                                for i in range(stride))
                score = sum(b if b < 128 else b - 256 for b in enc)
                score = abs(score)
                if best is None or score < best[0]:
                    best = (score, ftype, enc)
            raw.append(best[1])
            raw.extend(best[2])
            prev = row
        comp = zlib.compress(bytes(raw), 9)

        def chunk(kind, data):
            out = struct.pack(">I", len(data)) + kind + data
            out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
            return out

        ihdr = struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0)
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
                + chunk(b"IDAT", comp) + chunk(b"IEND", b""))


# ---------------------------------------------------------------- text ---

MASTER = 64  # font_data glyphs are rendered at 64 px em height
_scaled_cache = {}


def _scaled_glyph(font, code, size):
    """Scale one glyph bitmap to `size` px em height (box-filtered).

    Returns (advance, width, height, left, top, bytes) in output pixels,
    where left/top are offsets from the em-box origin. Results are cached.
    """
    key = (id(font), code, size)
    hit = _scaled_cache.get(key)
    if hit is not None:
        return hit
    adv, w, h, left, top, hx = font.get(code, (0, 0, 0, 0, 0, ""))
    scale = size / MASTER
    out_adv = int(round(adv * scale))
    out_left = int(round(left * scale))
    out_top = int(round(top * scale))
    if w == 0 or h == 0:
        res = (out_adv, 0, 0, out_left, out_top, b"")
        _scaled_cache[key] = res
        return res
    src = bytes.fromhex(hx)
    out_w = max(1, int(round(w * scale)))
    out_h = max(1, int(round(h * scale)))
    buf = bytearray(out_w * out_h)
    for oy in range(out_h):
        sy0 = oy / scale
        sy1 = (oy + 1) / scale
        y0 = int(sy0)
        y1 = min(h, int(sy1) + 1)
        for ox in range(out_w):
            sx0 = ox / scale
            sx1 = (ox + 1) / scale
            x0 = int(sx0)
            x1 = min(w, int(sx1) + 1)
            total = 0
            weight = 0.0
            for sy in range(y0, y1):
                wy = min(sy1, sy + 1) - max(sy0, sy)
                if wy <= 0:
                    continue
                row = sy * w
                for sx in range(x0, x1):
                    wx = min(sx1, sx + 1) - max(sx0, sx)
                    if wx <= 0:
                        continue
                    total += src[row + sx] * wx * wy
                    weight += wx * wy
            buf[oy * out_w + ox] = int(total / weight) if weight else 0
    res = (out_adv, out_w, out_h, out_left, out_top, bytes(buf))
    _scaled_cache[key] = res
    return res


def text_width(s, size, font=BOLD):
    """Width of `s` in output pixels at `size` px em height."""
    total = 0
    for ch in s:
        total += _scaled_glyph(font, ord(ch), size)[0]
    return total


def draw_text(cv, x, y, s, size, color, font=BOLD, tracking=0):
    """Draw `s` with its em-box top at (x, y). Returns the end x."""
    cx = x
    for ch in s:
        adv, w, h, left, top, bmp = _scaled_glyph(font, ord(ch), size)
        if w and h:
            gx = cx + left
            gy = y + top
            for oy in range(h):
                row = oy * w
                for ox in range(w):
                    a = bmp[row + ox]
                    if a:
                        cv.blend(gx + ox, gy + oy, color, a)
        cx += adv + tracking
    return cx


def draw_text_centered(cv, cx, y, s, size, color, font=BOLD, tracking=0):
    w = text_width(s, size, font) + tracking * max(0, len(s) - 1)
    draw_text(cv, cx - w // 2, y, s, size, color, font, tracking)
    return w


def draw_text_right(cv, rx, y, s, size, color, font=BOLD, tracking=0):
    w = text_width(s, size, font) + tracking * max(0, len(s) - 1)
    draw_text(cv, rx - w, y, s, size, color, font, tracking)
    return w


def wrap(s, size, font, max_w):
    """Greedy word wrap; returns a list of lines fitting max_w."""
    words = s.split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_width(trial, size, font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_para(cv, x, y, s, size, color, font, max_w, leading=None):
    """Draw a wrapped paragraph; returns the y below its last line."""
    lh = leading if leading is not None else int(size * 1.32)
    for line in wrap(s, size, font, max_w):
        draw_text(cv, x, y, line, size, color, font)
        y += lh
    return y


# ------------------------------------------------------------ drawn art ---

def starburst(cv, cx, cy, r, color):
    """A jagged explosion burst: 12 spikes around a filled core."""
    pts = []
    for i in range(24):
        ang = i * 3.14159265 / 12.0
        rr = r if i % 2 == 0 else r * 0.45
        import math
        pts.append((int(cx + rr * math.cos(ang)),
                    int(cy + rr * math.sin(ang))))
    cv.poly(pts, color)
    cv.circle(cx, cy, max(2, r // 3), color)


def jet(cv, x, y, scale, color, flip=False):
    """A small fighter-jet silhouette (top view), nose pointing right."""
    s = scale
    pts = [
        (x + 0, y + 0), (x + 26 * s, y - 3 * s), (x + 34 * s, y + 0),
        (x + 26 * s, y + 3 * s), (x + 12 * s, y + 3 * s),
        (x + 16 * s, y + 9 * s), (x + 10 * s, y + 9 * s),
        (x + 6 * s, y + 3 * s), (x - 2 * s, y + 3 * s),
        (x + 2 * s, y + 0), (x - 2 * s, y - 3 * s),
        (x + 6 * s, y - 3 * s), (x + 10 * s, y - 9 * s),
        (x + 16 * s, y - 9 * s), (x + 12 * s, y - 3 * s),
    ]
    if flip:
        pts = [(2 * x - px, py) for px, py in pts]
    cv.poly(pts, color)


def drone(cv, x, y, scale, color):
    """A small quad-rotor drone silhouette."""
    s = scale
    cv.rect(x - 8 * s, y - 2 * s, 16 * s, 4 * s, color)
    cv.circle(x - 9 * s, y, 3 * s, color)
    cv.circle(x + 9 * s, y, 3 * s, color)
    cv.circle(x, y, 4 * s, color)
    cv.rect(x - 2 * s, y, 4 * s, 6 * s, color)


def bridge_motif(cv, x, y, w, h, color, water):
    """A suspension bridge whose middle span has collapsed into water."""
    # Water.
    cv.rect(x, y + h - 12, w, 12, water)
    for i in range(5):
        wx = x + 12 + i * (w - 24) // 4
        cv.line(wx, y + h - 6, wx + 22, y + h - 6, WHITE, 2)
    # Towers and standing deck.
    deck_y = y + h - 28
    cv.rect(x + 8, deck_y, w // 3, 5, color)
    cv.rect(x + 2 * w // 3 - 8, deck_y, w // 3 + 8, 5, color)
    for tx in (x + 30, x + w - 34):
        cv.rect(tx, y + 2, 5, deck_y - y + 3, color)
    # Cables from the towers.
    cv.line(x + 32, y + 4, x + w // 3, deck_y, color, 2)
    cv.line(x + w - 32, y + 4, x + 2 * w // 3, deck_y, color, 2)
    # The fallen span: tilted deck pieces in the water.
    cv.poly([(x + w // 3 + 4, deck_y + 2), (x + w // 2 - 6, deck_y + 16),
             (x + w // 2 + 2, deck_y + 19), (x + w // 3 + 12, deck_y + 6)],
            color)
    cv.poly([(x + w // 2 + 8, deck_y + 18), (x + 2 * w // 3 - 12, deck_y + 4),
             (x + 2 * w // 3 - 4, deck_y + 2), (x + w // 2 + 16, deck_y + 19)],
            color)
    # Debris burst where the span fell.
    starburst(cv, x + w // 2, deck_y + 10, 8, GOLD)


def cyclone_motif(cv, cx, cy, r, color, color2):
    """A spiral cyclone seen from above: concentric arcs + rain bands."""
    import math
    for k in range(5):
        rr = r * (0.25 + 0.19 * k)
        a0 = k * 1.15
        a1 = a0 + 4.4
        steps = 40
        prev = None
        for i in range(steps + 1):
            a = a0 + (a1 - a0) * i / steps
            px = int(cx + rr * math.cos(a))
            py = int(cy + rr * math.sin(a) * 0.92)
            if prev is not None:
                cv.line(prev[0], prev[1], px, py,
                        color if k % 2 == 0 else color2, 3)
            prev = (px, py)
    cv.circle(cx, cy, max(3, r // 8), color2)


def skyline(cv, x, y, w, h, color, color2):
    """A flat city skyline with lit windows, for the Manila panel."""
    import math
    heights = [0.55, 0.8, 0.62, 0.95, 0.7, 1.0, 0.66, 0.85, 0.58, 0.78,
               0.9, 0.63, 0.72, 0.5, 0.82, 0.68]
    n = len(heights)
    bw = w // n
    for i, f in enumerate(heights):
        bh = int(h * f)
        bx = x + i * bw
        cv.rect(bx + 1, y + h - bh, bw - 2, bh, color)
        for wy in range(y + h - bh + 8, y + h - 6, 12):
            for wx in range(bx + 5, bx + bw - 5, 10):
                if (wx * 7 + wy * 13) % 5 == 0:
                    cv.rect(wx, wy, 3, 4, color2)
    # Sun.
    cv.circle(x + w - 52, y + 26, 18, GOLD)
    cv.ring(x + w - 52, y + 26, 21, GOLD, 2)


def kicker(cv, x, y, label, color=RED):
    """Small red section label with a rule; returns the y below it."""
    draw_text(cv, x, y, label, 17, color, BOLD, tracking=1)
    return y + 24


# -------------------------------------------------------------- layout ---

MX = 36            # side margin
CW = W - 2 * MX    # content width: 952


def masthead(cv):
    draw_text(cv, MX, 30, "VOL. I — No. 322", 15, INK_SOFT, REGULAR)
    draw_text_right(cv, W - MX, 30, "PRICE: ONE IMAGE", 15, INK_SOFT, REGULAR)
    draw_text_centered(cv, W // 2, 46, "THE WORLD TODAY", 62, INK, BOLD,
                       tracking=2)
    cv.hline(MX, 126, CW, INK, 3)
    cv.hline(MX, 132, CW, INK, 1)
    draw_text_centered(cv, W // 2, 142, "WEDNESDAY, 18 NOVEMBER 2026",
                       20, RED, BOLD, tracking=3)
    draw_text_centered(cv, W // 2, 168,
                       "Summits in Manila and Shenzhen, war in the Gulf, "
                       "and a cyclone bearing down on India",
                       17, INK_SOFT, REGULAR)


def pill(cv, x, y, s, size=13, fg=WHITE, bg=NAVY):
    """A map label: white text on a small dark pill, for contrast."""
    w = text_width(s, size, BOLD) + 12
    h = size + 8
    cv.rect(x, y, w, h, bg)
    draw_text(cv, x + 6, y + 4, s, size, fg, BOLD)
    return w


def lead_scene(cv, x, y, w, h):
    """The Strait of Hormuz on Tuesday night: sea, coasts, jets, drones."""
    cv.rect(x, y, w, h, SEA)
    cv.rect(x, y, w, 26, SEA_LIGHT)  # lighter water at the top
    # Iran's coast along the top, Arabia along the bottom.
    cv.poly([(x, y), (x + w, y), (x + w, y + 34), (x + w * 0.62, y + 52),
             (x + w * 0.30, y + 30), (x, y + 44)], SAND)
    cv.poly([(x, y + h), (x + w, y + h), (x + w, y + h - 30),
             (x + w * 0.55, y + h - 48), (x + w * 0.22, y + h - 26),
             (x, y + h - 40)], SAND)
    # Qeshm Island, long and low in the strait.
    cv.poly([(x + int(w * 0.42), y + 78), (x + int(w * 0.78), y + 66),
             (x + int(w * 0.86), y + 82), (x + int(w * 0.74), y + 100),
             (x + int(w * 0.46), y + 104), (x + int(w * 0.38), y + 90)],
            (196, 172, 122))
    # Tanker in the strait, clear of the labels.
    cv.rect(x + int(w * 0.24), y + 118, 74, 12, (30, 30, 30))
    cv.rect(x + int(w * 0.24) + 8, y + 108, 14, 10, (30, 30, 30))
    cv.rect(x + int(w * 0.24) + 52, y + 110, 10, 8, RED)
    # Jets over Qeshm, drones over Bahrain.
    jet(cv, x + int(w * 0.52), y + 52, 1, WHITE)
    jet(cv, x + int(w * 0.66), y + 40, 1, (220, 220, 220))
    drone(cv, x + int(w * 0.10), y + 96, 1, WHITE)
    drone(cv, x + int(w * 0.20), y + 76, 1, (220, 220, 220))
    # Explosions on Qeshm.
    starburst(cv, x + int(w * 0.58), y + 84, 16, GOLD)
    starburst(cv, x + int(w * 0.58), y + 84, 9, (255, 120, 40))
    starburst(cv, x + int(w * 0.72), y + 76, 11, GOLD)
    # Place markers and labels.
    cv.circle(x + int(w * 0.08), y + 116, 4, RED)
    cv.circle(x + int(w * 0.30), y + 150, 4, RED)
    pill(cv, x + 8, y + 8, "IRAN")
    pill(cv, x + int(w * 0.44), y + 108, "QESHM ISLAND")
    pill(cv, x + int(w * 0.08) + 10, y + 110, "BAHRAIN")
    pill(cv, x + int(w * 0.30) + 10, y + 144, "KUWAIT")
    pill(cv, x + int(w * 0.58), y + 148, "STRAIT OF HORMUZ")


def lead(cv):
    y = 196
    kicker(cv, MX, y, "THE GULF  ·  WAR IN THE STRAIT")
    draw_text(cv, MX, 224, "U.S. jets hit Iran as", 46, INK, BOLD)
    draw_text(cv, MX, 272, "Gulf war widens", 46, INK, BOLD)
    lead_scene(cv, MX, 326, 560, 166)
    draw_text(cv, MX, 500,
              "The Strait of Hormuz, Tuesday night into Wednesday.",
              13, GREY, REGULAR)
    deck = ("American jets struck a Revolutionary Guard missile site on "
            "Qeshm Island on Tuesday, hours after Iranian drones targeted "
            "a U.S. radar base in Bahrain.")
    draw_para(cv, MX + 588, 326, deck, 18, INK, REGULAR, 364, leading=24)
    draw_para(cv, MX + 588, 434,
              "Kuwait's air defences engaged hostile drones early today. "
              "Three U.S. carrier groups now in the region.",
              17, RED, BOLD, 364, leading=22)


def story_col(cv, x, y, w, kick, head, head_size, deck, deck_size, art):
    y = kicker(cv, x, y, kick)
    y = draw_para(cv, x, y, head, head_size, INK, BOLD, w,
                  leading=head_size + 6)
    y += 2
    y = draw_para(cv, x, y, deck, deck_size, INK_SOFT, REGULAR, w,
                  leading=deck_size + 6)
    y += 10
    art(cv, x, y, w)
    return y


def row2(cv):
    y = 534
    cv.hline(MX, 522, CW, RULE, 2)
    # Left: the Kerch Bridge.
    story_col(cv, MX, y, 452, "UKRAINE  ·  THE WAR",
              "Bridge to Crimea falls into the sea", 29,
              "Ukraine struck the Kerch Bridge for a second day. Its road "
              "arch and span collapsed into the strait, cutting Russia's "
              "road link to Crimea. Two were killed.", 17,
              lambda c, x, yy, w: bridge_motif(c, x, yy, w, 46, NAVY, SEA))
    cv.vline(512, 534, 216, RULE, 1)
    # Right: Manila and Shenzhen.
    story_col(cv, 536, y, 452, "DIPLOMACY  ·  ASIA",
              "Trump in Manila; Xi and Putin await in Shenzhen", 29,
              "Trump met Quad leaders in Manila and Ferdinand Marcos Jr., "
              "then flew to APEC. On Thursday he joins Xi and Putin for "
              "the first-ever trilateral of the three.", 17,
              lambda c, x, yy, w: skyline(c, x, yy, w, 46, NAVY, GOLD))


def row3(cv):
    y = 774
    cv.hline(MX, 762, CW, RULE, 2)
    col_w = 301
    # Cyclone Akvan, with a small spiral at the top right of its column.
    kicker(cv, MX, y, "WEATHER  ·  INDIA")
    cyclone_motif(cv, MX + col_w - 22, y + 12, 15, SEA, NAVY)
    draw_para(cv, MX, y + 26, "Cyclone Akvan bears down on Andhra", 23, INK,
              BOLD, col_w, leading=28)
    draw_para(cv, MX, y + 84,
              "Landfall due Friday near noon between Nellore and Tuni; "
              "winds 120-130 kmph. Orange alert for Andhra Pradesh.",
              14, INK_SOFT, REGULAR, col_w, leading=18)
    # Nvidia, with three rising bars at the top right of its column.
    kicker(cv, 361, y, "MARKETS")
    for i, f in enumerate((0.45, 0.7, 1.0)):
        bh = int(26 * f)
        cv.rect(361 + col_w - 58 + i * 18, y + 26 - bh, 12, bh,
                NAVY_LIGHT if i < 2 else RED)
    draw_para(cv, 361, y + 26, "Nvidia revenue doubles to $115.8bn", 23, INK,
              BOLD, col_w, leading=28)
    draw_para(cv, 361, y + 84,
              "Sales rose 103% to $115.8bn; data-centre revenue hit "
              "$107.6bn. Founder Jensen Huang resigned days earlier.",
              14, INK_SOFT, REGULAR, col_w, leading=18)
    # Peltola, with a small 56-44 split bar at the top right.
    kicker(cv, 686, y, "WASHINGTON")
    cv.rect(686 + col_w - 64, y + 4, 36, 14, NAVY_LIGHT)
    cv.rect(686 + col_w - 28, y + 4, 28, 14, RED)
    draw_text(cv, 686 + col_w - 61, y + 6, "56", 11, WHITE, BOLD)
    draw_text(cv, 686 + col_w - 25, y + 6, "44", 11, WHITE, BOLD)
    draw_para(cv, 686, y + 26, "Peltola flips Alaska; Senate 56-44", 23, INK,
              BOLD, col_w, leading=28)
    draw_para(cv, 686, y + 84,
              "Mary Peltola beat Dan Sullivan - first Democrat to win "
              "Alaska's Senate seat since 2008, and the first Alaska "
              "Native senator.",
              14, INK_SOFT, REGULAR, col_w, leading=18)


def sport_band(cv):
    y = 928
    cv.rect(MX, y, CW, 46, PAPER_DIM)
    cv.rect(MX, y, 6, 46, RED)
    draw_text(cv, MX + 18, y + 6, "SPORT", 16, RED, BOLD)
    draw_text(cv, MX + 96, y + 6, "Dhoni calls time on 18 IPL seasons",
              21, INK, BOLD)
    draw_text(cv, MX + 18, y + 27,
              "MS Dhoni, 45, retires as a player - 278 matches, 5,439 runs, "
              "five titles. He becomes CSK mentor from 2027.",
              15, INK_SOFT, REGULAR)
    # Cricket ball, Dhoni's No. 7.
    cv.circle(W - MX - 24, y + 23, 13, RED)
    cv.circle(W - MX - 24, y + 23, 9, (200, 60, 50))
    draw_text_centered(cv, W - MX - 24, y + 16, "7", 14, WHITE, BOLD)


def footer(cv):
    draw_text(cv, MX, 984,
              "ALSO TODAY:  146,000 march in France  ·  Ebola in DR Congo "
              "tops 11,000 cases  ·  An-12 crash in Siberia kills 19  ·  "
              "India wholesale prices +12.29%",
              13, INK_SOFT, REGULAR)
    draw_text_centered(cv, W // 2, 1006,
                       "Sources: Reuters  ·  AP  ·  AFP  ·  Al Jazeera  ·  "
                       "IMD  ·  Times of India  —  compiled 18 November 2026",
                       12, GREY, REGULAR)


def build():
    cv = Canvas(W, H, PAPER)
    masthead(cv)
    lead(cv)
    row2(cv)
    row3(cv)
    sport_band(cv)
    footer(cv)
    return cv


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    data = build().png_bytes()
    with open(os.path.join(out_dir, "entry.png"), "wb") as f:
        f.write(data)
    print("wrote entry.png: %d bytes" % len(data))


if __name__ == "__main__":
    main()
