"""Drawn levels (WP-35, puppet format v0.8): hand-drawn animation as a sequence of drawings with exposures.

A level is a puppet of template `level`: one root part and a swap set `level` whose shapes are the drawings (raster
strokes from scans, brush paintings or Pencil2D, or vector strokes) and whose `xsheet` is the exposure sheet:

    "swaps": {"level": {"anchor": "root", "z": 10, "shapes": {"d01": [stroke...], "d02": [...]},
                        "xsheet": {"fps": 24, "cells": ["d01", "d01", "d02", "d02", ...], "loop": true}}}

`cells` holds one drawing per frame of the level's own rate, so a run of the same drawing is a hold: on ones, twos or
threes, or any timing an animator writes. The xsheet is compiled into the puppet's own clip `play` (v0.7 clips: swap
keys that hold until the next key), so every renderer, the bake, `dbe/geom.py` and the exporters play a level the way
they play any swap; a shot starts it with `"timeline": {"clips": [{"clip": "play", "start": 0}]}` and can move,
scale and flip it like any cast member. Raster drawings render in the SVG renderer; vector drawings everywhere.
"""
import base64
import io
import json
import re
from pathlib import Path

import numpy as np

from . import ROOT

TIMINGS = {"ones": 1, "twos": 2, "threes": 3, "fours": 4}


def cells_for(drawings, timing="twos", hold_last=0):
    """drawing names and a timing ("ones"/"twos"/"threes", or a number of frames per drawing, or a list of holds,
    one per drawing) -> the exposure cells"""
    if isinstance(timing, list):
        if len(timing) != len(drawings):
            raise ValueError("one hold per drawing")
        holds = [int(h) for h in timing]
    else:
        n = TIMINGS.get(timing, timing)
        holds = [int(n)] * len(drawings)
    cells = [d for d, h in zip(drawings, holds) for _ in range(max(1, h))]
    return cells + [drawings[-1]] * hold_last


def compile_clip(cells, fps, loop=True, sid="level"):
    """exposure cells -> a v0.7 clip whose swap keys hold each drawing for its run of frames"""
    keys, prev = [], None
    for i, c in enumerate(cells):
        if c != prev:
            keys.append([round(i / fps, 5), c]); prev = c
    return {"duration": round(len(cells) / fps, 5), "loop": bool(loop), "fadeIn": 0, "fadeOut": 0, "tracks": {}, "swaps": {sid: keys}}


def runs(cells):
    """the exposure sheet as runs: [[drawing, frames], ...]"""
    out = []
    for c in cells:
        if out and out[-1][0] == c:
            out[-1][1] += 1
        else:
            out.append([c, 1])
    return out


def raster_stroke(rgba, ox=0, oy=0):
    """an RGBA array -> a raster stroke trimmed to its ink (artboard units = pixels, origin ox, oy)"""
    from PIL import Image
    a = np.asarray(rgba)
    ys, xs = np.nonzero(a[..., 3] > 0)
    if not len(xs):
        return None
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    buf = io.BytesIO(); Image.fromarray(a[y0:y1, x0:x1], "RGBA").save(buf, "PNG", optimize=True)
    return {"image": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(), "x": int(x0 + ox), "y": int(y0 + oy),
            "w": int(x1 - x0), "h": int(y1 - y0)}


def make(name, drawings, size, timing="twos", fps=24, loop=True, author="", license_="LicenseRef-owner", ground=None):
    """drawings: [{"name", "rgba" | "png" | "strokes"}] in order; size: the artboard [w, h] (the drawing's own pixels);
    -> a level puppet (dict)"""
    from PIL import Image
    W, H = size
    shapes = {}
    for i, d in enumerate(drawings, 1):
        nm = d.get("name") or f"d{i:02d}"
        if d.get("strokes") is not None:
            shapes[nm] = d["strokes"]; continue
        a = np.asarray(Image.open(d["png"]).convert("RGBA")) if d.get("png") else np.asarray(d["rgba"])
        if a.shape[1] != W or a.shape[0] != H:
            raise ValueError(f"drawing {nm} is {a.shape[1]}x{a.shape[0]}, the level is {W}x{H}")
        st = raster_stroke(a)
        shapes[nm] = [st] if st else []
    names = list(shapes)
    cells = cells_for(names, timing)
    if ground is None:   # where the drawings stand: the lowest ink across every drawing
        lows = [st["y"] + st["h"] for sh in shapes.values() for st in sh if "h" in st]
        ground = max(lows) if lows else H
    return {"format": "doodleberry.puppet", "version": "0.8", "name": name, "template": "level", "artboard": [W, H],
            "ground": ground, "palette": {},
            "parts": {"root": {"parent": None, "pivot": [W / 2, H], "z": 0, "strokes": []}},
            "swaps": {"level": {"anchor": "root", "z": 10, "shapes": shapes, "xsheet": {"fps": fps, "cells": cells, "loop": bool(loop)}}},
            "clips": {"play": compile_clip(cells, fps, loop)},
            "meta": {"author": author, "license": license_, "kind": "drawn level (WP-35)"}}


def set_xsheet(p, timing=None, cells=None, fps=None, loop=None, sid="level"):
    """retime a level: new holds (timing) or explicit cells; recompiles the clip"""
    sw = p["swaps"][sid]; x = dict(sw.get("xsheet") or {})
    names = list(sw["shapes"])
    if cells is not None:
        bad = [c for c in cells if c not in sw["shapes"]]
        if bad:
            raise ValueError(f"cells name drawings that do not exist: {sorted(set(bad))[:5]}")
        x["cells"] = list(cells)
    elif timing is not None:
        x["cells"] = cells_for(names, timing)
    if fps:
        x["fps"] = fps
    if loop is not None:
        x["loop"] = bool(loop)
    sw["xsheet"] = x
    p.setdefault("clips", {})["play" if sid == "level" else f"play_{sid}"] = compile_clip(x["cells"], x["fps"], x.get("loop", True), sid)
    return p


def from_frames(frames):
    """rendered frames (paths, in order, one per frame) -> distinct drawings and the cells that expose them (a held
    drawing is one drawing on several cells)"""
    from PIL import Image
    drawings, cells, last = [], [], None
    for f in frames:
        a = np.asarray(Image.open(f).convert("RGBA"))
        if last is not None and a.shape == last.shape and np.array_equal(a, last):
            cells.append(cells[-1]); continue
        drawings.append({"name": f"d{len(drawings) + 1:02d}", "rgba": a}); cells.append(drawings[-1]["name"]); last = a
    return drawings, cells


# ---------------------------------------------------------------- cleanup, capture, registration (WP-35 part 3)
def stroke_rgba(st, size):
    """a raster stroke back into a full-size RGBA array"""
    from PIL import Image
    W, H = size; out = np.zeros((H, W, 4), np.uint8)
    im = Image.open(io.BytesIO(base64.b64decode(st["image"].split(",", 1)[1]))).convert("RGBA").resize((int(st["w"]), int(st["h"])))
    a = np.asarray(im); x, y = int(st["x"]), int(st["y"])
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + a.shape[1]), min(H, y + a.shape[0])
    if x1 > x0 and y1 > y0:
        out[y0:y1, x0:x1] = a[y0 - y:y1 - y, x0 - x:x1 - x]
    return out


def drawing_rgba(p, name, sid="level", role=None):
    """a drawing composited to a full-size RGBA array (only strokes of `role` when given: line or paint)"""
    from PIL import Image
    W, H = p["artboard"]; base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for st in p["swaps"][sid]["shapes"].get(name, []):
        if "image" in st and (role is None or st.get("role", "line") == role):
            base.alpha_composite(Image.fromarray(stroke_rgba(st, (W, H)), "RGBA"))
    return np.asarray(base)


def clean_rgba(a, keep=0.45, min_speck=12, ink=None):
    """rough lines -> clean lines: faint construction strokes (alpha under `keep`) go, specks go, the rest is inked
    at full strength with soft edges kept; ink: a colour for every line, or None to keep each line's own"""
    from scipy import ndimage
    al = a[..., 3].astype(np.float32) / 255
    mask = al >= keep
    lab, n = ndimage.label(mask, np.ones((3, 3)))
    if n:
        sizes = ndimage.sum(mask, lab, range(1, n + 1))
        mask = np.isin(lab, [i + 1 for i, s_ in enumerate(sizes) if s_ >= min_speck])
    soft = np.clip((al - keep * 0.6) / (1 - keep * 0.6), 0, 1)
    soft = np.where(ndimage.binary_dilation(mask, iterations=1), np.maximum(soft, mask * 1.0), 0)
    out = a.copy()
    if ink:
        c = ink.lstrip("#"); out[..., :3] = [int(c[i:i + 2], 16) for i in (0, 2, 4)]
    out[..., 3] = (soft * 255).round().astype(np.uint8)
    return out


def photo_to_ink(photo_rgb, size, ink="#24160e", threshold=(225, 75), min_speck=25, margin=0.06):
    """a photo or scan of a drawing on paper -> ink on a transparent level-sized canvas, fitted inside the frame
    (lighting divided out, paper removed, specks dropped; the method of dbe/ink.py)"""
    from PIL import Image, ImageFilter
    from scipy import ndimage
    im = Image.fromarray(photo_rgb).convert("L")
    a = np.asarray(im).astype(np.float32)
    bg = np.asarray(im.filter(ImageFilter.GaussianBlur(25))).astype(np.float32)
    norm = np.clip(a / np.maximum(bg, 1) * 255, 0, 255)
    alpha = np.clip((threshold[0] - norm) / threshold[1], 0, 1)
    mask = alpha > 0.35
    lab, n = ndimage.label(mask, np.ones((3, 3)))
    if n:
        sizes = ndimage.sum(mask, lab, range(1, n + 1))
        alpha = alpha * np.isin(lab, [i + 1 for i, s_ in enumerate(sizes) if s_ >= min_speck])
    W, H = size; h, w = alpha.shape
    k = min(W * (1 - 2 * margin) / w, H * (1 - 2 * margin) / h)   # the paper fitted into the frame, as a camera stand would
    al = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).resize((max(1, int(w * k)), max(1, int(h * k))), Image.LANCZOS))
    out = np.zeros((H, W, 4), np.uint8); c = ink.lstrip("#")
    out[..., :3] = [int(c[i:i + 2], 16) for i in (0, 2, 4)]
    y0, x0 = (H - al.shape[0]) // 2, (W - al.shape[1]) // 2
    out[y0:y0 + al.shape[0], x0:x0 + al.shape[1], 3] = al
    return out


def register(ref, mov, max_shift=None):
    """the translation that lines a drawing up with the one before it (phase correlation of their ink), the digital
    peg bar for pencil tests -> (dx, dy) to apply to mov"""
    A = ref[..., 3].astype(np.float32) / 255; B = mov[..., 3].astype(np.float32) / 255
    if A.sum() < 1 or B.sum() < 1:
        return 0, 0
    FA, FB = np.fft.fft2(A), np.fft.fft2(B)
    R = FA * np.conj(FB); R /= np.abs(R) + 1e-9
    c = np.fft.ifft2(R).real
    dy, dx = np.unravel_index(np.argmax(c), c.shape)
    H, W = A.shape
    dy = dy - H if dy > H // 2 else dy; dx = dx - W if dx > W // 2 else dx
    if max_shift and (abs(dx) > max_shift or abs(dy) > max_shift):
        return 0, 0
    return int(dx), int(dy)


def shift(a, dx, dy):
    out = np.zeros_like(a); H, W = a.shape[:2]
    ys, yd = (slice(0, H - dy), slice(dy, H)) if dy >= 0 else (slice(-dy, H), slice(0, H + dy))
    xs, xd = (slice(0, W - dx), slice(dx, W)) if dx >= 0 else (slice(-dx, W), slice(0, W + dx))
    out[yd, xd] = a[ys, xs]
    return out


# ---------------------------------------------------------------- colour styles across every drawing
def regions(line_rgba, gap=2):
    """the closed areas of a line drawing: labels of non-ink areas (4-connected), the outside (touching the border)
    excluded; small gaps in the line (up to `gap` px) are closed for the purpose of finding areas"""
    from scipy import ndimage
    ink = line_rgba[..., 3] > 96
    closed = ndimage.binary_closing(ink, iterations=gap) | ink if gap else ink
    lab, n = ndimage.label(~closed)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    for b in border:
        lab[lab == b] = 0
    return lab


def paint_layer(line_rgba, seeds, styles, gap=2):
    """fills for the seeded areas of a drawing, grown under the line so no paper shows between paint and ink"""
    from scipy import ndimage
    lab = regions(line_rgba, gap); H, W = lab.shape
    out = np.zeros((H, W, 4), np.uint8)
    ink = line_rgba[..., 3] > 32
    for x, y, style in seeds:
        x, y = int(round(x)), int(round(y))
        if not (0 <= x < W and 0 <= y < H) or lab[y, x] == 0 or style not in styles:
            continue
        m = lab == lab[y, x]
        m = m | (ndimage.binary_dilation(m, iterations=gap + 2) & ink)
        c = styles[style].lstrip("#"); out[m] = [int(c[i:i + 2], 16) for i in (0, 2, 4)] + [255]
    return out


def carry_seeds(prev_line, prev_seeds, line, gap=2):
    """the seeds of a painted drawing carried to the next drawing: each painted area goes to the area of the new
    drawing it overlaps most (areas of a similar size; the nearest one when nothing overlaps)"""
    A, B = regions(prev_line, gap), regions(line, gap)
    out = []
    ids_b = [i for i in np.unique(B) if i]
    if not ids_b:
        return out
    cents = {i: np.argwhere(B == i).mean(0) for i in ids_b}; areas = {i: int((B == i).sum()) for i in ids_b}
    used = set()
    for x, y, style in prev_seeds:
        x, y = int(round(x)), int(round(y))
        if not (0 <= y < A.shape[0] and 0 <= x < A.shape[1]) or A[y, x] == 0:
            continue
        ma = A == A[y, x]; area = int(ma.sum())
        ov = {i: int((ma & (B == i)).sum()) for i in ids_b}
        cand = [i for i in ids_b if 0.4 <= areas[i] / max(1, area) <= 2.5 and i not in used]
        best = max(cand, key=lambda i: ov[i], default=None) if cand else None
        if best is None or ov[best] == 0:
            ca = np.argwhere(ma).mean(0)
            best = min(cand, key=lambda i: np.hypot(*(cents[i] - ca)), default=None)
        if best is None:
            continue
        used.add(best); cy, cx = cents[best]
        pts = np.argwhere(B == best); j = int(np.argmin(((pts - [cy, cx]) ** 2).sum(1)))   # a point inside, nearest the centre
        out.append([int(pts[j][1]), int(pts[j][0]), style])
    return out


def recolour(p, sid="level"):
    """rebuild every drawing's paint from the level's styles and seeds (lines untouched)"""
    sw = p["swaps"][sid]; pt = sw.get("paint") or {}
    styles, seeds = pt.get("styles", {}), pt.get("seeds", {})
    for name, shape in sw["shapes"].items():
        lines = [st for st in shape if st.get("role", "line") != "paint"]
        if seeds.get(name):
            line = drawing_rgba(p, name, sid, "line")
            fill = raster_stroke(paint_layer(line, seeds[name], styles))
            if fill:
                fill["role"] = "paint"; lines = [fill] + lines
        sw["shapes"][name] = lines
    return p


def onion(p, frame, before=2, after=1, sid="level"):
    """the drawings around a frame for onion skinning: [(drawing, offset in drawings, opacity)]"""
    cells = p["swaps"][sid]["xsheet"]["cells"]; rs = runs(cells)
    i, acc = 0, 0
    for k, (d, n) in enumerate(rs):
        if acc + n > frame:
            i = k; break
        acc += n
    out = []
    for off in range(-before, after + 1):
        j = i + off
        if 0 <= j < len(rs):
            out.append((rs[j][0], off, 1.0 if off == 0 else round(0.5 / abs(off), 2)))
    return out


def self_test(tmp):
    """timings expose drawings on ones, twos and threes; the compiled clip holds each drawing for its run; a Pencil2D
    render comes back as drawings plus holds; a level renders its drawings at the right frames in the SVG renderer
    (through the same loader every film uses)"""
    import shutil
    import subprocess
    from PIL import Image, ImageDraw
    fails, got = [], {}
    tmp = Path(tmp); shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir(parents=True)
    c2 = cells_for(["a", "b", "c"], "twos"); c3 = cells_for(["a", "b"], "threes"); cx = cells_for(["a", "b", "c"], [1, 3, 2])
    got["cells"] = {"twos": c2, "threes": c3, "custom": cx}
    if c2 != list("aabbcc") or c3 != list("aaabbb") or cx != list("abbbcc"):
        fails.append(f"timings: {got['cells']}")
    clip = compile_clip(c2, 12)
    if clip["swaps"]["level"] != [[0.0, "a"], [round(2 / 12, 5), "b"], [round(4 / 12, 5), "c"]] or abs(clip["duration"] - 0.5) > 1e-6:
        fails.append(f"clip: {clip}")
    # three drawings: a dot that moves right, on twos at 12 fps
    frames = []
    for i in range(3):
        im = Image.new("RGBA", (120, 80), (0, 0, 0, 0)); ImageDraw.Draw(im).ellipse([10 + i * 40, 30, 30 + i * 40, 50], fill=(36, 22, 14, 255))
        frames.append({"name": f"d{i + 1:02d}", "rgba": np.asarray(im)})
    lv = make("dot", frames, (120, 80), "twos", fps=12)
    js = json.dumps(lv)
    from . import commands as C
    errs = C._puppet_errors(lv) if hasattr(C, "_puppet_errors") else []
    if errs:
        fails.append(f"schema: {errs[:3]}")
    (tmp / "dot.puppet.json").write_text(js)
    probe = tmp / "probe.mjs"
    probe.write_text("""
import { createRequire } from 'module'; import fs from 'fs';
const require = createRequire(import.meta.url); const vm = require('vm');
const ctx = { window: {}, console }; ctx.globalThis = ctx; vm.createContext(ctx);
for (const f of process.argv.slice(3)) vm.runInContext(fs.readFileSync(f, 'utf8'), ctx);
const P = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const A = ctx.window.Acting || ctx.Acting, Pu = ctx.window.Puppet || ctx.Puppet;
const out = [];
for (const t of [0, 0.1, 0.2, 0.3, 0.45, 0.55]) {
  const pose = A.evaluate(P, { clips: [{ clip: 'play', start: 0 }] }, t, {});
  const svg = Pu.render(P, 0, 0, pose);
  const m = /<image[^>]*x="([-\\d.]+)"/.exec(svg);
  out.push([t, pose.level, m ? +m[1] : null]);
}
console.log(JSON.stringify(out));
""")
    r = subprocess.run(["node", str(probe), str(tmp / "dot.puppet.json"), str(ROOT / "puppet" / "loader" / "puppet.js"), str(ROOT / "puppet" / "loader" / "acting.js")],
                       capture_output=True, text=True, timeout=120)
    try:
        seq = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        seq = None; fails.append(f"loader probe: {(r.stderr or r.stdout)[-300:]}")
    got["loader"] = seq
    if seq:
        want = ["d01", "d01", "d02", "d02", "d03", "d01"]   # 12 fps on twos: 0-1/6 d01, 1/6-1/3 d02, 1/3-1/2 d03, then it loops
        if [s[1] for s in seq] != want:
            fails.append(f"drawings over time: {[s[1] for s in seq]} (want {want})")
        xs = [s[2] for s in seq]
        if not (None not in xs and xs[0] == xs[1] and xs[2] == xs[3] and xs[0] < xs[2] < xs[4]):
            fails.append(f"drawings not placed where drawn: {xs}")
    from . import oss
    if oss.available()["pencil2d"]:
        pngs = []
        for i, x in ((1, 10), (4, 60)):
            im = Image.new("RGBA", (120, 80), (0, 0, 0, 0)); im.paste((36, 22, 14, 255), (x, 20, x + 30, 60)); pth = tmp / f"p{i}.png"; im.save(pth); pngs.append({"frame": i, "png": str(pth)})
        oss.pencil2d_write(pngs, tmp / "l.pclx", (120, 80), 12)
        fr = oss.pencil2d_render(tmp / "l.pclx", tmp / "p2d", end=6)
        ds, cells = from_frames(fr)
        got["pencil2d"] = {"drawings": len(ds), "cells": cells}
        if len(ds) != 2 or cells != ["d01", "d01", "d01", "d02", "d02", "d02"]:
            fails.append(f"pencil2d import: {got['pencil2d']}")
    else:
        got["pencil2d"] = "skipped"
    shutil.rmtree(tmp, ignore_errors=True)
    return fails, got


def page_check(tmp, port=8794):
    """the Studio drawing page, driven like an animator would: three pen drawings with the onion skin on, a MyPaint
    brush stroke, the sheet set on twos, played back (tools/draw_check.mjs against a local server)"""
    import shutil
    import socket
    import subprocess
    import sys
    import time
    fails, got = [], {}
    tmp = Path(tmp); tmp.mkdir(parents=True, exist_ok=True)
    name = "zz-drawcheck"; f = ROOT / "cast" / "levels" / f"{name}.puppet.json"
    f.unlink(missing_ok=True)
    subprocess.run([sys.executable, "-m", "dbe", "level.new", json.dumps({"name": name, "size": [400, 300], "fps": 12})], cwd=ROOT, check=True, capture_output=True)
    srv = subprocess.Popen([sys.executable, "-m", "dbe", "serve", str(port)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            with socket.socket() as s_:
                if s_.connect_ex(("127.0.0.1", port)) == 0:
                    break
            time.sleep(0.2)
        r = subprocess.run(["node", "tools/draw_check.mjs", str(port), name, str(tmp)], cwd=ROOT, capture_output=True, text=True, timeout=300)
        try:
            out = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            return [f"draw page: {(r.stderr or r.stdout)[-400:]}"], got
        got = {"cells": out["cells"], "drawings": len(out["drawings"]), "onion_px": out["onion"], "painted": out.get("painted"), "errors": out["errs"]}
        if [k for k, v in (out.get("painted") or {}).items() if v] != ["d01", "d02", "d03"]:
            fails.append(f"paint and carry on the page: {out.get('painted')}")
        if out["cells"] != ["d01", "d01", "d02", "d02", "d03", "d03"] or len(out["drawings"]) != 3:
            fails.append(f"sheet after drawing three on twos: {out['cells']}")
        xs = [out["drawings"][k][0][0] for k in ("d01", "d02") if out["drawings"].get(k)]
        if len(xs) != 2 or not xs[0] < xs[1]:
            fails.append(f"drawings not where they were drawn: {out['drawings']}")
        if not out["drawings"].get("d03") or out["drawings"]["d03"][0][3] < 100:
            fails.append("the brush stroke did not land on the last drawing")
        if not (out["onion"][0] > 0 and out["onion"][1] > out["onion"][0]):
            fails.append(f"onion skin: {out['onion']}")
        if out["errs"]:
            fails.append(f"page errors: {out['errs'][:3]}")
    finally:
        srv.terminate(); f.unlink(missing_ok=True); shutil.rmtree(tmp, ignore_errors=True)
    return fails, got


def part3_test(tmp):
    """cleanup drops construction lines and specks and keeps the line; photos of drawings on unevenly lit paper come in
    lined up with each other (registration) however the paper moved; a painted area follows its shape to the next
    drawing, and changing the style repaints both"""
    import shutil
    from PIL import Image, ImageDraw
    from . import commands as C
    fails, got = [], {}
    tmp = Path(tmp); shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir(parents=True)
    name = "zz-part3"; f = ROOT / "cast" / "levels" / f"{name}.puppet.json"; f.unlink(missing_ok=True)
    try:
        C.level_new(name, [400, 300], 12)
        # 1. cleanup
        im = Image.new("RGBA", (400, 300), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.ellipse([100, 80, 220, 200], outline=(36, 22, 14, 255), width=6)
        for k in range(6):
            d.line([(60 + k * 40, 40), (90 + k * 40, 260)], fill=(36, 22, 14, 60), width=2)   # construction lines
        for k in range(10):
            d.point([(30 + k * 33, 280)], fill=(36, 22, 14, 255))                             # specks
        im.save(tmp / "rough.png")
        C.level_draw(name, "d01", "data:image/png;base64," + base64.b64encode((tmp / "rough.png").read_bytes()).decode())
        r = C.level_cleanup(name)
        p = json.loads(f.read_text()); a = drawing_rgba(p, "d01", role="line")
        ring = a[80:201, 100:221, 3] > 0
        got["cleanup"] = {**r["cleaned"]["d01"], "ring_kept_px": int(ring.sum()), "outside_px": int((a[..., 3] > 0).sum() - ring.sum())}
        if got["cleanup"]["outside_px"] > 0 or got["cleanup"]["ring_kept_px"] < 1500:
            fails.append(f"cleanup: {got['cleanup']}")
        # 2. capture with registration
        for i, (ox, oy) in enumerate(((0, 0), (14, -9))):
            ph = Image.new("RGB", (800, 600)); px = ph.load()
            g = np.linspace(190, 240, 800).astype(np.uint8)
            ph = Image.fromarray(np.repeat(np.tile(g, (600, 1))[..., None], 3, -1))
            dr = ImageDraw.Draw(ph)
            dr.ellipse([300 + ox, 200 + oy, 500 + ox, 400 + oy], outline=(70, 70, 75), width=9)   # the same drawing; the paper moved
            dr.line([(320 + ox + i * 20, 300 + oy), (480 + ox, 300 + oy)], fill=(70, 70, 75), width=7)   # what changes between drawings
            ph.save(tmp / f"photo{i}.png")
        c1 = C.level_capture(name, "p1", str(tmp / "photo0.png"), place_after="d01", hold=2)
        c2 = C.level_capture(name, "p2", str(tmp / "photo1.png"), place_after="p1", hold=2)
        p = json.loads(f.read_text())
        cen = []
        for dn in ("p1", "p2"):
            al = drawing_rgba(p, dn, role="line")[..., 3] > 60
            ys, xs = np.nonzero(al); cen.append((float(xs.mean()), float(ys.mean())))
        got["capture"] = {"shift_found": c2["registered_by"], "centres": [[round(x, 1), round(y, 1)] for x, y in cen]}
        if abs(cen[0][1] - cen[1][1]) > 2.5 or abs(cen[0][0] - cen[1][0]) > 6:
            fails.append(f"registration: {got['capture']}")
        # 3. colour styles carried across drawings
        for dn, x in (("r1", 60), ("r2", 110)):
            im = Image.new("RGBA", (400, 300), (0, 0, 0, 0)); ImageDraw.Draw(im).ellipse([x, 90, x + 120, 210], outline=(36, 22, 14, 255), width=5)
            im.save(tmp / f"{dn}.png")
            C.level_draw(name, dn, "data:image/png;base64," + base64.b64encode((tmp / f"{dn}.png").read_bytes()).decode(), place_after="p2")
        C.level_colour(name, styles={"skin": "#f2c9a0"}, seeds={"r1": [[120, 150, "skin"]]}, propagate_from="r1")
        p = json.loads(f.read_text())
        inside = drawing_rgba(p, "r2", role="paint")[150, 170]
        C.level_colour(name, styles={"skin": "#6aa0d8"})
        p = json.loads(f.read_text())
        after = [drawing_rgba(p, dn, role="paint")[150, x + 60] for dn, x in (("r1", 60), ("r2", 110))]
        got["colour"] = {"r2_inside": inside.tolist(), "after_style_change": [a_.tolist() for a_ in after]}
        if list(inside[:3]) != [0xf2, 0xc9, 0xa0] or any(list(a_[:3]) != [0x6a, 0xa0, 0xd8] for a_ in after):
            fails.append(f"colour styles: {got['colour']}")
        outside = drawing_rgba(p, "r2", role="paint")[20, 20, 3]
        if outside:
            fails.append("paint leaked outside the shape")
    finally:
        f.unlink(missing_ok=True); shutil.rmtree(tmp, ignore_errors=True)
    return fails, got
