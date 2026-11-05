"""Over-the-shoulder framing (WP-19).

An over-the-shoulder shot looks past one character (the *over* character, near the camera, seen from behind and cut
by the frame edge) at the other (the *on* character, framed medium close-up on the far third). In a 2D puppet film
"near the camera" is drawing the over character bigger and lower; the camera is held, so no parallax is owed, and the
shot is ordinary data (a camera key, a cast place, a view key) that the shared bake carries to every renderer.

- `back_view(puppet)`: a `views.back` override built from the puppet itself: the face (eyes, pupils, brows, mouth,
  nose and any face part) drawn empty, the back hair raised over the head and the front hair under it, and the
  left and right limbs swapping depth about the torso (the arm that was behind the body is now the near one).
- `layout(...)`: the camera key and the over character's place, from both characters' places, sizes and heads.
  The over character keeps the screen side it has in the wide shot, so the 180-degree line is kept.
"""
import copy
import re

from . import continuity as CT
from . import geom as G

FACE_SWAPS = re.compile(r"^(eyes?|pupils?|brows?|mouth|nose|lashes|cheeks?|blush|teeth|tongue)(_.*)?$")
FACE_PARTS = re.compile(r"^(face.*|eye.*|pupil.*|brow.*|mouth.*|nose.*|cheek.*|lash.*)$")
# (visible fraction of the on character from the head down, its head top as a share of the frame height, the widest
# its head may be as a share of the frame width: cartoon heads are big, and a tall frame is narrow)
SIZES = {"MS": (0.56, 0.24, 0.62), "MCU": (0.42, 0.2, 0.72), "CU": (0.28, 0.16, 0.85)}


def back_view(puppet):
    """-> a copy of the puppet with views.back (an existing views.back is kept as drawn)"""
    p = copy.deepcopy(puppet); views = p.setdefault("views", {}) or {}; p["views"] = views
    if "back" in views:
        return p
    parts = p["parts"]; v = {"parts": {}, "swaps": {}}
    for sid, sw in (p.get("swaps") or {}).items():
        if FACE_SWAPS.match(sid):
            v["swaps"][sid] = {"shapes": {k: [] for k in sw.get("shapes", {})}}
    for pid in parts:
        if FACE_PARTS.match(pid):
            v["parts"][pid] = {"strokes": []}
    if "head" in parts:   # the face drawn on the head (blush, nose lines) goes; the skull shows hair, the ears stay
        strokes = parts["head"].get("strokes", [])
        box = lambda st: _box({"parts": {"x": {"strokes": [st]}}}, ["x"]) or (0, 0, 0, 0)
        area = lambda st: (box(st)[2] - box(st)[0]) * (box(st)[3] - box(st)[1])
        if strokes:
            skull = max(strokes, key=area); skin = skull.get("fill")
            hair = next((st.get("fill") for k in ("hair_back", "hair_front", "hair") for st in (parts.get(k) or {}).get("strokes", []) if st.get("fill") not in (None, "none")), None)
            v["parts"]["head"] = {"strokes": [({**st, "fill": hair} if st is skull and hair else st) for st in strokes if st.get("fill") == skin]}
    zs = [q.get("z", 0) for q in parts.values()]
    head = parts.get("head", {}).get("z", max(zs) if zs else 0)
    if "hair_back" in parts:
        v["parts"]["hair_back"] = {"z": max(zs) + 1}   # seen from behind, the back of the hair covers the head
    if "hair_front" in parts:
        v["parts"]["hair_front"] = {"z": min(head - 1, parts["hair_front"].get("z", head) - 100)}
    zt = parts.get("torso", {}).get("z")
    if zt is not None:
        for pid, q in parts.items():
            if re.search(r"_(L|R)$", pid) and "z" in q:
                v["parts"].setdefault(pid, {})["z"] = 2 * zt - q["z"]   # limbs swap depth about the torso
            if pid.startswith("tail") and "z" in q and q["z"] < zt:
                v["parts"].setdefault(pid, {})["z"] = 2 * zt - q["z"]   # a tail behind the body is now in front of it
    views["back"] = v
    return p


def _box(puppet, ids):
    xs, ys = [], []
    for pid in ids:
        for st in (puppet["parts"].get(pid) or {}).get("strokes", []):
            if st.get("d"):
                for segs, _ in G.parse_path(st["d"]):
                    pts = G.sample(segs, 4); xs += [q[0] for q in pts]; ys += [q[1] for q in pts]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def head_box(puppet):
    """the head with its hair, at rest, in artboard units: (x0, y0, x1, y1)"""
    ids = [k for k in puppet["parts"] if k == "head" or k.startswith("hair") or k.startswith("ear")]
    return _box(puppet, ids) or _box(puppet, list(puppet["parts"]))


def dims(puppet):
    """(ground y, rest top y, ground pivot x, head box) in artboard units"""
    ground = puppet.get("ground", puppet["artboard"][1])
    return ground, CT.rest_top(puppet), puppet["artboard"][0] / 2, head_box(puppet)


def layout(on, over, size, W, H, size_name="MS", near=1.45, overlap=0.08, near_share=0.3):
    """on, over: {x, y, s, flip (1 or -1), puppet}; -> {"camera": [cx, cy, z], "place": {x, y, s, flip}, "side": -1|1, "notes": []}
    The on character fills the frame to the size asked on the far third; the over character, `near` times its own
    size on screen, has its head reach `overlap` of the way into the on character's head, and fills at least
    `near_share` of the frame width from its edge."""
    vis, top_k, head_k = SIZES.get(size_name, SIZES["MS"]); notes = []
    gB, tB, axB, hbB = dims(on["puppet"]); gA, tA, axA, hbA = dims(over["puppet"])
    side = 1 if over["x"] > on["x"] else -1   # the over character's side of the frame, as in the wide shot
    hB = (gB - tB) * on["s"]
    z = min((H * (1 - top_k) / vis) / hB, head_k * W / ((hbB[2] - hbB[0]) * on["s"]))
    yT = on["y"] - hB
    cy = yT + (H / 2 - top_k * H) / z
    # the on character's head on the far third
    fB = -1 if on.get("flip") == -1 else 1
    hx0, hx1 = sorted(((hbB[0] - axB) * fB, (hbB[2] - axB) * fB))   # head extent about the ground pivot, as drawn
    want_hc = W / 2 - side * W * 0.12
    cx = on["x"] + (hx0 + hx1) / 2 * on["s"] - (want_hc - W / 2) / z
    hw, hh = W / (2 * z), H / (2 * z)
    if not (hw <= cx <= W - hw and hh <= cy <= H - hh):
        notes.append("the framing reaches past the set's edge")
    sA = over["s"] * near
    fA = -1 if side > 0 else 1   # seen from behind, facing the on character (into the frame)
    ax0, ax1 = sorted(((hbA[0] - axA) * fA, (hbA[2] - axA) * fA))
    # screen x of the on character's head edges, then the over character's inner head edge just past the near one
    b_near = W / 2 + (on["x"] - cx) * z + (hx1 if side > 0 else hx0) * on["s"] * z
    head_wB = (hx1 - hx0) * on["s"] * z
    inner = b_near + side * overlap * head_wB * -1   # reach a little over the near edge of the on character's head
    inner = max(inner, near_share * W) if side < 0 else min(inner, (1 - near_share) * W)
    # over character's ground pivot x on screen so its inner head edge lands at `inner`
    a_inner_off = (ax0 if side > 0 else ax1) * sA * z
    xs = inner - a_inner_off
    # its head top a little below the on character's
    a_top = (top_k + 0.1) * H
    yA_top = cy + (a_top - H / 2) / z
    place = {"x": round(cx + (xs - W / 2) / z, 1), "y": round(yA_top + (gA - tA) * sA, 1), "s": round(sA, 3), "flip": fA}
    return {"camera": [round(cx, 2), round(cy, 2), round(z, 4)], "place": place, "side": side, "notes": notes}
