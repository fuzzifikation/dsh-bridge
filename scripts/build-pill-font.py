#!/usr/bin/env python3
"""
Build the two-glyph pill font used by `contributes.icons`.

Output: resources/dsh-bridge-icons.woff2
  'dsh-whale'      at U+E001  harness running: the Marketplace whale, spouting
  'dsh-whale-off'  at U+E002  harness stopped: same whale, spray gone; the
                              shipped art already rests on a waterline bar

Mechanism copied from the proven companion (vLLM-Copilot scripts/
build-icon-font.py): a TrueType built by fontTools, flavor woff2, glyphs in
the private-use area, consumed as `$(dsh-bridge-whale)` in status-bar text.
Same contribution point, same rendering path, same 1.140 proof.

The outlines are traced, not hand-drawn: docs/images/icon.png is decoded in
pure stdlib (RGBA, 8-bit, non-interlaced), thresholded to a mask, split into
connected components (body vs spout jets), and its boundary walked as directed
unit edges; loops are classified outer/hole by nesting depth, simplified with
Ramer-Douglas-Peucker, then forced to TrueType winding (y-up: outer
clockwise, counter counter-clockwise). Tracing the SHIPPED marketplace icon
means pill and gallery can never drift apart.

Run:  python scripts/build-pill-font.py
Requires: fonttools (+ brotli for woff2)
Previews: temp/pill-preview.png (rendered from the traced contours, incl. a
16px strip, because a glyph unreadable at pill size is not a glyph).
"""

import os
import struct
import zlib

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
SOURCE = os.path.join(ROOT, 'docs', 'images', 'icon.png')
EM = 1000
EM_TARGET = 840  # glyph longest side inside the em, leaves side bearings
ALPHA_MIN = 24  # the spout paint is translucent; 128 silently eats the jets
DP_TOLERANCE = 0.9  # px on the 256 source, applied only to bulky loops
SIMPLIFY_MIN = 200  # points below which a loop stays pixel-exact (see simplify_loop)
MIN_COMPONENT = 16  # antialias specks in the source are not glyph material

# ---------------------------------------------------------------------------
# PNG decode (8-bit RGBA, non-interlaced): the shipped icon, stdlib only.
# ---------------------------------------------------------------------------


def read_png_rgba(path):
    with open(path, 'rb') as handle:
        data = handle.read()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise SystemExit(f'{path}: not a PNG')
    pos = 8
    width = height = 0
    idat = bytearray()
    while pos < len(data):
        (length,) = struct.unpack('>I', data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        if kind == b'IHDR':
            width, height, depth, color, compression, filter_mode, interlace = struct.unpack('>IIBBBBB', chunk)
            if depth != 8 or color != 6 or interlace != 0:
                raise SystemExit(f'{path}: need 8-bit RGBA non-interlaced, got depth={depth} color={color} interlace={interlace}')
        elif kind == b'IDAT':
            idat += chunk
        elif kind == b'IEND':
            break
        pos += 12 + length
    raw = zlib.decompress(bytes(idat))
    stride = width * 4
    out = bytearray(height * stride)

    def paeth(a, b, c):
        p = a + b - c
        pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
        return a if pa <= pb and pa <= pc else (b if pb <= pc else c)

    ipos = 0
    for y in range(height):
        ftype = raw[ipos]
        ipos += 1
        line = bytearray(raw[ipos:ipos + stride])
        ipos += stride
        prev = out[(y - 1) * stride:y * stride] if y else bytes(stride)
        if ftype == 1:
            for x in range(4, stride):
                line[x] = (line[x] + line[x - 4]) & 0xFF
        elif ftype == 2:
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 0xFF
        elif ftype == 3:
            for x in range(stride):
                a = line[x - 4] if x >= 4 else 0
                line[x] = (line[x] + ((a + prev[x]) >> 1)) & 0xFF
        elif ftype == 4:
            for x in range(stride):
                a = line[x - 4] if x >= 4 else 0
                c = prev[x - 4] if x >= 4 else 0
                line[x] = (line[x] + paeth(a, prev[x], c)) & 0xFF
        elif ftype != 0:
            raise SystemExit(f'{path}: unknown filter {ftype}')
        out[y * stride:(y + 1) * stride] = line
    return width, height, out


# ---------------------------------------------------------------------------
# Mask, components, boundary walk.
# ---------------------------------------------------------------------------


def alpha_mask(width, height, rgba):
    return [[rgba[(y * width + x) * 4 + 3] >= ALPHA_MIN for x in range(width)] for y in range(height)]


def components(mask, width, height):
    seen = [[False] * width for _ in range(height)]
    comps = []
    for y in range(height):
        for x in range(width):
            if not mask[y][x] or seen[y][x]:
                continue
            stack = [(x, y)]
            seen[y][x] = True
            comp = []
            while stack:
                cx, cy = stack.pop()
                comp.append((cx, cy))
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < width and 0 <= ny < height and mask[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            comps.append(comp)
    comps.sort(key=len, reverse=True)
    return comps


def boundary_loops(mask, width, height):
    """Walk inside/outside unit edges into closed loops (corner coords).

    Convention: for every inside pixel, each side facing an outside pixel
    contributes one directed edge (fixed orientation per side, see below);
    at each corner the walk takes the sharpest clockwise turn, which keeps
    every loop consistently oriented and separates saddle crossings.
    """
    edges = {}  # corner -> list of other endpoints (directed out)

    def add(a, b):
        edges.setdefault(a, []).append(b)

    for y in range(height):
        for x in range(width):
            if not mask[y][x]:
                continue
            up = mask[y - 1][x] if y > 0 else False
            down = mask[y + 1][x] if y + 1 < height else False
            left = mask[y][x - 1] if x > 0 else False
            right = mask[y][x + 1] if x + 1 < width else False
            if not up:
                add((x, y), (x + 1, y))
            if not right:
                add((x + 1, y), (x + 1, y + 1))
            if not down:
                add((x + 1, y + 1), (x, y + 1))
            if not left:
                add((x, y + 1), (x, y))

    loops = []
    used = set()
    for start_a, outs in edges.items():
        for first in outs:
            if (start_a, first) in used:
                continue
            loop = [start_a]
            a, b = start_a, first
            while True:
                used.add((a, b))
                loop.append(b)
                if b == start_a:
                    break
                cands = [c for c in edges.get(b, []) if (b, c) not in used]
                if not cands:
                    raise SystemExit('boundary walk stalled: non-manifold edge set')
                dx1, dy1 = b[0] - a[0], b[1] - a[1]
                # sharpest clockwise turn in y-down coords == largest cross, then dot
                def score(c):
                    dx2, dy2 = c[0] - b[0], c[1] - b[1]
                    return (dx1 * dy2 - dy1 * dx2, dx1 * dx2 + dy1 * dy2)
                nxt = max(cands, key=score)
                a, b = b, nxt
            loop.pop()  # repeat of start
            loops.append(loop)
    return loops


def point_in_loop(pt, loop):
    x, y = pt
    inside = False
    j = len(loop) - 1
    for i in range(len(loop)):
        xi, yi = loop[i]
        xj, yj = loop[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def classify(loops):
    """Return [(loop, is_outer)] by nesting depth: even = outer, odd = hole."""
    out = []
    for i, loop in enumerate(loops):
        depth = sum(1 for j, other in enumerate(loops) if j != i and point_in_loop(loop[0], other))
        out.append((loop, depth % 2 == 0))
    return out


# ---------------------------------------------------------------------------
# Ramer-Douglas-Peucker on closed loops.
# ---------------------------------------------------------------------------


def _perp(pt, a, b):
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        if dx == dy == 0:
            return ((pt[0] - ax) ** 2 + (pt[1] - ay) ** 2) ** 0.5
        num = abs(dy * pt[0] - dx * pt[1] + bx * ay - by * ax)
        return num / (dx * dx + dy * dy) ** 0.5


def rdp(points, eps):
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        s, e = stack.pop()
        if e <= s + 1:
            continue
        far, dist = -1, 0.0
        for i in range(s + 1, e):
            d = _perp(points[i], points[s], points[e])
            if d > dist:
                far, dist = i, d
        if far >= 0 and dist > eps:
            keep[far] = True
            stack.append((s, far))
            stack.append((far, e))
    return [p for p, k in zip(points, keep) if k]


def simplify_loop(loop, eps):
    """Ramer-Douglas-Peucker for BULKY loops only, decided by the caller.

    Thin translucent loops (mouth slit, the lens between the jet arcs) DO
    get deformed by their own chords at any sane eps: measured, DP at 0.9
    flips even-odd parity over the head and eats the snout. Big outer loops
    simplify cleanly (verified render). Small loops stay pixel-exact; the
    font budget does not care.
    """
    return rdp(loop, eps)


# ---------------------------------------------------------------------------
# Font.
# ---------------------------------------------------------------------------


def signed_area(poly):
    n = len(poly)
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))


def placement(loops):
    """Shared bbox/scale for every glyph of this font, from the running glyph."""
    xs = [p[0] for loop in loops for p in loop]
    ys = [p[1] for loop in loops for p in loop]
    x_min, y_min, x_max, y_max = min(xs), min(ys), max(xs), max(ys)
    scale = EM_TARGET / max(x_max - x_min, y_max - y_min)
    left = (EM - (x_max - x_min) * scale) / 2.0
    bottom = (EM - (y_max - y_min) * scale) / 2.0

    def to_em(px, py):
        return (left + (px - x_min) * scale, EM - bottom - (py - y_min) * scale)

    return to_em


def contours_to_em(loops, is_outers, to_em):
    """Pixel loops (y-down) -> em-unit polygon contours (y-up), outer CW.

    `to_em` comes from placement() over the RUNNING glyph, so switching pill
    state never resizes or shifts the whale.
    Returns (contours, diagnostics).
    """
    contours = []
    for loop, outer in zip(loops, is_outers):
        poly = [to_em(px, py) for px, py in loop]
        area = signed_area(poly)
        # TrueType y-up: outer must be clockwise (negative), counter positive.
        if (area > 0) == outer:
            poly.reverse()
            area = -area
        contours.append(poly)
    return contours, (len(loops), sum(len(c) for c in contours))


def draw_glyph(pen, contours):
    for poly in contours:
        pen.moveTo(poly[0])
        for pt in poly[1:]:
            pen.lineTo(pt)
        pen.closePath()


# ---------------------------------------------------------------------------
# Preview rendering from the traced contours only (what the font will hold).
# ---------------------------------------------------------------------------


def png_write_gray(path, width, height, pixels):
    raw = b''.join(b'\x00' + bytes(pixels[y * width:(y + 1) * width]) for y in range(height))

    def chunk(kind, data):
        body = kind + data
        return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body) & 0xFFFFFFFF)

    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(raw, 9))
    png += chunk(b'IEND', b'')
    with open(path, 'wb') as handle:
        handle.write(png)


def render_preview(path, glyph_sets, size=200, strip=32, zoom=6):
    """White canvas per glyph at `size`, plus the same shape rasterized at
    real pill size (`strip`, shown zoomed `zoom`x nearest). A glyph that
    turns to mush at 32px is not a pill glyph, and 200px beauty shots hide
    exactly that."""
    pad = 10
    w = pad + (size + pad) * len(glyph_sets)
    h = pad + size + pad + strip * zoom + 20
    img = bytearray([255] * (w * h))

    def fill(contours, ox, oy, target, cell=1):
        for py in range(target):
            for px in range(target):
                cx = px + 0.5
                cy = py + 0.5
                inside = False
                for poly in contours:
                    if point_in_loop((cx, cy), poly):
                        inside = not inside
                if inside:
                    for dy in range(cell):
                        for dx in range(cell):
                            gx, gy = ox + px * cell + dx, oy + py * cell + dy
                            if 0 <= gx < w and 0 <= gy < h:
                                img[gy * w + gx] = 0

    # Contours arrive in pixel space (y-down). One shared bbox/scale for all
    # panels, exactly like placement() shares it in the font, so the two
    # states are directly comparable.
    xs = [p[0] for c in glyph_sets for loop in c for p in loop]
    ys = [p[1] for c in glyph_sets for loop in c for p in loop]
    x0, y0 = min(xs), min(ys)
    s = (size - 8) / max(max(xs) - x0, max(ys) - y0)
    s16 = (strip - 2) / max(max(xs) - x0, max(ys) - y0)
    for i, contours in enumerate(glyph_sets):
        fill([[((px - x0) * s, (py - y0) * s) for px, py in loop] for loop in contours], pad + i * (size + pad) + 4, pad + 4, size)
        fill([[((px - x0) * s16, (py - y0) * s16) for px, py in loop] for loop in contours], pad + i * (size + pad), pad + size + pad + 2, strip, zoom)
    png_write_gray(path, w, h, img)


def main():
    out_woff2 = os.path.join(ROOT, 'resources', 'dsh-bridge-icons.woff2')
    width, height, rgba = read_png_rgba(SOURCE)
    mask = alpha_mask(width, height, rgba)
    comps = components(mask, width, height)
    keep = [c for c in comps if len(c) >= MIN_COMPONENT]
    print(f'{SOURCE}: {width}x{height}, {len(comps)} components, kept sizes={[len(c) for c in keep]}')

    # Running glyph: every real component (body + fused spout jets), holes included.
    on_mask = [[False] * width for _ in range(height)]
    for comp in keep:
        for x, y in comp:
            on_mask[y][x] = True
    classified_on = classify(boundary_loops(on_mask, width, height))
    simplified_on = [(simplify_loop(loop, DP_TOLERANCE) if len(loop) > SIMPLIFY_MIN else list(loop), outer)
                     for loop, outer in classified_on]

    # Stopped glyph: the body component alone. The shipped whale already
    # rests on a flat waterline bar, so dropping the spray (activity) needs
    # no cropping: a whale that stopped spouting IS the resting state.
    body_mask = [[False] * width for _ in range(height)]
    for x, y in keep[0]:
        body_mask[y][x] = True
    classified_off = classify(boundary_loops(body_mask, width, height))
    simplified_off = [(simplify_loop(loop, DP_TOLERANCE) if len(loop) > SIMPLIFY_MIN else list(loop), outer)
                      for loop, outer in classified_off]

    print('running glyph: loops=%s points=%s' % (
        [(len(loop), 'o' if outer else 'h') for loop, outer in simplified_on],
        sum(len(loop) for loop, _ in simplified_on)))
    print('stopped glyph: loops=%s points=%s' % (
        [(len(loop), 'o' if outer else 'h') for loop, outer in simplified_off],
        sum(len(loop) for loop, _ in simplified_off)))

    to_em = placement([loop for loop, _ in simplified_on])
    contours_on, diag_on = contours_to_em([l for l, _ in simplified_on], [o for _, o in simplified_on], to_em)
    contours_off, diag_off = contours_to_em([l for l, _ in simplified_off], [o for _, o in simplified_off], to_em)
    print('em contours:', diag_on, diag_off)

    render_preview(
        os.path.join(ROOT, 'temp', 'pill-preview.png'),
        [[list(loop) for loop, _ in simplified_on],
         [list(loop) for loop, _ in simplified_off]],
    )

    pen = TTGlyphPen(None)
    draw_glyph(pen, contours_on)
    glyph_on = pen.glyph()
    pen = TTGlyphPen(None)
    draw_glyph(pen, contours_off)
    glyph_off = pen.glyph()
    notdef = TTGlyphPen(None).glyph()

    fb = FontBuilder(EM, isTTF=True)
    fb.setupGlyphOrder(['.notdef', 'dsh-whale', 'dsh-whale-off'])
    fb.setupCharacterMap({0xE001: 'dsh-whale', 0xE002: 'dsh-whale-off'})
    fb.setupGlyf({'.notdef': notdef, 'dsh-whale': glyph_on, 'dsh-whale-off': glyph_off})
    fb.setupHorizontalMetrics({'.notdef': (EM, 0), 'dsh-whale': (EM, 0), 'dsh-whale-off': (EM, 0)})
    fb.setupHorizontalHeader(ascent=EM, descent=0)
    fb.setupNameTable({
        'familyName': 'DSH Bridge Pill Icons',
        'styleName': 'Regular',
        'uniqueFontIdentifier': 'dsh-bridge pill icons',
        'fullName': 'DSH Bridge Pill Icons',
        'psName': 'dsh-bridge-pill-icons',
        'version': '1.0',
    })
    fb.setupOS2(sTypoAscender=EM, sTypoDescender=0, usWinAscent=EM, usWinDescent=0)
    fb.setupPost()
    os.makedirs(os.path.dirname(out_woff2), exist_ok=True)
    fb.font.flavor = 'woff2'
    fb.font.save(os.path.normpath(out_woff2))
    print(f'wrote {os.path.normpath(out_woff2)} ({os.path.getsize(out_woff2)} bytes)')
    print('wrote temp/pill-preview.png')


if __name__ == '__main__':
    main()
