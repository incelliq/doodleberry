"""Drawing request queue with ghost guides (plan 3.6, feature map E20).

When a script asks a character for something its rig cannot do (script.rigcheck), or a new doodle lacks drawings a
move needs (puppet.abilities), each missing drawing becomes a request: which swap shape or part, why (the sentences
or moves that need it), and a ghost guide, an image the size of the character's artboard showing the character
faintly at rest, the related drawing it already has, and a dashed box where the new drawing goes. A drawing made on
the ghost (on a phone over the guide, or on paper and photographed at the same framing) slots straight into the rig:
ink is lifted from it, kept inside the box, and stored as that swap shape or part in artboard space. The request
closes only when the rig check no longer lists the need.

Requests live next to the character: cast/drawn/nib.puppet.json -> cast/drawn/nib.requests.json.
"""
import json
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import ROOT
from . import geom as G

CANVAS_ONLY = ("pupils", "three-quarter", "chain", "clip for the")   # needs that are drawn and rigged in the Rig Canvas


def queue_path(puppet_rel):
    return ROOT / re.sub(r"\.puppet\.json$", ".requests.json", puppet_rel)


def parse_need(label):
    """'mouth: smile' -> [{kind: swap, swap: mouth, shape: smile}]; 'part tail' -> [{kind: part, part: tail}];
    'mouth: closed, small, mid, wide (O, FV, smile, frown help)' -> one per listed shape; others -> canvas"""
    if any(k in label for k in CANVAS_ONLY):
        return [{"kind": "canvas", "what": label}]
    m = re.match(r"part (\w+)$", label)
    if m:
        return [{"kind": "part", "part": m.group(1)}]
    m = re.match(r"(\w+): (.+)$", label)
    if m:
        shapes = [s.strip() for s in re.sub(r"\(.*?\)", "", m.group(2)).split(",") if s.strip()]
        return [{"kind": "swap", "swap": m.group(1), "shape": s} for s in shapes]
    return [{"kind": "canvas", "what": label}]


def missing(p, req):
    """is this request's drawing still missing from the puppet?"""
    if req["kind"] == "swap":
        return req["shape"] not in (((p.get("swaps") or {}).get(req["swap"]) or {}).get("shapes") or {})
    if req["kind"] == "part":
        return req["part"] not in p.get("parts", {})
    return True


def _stroke_box(st):
    if "image" in st:
        return [st["x"], st["y"], st["x"] + st["w"], st["y"] + st["h"]]
    if st.get("d"):
        pts = [q for segs, _ in G.parse_path(st["d"]) for q in G.sample(segs, 4)]
        if pts:
            xs, ys = [q[0] for q in pts], [q[1] for q in pts]
            return [min(xs), min(ys), max(xs), max(ys)]
    return None


def _union(boxes):
    boxes = [b for b in boxes if b]
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)] if boxes else None


def _swap_box(p, swap):
    sw = (p.get("swaps") or {}).get(swap) or {}
    return _union([_stroke_box(st) for strokes in (sw.get("shapes") or {}).values() for st in strokes])


def _part_box(p, part):
    return _union([_stroke_box(st) for st in (p.get("parts", {}).get(part) or {}).get("strokes", [])])


def box_for(p, req):
    """where the new drawing goes, in artboard units, with a little room"""
    W, H = p["artboard"]
    grow = lambda b, k: [b[0] - (b[2] - b[0]) * k, b[1] - (b[3] - b[1]) * k, b[2] + (b[2] - b[0]) * k, b[3] + (b[3] - b[1]) * k]
    if req["kind"] == "swap":
        b = _swap_box(p, req["swap"])
        if b:
            return grow(b, 0.35)
        eyes = _swap_box(p, "eyes"); head = _part_box(p, "head")
        if req["swap"] == "brows" and eyes:
            eh = eyes[3] - eyes[1]
            return [eyes[0] - 0.1 * (eyes[2] - eyes[0]), eyes[1] - 1.0 * eh, eyes[2] + 0.1 * (eyes[2] - eyes[0]), eyes[1] + 0.15 * eh]
        if req["swap"] == "mouth" and head:
            hw, hh = head[2] - head[0], head[3] - head[1]
            return [head[0] + 0.3 * hw, head[1] + 0.6 * hh, head[2] - 0.3 * hw, head[1] + 0.9 * hh]
        return grow(head or [W * 0.3, H * 0.1, W * 0.7, H * 0.4], 0.0)
    if req["kind"] == "part" and req["part"] == "tail":
        body = _part_box(p, "body") or [W * 0.3, H * 0.4, W * 0.7, H * 0.9]
        bw, bh = body[2] - body[0], body[3] - body[1]
        return [body[2] - 0.15 * bw, body[1] + 0.35 * bh, min(W, body[2] + 0.45 * bw), body[1] + 0.85 * bh]
    return [0, 0, W, H]


def make_requests(p, needs):
    """needs: {label: [why, ...]} -> request dicts (without ids)"""
    out = []
    for label, why in needs.items():
        for r in parse_need(label):
            if r["kind"] != "canvas" and not missing(p, r):
                continue
            r.update(need=label, why=why, status="open" if r["kind"] != "canvas" else "rig_canvas")
            if r["kind"] != "canvas":
                r["box"] = [round(v, 1) for v in box_for(p, r)]
            out.append(r)
    return out


def ghost_spec(p, puppet_rel):
    """pose_still spec that draws the character at rest exactly on its artboard (1 unit = 1 pixel)"""
    W, H = p["artboard"]; hip = p["parts"].get("hip", {}).get("pivot", [W / 2, p["ground"]])
    return {"size": [int(W), int(H)], "bg": "#ffffff", "items": [{"puppet": puppet_rel, "x": hip[0], "y": p["ground"], "s": 1,
                                                                   "pose": {"blink": 0}}]}


def compose_ghost(rest_png, p, req, out_png):
    """fade the character to a faint guide, keep the related drawing a little stronger, draw the dashed box and a label"""
    im = Image.open(rest_png).convert("RGB")
    faint = Image.blend(im, Image.new("RGB", im.size, "white"), 0.78)
    d = ImageDraw.Draw(faint)
    x0, y0, x1, y1 = req["box"]
    if req["kind"] == "swap" and _swap_box(p, req["swap"]):   # the related drawing it has, at 45%
        crop = (int(max(0, x0)), int(max(0, y0)), int(min(im.width, x1)), int(min(im.height, y1)))
        if crop[2] > crop[0] and crop[3] > crop[1]:
            faint.paste(Image.blend(im.crop(crop), Image.new("RGB", (crop[2] - crop[0], crop[3] - crop[1]), "white"), 0.55), crop[:2])
    dash = 10
    for (ax, ay, bx, by) in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
        L = math.hypot(bx - ax, by - ay); n = max(1, int(L // dash))
        for i in range(0, n, 2):
            t0, t1 = i / n, min(1, (i + 1) / n)
            d.line([(ax + (bx - ax) * t0, ay + (by - ay) * t0), (ax + (bx - ax) * t1, ay + (by - ay) * t1)], fill=(232, 116, 58), width=3)
    what = f"{req['swap']}: {req['shape']}" if req["kind"] == "swap" else f"{req['part']}"
    from PIL import ImageFont
    try:
        font = ImageFont.load_default(size=max(14, int(im.width / 30)))
    except TypeError:
        font = ImageFont.load_default()
    d.text((x0 + 4, max(2, y0 - font.size - 6 if hasattr(font, "size") else y0 - 16)), "draw " + what, fill=(232, 116, 58), font=font)
    faint.save(out_png)
    return out_png


def lift(image, p, req, ink_hex=None):
    """ink from a drawing made on the ghost (artboard-sized; a photo or a canvas export) inside the request's box ->
    a raster stroke in artboard units"""
    import importlib.util
    sp = importlib.util.spec_from_file_location("ink", ROOT / "dbe" / "ink.py"); ink = importlib.util.module_from_spec(sp); sp.loader.exec_module(ink)
    W, H = int(p["artboard"][0]), int(p["artboard"][1])
    im = Image.open(image)
    if im.mode in ("RGBA", "LA"):   # canvas exports: transparent background -> paper
        bg = Image.new("RGBA", im.size, "white"); bg.alpha_composite(im.convert("RGBA")); im = bg
    im = im.convert("RGB")
    if im.size != (W, H):
        im = im.resize((W, H), Image.LANCZOS)
    tmp = Path(image).with_suffix(".lift.png"); im.save(tmp)
    A = ink.extract(str(tmp)); tmp.unlink()
    x0, y0, x1, y1 = req["box"]; m = np.zeros_like(A, bool)
    m[int(max(0, y0)):int(min(H, y1)), int(max(0, x0)):int(min(W, x1))] = True
    A = A * m
    if (A > 0.35).sum() < 15:
        raise ValueError("no drawing found inside the dashed box")
    col = ink_hex or (p.get("palette") or {}).get("ink") or "#1c1e24"
    st = ink.raster(A, tuple(int(col[i:i + 2], 16) for i in (1, 3, 5)))
    return st, A


def slot(p, req, st, A):
    """put the lifted drawing into the rig"""
    if req["kind"] == "swap":
        sw = p.setdefault("swaps", {}).setdefault(req["swap"], {"anchor": "head" if "head" in p["parts"] else "body", "z": 32, "shapes": {}})
        sw.setdefault("shapes", {})[req["shape"]] = [st]
        if req["swap"] == "brows":
            sw["shapes"].setdefault("neutral", [])   # a doodle without brows keeps none at rest
        return f"swaps.{req['swap']}.shapes.{req['shape']}"
    if req["kind"] == "part":
        owner = "body" if "body" in p["parts"] else "head"
        ys, xs = np.nonzero(A > 0.35)
        ob = _part_box(p, owner) or [0, 0, *p["artboard"]]
        cx, cy = (ob[0] + ob[2]) / 2, (ob[1] + ob[3]) / 2
        k = int(np.argmin((xs - cx) ** 2 + (ys - cy) ** 2))   # the end nearest the body is the pivot
        p["parts"][req["part"]] = {"parent": owner, "pivot": [int(xs[k]), int(ys[k])], "z": 8, "strokes": [st]}
        return f"parts.{req['part']}"
    raise ValueError("this request is drawn in the Rig Canvas")
