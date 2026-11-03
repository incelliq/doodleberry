"""Auto cuts and pivots for a doodle photo (plan 3.6, the open part of 1.8).

    photo of a pen doodle --prepare--> upright, cropped to the ink, about 900 px
          --suggest--> an ink spec (dbe/ink.py format): head, arms, tail cuts as polygons, pivots, eyes and mouth swaps
          --ink.build--> a doodle-template puppet in the artist's own line

How the drawing is read (all on the ink mask, after small gaps in the line are closed):
- closed loops are the background areas the line encloses. The two largest stacked loops are the head (upper) and
  the body (lower); a single large loop is a blob character (all head, which tilts and talks on its own).
- features are the marks inside the head loop: those in its upper part are the eyes (one swap, blinks made by
  squashing), the lowest wide one is the mouth. A mouth is drawn as `closed`, and the talking shapes (small, mid,
  wide, O, FV, smile) are drawn for it in the same ink and line weight; with no mouth drawn, all are made.
- strokes leaving the body's sides at the body's height are arms (pivot where they meet the body); a third side
  stroke low on the body is a tail; everything else (legs, hats, feet) stays with the body.
Each guess is reported with a reason, so the person confirming the cuts knows what to look at.
"""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from scipy import ndimage

from . import ROOT


def _ink():
    import importlib.util
    spec = importlib.util.spec_from_file_location("ink", ROOT / "dbe" / "ink.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def prepare(photo, out_png, long_side=900):
    """an upright copy of the photo cropped to the drawing (6% margin) and scaled so its long side is ~long_side"""
    ink = _ink()
    im = ImageOps.exif_transpose(Image.open(photo)).convert("RGB")
    s = min(1.0, 1400 / max(im.size)); small = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS) if s < 1 else im
    tmp = Path(out_png).with_suffix(".probe.png"); small.save(tmp)
    A = ink.extract(str(tmp)); tmp.unlink()
    ys, xs = np.nonzero(A > 0.35)
    if len(ys) < 50:
        raise ValueError("no drawing found: photograph dark pen lines on light paper, filling most of the frame")
    x0, x1, y0, y1 = xs.min() / s, xs.max() / s, ys.min() / s, ys.max() / s
    m = 0.06 * max(x1 - x0, y1 - y0)
    box = (max(0, int(x0 - m)), max(0, int(y0 - m)), min(im.width, int(x1 + m)), min(im.height, int(y1 + m)))
    im = im.crop(box); k = long_side / max(im.size)
    im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
    im.save(out_png)
    return {"size": list(im.size), "crop": list(box), "scale": round(k, 4)}


def split_page(photo, out_dir, min_share=0.08):
    """a page with several doodles -> one photo per doodle (upright, each cropped to its own ink, the others' ink
    painted out with the paper colour), left to right then top to bottom. Strokes are grouped by closing gaps of
    about 2.5% of the page and filling the loops (so eyes and mouths drawn inside a head stay with it); groups with
    less than min_share of the ink are specks, left out. -> [{photo, box, ink_share}]"""
    ink = _ink()
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    im = ImageOps.exif_transpose(Image.open(photo)).convert("RGB")
    s = min(1.0, 1400 / max(im.size)); small = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS) if s < 1 else im
    tmp = out_dir / "page.probe.png"; small.save(tmp)
    A = ink.extract(str(tmp)); tmp.unlink()
    mask = A > 0.35
    if mask.sum() < 50:
        raise ValueError("no drawing found: photograph dark pen lines on light paper, filling most of the frame")
    g = max(3, int(round(0.025 * max(mask.shape))))
    pad = g + 2
    grown = ndimage.binary_dilation(np.pad(mask, pad), iterations=g)
    grown = ndimage.binary_fill_holes(grown)[pad:-pad, pad:-pad]
    lab, n = ndimage.label(grown, np.ones((3, 3)))
    total = float(mask.sum()); groups = []
    for i in range(1, n + 1):
        own = mask & (lab == i); share = own.sum() / total
        if share < min_share:
            continue
        ys, xs = np.nonzero(own); groups.append({"i": i, "share": round(float(share), 3), "box": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]})
    if not groups:
        raise ValueError("no doodle large enough on the page")
    # reading order: rows (boxes whose vertical spans overlap), then left to right
    groups.sort(key=lambda gr: (gr["box"][1], gr["box"][0]))
    rows = []
    for gr in groups:
        r = next((r for r in rows if gr["box"][1] <= max(x["box"][3] for x in r) and gr["box"][3] >= min(x["box"][1] for x in r)), None)
        (r.append(gr) if r is not None else rows.append([gr]))
    order = [gr for r in rows for gr in sorted(r, key=lambda gr: gr["box"][0])]
    paper = tuple(int(v) for v in np.median(np.asarray(small)[~ndimage.binary_dilation(mask, iterations=3)], axis=0))
    big = np.asarray(im).copy()
    out = []
    for k, gr in enumerate(order):
        others = (lab != gr["i"]) & (lab > 0)
        o_big = np.asarray(Image.fromarray((others * 255).astype(np.uint8)).resize(im.size, Image.NEAREST)) > 0
        page = big.copy(); page[o_big] = paper
        x0, y0, x1, y1 = (v / s for v in gr["box"]); m = 0.06 * max(x1 - x0, y1 - y0)
        box = (max(0, int(x0 - m)), max(0, int(y0 - m)), min(im.width, int(x1 + m)), min(im.height, int(y1 + m)))
        f = out_dir / f"doodle{k + 1}.png"; Image.fromarray(page).crop(box).save(f)
        out.append({"photo": str(f), "box": list(box), "ink_share": gr["share"]})
    return out


def synthetic_page(kinds=("nib", "cat"), seed=5):
    """a phone-photo-like page with several synthetic doodles side by side -> (PIL image, [truth per doodle])"""
    from PIL import ImageFilter
    tiles = [synthetic_doodle(k, seed=seed + i) for i, k in enumerate(kinds)]
    gap = 40; W = sum(t[0].width for t in tiles) + gap * (len(tiles) - 1); H = max(t[0].height for t in tiles)
    page = np.full((H, W, 3), (236, 233, 224), np.int16); x = 0; truths = []
    for im, tr in tiles:   # the ink of each doodle on one sheet of paper
        a = np.asarray(im).astype(np.int16); ink_ = a.mean(axis=2) < 150
        page[:a.shape[0], x:x + a.shape[1]][ink_] = a[ink_]; truths.append({**tr, "offset": [x, 0]}); x += im.width + gap
    g = np.linspace(255, 205, W)[None, :, None] / 255
    page = np.clip(page * g + np.random.default_rng(seed).integers(-6, 7, (H, W, 1)), 0, 255).astype(np.uint8)
    return Image.fromarray(page).filter(ImageFilter.GaussianBlur(0.5)), truths


def _hull(pts):
    pts = sorted(set(map(tuple, pts)))
    if len(pts) < 3:
        return [list(p) for p in pts]
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return [list(p) for p in lo[:-1] + hi[:-1]]


def _poly(mask, grow):
    """convex outline of a mask, pushed out by `grow` pixels, as an integer polygon"""
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return None
    edge = mask & ~ndimage.binary_erosion(mask)
    ey, ex = np.nonzero(edge)
    h = _hull(np.stack([ex, ey], 1)) if len(ex) >= 3 else _hull(np.stack([xs, ys], 1))
    c = np.array([xs.mean(), ys.mean()])
    out = []
    for p in h:
        v = np.array(p, float) - c; n = np.linalg.norm(v) or 1.0
        out.append([int(round(p[0] + v[0] / n * grow)), int(round(p[1] + v[1] / n * grow))])
    return out


def _bbox(m):
    ys, xs = np.nonzero(m)
    return xs.min(), xs.max(), ys.min(), ys.max()


def suggest(photo, name="Doodle", ink_hex="#1c1e24"):
    """-> ink spec for dbe/ink.py with a "found" report; photo should come from prepare()"""
    ink = _ink()
    A = ink.extract(photo); mask = A > 0.35
    H, W = mask.shape
    edt = ndimage.distance_transform_edt(mask)
    w = float(max(2.0, 2 * np.percentile(edt[mask], 90))) if mask.any() else 3.0
    g = int(max(2, round(w * 1.5)))
    pad = g + 2
    mc = ndimage.binary_closing(np.pad(mask, pad), iterations=g)[pad:-pad, pad:-pad] | mask
    filled = ndimage.binary_fill_holes(mc)
    lab, n = ndimage.label(filled & ~mc)
    bx0, bx1, by0, by1 = _bbox(mask); area = (bx1 - bx0 + 1) * (by1 - by0 + 1)
    regs = []
    for i in range(1, n + 1):
        r = lab == i; a = int(r.sum())
        if a > 0.015 * area:
            ys, xs = np.nonzero(r); regs.append({"i": i, "area": a, "cx": float(xs.mean()), "cy": float(ys.mean()), "m": r})
    regs.sort(key=lambda r: -r["area"])
    found, notes = {"line_width": round(w, 1)}, []
    head = body = None
    big = regs[:2]
    if len(big) == 2:
        a_, b_ = sorted(big, key=lambda r: r["cy"])
        # head and body: stacked loops (the upper one's centre above the lower one's top half)
        if a_["cy"] < b_["cy"] and abs(a_["cx"] - b_["cx"]) < 0.5 * (bx1 - bx0):
            head, body = a_, b_
        else:
            head = big[0]
    elif len(big) == 1:
        head = big[0]
    if head is None:
        notes.append("no closed loop for a head: draw the head as a closed outline")
    found["shape"] = "head and body" if body else "blob (one loop: all head)" if head else "unknown"

    spec = {"photo": str(photo), "name": name, "template": "doodle", "ink": ink_hex, "rest": "body", "parts": {}, "swaps": {}, "anchors": {}}
    eyes_m = np.zeros_like(mask); mouth_m = None
    if head:
        hf = ndimage.binary_fill_holes(head["m"])           # head interior including the marks drawn in it
        hx0, hx1, hy0, hy1 = _bbox(hf); hh, hw = hy1 - hy0 + 1, hx1 - hx0 + 1
        # marks inside the head: raw ink well inside the head's convex outline (closing gaps can glue a mouth to a
        # neighbouring line, so the closed loop alone would miss it) that is not joined to the outline itself
        from PIL import ImageDraw
        hm = Image.new("L", (W, H), 0); ImageDraw.Draw(hm).polygon([tuple(q) for q in _poly(hf, 0)], fill=255)
        hull = np.asarray(hm) > 0
        inner = ndimage.binary_erosion(hull, iterations=int(math.ceil(w * 1.2)))
        raw_lab, _ = ndimage.label(mask, np.ones((3, 3)))
        outline_ids = set(np.unique(raw_lab[mask & ~inner & ndimage.binary_dilation(hull, iterations=int(w))])) - {0}
        marks = mask & inner & ~np.isin(raw_lab, list(outline_ids))
        fl, fn = ndimage.label(ndimage.binary_fill_holes(ndimage.binary_closing(marks, iterations=1) | marks), np.ones((3, 3)))
        feats = []
        for i in range(1, fn + 1):
            f = fl == i; a = int(f.sum())
            if a < max(6, 0.002 * hf.sum()):
                continue
            x0, x1, y0, y1 = _bbox(f); feats.append({"m": f, "cx": (x0 + x1) / 2, "cy": (y0 + y1) / 2, "w": x1 - x0 + 1, "h": y1 - y0 + 1})
        low = [f for f in feats if f["cy"] > hy0 + 0.58 * hh and f["w"] >= 0.9 * f["h"]]
        mouth = max(low, key=lambda f: (f["cy"], f["w"]), default=None)
        eyes = [f for f in feats if f is not mouth and f["cy"] <= hy0 + 0.7 * hh]
        for f in eyes:
            eyes_m |= f["m"]
        found["eyes"] = len(eyes)
        if eyes:
            spec["swaps"]["eyes"] = {"anchor": "head", "z": 30, "open": {"poly": _poly(ndimage.binary_dilation(eyes_m, iterations=int(w)), w)}, "blink": "squash"}
        else:
            notes.append("no eyes found inside the head (eyes drawn as marks inside the head outline blink)")
        if mouth:
            mouth_m = mouth["m"]; mx0, mx1, my0, my1 = _bbox(mouth_m)
            gen = {"center": [round((mx0 + mx1) / 2), round((my0 + my1) / 2)], "width": int(max(mx1 - mx0 + 1, 0.18 * hw)), "line": round(w, 1)}
            spec["swaps"]["mouth"] = {"anchor": "head", "z": 31, "open": {"poly": _poly(ndimage.binary_dilation(mouth_m, iterations=int(w)), w)}, "talk": gen}
            found["mouth"] = "drawn (talking shapes made to match)"
        elif (mask & inner & ~ndimage.binary_dilation(eyes_m, iterations=int(w) + 1))[int(hy0 + 0.55 * hh):int(hy1), int((hx0 + hx1) / 2 - 0.22 * hw):int((hx0 + hx1) / 2 + 0.22 * hw)].any():
            # a mouth joined to another line (it cannot be cut out): it stays drawn as the closed mouth, and the
            # dark open shapes are drawn over it, centred on the topmost ink in the mouth zone
            zx0, zy0 = int((hx0 + hx1) / 2 - 0.22 * hw), int(hy0 + 0.55 * hh)
            zone = (mask & inner & ~ndimage.binary_dilation(eyes_m, iterations=int(w) + 1))[zy0:int(hy1), zx0:int((hx0 + hx1) / 2 + 0.22 * hw)]
            ys_, xs_ = np.nonzero(zone); top = ys_.min(); band = ys_ < top + 0.07 * hh
            cx_, cy_ = zx0 + xs_[band].mean(), zy0 + top + 0.03 * hh
            gen = {"center": [round(cx_), round(cy_)], "width": int(max(np.ptp(xs_[band]) + 2 * w, 0.18 * hw)), "line": round(w, 1), "keep_drawn": True}
            spec["swaps"]["mouth"] = {"anchor": "head", "z": 31, "talk": gen}
            found["mouth"] = "drawn but joined to another line: talking shapes drawn over it"
            notes.append("the mouth touches another line, so it stays as drawn and the open mouths cover it: check the mouth box")
        else:
            ey = (_bbox(eyes_m)[3] if eyes else hy0 + 0.45 * hh)
            gen = {"center": [round((hx0 + hx1) / 2), round(min(hy1 - 0.12 * hh, ey + 0.25 * hh))], "width": int(0.28 * hw), "line": round(w, 1)}
            spec["swaps"]["mouth"] = {"anchor": "head", "z": 31, "talk": gen}
            found["mouth"] = "none drawn: made one"; notes.append("no mouth found: one was made; draw your own through the drawing requests")
        ring = ndimage.binary_dilation(hf, iterations=int(math.ceil(w * 1.2)))
        spec["parts"]["head"] = {"poly": _poly(ring, w), "pivot": [round((hx0 + hx1) / 2), int(hy1)], "parent": "body", "z": 20, "overlap": int(max(2, w))}
        spec["anchors"]["bubble"] = [round((hx0 + hx1) / 2), int(hy0)]
        found["head"] = {"pivot": spec["parts"]["head"]["pivot"], "why": "the upper closed loop; pivot at its bottom (the neck)"}
    # limbs: strokes outside the head and body loops
    core = ndimage.binary_fill_holes(body["m"]) if body else (ndimage.binary_fill_holes(head["m"]) if head else np.zeros_like(mask))
    owner = "body" if body else "head"
    away = mask & ~ndimage.binary_dilation(core, iterations=int(math.ceil(w * 1.5)))
    if head and body:
        away &= ~ndimage.binary_dilation(ndimage.binary_fill_holes(head["m"]), iterations=int(math.ceil(w * 1.5)))
    if core.any():
        cx0, cx1, cy0, cy1 = _bbox(core); ch, cw = cy1 - cy0 + 1, cx1 - cx0 + 1
        dist_core = ndimage.distance_transform_edt(~core)
        cl, cn = ndimage.label(away, np.ones((3, 3)))
        side = {"L": [], "R": []}; head_extra = []
        for i in range(1, cn + 1):
            c = cl == i; a = int(c.sum())
            if a < max(10, min(0.0015 * area, 6 * w * w)):   # a stroke a few line widths long (not a share of the page: short arms count)
                continue
            ys, xs = np.nonzero(c); x, y = xs.mean(), ys.mean()
            if y > cy1 - 0.05 * ch and ys.max() > cy1:      # below the body: legs and feet stay with the body
                continue
            if y < cy0 + 0.05 * ch:                         # above the body's top: ears, hats, hair go with the head
                if head and body:
                    head_extra.append(c)
                continue
            near = ys.size and float(dist_core[c].min())
            if near > 3 * w + 4:                            # not touching the body: a floating mark
                continue
            s_ = "L" if x < (cx0 + cx1) / 2 else "R"
            k = int(np.argmin(dist_core[c])); side[s_].append({"m": c, "a": a, "y": y, "pivot": [int(xs[k]), int(ys[k])]})
        if head_extra and "head" in spec["parts"]:
            hx = np.zeros_like(mask)
            for c in head_extra:
                hx |= c
            ring = ndimage.binary_dilation(ndimage.binary_fill_holes(head["m"]), iterations=int(math.ceil(w * 1.2))) | ndimage.binary_dilation(hx, iterations=int(w))
            spec["parts"]["head"]["poly"] = _poly(ring, w)
            found["head"]["why"] += f"; with {len(head_extra)} mark(s) above it (ears, hair, a hat)"
        tail = None
        for s_ in "LR":
            cands = sorted(side[s_], key=lambda c: c["y"])
            if not cands:
                continue
            arm = max(cands[:2], key=lambda c: c["a"]) if len(cands) > 1 and cands[0]["y"] > cy0 + 0.6 * ch else cands[0]
            spec["parts"][f"arm_{s_}"] = {"poly": _poly(ndimage.binary_dilation(arm["m"], iterations=int(w)), w), "pivot": arm["pivot"], "parent": owner, "z": 12}
            found[f"arm_{s_}"] = {"pivot": arm["pivot"], "why": f"a stroke leaving the {'left' if s_ == 'L' else 'right'} side of the {owner}"}
            rest_ = [c for c in cands if c is not arm and c["y"] > cy0 + 0.5 * ch]
            if rest_ and tail is None:
                tail = max(rest_, key=lambda c: c["a"])
        if tail:
            spec["parts"]["tail"] = {"poly": _poly(ndimage.binary_dilation(tail["m"], iterations=int(w)), w), "pivot": tail["pivot"], "parent": owner, "z": 8}
            found["tail"] = {"pivot": tail["pivot"], "why": "a second stroke low on one side"}
        for s_ in "LR":
            if f"arm_{s_}" not in spec["parts"]:
                notes.append(f"no {'left' if s_ == 'L' else 'right'} arm found (arms are strokes leaving the body's sides)")
    if not body and head:   # a blob: the head is the whole character; it rests on the ground through the body
        spec["parts"]["head"]["pivot"] = [spec["parts"]["head"]["pivot"][0], int(_bbox(mask)[3])]
    found["notes"] = notes
    spec["found"] = found
    return spec


def synthetic_doodle(kind="nib", seed=3, size=(520, 700)):
    """a phone-photo-like doodle with known cuts (for tests): kind nib (head, body, arms, legs, eyes, mouth),
    blob (one loop with dot eyes, arms, no mouth), cat (head, body, arms, a tail). -> (PIL image, truth)"""
    import random
    from PIL import ImageDraw, ImageFilter
    rng = random.Random(seed); W, H = size
    im = Image.new("RGB", size, (236, 233, 224)); d = ImageDraw.Draw(im)
    pen = lambda pts, w=4: d.line([(x + rng.uniform(-1.2, 1.2), y + rng.uniform(-1.2, 1.2)) for x, y in pts], fill=(28, 30, 36), width=w, joint="curve")
    ell = lambda cx, cy, rx, ry: [(cx + rx * math.cos(2 * math.pi * i / 72), cy + ry * math.sin(2 * math.pi * i / 72)) for i in range(73)]
    truth = {}
    if kind in ("nib", "cat"):
        pen(ell(260, 230, 90, 80)); pen(ell(260, 440, 115, 140))
        for ex in (225, 295):
            pen(ell(ex, 215, 16, 18), 3); d.ellipse([ex - 4, 215, ex + 4, 223], fill=(28, 30, 36))
        pen([(232, 268), (260, 280), (288, 268)], 3)
        pen([(150, 400), (90, 470)]); pen([(370, 400), (430, 470)])
        pen([(225, 578), (220, 650), (200, 652)]); pen([(295, 578), (300, 650), (322, 652)])
        truth = {"shape": "head and body", "head_pivot": [260, 310], "arm_L": [148, 402], "arm_R": [372, 402], "eyes": 2, "mouth": True}
        if kind == "cat":
            pen([(372, 500), (440, 520), (470, 470)]); truth["tail"] = [372, 500]
            pen([(195, 165), (205, 125), (230, 155)]); pen([(290, 155), (315, 125), (325, 165)])
    elif kind == "blob":
        pen(ell(260, 380, 150, 170))
        for ex in (215, 305):
            d.ellipse([ex - 9, 320, ex + 9, 340], fill=(28, 30, 36))
        pen([(112, 380), (50, 330)]); pen([(408, 380), (470, 330)])
        pen([(220, 548), (215, 610)]); pen([(300, 548), (305, 610)])
        truth = {"shape": "blob (one loop: all head)", "arm_L": [112, 380], "arm_R": [408, 380], "eyes": 2, "mouth": False}
    # paper: uneven light, grain
    g = Image.linear_gradient("L").resize(size).point(lambda v: 255 - v // 6)
    im = Image.composite(im, Image.new("RGB", size, (205, 200, 190)), g).filter(ImageFilter.GaussianBlur(0.6))
    arr = np.asarray(im).astype(np.int16) + np.random.default_rng(seed).integers(-6, 7, (H, W, 1))
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)), truth


def self_test(tmp):
    """synthetic doodles must be cut where they were drawn -> (failures, measurements)"""
    fails, got = [], {}
    tmp = Path(tmp); tmp.mkdir(parents=True, exist_ok=True)
    for kind in ("nib", "blob", "cat"):
        im, truth = synthetic_doodle(kind)
        raw = tmp / f"{kind}_raw.png"; im.save(raw)
        prep = tmp / f"{kind}.png"; info = prepare(raw, prep)
        k, (ox, oy) = info["scale"], info["crop"][:2]
        to = lambda p: [(p[0] - ox) * k, (p[1] - oy) * k]
        sp = suggest(str(prep)); f = sp["found"]; P = sp["parts"]
        err = {}
        if f["shape"] != truth["shape"]:
            fails.append(f"{kind}: shape {f['shape']!r}, want {truth['shape']!r}")
        for part, key in (("head", "head_pivot"), ("arm_L", "arm_L"), ("arm_R", "arm_R"), ("tail", "tail")):
            if key not in truth:
                if part == "tail" and "tail" in P:
                    fails.append(f"{kind}: found a tail that is not there")
                continue
            if part not in P:
                fails.append(f"{kind}: no {part}"); continue
            e = math.dist(P[part]["pivot"], to(truth[key])) / k; err[part] = round(e, 1)
            if e > 22:
                fails.append(f"{kind}: {part} pivot {e:.0f} px from where it was drawn")
        if f.get("eyes") != truth["eyes"]:
            fails.append(f"{kind}: {f.get('eyes')} eyes, want {truth['eyes']}")
        if truth["mouth"] != f.get("mouth", "").startswith("drawn ("):
            fails.append(f"{kind}: mouth {f.get('mouth')}")
        if kind == "cat":   # the ears ride with the head
            from PIL import ImageDraw
            hm = Image.new("L", Image.open(prep).size, 0); ImageDraw.Draw(hm).polygon([tuple(q) for q in P["head"]["poly"]], fill=255)
            ears = [to(q) for q in ((205, 125), (315, 125))]
            if not all(np.asarray(hm)[int(y), int(x)] for x, y in ears):
                fails.append("cat: the ears are not cut with the head")
        got[kind] = {"pivot_error_px": err, "eyes": f.get("eyes"), "mouth": f.get("mouth"), "shape": f["shape"]}
    return fails, got


if __name__ == "__main__":
    import sys
    sp = suggest(sys.argv[1]); print(json.dumps(sp["found"], indent=1))
