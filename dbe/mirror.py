"""Mirror tool (WP-18): a part drawn on one side copied to the other, mirrored across the body's centre line.

Raster strokes are flipped left to right and moved across the axis; vector paths are reflected (x -> 2a - x); the
pivot is reflected; a joint's limits [lo, hi] become [-hi, -lo] (a mirrored joint turns the other way); parts that
hang from the part (a forearm, a hand) are mirrored with it, their names' side swapped (_L <-> _R). The axis is the
centre of the parent's drawing unless given.
"""
import base64
import copy
import io
import re

from . import drawing_import as DI
from . import geom as G


def _bbox_x(strokes):
    xs = []
    for st in strokes:
        if st.get("image") and not st.get("d"):
            xs += [st["x"], st["x"] + st["w"]]
        elif st.get("d"):
            for segs, _ in G.parse_path(st["d"]):
                xs += [q[0] for q in G.sample(segs, 3)]
    return (min(xs), max(xs)) if xs else None


def axis_of(p, part):
    """the centre line to mirror across: the middle of the parent's drawing (else of the whole artboard)"""
    parent = p["parts"][part].get("parent")
    bx = _bbox_x(p["parts"][parent]["strokes"]) if parent and p["parts"].get(parent) else None
    return (bx[0] + bx[1]) / 2 if bx else p["artboard"][0] / 2


def other(name):
    return re.sub(r"_L$", "_R", name) if name.endswith("_L") else re.sub(r"_R$", "_L", name) if name.endswith("_R") else name + "_mirror"


def _flip_stroke(st, a):
    st = copy.deepcopy(st)
    if st.get("mesh"):
        raise ValueError("mesh strokes cannot be mirrored yet")
    if st.get("image") and not st.get("d"):
        from PIL import Image, ImageOps
        head, data = st["image"].split(",", 1)
        im = ImageOps.mirror(Image.open(io.BytesIO(base64.b64decode(data))))
        b = io.BytesIO(); im.save(b, "PNG"); st["image"] = "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()
        st["x"] = round(2 * a - (st["x"] + st["w"]), 3)
        return st
    if st.get("d"):
        st["d"] = DI.transform_d(st["d"], [-1, 0, 0, 1, 2 * a, 0])
    return st


def mirror_part(p, src, dst=None, axis=None, replace=False):
    """-> (new puppet, report): src and its subtree copied to dst (default: the other side's name)"""
    if src not in p["parts"]:
        raise ValueError(f"no part {src}")
    dst = dst or other(src); p = copy.deepcopy(p); a = axis_of(p, src) if axis is None else float(axis)
    subtree, frontier = [src], [src]
    while frontier:
        kids = [k for k, v in p["parts"].items() if v.get("parent") in frontier and k not in subtree]
        subtree += kids; frontier = kids
    names = {k: (dst if k == src else other(k)) for k in subtree}
    clash = [n for n in names.values() if n in p["parts"] and n not in subtree]
    if clash and not replace:
        raise ValueError(f"{', '.join(clash)} already drawn (replace: true to redraw from the mirror)")
    made = []
    for k in subtree:
        part = copy.deepcopy(p["parts"][k]); nk = names[k]
        part["strokes"] = [_flip_stroke(st, a) for st in part.get("strokes", [])]
        part["pivot"] = [round(2 * a - part["pivot"][0], 3), part["pivot"][1]]
        if part.get("limits"):
            lo, hi = part["limits"]; part["limits"] = [-hi, -lo]
        if k != src and part.get("parent") in names:
            part["parent"] = names[part["parent"]]
        p["parts"][nk] = part; made.append(nk)
    return p, {"mirrored": dict(names), "axis": round(a, 2), "parts": made}
