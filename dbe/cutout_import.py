"""Cut-out rig import (plan 1.3): a Blender cut-out rig becomes a Doodleberry puppet with raster parts.

    python dbe/cutout_import.py EXTRACT_DIR OUT.puppet.json SPEC.json      (EXTRACT_DIR from dbe/blender_cutout.py)

Every textured mesh is rasterised from its triangles and UVs (no renderer needed), assigned to a template part by the
bone that carries it, and layered by its depth. Bones that are not template parts (hair locks, skirt panels, tails)
become extra parts with springs. Variants (phonemes, blinks, hand sprites) become swap shapes: the changed region of
the head (or hand) is cut out of the variant state and drawn over the base, so jaw and lid deformations come along.

SPEC: {"name": "Pepper", "template": "humanoid", "height": 900, "px": 2,
       "mouth": {"closed": "mouth/12", "small": "mouth/2", ...}, "eyes": {"half": "eyes/half", "closed": "eyes/closed"},
       "pupils": ["CTRL-eye.L", "CTRL-eye.R", "CTRL-eye-spec.L", "CTRL-eye-spec.R"], "movable": 3,
       "hands": {"hand_R_pose": {"point": "hand/3"}}, "bone_map": {"Bone.002": "hair_back"}, "springs": true,
       "meta": {"author": "...", "license": "CC-BY-4.0", "source_url": "...", "credit": "..."}}
"""
import base64
import io
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def load(ext_dir):
    d = Path(ext_dir)
    rig = json.loads((d / "rig.json").read_text())
    ims = {n: np.asarray(Image.open(d / v["file"]).convert("RGBA")).astype(np.float32) / 255 for n, v in rig["images"].items()}
    return rig, ims


def sample(img, u, v):
    """bilinear texture lookup; u, v arrays in 0..1 (v up)"""
    H, W = img.shape[:2]
    x = np.clip(u * W - 0.5, 0, W - 1.001); y = np.clip((1 - v) * H - 0.5, 0, H - 1.001)
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int); fx = (x - x0)[:, None]; fy = (y - y0)[:, None]
    a = img[y0, x0]; b = img[y0, x0 + 1]; c = img[y0 + 1, x0]; d = img[y0 + 1, x0 + 1]
    # premultiplied blend so transparent texels don't bleed colour
    pm = lambda t: np.concatenate([t[:, :3] * t[:, 3:], t[:, 3:]], 1)
    o = pm(a) * (1 - fx) * (1 - fy) + pm(b) * fx * (1 - fy) + pm(c) * (1 - fx) * fy + pm(d) * fx * fy
    al = o[:, 3:]
    return np.concatenate([np.where(al > 1e-4, o[:, :3] / np.maximum(al, 1e-4), 0), al], 1)


BODY_WORDS = ("arm", "leg", "spine", "chest", "hips", "foot", "toe", "torso", "neck")


def match_materials(rig, ims, overrides=None):
    """2.7x files lose their texture slots in Blender 2.8+: give each material the image whose name matches the
    material or the bones its meshes ride on (hand, lips, head, body), and whose alpha covers the UVs it uses"""
    out = {}
    for mat in rig["materials"]:
        if overrides and mat in overrides:
            out[mat] = {"image": overrides[mat], "coverage": None, "by": "spec"}; continue
        users = [o for o in rig["objects"] if any(t["mat"] == mat for t in o["tris"])]
        words = {w: 1.0 for w in set(re.findall(r"[a-z]{3,}", mat.lower())) - {"material"}}
        for o in users:  # each user mesh votes for the words of its bone
            b = (o["bone"] or "").lower()
            for w in ("hand", "lips", "head", "eye", "hair"):
                if w in b:
                    words[w] = words.get(w, 0) + 1 / len(users)
            if any(w in b for w in BODY_WORDS):
                words["body"] = words.get("body", 0) + 1 / len(users)
        uvs = np.array([[p[2], p[3]] for o in users for t in o["tris"] if t["mat"] == mat for p in t["p"]] +
                       [[(t["p"][0][2] + t["p"][1][2] + t["p"][2][2]) / 3, (t["p"][0][3] + t["p"][1][3] + t["p"][2][3]) / 3]
                        for o in users for t in o["tris"] if t["mat"] == mat])
        best, score, cov = None, -1, 0
        for n, im in ims.items():
            if "rim" in n.lower():
                continue
            c = float(sample(im, uvs[:, 0], uvs[:, 1])[:, 3].mean()) if len(uvs) else 0
            name_hit = sum(v for w, v in words.items() if w in n.lower())
            sc = c + name_hit
            if sc > score:
                best, score, cov = n, sc, c
        out[mat] = {"image": best, "coverage": round(cov, 3), "words": {k: round(v, 2) for k, v in words.items()}}
    return out


class Frame:
    """Blender front-view units -> artboard units"""
    def __init__(self, objs, height):
        P = np.array([p[:2] for o in objs for t in o["tris"] for p in t["p"]])
        self.xmin, self.zmin = P.min(0); xmax, zmax = P.max(0)
        self.k = height / (zmax - self.zmin)
        self.margin = 40
        self.W = round(max(600, (xmax - self.xmin) * self.k + 2 * self.margin))
        self.ground = round(self.margin + height, 1)
        self.H = round(self.ground + 20)
        self.cx = (self.xmin + xmax) / 2

    def xy(self, x, z):
        return (self.W / 2 + (x - self.cx) * self.k, self.ground - (z - self.zmin) * self.k)


def raster(objs, F, mats, ims, px):
    """rasterise mesh records (list) together into one RGBA image; returns (image, x, y) in artboard units or None"""
    tris = [(t, o["depth"]) for o in objs for t in o["tris"]]
    if not tris:
        return None
    pts = np.array([F.xy(p[0], p[1]) for t, _ in tris for p in t["p"]])
    x0, y0 = np.floor(pts.min(0)) - 1; x1, y1 = np.ceil(pts.max(0)) + 1
    Wp, Hp = int((x1 - x0) * px), int((y1 - y0) * px)
    if Wp <= 0 or Hp <= 0:
        return None
    acc = np.zeros((Hp, Wp, 4), np.float32)
    for t, _ in sorted(tris, key=lambda q: -q[1]):  # far first
        img = ims.get(mats.get(t["mat"], {}).get("image"))
        if img is None:
            continue
        P = np.array([[(F.xy(p[0], p[1])[0] - x0) * px, (F.xy(p[0], p[1])[1] - y0) * px] for p in t["p"]])
        UV = np.array([[p[2], p[3]] for p in t["p"]])
        bx0, by0 = np.maximum(np.floor(P.min(0)).astype(int), 0); bx1, by1 = np.minimum(np.ceil(P.max(0)).astype(int) + 1, [Wp, Hp])
        if bx1 <= bx0 or by1 <= by0:
            continue
        gx, gy = np.meshgrid(np.arange(bx0, bx1) + 0.5, np.arange(by0, by1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = P
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-9:
            continue
        l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
        l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / den
        l3 = 1 - l1 - l2
        e = -1e-4
        inside = (l1 >= e) & (l2 >= e) & (l3 >= e)
        if not inside.any():
            continue
        u = l1[inside] * UV[0, 0] + l2[inside] * UV[1, 0] + l3[inside] * UV[2, 0]
        v = l1[inside] * UV[0, 1] + l2[inside] * UV[1, 1] + l3[inside] * UV[2, 1]
        c = sample(img, u, v)
        yy, xx = gy[inside].astype(int), gx[inside].astype(int)
        dst = acc[yy, xx]; a = c[:, 3:]
        out_a = a + dst[:, 3:] * (1 - a)
        out_c = (c[:, :3] * a + dst[:, :3] * dst[:, 3:] * (1 - a)) / np.maximum(out_a, 1e-6)
        acc[yy, xx] = np.concatenate([out_c, out_a], 1)
    im = Image.fromarray((np.clip(acc, 0, 1) * 255).astype(np.uint8), "RGBA")
    return im, float(x0), float(y0)


def stroke(res, px, crop=None):
    if res is None:
        return None
    im, x0, y0 = res
    bb = crop or im.getchannel("A").point(lambda v: 255 if v > 3 else 0).getbbox()
    if not bb:
        return None
    c = im.crop(bb); buf = io.BytesIO(); c.save(buf, "PNG", optimize=True)
    return {"image": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(),
            "x": round(x0 + bb[0] / px, 2), "y": round(y0 + bb[1] / px, 2), "w": round((bb[2] - bb[0]) / px, 2), "h": round((bb[3] - bb[1]) / px, 2)}


def mesh_stroke(tris, F, img, weights_of, px, subdivide=1, smooth=3):
    """skinned triangles -> a v0.5 mesh stroke: shared vertices, texture crop, per-vertex part weights"""
    H, W = img.shape[:2]
    keyv, verts, uv, wts, tri_ix = {}, [], [], [], []
    for t in tris:
        ix = []
        for p, w in zip(t["p"], t["w"]):
            k = (round(p[0], 4), round(p[1], 4), round(p[2], 4), round(p[3], 4))
            if k not in keyv:
                keyv[k] = len(verts); verts.append(F.xy(p[0], p[1])); uv.append((p[2] * W, (1 - p[3]) * H)); wts.append(weights_of(w))
            ix.append(keyv[k])
        tri_ix.append(ix)
    for _ in range(subdivide):  # midpoint subdivision: four triangles per triangle, attributes interpolated
        mid = {}

        def midpoint(i, j):
            k = (min(i, j), max(i, j))
            if k not in mid:
                mid[k] = len(verts)
                verts.append(((verts[i][0] + verts[j][0]) / 2, (verts[i][1] + verts[j][1]) / 2))
                uv.append(((uv[i][0] + uv[j][0]) / 2, (uv[i][1] + uv[j][1]) / 2))
                acc = {}
                for q, w in wts[i] + wts[j]:
                    acc[q] = acc.get(q, 0) + w / 2
                wts.append([[q, w] for q, w in acc.items()])
            return mid[k]
        new = []
        for a, b, c in tri_ix:
            ab, bc, ca = midpoint(a, b), midpoint(b, c), midpoint(c, a)
            new += [[a, ab, ca], [ab, b, bc], [ca, bc, c], [ab, bc, ca]]
        tri_ix = new
    if smooth:  # diffuse weights over the mesh so bends become arcs instead of kinks (boundary of the mesh included)
        nb = [set() for _ in verts]
        for a, b, c in tri_ix:
            nb[a] |= {b, c}; nb[b] |= {a, c}; nb[c] |= {a, b}
        WD = [dict((q, w) for q, w in ws) for ws in wts]
        for _ in range(smooth):
            nxt = []
            for i, ws in enumerate(WD):
                acc = {q: 0.5 * w for q, w in ws.items()}
                for j in nb[i]:
                    for q, w in WD[j].items():
                        acc[q] = acc.get(q, 0) + 0.5 * w / len(nb[i])
                nxt.append(acc)
            WD = nxt
        wts = []
        for ws in WD:
            tot = sum(ws.values()) or 1
            wts.append([[q, round(w / tot, 3)] for q, w in sorted(ws.items(), key=lambda kv: -kv[1]) if w / tot >= 0.02][:4])
    U = np.array(uv)
    x0, y0 = np.maximum(np.floor(U.min(0)) - 2, 0).astype(int); x1, y1 = np.minimum(np.ceil(U.max(0)) + 2, [W, H]).astype(int)
    crop = Image.fromarray((np.clip(img[y0:y1, x0:x1], 0, 1) * 255).astype(np.uint8), "RGBA")
    buf = io.BytesIO(); crop.save(buf, "PNG", optimize=True)
    return {"mesh": {"image": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(), "iw": int(x1 - x0), "ih": int(y1 - y0),
                     "verts": [[round(v[0], 2), round(v[1], 2)] for v in verts], "uv": [[round(u - x0, 2), round(v - y0, 2)] for u, v in uv],
                     "tris": tri_ix, "weights": wts, "grow": 1.1}}


# ---------------- bones -> parts ----------------
TEMPLATE_RULES = [(r"hand", "hand"), (r"fore.?arm|lower.?arm", "forearm"), (r"upper.?arm|^(def-)?arm", "upperarm"),
                  (r"leg\.0*1\b|shin|calf|lower.?leg", "shin"), (r"leg\.0*0\b|thigh|upper.?leg", "thigh"), (r"foot|toe", "foot"),
                  (r"head", "head"), (r"neck", "neck"), (r"chest|spine|torso", "torso"), (r"hips|pelvis", "hip")]
SIDED = {"hand", "forearm", "upperarm", "shin", "thigh", "foot"}


def part_for_bone(name, head_x, cx):
    low = name.lower()
    if not low.startswith(("def", "mch-head", "mch-lips", "ctrl-eye", "ctrl-nose")) and not re.match(r"^(def-)?(hips|spine|chest|neck|head)", low):
        return None
    for pat, part in TEMPLATE_RULES:
        if re.search(pat, low):
            if part in SIDED:
                m = re.search(r"[._-]([LR])(?:\.\d+)?$", name)
                if m:  # Blender .L is the character's left = screen right = template R (front)
                    return f"{part}_{'R' if m.group(1) == 'L' else 'L'}"
                return f"{part}_{'R' if head_x >= cx else 'L'}"
            return part
    return None


def build(ext_dir, spec):
    rig, ims = load(ext_dir)
    px = spec.get("px", 2)
    objs = rig["objects"]; bones = rig["bones"]
    mats = match_materials(rig, ims, spec.get("materials"))
    F = Frame(objs, spec.get("height", 900))
    cx = F.cx
    bone_map = dict(spec.get("bone_map") or {})
    T = json.loads((Path(__file__).resolve().parent.parent / "puppet" / "templates" / f"{spec.get('template', 'humanoid')}.json").read_text())
    tparts = {p["id"]: p for p in T["parts"]}
    pupil_bones = set(spec.get("pupils") or [])
    tpl_of = lambda b: bone_map.get(b) if b in bone_map else part_for_bone(b, bones[b]["head"][0], cx)

    def chain_root(b):
        """walk up while the parent is not a template bone: the top of a hair lock or skirt panel chain"""
        while bones[b]["parent"] and not tpl_of(bones[b]["parent"]):
            b = bones[b]["parent"]
        return b

    def chainy(b):
        low = b.lower()
        return bool((low.startswith("def") or re.match(r"^bone", low) or "hair" in low) and not low.startswith(("ctrl", "mch"))
                    and bones[b].get("deform", True) and not tpl_of(b))

    def clean(b):
        nm = re.sub(r"^(ctrl|mch|def)[-_.]?", "", b.lower())
        return re.sub(r"[^a-z0-9]+", "_", nm).strip("_") or "chain"

    def owner(b):
        """bone -> (part id, chain bone or None). Each deforming chain bone (hair lock, skirt panel, tail segment) is its
        own spring part, so meshes weighted along the chain bend smoothly"""
        if not b:
            return "hip", None
        if tpl_of(b):
            return tpl_of(b), None
        if spec.get("springs", True) and chainy(b):
            return clean(b), b
        q = b
        while q and not tpl_of(q) and not (spec.get("springs", True) and chainy(q)):
            q = bones[q]["parent"]
        return owner(q) if q else ("hip", None)

    # pieces: each mesh, skinned meshes split by the part their vertex weights belong to (overlapping at joints)
    for o in objs:  # Blender only skins with deforming bones: drop weights on control bones, renormalise
        for t in o["tris"]:
            if "w" in t:
                t["w"] = [[[bn, w] for bn, w in vw if bones.get(bn, {}).get("deform")] or vw for vw in t["w"]]
    pieces = []  # {"obj", "tris", "part", "root", "depth"}
    for o in objs:
        if o["bone"] in pupil_bones:
            pieces.append({"obj": o, "tris": o["tris"], "part": "@pupils", "root": None, "depth": o["depth"]}); continue
        if o["how"] == "skin" and o["tris"] and "w" in o["tris"][0] and spec.get("meshes", True):
            tot = {}
            for t in o["tris"]:
                for vw in t["w"]:
                    for bn, w in vw:
                        pid_ = owner(bn)
                        tot[pid_] = tot.get(pid_, 0) + w
            if len(tot) > 1:  # smooth skinning across parts: one deforming mesh stroke on the dominant part
                (pid, root) = max(tot, key=tot.get)
                pieces.append({"obj": o, "tris": o["tris"], "part": pid, "root": root, "depth": o["depth"], "mesh": True, "parts_used": sorted(tot)})
                continue
        if o["how"] == "skin" and o["tris"] and "w" in o["tris"][0]:
            by = {}
            for t in o["tris"]:
                share = {}
                for vw in t["w"]:
                    for bn, w in vw:
                        key = owner(bn)
                        share[key] = share.get(key, 0) + w / 3
                if not share:
                    share = {owner(o["bone"]): 1}
                top = max(share.values())
                for key, w in share.items():
                    if w >= max(0.15 * top, 0.06):  # joint triangles go to both sides
                        by.setdefault(key, []).append(t)
            for (pid, root), tris in by.items():
                pieces.append({"obj": o, "tris": tris, "part": pid, "root": root, "depth": o["depth"]})
        else:
            pid, root = owner(o["bone"])
            pieces.append({"obj": o, "tris": o["tris"], "part": pid, "root": root, "depth": o["depth"]})

    rank = {id(pc): i for i, pc in enumerate(sorted(pieces, key=lambda pc: (-pc["depth"], pc["obj"]["name"])))}
    zof = lambda pc: 10 + rank[id(pc)]

    def main_bone(pid):
        c = [b for b in bones if tpl_of(b) == pid]
        return min(c, key=lambda b: (not b.lower().startswith("def"), not bones[b].get("deform"), len(b))) if c else None

    def piv(b):
        return [round(v, 1) for v in F.xy(*bones[b]["head"])]

    # sprite objects owned by swap sets (removed from the base layers)
    swap_specs = {"mouth": spec.get("mouth") or {}, "eyes": spec.get("eyes") or {}}
    for sid, d in (spec.get("hands") or {}).items():
        swap_specs[sid] = d
    owned = set()
    for sid, mapping in swap_specs.items():
        anchor = "head" if sid in ("mouth", "eyes") else f"hand_{sid.split('_')[1]}"
        mb = main_bone(anchor)
        for var in mapping.values():
            for n in (rig["variants"].get(var) or {}):
                o = next(x for x in objs if x["name"] == n)
                if sid in ("mouth", "eyes") and o["bone"] != mb:
                    owned.add(n)

    obj_swaps = spec.get("object_swaps") or {}
    for sid, d in obj_swaps.items():
        for o in objs:
            if o["bone"] in d.get("bones", []):
                owned.add(o["name"])

    parts, springs = {}, {}
    drawn = {pc["part"] for pc in pieces if pc["part"] != "@pupils"}
    roots = {pc["part"]: pc["root"] for pc in pieces if pc["root"]}
    for pc in pieces:  # parts that only carry mesh weights (thighs, feet, skirt chains) must exist too
        for (q, r) in pc.get("parts_used", []):
            drawn.add(q)
            if r:
                roots[q] = r
    def bdepth(b):
        d = 0
        while bones[b]["parent"]:
            b, d = bones[b]["parent"], d + 1
        return d
    order = [p["id"] for p in T["parts"]] + sorted(roots, key=lambda q: (bdepth(roots[q]), q))
    for pid in order:
        if pid not in drawn and pid != "hip":
            continue
        mine = sorted([pc for pc in pieces if pc["part"] == pid and pc["obj"]["name"] not in owned], key=lambda pc: -pc["depth"])
        if pid in roots:
            root = roots[pid]; pv = piv(root)
            pb, par = bones[root]["parent"], "hip"
            while pb:  # nearest ancestor that is a part (chain bones without drawings are skipped)
                q = owner(pb)[0]
                if q in drawn and q != pid:
                    par = q; break
                pb = bones[pb]["parent"]
            springs[pid] = {"driver": par, "freq": 1.6, "damping": 0.35, "gain": 0.55, "limit": 12}
        else:
            mb = main_bone(pid)
            pv = piv(mb) if mb else [F.W / 2, F.ground]
            par = tparts[pid].get("parent") if pid in tparts else "hip"
            while par and par not in drawn and par != "hip":
                par = tparts[par].get("parent")
        if pid == "torso" and "hip" in parts:
            pv = parts["hip"]["pivot"]
        def piece_stroke(pc):
            if not pc.get("mesh"):
                return stroke(raster([dict(pc["obj"], tris=pc["tris"])], F, mats, ims, px), px)
            by_mat = {}
            for t in pc["tris"]:
                by_mat.setdefault(t["mat"], []).append(t)
            mat, tris = max(by_mat.items(), key=lambda kv: len(kv[1]))
            img = ims.get(mats.get(mat, {}).get("image"))
            if img is None:
                return None

            def weights_of(vws):
                acc = {}
                for bn, w in vws:
                    k = owner(bn)[0]; acc[k] = acc.get(k, 0) + w
                tot = sum(acc.values()) or 1
                return [[k, round(v / tot, 3)] for k, v in sorted(acc.items(), key=lambda kv: -kv[1]) if v / tot >= 0.01]
            return mesh_stroke(tris, F, img, weights_of, px, spec.get("mesh_subdivide", 1), spec.get("mesh_smooth", 3))
        layers = [(zof(pc), piece_stroke(pc)) for pc in mine]
        layers = [(z, s) for z, s in layers if s]
        if not layers:
            parts[pid] = {"parent": None if pid == "hip" else par, "pivot": pv, "z": 10, "strokes": []}
            continue
        z0, s0 = layers[0]
        parts[pid] = {"parent": None if pid == "hip" else par, "pivot": pv, "z": z0, "strokes": [s0]}
        for k, (z, s) in enumerate(layers[1:], 1):  # every other mesh keeps its own depth as a child layer
            parts[f"{pid}__{k}"] = {"parent": pid, "pivot": pv, "z": z, "strokes": [s]}
    if "hip" in parts and parts["hip"]["parent"] is None:
        hb = main_bone("hip")
        if hb:
            parts["hip"]["pivot"] = piv(hb)
            for k in parts:
                if k == "torso" or k.startswith("torso__") or k.startswith("hip__"):
                    parts[k]["pivot"] = parts["hip"]["pivot"]

    swaps = {}
    pp = [pc for pc in pieces if pc["part"] == "@pupils"]
    if pp:  # drop stray planes parked far behind (alternate eyes), then sit just above the eye whites
        med = sorted(pc["depth"] for pc in pp)[len(pp) // 2]
        pp = [pc for pc in pp if abs(pc["depth"] - med) < 0.02]
        swaps["pupils"] = {"anchor": "head", "z": max(zof(pc) for pc in pp), "movable": spec.get("movable", 3),
                           "shapes": {"default": [s for s in (stroke(raster([pc["obj"]], F, mats, ims, px), px) for pc in sorted(pp, key=lambda pc: -pc["depth"])) if s]}}

    def canvas(res, x0, y0, W, H):
        c = Image.new("RGBA", (W, H))
        if res:
            c.alpha_composite(res[0], (int(round((res[1] - x0) * px)), int(round((res[2] - y0) * px))))
        return c

    def variant_objs(var, names):
        ch = rig["variants"].get(var) or {}
        return [dict(o, **ch[o["name"]]) if o["name"] in ch else o for o in objs if o["name"] in names]

    pupil_depth = min([pc["depth"] for pc in pieces if pc["part"] == "@pupils"] or [-1e9])

    def patch(var, anchor, with_pupils=False, front_only=False):
        """the region a variant changes, cut from the variant state of everything on the anchor part. front_only keeps
        just what lies in front of the pupils, so eye holes stay open and the moving pupils show through"""
        names = ({pc["obj"]["name"] for pc in pieces if (pc["part"] == anchor and (not front_only or pc["depth"] < pupil_depth))
                  or (with_pupils and pc["part"] == "@pupils")} - owned) | (owned & set(rig["variants"].get(var) or {}))
        names_base = names - owned
        A = raster([o for o in objs if o["name"] in names_base], F, mats, ims, px)
        B = raster(variant_objs(var, names), F, mats, ims, px)
        if B is None:
            return []
        boxes = [r for r in (A, B) if r]
        x0 = min(r[1] for r in boxes); y0 = min(r[2] for r in boxes)
        W = int(max(r[1] * px + r[0].width for r in boxes) - x0 * px) + 2; H = int(max(r[2] * px + r[0].height for r in boxes) - y0 * px) + 2
        ca, cb = canvas(A, x0, y0, W, H), canvas(B, x0, y0, W, H)
        diff = np.abs(np.asarray(ca, np.int16) - np.asarray(cb, np.int16)).max(-1) > (24 if front_only else 6)
        if not diff.any():
            return []
        ys, xs = np.nonzero(diff); pad = int(5 * px)
        bb = (max(0, xs.min() - pad), max(0, ys.min() - pad), min(W, xs.max() + pad + 1), min(H, ys.max() + pad + 1))
        return [stroke((cb, x0, y0), px, crop=bb)]

    for sid, mapping in swap_specs.items():
        if not mapping:
            continue
        if sid in ("mouth", "eyes"):
            chg = {n for var in mapping.values() for n in (rig["variants"].get(var) or {})}
            zs = [zof(pc) for pc in pieces if pc["obj"]["name"] in chg]
            swaps[sid] = {"anchor": "head", "z": (max(zs) if zs else parts.get("head", {}).get("z", 40)) + 0.5,
                          "shapes": {name: patch(var, "head", with_pupils=(sid == "eyes"), front_only=(sid == "mouth")) for name, var in mapping.items()}}
            if sid == "mouth":
                swaps[sid]["talk"] = [k for k in ("closed", "small", "mid", "wide") if k in mapping]
        else:
            side = sid.split("_")[1]
            hp = [pc for pc in pieces if pc["part"] == f"hand_{side}"]
            shapes = {}
            for name, var in mapping.items():
                vo = variant_objs(var, {pc["obj"]["name"] for pc in hp})
                shapes[name] = [s for s in (stroke(raster([o], F, mats, ims, px), px) for o in sorted(vo, key=lambda o: -o["depth"])) if s]
            swaps[sid] = {"anchor": f"forearm_{side}", "z": parts.get(f"hand_{side}", {}).get("z", 30), "replaces": f"hand_{side}", "shapes": shapes}

    for sid, d in obj_swaps.items():
        own = [o for o in objs if o["bone"] in d.get("bones", [])]
        if not own:
            continue
        shapes = {}
        for name, var in d.get("shapes", {}).items():
            vo = variant_objs(var, {o["name"] for o in own}) if var else own
            shapes[name] = [s_ for s_ in (stroke(raster([o], F, mats, ims, px), px) for o in sorted(vo, key=lambda o: -o["depth"])) if s_]
        zs = [zof(pc) for pc in pieces if pc["obj"]["name"] in {o["name"] for o in own}]
        swaps[sid] = {"anchor": d.get("anchor", "head"), "z": max(zs) if zs else 40, "shapes": shapes}
    if "eyes" in swaps and "open" not in swaps["eyes"]["shapes"]:
        # the open eyes are the base drawing: cut the same region from the base state so the set is complete
        regions = [s_ for v in swaps["eyes"]["shapes"].values() for s_ in v]
        if regions:
            x0 = min(r["x"] for r in regions); y0 = min(r["y"] for r in regions)
            x1 = max(r["x"] + r["w"] for r in regions); y1 = max(r["y"] + r["h"] for r in regions)
            pupil_depth = min([pc["depth"] for pc in pieces if pc["part"] == "@pupils"] or [1e9])
            names = {pc["obj"]["name"] for pc in pieces if pc["part"] == "head" and pc["depth"] < pupil_depth} - owned  # only what lies in front of the pupils
            A = raster([o for o in objs if o["name"] in names], F, mats, ims, px)
            if A:
                bb = (int((x0 - A[1]) * px), int((y0 - A[2]) * px), int((x1 - A[1]) * px), int((y1 - A[2]) * px))
                swaps["eyes"]["shapes"] = {"open": [stroke(A, px, crop=bb)], **swaps["eyes"]["shapes"]}

    anchors = {}
    head_strokes = [s for k, v in parts.items() if k == "head" or k.startswith("head__") for s in v["strokes"]]
    if head_strokes:
        anchors["bubble"] = [parts["head"]["pivot"][0], round(min(s["y"] for s in head_strokes) + 10, 1)]
    meta = {"author": "", "license": "", **(spec.get("meta") or {}), "source": Path(rig["blend"]).name,
            "import": "dbe/cutout_import.py (Blender cut-out rig)", "notes": rig.get("notes", [])[:1]}
    pz = {"format": "doodleberry.puppet", "version": "0.4", "name": spec.get("name", "Imported"), "template": spec.get("template", "humanoid"),
          "artboard": [F.W, F.H], "ground": F.ground, "palette": {"ink": spec.get("ink", "#2a1f1a")}, "parts": parts, "swaps": swaps,
          "anchors": anchors, "meta": meta}
    if springs:
        pz["springs"] = springs
    report = {"materials": mats, "parts": {k: {"pivot": v["pivot"], "parent": v["parent"], "z": v["z"], "strokes": len(v["strokes"])} for k, v in parts.items()},
              "swaps": {k: {s: len(v) for s, v in sw["shapes"].items()} for k, sw in swaps.items()}, "owned": sorted(owned), "artboard": [F.W, F.H]}
    return pz, report


if __name__ == "__main__":
    spec = json.loads(Path(sys.argv[3]).read_text()) if len(sys.argv) > 3 else {}
    pz, rep = build(sys.argv[1], spec)
    Path(sys.argv[2]).write_text(json.dumps(pz))
    print(json.dumps(rep))
