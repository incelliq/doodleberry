"""Open-source parts behind commands (WP-34; decisions in docs/oss-integration.md).

Three first parts, one from each of the parity map's first groups:

- **frame-by-frame (Pencil2D, GPL-2.0, driven):** `pencil2d_write` writes a drawn level (frames with their exposure
  numbers) as a Pencil2D project an artist can open and keep drawing in; `pencil2d_render` renders any Pencil2D
  project headless (its own command-line exporter, Qt offscreen) to PNG frames with transparency, so an artist's
  hand-drawn animation comes back into a film as a frame sequence with its holds.
- **painting and brushes (libmypaint, ISC, linked in-process through ctypes; MyPaint brush presets, CC0-1.0 and
  GPL-2+):** `paint` draws pressure strokes with any MyPaint brush onto a transparent surface (64-pixel tiles of
  15-bit premultiplied RGBA, read back and un-premultiplied).
- **vector editing (Inkscape, GPL-2.0-or-later, driven):** `boolean` unites, subtracts, intersects, excludes or
  divides SVG shapes with Inkscape's own path operations (`--actions`), headless.

Each tool is optional: `engine.doctor` reports it and `tools/setup.sh oss` installs it (apt).
"""
import ctypes as C
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import numpy as np

from . import ROOT

BRUSH_DIRS = [Path("/usr/share/mypaint-data/2.0/brushes"), Path("/usr/share/mypaint-data/1.0/brushes")]
TILE = 64


def _env():
    rt = Path(tempfile.gettempdir()) / "dbe-xdg-runtime"; rt.mkdir(mode=0o700, exist_ok=True)
    return {**os.environ, "QT_QPA_PLATFORM": "offscreen", "XDG_RUNTIME_DIR": str(rt)}


def available():
    lib = None
    try:
        lib = C.CDLL("libmypaint-1.5.so.1")
    except OSError:
        pass
    return {"pencil2d": shutil.which("pencil2d"), "inkscape": shutil.which("inkscape"), "libmypaint": bool(lib),
            "mypaint_brushes": next((str(d) for d in BRUSH_DIRS if d.is_dir()), None)}


# ---------------------------------------------------------------- MyPaint brushes (libmypaint, linked)
class _Req(C.Structure):
    _fields_ = [("tx", C.c_int), ("ty", C.c_int), ("readonly", C.c_int), ("buffer", C.POINTER(C.c_uint16)),
                ("context", C.c_void_p), ("thread_id", C.c_int), ("mipmap_level", C.c_int)]


class _Rect(C.Structure):
    _fields_ = [("x", C.c_int), ("y", C.c_int), ("width", C.c_int), ("height", C.c_int)]


_LIB = None


def _lib():
    global _LIB
    if _LIB is None:
        L = None
        import ctypes.util
        for nm in ("libmypaint-1.5.so.1", "libmypaint-1.6.so.1", "libmypaint.so.0", "libmypaint.so", ctypes.util.find_library("mypaint")):
            try:
                L = C.CDLL(nm) if nm else None
            except OSError:
                continue
            if L:
                break
        if not L:
            raise OSError("libmypaint: cannot open shared object file (install it: apt-get install libmypaint-1.5-1 mypaint-brushes, "
                          "or on Fedora dnf install libmypaint mypaint-brushes)")
        sig = {"mypaint_brush_new": ([], C.c_void_p), "mypaint_brush_unref": ([C.c_void_p], None),
               "mypaint_brush_from_string": ([C.c_void_p, C.c_char_p], C.c_int), "mypaint_brush_new_stroke": ([C.c_void_p], None),
               "mypaint_brush_stroke_to": ([C.c_void_p, C.c_void_p, C.c_float, C.c_float, C.c_float, C.c_float, C.c_float, C.c_double], C.c_int),
               "mypaint_brush_setting_from_cname": ([C.c_char_p], C.c_int), "mypaint_brush_set_base_value": ([C.c_void_p, C.c_int, C.c_float], None),
               "mypaint_fixed_tiled_surface_new": ([C.c_int, C.c_int], C.c_void_p), "mypaint_fixed_tiled_surface_interface": ([C.c_void_p], C.c_void_p),
               "mypaint_surface_begin_atomic": ([C.c_void_p], None), "mypaint_surface_end_atomic": ([C.c_void_p, C.POINTER(_Rect)], None),
               "mypaint_surface_unref": ([C.c_void_p], None),
               "mypaint_tile_request_init": ([C.POINTER(_Req), C.c_int, C.c_int, C.c_int, C.c_int], None),
               "mypaint_tiled_surface_tile_request_start": ([C.c_void_p, C.POINTER(_Req)], None),
               "mypaint_tiled_surface_tile_request_end": ([C.c_void_p, C.POINTER(_Req)], None)}
        for name, (args, res) in sig.items():
            f = getattr(L, name); f.argtypes = args; f.restype = res
        _LIB = L
    return _LIB


def brushes():
    """MyPaint brush presets installed: {"set/name": path}"""
    out = {}
    for d in BRUSH_DIRS:
        for f in sorted(d.glob("*/*.myb")):
            out.setdefault(f"{f.parent.name}/{f.stem}", str(f))
    return out


def _tiles(L, fs, W, H, fn):
    for ty in range((H + TILE - 1) // TILE):
        for tx in range((W + TILE - 1) // TILE):
            q = _Req(); L.mypaint_tile_request_init(C.byref(q), 0, tx, ty, 0)
            L.mypaint_tiled_surface_tile_request_start(fs, C.byref(q))
            fn(tx, ty, np.ctypeslib.as_array(q.buffer, shape=(TILE, TILE, 4)))
            L.mypaint_tiled_surface_tile_request_end(fs, C.byref(q))


def _hsv(colour):
    import colorsys
    c = colour.lstrip("#")
    return colorsys.rgb_to_hsv(*(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)))


def paint(brush, strokes, size, colour="#24160e", radius_scale=1.0):
    """strokes: [[[x, y, pressure, dt], ...], ...] in pixels -> RGBA uint8 array (H, W, 4), transparent background"""
    L = _lib(); W, H = size
    path = brushes().get(brush, brush)
    fs = L.mypaint_fixed_tiled_surface_new(W, H); surf = L.mypaint_fixed_tiled_surface_interface(fs)
    _tiles(L, fs, W, H, lambda tx, ty, a: a.fill(0))   # a transparent surface (the library starts it white)
    b = L.mypaint_brush_new()
    if not L.mypaint_brush_from_string(b, Path(path).read_text().encode()):
        raise ValueError(f"not a MyPaint brush: {brush}")
    h, s_, v = _hsv(colour)
    for k, val in (("color_h", h), ("color_s", s_), ("color_v", v)):
        L.mypaint_brush_set_base_value(b, L.mypaint_brush_setting_from_cname(k.encode()), val)
    if radius_scale != 1.0:
        sid = L.mypaint_brush_setting_from_cname(b"radius_logarithmic")
        import math
        base = json.loads(Path(path).read_text()).get("settings", {}).get("radius_logarithmic", {}).get("base_value", 1.0)
        L.mypaint_brush_set_base_value(b, sid, base + math.log(radius_scale))
    L.mypaint_surface_begin_atomic(surf)
    for st in strokes:
        L.mypaint_brush_new_stroke(b)
        x0, y0 = st[0][0], st[0][1]
        L.mypaint_brush_stroke_to(b, surf, x0, y0, 0.0, 0.0, 0.0, 0.1)   # pen down without ink
        for p in st:
            L.mypaint_brush_stroke_to(b, surf, float(p[0]), float(p[1]), float(p[2] if len(p) > 2 else 0.6), 0.0, 0.0, float(p[3] if len(p) > 3 else 0.012))
        L.mypaint_brush_stroke_to(b, surf, float(st[-1][0]), float(st[-1][1]), 0.0, 0.0, 0.0, 0.05)
    r = _Rect(); L.mypaint_surface_end_atomic(surf, C.byref(r))
    out = np.zeros((H, W, 4), np.float32)

    def grab(tx, ty, a):
        hh, ww = min(TILE, H - ty * TILE), min(TILE, W - tx * TILE)
        out[ty * TILE:ty * TILE + hh, tx * TILE:tx * TILE + ww] = a[:hh, :ww].astype(np.float32) / (1 << 15)
    _tiles(L, fs, W, H, grab)
    L.mypaint_brush_unref(b); L.mypaint_surface_unref(surf)
    al = out[..., 3:4]; rgb = np.where(al > 1e-6, out[..., :3] / np.maximum(al, 1e-6), 0)
    return (np.concatenate([rgb, al], -1).clip(0, 1) * 255).round().astype(np.uint8)


# ---------------------------------------------------------------- Pencil2D (driven)
def pencil2d_write(frames, out, size=(1080, 1920), fps=24):
    """frames: [{"frame": n, "png": path}] (a drawing held until the next one, as on an exposure sheet) -> .pclx"""
    W, H = size
    imgs = []
    for f in sorted(frames, key=lambda x: x["frame"]):
        from PIL import Image
        im = Image.open(f["png"]); w, h = im.size
        imgs.append((int(f["frame"]), f["png"], -W // 2 + (W - w) // 2, -H // 2 + (H - h) // 2))
    xml = ['<!DOCTYPE PencilDocument>', '<document>', ' <projectdata>', '  <version>0.6.6</version>',
           f'  <camera width="{W}" height="{H}"/>', f'  <fps>{fps}</fps>', '  <currentFrame>1</currentFrame>', ' </projectdata>', ' <object>',
           f'  <layer id="1" name="Camera Layer" visibility="1" type="5" width="{W}" height="{H}">',
           '   <camera frame="1" m11="1" m12="0" m21="0" m22="1" dx="0" dy="0"/>', '  </layer>',
           '  <layer id="2" name="Drawing" visibility="1" type="1">']
    for n, _, x, y in imgs:
        xml.append(f'   <image frame="{n}" src="002.{n:03d}.png" topLeftX="{x}" topLeftY="{y}" opacity="1"/>')
    xml += ['  </layer>', ' </object>', '</document>', '']
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("main.xml", "\n".join(xml))
        for n, png, _, _ in imgs:
            z.write(png, f"data/002.{n:03d}.png")
    return {"file": str(out), "drawings": len(imgs), "frames": imgs[-1][0] if imgs else 0}


def pencil2d_render(pclx, out_dir, start=1, end="last", size=None, transparent=True):
    """render a Pencil2D project headless with Pencil2D's own exporter -> sorted frame paths"""
    exe = shutil.which("pencil2d")
    if not exe:
        raise FileNotFoundError("pencil2d is not installed (bash tools/setup.sh oss)")
    out_dir = Path(out_dir); shutil.rmtree(out_dir, ignore_errors=True); out_dir.mkdir(parents=True)
    cmd = [exe, str(pclx), "-o", str(out_dir / "frame.png"), "--start", str(start), "--end", str(end)]
    if size:
        cmd += ["--width", str(size[0]), "--height", str(size[1])]
    if transparent:
        cmd.append("--transparency")
    r = subprocess.run(cmd, capture_output=True, text=True, env=_env(), timeout=1800)
    frames = sorted(out_dir.glob("frame*.png"))
    if r.returncode or not frames:
        raise RuntimeError(f"pencil2d failed: {(r.stderr or r.stdout)[-400:]}")
    return frames


# ---------------------------------------------------------------- Inkscape path operations (driven)
OPS = {"union": "path-union", "difference": "path-difference", "intersection": "path-intersection",
       "exclusion": "path-exclusion", "division": "path-division"}


def boolean(shapes, op, size=(1080, 1920)):
    """shapes: SVG elements (paths, circles, rects...) in drawing order; for difference the top one is cut from the
    one below -> the resulting path data (one or more d strings)"""
    exe = shutil.which("inkscape")
    if not exe:
        raise FileNotFoundError("inkscape is not installed (bash tools/setup.sh oss)")
    if op not in OPS:
        raise ValueError(f"op is one of {sorted(OPS)}")
    with tempfile.TemporaryDirectory() as td:
        src, dst = Path(td) / "in.svg", Path(td) / "out.svg"
        src.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{size[0]}" height="{size[1]}" viewBox="0 0 {size[0]} {size[1]}">'
                       + "".join(shapes) + "</svg>")
        r = subprocess.run([exe, str(src), f"--actions=select-all:all;object-to-path;{OPS[op]};export-filename:{dst};export-plain-svg;export-do"],
                           capture_output=True, text=True, env=_env(), timeout=300)
        if not dst.exists():
            raise RuntimeError(f"inkscape failed: {(r.stderr or r.stdout)[-400:]}")
        return re.findall(r'<path[^>]*?\sd="([^"]+)"', dst.read_text())


def self_test(tmp):
    """a brush stroke paints where it goes and nowhere else; a drawn level round-trips through Pencil2D with its
    holds; Inkscape's union of two overlapping shapes is one path and their intersection is smaller than either"""
    from PIL import Image
    fails, got = [], {}
    av = available(); got["available"] = {k: bool(v) for k, v in av.items()}
    tmp = Path(tmp); shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir(parents=True)
    if av["libmypaint"] and av["mypaint_brushes"]:
        st = [[[40 + i * 4, 120, 0.2 + 0.6 * (i / 60), 0.012] for i in range(61)]]
        a = paint("deevad/2B_pencil", st, (400, 240), "#5a3fc0")
        ink = a[..., 3] > 20
        ys, xs = np.nonzero(ink)
        got["brush"] = {"inked_px": int(ink.sum()), "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None,
                        "corner_alpha": int(a[0, 0, 3])}
        if not len(xs) or a[0, 0, 3] != 0 or not (30 <= xs.min() <= 80 and 260 <= xs.max() <= 300 and 100 <= ys.min() <= 120 <= ys.max() <= 140):
            fails.append(f"brush stroke: {got['brush']}")
        mean = a[ink][:, :3].mean(0)
        if not (mean[2] > mean[1] and mean[2] > 100):   # #5a3fc0 is blue-violet
            fails.append(f"brush colour: {mean}")
    else:
        got["brush"] = "skipped (libmypaint or brushes missing)"
    if av["pencil2d"]:
        pngs = []
        for i, x in ((1, 40), (3, 140)):
            im = Image.new("RGBA", (200, 120), (0, 0, 0, 0)); im.paste((36, 22, 14, 255), (x, 30, x + 40, 90)); p = tmp / f"d{i}.png"; im.save(p); pngs.append({"frame": i, "png": str(p)})
        pencil2d_write(pngs, tmp / "level.pclx", size=(200, 120), fps=12)
        fr = pencil2d_render(tmp / "level.pclx", tmp / "p2d", end=4)
        boxes = [Image.open(f).getchannel("A").getbbox() for f in fr]
        got["pencil2d"] = {"frames": len(fr), "boxes": boxes}
        if len(fr) != 4 or boxes[0] != boxes[1] or boxes[2] != boxes[3] or boxes[0] == boxes[2] or not boxes[0] or boxes[0][0] != 40:
            fails.append(f"pencil2d round trip: {got['pencil2d']}")
    else:
        got["pencil2d"] = "skipped (not installed)"
    if av["inkscape"]:
        sh = ['<rect x="40" y="40" width="140" height="120" fill="#b8325f"/>', '<circle cx="190" cy="100" r="70" fill="#5a3fc0"/>']
        u = boolean(sh, "union", (300, 200)); i = boolean(sh, "intersection", (300, 200))
        got["inkscape"] = {"union_paths": len(u), "intersection_paths": len(i)}
        if len(u) != 1 or len(i) != 1:
            fails.append(f"inkscape booleans: {got['inkscape']}")
    else:
        got["inkscape"] = "skipped (not installed)"
    shutil.rmtree(tmp, ignore_errors=True)
    return fails, got
