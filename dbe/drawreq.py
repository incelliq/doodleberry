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

CANVAS_ONLY = ("chain", "clip for the")   # needs that are drawn and rigged in the Rig Canvas
TURN_VIEW = "three_quarter"               # the view a turn request draws (the head turned three-quarters, facing right)


def queue_path(puppet_rel):
    return ROOT / re.sub(r"\.puppet\.json$", ".requests.json", puppet_rel)


def parse_need(label):
    """'mouth: smile' -> [{kind: swap, swap: mouth, shape: smile}]; 'part tail' -> [{kind: part, part: tail}];
    'mouth: closed, small, mid, wide (O, FV, smile, frown help)' -> one per listed shape; others -> canvas"""
    if any(k in label for k in CANVAS_ONLY):
        return [{"kind": "canvas", "what": label}]
    if label.startswith("pupils"):                # WP-18: pupils are drawn over the eyes on a ghost
        return [{"kind": "swap", "swap": "pupils", "shape": "default"}]
    if "three-quarter" in label:                  # WP-18: the head turned, drawn over the head on a ghost
        return [{"kind": "view", "view": TURN_VIEW, "part": "head"}]
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
    if req["kind"] == "view":
        return "turn" not in (p.get("controls") or {}) and req["part"] not in (((p.get("views") or {}).get(req["view"]) or {}).get("parts") or {})
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
    if req["kind"] == "swap" and req["swap"] == "pupils" and not _swap_box(p, "pupils") and _swap_box(p, "eyes"):
        return grow(_swap_box(p, "eyes"), 0.15)  # pupils go inside the eyes
    if req["kind"] == "view":
        b = _part_box(p, req["part"]) or [W * 0.25, H * 0.05, W * 0.75, H * 0.45]
        return [max(0, v) if i < 2 else min((W, H)[i - 2], v) for i, v in enumerate(grow(b, 0.12))]
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
    related = req["kind"] == "view" or (req["kind"] == "swap" and (_swap_box(p, req["swap"]) or (req["swap"] == "pupils" and _swap_box(p, "eyes"))))
    if related:   # the related drawing it has (the shape it varies, the eyes for pupils, the head for a turn), at 45%
        crop = (int(max(0, x0)), int(max(0, y0)), int(min(im.width, x1)), int(min(im.height, y1)))
        if crop[2] > crop[0] and crop[3] > crop[1]:
            faint.paste(Image.blend(im.crop(crop), Image.new("RGB", (crop[2] - crop[0], crop[3] - crop[1]), "white"), 0.55), crop[:2])
    dash = 10
    for (ax, ay, bx, by) in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
        L = math.hypot(bx - ax, by - ay); n = max(1, int(L // dash))
        for i in range(0, n, 2):
            t0, t1 = i / n, min(1, (i + 1) / n)
            d.line([(ax + (bx - ax) * t0, ay + (by - ay) * t0), (ax + (bx - ax) * t1, ay + (by - ay) * t1)], fill=(232, 116, 58), width=3)
    what = ("pupils inside the eyes" if req.get("swap") == "pupils" else f"{req['swap']}: {req['shape']}") if req["kind"] == "swap" else \
        f"the {req['part']} turned 3/4 to the right (no face)" if req["kind"] == "view" else f"{req['part']}"
    from PIL import ImageFont
    try:
        font = ImageFont.load_default(size=max(14, int(im.width / 30)))
    except TypeError:
        font = ImageFont.load_default()
    fs = getattr(font, "size", 12)
    ty = y0 - fs - 6 if y0 - fs - 6 >= 2 else y1 + 6   # above the box, or below it when the box reaches the top
    d.text((x0 + 4, ty), "draw " + what, fill=(232, 116, 58), font=font)
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
    if req["kind"] == "swap" and req["swap"] == "pupils":
        return _slot_pupils(p, st, A)
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
    if req["kind"] == "view":
        return _slot_view(p, req, st, A)
    raise ValueError("this request is drawn in the Rig Canvas")


# ---------- WP-18: pupils and a turned view from drawings on the ghost ----------
FACE = ("eyes", "pupils", "mouth", "brows")


def _decode(st):
    import base64, io
    return Image.open(io.BytesIO(base64.b64decode(st["image"].split(",", 1)[1]))).convert("RGBA")


def _encode(im):
    import base64, io
    buf = io.BytesIO(); im.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _alpha_art(p, st):
    """a raster stroke's alpha on the artboard grid (artboard units = pixels)"""
    W, H = int(p["artboard"][0]), int(p["artboard"][1]); out = np.zeros((H, W), np.float32)
    a = np.asarray(_decode(st).resize((st["w"], st["h"]), Image.BOX))[..., 3].astype(np.float32) / 255
    x0, y0 = st["x"], st["y"]; x1, y1 = min(W, x0 + st["w"]), min(H, y0 + st["h"])
    out[max(0, y0):y1, max(0, x0):x1] = a[max(0, -y0):y1 - y0, max(0, -x0):x1 - x0]
    return out


def _widths(mask):
    from scipy import ndimage
    lab, n = ndimage.label(mask, np.ones((3, 3)))
    objs = [(sl, int((lab[sl] == i + 1).sum())) for i, sl in enumerate(ndimage.find_objects(lab)) if sl is not None]
    big = max((a for _, a in objs), default=0)
    return [sl[1].stop - sl[1].start for sl, a in objs if a >= 0.1 * big]   # specks (left by a painted-out dot) are not eyes


def _slot_pupils(p, st, A):
    """pupils drawn inside the eyes: the eyes' own drawn dots under them are painted out of the open eyes (the
    pupils move now), and how far they may move is what the eye leaves around them"""
    from scipy import ndimage
    sw = (p.get("swaps") or {}).get("eyes") or {}
    pm = A > 0.35
    for name in ("open",):
        for i, est in enumerate((sw.get("shapes") or {}).get(name) or []):
            if "image" not in est:
                continue
            im = _decode(est); k = im.width / est["w"]
            cover = ndimage.binary_dilation(pm, iterations=4)[est["y"]:est["y"] + est["h"], est["x"]:est["x"] + est["w"]]
            cv = Image.fromarray((cover * 255).astype(np.uint8)).resize(im.size, Image.NEAREST)
            arr = np.asarray(im).copy(); arr[..., 3][np.asarray(cv) > 0] = 0
            # (draw the pupils inside the eye outline: ink of the eye within a few pixels of them goes too)
            sw["shapes"][name][i] = {**est, "image": _encode(Image.fromarray(arr, "RGBA"))}
    eye_w = _widths(_alpha_art(p, (sw.get("shapes") or {}).get("open", [{}])[0]) > 0.35) if (sw.get("shapes") or {}).get("open") else []
    pup_w = _widths(pm)
    room = (min(eye_w) - max(pup_w)) / 2 if eye_w and pup_w else 8
    movable = round(float(np.clip(0.6 * room, 2, 14)), 1)   # leave the eye's own line width
    p.setdefault("swaps", {})["pupils"] = {"anchor": sw.get("anchor", "head" if "head" in p["parts"] else "body"), "z": sw.get("z", 30) + 2,
                                           "movable": movable, "shapes": {"default": [st]}}
    for vname, fm in ((p.get("meta") or {}).get("face_map") or {}).items():   # a turned view drawn earlier carries the pupils too
        p["views"][vname].setdefault("swaps", {})["pupils"] = {"shapes": {"default": [_map_stroke(st, fm)]}}
    return "swaps.pupils.shapes.default"


def _map_stroke(st, fm):
    """x -> to + (x - from) * k (a face slid and narrowed for a turned view)"""
    f = lambda x: fm["to"] + (x - fm["from"]) * fm["k"]
    if "image" in st:
        x0, x1 = f(st["x"]), f(st["x"] + st["w"])
        return {**st, "x": int(round(x0)), "w": max(1, int(round(x1 - x0)))}
    if st.get("d"):
        d = []
        for segs, closed in G.parse_path(st["d"]):
            if not segs:
                continue
            d.append(f"M{f(segs[0][0][0]):.1f} {segs[0][0][1]:.1f}")
            d += [f"C{f(c1[0]):.1f} {c1[1]:.1f} {f(c2[0]):.1f} {c2[1]:.1f} {f(p1[0]):.1f} {p1[1]:.1f}" for (_, c1, c2, p1) in segs]
            if closed:
                d.append("Z")
        return {**st, "d": " ".join(d)}
    return dict(st)


def _slot_view(p, req, st, A):
    """the head drawn turned three-quarters: it replaces the head's strokes in that view, and the face (eyes,
    pupils, mouth, brows) slides toward the side it faces and narrows, as a face does when a head turns"""
    ys, xs = np.nonzero(A > 0.35)
    old = _part_box(p, req["part"]) or req["box"]
    nx0, nx1 = float(xs.min()), float(xs.max())
    face = _union([_swap_box(p, k) for k in FACE if k in (p.get("swaps") or {})])
    fc0 = (face[0] + face[2]) / 2 if face else (old[0] + old[2]) / 2
    rel = (fc0 - (old[0] + old[2]) / 2) / max(1.0, old[2] - old[0])
    k = round(0.8 * min(1.0, (nx1 - nx0) / max(1.0, old[2] - old[0])), 3)
    fm = {"from": round(fc0, 1), "to": round((nx0 + nx1) / 2 + (rel + 0.1) * (nx1 - nx0), 1), "k": k}
    v = p.setdefault("views", {}).setdefault(req["view"], {})
    v.setdefault("parts", {})[req["part"]] = {"strokes": [st]}
    for k in FACE:
        sw = (p.get("swaps") or {}).get(k)
        if sw:
            v.setdefault("swaps", {})[k] = {"shapes": {name: [_map_stroke(x, fm) for x in sts] for name, sts in (sw.get("shapes") or {}).items()}}
    p.setdefault("meta", {}).setdefault("face_map", {})[req["view"]] = fm
    return f"views.{req['view']}.parts.{req['part']}"
