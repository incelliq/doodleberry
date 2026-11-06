"""Characters from a cut-out kit (cast.from_kit): a humanoid puppet put together from parts an image model drew whole
and apart, fitted onto the character's model sheet, the way a professional cut-out rig is drawn for the rig and built
to the model sheet rather than cut out of a finished picture.

The kit is one sheet on white. The top row holds the head, the torso and the hips. The bottom row holds the two arms,
then the two legs (or, under a long skirt, the two feet). Every part is drawn complete, including what another part
covers: the head ends at the jaw, the torso carries the neck and has closed shoulders and no sleeves, and each limb is
whole from a rounded top down to the hand or shoe. From it:

- the pieces are found on the page and named by their place;
- each piece's joints come from its shape. A limb's top joint is the centre of its rounded top; the wrist or ankle is
  where it widens into the hand or shoe, and the elbow or knee is halfway. The torso's neck is its narrow top and its
  shoulders are where its sides are widest below the neck;
- with a model sheet (a turnaround whose front view is the design), every piece is fitted onto the front view: its
  scale, angle (limbs) and place are those where most of its pixels land on their own flat colour. Landing on a part
  drawn in front of it (legs under the shorts, the torso under the arms) counts neither way. The torso goes first,
  then the hips and arms near it at about its scale, then the legs inside the hips. The head is cut from the model
  itself at the neck, so the face is the design's, and each piece takes the model's flat colours;
- without one, the pieces are put together at their joints as the kit drew them: the jaw over the neck, each arm's top
  joint just inside the torso's shoulder, the hips under the waist, each leg's top joint in its leg opening (or the
  ankles just under the hem). Image models do not keep proportions from one picture to the next, so this is only as
  true to the design as the kit is;
- each arm and leg stays one drawing, skinned to its three bones (puppet.auto_weights), so it bends in an arc at the
  elbow or knee instead of showing a cut. The head and torso get joint limits: a cut-out turns only a little from how
  it was drawn;
- the face's eyes and mouth become swaps as in cast.from_sheet, with an optional mouth sheet.
"""
import colorsys

import numpy as np
from PIL import Image
from scipy import ndimage as ND

from . import autoweights as AW
from . import fromsheet as FS

ROWS = (("head", "torso", "hips"), ("arm_L", "arm_R", "leg_L", "leg_R"))
LIMITS = {"head": [-15, 15], "torso": [-12, 12]}
# both arms hang in front of the torso in a front view (the screen-left one under the screen-right one)
Z = {"hip": 20, "torso": 22, "head": 40, "upperarm_L": 26, "forearm_L": 27, "hand_L": 28, "upperarm_R": 30, "forearm_R": 31,
     "hand_R": 32, "thigh_L": 14, "shin_L": 15, "foot_L": 16, "thigh_R": 17, "shin_R": 18, "foot_R": 19}
PARENT = {"hip": None, "torso": "hip", "head": "torso", "upperarm_L": "torso", "forearm_L": "upperarm_L", "hand_L": "forearm_L",
          "upperarm_R": "torso", "forearm_R": "upperarm_R", "hand_R": "forearm_R", "thigh_L": "hip", "shin_L": "thigh_L", "foot_L": "shin_L",
          "thigh_R": "hip", "shin_R": "thigh_R", "foot_R": "shin_R"}


def pieces(rgb, white_tol=40):
    """the kit's pieces, row by row (top to bottom), each row left to right: [[{"m", "box"}, ...], ...]. The page is
    the white joined to the border, so white inside a piece (a shoe, an eye) stays; marks close together are one piece"""
    near_white = (255 - rgb).sum(-1) < white_tol
    lab, _ = ND.label(near_white)
    edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    ink = ~np.isin(lab, edge[edge > 0])
    grp, n = ND.label(ND.binary_dilation(ink, iterations=max(3, int(0.01 * max(ink.shape)))))
    items = []
    for i in range(1, n + 1):
        m = ND.binary_fill_holes((grp == i) & ink)
        if m.sum() < 0.002 * m.size:   # specks
            continue
        ys, xs = np.where(m)
        items.append({"m": m, "box": (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1), "cx": (xs.min() + xs.max()) / 2, "cy": (ys.min() + ys.max()) / 2})
    if not items:
        raise ValueError("nothing drawn on the kit")
    items.sort(key=lambda it: it["cy"]); hmed = float(np.median([it["box"][3] - it["box"][1] for it in items]))
    rows = []
    for it in items:   # a new row where the next piece's middle is well below the last one's
        if rows and it["cy"] - rows[-1][-1]["cy"] < 0.5 * hmed:
            rows[-1].append(it)
        else:
            rows.append([it])
    return [sorted(r, key=lambda it: it["cx"]) for r in rows]


def _extent(m):
    """first and last row of a piece and, for each row between, its leftmost and rightmost pixel (nan where empty)"""
    ys = np.where(m.any(1))[0]; y0, y1 = int(ys.min()), int(ys.max())
    l = np.full(y1 - y0 + 1, np.nan); r = l.copy()
    for y in range(y0, y1 + 1):
        xs = np.where(m[y])[0]
        if len(xs):
            l[y - y0], r[y - y0] = xs.min(), xs.max()
    return y0, y1, l, r


def limb(m, k):
    """joints of a limb drawn hanging straight down: top (the centre of its rounded top), mid (elbow or knee, halfway)
    and end (wrist or ankle: where it widens k times into the hand or shoe), in image px; r is half its width at the top"""
    y0, y1, l, r = _extent(m); w = r - l + 1; L = len(w)
    rad = float(np.nanmedian(w[int(0.15 * L): max(int(0.15 * L) + 1, int(0.35 * L))])) / 2
    i = min(L - 1, int(round(rad)))
    top = ((l[i] + r[i]) / 2, y0 + rad)
    narrow = float(np.nanmedian(w[int(0.3 * L): int(0.55 * L)]))
    sm = np.convolve(np.nan_to_num(w), np.ones(5) / 5, mode="same")
    j = next((j for j in range(int(0.5 * L), L) if sm[j] > k * narrow), int(0.8 * L))
    end = ((l[j] + r[j]) / 2, float(y0 + j))
    return {"top": top, "mid": ((top[0] + end[0]) / 2, (top[1] + end[1]) / 2), "end": end, "r": rad, "y0": y0, "y1": y1}


def torso(m, arm_r):
    """the torso's axis, neck, shoulder joints (for arms of top radius arm_r, by side) and waist, in image px"""
    y0, y1, l, r = _extent(m); w = r - l + 1; L = len(w)
    body = float(np.nanmedian(w[int(0.5 * L): int(0.9 * L)]))
    cx = float(np.nanmedian(((l + r) / 2)[int(0.5 * L): int(0.9 * L)]))
    sh = next((i for i in range(L) if w[i] >= 0.6 * body), 0)   # the first row past the narrow neck
    neck_x = float(np.nanmedian(((l + r) / 2)[:sh])) if sh else (l[0] + r[0]) / 2
    neck = (neck_x, y0 + (0.6 * sh if sh else 0.02 * L))   # where the jaw sits: 0.4 of the neck shows below it
    band = slice(sh, sh + max(1, int(0.35 * L)))
    shoulders = {}
    for side, xe, inward in (("L", np.nanmin(l[band]), 1), ("R", np.nanmax(r[band]), -1)):
        x = xe + inward * 0.25 * arm_r   # the joint just inside the shoulder's edge
        col = np.where(m[:, int(round(x))])[0]
        shoulders[side] = (float(x), float((col.min() if len(col) else y0 + sh) + arm_r))
    col = np.where(m[:, int(round(cx))])[0]
    warn = []
    if np.nanmax(w[band]) > 1.3 * body:
        warn.append("the torso is much wider at the shoulders than the body: it seems to have sleeves (they belong on the arms)")
    if L > 2.2 * body:
        warn.append("the torso is very tall for its width: it may include the head or a skirt (they are separate pieces)")
    return {"cx": cx, "neck": neck, "neck_rows": (y0, y0 + sh), "shoulders": shoulders, "waist": float(col.max()), "y0": y0, "warn": warn}


def hips(m):
    """the hips' top centre and leg openings: with two openings (shorts, trousers) the crotch is where they join going
    up; with one (a skirt) the feet stand under its hem"""
    y0, y1, l, r = _extent(m); L = y1 - y0 + 1
    cx = float(np.nanmedian(((l + r) / 2)[: max(1, int(0.2 * L))]))
    yb = y1 - max(1, int(0.03 * L))
    runs = sorted(FS._runs(m[yb]), key=lambda ab: ab[0] - ab[1])[:2]   # the two widest runs along the bottom
    if len(runs) == 2:
        runs.sort()
        y = yb
        while y > y0 and len(FS._runs(m[y])) >= 2:
            y -= 1
        return {"cx": cx, "y0": y0, "h": L, "skirt": False, "open": [(a + b) / 2 for a, b in runs], "crotch": float(y + 1), "hem": float(y1)}
    a, b = runs[0]; hw = b - a
    return {"cx": cx, "y0": y0, "h": L, "skirt": True, "open": [cx - 0.22 * hw, cx + 0.22 * hw], "crotch": None, "hem": float(y1)}


def _mode(rgb, m):
    px = rgb[m & (rgb.sum(-1) > 120) & (rgb.sum(-1) < 700)]
    return FS._mode_colour(px) if len(px) else np.array([128, 128, 128])


def _shade_of(c, ref):
    """whether colour c is a lighter or darker shade of ref: about the same hue, and not grey"""
    (h1, s1, _), (h2, s2, _) = (colorsys.rgb_to_hsv(*(np.asarray(v, float) / 255)) for v in (c, ref))
    return s1 > 0.15 and s2 > 0.15 and min(abs(h1 - h2), 1 - abs(h1 - h2)) < 25 / 360


# ------------------------------------------------------------------ fitting the pieces onto the model sheet
def _flat_colours(rgb, m, step=24, min_frac=0.003, merge=45):
    """the drawing's flat colours under mask m: the means of its most common colour bins, near duplicates merged"""
    px = rgb[m].astype(np.int32)
    _, inv, cnt = np.unique((px // step) @ np.array([1 << 16, 1 << 8, 1]), return_inverse=True, return_counts=True)
    inv = inv.ravel(); pal = []
    for i in np.argsort(-cnt):
        if cnt[i] < min_frac * len(px):
            break
        c = px[inv == i].mean(0)
        if all(np.abs(c - q).sum() > merge for q in pal):
            pal.append(c)
    return np.array(pal)


def _classes(rgb, pal, tol=90):
    """each pixel's nearest flat colour (an index into pal); -1 where none is near"""
    d = np.abs(rgb[..., None, :].astype(np.int32) - pal.astype(np.int32)).sum(-1)
    c = d.argmin(-1).astype(np.int16); c[d.min(-1) > tol] = -1
    return c


def _rot(s, a):
    r = np.radians(a)
    return s * np.array([[np.cos(r), -np.sin(r)], [np.sin(r), np.cos(r)]])


def _warp(rgba, M, t, size):
    """an RGBA image through p -> M p + t, into a canvas of the given (w, h)"""
    Mi = np.linalg.inv(M); ti = -Mi @ t
    return rgba.transform(size, Image.AFFINE, (Mi[0, 0], Mi[0, 1], ti[0], Mi[1, 0], Mi[1, 1], ti[1]), resample=Image.BILINEAR)


def _fit(rgba, fcls, pal, inform, scales, angles, ok, f, behind=()):
    """the scale, angle and place that best lay a piece (an RGBA crop) over the model drawing (fcls: its colour classes):
    the piece's pixels landing on their own colour less those landing elsewhere, except that landing on a colour of a
    part drawn in front of it (behind: those colours) counts neither way; searched on a drawing f times smaller, then
    at full size around the best. ok(x, y) says where the piece's centre may go.
    -> (M, t) taking crop px to drawing px, and the share of the piece's pixels that matched"""
    from scipy.signal import fftconvolve
    w, h = rgba.size; c = np.array([w / 2, h / 2])

    def score(F, s, a, k):   # F: the drawing's classes at 1/k size; -> score map, piece size, M, t, canvas side
        M = _rot(s / k, a); D = int(np.ceil(np.hypot(w, h) * s / k)) + 2
        t = np.array([D / 2, D / 2]) - M @ c
        im = np.asarray(_warp(rgba, M, t, (D, D)))
        pc = np.where(im[..., 3] > 127, _classes(im[..., :3], pal), -1)
        n = int(np.isin(pc, inform).sum())
        corr = lambda a, b: fftconvolve(a.astype(np.float32), b[::-1, ::-1].astype(np.float32), mode="valid")
        agree = sum(corr(F == q, pc == q) for q in inform if (pc == q).any())
        hid = 0
        if behind:   # landing on something in front of the piece: hidden there, neither for nor against
            hid = corr(np.isin(F, behind), np.isin(pc, inform)) - sum(corr(F == q, pc == q) for q in behind if q in inform and (pc == q).any())
        return 2 * agree + hid - n, max(n, 1), M, t, D

    Fs = fcls[::f, ::f]; P = int(np.ceil(np.hypot(w, h) * max(scales) / f)) + 2
    Fp = np.pad(Fs, P, constant_values=-1); best = None
    for s in scales:
        for a in angles:
            S, n, M, t, D = score(Fp, s, a, f)
            ii, jj = np.mgrid[: S.shape[0], : S.shape[1]]
            S = np.where(ok((jj - P + D / 2) * f, (ii - P + D / 2) * f), S, -np.inf)
            i, j = np.unravel_index(np.argmax(S), S.shape)
            if best is None or S[i, j] > best[0]:
                best = (S[i, j], s, a, ((j - P + D / 2) * f, (i - P + D / 2) * f))
    _, s0, a0, (qx, qy) = best; m = 2 * f + 2; best = None
    for s in (s0 * k for k in (0.97, 0.985, 1, 1.015, 1.03)):
        for a in ((a0 - 3, a0 - 1.5, a0, a0 + 1.5, a0 + 3) if len(angles) > 1 else (a0,)):
            D = int(np.ceil(np.hypot(w, h) * s)) + 2; X0, Y0 = int(round(qx - D / 2)) - m, int(round(qy - D / 2)) - m
            win = np.pad(fcls, D + m, constant_values=-1)[Y0 + D + m: Y0 + 2 * D + 3 * m, X0 + D + m: X0 + 2 * D + 3 * m]
            S, n, M, t, _ = score(win, s, a, 1)
            i, j = np.unravel_index(np.argmax(S), S.shape)
            if best is None or S[i, j] > best[0]:
                best = (S[i, j], M, t + np.array([X0 + j, Y0 + i]), (S[i, j] + n) / 2 / n, s, a)
    return best[1], best[2], {"match": round(float(best[3]), 3), "scale": round(best[4], 3), "angle": round(best[5], 1)}


def model_head(rgb, fm, neck_y, H):
    """the head cut from the model drawing (fm: its figure) at the neck's narrowest row near neck_y, with all the hair
    joined to it -> (mask, pivot)"""
    yy = np.arange(rgb.shape[0])[:, None]
    ff = FS.face_features(rgb, fm & (yy < neck_y + 0.04 * H))
    fy, fx = np.where(ff["face"]); cx = int((fx.min() + fx.max()) / 2)
    skin = ND.binary_fill_holes((np.abs(rgb - ff["skin"]).sum(-1) < 60) & fm)   # eyes, nose and mouth filled: they would break the rows
    eye_y = max((e["c"][1] for e in ff["eyes"]), default=neck_y - 0.1 * H)
    neck = [(r1 - r0, y, r0, r1) for y in range(int(eye_y + 0.04 * H), int(neck_y + 0.06 * H)) for r0, r1 in FS._runs(skin[y]) if r0 <= cx < r1]
    _, yn, n0, n1 = min(neck) if neck else (0, int(neck_y), cx - 1, cx + 1)
    head = fm & (yy < yn)
    hc = FS._mode_colour(rgb[fm & (yy < fy.min())]) if fy.min() > np.where(fm.any(1))[0].min() else None
    if hc is not None:   # hair hanging below the cut stays with the head
        hair = (np.abs(rgb - hc).sum(-1) < 45) & fm
        lab, _ = ND.label(hair); ids = np.unique(lab[head & hair]); ids = ids[ids > 0]
        head |= ND.binary_dilation(np.isin(lab, ids), iterations=3) & fm
    return head, ((n0 + n1) / 2, float(yn))


def _recolour(rgba, pal, tol=90):
    """a kit piece in the model's flat colours: each colour the piece shares with the model moved onto the model's"""
    a = np.asarray(rgba).astype(np.int32); rgb, m = a[..., :3], a[..., 3] > 127
    c = _classes(rgb, pal, tol)
    for k in np.unique(c[m]):
        if k >= 0:
            sel = m & (c == k); rgb[sel] = rgb[sel] - rgb[sel].mean(0).astype(np.int32) + pal[k].astype(np.int32)
    return Image.fromarray(np.dstack([np.clip(rgb, 0, 255), a[..., 3]]).astype(np.uint8), "RGBA")


BEHIND = {"torso": ("head", "arm_L", "arm_R"), "hips": ("torso", "arm_L", "arm_R"), "arm_L": (), "arm_R": (),
          "leg_L": ("hips",), "leg_R": ("hips",)}   # what is drawn in front of each piece in a front view


def build(kit, name, sheet=None, view=0, mouths=None, mouths_extra=None, model="", license_id=""):
    """-> (puppet dict, report). With a model sheet (a turnaround; view: which figure from the left is the front view)
    every piece is fitted onto the model's front view and the head is the model's own; without one the pieces are put
    together at their joints as the kit drew them"""
    rgb = FS._load(kit)
    rows = pieces(rgb)
    if [len(r) for r in rows] != [3, 4]:
        raise ValueError(f"a kit has 3 pieces in its top row (head, torso, hips) and 4 below (two arms, then two legs or feet), "
                         f"each apart from the others; found rows of {[len(r) for r in rows]}")
    P = {nm: it for names, r in zip(ROWS, rows) for nm, it in zip(names, r)}
    M = {nm: it["m"] for nm, it in P.items()}
    report = {"warnings": []}
    # joints of each piece, where it was drawn on the kit
    arm = {s: limb(M[f"arm_{s}"], 1.3) for s in "LR"}
    leg = {s: limb(M[f"leg_{s}"], 1.25) for s in "LR"}
    T = torso(M["torso"], (arm["L"]["r"] + arm["R"]["r"]) / 2); report["warnings"] += T["warn"]
    Hp = hips(M["hips"])
    ff = FS.face_features(rgb, M["head"])
    fy, fx = np.where(ff["face"])
    jaw = ((fx.min() + fx.max()) / 2, float(fy.max()))   # the chin (hair may hang lower)
    # put together at the joints, as offsets from where each piece was drawn (the torso stays put)
    off = {"torso": (0.0, 0.0), "head": (T["neck"][0] - jaw[0], T["neck"][1] - jaw[1]),
           "hips": (T["cx"] - Hp["cx"], T["waist"] - 0.18 * Hp["h"] - Hp["y0"])}
    for s in "LR":
        off[f"arm_{s}"] = (T["shoulders"][s][0] - arm[s]["top"][0], T["shoulders"][s][1] - arm[s]["top"][1])
    for i, s in enumerate("LR"):
        if Hp["skirt"]:   # the ankle just under the hem
            oy = Hp["hem"] + off["hips"][1] - 0.85 * (leg[s]["end"][1] - leg[s]["top"][1])
        else:             # the leg's rounded top in its leg opening, at the crotch
            oy = Hp["crotch"] + off["hips"][1]
        off[f"leg_{s}"] = (Hp["open"][i] + off["hips"][0] - leg[s]["top"][0], oy - leg[s]["top"][1])
    # each part: its crop (rgb, mask) and the map (A, t) from crop px into the frame
    part = {}
    for k, it in P.items():
        x0, y0, x1, y1 = it["box"]
        part[k] = [rgb[y0:y1, x0:x1], M[k][y0:y1, x0:x1], np.eye(2), np.round(np.array(off[k], float)) + (x0, y0)]
    skin_ref, head_piv, head_rgb = ff["skin"], (T["neck"][0], T["neck"][1]), FS.lift_face(rgb, ff)
    hx0, hy0, hx1, hy1 = P["head"]["box"]; part["head"][0] = head_rgb[hy0:hy1, hx0:hx1]
    if sheet:   # fit every piece onto the model's front view; the head is the model's own
        mrgb = FS._load(sheet)
        figs = [it for r in pieces(mrgb) for it in r]; tall = max(it["box"][3] - it["box"][1] for it in figs)
        figs = sorted((it for it in figs if it["box"][3] - it["box"][1] > 0.6 * tall), key=lambda it: it["cx"])
        fig = figs[min(view, len(figs) - 1)]; fm = fig["m"]; bx0, by0, bx1, by1 = fig["box"]
        pal = _flat_colours(mrgb, fm); inform = [k for k in range(len(pal)) if pal[k].sum() < 690]   # white tells little
        fcls = np.where(fm, _classes(mrgb, pal), -1)
        top = min(P[k]["box"][1] + off[k][1] for k in P); bot = max(P[k]["box"][3] + off[k][1] for k in P)
        sg = (by1 - by0) / max(1.0, bot - top); scales = [sg * 1.05 ** k for k in range(-8, 9)]
        f = max(1, int((by1 - by0) / 160)); report["fit"] = {}
        crops = {k: _recolour(Image.fromarray(np.dstack([part[k][0], part[k][1] * 255]).astype(np.uint8), "RGBA"), pal) for k in P}
        own = {}   # each piece's colours (as the model's classes)
        for k, im in crops.items():
            a_ = np.asarray(im); c = np.where(a_[..., 3] > 127, _classes(a_[..., :3], pal), -1)
            q, n = np.unique(c[c >= 0], return_counts=True); own[k] = [int(x) for x, m in zip(q, n) if m > 0.05 * n.sum() and x in inform]
        W, H = bx1 - bx0, by1 - by0
        region = lambda x0, x1, y0, y1: (lambda x, y: (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1))
        box = {}
        for k in ("torso", "hips", "arm_L", "arm_R", "leg_L", "leg_R"):
            if k == "torso":
                sc, ok = scales, region(bx0, bx1, by0 + 0.2 * H, by0 + 0.7 * H)
            else:   # one kit is drawn at one scale: every piece near the torso's
                sc = [report["fit"]["torso"]["scale"] * 1.05 ** j for j in range(-7, 8)]
                tb = box["torso"]
                if k == "hips":
                    ok = region(tb[0], tb[2], tb[1] + 0.3 * (tb[3] - tb[1]), by1)
                elif k.startswith("arm"):
                    ok = region(bx0, (tb[0] + tb[2]) / 2, tb[1], by1) if k.endswith("L") else region((tb[0] + tb[2]) / 2, bx1, tb[1], by1)
                else:       # a leg's middle inside its half of the hips' width, below their top
                    hb = box["hips"]; hc = (hb[0] + hb[2]) / 2
                    ok = region(hb[0], hc, hb[1], by1) if k.endswith("L") else region(hc, hb[2], hb[1], by1)
            behind = sorted({q for o in BEHIND[k] for q in own[o]})
            A, t, info = _fit(crops[k], fcls, pal, inform, sc, [0] if k in ("torso", "hips") else list(range(-24, 25, 6)), ok, f, behind)
            report["fit"][k] = info
            if info["match"] < 0.5:
                report["warnings"].append(f"the {k} piece matches the model's front view poorly ({info['match']:.0%} of it lands on its own colour)")
            h_, w_ = part[k][1].shape; cs = np.array([[0, 0], [w_, 0], [0, h_], [w_, h_]], float) @ A.T + t
            box[k] = (*cs.min(0), *cs.max(0))
            part[k] = [np.asarray(crops[k])[..., :3].astype(np.int16), part[k][1], A, t]
        tx0, ty0 = P["torso"]["box"][:2]
        neck_at = part["torso"][2] @ (np.array(T["neck"]) - (tx0, ty0)) + part["torso"][3]
        hm, head_piv = model_head(mrgb, fm, neck_at[1], by1 - by0)
        ff = FS.face_features(mrgb, hm); skin_ref = ff["skin"]
        ys, xs = np.where(hm); hx0, hy0, hx1, hy1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
        part["head"] = [FS.lift_face(mrgb, ff)[hy0:hy1, hx0:hx1], hm[hy0:hy1, hx0:hx1], np.eye(2), np.array([hx0, hy0], float)]
        head_frame = (mrgb, (0.0, 0.0))
    else:
        head_frame = (rgb, off["head"])
    # the neck in the face's skin colour (models often draw it a shade off)
    tr, tm = part["torso"][0].copy(), part["torso"][1]; n1 = T["neck_rows"][1] - P["torso"]["box"][1]
    if n1 > 0:
        nm = tm & (np.arange(tm.shape[0])[:, None] < n1); nc = _mode(tr, nm)
        if np.abs(nc - skin_ref).sum() > 30 and _shade_of(nc, skin_ref):
            tr[tm & (np.abs(tr - nc).sum(-1) < 40)] = skin_ref; part["torso"][0] = tr
            report["neck_recoloured"] = [FS._hex(nc), FS._hex(skin_ref)]
    # each part's drawing in the frame
    placed = {}
    for k, (crgb, cm, A, t) in part.items():
        h, w = cm.shape; cs = np.array([[0, 0], [w, 0], [0, h], [w, h]], float) @ A.T + t
        x0, y0 = np.floor(cs.min(0)).astype(int); x1, y1 = np.ceil(cs.max(0)).astype(int)
        im = Image.fromarray(np.dstack([np.clip(crgb, 0, 255), cm * 255]).astype(np.uint8), "RGBA")
        placed[k] = (_warp(im, A, t - (x0, y0), (int(x1 - x0), int(y1 - y0))) if not np.allclose(A, np.eye(2)) or np.any(t % 1) else _shift(im, t - (x0, y0), (int(x1 - x0), int(y1 - y0))), (x0, y0))
    to_frame = lambda k, p: part[k][2] @ (np.array(p, float) - P[k]["box"][:2]) + part[k][3]
    # onto the artboard: soles on the ground, the torso's axis in the middle
    top = min(o[1] + im.getbbox()[1] for im, o in placed.values()); bot = max(o[1] + im.getbbox()[3] for im, o in placed.values())
    waist = to_frame("torso", (T["cx"], T["waist"]))
    s = FS.HEIGHT / max(1.0, bot - top)
    ax = lambda x: (x - waist[0]) * s + FS.ARTBOARD[0] / 2
    ay = lambda y: (y - bot) * s + FS.GROUND
    A_ = lambda p: [round(float(ax(p[0])), 1), round(float(ay(p[1])), 1)]
    piv = {"hip": waist, "torso": waist, "head": head_piv if sheet else to_frame("torso", T["neck"])}
    for sd in "LR":
        for p, q in (("upperarm", "top"), ("forearm", "mid"), ("hand", "end")):
            piv[f"{p}_{sd}"] = to_frame(f"arm_{sd}", arm[sd][q])
        for p, q in (("thigh", "top"), ("shin", "mid"), ("foot", "end")):
            piv[f"{p}_{sd}"] = to_frame(f"leg_{sd}", leg[sd][q])
    carrier = {"hip": "hips", "torso": "torso", "head": "head", "upperarm_L": "arm_L", "upperarm_R": "arm_R", "thigh_L": "leg_L", "thigh_R": "leg_R"}
    parts = {}
    for p in PARENT:
        st = []
        if p in carrier:
            im, (x0, y0) = placed[carrier[p]]
            st = [{"image": FS._uri(im), "x": round(float(ax(x0)), 1), "y": round(float(ay(y0)), 1), "w": round(im.width * s, 1), "h": round(im.height * s, 1)}]
        parts[p] = {"parent": PARENT[p], "pivot": A_(piv[p]), "z": Z[p], "strokes": st}
    for p, lim in LIMITS.items():
        parts[p]["limits"] = list(lim)
    hrgb, (hox, hoy) = head_frame
    swaps = FS.face_swaps(hrgb, ff, lambda x: ax(x + hox), lambda y: ay(y + hoy), s, mouths, mouths_extra, report)
    col = lambda k, extra=None: FS._hex(_mode(part[k][0], part[k][1] if extra is None else part[k][1] & extra))
    palette = {"skin": FS._hex(ff["skin"]), "ink": FS._hex(ff["ink"]), "eye": "#ffffff", "cloth1": col("torso"), "cloth2": col("hips"),
               "hair": FS._hex(FS._mode_colour(part["head"][0][part["head"][1] & (part["head"][0].sum(-1) < 700)])),
               "shoe": FS._hex(FS._mode_colour(rgb[M["leg_L"] & (np.arange(rgb.shape[0])[:, None] > leg["L"]["end"][1]) & (rgb.sum(-1) > 120)]))}
    puppet = {"format": "doodleberry.puppet", "version": "0.14", "name": name, "template": "humanoid", "artboard": list(FS.ARTBOARD), "ground": FS.GROUND,
              "palette": palette, "parts": parts, "swaps": swaps, "acting": {"gestures": "humanoid"},
              "meta": {"author": "cast.from_kit", "source": "generated cut-out kit" + (" fitted to its model sheet" if sheet else ""),
                       "model": model or "unrecorded", "license": license_id or "unrecorded",
                       "note": "drawn by an image model from a written description; check it resembles no existing character"}}
    # each arm and leg one drawing over its three bones
    mesh = {}
    for sd in "LR":
        for chain in ([f"upperarm_{sd}", f"forearm_{sd}", f"hand_{sd}"], [f"thigh_{sd}", f"shin_{sd}", f"foot_{sd}"]):
            _, rep = AW.auto_mesh(puppet, chain[0], chain)
            mesh[chain[0]] = rep[0]["verts"]
            for st in puppet["parts"][chain[0]]["strokes"]:
                st["mesh"]["grow"] = 1.6   # flat-coloured textures show the triangles' seams at the default 0.8
    report.update({"pieces": {k: list(P[k]["box"]) for k in P}, "skirt": Hp["skirt"], "eyes": len(ff["eyes"]), "mouth": bool(ff["mouth"]),
                   "scale": round(s, 4), "mesh_verts": mesh, "pivots": {p: parts[p]["pivot"] for p in parts}, "palette": palette})
    return puppet, report


def _shift(im, t, size):
    """a whole-pixel move (no resampling, so the drawing stays sharp)"""
    out = Image.new("RGBA", size, (0, 0, 0, 0)); out.paste(im, (int(round(t[0])), int(round(t[1]))))
    return out
