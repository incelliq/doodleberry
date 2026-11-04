"""Raster parts to vector shapes (WP-14, WP-33): a puppet's image strokes (scanned or photographed doodles, painted
parts) traced into filled paths, so renderers that cannot draw images (Grease Pencil) draw the character too, at any
size.

Each image is read in its own pixels. Flat art (line art and cartoon fills: its opaque pixels fit within a few
colours, k-means k <= 6, mean error under 14 levels) is traced one colour at a time with potrace (the vendored 1.16),
each colour's mask over the ones below, so the drawing keeps its own colours and its line stays one line. Painted art
(more colours than that) is traced by vtracer (the vendored 0.6.5) in colour mode, stacked, with colours merged to
5 bits a channel. Every colour becomes a palette slot (`vec0`, `vec1`, ...), so palette variants (WP-16) recolour
it. Coordinates go from image pixels to the artboard by the stroke's x, y, w, h.
"""
import base64
import io
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
POTRACE = ROOT / "out" / "vendor-build" / "potrace" / "bin" / "potrace"
VTRACER = ROOT / "out" / "vendor-build" / "vtracer" / "release" / "vtracer"


def _img(st):
    src = st["image"]
    data = base64.b64decode(src.split(",", 1)[1]) if src.startswith("data:") else (ROOT / src).read_bytes()
    return np.asarray(Image.open(io.BytesIO(data)).convert("RGBA"))


def _kmeans(px, k, iters=12, seed=0):
    rng = np.random.default_rng(seed)
    c = px[rng.choice(len(px), size=min(k, len(px)), replace=False)].astype(float)
    for _ in range(iters):
        lab = np.argmin(((px[:, None, :] - c[None]) ** 2).sum(-1), 1)
        for j in range(len(c)):
            if (lab == j).any():
                c[j] = px[lab == j].mean(0)
    lab = np.argmin(((px[:, None, :] - c[None]) ** 2).sum(-1), 1)
    err = float(np.sqrt(((px - c[lab]) ** 2).sum(-1)).mean())
    return c, lab, err


def _xform(d, a):
    """SVG path data through an affine [a, b, c, d, e, f] (x' = a x + c y + e, y' = b x + d y + f), as absolute data"""
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.svgLib.path import parse_path
    pen = SVGPathPen(None, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
    parse_path(d, TransformPen(pen, a))
    return pen.getCommands()


def _potrace(mask):
    with tempfile.TemporaryDirectory() as td:
        pbm = Path(td) / "m.pbm"; Image.fromarray((~mask).astype(np.uint8) * 255).convert("1").save(pbm)
        svg = Path(td) / "m.svg"
        subprocess.run([str(POTRACE), "-s", "-o", str(svg), "--flat", "-t", "3", "-a", "1.0", "-O", "0.3", str(pbm)], check=True, capture_output=True)
        t = svg.read_text()
    m = re.search(r'transform="translate\(([-\d.]+),([-\d.]+)\) scale\(([-\d.]+),([-\d.]+)\)"', t)
    tx, ty, sx, sy = [float(v) for v in m.groups()] if m else (0, 0, 1, 1)
    return " ".join(re.findall(r'<path d="([^"]+)"', t)), (sx, 0, 0, sy, tx, ty)


def _vtracer(rgba):
    with tempfile.TemporaryDirectory() as td:
        png = Path(td) / "i.png"; Image.fromarray(rgba).save(png); svg = Path(td) / "i.svg"
        subprocess.run([str(VTRACER), "-i", str(png), "-o", str(svg), "--colormode", "color", "--mode", "spline", "-p", "5", "-f", "6", "-g", "24",
                        "--hierarchical", "stacked", "--path_precision", "2"], check=True, capture_output=True)
        t = svg.read_text()
    out = []
    for m in re.finditer(r'<path d="([^"]+)" fill="(#[0-9A-Fa-f]{6})" transform="translate\(([-\d.]+),([-\d.]+)\)"', t):
        out.append((m.group(1), m.group(2).lower(), (float(m.group(3)), float(m.group(4)))))
    return out


def trace_image(st, max_flat=6, flat_err=14.0):
    """one image stroke -> ([(path d in artboard units, '#rrggbb')], how)"""
    a = _img(st); H, W = a.shape[:2]
    sx, sy = st["w"] / W, st["h"] / H; ox, oy = st["x"], st["y"]
    opaque = a[..., 3] >= 128
    if not opaque.any():
        return [], "empty"
    px = a[..., :3][opaque].astype(float)
    sub = px[np.random.default_rng(0).choice(len(px), size=min(len(px), 20000), replace=False)]
    best = None
    for k in range(1, max_flat + 1):
        c, _, err = _kmeans(sub, k)
        if err < flat_err:
            best = c; break
    shapes = []
    if best is not None:
        lab = np.full(opaque.shape, -1); lab[opaque] = np.argmin(((px[:, None, :] - best[None]) ** 2).sum(-1), 1)
        order = sorted(range(len(best)), key=lambda j: -(lab == j).sum())   # the largest colour first, the rest over it
        for j in order:
            m = lab == j
            if m.sum() < 4:
                continue
            d, (a0, b0, c0, d0, e0, f0) = _potrace(m)
            # potrace units -> image pixels (its own transform) -> artboard
            A = (a0 * sx, 0, 0, d0 * sy, ox + e0 * sx, oy + f0 * sy)
            shapes.append((_xform(d, A), "#%02x%02x%02x" % tuple(int(round(v)) for v in best[j])))
        return shapes, f"flat: {len(best)} colour(s), potrace"
    for d, col, (tx, ty) in _vtracer(a):
        shapes.append((_xform(d, (sx, 0, 0, sy, ox + tx * sx, oy + ty * sy)), col))
    return shapes, f"painted: {len(shapes)} shapes, vtracer"


def vectorize(puppet):
    """-> (the puppet with every image stroke traced, report)"""
    import copy
    p = copy.deepcopy(puppet); pal = p.setdefault("palette", {}); slot = {}
    report = []
    def name(col):
        if col not in slot:
            slot[col] = f"vec{len(slot)}"; pal[slot[col]] = col
        return slot[col]
    def conv(strokes, where):
        out = []
        for st in strokes:
            if "image" not in st:
                out.append(st); continue
            shapes, how = trace_image(st)
            report.append({"where": where, "how": how, "shapes": len(shapes)})
            out += [{"d": d, "fill": name(col), **({"opacity": st["opacity"]} if st.get("opacity") is not None else {})} for d, col in shapes]
        return out
    for pid, part in p["parts"].items():
        part["strokes"] = conv(part["strokes"], pid)
    for sid, sw in (p.get("swaps") or {}).items():
        for k, strokes in (sw.get("shapes") or {}).items():
            sw["shapes"][k] = conv(strokes, f"{sid}.{k}")
    for vname, v in (p.get("views") or {}).items():
        for pid, part in (v.get("parts") or {}).items():
            if "strokes" in part:
                part["strokes"] = conv(part["strokes"], f"views.{vname}.{pid}")
    p.setdefault("meta", {})["vectorized"] = {"tools": ["potrace 1.16 (GPL-2.0-or-later)", "vtracer 0.6.5 (MIT OR Apache-2.0)"], "parts": report}
    return p, report
