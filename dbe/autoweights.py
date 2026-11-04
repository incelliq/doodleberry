"""Automatic vertex weights from bone influence (WP-11): a drawing made in one piece over several parts (a whole leg
on the thigh, an arm with its hand) becomes a skinned mesh stroke (puppet format v0.5) that bends at the joints.

The drawing's ink is covered by a grid of triangles (cells with no ink are left out, so the mesh follows the shape);
each vertex is weighted by the parts' bones (a part's bone runs from its pivot to the next part's pivot; the last
part's runs on in the direction of the one before, its own length or `tail` units), by inverse squared distance,
then diffused over the mesh so a bend becomes an arc rather than a kink (as cutout_import does for imported meshes).
Weights below 2% are dropped and each vertex keeps at most three parts. The mesh stroke sits on the chain's first part;
the image strokes it replaces are removed.
"""
import base64
import io

import numpy as np
from PIL import Image


def _seg_dist(p, a, b):
    """distance from points p (n, 2) to segment ab"""
    ab = b - a; L2 = float(ab @ ab)
    t = np.clip(((p - a) @ ab) / L2, 0, 1) if L2 > 1e-9 else np.zeros(len(p))
    return np.linalg.norm(p - (a + t[:, None] * ab), axis=1)


def bones(puppet, chain, tail=None):
    """{part: (start, end)} in artboard units"""
    P = puppet["parts"]; out = {}
    for i, q in enumerate(chain):
        a = np.array(P[q]["pivot"], float)
        if i + 1 < len(chain):
            b = np.array(P[chain[i + 1]]["pivot"], float)
        else:
            prev = np.array(P[chain[i - 1]]["pivot"], float) if i else a - np.array([0.0, 1.0])
            d = a - prev; n = np.linalg.norm(d) or 1.0
            b = a + d / n * (tail if tail is not None else min(n, 120.0) * 0.6)
        out[q] = (a, b)
    return out


def weights(verts, nbrs, bone_of, power=2.0, smooth=6, keep=3):
    """per vertex [[part, w], ...]"""
    names = list(bone_of); V = np.asarray(verts, float)
    D = np.stack([_seg_dist(V, *bone_of[q]) for q in names], 1)
    W = 1.0 / (D ** power + 1.0)
    W /= W.sum(1, keepdims=True)
    for _ in range(smooth):   # diffusion over the mesh's edges
        W = 0.5 * W + 0.5 * np.stack([W[list(n)].mean(0) if n else W[i] for i, n in enumerate(nbrs)])
    out = []
    for row in W:
        order = np.argsort(-row)[:keep]; tot = float(row[order].sum()) or 1.0
        out.append([[names[j], round(float(row[j] / tot), 3)] for j in order if row[j] / tot >= 0.02])
    return out


def grid_mesh(alpha, x, y, w, h, step):
    """triangles over the inked cells of an image laid at (x, y, w, h) in artboard units -> verts, uv, tris"""
    ih, iw = alpha.shape; sx, sy = iw / w, ih / h
    nx, ny = max(1, int(np.ceil(w / step))), max(1, int(np.ceil(h / step)))
    gx, gy = np.linspace(0, w, nx + 1), np.linspace(0, h, ny + 1)
    keyv, verts, uv, tris = {}, [], [], []

    def vid(i, j):
        if (i, j) not in keyv:
            keyv[(i, j)] = len(verts); verts.append([x + gx[i], y + gy[j]]); uv.append([gx[i] * sx, gy[j] * sy])
        return keyv[(i, j)]
    for j in range(ny):
        for i in range(nx):
            c = alpha[int(gy[j] * sy):max(int(gy[j] * sy) + 1, int(np.ceil(gy[j + 1] * sy))), int(gx[i] * sx):max(int(gx[i] * sx) + 1, int(np.ceil(gx[i + 1] * sx)))]
            if c.size and c.max() > 0.04:
                a, b, cc, d = vid(i, j), vid(i + 1, j), vid(i + 1, j + 1), vid(i, j + 1)
                tris += [[a, b, cc], [a, cc, d]]
    return verts, uv, tris


def _img(st):
    return Image.open(io.BytesIO(base64.b64decode(st["image"].split(",", 1)[1]))).convert("RGBA")


def auto_mesh(puppet, part, chain, step=12.0, tail=None, smooth=6):
    """the image strokes of `part` -> one mesh stroke weighted over `chain` (which must start with `part`); the
    puppet is changed in place and returned with a report"""
    P = puppet["parts"]
    if chain[0] != part:
        raise ValueError("the chain starts with the part that carries the drawing")
    missing = [q for q in chain if q not in P]
    if missing:
        raise KeyError(f"no part {missing}")
    imgs = [st for st in P[part].get("strokes", []) if "image" in st]
    if not imgs:
        raise ValueError(f"{part} has no image stroke to skin")
    bone_of = bones(puppet, chain, tail); new, report = [], []
    for st in imgs:
        im = _img(st); a = np.asarray(im, float)[..., 3] / 255.0
        verts, uv, tris = grid_mesh(a, st["x"], st["y"], st["w"], st["h"], step)
        nb = [set() for _ in verts]
        for t in tris:
            for u in t:
                nb[u] |= set(t) - {u}
        wts = weights(verts, nb, bone_of, smooth=smooth)
        new.append({"mesh": {"image": st["image"], "iw": im.width, "ih": im.height, "verts": [[round(v[0], 2), round(v[1], 2)] for v in verts],
                             "uv": [[round(u[0], 2), round(u[1], 2)] for u in uv], "tris": tris, "weights": wts, "grow": 0.8}})
        report.append({"verts": len(verts), "tris": len(tris), "parts": sorted({q for ws in wts for q, _ in ws})})
    P[part]["strokes"] = [st for st in P[part].get("strokes", []) if "image" not in st] + new
    return puppet, report
