"""Exporters from a baked puppet animation (tools/bake.mjs) to other engines:
- Lottie JSON (web, apps, After Effects): parented shape layers with rotation keys about each pivot.
- Synfig .sif (rendered headless by the synfig CLI): one group per part with an animated transformation.
- Grease Pencil frames JSON (read by dbe/blender_gp.py inside headless Blender).
"""
import json
import math
from pathlib import Path

from . import geom as G


def _load(p):
    return json.loads(Path(p).read_text())


# ======================= Lottie =======================
def _view_masks(p, frs):
    """[(view or None, [1/0 per frame])] for every view a cast member uses; None is the default (drawn) view"""
    views = (p.get("views") or {})
    key = lambda fr: fr.get("view") if fr.get("view") in views else None
    used = list(dict.fromkeys(key(fr) for fr in frs))
    return [(v, [1 if key(fr) == v else 0 for fr in frs]) for v in used]


def z_track(frs, key, base):
    """a part's (key) or a swap's ("@" + id) layer order on every frame: clips and controls may move it (WP-14)"""
    return [((fr.get("z") or {}).get(key, base)) for fr in frs]


def raster_strokes(strokes):
    return [st for st in strokes if st.get("image") and not st.get("d")]


def to_lottie(baked, size, name="doodleberry", bg=None, bg_image=None):
    """bg: a solid colour layer; bg_image: a PNG data URI embedded as an image asset (the set plate)"""
    W, H = size
    fps, n = baked["fps"], baked["frames"]
    layers, ind = [], [0]

    def nid():
        ind[0] += 1
        return ind[0]

    def kf(values, hold=False):
        """per-frame values -> Lottie animated property (drop repeats; a value held over several frames keeps a key
        at the end of the hold too, so the next change is not smeared back across the hold: WP-14)"""
        ks, last = [], None
        for f, v in enumerate(values):
            if not hold and ks and v != last and ks[-1]["t"] < f - 1:
                k = {"t": f - 1, "s": last if isinstance(last, list) else [last], "i": {"x": [0.5], "y": [0.5]}, "o": {"x": [0.5], "y": [0.5]}}
                ks.append(k)
            if v != last or f == n - 1:
                k = {"t": f, "s": v if isinstance(v, list) else [v]}
                if hold:
                    k["h"] = 1
                else:
                    k["i"] = {"x": [0.5], "y": [0.5]}; k["o"] = {"x": [0.5], "y": [0.5]}
                ks.append(k); last = v
        return {"a": 1, "k": ks} if len(ks) > 1 else {"a": 0, "k": values[0] if isinstance(values[0], list) else values[0]}

    def shape_group(strokes, pal):
        """one group per stroke: its subpaths share one fill, so an even-odd stroke (v0.9 fill rule) cuts holes"""
        items = []
        for st in strokes:
            it = []
            for segs, closed in G.parse_path(st.get("d") or ""):
                v = [list(s[0]) for s in segs]
                o = [[s[1][0] - s[0][0], s[1][1] - s[0][1]] for s in segs]
                i_ = [[segs[k - 1][2][0] - segs[k - 1][3][0], segs[k - 1][2][1] - segs[k - 1][3][1]] for k in range(len(segs))]
                if not closed:
                    v.append(list(segs[-1][3])); o.append([0, 0]); i_[0] = [0, 0]; i_.append([segs[-1][2][0] - segs[-1][3][0], segs[-1][2][1] - segs[-1][3][1]])
                it.append({"ty": "sh", "ks": {"a": 0, "k": {"i": i_, "o": o, "v": v, "c": closed}}})
            if not it:
                continue
            fill, line = G.colour(st.get("fill"), pal), G.colour(st.get("stroke"), pal)
            if fill:
                it.append({"ty": "fl", "c": {"a": 0, "k": G.hex_rgb(fill) + [1]}, "o": {"a": 0, "k": 100 * st.get("opacity", 1)}, "r": 2 if st.get("rule") == "evenodd" else 1})
            if line:
                it.append({"ty": "st", "c": {"a": 0, "k": G.hex_rgb(line) + [1]}, "o": {"a": 0, "k": 100}, "w": {"a": 0, "k": st.get("width", 3)}, "lc": 2, "lj": 2})
            it.append({"ty": "tr", "p": {"a": 0, "k": [0, 0]}, "a": {"a": 0, "k": [0, 0]}, "s": {"a": 0, "k": [100, 100]}, "r": {"a": 0, "k": 0}, "o": {"a": 0, "k": 100}})
            items.append({"ty": "gr", "it": it})
        return items

    def scaled(items, pivot, frs, pid):
        """v0.9 per-part scale on the part's own drawing only (children keep their proportions, as in puppet.js)"""
        sc = [G._scale_of(fr.get("scales"), pid) or [1, 1] for fr in frs]
        if all(v == [1, 1] for v in sc):
            return items
        return [{"ty": "gr", "it": items + [{"ty": "tr", "p": {"a": 0, "k": list(pivot)}, "a": {"a": 0, "k": list(pivot)}, "r": {"a": 0, "k": 0}, "o": {"a": 0, "k": 100},
                                             "s": kf([[round(100 * v[0], 3), round(100 * v[1], 3)] for v in sc])}]}]

    def stretch_offset(p, pid, fr):
        """where a part's pivot moves because its parent is stretched (v0.9)"""
        par = p["parts"][pid].get("parent")
        ps = G._scale_of(fr.get("scales"), par) if par in p["parts"] else None
        if not ps:
            return [0, 0]
        pp, cp = p["parts"][par]["pivot"], p["parts"][pid]["pivot"]
        return [(ps[0] - 1) * (cp[0] - pp[0]), (ps[1] - 1) * (cp[1] - pp[1])]

    assets = []

    def image_layers(parent_ind, strokes, vis):
        """raster strokes (scans, brushes, drawn levels) as image layers in their part's space (WP-14)"""
        out = []
        for st in strokes:
            aid = f"img{len(assets)}"
            from PIL import Image as _I
            import base64 as _b, io as _io
            iw, ih = _I.open(_io.BytesIO(_b.b64decode(st["image"].split(",", 1)[1]))).size
            assets.append({"id": aid, "w": iw, "h": ih, "u": "", "p": st["image"], "e": 1})
            out.append({"ddd": 0, "ind": nid(), "ty": 2, "nm": aid, "refId": aid, "parent": parent_ind, "sr": 1, "ao": 0, "ip": 0, "op": n, "st": 0, "bm": 0,
                        "ks": {"o": kf(vis, hold=True), "r": {"a": 0, "k": 0}, "a": {"a": 0, "k": [0, 0, 0]},
                               "p": {"a": 0, "k": [st["x"], st["y"], 0]}, "s": {"a": 0, "k": [100 * st["w"] / iw, 100 * st["h"] / ih, 100]}}})
        return out

    def with_z(lay, vis, zs, rasters):
        """a layer whose order changes over time becomes one copy per order, each shown only on its frames (the first
        stays the transform parent of the part's children); raster strokes ride along as image layers"""
        vis = [v if isinstance(v, (int, float)) else 100 for v in vis]
        levels = sorted(set(zs), key=zs.index)
        out = []
        for k, zv in enumerate(levels):
            l = lay if k == 0 else {**lay, "ind": nid(), "ks": dict(lay["ks"])}
            mask = [v if z_ == zv else 0 for v, z_ in zip(vis, zs)]
            if len(levels) > 1 or "o" in lay["ks"]:
                l["ks"]["o"] = kf(mask, hold=True)
            l["_z"] = zv
            out.append(l)
            for im in image_layers(l["ind"] if k == 0 else lay.get("parent"), rasters, mask):
                if k:
                    im["parent"] = lay["ind"]
                im["_z"] = zv + 0.001
                out.append(im)
        return out

    for c in baked["cast"]:
      p0 = _load(c["puppet"]); frs = c["frames"]
      root = None
      for view, on in _view_masks(p0, frs):
        p = G.in_view(p0, view); pal = p["palette"]
        hip = (p["parts"].get("hip") or {}).get("pivot") or [p["artboard"][0] / 2, p["ground"]]   # as the player: drawn levels have no hip
        root = nid()
        layers.append({"ddd": 0, "ind": root, "ty": 3, "nm": f"{p['name']} root", "sr": 1, "ao": 0, "ip": 0, "op": n, "st": 0, "bm": 0,
                       "ks": {"o": {"a": 0, "k": 0}, "r": {"a": 0, "k": 0},
                              "p": kf([[round(fr["x"], 2), round(fr["y"], 2), 0] for fr in frs]),
                              "a": kf([[round(hip[0] - (fr["offset"] or [0, 0])[0], 2), round(p["ground"] - (fr["offset"] or [0, 0])[1], 2), 0] for fr in frs]),
                              "s": kf([[round(100 * fr["s"] * fr["flip"] * (fr.get("squash") or 1), 2), round(100 * fr["s"], 2), 100] for fr in frs])}})
        ids = {pid: nid() for pid in p["parts"]}
        part_layers = []
        for pid, part in p["parts"].items():
            par = part.get("parent")
            lay = {"ddd": 0, "ind": ids[pid], "ty": 4, "nm": pid if not view else f"{pid}@{view}", "parent": ids[par] if par in ids else root, "sr": 1, "ao": 0, "ip": 0, "op": n, "st": 0, "bm": 0,
                   "ks": {"o": kf([100 * o for o in on], hold=True), "r": kf([round(fr["angles"].get(pid, 0) or 0, 2) for fr in frs]),
                          "p": kf([[round(part["pivot"][0] + ((fr.get("shifts") or {}).get(pid) or [0, 0])[0] + stretch_offset(p, pid, fr)[0], 2),
                                     round(part["pivot"][1] + ((fr.get("shifts") or {}).get(pid) or [0, 0])[1] + stretch_offset(p, pid, fr)[1], 2), 0] for fr in frs]),
                          "a": {"a": 0, "k": [part["pivot"][0], part["pivot"][1], 0]}, "s": {"a": 0, "k": [100, 100, 100]}},
                   "shapes": scaled(shape_group(part["strokes"], pal), part["pivot"], frs, pid), "_z": part.get("z", 0)}
            # hidden while a replacing swap shows
            repl = [(sid, sw) for sid, sw in (p.get("swaps") or {}).items() if sw.get("replaces") == pid]
            vis = [0 if (repl and any(G.chosen_swaps(p, fr).get(sid) for sid, _ in repl)) or not o else 100 for fr, o in zip(frs, on)]
            if repl:
                lay["ks"]["o"] = kf(vis, hold=True)
            part_layers += with_z(lay, vis, z_track(frs, pid, part.get("z", 0)), raster_strokes(part["strokes"]))
        for sid, sw in (p.get("swaps") or {}).items():
            for shape, strokes in sw["shapes"].items():
                if not strokes:
                    continue
                vis = [100 if G.chosen_swaps(p, fr).get(sid) == shape and o else 0 for fr, o in zip(frs, on)]
                if not any(vis):
                    continue
                offs = [[((fr["look"] or [0, 0])[0] * sw.get("movable", 8) if sid == "pupils" else 0) + ((fr.get("shifts") or {}).get("@" + sid) or [0, 0])[0],
                         ((fr["look"] or [0, 0])[1] * sw.get("movable", 8) * 0.7 if sid == "pupils" else 0) + ((fr.get("shifts") or {}).get("@" + sid) or [0, 0])[1]] for fr in frs]
                apiv = (p["parts"].get(sw["anchor"]) or {}).get("pivot") or [0, 0]
                asc = [G._scale_of(fr.get("scales"), sw["anchor"]) or [1, 1] for fr in frs]
                anch = any(v != [1, 1] for v in asc)   # anchored to a stretched part: scale about its pivot, as puppet.js does
                lay = {"ddd": 0, "ind": nid(), "ty": 4, "nm": f"{sid}:{shape}" + (f"@{view}" if view else ""), "parent": ids.get(sw["anchor"], root), "sr": 1, "ao": 0, "ip": 0, "op": n, "st": 0, "bm": 0,
                       "ks": {"o": kf(vis, hold=True), "r": {"a": 0, "k": 0},
                              "a": kf([[round(apiv[0] - o_[0], 2), round(apiv[1] - o_[1], 2), 0] for o_ in offs]) if anch else {"a": 0, "k": [0, 0, 0]},
                              "s": kf([[round(100 * v[0], 3), round(100 * v[1], 3), 100] for v in asc]) if anch else {"a": 0, "k": [100, 100, 100]},
                              "p": {"a": 0, "k": [apiv[0], apiv[1], 0]} if anch else kf([[round(o_[0], 2), round(o_[1], 2), 0] for o_ in offs])},
                       "shapes": shape_group(strokes, pal), "_z": sw.get("z", 40)}
                part_layers += with_z(lay, vis, z_track(frs, "@" + sid, sw.get("z", 40)), raster_strokes(strokes))
        part_layers.sort(key=lambda l: -l["_z"])  # Lottie draws the first layer on top
        for l in part_layers:
            l.pop("_z", None)
        layers = part_layers + layers
    if bg:
        layers.append({"ddd": 0, "ind": nid(), "ty": 1, "nm": "background", "sc": bg, "sw": W, "sh": H, "sr": 1, "ao": 0, "ip": 0, "op": n, "st": 0, "bm": 0,
                       "ks": {"o": {"a": 0, "k": 100}, "r": {"a": 0, "k": 0}, "p": {"a": 0, "k": [W / 2, H / 2, 0]}, "a": {"a": 0, "k": [W / 2, H / 2, 0]}, "s": {"a": 0, "k": [100, 100, 100]}}})
    if bg_image:
        assets.append({"id": "plate", "w": W, "h": H, "u": "", "p": bg_image, "e": 1})
        layers.append({"ddd": 0, "ind": nid(), "ty": 2, "nm": "set", "refId": "plate", "sr": 1, "ao": 0, "ip": 0, "op": n, "st": 0, "bm": 0,
                       "ks": {"o": {"a": 0, "k": 100}, "r": {"a": 0, "k": 0}, "p": {"a": 0, "k": [W / 2, H / 2, 0]}, "a": {"a": 0, "k": [W / 2, H / 2, 0]}, "s": {"a": 0, "k": [100, 100, 100]}}})
    return {"v": "5.7.4", "fr": fps, "ip": 0, "op": n, "w": W, "h": H, "nm": name, "ddd": 0, "assets": assets, "layers": layers}


# ======================= Synfig =======================
def _sif_color(h, a=1.0):
    r, g, b = G.hex_rgb(h)
    lin = lambda c: c  # canvas gamma is 1.0, so colours pass through unchanged
    return f"<color><r>{lin(r):.6f}</r><g>{lin(g):.6f}</g><b>{lin(b):.6f}</b><a>{a:.3f}</a></color>"


def _bline(segs, closed):
    pts = []
    n = len(segs)
    for k, (p0, c1, c2, p1) in enumerate(segs):
        prev = segs[k - 1] if (k > 0 or closed) else None
        t1 = (3 * (p0[0] - prev[2][0]), 3 * (p0[1] - prev[2][1])) if prev else (3 * (c1[0] - p0[0]), 3 * (c1[1] - p0[1]))
        t2 = (3 * (c1[0] - p0[0]), 3 * (c1[1] - p0[1]))
        pts.append((p0, t1, t2))
    if not closed:
        last = segs[-1]
        pts.append((last[3], (3 * (last[3][0] - last[2][0]), 3 * (last[3][1] - last[2][1])), (3 * (last[3][0] - last[2][0]), 3 * (last[3][1] - last[2][1]))))
    v = lambda p: f"<vector><x>{p[0]:.4f}</x><y>{p[1]:.4f}</y></vector>"
    out = f'<bline type="bline_point" loop="{"true" if closed else "false"}">'
    for p, t1, t2 in pts:
        out += (f"<entry><composite type=\"bline_point\"><point>{v(p)}</point><width><real value=\"1\"/></width><origin><real value=\"0.5\"/></origin>"
                f"<split><bool value=\"true\"/></split><t1>{v(t1)}</t1><t2>{v(t2)}</t2><split_radius><bool value=\"true\"/></split_radius><split_angle><bool value=\"true\"/></split_angle></composite></entry>")
    return out + "</bline>"


def _shapes_sif(strokes, pal):
    out = ""
    for st in strokes:
        fill, line = G.colour(st.get("fill"), pal), G.colour(st.get("stroke"), pal)
        subs = G.parse_path(st.get("d") or "")
        region = lambda segs, extra="": (f'<layer type="region" active="true" version="0.1"><param name="amount"><real value="{st.get("opacity", 1):.3f}"/></param>{extra}'
                                         f'<param name="color">{_sif_color(fill)}</param><param name="bline">{_bline(segs, True)}</param></layer>')
        closed_subs = [segs for segs, closed in subs if closed]
        if fill and st.get("rule") == "evenodd" and len(closed_subs) > 1:
            # v0.9 even-odd fill: the first contour fills, the others cut holes ("alpha over"), inside a group so the
            # cuts only reach this stroke
            cut = '<param name="blend_method"><integer value="19"/></param>'
            inner = region(closed_subs[0]) + "".join(region(sg, cut) for sg in closed_subs[1:])
            out += f'<layer type="group" active="true" version="0.3"><param name="canvas"><canvas>{inner}</canvas></param></layer>'
        elif fill:
            out += "".join(region(sg) for sg in closed_subs)
        if line:
            for segs, closed in subs:
                out += f'<layer type="outline" active="true" version="0.2"><param name="color">{_sif_color(line)}</param><param name="width"><real value="{st.get("width", 3):.3f}"/></param><param name="sharp_cusps"><bool value="false"/></param><param name="round_tip[0]"><bool value="true"/></param><param name="round_tip[1]"><bool value="true"/></param><param name="bline">{_bline(segs, closed)}</param></layer>'
    return out


def _raster_sif(strokes, assets_dir):
    """raster strokes as Synfig import layers (the images written to assets_dir; WP-14)"""
    import base64 as _b
    import hashlib
    out = ""
    for st in raster_strokes(strokes):
        if not assets_dir:
            continue
        data = _b.b64decode(st["image"].split(",", 1)[1])
        f = Path(assets_dir) / f"img_{hashlib.sha1(data).hexdigest()[:16]}.png"
        if not f.exists():
            f.write_bytes(data)
        out += (f'<layer type="import" active="true" version="0.1"><param name="tl"><vector><x>{st["x"]:.3f}</x><y>{st["y"]:.3f}</y></vector></param>'
                f'<param name="br"><vector><x>{st["x"] + st["w"]:.3f}</x><y>{st["y"] + st["h"]:.3f}</y></vector></param><param name="filename"><string>{f}</string></param></layer>')
    return out


def to_synfig(baked, size, bg_png=None, transparent=False, assets_dir=None):
    W, H = size
    fps, n = baked["fps"], baked["frames"]
    U = 60.0  # pixels per synfig unit
    F = [1 / U, 0, 0, -1 / U, -W / 2 / U, H / 2 / U]  # screen px -> synfig units (y up)
    t = lambda f: f"{f / fps:.5f}s"
    head = (f'<?xml version="1.0" encoding="UTF-8"?>\n<canvas version="1.2" width="{W}" height="{H}" xres="2834.645669" yres="2834.645669" gamma-r="1" gamma-g="1" gamma-b="1" '
            f'view-box="{-W / 2 / U:.4f} {H / 2 / U:.4f} {W / 2 / U:.4f} {-H / 2 / U:.4f}" antialias="1" fps="{fps}" begin-time="0f" end-time="{t(n - 1)}" bgcolor="{'0 0 0 0' if transparent else '1 1 1 1'}"><name>doodleberry</name>')
    body = ""
    if bg_png:
        body += (f'<layer type="import" active="true" version="0.1"><param name="tl"><vector><x>{-W / 2 / U:.4f}</x><y>{H / 2 / U:.4f}</y></vector></param>'
                 f'<param name="br"><vector><x>{W / 2 / U:.4f}</x><y>{-H / 2 / U:.4f}</y></vector></param><param name="filename"><string>{bg_png}</string></param></layer>')

    def decompose(m):
        """offset, angle and scale of a matrix without shear (per-part scales are local, v0.9: a part's x and y axes
        stay perpendicular, so an uneven scale needs no skew)"""
        a, b, c, d, e, f = m
        det = a * d - b * c
        kx, ky = math.hypot(a, b), math.hypot(c, d)
        if det < 0:
            ang, sx, sy = math.atan2(-b, -a), -kx, ky
        else:
            ang, sx, sy = math.atan2(b, a), kx, ky
        return e, f, math.degrees(ang), sx, sy

    def reduce(keys, tol):
        """drop keys a straight line between their neighbours reproduces within tol (WP-14: long shots stayed under
        the XML parser's 10 MB limit only with this)"""
        if len(keys) <= 2:
            return keys
        out = [keys[0]]
        for i in range(1, len(keys) - 1):
            (f0, v0), (f1, v1), (f2, v2) = out[-1], keys[i], keys[i + 1]
            k = (f1 - f0) / (f2 - f0)
            if max(abs(a_ + (c_ - a_) * k - b_) for a_, b_, c_ in zip(v0, v1, v2)) > tol:
                out.append(keys[i])
        out.append(keys[-1])
        return out

    def anim_transform(mats, vis=None):
        ko, ka, ks = [], [], []
        last = None
        for fi, m in enumerate(mats):
            if vis is not None and not any(vis[max(0, fi - 1):fi + 2]):
                continue   # hidden here and at both neighbours: its transform does not show
            e, f, ang, sx, sy = decompose(m)
            # keep angles continuous
            if last is not None:
                while ang - last > 180: ang -= 360
                while ang - last < -180: ang += 360
            last = ang
            ko.append((fi, (e, f))); ka.append((fi, (ang,))); ks.append((fi, (sx, sy)))
        if not ko:
            e, f, ang, sx, sy = decompose(mats[0]); ko, ka, ks = [(0, (e, f))], [(0, (ang,))], [(0, (sx, sy))]
        wps_o = "".join(f'<waypoint time="{t(fi)}" before="linear" after="linear"><vector><x>{v[0]:.4f}</x><y>{v[1]:.4f}</y></vector></waypoint>' for fi, v in reduce(ko, 0.0016))
        wps_a = "".join(f'<waypoint time="{t(fi)}" before="linear" after="linear"><angle value="{v[0]:.3f}"/></waypoint>' for fi, v in reduce(ka, 0.05))
        wps_s = "".join(f'<waypoint time="{t(fi)}" before="linear" after="linear"><vector><x>{v[0]:.5f}</x><y>{v[1]:.5f}</y></vector></waypoint>' for fi, v in reduce(ks, 0.0005))
        return (f'<param name="transformation"><composite type="transformation"><offset><animated type="vector">{wps_o}</animated></offset>'
                f'<angle><animated type="angle">{wps_a}</animated></angle><skew_angle><angle value="0"/></skew_angle>'
                f'<scale><animated type="vector">{wps_s}</animated></scale></composite></param>')

    def amount(vals):
        if all(v == vals[0] for v in vals):
            return f'<param name="amount"><real value="{vals[0]}"/></param>'
        w, last = "", None
        for fi, v in enumerate(vals):
            if v != last:
                w += f'<waypoint time="{t(fi)}" before="constant" after="constant"><real value="{v}"/></waypoint>'; last = v
        return f'<param name="amount"><animated type="real">{w}</animated></param>'

    for c in baked["cast"]:
      p0 = _load(c["puppet"]); frs = c["frames"]
      items = []
      for view, on in _view_masks(p0, frs):
        p = G.in_view(p0, view); pal = p["palette"]
        Ms = [G.part_matrices(p, fr["angles"], fr.get("shifts"), fr.get("scales")) for fr in frs]
        Rs = [G.root_matrix(p, fr) for fr in frs]
        for pid, part in p["parts"].items():
            if not part["strokes"]:
                continue
            mats = [G.mul(F, G.mul(Rs[i], Ms[i][pid])) for i in range(n)]
            repl = [sid for sid, sw in (p.get("swaps") or {}).items() if sw.get("replaces") == pid]
            vis = [0 if any(G.chosen_swaps(p, fr).get(s) for s in repl) else 1 for fr in frs] if repl else [1] * n
            vis = [v * o for v, o in zip(vis, on)]
            if not any(vis):
                continue
            zs = z_track(frs, pid, part.get("z", 0))
            for zv in sorted(set(zs), key=zs.index):   # a part whose layer order changes: one layer per order (WP-14)
                vz = [v if z_ == zv else 0 for v, z_ in zip(vis, zs)]
                if any(vz):
                    items.append((zv, f'<layer type="group" active="true" version="0.3" desc="{pid}">{amount(vz)}<param name="origin"><vector><x>0</x><y>0</y></vector></param>{anim_transform(mats, vz)}<param name="canvas"><canvas>{_raster_sif(part["strokes"], assets_dir)}{_shapes_sif(part["strokes"], pal)}</canvas></param></layer>'))
        for sid, sw in (p.get("swaps") or {}).items():
            for shape, strokes in sw["shapes"].items():
                if not strokes:
                    continue
                vis = [1 if G.chosen_swaps(p, fr).get(sid) == shape and o else 0 for fr, o in zip(frs, on)]
                if not any(vis):
                    continue
                anchor = sw["anchor"]
                mats = []
                for i, fr in enumerate(frs):
                    m = G.mul(Rs[i], Ms[i].get(anchor, G.I))
                    if (fr.get("shifts") or {}).get("@" + sid):
                        m = G.mul(m, [1, 0, 0, 1, *fr["shifts"]["@" + sid]])
                    if sid == "pupils" and fr.get("look"):
                        m = G.mul(m, [1, 0, 0, 1, fr["look"][0] * sw.get("movable", 8), fr["look"][1] * sw.get("movable", 8) * 0.7])
                    mats.append(G.mul(F, m))
                zs = z_track(frs, "@" + sid, sw.get("z", 40))
                for zv in sorted(set(zs), key=zs.index):
                    vz = [v if z_ == zv else 0 for v, z_ in zip(vis, zs)]
                    if any(vz):
                        items.append((zv, f'<layer type="group" active="true" version="0.3" desc="{sid}:{shape}">{amount(vz)}<param name="origin"><vector><x>0</x><y>0</y></vector></param>{anim_transform(mats, vz)}<param name="canvas"><canvas>{_raster_sif(strokes, assets_dir)}{_shapes_sif(strokes, pal)}</canvas></param></layer>'))
      items.sort(key=lambda x: x[0])  # synfig: later layers draw on top
      body += "".join(s for _, s in items)
    return head + body + "</canvas>\n"


# ======================= Grease Pencil frames =======================
def _keyhole(polys):
    """one simple polygon for an even-odd fill: the largest contour, with each other contour cut in through a bridge"""
    def area(q):
        return sum(q[i][0] * q[(i + 1) % len(q)][1] - q[(i + 1) % len(q)][0] * q[i][1] for i in range(len(q))) / 2
    polys = sorted(polys, key=lambda q: -abs(area(q)))
    out = list(polys[0])
    for hole in polys[1:]:
        h = hole if (area(hole) > 0) != (area(polys[0]) > 0) else hole[::-1]   # holes wind the other way
        i, j = min(((i, j) for i in range(len(out)) for j in range(len(h))), key=lambda ij: (out[ij[0]][0] - h[ij[1]][0]) ** 2 + (out[ij[0]][1] - h[ij[1]][1]) ** 2)
        out = out[:i + 1] + h[j:] + h[:j + 1] + out[i:]
    return out


def to_gp_frames(baked, size, per=6):
    """per frame, a z-ordered list of world-space strokes (polylines) with fill/line colours, for blender_gp.py"""
    out = {"fps": baked["fps"], "frames": baked["frames"], "size": list(size), "palette": {}, "data": []}
    pals = {}
    for f in range(baked["frames"]):
        strokes = []
        for c in baked["cast"]:
            p = pals.setdefault(c["puppet"], _load(c["puppet"])); fr = c["frames"][f]; p = G.in_view(p, fr.get("view")); pal = p["palette"]
            M = G.part_matrices(p, fr["angles"], fr.get("shifts"), fr.get("scales")); R = G.root_matrix(p, fr)
            sw = G.chosen_swaps(p, fr)
            items = []
            for pid, part in p["parts"].items():
                if any(s.get("replaces") == pid and sw.get(sid) for sid, s in (p.get("swaps") or {}).items()):
                    continue
                if part.get("bend") and part.get("parent") in M and not (fr.get("shifts") or {}).get(pid):
                    # bendy limb: points follow the arc bend in the parent's space (rigid exporters can't do this)
                    ax = part.setdefault("_axis", G.part_axis(part)); th = fr["angles"].get(pid, 0) or 0
                    Mp = G.mul(R, M[part["parent"]])
                    items.append(((fr.get("z") or {}).get(pid, part.get("z", 0)), ("bend", Mp, part["pivot"], ax, part["bend"].get("width", 40), th), part["strokes"]))
                    continue
                items.append(((fr.get("z") or {}).get(pid, part.get("z", 0)), G.mul(R, M[pid]), part["strokes"]))
            for sid, shape in sw.items():
                s = p["swaps"][sid]; m = G.mul(R, M.get(s["anchor"], G.I))
                if (fr.get("shifts") or {}).get("@" + sid):
                    m = G.mul(m, [1, 0, 0, 1, *fr["shifts"]["@" + sid]])
                if sid == "pupils" and fr.get("look"):
                    m = G.mul(m, [1, 0, 0, 1, fr["look"][0] * s.get("movable", 8), fr["look"][1] * s.get("movable", 8) * 0.7])
                items.append((s.get("z", 40), m, s["shapes"][shape]))
            items.sort(key=lambda x: x[0])
            for _, m, sts in items:
                for st in sts:
                    subs = G.parse_path(st.get("d") or "")
                    if st.get("rule") == "evenodd" and st.get("fill") and sum(1 for _, c in subs if c) > 1:
                        # v0.9 even-odd fill: Grease Pencil fills cannot have holes, so the outer contour and its holes
                        # become one keyhole polygon (joined by a zero-width bridge); the outlines are drawn separately
                        polys = []
                        for segs, closed in subs:
                            if not closed:
                                continue
                            if isinstance(m, tuple) and m and m[0] == "bend":
                                _, Mp, piv, ax, wd, th = m
                                polys.append([G.apply(Mp, G.bend_point(q, piv, ax, wd, th)) for q in G.sample(segs, per)])
                            else:
                                polys.append([G.apply(m, q) for q in G.sample(segs, per)])
                        strokes.append({"pts": [[round(x, 1), round(y, 1)] for x, y in _keyhole(polys)], "closed": True,
                                        "fill": G.colour(st.get("fill"), pal), "line": None, "w": st.get("width", 3) * fr.get("s", 1), "op": st.get("opacity", 1)})
                        st = {**st, "fill": None}
                    for segs, closed in subs:
                        if isinstance(m, tuple) and m and m[0] == "bend":
                            _, Mp, piv, ax, wd, th = m
                            pts = [G.apply(Mp, G.bend_point(q, piv, ax, wd, th)) for q in G.sample(segs, per)]
                        else:
                            pts = [G.apply(m, q) for q in G.sample(segs, per)]
                        strokes.append({"pts": [[round(x, 1), round(y, 1)] for x, y in pts], "closed": closed,
                                        "fill": G.colour(st.get("fill"), pal) if closed else None, "line": G.colour(st.get("stroke"), pal),
                                        "w": st.get("width", 3) * fr.get("s", 1), "op": st.get("opacity", 1)})
        out["data"].append(strokes)
    return out
