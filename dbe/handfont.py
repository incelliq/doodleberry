"""Handwriting fonts from an artist's samples (WP-29).

1. **The sheet** (`sheet`): a printable page (A4 at 300 dpi, PNG and PDF) with one box per character in a grid. Each
   box has a small grey label of the character it wants, a baseline and an x-height line, all in a light blue that
   drops out of a scan. Black squares in the four corners register the page. sheet.json records the layout.
2. **The scan** (`read_scan`): the four corner squares are found and the page is warped back to the sheet's geometry,
   so a photo or a slightly skewed scan works. In each box the ink is everything darker than the guides; specks are
   removed.
3. **The glyphs** (`trace`): each box's ink is traced by potrace (the vendored 1.16, GPL, built by vendor.build) into
   cubic outlines. They are placed in font units with the box's baseline at y = 0 and the x-height line at the
   font's x-height, so letters keep the size and the height on the line the artist gave them. Side bearings are set
   from the ink's extent.
4. **The font** (`build`): an OpenType (CFF) font made with fontTools' FontBuilder (cmap, metrics, a space, the
   artist's name in the name table), saved with a preview.
"""
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

DPI = 300
PAGE_MM = (210, 297)
GUIDE = (150, 200, 235)      # light blue: guides drop out of a scan (luminance well above the ink threshold)
LABEL = (175, 175, 175)
DEFAULT_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,!?'-:;()"
UPM, XH, CAP = 1000, 500, 700


def mm(v):
    return round(v / 25.4 * DPI)


def layout(chars, cols=8, margin_mm=16.0):
    """the sheet's geometry in pixels: page size, corner marks, and each character's box with its guides (the boxes
    as large as the page width allows at that many columns)"""
    W, H = mm(PAGE_MM[0]), mm(PAGE_MM[1]); m = mm(margin_mm); gap = mm(2.5); top = m + mm(14)
    b = (W - 2 * m - (cols - 1) * gap) // cols
    cells = []
    for i, ch in enumerate(chars):
        r, c = divmod(i, cols); x, y = m + c * (b + gap), top + r * (b + gap + mm(3))
        cells.append({"char": ch, "box": [x, y, x + b, y + b], "baseline": y + round(b * 0.72), "xheight": y + round(b * 0.47)})
    if cells and cells[-1]["box"][3] > H - m:
        raise ValueError(f"{len(chars)} characters do not fit one sheet at {cols} columns; use more columns or two sheets")
    s = mm(6)
    marks = [[m - s - mm(4), m - s - mm(4)], [W - m + mm(4), m - s - mm(4)], [m - s - mm(4), H - m + mm(4)], [W - m + mm(4), H - m + mm(4)]]
    return {"dpi": DPI, "size": [W, H], "mark": s, "marks": marks, "cells": cells, "box_px": b}


def sheet(chars, out_png, title="Handwriting sheet", cols=8):
    """draw the printable sheet -> its layout (also written beside it as .json)"""
    L = layout(chars, cols); W, H = L["size"]
    im = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(im)
    f_small = _font(mm(3)); f_title = _font(mm(5))
    d.text((mm(16), mm(9)), title, fill=(60, 60, 60), font=f_title)
    d.text((mm(16), mm(16)), "One character per box, sitting on the lower line; small letters reach the upper line. Dark pen; keep the corner squares in the scan.", fill=(110, 110, 110), font=f_small)
    for x, y in L["marks"]:
        d.rectangle([x, y, x + L["mark"], y + L["mark"]], fill="black")
    for c in L["cells"]:
        x0, y0, x1, y1 = c["box"]
        d.rectangle(c["box"], outline=GUIDE, width=3)
        d.line([x0, c["baseline"], x1, c["baseline"]], fill=GUIDE, width=3)
        d.line([x0, c["xheight"], x1, c["xheight"]], fill=GUIDE, width=2)
        d.text((x0 + mm(1), y1 + mm(0.4)), c["char"], fill=LABEL, font=f_small)
    im.save(out_png, dpi=(DPI, DPI)); im.save(Path(out_png).with_suffix(".pdf"), resolution=DPI)
    Path(out_png).with_suffix(".json").write_text(json.dumps({"chars": chars, "cols": cols, **L}, ensure_ascii=False))
    return L


def _font(px):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if Path(p).exists():
            return ImageFont.truetype(p, px)
    return ImageFont.load_default()


def _find_marks(gray, L):
    """the four corner squares: the darkest square blobs of the mark's size nearest each corner"""
    import cv2
    H, W = gray.shape
    k = gray.shape[1] / L["size"][0]   # scans at another resolution
    _, bw = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)
    n, lab, st, cen = cv2.connectedComponentsWithStats(bw)
    want = (L["mark"] * k) ** 2
    cand = [(cen[i], st[i]) for i in range(1, n) if 0.4 * want < st[i][4] < 2.0 * want and 0.6 < st[i][2] / max(1, st[i][3]) < 1.6 and st[i][4] > 0.7 * st[i][2] * st[i][3]]
    if len(cand) < 4:
        raise ValueError(f"found {len(cand)} of the 4 corner marks: scan the whole page")
    corners = [(0, 0), (W, 0), (0, H), (W, H)]
    pts = []
    for cx, cy in corners:
        c = min(cand, key=lambda q: (q[0][0] - cx) ** 2 + (q[0][1] - cy) ** 2); pts.append(c[0])
    return np.float32(pts)


def read_scan(scan_path, L):
    """-> the page warped to the sheet's geometry (grey, uint8)"""
    import cv2
    im = np.asarray(Image.open(scan_path).convert("L"))
    src = _find_marks(im, L); s = L["mark"] / 2
    dst = np.float32([[x + s, y + s] for x, y in L["marks"]])
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(im, M, tuple(L["size"]), flags=cv2.INTER_LINEAR, borderValue=255)


def cell_ink(page, c, thresh=110, min_area=40):
    """a box's ink as a boolean array (guides dropped by the threshold, the border inset, specks removed)"""
    import cv2
    x0, y0, x1, y1 = c["box"]; inset = 8
    a = page[y0 + inset:y1 - inset, x0 + inset:x1 - inset] < thresh
    n, lab, st, _ = cv2.connectedComponentsWithStats(a.astype(np.uint8))
    keep = np.zeros_like(a)
    for i in range(1, n):
        if st[i][4] >= min_area:
            keep |= lab == i
    return keep, (x0 + inset, y0 + inset)


def trace(ink, potrace):
    """ink -> potrace SVG path data and its transform (potrace's own: translate + scale with y up)"""
    import re
    with tempfile.TemporaryDirectory() as td:
        pbm = Path(td) / "g.pbm"; Image.fromarray((~ink).astype(np.uint8) * 255).convert("1").save(pbm)
        svg = Path(td) / "g.svg"
        subprocess.run([str(potrace), "-s", "-o", str(svg), "--flat", "-t", "4", "-a", "1.0", "-O", "0.4", str(pbm)], check=True, capture_output=True)
        t = svg.read_text()
    m = re.search(r'transform="translate\(([-\d.]+),([-\d.]+)\) scale\(([-\d.]+),([-\d.]+)\)"', t)
    d = " ".join(re.findall(r'<path d="([^"]+)"', t))
    return d, [float(v) for v in m.groups()] if m else [0, 0, 1, 1]


def build(chars_ink, out_path, family, designer, potrace):
    """chars_ink: [(char, ink, (ox, oy), baseline_y, xheight_y)] in page pixels -> the font file and its glyph metrics"""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.t2CharStringPen import T2CharStringPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.svgLib.path import parse_path
    names = {".notdef": None, "space": " "}; order = [".notdef", "space"]; cs = {}; metrics = {"space": (UPM * 3 // 10, 0)}; cmap = {32: "space"}
    pen0 = T2CharStringPen(600, None); pen0.moveTo((50, 0)); pen0.lineTo((550, 0)); pen0.lineTo((550, 700)); pen0.lineTo((50, 700)); pen0.closePath()
    cs[".notdef"] = pen0.getCharString(); metrics[".notdef"] = (600, 50)
    sp = T2CharStringPen(metrics["space"][0], None); cs["space"] = sp.getCharString()
    report = []
    for ch, ink, (ox, oy), base, xh in chars_ink:
        gname = f"uni{ord(ch):04X}"
        if not ink.any():
            report.append({"char": ch, "empty": True}); continue
        d, (tx, ty, sx, sy) = trace(ink, potrace)
        k = XH / float(base - xh)   # pixels -> font units: the box's x-height band is the font's x-height
        # potrace coords -> cell pixels (x' = tx + sx*x, y' = ty + sy*y), then page pixels, then font units with y up
        A = [sx * k, 0, 0, -sy * k, (ox + tx) * k, (base - oy - ty) * k]
        bp = BoundsPen(None); parse_path(d, TransformPen(bp, A)); x0, y0, x1, y1 = bp.bounds
        lsb = 50; A[4] -= x0 - lsb; adv = round(x1 - x0 + 2 * lsb)
        pen = T2CharStringPen(adv, None); parse_path(d, TransformPen(pen, A)); cs[gname] = pen.getCharString()
        metrics[gname] = (adv, lsb); order.append(gname); cmap[ord(ch)] = gname
        report.append({"char": ch, "advance": adv, "bottom": round(y0), "top": round(y1)})
    fb = FontBuilder(UPM, isTTF=False)
    fb.setupGlyphOrder(order); fb.setupCharacterMap(cmap)
    fb.setupCFF(family.replace(" ", ""), {"FullName": family}, cs, {})
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=900, descent=-250)
    fb.setupNameTable({"familyName": family, "styleName": "Regular", "designer": designer, "manufacturer": "Doodleberry handwriting (WP-29)",
                       "description": f"Made from {designer}'s handwriting samples"})
    fb.setupOS2(sTypoAscender=900, sTypoDescender=-250, usWinAscent=1000, usWinDescent=300, sxHeight=XH, sCapHeight=CAP)
    fb.setupPost(); fb.save(out_path)
    return report
