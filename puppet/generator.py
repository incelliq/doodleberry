"""Character generator (plan 1.5): original, fully rigged humanoid puppets from a short spec.

    python puppet/generator.py SPEC.json OUT.puppet.json

SPEC (all optional): {"name": "Ama", "build": "slim|average|broad", "age": "child|teen|adult|elder",
  "skin": "#c68a62", "hair": {"style": "short|bob|long|curly|bun|ponytail|spiky|bald|hijab", "color": "#2b1d14"},
  "top": {"style": "tee|shirt|hoodie|sweater|jacket|dress|overalls", "color": "#e0703c", "color2": "#ffffff"},
  "bottom": {"style": "trousers|shorts|skirt", "color": "#2f4f6f"}, "shoes": "#f1f1ee", "eyes": "#5a3a22",
  "accessories": ["glasses", "beard", "moustache", "freckles", "earrings", "tie"]}
Every character gets the full humanoid rig (template parts, eyes/half/closed, pupils, four brows, eight mouths,
right-hand poses), a `turn` control, springy hair, and palette slots so outfits can be recoloured later.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).parent
T = json.loads((HERE / "templates" / "humanoid.json").read_text())
f = lambda n: f"{n:.1f}"


def ellipse(cx, cy, rx, ry):
    return f"M{f(cx - rx)} {f(cy)} A{f(rx)} {f(ry)} 0 1 0 {f(cx + rx)} {f(cy)} A{f(rx)} {f(ry)} 0 1 0 {f(cx - rx)} {f(cy)} Z"


def capsule(a, b, r0, r1):
    (ax, ay), (bx, by) = a, b
    ang = math.atan2(by - ay, bx - ax); nx, ny = -math.sin(ang), math.cos(ang)
    p1 = (ax + nx * r0, ay + ny * r0); p2 = (bx + nx * r1, by + ny * r1); p3 = (bx - nx * r1, by - ny * r1); p4 = (ax - nx * r0, ay - ny * r0)
    return (f"M{f(p1[0])} {f(p1[1])} L{f(p2[0])} {f(p2[1])} A{f(r1)} {f(r1)} 0 0 0 {f(p3[0])} {f(p3[1])} "
            f"L{f(p4[0])} {f(p4[1])} A{f(r0)} {f(r0)} 0 0 0 {f(p1[0])} {f(p1[1])} Z")


def poly(pts, close=True):
    return "M" + " L".join(f"{f(x)} {f(y)}" for x, y in pts) + (" Z" if close else "")


st = lambda d, fill, stroke="ink", width=4: {"d": d, "fill": fill, "stroke": stroke, "width": width}
line = lambda d, width=4, col="ink": {"d": d, "fill": "none", "stroke": col, "width": width}

AGE = {"child": (0.74, 1.12), "teen": (0.9, 1.04), "adult": (1.0, 1.0), "elder": (0.97, 1.0)}   # body height scale, head scale
BUILD = {"slim": 0.86, "average": 1.0, "broad": 1.18}


def generate(spec):
    name = spec.get("name", "Guest")
    kb, kh = AGE.get(spec.get("age", "adult"), AGE["adult"])
    wb = BUILD.get(spec.get("build", "average"), 1.0)
    ground = T["ground"]; P0 = {p["id"]: p["pivot"] for p in T["parts"]}
    neck_y0 = P0["neck"][1]
    # body below the neck scales about the ground; head moves with the neck and scales by kh
    def body(pt):
        x, y = pt
        return [300 + (x - 300) * wb, ground - (ground - y) * kb]
    neck = body(P0["neck"]); dy_head = neck[1] - neck_y0
    def head(pt):
        x, y = pt
        return [300 + (x - 300) * kh, neck[1] + (y - neck_y0) * kh]
    P = {k: (head(v) if k in ("head", "hair_front", "hair_back") else body(v)) for k, v in P0.items()}
    P["head"] = head(P0["head"]); P["neck"] = neck
    parts = {p["id"]: {"parent": p["parent"], "pivot": [round(v, 1) for v in P[p["id"]]], "z": p["z"], "strokes": []} for p in T["parts"]}
    add = lambda pid, *s: parts[pid]["strokes"].extend(s)
    H = lambda x, y: head((x, y))
    hc = H(300, 262); hrx, hry = 80 * kh, 90 * kh
    top = spec.get("top", {}); tst = top.get("style", "tee"); bot = spec.get("bottom", {}); bst = bot.get("style", "trousers")
    hair = spec.get("hair", {}); hs = hair.get("style", "short"); acc = set(spec.get("accessories", []))
    if tst == "dress":
        bst = "skirt"

    # ---- torso, hip
    sh_l, sh_r = body((232, 352)), body((368, 352)); wl, wr = body((250, 566)), body((350, 566))
    torso = f"M{f(sh_l[0])} {f(sh_l[1])} C{f(sh_l[0] + 4)} {f(sh_l[1] - 16)} {f(sh_r[0] - 4)} {f(sh_r[1] - 16)} {f(sh_r[0])} {f(sh_r[1])} L{f(sh_r[0] - 6)} {f(body((0, 470))[1])} C{f(sh_r[0] - 8)} {f(body((0, 520))[1])} {f(wr[0] + 2)} {f(wr[1] - 10)} {f(wr[0])} {f(wr[1])} L{f(wl[0])} {f(wl[1])} C{f(wl[0] - 2)} {f(wl[1] - 10)} {f(sh_l[0] + 8)} {f(body((0, 520))[1])} {f(sh_l[0] + 6)} {f(body((0, 470))[1])} Z"
    add("torso", st(torso, "cloth1"))
    cx = 300; ny = body((0, 338))[1]
    if tst in ("shirt", "jacket"):
        add("torso", st(poly([(cx - 22, ny), (cx, ny + 26), (cx - 6, ny + 2)]), "cloth3", width=3), st(poly([(cx + 22, ny), (cx, ny + 26), (cx + 6, ny + 2)]), "cloth3", width=3))
    if tst == "jacket":
        add("torso", st(poly([(cx - 16, ny + 8), (cx + 16, ny + 8), (cx + 12, wl[1]), (cx - 12, wl[1])]), "cloth3", width=3))
    elif tst == "hoodie":
        add("torso", st(ellipse(cx, body((0, 500))[1], 46 * wb, 22), "cloth1", width=3), line(f"M{f(cx - 10)} {f(ny + 4)} L{f(cx - 12)} {f(ny + 60)} M{f(cx + 10)} {f(ny + 4)} L{f(cx + 12)} {f(ny + 60)}", 3))
    elif tst == "overalls":
        bib = poly([(cx - 40 * wb, body((0, 430))[1]), (cx + 40 * wb, body((0, 430))[1]), (wr[0] - 4, wr[1]), (wl[0] + 4, wl[1])])
        add("torso", st(bib, "cloth2"), line(f"M{f(cx - 36 * wb)} {f(body((0, 432))[1])} L{f(sh_l[0] + 18)} {f(sh_l[1] - 8)} M{f(cx + 36 * wb)} {f(body((0, 432))[1])} L{f(sh_r[0] - 18)} {f(sh_r[1] - 8)}", 5, "cloth2"))
    else:
        add("torso", line(f"M{f(cx - 18)} {f(ny)} L{f(cx)} {f(ny + 22)} L{f(cx + 18)} {f(ny)}", 3.5))
    if tst in ("sweater", "hoodie"):
        add("torso", line(f"M{f(wl[0] + 2)} {f(wl[1] - 18)} L{f(wr[0] - 2)} {f(wr[1] - 18)}", 3))
    if "tie" in acc:
        add("torso", st(poly([(cx - 8, ny + 22), (cx + 8, ny + 22), (cx + 12, ny + 130), (cx, ny + 150), (cx - 12, ny + 130)]), "cloth3", width=3))
    hip_top = body((0, 548))[1]
    if bst == "skirt":
        skirt_col = "cloth1" if tst == "dress" else "cloth2"
        add("hip", st(poly([(wl[0] - 4, hip_top), (wr[0] + 4, hip_top), (wr[0] + 46 * wb, body((0, 700))[1]), (wl[0] - 46 * wb, body((0, 700))[1])]), skirt_col))
    else:
        add("hip", st(f"M{f(body((244, 548))[0])} {f(hip_top)} L{f(body((356, 548))[0])} {f(hip_top)} L{f(body((362, 612))[0])} {f(body((0, 612))[1])} C{f(330)} {f(body((0, 620))[1])} {f(270)} {f(body((0, 620))[1])} {f(body((238, 612))[0])} {f(body((0, 612))[1])} Z", "cloth2"))

    # ---- neck, head, ears, face details
    add("neck", st(capsule(head((300, 318)), body((300, 352)), 17 * kh, 18 * wb), "skin"))
    add("head", st(ellipse(hc[0] - hrx + 2 * kh, hc[1] + 10 * kh, 13 * kh, 18 * kh), "skin"), st(ellipse(hc[0] + hrx - 2 * kh, hc[1] + 10 * kh, 13 * kh, 18 * kh), "skin"),
        st(ellipse(hc[0], hc[1], hrx, hry), "skin"),
        {"d": ellipse(*H(262, 300), 14 * kh, 8 * kh), "fill": "blush", "opacity": 0.35}, {"d": ellipse(*H(338, 300), 14 * kh, 8 * kh), "fill": "blush", "opacity": 0.35},
        line("M{} {} Q{} {} {} {}".format(*map(f, H(300, 270) + H(310, 292) + H(298, 296))), 3.5))
    if "freckles" in acc:
        add("head", *[{"d": ellipse(*H(x, y), 2.2, 2.2), "fill": "ink", "opacity": 0.45} for x, y in ((258, 288), (266, 296), (252, 298), (342, 288), (334, 296), (348, 298))])
    if "earrings" in acc:
        add("head", *[st(ellipse(*H(x, 300), 5, 5), "cloth3", width=2.5) for x in (222, 378)])
    if spec.get("age") == "elder":
        add("head", line("M{} {} Q{} {} {} {}".format(*map(f, H(270, 220) + H(300, 214) + H(330, 220))), 2.5), line("M{} {} Q{} {} {} {}".format(*map(f, H(276, 232) + H(300, 227) + H(324, 232))), 2.5))

    # ---- hair (front over the forehead, back behind the head; back hair springs)
    hb, hf = [], []
    if hs == "short":
        hf.append(st(f"M{f(H(218, 250)[0])} {f(H(0, 250)[1])} C{f(H(214, 186)[0])} {f(H(0, 186)[1])} {f(H(258, 160)[0])} {f(H(0, 160)[1])} {f(H(304, 162)[0])} {f(H(0, 162)[1])} C{f(H(352, 164)[0])} {f(H(0, 164)[1])} {f(H(388, 196)[0])} {f(H(0, 196)[1])} {f(H(382, 252)[0])} {f(H(0, 252)[1])} C{f(H(370, 220)[0])} {f(H(0, 220)[1])} {f(H(350, 204)[0])} {f(H(0, 204)[1])} {f(H(322, 200)[0])} {f(H(0, 200)[1])} C{f(H(300, 214)[0])} {f(H(0, 214)[1])} {f(H(262, 222)[0])} {f(H(0, 222)[1])} {f(H(236, 214)[0])} {f(H(0, 214)[1])} Z", "hair"))
    elif hs in ("bob", "long"):
        low = 360 if hs == "bob" else 470
        hb.append(st(poly([H(212, 220), H(388, 220), H(394, low), H(206, low)]), "hair"))
        hf.append(st(f"M{f(H(214, 268)[0])} {f(H(0, 268)[1])} C{f(H(204, 132)[0])} {f(H(0, 132)[1])} {f(H(396, 132)[0])} {f(H(0, 132)[1])} {f(H(386, 268)[0])} {f(H(0, 268)[1])} C{f(H(372, 214)[0])} {f(H(0, 214)[1])} {f(H(320, 206)[0])} {f(H(0, 206)[1])} {f(H(300, 222)[0])} {f(H(0, 222)[1])} C{f(H(280, 206)[0])} {f(H(0, 206)[1])} {f(H(228, 214)[0])} {f(H(0, 214)[1])} {f(H(214, 268)[0])} {f(H(0, 268)[1])} Z", "hair"))
    elif hs == "curly":
        pts = [(300 + 92 * math.cos(a), 238 - 80 * math.sin(a)) for a in [math.pi * i / 10 for i in range(-1, 12)]]
        hb.append(st(ellipse(*H(300, 230), 96 * kh, 70 * kh), "hair"))
        for x, y in pts:
            hf.append(st(ellipse(*H(x, y), 22 * kh, 22 * kh), "hair", width=3))
        hf.append({"d": ellipse(*H(300, 200), 70 * kh, 30 * kh), "fill": "hair"})
    elif hs in ("bun", "ponytail"):
        hf.append(st(f"M{f(H(218, 246)[0])} {f(H(0, 246)[1])} C{f(H(208, 134)[0])} {f(H(0, 134)[1])} {f(H(392, 134)[0])} {f(H(0, 134)[1])} {f(H(382, 246)[0])} {f(H(0, 246)[1])} C{f(H(360, 206)[0])} {f(H(0, 206)[1])} {f(H(240, 206)[0])} {f(H(0, 206)[1])} {f(H(218, 246)[0])} {f(H(0, 246)[1])} Z", "hair"))
        if hs == "bun":
            hb.append(st(ellipse(*H(300, 158), 40 * kh, 36 * kh), "hair"))
        else:
            hb.append(st(capsule(H(360, 220), H(410, 360), 22 * kh, 14 * kh), "hair"))
    elif hs == "spiky":
        zig = [H(216, 250)] + [H(216 + i * 21, 168 if i % 2 else 200) for i in range(1, 9)] + [H(386, 250), H(300, 214)]
        hf.append(st(poly(zig), "hair"))
    elif hs == "hijab":
        hb.append(st(f"M{f(H(196, 250)[0])} {f(H(0, 250)[1])} C{f(H(196, 140)[0])} {f(H(0, 140)[1])} {f(H(404, 140)[0])} {f(H(0, 140)[1])} {f(H(404, 250)[0])} {f(H(0, 250)[1])} L{f(body((392, 420))[0])} {f(body((0, 420))[1])} L{f(body((208, 420))[0])} {f(body((0, 420))[1])} Z", "cloth3"))
        fx, fy = H(300, 272); frx, fry = 64 * kh, 76 * kh   # the face opening
        outer = f"M{f(H(206, 330)[0])} {f(H(0, 330)[1])} C{f(H(190, 130)[0])} {f(H(0, 130)[1])} {f(H(410, 130)[0])} {f(H(0, 130)[1])} {f(H(394, 330)[0])} {f(H(0, 330)[1])} Q{f(H(300, 372)[0])} {f(H(0, 372)[1])} {f(H(206, 330)[0])} {f(H(0, 330)[1])} Z"
        hole = f"M{f(fx - frx)} {f(fy)} A{f(frx)} {f(fry)} 0 1 1 {f(fx + frx)} {f(fy)} A{f(frx)} {f(fry)} 0 1 1 {f(fx - frx)} {f(fy)} Z"
        hf.append({"d": outer + " " + hole, "fill": "cloth3", "stroke": "ink", "width": 4, "rule": "evenodd"})
    add("hair_back", *hb); add("hair_front", *hf)
    if "glasses" in acc or "beard" in acc or "moustache" in acc:
        extra = []
        if "glasses" in acc:
            for x in (272, 328):
                extra.append(st(ellipse(*H(x, 262), 22 * kh, 18 * kh), "none", width=4))
            extra.append(line("M{} {} L{} {}".format(*map(f, H(294, 260) + H(306, 260))), 4))
        if "beard" in acc:
            extra.append(st(f"M{f(H(226, 286)[0])} {f(H(0, 286)[1])} C{f(H(230, 370)[0])} {f(H(0, 370)[1])} {f(H(370, 370)[0])} {f(H(0, 370)[1])} {f(H(374, 286)[0])} {f(H(0, 286)[1])} C{f(H(350, 330)[0])} {f(H(0, 330)[1])} {f(H(250, 330)[0])} {f(H(0, 330)[1])} {f(H(226, 286)[0])} {f(H(0, 286)[1])} Z", "hair", width=3))
        if "moustache" in acc or "beard" in acc:
            extra.append(st(f"M{f(H(278, 312)[0])} {f(H(0, 312)[1])} C{f(H(290, 300)[0])} {f(H(0, 300)[1])} {f(H(310, 300)[0])} {f(H(0, 300)[1])} {f(H(322, 312)[0])} {f(H(0, 312)[1])} C{f(H(306, 308)[0])} {f(H(0, 308)[1])} {f(H(294, 308)[0])} {f(H(0, 308)[1])} {f(H(278, 312)[0])} {f(H(0, 312)[1])} Z", "hair", width=2.5))
        parts["face_extras"] = {"parent": "head", "pivot": parts["head"]["pivot"], "z": 47, "strokes": extra}

    # ---- arms and legs
    long_sleeve = tst in ("shirt", "hoodie", "sweater", "jacket")
    for side in "LR":
        sx = -1 if side == "L" else 1
        u, fo, h = f"upperarm_{side}", f"forearm_{side}", f"hand_{side}"
        add(u, st(capsule(P[u], P[fo], 27 * wb, 24 * wb), "cloth1" if tst != "dress" else "skin"))
        add(fo, st(capsule((P[fo][0], P[fo][1] - 6), P[h], 20 * wb, 17 * wb), "cloth1" if long_sleeve else "skin"))
        if long_sleeve:
            add(fo, st(capsule((P[h][0], P[h][1] - 20), (P[h][0], P[h][1] - 6), 18 * wb, 18 * wb), "cloth1" if tst != "jacket" else "cloth3", width=3))
        hx, hy = P[h]
        add(h, st(ellipse(hx + sx * 2, hy + 18, 21 * wb, 24 * wb), "skin"), st(capsule((hx - sx * 14, hy + 6), (hx - sx * 26, hy + 22), 7, 6), "skin"))
        t_, s_, ft = f"thigh_{side}", f"shin_{side}", f"foot_{side}"
        leg_top = "skin" if bst == "skirt" else "cloth2"
        add(t_, st(capsule((P[t_][0], P[t_][1] - 14), P[s_], 33 * wb if bst != "skirt" else 22 * wb, 27 * wb if bst != "skirt" else 20 * wb), leg_top))
        add(s_, st(capsule((P[s_][0], P[s_][1] - 10), P[ft], 22 * wb if bst == "trousers" else 18 * wb, 19 * wb if bst == "trousers" else 16 * wb), "cloth2" if bst == "trousers" else "skin"))
        fx, fy = P[ft]
        add(ft, st(f"M{f(fx - 26)} {f(fy - 14)} C{f(fx - 30)} {f(fy + 14)} {f(fx - 18)} {f(ground - 10)} {f(fx)} {f(ground)} L{f(fx + 50)} {f(ground)} C{f(fx + 62)} {f(ground - 2)} {f(fx + 60)} {f(fy + 12)} {f(fx + 40)} {f(fy + 4)} L{f(fx + 16)} {f(fy - 16)} Z", "shoe"))

    # ---- face swaps (scaled with the head)
    E = [H(272, 262), H(328, 262)]; s = kh
    eyes = {"open": [st(ellipse(x, y, 13 * s, 16 * s), "eye", width=3.5) for x, y in E],
            "half": [st(f"M{f(x - 13 * s)} {f(y)} A{f(13 * s)} {f(9 * s)} 0 0 0 {f(x + 13 * s)} {f(y)} Z", "eye", width=3.5) for x, y in E] + [line(f"M{f(x - 14 * s)} {f(y)} L{f(x + 14 * s)} {f(y)}", 3.5) for x, y in E],
            "closed": [line(f"M{f(x - 13 * s)} {f(y + 2)} Q{f(x)} {f(y + 10 * s)} {f(x + 13 * s)} {f(y + 2)}", 4) for x, y in E]}
    pupils = {"default": [{"d": ellipse(x, y + 1, 7 * s, 8 * s), "fill": "iris"} for x, y in E] + [{"d": ellipse(x, y + 1, 4 * s, 4.5 * s), "fill": "ink"} for x, y in E] + [{"d": ellipse(x + 2.5 * s, y - 2.5 * s, 2 * s, 2 * s), "fill": "eye"} for x, y in E]}
    brow = lambda di, do: [line(f"M{f(x - 14 * s)} {f(y - 26 * s + (do if x < 300 else di))} Q{f(x)} {f(y - 34 * s)} {f(x + 14 * s)} {f(y - 26 * s + (di if x < 300 else do))}", 5, "hair" if hs not in ("bald", "hijab") else "ink") for x, y in E]
    brows = {"neutral": brow(0, 0), "raised": brow(-8, -8), "worried": brow(-8, 4), "angry": brow(8, -4)}
    Mx, My = H(300, 320)
    W_ = 1.0 * s
    mouth = {
        "closed": [line(f"M{f(Mx - 14 * W_)} {f(My)} Q{f(Mx)} {f(My + 4)} {f(Mx + 14 * W_)} {f(My)}")],
        "small": [st(ellipse(Mx, My + 2, 9 * W_, 5 * W_), "mouth", width=3.5)],
        "mid": [st(ellipse(Mx, My + 4, 12 * W_, 9 * W_), "mouth", width=3.5), {"d": ellipse(Mx, My + 9 * W_, 7 * W_, 3 * W_), "fill": "tongue"}],
        "wide": [st(f"M{f(Mx - 16 * W_)} {f(My - 2)} Q{f(Mx)} {f(My - 6)} {f(Mx + 16 * W_)} {f(My - 2)} Q{f(Mx + 13 * W_)} {f(My + 22 * W_)} {f(Mx)} {f(My + 22 * W_)} Q{f(Mx - 13 * W_)} {f(My + 22 * W_)} {f(Mx - 16 * W_)} {f(My - 2)} Z", "mouth", width=3.5),
                 {"d": poly([(Mx - 11 * W_, My - 1), (Mx + 11 * W_, My - 1), (Mx + 9 * W_, My + 4), (Mx - 9 * W_, My + 4)]), "fill": "eye"}, {"d": ellipse(Mx, My + 15 * W_, 8 * W_, 4 * W_), "fill": "tongue"}],
        "O": [st(ellipse(Mx, My + 4, 8 * W_, 11 * W_), "mouth", width=3.5)],
        "FV": [st(ellipse(Mx, My + 2, 13 * W_, 5 * W_), "mouth", width=3.5), {"d": poly([(Mx - 10 * W_, My - 1), (Mx + 10 * W_, My - 1), (Mx + 8 * W_, My + 3), (Mx - 8 * W_, My + 3)]), "fill": "eye"}],
        "smile": [line(f"M{f(Mx - 18 * W_)} {f(My - 4)} Q{f(Mx)} {f(My + 14 * W_)} {f(Mx + 18 * W_)} {f(My - 4)}", 4.5)],
        "frown": [line(f"M{f(Mx - 15 * W_)} {f(My + 6)} Q{f(Mx)} {f(My - 6)} {f(Mx + 15 * W_)} {f(My + 6)}", 4.5)]}
    hx, hy = P["hand_R"]
    hand_pose = {"point": [st(ellipse(hx + 2, hy + 16, 19 * wb, 20 * wb), "skin"), st(capsule((hx + 10, hy + 6), (hx + 46, hy - 8), 8, 7), "skin")],
                 "fist": [st(ellipse(hx + 2, hy + 16, 19 * wb, 19 * wb), "skin"), line(f"M{f(hx - 8)} {f(hy + 10)} L{f(hx + 12)} {f(hy + 10)} M{f(hx - 8)} {f(hy + 20)} L{f(hx + 12)} {f(hy + 20)}", 2.5)]}
    swaps = {"eyes": {"anchor": "head", "z": 42, "shapes": eyes}, "pupils": {"anchor": "head", "z": 43, "shapes": pupils, "movable": 8 * s},
             "brows": {"anchor": "head", "z": 44, "shapes": brows}, "mouth": {"anchor": "head", "z": 45, "shapes": mouth, "talk": ["closed", "small", "mid", "wide"]},
             "hand_R_pose": {"anchor": "forearm_R", "z": 33, "shapes": hand_pose, "replaces": "hand_R"}}
    turn = {"range": [-1, 1], "drives": [{"target": "angles.head", "keys": [[-1, -4], [0, 0], [1, 4]]},
             *[{"target": f"shift.@{k}", "keys": [[-1, [-v * kh, 0]], [0, [0, 0]], [1, [v * kh, 0]]]} for k, v in (("eyes", 16), ("pupils", 19), ("brows", 15), ("mouth", 12))],
             {"target": "shift.hair_front", "keys": [[-1, [-7, 0]], [0, [0, 0]], [1, [7, 0]]]}, {"target": "shift.hair_back", "keys": [[-1, [9, 0]], [0, [0, 0]], [1, [-9, 0]]]}]}
    if "face_extras" in parts:
        turn["drives"].append({"target": "shift.face_extras", "keys": [[-1, [-14 * kh, 0]], [0, [0, 0]], [1, [14 * kh, 0]]]})
    palette = {"skin": spec.get("skin", "#d9a27a"), "hair": hair.get("color", "#3a2618"), "cloth1": top.get("color", "#e0703c"), "cloth2": bot.get("color", "#2f4f6f"),
               "cloth3": top.get("color2", "#f4f1e8"), "shoe": spec.get("shoes", "#f1f1ee"), "eye": "#ffffff", "iris": spec.get("eyes", "#5a3a22"),
               "ink": "#24160e", "blush": "#ff8f8a", "mouth": "#6a2420", "tongue": "#e27a76"}
    springs = {"hair_back": {"driver": "head", "freq": 2.2, "damping": 0.3, "gain": 1.3 if hs in ("long", "ponytail", "bun") else 0.8, "limit": 20}}
    parts["head"]["limits"] = [-30, 30]   # v0.6 joint limit: no clip, look-at or spring can wring the neck
    chains = {}
    tail = spec.get("tail")
    if tail:  # v0.6: a FABRIK tail (costume or creature): a chain of tapering segments behind the hips, curling up at the end
        n = int(tail.get("segments", 5)); L = tail.get("length", 300) * wb; seg = L / n
        hp = parts["hip"]["pivot"]; x0, y0 = hp[0] + 34 * wb, hp[1] + 30
        r0, r1 = tail.get("root_width", 26) * wb, tail.get("tip_width", 7) * wb
        palette_key = "tail"
        prev, pts = "hip", []
        for i in range(n + 1):  # rest curve: out to screen right and gently up
            a = math.radians(-8 - 70 * (i / n) ** 1.6)
            if i == 0:
                pts.append((x0, y0))
            else:
                pts.append((pts[-1][0] + seg * math.cos(a), pts[-1][1] + seg * math.sin(a)))
        ids = []
        for i in range(n):
            pid = f"tail_{i + 1}"; ids.append(pid)
            ra, rb = r0 + (r1 - r0) * i / n, r0 + (r1 - r0) * (i + 1) / n
            strokes = [{"d": capsule(pts[i], pts[i + 1], ra, rb), "fill": palette_key, "stroke": "ink", "width": 4}]
            if tail.get("spikes", True) and i < n - 1:  # dino plates along the top
                mx, my = (pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2
                dx, dy = pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]; d = math.hypot(dx, dy) or 1; nx, ny = dy / d, -dx / d
                h = (ra + rb) / 2 * 0.9
                strokes.append({"d": poly([(mx - dx * 0.25 + nx * ra * 0.8, my - dy * 0.25 + ny * ra * 0.8), (mx + nx * (ra + h), my + ny * (ra + h)), (mx + dx * 0.25 + nx * rb * 0.8, my + dy * 0.25 + ny * rb * 0.8)]),
                                "fill": "tail2", "stroke": "ink", "width": 3})
            parts[pid] = {"parent": prev, "pivot": [round(pts[i][0], 1), round(pts[i][1], 1)], "z": 4 - i * 0.01, "strokes": strokes, "limits": [-40, 40]}
            prev = pid
        palette["tail"] = tail.get("color", top.get("color", "#6fbf73")); palette["tail2"] = tail.get("color2", "#f2c14e")
        chains["tail"] = {"parts": ids, "tip": [round(pts[-1][0], 1), round(pts[-1][1], 1)], "wave": {"amp": tail.get("wag", 7), "freq": 0.55, "lag": 0.7}}
        for i, pid in enumerate(ids[1:], 1):
            springs[pid] = {"driver": ids[i - 1], "freq": 2.6, "damping": 0.35, "gain": 0.7, "limit": 25}
    return {"format": "doodleberry.puppet", "version": "0.6", "name": name, "template": "humanoid", "artboard": T["artboard"], "ground": ground,
            "palette": palette, "parts": parts, "swaps": swaps, "controls": {"turn": turn}, "springs": springs, **({"chains": chains} if chains else {}),
            "anchors": {"bubble": [round(hc[0], 1), round(hc[1] - hry - 20, 1)]},
            "meta": {"author": "Doodleberry character generator", "license": "CC0-1.0", "generator": "puppet/generator.py", "spec": spec}}


if __name__ == "__main__":
    spec = json.loads(Path(sys.argv[1]).read_text()) if len(sys.argv) > 1 and sys.argv[1] != "-" else json.loads(sys.stdin.read())
    pz = generate(spec)
    Path(sys.argv[2]).write_text(json.dumps(pz))
    print(json.dumps({"name": pz["name"], "parts": len(pz["parts"]), "strokes": sum(len(p["strokes"]) for p in pz["parts"].values())}))
