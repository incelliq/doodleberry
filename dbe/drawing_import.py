"""Drawing import (plan 1.3): a layered drawing becomes a puppet, by layer name.

    python dbe/drawing_import.py SOURCE OUT.puppet.json [OPTIONS_JSON]

Sources:
- SVG (Inkscape layers or plain groups): vector parts. Transforms, styles, gradients (first stop), <use> and the basic
  shapes are flattened into path data in artboard units.
- PSD (psd-tools, MIT; run with DBE_PY) and OpenRaster .ora (what Krita, GIMP and MyPaint export): raster parts.

Layer names (case, spaces and punctuation ignored):
- a template part: `head`, `upperarm_R`, `Upper arm R`, `upper arm right`, `lower leg left`, `hips`;
- a swap shape: `mouth/closed` (or `mouth.closed`, `mouth:closed`), or a group `mouth` holding layers `closed`, `wide`...;
- `pivot:<part>`: a small dot whose centre is that part's joint; `anchor:<name>`: a named point (e.g. `anchor:bubble`);
- `ground`: a line or shape whose bottom is the floor;
- `guide`, `sketch`, `ref`, `background`... and hidden layers are skipped.

Missing pivots are estimated from the drawing: a part that shares its parent's joint in the template takes the parent's
pivot; otherwise the centre of the overlap between the part and its parent (artists draw past the joint), else the
midpoint of their closest points (reported, because the joint will open a gap when it bends).

OPTIONS: {"template": "humanoid" | "doodle" (default: guessed), "name": "...", "z": "document" | "template",
          "author": "...", "license": "...", "source_url": "..."}
"""
import base64
import difflib
import io
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dbe import geom as G  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SKIP = {"guide", "guides", "sketch", "sketches", "ref", "refs", "reference", "references", "background", "bg", "notes", "paper"}
ALIASES = [("lowerarm", "forearm"), ("upperleg", "thigh"), ("lowerleg", "shin"), ("calf", "shin"), ("hips", "hip"),
           ("pelvis", "hip"), ("chest", "torso"), ("left", "l"), ("right", "r")]
DOODLE_PARENTS = {"hip": None, "body": "hip", "head": "body", "arm_L": "body", "arm_R": "body", "tail": "body"}
HINT = [("hair", "hair"), ("head", "skin"), ("neck", "skin"), ("hand", "skin"), ("forearm", "skin"), ("torso", "cloth1"),
        ("upperarm", "cloth1"), ("hip", "cloth2"), ("thigh", "cloth2"), ("shin", "cloth2"), ("foot", "shoe"),
        ("eyes", "eye"), ("brows", "hair"), ("body", "body")]
AUTO_ID = re.compile(r"^(path|g|layer|rect|circle|ellipse|use|text|tspan|polygon|polyline|line|svg|image)[-_]?\d+$", re.I)
NAMED = {"black": "#000000", "white": "#ffffff", "red": "#ff0000", "green": "#008000", "blue": "#0000ff",
         "gray": "#808080", "grey": "#808080", "yellow": "#ffff00", "orange": "#ffa500", "brown": "#a52a2a", "pink": "#ffc0cb"}


def norm(s):
    s = re.sub(r"[^a-z0-9]", "", str(s).lower())
    for a, b in ALIASES:
        s = s.replace(a, b) if a not in ("left", "right") else (s[:-len(a)] + b if s.endswith(a) else s)
    return s


# ---------------- template ----------------
def load_template(name):
    T = json.loads((ROOT / "puppet" / "templates" / f"{name}.json").read_text())
    parts = [{**p, "parent": p["parent"] if "parent" in p else DOODLE_PARENTS.get(p["id"])} for p in T["parts"]]
    T["parts"] = parts
    return T


def classify(names, T):
    """layer path (outermost first) -> ('part', id) | ('swap', sid, shape) | ('pivot', id) | ('anchor', name) |
    ('ground',) | ('skip',) | ('unmatched', name)"""
    pids = {norm(p["id"]): p["id"] for p in T["parts"]}
    sids = {norm(s["id"]): s for s in T.get("swaps", [])}
    for nm in reversed(names):
        m = re.match(r"^\s*(pivot|anchor)\s*[:._ /-]\s*(.+)$", nm, re.I)
        if m:
            kind, what = m.group(1).lower(), m.group(2).strip()
            if kind == "pivot":
                return ("pivot", pids.get(norm(what), what))
            return ("anchor", re.sub(r"\W+", "_", what.lower()))
        if norm(nm) == "ground":
            return ("ground",)
        if norm(nm) in SKIP:
            return ("skip",)
    for i in range(len(names) - 1, -1, -1):
        nm = names[i]
        bits = re.split(r"\s*[/:.]\s*", nm.strip())
        if len(bits) == 2 and norm(bits[0]) in sids:
            return ("swap", sids[norm(bits[0])]["id"], shape_name(sids[norm(bits[0])], bits[1]))
        if norm(nm) in sids and i < len(names) - 1:
            return ("swap", sids[norm(nm)]["id"], shape_name(sids[norm(nm)], names[i + 1]))
        if norm(nm) in pids:
            return ("part", pids[norm(nm)])
    return ("unmatched", names[-1] if names else "(unnamed)")


def shape_name(sw, given):
    known = {norm(k): k for k in sw.get("shapes", [])}
    return known.get(norm(given), re.sub(r"\W+", "_", given.strip().lower()))


def guess_template(names_list):
    flat = {norm(n) for names in names_list for n in names}
    return "humanoid" if flat & {"upperarmr", "upperarml", "thighl", "thighr", "torso", "forearmr"} else "doodle"


# ---------------- SVG ----------------
def parse_transform(s):
    M = G.I[:]
    for name, args in re.findall(r"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)", s or ""):
        a = [float(v) for v in re.findall(r"-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", args)]
        if name == "matrix":
            T = a[:6]
        elif name == "translate":
            T = [1, 0, 0, 1, a[0], a[1] if len(a) > 1 else 0]
        elif name == "scale":
            T = [a[0], 0, 0, a[1] if len(a) > 1 else a[0], 0, 0]
        elif name == "rotate":
            c, s_ = math.cos(math.radians(a[0])), math.sin(math.radians(a[0]))
            R = [c, s_, -s_, c, 0, 0]
            T = G.mul(G.mul([1, 0, 0, 1, a[1], a[2]], R), [1, 0, 0, 1, -a[1], -a[2]]) if len(a) == 3 else R
        elif name == "skewX":
            T = [1, 0, math.tan(math.radians(a[0])), 1, 0, 0]
        else:
            T = [1, math.tan(math.radians(a[0])), 0, 1, 0, 0]
        M = G.mul(M, T)
    return M


def colour(v, ids):
    if v is None:
        return None
    v = v.strip()
    if v in ("none", "transparent", ""):
        return "none"
    m = re.match(r"url\(\s*#([^)]+)\)", v)
    if m:
        g = ids.get(m.group(1))
        while g is not None and not list(g) and g.get("{http://www.w3.org/1999/xlink}href", g.get("href")):
            g = ids.get(g.get("{http://www.w3.org/1999/xlink}href", g.get("href"))[1:])
        stops = [s for s in (g if g is not None else []) if s.tag.endswith("stop")]
        if not stops:
            return "#808080"
        st = style_of(stops[0], {})
        return colour(st.get("stop-color", "#808080"), ids)
    if v.startswith("#"):
        h = v[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return "#" + h[:6].lower()
    m = re.match(r"rgba?\(([^)]*)\)", v)
    if m:
        ch = [c.strip() for c in m.group(1).split(",")][:3]
        vals = [round(float(c[:-1]) * 2.55) if c.endswith("%") else int(float(c)) for c in ch]
        return "#" + "".join(f"{max(0, min(255, c)):02x}" for c in vals)
    return NAMED.get(v.lower(), "#000000" if v == "currentColor" else None)


def style_of(el, inherited):
    st = dict(inherited); st.pop("opacity", None)
    own = {}
    for k in ("fill", "stroke", "stroke-width", "opacity", "fill-opacity", "stroke-opacity", "display", "visibility", "stop-color", "fill-rule"):
        if el.get(k) is not None:
            own[k] = el.get(k)
    for decl in (el.get("style") or "").split(";"):
        if ":" in decl:
            k, v = decl.split(":", 1)
            own[k.strip()] = v.strip()
    st.update(own)
    st["opacity"] = str(float(inherited.get("opacity", 1)) * float(own.get("opacity", 1)))  # group opacity multiplies down
    return st


def shape_d(el, tag):
    g = lambda k, d=0.0: float(re.sub(r"[a-z%]+$", "", el.get(k, str(d))) or d)
    if tag == "path":
        return el.get("d")
    if tag == "rect":
        x, y, w, h = g("x"), g("y"), g("width"), g("height")
        rx = g("rx", -1); ry = g("ry", -1)
        rx = ry if rx < 0 else rx; ry = rx if ry < 0 else ry
        rx, ry = max(0, min(rx, w / 2)), max(0, min(ry, h / 2))
        if rx == 0:
            return f"M{x} {y} H{x + w} V{y + h} H{x} Z"
        return (f"M{x + rx} {y} H{x + w - rx} A{rx} {ry} 0 0 1 {x + w} {y + ry} V{y + h - ry} A{rx} {ry} 0 0 1 {x + w - rx} {y + h} "
                f"H{x + rx} A{rx} {ry} 0 0 1 {x} {y + h - ry} V{y + ry} A{rx} {ry} 0 0 1 {x + rx} {y} Z")
    if tag in ("circle", "ellipse"):
        cx, cy = g("cx"), g("cy")
        rx = g("r") if tag == "circle" else g("rx"); ry = g("r") if tag == "circle" else g("ry")
        return f"M{cx - rx} {cy} A{rx} {ry} 0 1 0 {cx + rx} {cy} A{rx} {ry} 0 1 0 {cx - rx} {cy} Z"
    if tag == "line":
        return f"M{g('x1')} {g('y1')} L{g('x2')} {g('y2')}"
    if tag in ("polyline", "polygon"):
        pts = re.findall(r"-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", el.get("points", ""))
        if len(pts) < 4:
            return None
        xy = [f"{pts[i]} {pts[i + 1]}" for i in range(0, len(pts) - 1, 2)]
        return "M" + " L".join(xy) + (" Z" if tag == "polygon" else "")
    return None


def fmt(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def transform_d(d, M):
    out = []
    for segs, closed in G.parse_path(d):
        if not segs:
            continue
        p = G.apply(M, segs[0][0]); s = f"M{fmt(p[0])} {fmt(p[1])}"
        for (p0, c1, c2, p1) in segs:
            if c1 == p0 and c2 == p1:
                q = G.apply(M, p1); s += f" L{fmt(q[0])} {fmt(q[1])}"
            else:
                a, b, q = G.apply(M, c1), G.apply(M, c2), G.apply(M, p1)
                s += f" C{fmt(a[0])} {fmt(a[1])} {fmt(b[0])} {fmt(b[1])} {fmt(q[0])} {fmt(q[1])}"
        out.append(s + (" Z" if closed else ""))
    return " ".join(out)


def read_svg(path):
    tree = ET.parse(path); root = tree.getroot()
    ids = {el.get("id"): el for el in root.iter() if el.get("id")}
    vb = [float(v) for v in re.split(r"[\s,]+", root.get("viewBox", "").strip())] if root.get("viewBox") else None
    num = lambda s: float(re.sub(r"[a-z%]+$", "", s)) if s else None
    if vb:
        W, H = vb[2], vb[3]; M0 = [1, 0, 0, 1, -vb[0], -vb[1]]
    else:
        W, H = num(root.get("width")) or 600, num(root.get("height")) or 1000; M0 = G.I[:]
    items, hidden = [], []
    LABEL = "{http://www.inkscape.org/namespaces/inkscape}label"
    SKIP_TAGS = {"defs", "metadata", "title", "desc", "clipPath", "mask", "symbol", "style", "script", "pattern",
                 "linearGradient", "radialGradient", "namedview", "filter", "marker"}

    def walk(el, M, st, names, hid, order):
        tag = el.tag.split("}")[-1]
        if tag in SKIP_TAGS:
            return
        label = el.get(LABEL) or (el.get("id") if el.get("id") and not AUTO_ID.match(el.get("id")) else None)
        M2 = G.mul(M, parse_transform(el.get("transform")))
        st2 = style_of(el, st)
        h2 = hid or st2.get("display") == "none" or st2.get("visibility") == "hidden"
        names2 = names + [label] if label and el is not root else names
        if tag in ("g", "a", "svg", "switch"):
            for ch in el:
                walk(ch, M2, st2, names2, h2, order)
            return
        if tag == "use":
            ref = el.get("{http://www.w3.org/1999/xlink}href") or el.get("href")
            if ref and ref[1:] in ids:
                x, y = float(el.get("x", 0)), float(el.get("y", 0))
                walk(ids[ref[1:]], G.mul(M2, [1, 0, 0, 1, x, y]), st2, names2, h2, order)
            return
        d = shape_d(el, tag)
        if not d:
            return
        rec = {"names": names2, "d": transform_d(d, M2), "style": st2, "scale": math.sqrt(abs(M2[0] * M2[3] - M2[1] * M2[2])),
               "order": len(order), "tag": tag, "slot": el.get("data-slot")}
        order.append(1)
        (hidden if h2 else items).append(rec)

    walk(root, M0, {"fill": "#000000"}, [], False, [])
    return {"kind": "vector", "size": [W, H], "items": items, "hidden": hidden, "ids": ids}


# ---------------- raster: OpenRaster and PSD ----------------
def read_ora(path):
    z = zipfile.ZipFile(path)
    st = ET.fromstring(z.read("stack.xml"))
    W, H = int(st.get("w")), int(st.get("h"))
    items, hidden = [], []

    def walk(el, names, hid):
        for ch in el:  # stack.xml lists the top layer first
            nm = ch.get("name") or ""
            h2 = hid or ch.get("visibility") == "hidden"
            if ch.tag == "stack":
                walk(ch, names + ([nm] if nm else []), h2)
            elif ch.tag == "layer":
                im = Image.open(io.BytesIO(z.read(ch.get("src")))).convert("RGBA")
                op = float(ch.get("opacity", 1))
                allr.append({"names": names + [nm], "image": im, "x": int(float(ch.get("x", 0))), "y": int(float(ch.get("y", 0))), "opacity": op, "hid": h2})
    allr = []
    walk(st.find("stack"), [], False)
    allr.reverse()  # painter order: bottom first
    for i, r in enumerate(allr):
        r["order"] = i
    items = [r for r in allr if not r["hid"]]; hidden = [r for r in allr if r["hid"]]
    return {"kind": "raster", "size": [W, H], "items": items, "hidden": hidden}


def read_psd(path):
    from psd_tools import PSDImage
    psd = PSDImage.open(path)
    items, hidden = [], []

    def walk(group, names, hid):
        for layer in group:  # psd-tools lists bottom first
            h2 = hid or not layer.visible
            if layer.is_group():
                walk(layer, names + [layer.name], h2)
            else:
                im = layer.topil()
                if im is None:
                    continue
                allr.append({"names": names + [layer.name], "image": im.convert("RGBA"), "x": layer.left, "y": layer.top, "opacity": layer.opacity / 255, "hid": h2})
    allr = []
    walk(psd, [], False)
    for i, r in enumerate(allr):
        r["order"] = i
    items = [r for r in allr if not r["hid"]]; hidden = [r for r in allr if r["hid"]]
    return {"kind": "raster", "size": [psd.width, psd.height], "items": items, "hidden": hidden}


def read_source(path):
    ext = Path(path).suffix.lower()
    if ext == ".svg":
        return read_svg(path)
    if ext == ".ora":
        return read_ora(path)
    if ext in (".psd", ".psb"):
        return read_psd(path)
    if ext == ".kra":
        raise ValueError("Krita .kra: export as OpenRaster (.ora) or PSD from Krita (File > Export), keeping the layers")
    raise ValueError(f"unsupported drawing format {ext} (use .svg, .ora or .psd)")


# ---------------- masks and pivots ----------------
MS = 0.5  # mask resolution (pixels per artboard unit)


def mask_of(recs, src):
    W, H = src["size"]
    im = Image.new("L", (max(1, int(W * MS)), max(1, int(H * MS))), 0); dr = ImageDraw.Draw(im)
    for r in recs:
        if src["kind"] == "raster":
            a = r["image"].getchannel("A").point(lambda v: 255 if v > 110 else 0)
            w, h = a.size
            a = a.resize((max(1, int(w * MS)), max(1, int(h * MS))))
            im.paste(255, (int(r["x"] * MS), int(r["y"] * MS)), a)
            continue
        fill = colour(r["style"].get("fill"), src["ids"]); stroke = colour(r["style"].get("stroke"), src["ids"])
        sw = float(re.sub(r"[a-z]+$", "", str(r["style"].get("stroke-width", 1))) or 1) * r["scale"]
        for segs, closed in G.parse_path(r["d"]):
            pts = [(x * MS, y * MS) for x, y in G.sample(segs, 6)]
            if len(pts) < 2:
                continue
            if fill not in (None, "none") and len(pts) > 2:
                dr.polygon(pts, fill=255)
            if stroke not in (None, "none"):
                dr.line(pts + ([pts[0]] if closed else []), fill=255, width=max(1, int(sw * MS)))
    return np.array(im) > 0


def centroid(m):
    ys, xs = np.nonzero(m)
    return [round(float(xs.mean()) / MS, 1), round(float(ys.mean()) / MS, 1)]


def nearest(a, b):
    pa = np.argwhere(a); pb = np.argwhere(b)
    if not len(pa) or not len(pb):
        return None
    pa = pa[:: max(1, len(pa) // 1500)]; pb = pb[:: max(1, len(pb) // 1500)]
    d = ((pa[:, None, :] - pb[None, :, :]) ** 2).sum(-1)
    i, j = np.unravel_index(int(d.argmin()), d.shape)
    y, x = (pa[i] + pb[j]) / 2
    return [round(float(x) / MS, 1), round(float(y) / MS, 1)]


def _axis(m):
    """principal axis of a mask: (mean xy, unit vector, projections, perpendiculars, elongation, points xy)"""
    pts = np.argwhere(m)[:, ::-1].astype(float)
    if len(pts) < 8:
        return None
    pts = pts[:: max(1, len(pts) // 6000)]
    mu = pts.mean(0); C = np.cov((pts - mu).T)
    w, V = np.linalg.eigh(C)
    v = V[:, 1]; n = np.array([-v[1], v[0]])
    return mu, v, (pts - mu) @ v, (pts - mu) @ n, float(np.sqrt(max(w[1], 1e-9) / max(w[0], 1e-9))), n


def _cap_centre(m, toward):
    """centre of the rounded cap at the end of an elongated mask nearest `toward` (pixels)"""
    a = _axis(m)
    if a is None:
        return None, 0
    mu, v, pr, pe, el, n = a
    ends = [(pr.max(), 1), (pr.min(), -1)]
    t, sgn = min(ends, key=lambda e: np.hypot(*(mu + v * e[0] - toward)))
    near = np.abs(pr - t) < max(3.0, 0.18 * (pr.max() - pr.min()))
    r = (pe[near].max() - pe[near].min()) / 2 if near.sum() > 2 else 0
    r = min(r, 0.45 * (pr.max() - pr.min()))
    c = mu + v * (t - sgn * r) + n * ((pe[near].max() + pe[near].min()) / 2 if near.sum() > 2 else 0)
    return c, el


def joint(child, parent):
    """joint between two overlapping masks: the cap centre at the near end of whichever is limb-shaped, checked
    against the overlap; else the overlap's centre"""
    ov = child & parent
    oc = np.argwhere(ov)[:, ::-1].mean(0)
    cands = []
    for m, other_c in ((child, oc), (parent, oc)):
        c, el = _cap_centre(m, other_c)
        if c is not None and el > 1.6:
            cands.append((el, c))
    for el, c in sorted(cands, key=lambda t: -t[0]):
        x, y = int(round(c[0])), int(round(c[1]))
        if 0 <= y < ov.shape[0] and 0 <= x < ov.shape[1] and (child[y, x] or parent[y, x]):
            return [round(float(c[0]) / MS, 1), round(float(c[1]) / MS, 1)], "cap"
    return [round(float(oc[0]) / MS, 1), round(float(oc[1]) / MS, 1)], "overlap"


# ---------------- palette ----------------
def build_palette(src, by_target, T):
    """vector: give every colour a named slot, using the part each colour mostly paints as a hint"""
    slots_order = T.get("palette") or []
    weight = {}  # colour -> {hint: weight}
    stroke_count = {}
    forced, forced_slots = {}, set()
    for (kind, *key), recs in by_target.items():
        pid = key[0]
        hint = next((h for k, h in HINT if k in pid.lower()), None)
        for r in recs:
            f = colour(r["style"].get("fill"), src["ids"]); s = colour(r["style"].get("stroke"), src["ids"])
            if r.get("slot"):
                forced_slots.add(r["slot"])
                if f not in (None, "none"):
                    forced[f] = r["slot"]
            if f not in (None, "none"):
                xs = [float(v) for v in re.findall(r"-?\d+\.?\d*", r["d"])]
                area = (max(xs[0::2]) - min(xs[0::2])) * (max(xs[1::2]) - min(xs[1::2])) if len(xs) >= 4 else 1
                weight.setdefault(f, {}); weight[f][hint] = weight[f].get(hint, 0) + max(1, area)
            if s not in (None, "none"):
                stroke_count[s] = stroke_count.get(s, 0) + 1
    pal, used = {}, set(forced_slots)
    ink = max(stroke_count, key=stroke_count.get) if stroke_count else None
    if ink:
        pal[ink] = "ink"; used.add("ink")
    for c, slot in forced.items():
        if c not in pal:
            pal[c] = slot
        used.add(slot)
    claims = sorted(((w, c, h) for c, hs in weight.items() for h, w in hs.items() if h and c not in pal), reverse=True)
    for w, c, h in claims:
        if c in pal or h in used:
            continue
        pal[c] = h; used.add(h)
    spare = [s for s in slots_order if s not in used]; n = 1
    for c in list(weight) + list(stroke_count):
        if c in pal:
            continue
        if spare:
            pal[c] = spare.pop(0)
        else:
            while f"c{n}" in used:
                n += 1
            pal[c] = f"c{n}"
        used.add(pal[c])
    return pal


# ---------------- build ----------------
def build(source, opts=None):
    opts = opts or {}
    src = read_source(source)
    for i, h in enumerate(src["hidden"]):
        h.setdefault("order", len(src["items"]) + i)
    tname = opts.get("template") or guess_template([r["names"] for r in src["items"]])
    T = load_template(tname)
    tparts = {p["id"]: p for p in T["parts"]}
    tswaps = {s["id"]: s for s in T.get("swaps", [])}
    by_target, markers, report = {}, {"pivot": {}, "anchor": {}}, {"layers": {}, "unmatched": [], "skipped": [], "hidden": len(src["hidden"])}
    ground_recs = []
    for r in src["items"] + [dict(h, hidden=True) for h in src["hidden"]]:
        c = classify(r["names"], T)
        label = "/".join(r["names"]) or "(unnamed)"
        if r.get("hidden") and c[0] != "swap":  # hidden layers are skipped, except swap shapes (artists hide all but one)
            continue
        if c[0] in ("part", "swap"):
            by_target.setdefault(c, []).append(r); report["layers"][label] = ":".join(c[1:]) if c[0] == "swap" else c[1]
        elif c[0] in ("pivot", "anchor"):
            markers[c[0]][c[1]] = r
        elif c[0] == "ground":
            ground_recs.append(r)
        elif c[0] == "skip":
            report["skipped"].append(label)
        else:
            cands = [p["id"] for p in T["parts"]] + [f"{s}/{k}" for s, sw in tswaps.items() for k in sw.get("shapes", [])]
            sug = difflib.get_close_matches(c[1], cands, n=2, cutoff=0.5)
            if label not in [u["layer"] for u in report["unmatched"]]:
                report["unmatched"].append({"layer": label, "suggest": sug})
    if not by_target:
        raise ValueError(f"no layer names matched the {tname} template; name layers after parts (head, torso, upperarm_R...) ")

    W, H = src["size"]
    masks = {k: mask_of(v, src) for k, v in by_target.items()}
    mark_xy = {}
    for kind in ("pivot", "anchor"):
        for k, r in markers[kind].items():
            m = mask_of([r], src)
            if m.any():
                mark_xy[(kind, k)] = centroid(m)

    # palette and strokes
    if src["kind"] == "vector":
        pal = build_palette(src, {k: v for k, v in by_target.items()}, T)
        palette = {slot: c for c, slot in pal.items()}
    else:
        dark = []
        for r in src["items"]:
            a = np.asarray(r["image"])
            sel = a[(a[..., 3] > 200) & (a[..., :3].sum(-1) < 200)]
            if len(sel):
                dark.append(np.median(sel[:, :3], axis=0))
        ink = np.median(np.array(dark), axis=0) if dark else np.array([24, 22, 30])
        palette = {"ink": "#" + "".join(f"{int(v):02x}" for v in ink)}

    def strokes(recs):
        out = []
        for r in sorted(recs, key=lambda r: r["order"]):
            if src["kind"] == "raster":
                im = r["image"]; bb = im.getchannel("A").getbbox()
                if not bb:
                    continue
                crop = im.crop(bb); buf = io.BytesIO(); crop.save(buf, "PNG", optimize=True)
                s = {"image": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(), "x": r["x"] + bb[0], "y": r["y"] + bb[1], "w": bb[2] - bb[0], "h": bb[3] - bb[1]}
                if r.get("opacity", 1) < 0.999:
                    s["opacity"] = round(r["opacity"], 3)
                out.append(s); continue
            st = r["style"]
            f = colour(st.get("fill"), src["ids"]); s_ = colour(st.get("stroke"), src["ids"])
            if f in (None, "none") and s_ in (None, "none"):
                continue
            sw = float(re.sub(r"[a-z]+$", "", str(st.get("stroke-width", 1))) or 1) * r["scale"]
            fslot = r.get("slot") if r.get("slot") and f not in (None, "none") else None
            if fslot:
                palette.setdefault(fslot, f)
            rec = {"d": r["d"], "fill": (fslot or pal.get(f, "none")) if f not in (None, "none") else "none",
                   "stroke": pal.get(s_, "none") if s_ not in (None, "none") else "none"}
            if rec["stroke"] != "none":
                rec["width"] = round(sw, 2)
            op = float(st.get("opacity", 1)) * float(st.get("fill-opacity", 1) if rec["fill"] != "none" else st.get("stroke-opacity", 1))
            if op < 0.999:
                rec["opacity"] = round(op, 3)
            out.append(rec)
        return out

    # parts, parents and pivots
    drawn = {k[1] for k in by_target if k[0] == "part"}
    order_of = {k: min(r["order"] for r in v) for k, v in by_target.items()}
    zmode = opts.get("z", "document")
    rank = {k: i for i, k in enumerate(sorted(order_of, key=order_of.get))}

    def eff_parent(pid):
        par = tparts[pid].get("parent")
        while par and par not in drawn and par != "hip":
            par = tparts[par].get("parent")
        return par

    pivots, methods, warnings = {}, {}, []
    all_mask = np.zeros_like(next(iter(masks.values())))
    for m in masks.values():
        all_mask |= m
    ys = np.nonzero(all_mask)[0]
    feet = [k for k in masks if k[0] == "part" and k[1].startswith("foot")]
    if ground_recs:
        gm = mask_of(ground_recs, src); ground = round(float(np.nonzero(gm)[0].max()) / MS, 1) if gm.any() else round(float(ys.max()) / MS, 1)
    elif feet:
        fm = np.zeros_like(all_mask)
        for k in feet:
            fm |= masks[k]
        ground = round(float(np.nonzero(fm)[0].max()) / MS, 1)
    else:
        ground = round(float(ys.max()) / MS, 1)

    def get_mask(pid):
        return masks.get(("part", pid))

    def depth(pid):
        d, q = 0, tparts[pid].get("parent")
        while q:
            d, q = d + 1, tparts[q].get("parent")
        return d
    for tp in sorted(T["parts"], key=lambda t: depth(t["id"])):
        pid = tp["id"]
        if pid not in drawn and pid != "hip":
            continue
        par = eff_parent(pid)
        if ("pivot", pid) in mark_xy:
            pivots[pid] = mark_xy[("pivot", pid)]; methods[pid] = "marker"; continue
        if par is None:  # root
            if pid in drawn and get_mask("torso") is not None and (get_mask("torso") & get_mask(pid)).sum() > 4:
                pivots[pid] = centroid(get_mask("torso") & get_mask(pid)); methods[pid] = "overlap"
            else:
                bottom = all_mask[max(0, int(ground * MS) - int(25 * MS)):int(ground * MS) + 1]
                xs = np.nonzero(bottom)[1]
                pivots[pid] = [round(float(np.median(xs)) / MS, 1) if len(xs) else W / 2, ground]; methods[pid] = "base"
            continue
        tpar = tparts.get(tp.get("parent")) if tp.get("parent") else None
        if (tpar and tp.get("pivot") and tp.get("pivot") == tpar.get("pivot")) or (tname == "doodle" and pid == "body"):
            pivots[pid] = pivots.get(par, [W / 2, ground]); methods[pid] = "shared"; continue
        pm = get_mask(par) if par in drawn else None
        cm = get_mask(pid)
        if pm is not None and cm is not None and (pm & cm).sum() >= 4:
            pivots[pid], methods[pid] = joint(cm, pm)
        elif pm is not None and cm is not None:
            pivots[pid] = nearest(cm, pm); methods[pid] = "nearest"
            warnings.append(f"{pid} does not overlap {par}: the joint will open a gap when it bends (draw {pid} a little past the joint)")
        else:
            pivots[pid] = centroid(cm); methods[pid] = "centre"
            warnings.append(f"{pid}: no parent drawing to find its joint; add a pivot:{pid} marker")

    parts = {}
    for tp in T["parts"]:
        pid = tp["id"]
        if pid not in pivots:
            continue
        z = tp.get("z", 10) if zmode == "template" or ("part", pid) not in rank else 10 + 2 * rank[("part", pid)]
        parts[pid] = {"parent": eff_parent(pid), "pivot": pivots[pid], "z": z, "strokes": strokes(by_target.get(("part", pid), []))}

    swaps = {}
    for (kind, *key), recs in by_target.items():
        if kind != "swap":
            continue
        sid, shp = key
        tsw = tswaps.get(sid, {})
        sw = swaps.setdefault(sid, {"anchor": tsw.get("anchor") if tsw.get("anchor") in parts else ("head" if "head" in parts else next(iter(parts))),
                                    "z": tsw.get("z", 30) if zmode == "template" else 10 + 2 * rank[(kind, sid, shp)], "shapes": {}})
        if zmode != "template":
            sw["z"] = min(sw["z"], 10 + 2 * rank[(kind, sid, shp)])
        for k in ("talk", "movable", "replaces"):
            if tsw.get(k) is not None:
                sw[k] = tsw[k]
        sw["shapes"][shp] = strokes(recs)

    anchors = {k: v for (kind, k), v in mark_xy.items() if kind == "anchor"}
    if "bubble" not in anchors and get_mask("head") is not None:
        hm = get_mask("head"); ys_, xs_ = np.nonzero(hm)
        anchors["bubble"] = [round(float(xs_.mean()) / MS, 1), round(float(ys_.min()) / MS + 10, 1)]

    name = opts.get("name") or Path(source).stem.split(".")[0].replace("_", " ").title()
    puppet = {"format": "doodleberry.puppet", "version": "0.4", "name": name, "template": tname, "artboard": [round(W, 2), round(H, 2)],
              "ground": ground, "palette": palette, "parts": parts, "swaps": swaps, "anchors": anchors,
              "meta": {"author": opts.get("author", ""), "license": opts.get("license", ""), "source": Path(source).name,
                       **({"source_url": opts["source_url"]} if opts.get("source_url") else {}), "import": "dbe/drawing_import.py"}}
    report.update({"template": tname, "pivots": {k: {"at": pivots[k], "method": methods[k]} for k in pivots}, "warnings": warnings,
                   "palette": palette, "missing": [p["id"] for p in T["parts"] if p.get("required") and p["id"] not in drawn]
                   + [f"{s['id']}/{k}" for s in T.get("swaps", []) for k in s.get("required", []) if k not in (swaps.get(s["id"], {}).get("shapes") or {})]})
    return puppet, report


if __name__ == "__main__":
    opts = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    pz, rep = build(sys.argv[1], opts)
    Path(sys.argv[2]).write_text(json.dumps(pz))
    print(json.dumps(rep))
