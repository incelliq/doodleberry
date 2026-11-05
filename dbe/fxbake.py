"""Motion effects for every renderer (WP-14). tools/bake.mjs records, frame by frame, the markup the player's
FX.render draws (speed lines, dust, impact stars, motion arcs) in world coordinates. Here each distinct frame becomes a
drawing of a swap set on a generated puppet that covers the frame, placed so the shot camera frames it as it frames the
characters; the bake's cast gains that puppet last, so Synfig, Lottie and Grease Pencil draw the effects as they draw
any swap. Frames that draw nothing show no drawing.
"""
import hashlib
import json
import tempfile
from pathlib import Path

from . import drawing_import as DI

DEFAULT_FRAME = {"angles": {}, "offset": [0, 0], "mouth": None, "eyes": None, "blink": 0, "look": None, "brows": None, "hand_R_pose": None,
                 "view": None, "squash": 1, "shifts": None, "scales": None, "grow": None, "z": None}


def _strokes(markup, size, palette):
    W, H = size
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "fx.svg"
        f.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">{markup}</svg>')
        src = DI.read_svg(f)
    out = []
    for r in src["items"]:
        st = r["style"]
        def slot(v):
            c = (DI.colour(v, {}) or "none").lower()
            if c in ("none", "transparent"):
                return "none"
            key = next((k for k, x in palette.items() if x == c), None)
            if not key:
                key = f"fx{len(palette)}"; palette[key] = c
            return key
        fill, line = slot(st.get("fill")), slot(st.get("stroke"))
        if "z" not in r["d"].lower():   # an open line (a speed line, an arc): SVG's default fill draws nothing there
            fill = "none"
        if fill == "none" and line == "none":
            continue
        s = {"d": r["d"], "fill": fill}
        if line != "none":
            s["stroke"] = line; s["width"] = round(float(st.get("stroke-width") or 1) * r.get("scale", 1.0), 2)
        op = float(st.get("opacity") or 1) * float(st.get("fill-opacity" if fill != "none" else "stroke-opacity") or 1)
        if op < 0.999:
            s["opacity"] = round(op, 3)
        out.append(s)
    return out


def add_fx_puppet(baked, size, puppet_path):
    """baked (with "fx" from tools/bake.mjs) -> the same dict with the effects puppet appended to its cast"""
    fx = baked.pop("fx", None)
    if not fx:
        return baked
    W, H = size; palette = {}; shapes = {}; names = {}; frames = []
    for markup, (cx, cy, z) in zip(fx["frames"], fx["camera"]):
        m = (markup or "").strip(); name = None
        if m:
            h = hashlib.sha1(m.encode()).hexdigest()[:12]
            if h not in names:
                strokes = _strokes(m, size, palette)
                names[h] = f"f{len(shapes)}" if strokes else None
                if strokes:
                    shapes[names[h]] = strokes
            name = names[h]
        frames.append({**DEFAULT_FRAME, "x": W / 2 - cx * z, "y": H / 2 - cy * z, "s": z, "flip": 1, "fx": name})
    if not shapes:
        return baked
    raster = _rasters(fx["frames"], names, shapes, size, Path(str(puppet_path) + ".assets"))
    pz = {"format": "doodleberry.puppet", "version": "0.12", "name": "motion effects", "template": "doodle", "artboard": [W, H], "ground": 0,
          "palette": palette, "parts": {"hip": {"parent": None, "pivot": [0, 0], "z": 0, "strokes": []}},
          "swaps": {"fx": {"anchor": "hip", "z": 99, "shapes": shapes, "raster_shapes": raster}}, "meta": {"generated_by": "dbe/fxbake.py", "drawings": len(shapes)}}
    Path(puppet_path).write_text(json.dumps(pz))
    baked["cast"].append({"puppet": str(puppet_path), "name": "motion effects", "fx": True, "frames": frames})
    return baked


def _rasters(frames, names, shapes, size, adir):
    """each drawing also as a PNG cropped to its ink (the player's own markup drawn by Chromium), for renderers whose
    file format cannot hold hundreds of vector drawings (Synfig's XML parser stops at 10 MB)"""
    import base64
    import subprocess
    from . import ROOT, geom as G
    adir.mkdir(parents=True, exist_ok=True); jobs, seen = [], set()
    for m in frames:
        m = (m or "").strip()
        if not m:
            continue
        nm = names.get(hashlib.sha1(m.encode()).hexdigest()[:12])
        if not nm or nm in seen:
            continue
        seen.add(nm); xs, ys = [], []
        for st in shapes[nm]:
            for segs, _ in G.parse_path(st["d"]):
                for q in G.sample(segs, 3):
                    xs.append(q[0]); ys.append(q[1])
        pad = 4 + max([st.get("width", 0) for st in shapes[nm]] + [0])
        x0, y0, x1, y1 = min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad
        jobs.append({"svg": m, "box": [x0, y0, x1 - x0, y1 - y0], "out": str(adir / f"{nm}.png"), "name": nm})
    if not jobs:
        return {}
    (adir / "jobs.json").write_text(json.dumps({"size": size, "items": jobs}))
    subprocess.run(["node", str(ROOT / "tools" / "fx_raster.mjs"), str(adir / "jobs.json")], check=True, cwd=ROOT, capture_output=True, timeout=1800)
    out = {}
    for j in jobs:
        x, y, w, h = [round(v) for v in j["box"]]
        out[j["name"]] = [{"image": "data:image/png;base64," + base64.b64encode(Path(j["out"]).read_bytes()).decode(), "x": x, "y": y, "w": w, "h": h}]
    return out
