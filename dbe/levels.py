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
