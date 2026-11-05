"""OpenUSD export of a shot (WP-42): the baked animation (tools/bake.mjs, the same frames every renderer draws) as a
USD stage any DCC or Hydra viewer opens: usdview, Blender, Houdini, Maya, Omniverse.

    /Film                 (the screen: y up, 1 unit = 1 frame pixel; defaultPrim)
      /<cast>/<part>      an Xform per part, its transform sampled every frame (the part's matrix in the frame, with
                          the camera folded in); visibility sampled where a swap drawing replaces it
        /fill_<i>         a Mesh (the fill, ear-clipped triangles) and /line_<i> BasisCurves (the outline, with width)
        /image_<i>        a textured quad for raster drawings (UsdPreviewSurface, the PNG beside the .usda)
      /<cast>/at_<swap>/<shape>   swap drawings, each shown only on its frames
    /Camera               orthographic, framing the frame exactly

Layer order is depth: a part sits at z = its layer (0.1 units a step), strokes inside it 0.001 apart, so a viewer
looking down -z paints them in the player's order. A bendy limb follows its parent and its points are sampled every
frame, bent as the player bends them. Each view a character uses (a side view while walking) is its own set of parts
under /<cast>/view_<name>, shown on that view's frames.
"""
import base64
import re
from pathlib import Path

from . import geom as G


def _name(s):
    s = re.sub(r"[^A-Za-z0-9_]", "_", str(s))
    return s if s and not s[0].isdigit() else "_" + s


def _m4(m, z=0.0):
    """a 2D affine [a, b, c, d, e, f] (x' = a x + c y + e) as a USD row-vector 4x4, lifted to depth z"""
    from pxr import Gf
    a, b, c, d, e, f = m
    return Gf.Matrix4d(a, b, 0, 0, c, d, 0, 0, 0, 0, 1, 0, e, f, z, 1)


def _area(poly):
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1])) / 2


def earclip(poly):
    """triangles (index triples) of a simple polygon by ear clipping (O(n^2), fine for drawing outlines)"""
    pts = [p for i, p in enumerate(poly) if i == 0 or abs(p[0] - poly[i - 1][0]) + abs(p[1] - poly[i - 1][1]) > 1e-6]
    if len(pts) > 2 and abs(pts[0][0] - pts[-1][0]) + abs(pts[0][1] - pts[-1][1]) < 1e-6:
        pts = pts[:-1]
    idx = list(range(len(pts)))
    if _area(pts) < 0:
        idx.reverse()
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    def inside(p, a, b, c):
        return cross(a, b, p) >= 0 and cross(b, c, p) >= 0 and cross(c, a, p) >= 0
    tris, guard = [], 0
    while len(idx) > 3 and guard < 10 * len(pts) ** 2:
        guard += 1; n = len(idx); found = False
        for k in range(n):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % n]
            a, b, c = pts[i0], pts[i1], pts[i2]
            if cross(a, b, c) <= 1e-9:
                continue
            if any(inside(pts[j], a, b, c) for j in idx if j not in (i0, i1, i2)):
                continue
            tris.append((i0, i1, i2)); idx.pop(k); found = True; break
        if not found:   # degenerate leftovers (collinear runs, slight self-touching): fan them
            break
    if len(idx) >= 3:
        tris += [(idx[0], idx[k], idx[k + 1]) for k in range(1, len(idx) - 1)]
    return pts, tris


def _lin(hexv):
    r, g, b = G.hex_rgb(hexv)
    f = lambda v: v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4   # displayColor is linear
    return (f(r), f(g), f(b))


def _geometry(stage, path, strokes, pal, tex_dir, per=6, bend=None):
    """a part's (or swap shape's) drawing in its own rest units, under prim `path`. bend: for a bendy limb, per frame
    (pivot, axis, width, theta), and its points are sampled every frame (in its parent's space) as the player bends them"""
    from pxr import UsdGeom, UsdShade, Sdf, Gf, Vt
    from . import exporters as X
    for i, st in enumerate(strokes):
        z = 0.001 * i
        if st.get("image") and not st.get("d"):   # a raster drawing: a textured quad
            fn = Path(tex_dir) / f"{_name(path.replace('/', '_'))}_{i}.png"
            fn.write_bytes(base64.b64decode(st["image"].split(",", 1)[1]))
            x0, y0, w, h = st["x"], st["y"], st["w"], st["h"]
            q = UsdGeom.Mesh.Define(stage, f"{path}/image_{i}")
            q.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(x0, y0, z), Gf.Vec3f(x0 + w, y0, z), Gf.Vec3f(x0 + w, y0 + h, z), Gf.Vec3f(x0, y0 + h, z)]))
            q.CreateFaceVertexCountsAttr([4]); q.CreateFaceVertexIndicesAttr([0, 1, 2, 3]); q.CreateDoubleSidedAttr(True)
            st_ = UsdGeom.PrimvarsAPI(q).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex)
            st_.Set(Vt.Vec2fArray([Gf.Vec2f(0, 1), Gf.Vec2f(1, 1), Gf.Vec2f(1, 0), Gf.Vec2f(0, 0)]))   # (image rows run down the frame)
            mat = UsdShade.Material.Define(stage, f"{path}/image_{i}_mat")
            sh = UsdShade.Shader.Define(stage, f"{path}/image_{i}_mat/surface"); sh.CreateIdAttr("UsdPreviewSurface")
            tx = UsdShade.Shader.Define(stage, f"{path}/image_{i}_mat/texture"); tx.CreateIdAttr("UsdUVTexture")
            tx.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(f"./{Path(tex_dir).name}/{fn.name}")
            rd = UsdShade.Shader.Define(stage, f"{path}/image_{i}_mat/st"); rd.CreateIdAttr("UsdPrimvarReader_float2")
            rd.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")
            tx.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(rd.ConnectableAPI(), "result")
            sh.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(tx.ConnectableAPI(), "rgb")
            sh.CreateInput("opacity", Sdf.ValueTypeNames.Float).ConnectToSource(tx.ConnectableAPI(), "a")
            mat.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(), "surface")
            UsdShade.MaterialBindingAPI.Apply(q.GetPrim()).Bind(mat)
            continue
        subs = G.parse_path(st.get("d") or "")
        if not subs:
            continue
        fill, line = G.colour(st.get("fill"), pal), G.colour(st.get("stroke"), pal)
        closed = [[tuple(p) for p in G.sample(segs, per)] for segs, c in subs if c]
        if fill and closed:
            polys = [X._keyhole(g) for g in X.evenodd_groups(closed)] if st.get("rule") == "evenodd" and len(closed) > 1 else closed
            P, idx, cnt = [], [], []
            for poly in polys:
                pts, tris = earclip(poly); base = len(P); P += pts
                for t in tris:
                    idx += [base + t[0], base + t[1], base + t[2]]; cnt.append(3)
            if cnt:
                m = UsdGeom.Mesh.Define(stage, f"{path}/fill_{i}")
                pa = m.CreatePointsAttr()
                if bend:
                    for f, (piv, ax, wd, th) in enumerate(bend):
                        pa.Set(Vt.Vec3fArray([Gf.Vec3f(*G.bend_point(q, piv, ax, wd, th), z) for q in P]), f)
                else:
                    pa.Set(Vt.Vec3fArray([Gf.Vec3f(x, y, z) for x, y in P]))
                m.CreateFaceVertexCountsAttr(cnt); m.CreateFaceVertexIndicesAttr(idx)
                m.CreateDoubleSidedAttr(True); m.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
                m.CreateDisplayColorAttr([Gf.Vec3f(*_lin(fill))])
                if st.get("opacity") is not None and st["opacity"] < 1:
                    m.CreateDisplayOpacityAttr([float(st["opacity"])])
        if line:
            curves = [([tuple(p) for p in G.sample(segs, per)], c) for segs, c in subs]
            cv = UsdGeom.BasisCurves.Define(stage, f"{path}/line_{i}")
            cv.CreateTypeAttr(UsdGeom.Tokens.linear)
            pts = [q for pl, c in curves for q in (pl + [pl[0]] if c else pl)]
            ca = cv.CreatePointsAttr()
            if bend:
                for f, (piv, ax, wd, th) in enumerate(bend):
                    ca.Set(Vt.Vec3fArray([Gf.Vec3f(*G.bend_point(q, piv, ax, wd, th), z + 0.0005) for q in pts]), f)
            else:
                ca.Set(Vt.Vec3fArray([Gf.Vec3f(x, y, z + 0.0005) for x, y in pts]))
            cv.CreateCurveVertexCountsAttr([len(pl) + (1 if c else 0) for pl, c in curves])
            cv.CreateWidthsAttr([float(st.get("width", 3))]); cv.SetWidthsInterpolation(UsdGeom.Tokens.constant)
            cv.CreateDisplayColorAttr([Gf.Vec3f(*_lin(line))])


def to_usd(baked, size, path, per=6):
    """baked: tools/bake.mjs output; size [W, H]; path: .usda or .usd -> summary"""
    from pxr import Usd, UsdGeom, Gf, Sdf
    W, H = size; n = baked["frames"]; fps = baked["fps"]
    path = Path(path); tex = path.with_suffix("").with_name(path.stem + "_textures"); tex.mkdir(parents=True, exist_ok=True)
    stage = Usd.Stage.CreateNew(str(path))
    stage.SetStartTimeCode(0); stage.SetEndTimeCode(max(0, n - 1)); stage.SetTimeCodesPerSecond(fps); stage.SetFramesPerSecond(fps)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y); UsdGeom.SetStageMetersPerUnit(stage, 0.001)
    root = UsdGeom.Xform.Define(stage, "/Film"); stage.SetDefaultPrim(root.GetPrim())
    root.AddTransformOp().Set(Gf.Matrix4d(1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 1, 0, 0, H, 0, 1))   # frame pixels (y down) -> y up
    cam = UsdGeom.Camera.Define(stage, "/Camera")
    cam.CreateProjectionAttr(UsdGeom.Tokens.orthographic)
    cam.CreateHorizontalApertureAttr(W * 10.0); cam.CreateVerticalApertureAttr(H * 10.0)   # (apertures in tenths of a unit)
    cam.CreateClippingRangeAttr(Gf.Vec2f(0.1, 10000)); cam.AddTranslateOp().Set(Gf.Vec3d(W / 2, H / 2, 1000))
    summary = {"cast": [], "frames": n, "fps": fps, "size": [W, H], "parts": 0, "swap_shapes": 0}
    used = set()
    for ci, c in enumerate(baked["cast"]):
        from . import exporters as X
        p0 = X._load(c["puppet"])
        pal = p0.get("palette") or {}
        nm = _name(c.get("name") or Path(c["puppet"]).stem.split(".")[0])
        while nm in used:
            nm += "_"
        used.add(nm); base0 = f"/Film/{nm}"; UsdGeom.Xform.Define(stage, base0)
        frs = c["frames"]
        views = (p0.get("views") or {})
        vkey = lambda fr: fr.get("view") if fr.get("view") in views else None
        for view in dict.fromkeys(vkey(fr) for fr in frs):   # each view the cast uses: its own parts, shown on its frames
            p = G.in_view(p0, view); base = base0 if view is None else f"{base0}/view_{_name(view)}"
            if view is not None:
                UsdGeom.Xform.Define(stage, base)
            on = [vkey(fr) == view for fr in frs]
            mats = [G.part_matrices(p, fr["angles"], fr.get("shifts"), fr.get("scales"), fr.get("grow")) for fr in frs]
            roots = [G.root_matrix(p, fr) for fr in frs]
            sws = [G.chosen_swaps(p, fr) for fr in frs]
            for pid, part in p["parts"].items():
                if not part.get("strokes"):
                    continue
                x = UsdGeom.Xform.Define(stage, f"{base}/{_name(pid)}"); op = x.AddTransformOp(); vis = x.CreateVisibilityAttr()
                bendy = bool(part.get("bend")) and part.get("parent") in p["parts"]
                ax = G.part_axis(part) if bendy else None; bend = [] if bendy else None
                for f, fr in enumerate(frs):
                    zl = (fr.get("z") or {}).get(pid, part.get("z", 0)) * 0.1 + ci * 100
                    if bendy and not (fr.get("shifts") or {}).get(pid):   # as the player and Grease Pencil bend it: in the parent's space
                        op.Set(_m4(G.mul(roots[f], mats[f][part["parent"]]), zl), f)
                        bend.append((part["pivot"], ax, part["bend"].get("width", 40), fr["angles"].get(pid, 0) or 0))
                    else:
                        op.Set(_m4(G.mul(roots[f], mats[f][pid]), zl), f)
                        if bendy:
                            bend.append((part["pivot"], ax, part["bend"].get("width", 40), 0))
                    hidden = not on[f] or fr.get("hidden") or any(s_.get("replaces") == pid and sws[f].get(sid) for sid, s_ in (p.get("swaps") or {}).items())
                    vis.Set(UsdGeom.Tokens.invisible if hidden else UsdGeom.Tokens.inherited, f)
                _geometry(stage, f"{base}/{_name(pid)}", part["strokes"], pal, tex, per, bend); summary["parts"] += 1
                summary["bendy"] = summary.get("bendy", 0) + (1 if bendy else 0)
            for sid, sw in (p.get("swaps") or {}).items():
                sp = f"{base}/at_{_name(sid)}"; x = UsdGeom.Xform.Define(stage, sp); op = x.AddTransformOp()
                for f, fr in enumerate(frs):
                    m = G.mul(roots[f], mats[f].get(sw["anchor"], G.I))
                    if (fr.get("shifts") or {}).get("@" + sid):
                        m = G.mul(m, [1, 0, 0, 1, *fr["shifts"]["@" + sid]])
                    if sid == "pupils" and fr.get("look"):
                        m = G.mul(m, [1, 0, 0, 1, fr["look"][0] * sw.get("movable", 8), fr["look"][1] * sw.get("movable", 8) * 0.7])
                    op.Set(_m4(m, (fr.get("z") or {}).get("@" + sid, sw.get("z", 40)) * 0.1 + ci * 100), f)
                for shape, strokes in (sw.get("shapes") or {}).items():
                    if not strokes:
                        continue
                    spath = f"{sp}/{_name(shape)}"; UsdGeom.Xform.Define(stage, spath)
                    vis = UsdGeom.Imageable(stage.GetPrimAtPath(spath)).CreateVisibilityAttr()
                    for f, fr in enumerate(frs):
                        vis.Set(UsdGeom.Tokens.inherited if on[f] and sws[f].get(sid) == shape and not fr.get("hidden") else UsdGeom.Tokens.invisible, f)
                    _geometry(stage, spath, strokes, pal, tex, per); summary["swap_shapes"] += 1
            summary.setdefault("views", []).append(view or "default")
        summary["cast"].append(nm)
    stage.GetRootLayer().Save()
    return summary
