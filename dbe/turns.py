"""Turns between views as in-between drawings (WP-43: morphs between views).

A view switch (`view` keys on a timeline: front to side) used to be a cut with a 0.09 s squash. `make_turns` draws
the in-betweens instead, as ordinary views, so every renderer, the bake and the exporters already play them:

    views["turn:<from>><to>:<k>"]   k = 1..K, from/to a view name or "base" (the drawn default)

Per part, each stroke of the target view is paired with a stroke of the source of the same fill, the nearest in
place and size first; a stroke left over shrinks to its centre (or grows from it). Each pair is resampled to the same number of
points by arc length, with the start point and direction that line them up best, and blended; pivots blend; the
layer order and the swap drawings (eyes, mouth) come from the nearer end. The loader (acting.js) shows in-between k
for one step around the switch (on twos at 30 fps by default) and drops the squash for that switch.
"""
import copy
import math

from . import geom as G

N = 64   # points per resampled outline


def _poly(d):
    """a path's subpaths as polylines [(points, closed)]"""
    out = []
    for segs, closed in G.parse_path(d):
        pts = G.sample(segs, 12)
        if len(pts) >= 2:
            out.append((pts, closed))
    return out


def _resample(pts, closed, n=N):
    P = list(pts) + ([pts[0]] if closed else [])
    L = [0.0]
    for a, b in zip(P, P[1:]):
        L.append(L[-1] + math.dist(a, b))
    tot = L[-1] or 1.0; out = []; j = 0
    for i in range(n):
        s = tot * i / (n if closed else n - 1)
        while j < len(L) - 2 and L[j + 1] < s:
            j += 1
        seg = (L[j + 1] - L[j]) or 1.0; u = (s - L[j]) / seg
        out.append((P[j][0] + (P[j + 1][0] - P[j][0]) * u, P[j][1] + (P[j + 1][1] - P[j][1]) * u))
    return out


def _align(a, b, closed):
    """b reordered (start point, direction) to line up with a"""
    cands = []
    for bb in (b, b[::-1]):
        shifts = range(len(bb)) if closed else [0]
        for s in shifts:
            c = bb[s:] + bb[:s]
            cands.append((sum((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 for p, q in zip(a, c)), c))
    return min(cands, key=lambda x: x[0])[1]


def _centre(pts):
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def _d(pts, closed):
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + (" Z" if closed else "")


def _stroke_polys(st):
    return [(_resample(p, c), c) for p, c in _poly(st["d"])] if st.get("d") else None


def _pair(src, dst):
    """pairs of (source stroke or None, target stroke or None): same fill (and kind), cheapest first, the cost being
    how far apart the centres are plus how different the sizes (an ear pairs with an ear, not the skull beside it)"""
    def geo(st):
        pts = [q for p, _ in (_stroke_polys(st) or [([(0, 0)], False)]) for q in p]
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        return _centre(pts), math.sqrt(max(1.0, (max(xs) - min(xs)) * (max(ys) - min(ys))))
    gs, gd = [geo(x) for x in src], [geo(y) for y in dst]
    cand = sorted((math.dist(gs[i][0], gd[j][0]) + abs(gs[i][1] - gd[j][1]), i, j) for i in range(len(src)) for j in range(len(dst))
                  if src[i].get("fill") == dst[j].get("fill") and bool(src[i].get("d")) == bool(dst[j].get("d")))
    used_i, used_j, match = set(), set(), {}
    for _, i, j in cand:
        if i not in used_i and j not in used_j:
            used_i.add(i); used_j.add(j); match[j] = i
    pairs = [(src[match[j]] if j in match else None, t) for j, t in enumerate(dst)]
    return pairs + [(src[i], None) for i in range(len(src)) if i not in used_i]


def _blend_stroke(a, b, u):
    """an in-between stroke, u in (0, 1) from a to b (either may be None: it shrinks to / grows from its centre)"""
    base = b if (u >= 0.5 and b) or not a else a
    if not ((a or {}).get("d") or (b or {}).get("d")):   # images and meshes switch at the halfway point
        return copy.deepcopy(base)
    pa, pb = (_stroke_polys(a) if a else None), (_stroke_polys(b) if b else None)
    if pa is None and pb is None:
        return copy.deepcopy(base)
    if pa is None:   # grows from its centre
        pa = [([_centre(p)] * N, c) for p, c in pb]
    if pb is None:   # shrinks to its centre
        pb = [([_centre(p)] * N, c) for p, c in pa]
    subs = []
    for k in range(max(len(pa), len(pb))):
        p, cp = pa[k] if k < len(pa) else ([_centre(pb[k][0])] * N, pb[k][1])
        q, cq = pb[k] if k < len(pb) else ([_centre(p)] * N, cp)
        closed = cp and cq
        q = _align(p, q, closed)
        subs.append(_d([(x0 + (x1 - x0) * u, y0 + (y1 - y0) * u) for (x0, y0), (x1, y1) in zip(p, q)], closed))
    out = {k: v for k, v in copy.deepcopy(base).items() if k != "d"}
    if a and b and a.get("width") is not None and b.get("width") is not None:
        out["width"] = round(a["width"] + (b["width"] - a["width"]) * u, 2)
    out["d"] = " ".join(subs)
    return out


def resolved(puppet, view):
    """a view's full parts and swaps (the default, "base", is the puppet's own)"""
    return G.in_view(puppet, None if view in (None, "", "base") else view)


def make_turns(puppet, a="base", b="side", steps=3):
    """-> a copy of the puppet with views turn:a>b:1..steps (in-betweens from view a to view b)"""
    p = copy.deepcopy(puppet); views = p.setdefault("views", {}) or {}; p["views"] = views
    for k in [k for k in views if k.startswith(f"turn:{a}>{b}:")]:
        del views[k]
    A, B = resolved(puppet, a), resolved(puppet, b)
    for k in range(1, steps + 1):
        u = k / (steps + 1); v = {"parts": {}, "swaps": {}}
        for pid, pa in A["parts"].items():
            pb = B["parts"].get(pid, pa)
            if pa == pb:
                continue
            sa, sb = pa.get("strokes", []), pb.get("strokes", [])
            prs = _pair(sa, sb); prs = [q for q in prs if q[1] is None] + [q for q in prs if q[1] is not None]   # what turns away goes under
            strokes = [s for s in (_blend_stroke(x, y, u) for x, y in prs) if s]
            piv = [round(pa["pivot"][i] + (pb["pivot"][i] - pa["pivot"][i]) * u, 2) for i in (0, 1)]
            v["parts"][pid] = {"strokes": strokes, "pivot": piv, "z": (pa if u < 0.5 else pb).get("z", pa.get("z", 0))}
        for sid, sw in (B if u >= 0.5 else A).get("swaps", {}).items():
            if sw != A.get("swaps", {}).get(sid):
                v["swaps"][sid] = {"shapes": copy.deepcopy(sw.get("shapes", {}))}
        views[f"turn:{a}>{b}:{k}"] = v
    return p
