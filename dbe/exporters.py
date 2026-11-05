"""Exporters from a baked puppet animation (tools/bake.mjs) to other engines:
- Lottie JSON (web, apps, After Effects): parented shape layers with rotation keys about each pivot.
- Synfig .sif (rendered headless by the synfig CLI): one group per part with an animated transformation.
- Grease Pencil frames JSON (read by dbe/blender_gp.py inside headless Blender).
"""
import json
import math
import re
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


def to_lottie(baked, size, name="doodleberry", bg=None, bg_image=None, slots=False):
    """bg: a solid colour layer; bg_image: a PNG data URI embedded as an image asset (the set plate). slots (WP-23):
    every colour taken from a puppet's palette names its slot ("sid": "skin", or "<puppet>.skin" with several in the
    cast) and the root "slots" holds each slot's value, so a dotLottie theme (or a player) can recolour by name"""
    W, H = size
    SL = {"on": slots, "prefix": "", "slots": {}}

    def colour_prop(v, pal):
        """a colour property; with slots, palette colours carry their slot id"""
        hexv = G.colour(v, pal); prop = {"a": 0, "k": G.hex_rgb(hexv) + [1]}
        if SL["on"] and not v.startswith("#"):
            sid = SL["prefix"] + v; prop["sid"] = sid; SL["slots"].setdefault(sid, {"p": {"a": 0, "k": prop["k"]}})
        return prop
    fps, n = baked["fps"], baked["frames"]
    layers, ind = [], [0]

    def nid():
        ind[0] += 1
        return ind[0]

    def pos(values):
        """a layer's position: spatial keyframes carry tangents (straight lines here), which rlottie needs"""
        k = kf(values)
        if k.get("a"):
            for key in k["k"][:-1]:
                key.setdefault("to", [0, 0, 0]); key.setdefault("ti", [0, 0, 0])
        return k

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
        for k0, k1 in zip(ks, ks[1:]):   # explicit end values: rlottie (Telegram's renderer) needs them, lottie-web accepts them
            if not k0.get("h"):
                k0["e"] = k1["s"]
        if len(ks) > 1:   # the last key is only a time and a value: easing on it stops rlottie drawing the layer after frame 0
            ks[-1] = {k: v for k, v in ks[-1].items() if k in ("t", "s", "h")}
        return {"a": 1, "k": ks} if len(ks) > 1 else {"a": 0, "k": values[0] if isinstance(values[0], list) else values[0]}

    def grad_fill(g, st, pal):
        """v0.13 gradient fill as Lottie's gradient fill (linear or radial), in the part's rest units as the paths"""
        stops = g.get("stops") or []
        k = [v for o, c, *_ in stops for v in [o] + G.hex_rgb(G.colour(c, pal) or "#000000")]
        if any(len(x) > 2 and x[2] is not None for x in stops):
            k += [v for x in stops for v in (x[0], x[2] if len(x) > 2 and x[2] is not None else 1)]
        radial = g.get("type") == "radial"
        s0 = g["center"] if radial else g["from"]; e0 = [g["center"][0] + g["radius"], g["center"][1]] if radial else g["to"]
        it = {"ty": "gf", "o": {"a": 0, "k": 100 * st.get("opacity", 1)}, "r": 2 if st.get("rule") == "evenodd" else 1, "t": 2 if radial else 1,
              "s": {"a": 0, "k": list(s0)}, "e": {"a": 0, "k": list(e0)}, "g": {"p": len(stops), "k": {"a": 0, "k": k}}}
        if radial:
            it["h"] = {"a": 0, "k": 0}; it["a"] = {"a": 0, "k": 0}
        return it

    def shape_group(strokes, pal, grads=None):
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
            # Lottie draws the first item on top: the outline goes before the fill, as SVG paints it over the fill
            if line:
                it.append({"ty": "st", "c": colour_prop(st.get("stroke"), pal), "o": {"a": 0, "k": 100 * st.get("opacity", 1)}, "w": {"a": 0, "k": st.get("width", 3)}, "lc": 2, "lj": 2})
            if fill and st.get("gradient") and (grads or {}).get(st["gradient"]):
                it.append(grad_fill(grads[st["gradient"]], st, pal))
            elif fill:
                it.append({"ty": "fl", "c": colour_prop(st.get("fill"), pal), "o": {"a": 0, "k": 100 * st.get("opacity", 1)}, "r": 2 if st.get("rule") == "evenodd" else 1})
            it.append({"ty": "tr", "p": {"a": 0, "k": [0, 0]}, "a": {"a": 0, "k": [0, 0]}, "s": {"a": 0, "k": [100, 100]}, "r": {"a": 0, "k": 0}, "o": {"a": 0, "k": 100}})
            items.append({"ty": "gr", "it": it})
        return items[::-1]   # and the last stroke drawn (on top in SVG) first

    def scaled(items, pivot, frs, pid):
        """v0.9 per-part scale on the part's own drawing only (children keep their proportions, as in puppet.js)"""
        sc = [G._scale_of(fr.get("scales"), pid) or [1, 1] for fr in frs]
        if all(v == [1, 1] for v in sc):
            return items
        return [{"ty": "gr", "it": items + [{"ty": "tr", "p": {"a": 0, "k": list(pivot)}, "a": {"a": 0, "k": list(pivot)}, "r": {"a": 0, "k": 0}, "o": {"a": 0, "k": 100},
                                             "s": kf([[round(100 * v[0], 3), round(100 * v[1], 3)] for v in sc])}]}]

    def grow_track(frs, pid):
        """v0.11 recursive scale as the layer's own scale (about its anchor, the pivot)"""
        gs = [float((fr.get("grow") or {}).get(pid, 1)) for fr in frs]
        return kf([[round(100 * g, 3), round(100 * g, 3), 100] for g in gs]) if any(g != 1 for g in gs) else {"a": 0, "k": [100, 100, 100]}

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
      if len(baked["cast"]) > 1:
          SL["prefix"] = re.sub(r"[^a-zA-Z0-9_-]+", "_", p0.get("name") or Path(c["puppet"]).stem.split(".")[0]) + "."
      root = None
      for view, on in _view_masks(p0, frs):
        p = G.in_view(p0, view); pal = p["palette"]
        hip = (p["parts"].get("hip") or {}).get("pivot") or [p["artboard"][0] / 2, p["ground"]]   # as the player: drawn levels have no hip
        root = nid()
        layers.append({"ddd": 0, "ind": root, "ty": 3, "nm": f"{p['name']} root", "sr": 1, "ao": 0, "ip": 0, "op": n, "st": 0, "bm": 0,
                       "ks": {"o": {"a": 0, "k": 0}, "r": {"a": 0, "k": 0},
                              "p": pos([[round(fr["x"], 2), round(fr["y"], 2), 0] for fr in frs]),
                              "a": kf([[round(hip[0] - (fr["offset"] or [0, 0])[0], 2), round(p["ground"] - (fr["offset"] or [0, 0])[1], 2), 0] for fr in frs]),
                              "s": kf([[round(100 * fr["s"] * fr["flip"] * (fr.get("squash") or 1), 2), round(100 * fr["s"], 2), 100] for fr in frs])}})
        ids = {pid: nid() for pid in p["parts"]}
        part_layers = []
        for pid, part in p["parts"].items():
            par = part.get("parent")
            lay = {"ddd": 0, "ind": ids[pid], "ty": 4, "nm": pid if not view else f"{pid}@{view}", "parent": ids[par] if par in ids else root, "sr": 1, "ao": 0, "ip": 0, "op": n, "st": 0, "bm": 0,
                   "ks": {"o": kf([100 * o for o in on], hold=True), "r": kf([round(fr["angles"].get(pid, 0) or 0, 2) for fr in frs]),
                          "p": pos([[round(part["pivot"][0] + ((fr.get("shifts") or {}).get(pid) or [0, 0])[0] + stretch_offset(p, pid, fr)[0], 2),
                                     round(part["pivot"][1] + ((fr.get("shifts") or {}).get(pid) or [0, 0])[1] + stretch_offset(p, pid, fr)[1], 2), 0] for fr in frs]),
                          "a": {"a": 0, "k": [part["pivot"][0], part["pivot"][1], 0]},
                          # v0.11 recursive scale: the layer's own scale about its pivot, which Lottie's parenting carries to every child
                          "s": grow_track(frs, pid)},
                   "shapes": scaled(shape_group(part["strokes"], pal, p.get("gradients")), part["pivot"], frs, pid), "_z": part.get("z", 0)}
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
                       "shapes": shape_group(strokes, pal, p.get("gradients")), "_z": sw.get("z", 40)}
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
    return {"v": "5.7.4", "fr": fps, "ip": 0, "op": n, "w": W, "h": H, "nm": name, "ddd": 0, "assets": assets, "layers": layers, **({"slots": SL["slots"]} if slots else {})}


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


def _grad_sif(g, pal):
    """v0.13 gradient as a Synfig gradient layer (linear or radial), in the same units as the regions"""
    v = lambda p: f"<vector><x>{p[0]:.4f}</x><y>{p[1]:.4f}</y></vector>"
    cols = "".join(f'<color pos="{x[0]:.6f}"><r>{c[0]:.6f}</r><g>{c[1]:.6f}</g><b>{c[2]:.6f}</b><a>{(x[2] if len(x) > 2 and x[2] is not None else 1):.6f}</a></color>'
                   for x in g.get("stops") or [] for c in [G.hex_rgb(G.colour(x[1], pal) or "#000000")])
    grad = f'<param name="gradient"><gradient>{cols}</gradient></param>'
    loop = f'<param name="loop"><bool value="{"true" if g.get("spread") == "repeat" else "false"}"/></param><param name="zigzag"><bool value="false"/></param>'
    onto = '<param name="blend_method"><integer value="13"/></param>'   # "onto": only where the region below is drawn
    if g.get("type") == "radial":
        return f'<layer type="radial_gradient" active="true" version="0.1">{onto}{grad}<param name="center">{v(g["center"])}</param><param name="radius"><real value="{g["radius"]:.4f}"/></param>{loop}</layer>'
    return f'<layer type="linear_gradient" active="true" version="0.0">{onto}{grad}<param name="p1">{v(g["from"])}</param><param name="p2">{v(g["to"])}</param>{loop}</layer>'


def _toon_sif(closed_subs, toon, fps):
    """WP-14 toon shading in Synfig, as puppet.js draws it: over the fill, the shape in the shade colour minus the same
    shape shifted toward the light (in the part's own axes, so the offset is animated as the part turns), at the toon's
    opacity. A group: the shade region, then a cut ("alpha over") by the shifted copy, in a nested animated group."""
    v = lambda p: f"<vector><x>{p[0]:.4f}</x><y>{p[1]:.4f}</y></vector>"
    reg = lambda segs, col: (f'<layer type="region" active="true" version="0.1"><param name="color">{_sif_color(col)}</param>'
                             f'<param name="bline">{_bline(segs, True)}</param></layer>')
    keys, last = [], None
    for fi, o in enumerate(toon["offsets"]):
        if last is None or abs(o[0] - last[0]) + abs(o[1] - last[1]) > 0.02 or fi == len(toon["offsets"]) - 1:
            keys.append((fi, o)); last = o
    wps = "".join(f'<waypoint time="{fi / fps:.5f}s" before="linear" after="linear">{v(o)}</waypoint>' for fi, o in keys)
    off = f'<animated type="vector">{wps}</animated>' if len(keys) > 1 else v(keys[0][1])
    cut = ('<layer type="group" active="true" version="0.3"><param name="blend_method"><integer value="19"/></param>'
           f'<param name="transformation"><composite type="transformation"><offset>{off}</offset><angle><angle value="0"/></angle>'
           f'<skew_angle><angle value="0"/></skew_angle><scale>{v((1, 1))}</scale></composite></param>'
           f'<param name="canvas"><canvas>{"".join(reg(sg, "#000000") for sg in closed_subs)}</canvas></param></layer>')
    return (f'<layer type="group" active="true" version="0.3"><param name="amount"><real value="{toon.get("opacity", 0.26):.3f}"/></param>'
            f'<param name="canvas"><canvas>{"".join(reg(sg, toon.get("shade", "#2a1a10")) for sg in closed_subs)}{cut}</canvas></param></layer>')


def _shapes_sif(strokes, pal, grads=None, toon=None, fps=30):
    out = ""
    for st in strokes:
        fill, line = G.colour(st.get("fill"), pal), G.colour(st.get("stroke"), pal)
        subs = G.parse_path(st.get("d") or "")
        region = lambda segs, extra="": (f'<layer type="region" active="true" version="0.1"><param name="amount"><real value="{st.get("opacity", 1):.3f}"/></param>{extra}'
                                         f'<param name="color">{_sif_color(fill)}</param><param name="bline">{_bline(segs, True)}</param></layer>')
        closed_subs = [segs for segs, closed in subs if closed]
        fx = ""
        if fill and st.get("rule") == "evenodd" and len(closed_subs) > 1:
            # v0.9 even-odd fill: the first contour fills, the others cut holes ("alpha over"), inside a group so the
            # cuts only reach this stroke
            cut = '<param name="blend_method"><integer value="19"/></param>'
            inner = region(closed_subs[0]) + "".join(region(sg, cut) for sg in closed_subs[1:])
            fx = f'<layer type="group" active="true" version="0.3"><param name="canvas"><canvas>{inner}</canvas></param></layer>'
        elif fill:
            fx = "".join(region(sg) for sg in closed_subs)
        if fx and st.get("gradient") and (grads or {}).get(st["gradient"]):
            # v0.13: the gradient goes onto what this stroke filled, inside a group so it reaches nothing below
            fx = f'<layer type="group" active="true" version="0.3"><param name="canvas"><canvas>{fx}{_grad_sif(grads[st["gradient"]], pal)}</canvas></param></layer>'
        if fx and toon and st.get("d") and (st.get("opacity") is None or st["opacity"] > 0.9):
            fx += _toon_sif(closed_subs, toon, fps)
        out += fx
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


def _toon_spec(toon):
    """a shot's style.toon (true or an object) with puppet.js's defaults; None when off (never an empty, falsy dict)"""
    if not toon:
        return None
    return {"dir": [-0.6, -0.8], "d": 11, "shade": "#2a1a10", "opacity": 0.26, **(toon if isinstance(toon, dict) else {})}


def _toon_offsets(toon, mats):
    """per frame, the toon's offset toward the light in a part's own axes (puppet.js toonSVG): the world direction
    through the transpose of the part's matrix (without the placement, as the player computes it)"""
    lx, ly = toon.get("dir") or [-0.6, -0.8]; n_ = math.hypot(lx, ly) or 1; d = toon.get("d", 11)
    wx, wy = lx / n_ * d, ly / n_ * d
    return [(m[0] * wx + m[1] * wy, m[2] * wx + m[3] * wy) for m in mats]


def to_synfig(baked, size, bg_png=None, transparent=False, assets_dir=None, toon=None):
    """toon: the shot's style.toon (WP-14), drawn as puppet.js draws it"""
    W, H = size
    toon = _toon_spec(toon)
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
        # a key is dropped only if the straight line from the last kept key to the next one reproduces it AND every key
        # dropped since (testing only the neighbours let a slow ramp lose all its keys: a head growing over 1.5 s
        # jumped straight from its first size to its last, WP-11)
        out, last = [keys[0]], 0
        for i in range(1, len(keys) - 1):
            f0, v0 = keys[last]; f2, v2 = keys[i + 1]
            ok = True
            for j in range(last + 1, i + 1):
                fj, vj = keys[j]; k = (fj - f0) / (f2 - f0)
                if max(abs(a_ + (c_ - a_) * k - b_) for a_, b_, c_ in zip(v0, vj, v2)) > tol:
                    ok = False; break
            if not ok:
                out.append(keys[i]); last = i
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
        Ms = [G.part_matrices(p, fr["angles"], fr.get("shifts"), fr.get("scales"), fr.get("grow")) for fr in frs]
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
                    tz = {**toon, "offsets": _toon_offsets(toon, [Ms[i][pid] for i in range(n)])} if toon and not part.get("bend") else None   # (bendy parts: as puppet.js, unshaded)
                    items.append((zv, f'<layer type="group" active="true" version="0.3" desc="{pid}">{amount(vz)}<param name="origin"><vector><x>0</x><y>0</y></vector></param>{anim_transform(mats, vz)}<param name="canvas"><canvas>{_raster_sif(part["strokes"], assets_dir)}{_shapes_sif(part["strokes"], pal, p.get("gradients"), tz, fps)}</canvas></param></layer>'))
        for sid, sw in (p.get("swaps") or {}).items():
            for shape, strokes in sw["shapes"].items():
                if not strokes:
                    continue
                vis = [1 if G.chosen_swaps(p, fr).get(sid) == shape and o else 0 for fr, o in zip(frs, on)]
                if not any(vis):
                    continue
                if assets_dir and (sw.get("raster_shapes") or {}).get(shape):
                    strokes = sw["raster_shapes"][shape]   # WP-14: motion effects as images in Synfig (its XML parser stops at 10 MB)
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
                        tz = None   # (puppet.js shades parts only, not swap drawings)
                        items.append((zv, f'<layer type="group" active="true" version="0.3" desc="{sid}:{shape}">{amount(vz)}<param name="origin"><vector><x>0</x><y>0</y></vector></param>{anim_transform(mats, vz)}<param name="canvas"><canvas>{_raster_sif(strokes, assets_dir)}{_shapes_sif(strokes, pal, p.get("gradients"), tz, fps)}</canvas></param></layer>'))
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


def _toon_band(polys, off):
    """WP-14 toon shading as geometry: the shape minus itself shifted toward the light (screen offset), as polygons"""
    from shapely.geometry import Polygon
    from shapely.affinity import translate
    from shapely.ops import unary_union
    shp = unary_union([Polygon(q).buffer(0) for q in polys if len(q) >= 3])
    band = shp.difference(translate(shp, off[0], off[1]))
    geoms = [band] if band.geom_type == "Polygon" else list(getattr(band, "geoms", []))
    out = []
    for g in geoms:
        if g.is_empty or g.area < 4:
            continue
        rings = [list(g.exterior.coords)[:-1]] + [list(r.coords)[:-1] for r in g.interiors]
        out.append(_keyhole(rings) if len(rings) > 1 else rings[0])
    return out


def to_gp_frames(baked, size, per=6, toon=None):
    """per frame, a z-ordered list of world-space strokes (polylines) with fill/line colours, for blender_gp.py.
    toon: the shot's style.toon (WP-14): a filled stroke of a rigid part gets its shade band (the shape minus itself
    shifted toward the light) as an extra fill between its fill and its outline, as puppet.js draws it"""
    toon = _toon_spec(toon)
    out = {"fps": baked["fps"], "frames": baked["frames"], "size": list(size), "palette": {}, "data": []}
    pals = {}
    for f in range(baked["frames"]):
        strokes = []
        for c in baked["cast"]:
            p = pals.setdefault(c["puppet"], _load(c["puppet"])); fr = c["frames"][f]; p = G.in_view(p, fr.get("view")); pal = p["palette"]
            M = G.part_matrices(p, fr["angles"], fr.get("shifts"), fr.get("scales"), fr.get("grow")); R = G.root_matrix(p, fr)
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
                items.append(((fr.get("z") or {}).get(pid, part.get("z", 0)), G.mul(R, M[pid]), part["strokes"], M[pid]))
            for sid, shape in sw.items():
                s = p["swaps"][sid]; m = G.mul(R, M.get(s["anchor"], G.I))
                if (fr.get("shifts") or {}).get("@" + sid):
                    m = G.mul(m, [1, 0, 0, 1, *fr["shifts"]["@" + sid]])
                if sid == "pupils" and fr.get("look"):
                    m = G.mul(m, [1, 0, 0, 1, fr["look"][0] * s.get("movable", 8), fr["look"][1] * s.get("movable", 8) * 0.7])
                items.append((s.get("z", 40), m, s["shapes"][shape], None))
            items.sort(key=lambda x: x[0])
            for it in items:
                _, m, sts, Mpart = (it + (None,))[:4] if len(it) == 3 else it
                for st in sts:
                    if toon and Mpart is not None and not isinstance(m, tuple) and st.get("d") and st.get("fill") and not st.get("image") \
                            and (st.get("opacity") is None or st["opacity"] > 0.9) and G.colour(st.get("fill"), pal):
                        # the band: offset v in the part's axes (puppet.js: through the transpose of the part's matrix), then
                        # carried to the screen by the part and placement matrices, as the SVG renderer shifts its copy
                        lx, ly = toon.get("dir") or [-0.6, -0.8]; nn = math.hypot(lx, ly) or 1; dd = toon.get("d", 11)
                        wx, wy = lx / nn * dd, ly / nn * dd
                        vx, vy = Mpart[0] * wx + Mpart[1] * wy, Mpart[2] * wx + Mpart[3] * wy
                        off = (m[0] * vx + m[2] * vy, m[1] * vx + m[3] * vy)
                        subs_ = G.parse_path(st["d"])
                        polys = [[G.apply(m, q) for q in G.sample(segs, per)] for segs, c in subs_ if c]
                        line_ = G.colour(st.get("stroke"), pal)
                        for q in polys:   # the fill first, then the band, then the outline
                            strokes.append({"pts": [[round(x, 1), round(y, 1)] for x, y in q], "closed": True, "fill": G.colour(st["fill"], pal), "line": None,
                                            "w": st.get("width", 3) * fr.get("s", 1), "op": st.get("opacity", 1)})
                        for b in (_toon_band(polys, off) if polys else []):
                            strokes.append({"pts": [[round(x, 1), round(y, 1)] for x, y in b], "closed": True, "fill": toon.get("shade", "#2a1a10"), "line": None,
                                            "w": 0, "op": toon.get("opacity", 0.26)})
                        if line_:
                            for segs, closed in subs_:
                                strokes.append({"pts": [[round(x, 1), round(y, 1)] for x, y in (G.apply(m, q) for q in G.sample(segs, per))], "closed": closed,
                                                "fill": None, "line": line_, "w": st.get("width", 3) * fr.get("s", 1), "op": st.get("opacity", 1)})
                        continue
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
