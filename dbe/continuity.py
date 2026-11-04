"""Continuity checks and named shot sizes (WP-19), measured on the baked frames every renderer reads (screen positions
with the shot camera already folded in).

- **180-degree rule**: two characters seen together in consecutive shots keep their left-right order on screen (the
  camera stays on one side of the line between them), unless the later shot says it crosses on purpose
  (`"cross_line": true`).
- **Screen direction**: a character travelling across the frame in consecutive shots keeps going the same way (a walk
  to the right does not continue to the left after the cut), unless `"cross_line": true`.
- **Eyeline**: in a shot / reverse-shot pair (consecutive shots each showing one of two characters seen together in an
  earlier shot), each looks towards where the other stands on screen: A, left of B, looks right; B looks left.
- **Shot size**: from how much of the main character the frame shows: extreme long (a figure under 15% of the frame
  height), long (whole figure, under a third), full (whole figure), medium long (cut around the knees), medium (the
  waist), medium close-up (the chest), close-up (head and shoulders), extreme close-up (less).
"""
import numpy as np

from . import geom as G

SIZES = [("ECU", "extreme close-up"), ("CU", "close-up"), ("MCU", "medium close-up"), ("MS", "medium shot"), ("MLS", "medium long shot"),
         ("FS", "full shot"), ("LS", "long shot"), ("ELS", "extreme long shot")]


def rest_top(puppet):
    """the highest point of the drawing at rest, in artboard units (the top of the head)"""
    ys = []
    for part in puppet["parts"].values():
        for st in part.get("strokes", []):
            if st.get("d"):
                for segs, _ in G.parse_path(st["d"]):
                    ys += [p[1] for p in G.sample(segs, 4)]
            elif "image" in st:
                ys.append(st["y"])
            elif "mesh" in st:
                ys += [v[1] for v in st["mesh"]["verts"]]
    for sw in (puppet.get("swaps") or {}).values():   # heads drawn as swaps (drawn levels) count too
        for strokes in (sw.get("shapes") or {}).values():
            for st in strokes or []:
                if "image" in st:
                    ys.append(st["y"])
    return min(ys) if ys else 0.0


def size_of(top_y, bottom_y, H):
    """shot size from a character's screen top and ground point (frame px)"""
    h = bottom_y - top_y
    if h <= 0:
        return None
    if bottom_y <= H + 2:   # feet in frame: the whole figure
        k = h / H
        return "ELS" if k < 0.15 else "LS" if k < 1 / 3 else "FS"
    vis = (min(bottom_y, H) - max(top_y, 0)) / h   # the share of the figure shown, from the head down
    return "MLS" if vis >= 0.72 else "MS" if vis >= 0.5 else "MCU" if vis >= 0.33 else "CU" if vis >= 0.18 else "ECU"


def summary(shot, baked, puppets, size):
    """per character in a shot: mid-shot screen x, travel (px over the shot), gaze (mean pupil x where it looks
    sideways), screen top and ground at mid-shot"""
    W, H = size; out = {}
    for c, k in zip(shot["cast"], baked["cast"]):
        frs = k["frames"]
        if not frs:
            continue
        pz = puppets[c["puppet"]]; key = c.get("name") or pz.get("name") or c["puppet"]
        mid = frs[len(frs) // 2]
        xs = np.array([f["x"] for f in frs])
        gx = [f["look"][0] for f in frs if f.get("look") and abs(f["look"][0]) > 0.15]
        top = mid["y"] - (pz.get("ground", pz["artboard"][1]) - rest_top(pz)) * mid["s"]
        out[key] = {"x": float(np.median(xs)), "travel": float(xs[-1] - xs[0]), "gaze": float(np.mean(gx)) if len(gx) > len(frs) * 0.2 else 0.0,
                    "top": float(top), "ground": float(mid["y"]), "visible": bool(-50 < mid["x"] < W + 50 and top < H)}
    return out


def check(shots, sums, size):
    """-> (issues, per-shot rows)"""
    W, H = size; issues, rows = [], []
    for i, (sh, sm) in enumerate(zip(shots, sums)):
        vis = {k: v for k, v in sm.items() if v["visible"]}
        main = max(vis.items(), key=lambda kv: kv[1]["ground"] - kv[1]["top"], default=(None, None))
        rows.append({"shot": sh["id"], "size": size_of(main[1]["top"], main[1]["ground"], H) if main[0] else None, "main": main[0],
                     "order": [k for k, _ in sorted(vis.items(), key=lambda kv: kv[1]["x"])], "cross_line": bool(sh.get("cross_line"))})
    seen = {}   # 180-degree rule over the scene: each pair's left-right order where they were last seen together
    for i, (row, sm) in enumerate(zip(rows, sums)):
        if row["cross_line"]:
            seen = {}   # a deliberate cross: the line is drawn anew
        o = row["order"]
        for p_ in range(len(o)):
            for q in range(p_ + 1, len(o)):
                pair = (o[p_], o[q]); key = tuple(sorted(pair)); left = o[p_]
                if key in seen and seen[key][0] != left:
                    issues.append({"rule": "180-degree", "shots": [seen[key][1], row["shot"]], "what": f"{key[0]} and {key[1]} swap sides (the camera crossed the line between them)"})
                seen[key] = (left, row["shot"])
    for i in range(1, len(shots)):
        a, b, sa, sb = rows[i - 1], rows[i], sums[i - 1], sums[i]
        if b["cross_line"]:
            continue
        for k in set(sa) & set(sb):   # screen direction for a character travelling in both shots
            ta, tb = sa[k]["travel"], sb[k]["travel"]
            if abs(ta) > 0.1 * W and abs(tb) > 0.1 * W and ta * tb < 0:
                issues.append({"rule": "screen direction", "shots": [a["shot"], b["shot"]], "what": f"{k} travels {'right' if ta > 0 else 'left'}, then {'right' if tb > 0 else 'left'}"})
    # eyelines: shot / reverse shot of two characters established together earlier
    est = {}   # pair -> their screen x in the last shot showing both
    for i, (row, sm) in enumerate(zip(rows, sums)):
        if len(row["order"]) >= 2:
            for p in range(len(row["order"])):
                for q in range(p + 1, len(row["order"])):
                    A, B = row["order"][p], row["order"][q]; est[frozenset((A, B))] = {A: sm[A]["x"], B: sm[B]["x"]}
        if i == 0 or len(row["order"]) != 1 or len(rows[i - 1]["order"]) != 1:
            continue
        A, B = rows[i - 1]["order"][0], row["order"][0]
        e = est.get(frozenset((A, B)))
        if not e or A == B:
            continue
        for who, other, sm_ in ((A, B, sums[i - 1]), (B, A, sm)):
            g = sm_[who]["gaze"]; want = np.sign(e[other] - e[who])
            if g and np.sign(g) != want:
                issues.append({"rule": "eyeline", "shots": [rows[i - 1]["shot"], row["shot"]],
                               "what": f"{who} looks {'right' if g > 0 else 'left'}, away from {other} (who stands to the {'right' if want > 0 else 'left'})"})
    return issues, rows
