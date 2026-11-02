"""Drawing coach (plan 1.10): checks a puppet (or a layered drawing before import) and gives specific, visual advice.

    python dbe/coach.py SOURCE OUT.png [OPTIONS_JSON]       SOURCE: .puppet.json, .svg, .psd or .ora

Checks, each with a measured value and what to do:
- template completeness: required parts and swap shapes (blink, lip-sync, look);
- joints that will open a gap: each joint is bent +-50 degrees and the hole that appears next to it is measured;
- pivots outside their own drawing;
- limb proportions (upper vs lower limb) and left/right mismatch;
- face: eyes as their own layer (to blink), pupils (to look), closed and open mouths (to lip-sync);
- scale: character height on the artboard, feet on the ground line;
- layers the importer could not place (with name suggestions).
Writes OUT.png: the drawing with every problem circled and numbered, and returns the list as JSON.
"""
import base64
import io
import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dbe import geom as G  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
K = 1.0  # mask pixels per artboard unit


def part_mask(puppet, strokes, size, M=None):
    W, H = size
    im = Image.new("L", (W, H), 0); dr = ImageDraw.Draw(im)
    M = M or G.I
    for st in strokes:
        if st.get("image"):
            src = Image.open(io.BytesIO(base64.b64decode(st["image"].split(",", 1)[1]))).convert("RGBA").getchannel("A")
            src = src.resize((max(1, int(st["w"] * K)), max(1, int(st["h"] * K))))
            if M == G.I:
                im.paste(255, (int(st["x"] * K), int(st["y"] * K)), src.point(lambda v: 255 if v > 100 else 0))
            else:  # rotate the image about the matrix: use PIL affine on the full canvas
                full = Image.new("L", (W, H), 0); full.paste(src.point(lambda v: 255 if v > 100 else 0), (int(st["x"] * K), int(st["y"] * K)))
                a, b, c, d, e, f = M; det = a * d - b * c
                inv = [d / det, -c / det, (c * f - d * e) / det, -b / det, a / det, (b * e - a * f) / det]
                full = full.transform((W, H), Image.AFFINE, (inv[0], inv[1], inv[2], inv[3], inv[4], inv[5]), resample=Image.NEAREST)
                im = Image.fromarray(np.maximum(np.asarray(im), np.asarray(full)))
                dr = ImageDraw.Draw(im)
            continue
        if st.get("mesh"):  # skinned mesh at rest: its triangles
            mm = st["mesh"]
            for tri in mm["tris"]:
                dr.polygon([tuple(v * K for v in G.apply(M, mm["verts"][i])) for i in tri], fill=255)
            continue
        if not st.get("d"):
            continue
        for segs, closed in G.parse_path(st["d"]):
            pts = [G.apply(M, p) for p in G.sample(segs, 6)]
            pts = [(x * K, y * K) for x, y in pts]
            if len(pts) < 2:
                continue
            if st.get("fill", "none") != "none" and len(pts) > 2:
                dr.polygon(pts, fill=255)
            if st.get("stroke", "none") != "none":
                dr.line(pts + ([pts[0]] if closed else []), fill=255, width=max(1, int(st.get("width", 3) * K)))
    return np.asarray(im) > 0


def coach(pz, report=None):
    T = json.loads((ROOT / "puppet" / "templates" / f"{pz['template']}.json").read_text())
    W, H = int(math.ceil(pz["artboard"][0] * K)), int(math.ceil(pz["artboard"][1] * K))
    parts, swaps = pz["parts"], pz.get("swaps", {})
    issues = []
    add = lambda level, what, msg, at=None, value=None: issues.append({"level": level, "check": what, "msg": msg, **({"at": [round(v, 1) for v in at]} if at else {}), **({"value": value} if value is not None else {})})
    masks = {k: part_mask(pz, v.get("strokes", []), (W, H)) for k, v in parts.items()}
    # 1. completeness
    for tp in T["parts"]:
        if tp.get("required") and (tp["id"] not in parts or (not parts[tp["id"]].get("strokes") and not any(st.get("mesh") for v in parts.values() for st in v.get("strokes", [])))):
            add("error", "missing part", f"{tp.get('label', tp['id'])} is not drawn: add a layer named `{tp['id']}`")
    # 2. face abilities
    if "eyes" not in swaps:
        add("warn", "blink", "eyes are part of the head drawing, so the character cannot blink: put the eyes on their own layer `eyes/open` (and `eyes/closed` if you like)")
    if "pupils" not in swaps and pz["template"] == "humanoid":
        add("warn", "look", "no `pupils` layer: the eyes cannot look around; draw the pupils on their own layer")
    m = swaps.get("mouth", {}).get("shapes", {})
    if not m:
        add("warn", "lip-sync", "no mouth shapes: draw at least `mouth/closed` and `mouth/wide` so the character can talk")
    elif not ({"closed"} <= set(m) and len(set(m) & {"small", "mid", "wide", "O"}) >= 1):
        add("warn", "lip-sync", f"mouth has {sorted(m)}: add `closed` plus at least one open shape (`small`, `mid`, `wide`)")
    # 3. pivots and joint gaps: bend each joint and measure the hole beside it
    for pid, part in parts.items():
        par = part.get("parent")
        if not par or par not in parts or pid.endswith(tuple(f"__{i}" for i in range(20))):
            continue
        cm, pm = masks.get(pid), masks.get(par)
        if cm is None or not cm.any() or pm is None or not pm.any():
            continue
        px, py = part["pivot"]
        if not cm[min(H - 1, max(0, int(py * K))), min(W - 1, max(0, int(px * K)))] and not pm[min(H - 1, max(0, int(py * K))), min(W - 1, max(0, int(px * K)))]:
            add("warn", "pivot", f"{pid}'s joint sits outside both {pid} and {par}: move the joint (or a `pivot:{pid}` dot) onto the overlap", at=(px, py))
        ov = (cm & pm).sum()
        if ov < 0.02 * min(cm.sum(), pm.sum()):  # not even touching at rest
            pa, pb = np.argwhere(cm)[::7], np.argwhere(pm)[::7]
            dmin = float(np.sqrt(((pa[:, None, :] - pb[None, :, :]) ** 2).sum(-1).min())) / K if len(pa) and len(pb) else 0
            add("error", "joint gap", f"{pid} does not overlap {par}" + (f" (a {dmin:.0f}-unit gap)" if dmin > 1 else "") +
                f": extend {pid} past the joint so the two drawings overlap by about half the limb's width", at=(px, py), value=round(dmin, 1))
            continue
        r = int(max(12, 0.6 * math.sqrt(cm.sum() / math.pi)) * K)
        yy, xx = np.ogrid[:H, :W]; disk = (xx - px * K) ** 2 + (yy - py * K) ** 2 <= r * r
        rest = (cm | pm) & disk
        worst = 0.0
        for ang in (-50, 50):
            Mr = G.rot_about(ang, (px, py))
            bent = part_mask(pz, part.get("strokes", []), (W, H), Mr) | pm
            hole = rest.sum() and float(((rest & ~bent).sum()) / max(1, rest.sum()))
            worst = max(worst, hole)
        if worst > 0.12:
            add("warn" if worst < 0.3 else "error", "joint gap", f"bending {pid} opens a gap at the joint ({worst:.0%} of the joint area shows through): draw {pid} further past the joint, with a rounded end centred on it", at=(px, py), value=round(worst, 2))
    # 4. proportions and symmetry
    def length(a, b):
        if a in parts and b in parts:
            return math.dist(parts[a]["pivot"], parts[b]["pivot"])
    for up, lo, end in (("upperarm", "forearm", "hand"), ("thigh", "shin", "foot")):
        for side in ("L", "R"):
            a, b = length(f"{up}_{side}", f"{lo}_{side}"), length(f"{lo}_{side}", f"{end}_{side}")
            if a and b and not (0.55 <= a / b <= 1.8):
                add("warn", "proportions", f"{up}_{side} is {a / b:.1f}x {lo}_{side}: limbs bend oddly when the two segments differ this much (aim for 0.7-1.4x)", at=parts[f"{lo}_{side}"]["pivot"], value=round(a / b, 2))
        for seg in (f"{up}", f"{lo}"):
            nxt = {"upperarm": "forearm", "forearm": "hand", "thigh": "shin", "shin": "foot"}[seg]
            l, r_ = length(f"{seg}_L", f"{nxt}_L"), length(f"{seg}_R", f"{nxt}_R")
            if l and r_ and abs(l - r_) / max(l, r_) > 0.25:
                add("warn", "symmetry", f"{seg}_L and {seg}_R differ by {abs(l - r_) / max(l, r_):.0%}: walks and waves will look lopsided", at=parts[f"{seg}_L"]["pivot"], value=round(abs(l - r_) / max(l, r_), 2))
    # 5. scale and ground
    allm = np.zeros((H, W), bool)
    for v in masks.values():
        allm |= v
    if allm.any():
        ys, xs = np.nonzero(allm)
        h = (ys.max() - ys.min()) / K
        if h < 0.5 * pz["artboard"][1]:
            add("warn", "scale", f"the character fills only {h / pz['artboard'][1]:.0%} of the artboard height: draw bigger (detail is lost when it is scaled up)", value=round(h / pz["artboard"][1], 2))
        gap = pz.get("ground", ys.max() / K) - ys.max() / K
        if abs(gap) > 0.04 * pz["artboard"][1]:
            add("warn", "ground", f"the feet are {gap:.0f} units {'above' if gap > 0 else 'below'} the ground line: the character will float or sink", at=(xs.mean() / K, ys.max() / K), value=round(gap, 1))
    # 6. importer notes
    for u in (report or {}).get("unmatched", []):
        add("warn", "layer name", f"layer `{u['layer']}` was not used" + (f": did you mean `{'` or `'.join(u['suggest'])}`?" if u.get("suggest") else ": name it after a part or a swap shape"))
    order = {"error": 0, "warn": 1}
    issues.sort(key=lambda i: order[i["level"]])
    return issues, masks, allm


def annotate(pz, issues, allm, out):
    W, H = allm.shape[1], allm.shape[0]
    base = Image.new("RGB", (W, H), (250, 249, 244))
    ink = Image.fromarray((allm * 255).astype(np.uint8))
    base.paste((185, 190, 198), (0, 0), ink)
    dr = ImageDraw.Draw(base)
    try:
        font = ImageFont.truetype(str(ROOT / "engine" / "fonts" / "Fredoka.ttf"), max(14, W // 30))
    except Exception:
        font = ImageFont.load_default()
    n = 0
    for i in issues:
        if not i.get("at"):
            continue
        n += 1; x, y = i["at"][0] * K, i["at"][1] * K; r = max(14, W // 28)
        col = (210, 50, 40) if i["level"] == "error" else (230, 140, 20)
        dr.ellipse([x - r, y - r, x + r, y + r], outline=col, width=4)
        dr.text((x + r + 4, y - r), str(n), fill=col, font=font)
        i["marker"] = n
    base.save(out)


def run(source, out, opts=None):
    src = Path(source); report = None
    if src.suffix == ".json":
        pz = json.loads(src.read_text())
    else:
        from dbe import drawing_import as D
        pz, report = D.build(str(src), opts or {})
    issues, masks, allm = coach(pz, report)
    annotate(pz, issues, allm, out)
    return {"puppet": pz.get("name"), "template": pz["template"], "errors": sum(i["level"] == "error" for i in issues),
            "warnings": sum(i["level"] == "warn" for i in issues), "issues": issues, "image": str(out)}


if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1], sys.argv[2], json.loads(sys.argv[3]) if len(sys.argv) > 3 else {})))
