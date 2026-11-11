#!/usr/bin/env python3
"""
Build everything the whale ships as: the pill font AND the Marketplace icon,
both traced from one vector source, docs/images/icon_whale.svg.

Outputs:
  resources/dsh-bridge-icons.woff2  (`contributes.icons`, consumed as
      `$(dsh-bridge-whale)` in status-bar text; mechanism and font recipe
      copied from the proven companion, vLLM-Copilot scripts/build-icon-font.py:
      fontTools, em 1000, cmap in the private-use area, woff2 flavor)
        'dsh-whale'      U+E001  harness running: the whale, spouting
        'dsh-whale-off'  U+E002  harness stopped: spray gone; a whale that
                                 stopped spouting IS the resting state
  docs/images/icon.png            1024px RGBA, the same artwork in full color

Why the icon is regenerated too: one artwork, one source. Pill and gallery
are both rasterizations of the same paths, so they cannot drift apart.

The monochrome silhouette is the UNION of the inked paths, and the union is
taken at raster resolution, not in vector space: vector polygon booleans are
their own research field, and at the viewBox's own 1024 units per pixel this
loses nothing a 16px pill can show. Per-path fill uses the SVG default
nonzero rule with all subpaths of a path sharing one winding counter, which
is load-bearing: the eye and the spray's negative spaces are reversed
subpaths and would silently fill solid under the obvious per-subpath OR
(verified: path 0 group-nonzero 204652 = body 206110 - eye 1458).

Run:  python scripts/build-pill-font.py   (npm run icons:build)
Requires: fonttools (+ brotli for woff2)
Previews: temp/pill-preview.png (traced contours at 200px and at real pill
size, enlarged; a glyph unreadable at pill size is not a pill glyph).
"""

import os

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

import svggeom

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
SVG = os.path.join(ROOT, 'docs', 'images', 'icon_whale.svg')
ICON_PNG = os.path.join(ROOT, 'docs', 'images', 'icon.png')
FONT_OUT = os.path.join(ROOT, 'resources', 'dsh-bridge-icons.woff2')
RASTER = 1024  # the SVG viewBox is 0 0 1024 1024: one raster px per unit
ICON_SIZE = 1024  # square output px for the Marketplace icon
EM = 1000
EM_TARGET = 840  # glyph longest side inside the em, leaves side bearings
DP_TOLERANCE = 2.0  # raster units (1024 scale); 0.5 px on a 256 tile
SIMPLIFY_MIN = 48  # loops under this many points stay pixel-exact
MIN_COMPONENT = 200  # antialias specks are not glyph material at 1024


# ---------------------------------------------------------------------------
# Mask algebra (bytearray row masks).
# ---------------------------------------------------------------------------


def or_masks(masks, width, height):
    out = [bytearray(width) for _ in range(height)]
    for mask in masks:
        for y in range(height):
            row = out[y]
            src = mask[y]
            for x in range(width):
                if src[x]:
                    row[x] = 1
    return out


def mask_from_component(comp, width, height):
    out = [bytearray(width) for _ in range(height)]
    for x, y in comp:
        out[y][x] = 1
    return out


def components(mask, width, height):
    seen = [bytearray(width) for _ in range(height)]
    comps = []
    for y in range(height):
        for x in range(width):
            if not mask[y][x] or seen[y][x]:
                continue
            stack = [(x, y)]
            seen[y][x] = 1
            comp = []
            while stack:
                cx, cy = stack.pop()
                comp.append((cx, cy))
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < width and 0 <= ny < height and mask[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = 1
                        stack.append((nx, ny))
            comps.append(comp)
    comps.sort(key=len, reverse=True)
    return comps


def drop_small_components(mask, width, height, min_size):
    """Zero out components under min_size, in place, keeping holes intact.

    Rebuilding a mask FROM components would fill the eye and the spray gaps
    solid, so components are only used to find pixels to delete.
    """
    small = 0
    for comp in components(mask, width, height):
        if len(comp) < min_size:
            small += 1
            for x, y in comp:
                mask[y][x] = 0
    return small


# ---------------------------------------------------------------------------
# Trace: boundary walk, nesting, simplification.
# ---------------------------------------------------------------------------


def boundary_loops(mask, width, height):
    """Walk inside/outside unit edges into closed loops (corner coords).

    For every inside pixel, each side facing an outside pixel contributes one
    directed edge; at each corner the walk takes the sharpest clockwise turn,
    which keeps every loop consistently oriented and separates saddle crossings.
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


def trace_mask(mask, width, height):
    """Pixel mask -> [(loop, is_outer)] with bulky loops simplified.

    Douglas-Peucker runs only on loops above SIMPLIFY_MIN points: thin loops
    (the eye, the spray gaps) get deformed past their neighbors by their own
    chords, the exact failure the PNG-era trace measured when a simplified
    jet chord reached over the head and even-odd parity ate the snout.
    """
    classified = classify(boundary_loops(mask, width, height))
    return [(rdp(loop, DP_TOLERANCE) if len(loop) > SIMPLIFY_MIN else list(loop), outer)
            for loop, outer in classified]


# ---------------------------------------------------------------------------
# Font placement and drawing.
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
    state never resizes or shifts the whale. Returns (contours, diagnostics).
    """
    contours = []
    for loop, outer in zip(loops, is_outers):
        poly = [to_em(px, py) for px, py in loop]
        area = signed_area(poly)
        # TrueType y-up: outer must be clockwise (negative), counter positive.
        if (area > 0) == outer:
            poly.reverse()
        contours.append(poly)
    return contours, (len(loops), sum(len(c) for c in contours))


def draw_glyph(pen, contours):
    for poly in contours:
        pen.moveTo(poly[0])
        for pt in poly[1:]:
            pen.lineTo(pt)
        pen.closePath()


# ---------------------------------------------------------------------------
# PNG writing (stdlib): gray preview, RGBA icon.
# ---------------------------------------------------------------------------


def _png_chunk(kind, data):
    import struct
    import zlib
    body = kind + data
    return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body) & 0xFFFFFFFF)


def png_write_gray(path, width, height, pixels):
    import struct
    import zlib
    raw = b''.join(b'\x00' + bytes(pixels[y * width:(y + 1) * width]) for y in range(height))
    png = b'\x89PNG\r\n\x1a\n'
    png += _png_chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0))
    png += _png_chunk(b'IDAT', zlib.compress(raw, 9))
    png += _png_chunk(b'IEND', b'')
    with open(path, 'wb') as handle:
        handle.write(png)


def png_write_rgba(path, width, height, rgba):
    import struct
    import zlib
    raw = b''.join(b'\x00' + bytes(rgba[y * width * 4:(y + 1) * width * 4]) for y in range(height))
    png = b'\x89PNG\r\n\x1a\n'
    png += _png_chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
    png += _png_chunk(b'IDAT', zlib.compress(raw, 9))
    png += _png_chunk(b'IEND', b'')
    with open(path, 'wb') as handle:
        handle.write(png)


def render_icon(paths, out_path, out_size):
    """Painter-order composite of the SVG paths at 2x, box-downsampled for AA."""
    ss = out_size * 2
    masks = [svggeom.path_mask(subs, ss, ss) for _, subs in paths]
    colors = [svggeom.hex_rgb(fill) for fill, _ in paths]
    # Topmost path index per supersample pixel (painter order: last wins).
    top = [-1] * (ss * ss)
    for pi, mask in enumerate(masks):
        for y in range(ss):
            row = mask[y]
            base = y * ss
            for x in range(ss):
                if row[x]:
                    top[base + x] = pi
    out = bytearray(out_size * out_size * 4)
    f = ss // out_size
    for oy in range(out_size):
        for ox in range(out_size):
            rs = gs = bs = cov = 0
            for dy in range(f):
                sy = oy * f + dy
                srow = sy * ss + ox * f
                for dx in range(f):
                    pi = top[srow + dx]
                    if pi >= 0:
                        r, g, b = colors[pi]
                        rs += r
                        gs += g
                        bs += b
                        cov += 1
            if cov:
                i = (oy * out_size + ox) * 4
                out[i] = rs // cov
                out[i + 1] = gs // cov
                out[i + 2] = bs // cov
                out[i + 3] = 255 * cov // (f * f)
    png_write_rgba(out_path, out_size, out_size, out)


# ---------------------------------------------------------------------------
# Preview rendering from the traced contours (what the font will hold).
# ---------------------------------------------------------------------------


def render_preview(path, glyph_sets, size=200, strip=32, zoom=6):
    """White canvas per glyph at `size`, plus the same shape rasterized at
    real pill size (`strip`, shown zoomed `zoom`x nearest). A glyph that
    turns to mush at pill size is not a pill glyph."""
    pad = 10
    w = pad + (size + pad) * len(glyph_sets)
    h = pad + size + pad + strip * zoom + 20
    img = bytearray([255] * (w * h))

    def fill(points, ox, oy, target, cell=1):
        for py in range(target):
            for px in range(target):
                cx = px + 0.5
                cy = py + 0.5
                inside = False
                for poly in points:
                    if point_in_loop((cx, cy), poly):
                        inside = not inside
                if inside:
                    for dy in range(cell):
                        for dx in range(cell):
                            gx, gy = ox + px * cell + dx, oy + py * cell + dy
                            if 0 <= gx < w and 0 <= gy < h:
                                img[gy * w + gx] = 0

    # One shared bbox/scale for all panels, exactly like placement() shares
    # it in the font, so the two states are directly comparable.
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
    paths = svggeom.load_ink_paths(SVG)
    print(f'{SVG}: {len(paths)} inked paths')
    path_masks = [svggeom.path_mask(subs, RASTER, RASTER) for _, subs in paths]
    for (fill, subs), m in zip(paths, path_masks):
        print(f'  path {fill}: {len(subs)} subpaths, {sum(sum(r) for r in m)} px (group nonzero)')

    running_mask = or_masks(path_masks, RASTER, RASTER)
    dropped = drop_small_components(running_mask, RASTER, RASTER, MIN_COMPONENT)
    comps = components(running_mask, RASTER, RASTER)
    print(f'union: {sum(sum(r) for r in running_mask)} px, {len(comps)} components '
          f'{[len(c) for c in comps[:5]]}, dropped {dropped} specks')

    # Running glyph: the full union (body with eye hole + spray with gaps).
    simplified_on = trace_mask(running_mask, RASTER, RASTER)
    # Stopped glyph: the largest component only, body without spray. Pixels
    # of the other components are deleted, never the mask rebuilt, so the eye
    # hole survives the copy.
    stopped_mask = mask_from_component(comps[0], RASTER, RASTER)
    simplified_off = trace_mask(stopped_mask, RASTER, RASTER)

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
        'version': '1.1',
    })
    fb.setupOS2(sTypoAscender=EM, sTypoDescender=0, usWinAscent=EM, usWinDescent=0)
    fb.setupPost()
    os.makedirs(os.path.dirname(FONT_OUT), exist_ok=True)
    fb.font.flavor = 'woff2'
    fb.font.save(FONT_OUT)
    print(f'wrote {FONT_OUT} ({os.path.getsize(FONT_OUT)} bytes)')

    render_icon(paths, ICON_PNG, ICON_SIZE)
    print(f'wrote {ICON_PNG} ({os.path.getsize(ICON_PNG)} bytes, {ICON_SIZE}px RGBA)')
    print('wrote temp/pill-preview.png')


if __name__ == '__main__':
    main()
