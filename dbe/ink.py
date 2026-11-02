"""Ink-fidelity import (plan 1.8): a photo or scan of a drawing becomes a puppet whose parts are the artist's own line.

    python dbe/ink.py SPEC.json OUT.puppet.json        (run with DBE_PY: needs numpy, scipy, Pillow)

The method comes from the doodle toolkit studied earlier: flatten lighting by dividing by a blurred copy, threshold ink
to alpha, drop specks. Parts are cut from the one ink layer by polygons, each part optionally grown a few pixels so
neighbouring parts overlap and the cuts don't show.

SPEC: {"photo": "path", "crop": [x0, y0, x1, y1] (optional), "name": "Nib", "template": "doodle",
       "ink": "#181e26", "threshold": [225, 75], "min_speck": 25,
       "parts": {"head": {"poly": [[x, y], ...], "pivot": [x, y], "parent": "body", "z": 20, "overlap": 4}, ...},
       "rest": "body"  (part that takes every ink pixel not claimed by another part),
       "swaps": {"eyes": {"anchor": "head", "z": 30, "open": {"poly": [...]}, "blink": "squash"}},
       "anchors": {"bubble": [x, y]}, "meta": {...}}
Coordinates are in the cropped drawing's pixels.
"""
import base64
import math
import io
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

UP = 3  # stored resolution multiplier


def extract(photo, crop=None, threshold=(225, 75), min_speck=25):
    im = Image.open(photo).convert("L")
    if crop:
        im = im.crop(tuple(crop))
    a = np.asarray(im).astype(np.float32)
    bg = np.asarray(im.filter(ImageFilter.GaussianBlur(25))).astype(np.float32)
    norm = np.clip(a / np.maximum(bg, 1) * 255, 0, 255)          # removes paper shadow and lighting gradients
    alpha = np.clip((threshold[0] - norm) / threshold[1], 0, 1)    # dark = ink
    mask = alpha > 0.35
    lab, n = ndimage.label(mask, np.ones((3, 3)))
    if n:
        sizes = ndimage.sum(mask, lab, range(1, n + 1))
        keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= min_speck])
        alpha = alpha * keep
    return alpha


def poly_mask(shape, poly, grow=0):
    m = Image.new("L", (shape[1], shape[0]), 0)
    ImageDraw.Draw(m).polygon([tuple(p) for p in poly], fill=255)
    out = np.asarray(m) > 0
    return ndimage.binary_dilation(out, iterations=grow) if grow else out


def raster(a, ink, pad=2):
    ys, xs = np.nonzero(a > 0.02)
    if not len(ys):
        return None
    y0, y1 = max(0, ys.min() - pad), min(a.shape[0], ys.max() + 1 + pad)
    x0, x1 = max(0, xs.min() - pad), min(a.shape[1], xs.max() + 1 + pad)
    rgba = np.zeros((y1 - y0, x1 - x0, 4), np.uint8)
    rgba[..., :3] = ink
    rgba[..., 3] = (np.clip(a[y0:y1, x0:x1], 0, 1) * 255).astype(np.uint8)
    im = Image.fromarray(rgba, "RGBA").resize(((x1 - x0) * UP, (y1 - y0) * UP), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "PNG", optimize=True)
    return {"image": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(), "x": int(x0), "y": int(y0), "w": int(x1 - x0), "h": int(y1 - y0)}


def squash(e, k):
    """line-weight-preserving vertical squash toward the lower edge (blinks): area-average, then re-ink"""
    ys, xs = np.nonzero(e > 0.02)
    if not len(ys):
        return e
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    nh = max(2, int(round((y1 - y0) * k)))
    small = np.asarray(Image.fromarray((e[y0:y1, x0:x1] * 255).astype(np.uint8), "L").resize((x1 - x0, nh), Image.BOX)).astype(np.float32) / 255
    small = np.clip(small * min(6.0, 1.1 / k), 0, 1)
    out = np.zeros_like(e); top = y1 - nh
    out[top:top + nh, x0:x1] = small
    return out


def make_mouths(gen, H, W):
    """talking mouth shapes in ink for a doodle: {shape: alpha array}, drawn at gen.center, gen.width wide, in the
    doodle's line weight (filled dark inside, like a pen-drawn open mouth)"""
    cx, cy = gen["center"]; mw = gen["width"]; lw = max(2, int(round(gen["line"])))
    S = {  # (kind, width factor, height factor)
        "closed": ("line", 0.75, 0.0), "small": ("oval", 0.45, 0.22), "mid": ("oval", 0.7, 0.4), "wide": ("oval", 0.95, 0.65),
        "O": ("oval", 0.42, 0.55), "FV": ("oval", 0.7, 0.16), "smile": ("smile", 0.9, 0.3)}
    out = {}
    for name, (kind, fw, fh) in S.items():
        im = Image.new("L", (W, H), 0); d = ImageDraw.Draw(im)
        if gen.get("keep_drawn") and kind == "oval" and name != "FV":   # cover the drawn mouth underneath
            fw, fh = max(fw, 0.8), max(fh, 0.4)
        hw, hh = mw * fw / 2, max(lw, mw * fh / 2)
        if kind == "line":
            d.line([(cx - hw, cy), (cx + hw, cy)], fill=255, width=lw)
        elif kind == "oval":
            d.ellipse([cx - hw, cy - hh, cx + hw, cy + hh], fill=235, outline=255, width=lw)
        else:
            d.arc([cx - hw, cy - 2 * hh, cx + hw, cy + hh], 15, 165, fill=255, width=lw)
        out[name] = np.asarray(im).astype(np.float32) / 255
    return out


def build(spec):
    ink = tuple(int(spec.get("ink", "#181e26")[i:i + 2], 16) for i in (1, 3, 5))
    A = extract(spec["photo"], spec.get("crop"), tuple(spec.get("threshold", (225, 75))), spec.get("min_speck", 25))
    H, W = A.shape
    claimed = np.zeros(A.shape, bool)
    parts = {}
    swap_masks = {sid: poly_mask(A.shape, sw["open"]["poly"], sw["open"].get("grow", 0)) for sid, sw in (spec.get("swaps") or {}).items() if sw.get("open")}
    any_swap = np.zeros(A.shape, bool)
    for m in swap_masks.values():
        any_swap |= m
    for pid, ps in spec.get("parts", {}).items():
        m = poly_mask(A.shape, ps["poly"], ps.get("overlap", 0))
        claimed |= poly_mask(A.shape, ps["poly"])
        st = raster(A * m * ~any_swap, ink)
        parts[pid] = {"parent": ps.get("parent"), "pivot": ps["pivot"], "z": ps.get("z", 10), "strokes": [st] if st else []}
    rest = spec.get("rest", "body")
    ys, xs = np.nonzero(A > 0.35)
    ground = int(ys.max()); feet = float(np.median(xs[ys > ground - 25]))
    parts.setdefault("hip", {"parent": None, "pivot": [feet, ground], "z": 0, "strokes": []})
    rest_st = raster(A * ~claimed * ~any_swap, ink)
    base = parts.get(rest, {"parent": "hip", "pivot": [feet, ground], "z": 10, "strokes": []})
    base["strokes"] = base.get("strokes", []) + ([rest_st] if rest_st else [])
    base.setdefault("parent", "hip"); parts[rest] = base
    swaps = {}
    for sid, sw in (spec.get("swaps") or {}).items():
        if sw.get("talk"):   # plan 3.6: a mouth; the drawn one is "closed", talking shapes are drawn to match it
            gen = make_mouths(sw["talk"], H, W)
            shapes = {k: [s for s in [raster(v, ink)] if s] for k, v in gen.items()}
            if sw["talk"].get("keep_drawn"):   # the drawn mouth stays in the head; "closed" adds nothing
                shapes["closed"] = []
            if sid in swap_masks:
                drawn = raster(A * swap_masks[sid], ink)
                if drawn:
                    shapes["closed"] = [drawn]
            swaps[sid] = {"anchor": sw.get("anchor", "head"), "z": sw.get("z", 31), "shapes": shapes, "talk": ["closed", "small", "mid", "wide"],
                          "made": "talking shapes drawn to match the doodle's line (dbe/autorig.py)"}
            continue
        e = A * swap_masks[sid]
        shapes = {"open": [s for s in [raster(e, ink)] if s]}
        if sw.get("blink", "squash") == "squash":
            shapes["half"] = [s for s in [raster(squash(e, 0.45), ink)] if s]
            shapes["closed"] = [s for s in [raster(squash(e, 0.12), ink)] if s]
        swaps[sid] = {"anchor": sw.get("anchor", "head"), "z": sw.get("z", 30), "shapes": shapes}
    return {"format": "doodleberry.puppet", "version": "0.3", "name": spec.get("name", "Doodle"), "template": spec.get("template", "doodle"),
            "artboard": [W, H], "ground": ground, "palette": {"ink": spec.get("ink", "#181e26")}, "parts": parts, "swaps": swaps,
            **({"springs": spec["springs"]} if spec.get("springs") else {}), "anchors": spec.get("anchors", {}),
            "meta": {**spec.get("meta", {}), "source": str(spec["photo"]), "import": "dbe/ink.py (ink-fidelity import)"}}


if __name__ == "__main__":
    spec = json.loads(Path(sys.argv[1]).read_text())
    base = Path(sys.argv[1]).parent
    if not Path(spec["photo"]).is_absolute():
        spec["photo"] = str((base / spec["photo"]).resolve())
    pz = build(spec)
    Path(sys.argv[2]).write_text(json.dumps(pz))
    print(json.dumps({"parts": {k: len(v["strokes"]) for k, v in pz["parts"].items()}, "swaps": {k: list(v["shapes"]) for k, v in pz["swaps"].items()},
                      "ground": pz["ground"], "kb": len(json.dumps(pz)) // 1024}))
