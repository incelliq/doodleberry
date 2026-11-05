"""A humanoid puppet from one generated character sheet (cast.from_sheet).

Input: a full-colour character drawn front-on in a T-pose (arms straight out at shoulder height, legs apart, feet
visible) on a plain white page, optionally with a sheet of mouth shapes drawn alone. The figure is found by flooding
the white page from its border; the silhouette's row widths give the arm band, the torso sides below it, the head
above it and the gap between the legs; the arm's thickness along its length gives the wrist, the leg's width the
ankle. Each part is the figure's own pixels in its region plus a round cap over its joint, so the parts overlap where
they turn. The arms are swung down about the shoulders (the humanoid template's rest pose has them hanging), the
eyes and the mouth are lifted off the face (painted over with the skin colour) into the eyes and mouth swaps, and a
sheet of mouths, scaled so its closed smile is the face's own mouth, fills the lip-sync shapes. Parts are raster
strokes ({"image", x, y, w, h}); puppet.vectorize traces them afterwards.
"""
import base64
import io
import math

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ND

ARTBOARD = (600, 1000)
GROUND = 980
HEIGHT = 820          # figure height on the artboard, head top to soles


# ------------------------------------------------------------------ page and figure
def _load(path):
    im = Image.open(path).convert("RGB")
    return np.asarray(im).astype(np.int16)


def figure_mask(rgb, white_tol=40):
    """the figure: everything but the white page connected to the border (white inside the figure stays figure)"""
    near_white = (255 - rgb).sum(-1) < white_tol
    lab, _ = ND.label(near_white)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    page = np.isin(lab, list(border))
    fig = ~page
    lab2, n = ND.label(fig)
    if n == 0:
        raise ValueError("no figure found on the page")
    sizes = ND.sum(fig, lab2, range(1, n + 1))
    keep = 1 + int(np.argmax(sizes))
    fig = lab2 == keep   # the largest piece: specks and stray marks go
    return ND.binary_fill_holes(fig)


def _runs(row):
    """[(start, end)] of True runs in a boolean row"""
    d = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))


def _mode_colour(px):
    """the commonest colour (quantised to 8 levels a channel) among pixels [n, 3], returned as its mean"""
    if len(px) == 0:
        return np.array([128, 128, 128])
    q = (px // 32).astype(np.int32); key = q[:, 0] * 64 + q[:, 1] * 8 + q[:, 2]
    k = np.bincount(key).argmax()
    return px[key == k].mean(0)


def _hex(c):
    return "#%02x%02x%02x" % tuple(int(max(0, min(255, v))) for v in c)


# ------------------------------------------------------------------ landmarks
def landmarks(fig):
    """joints of a front-on T-pose figure, in image pixels"""
    ys, xs = np.where(fig)
    top, bot, left, right = ys.min(), ys.max(), xs.min(), xs.max()
    H = bot - top
    width = np.array([(fig[y].nonzero()[0].max() - fig[y].nonzero()[0].min() + 1) if fig[y].any() else 0 for y in range(fig.shape[0])])
    # the torso's sides: the figure's edges in rows through the middle of the body (below the arms, above the legs)
    rows = [y for y in range(top + int(0.45 * H), top + int(0.62 * H)) if fig[y].any()]
    tl = int(np.median([fig[y].nonzero()[0].min() for y in rows])); tr = int(np.median([fig[y].nonzero()[0].max() for y in rows]))
    cx = (tl + tr) / 2
    # the arm band: rows that reach well out past the torso on both sides (hair and shoulders do not)
    lx = np.array([fig[y].nonzero()[0].min() if fig[y].any() else 10 ** 6 for y in range(fig.shape[0])])
    rx = np.array([fig[y].nonzero()[0].max() if fig[y].any() else -1 for y in range(fig.shape[0])])
    far = (lx < tl - 0.45 * (tl - left)) & (rx > tr + 0.45 * (right - tr))
    band = np.where(far)[0]
    if len(band) < 3 or tl - left < 0.15 * H:
        raise ValueError("no arms held out sideways: draw the character in a T-pose (arms straight out at shoulder height)")
    a0, a1 = band.min(), band.max()
    # each arm: thickness along x, from the torso side out to the tip
    arms = {}
    for side, xr in (("L", range(tl, left - 1, -1)), ("R", range(tr, right + 1))):
        th, cy = [], []
        for x in xr:
            col = np.where(fig[a0 - int(0.04 * H): a1 + int(0.04 * H), x])[0]
            if len(col) == 0:
                break
            th.append(col.max() - col.min() + 1); cy.append(a0 - int(0.04 * H) + (col.max() + col.min()) / 2)
        th = np.array(th, float); L = len(th)
        if L < 10:
            raise ValueError(f"arm {side} too short to find")
        fore = np.median(th[int(0.45 * L): int(0.65 * L)])
        # wrist: going out from the elbow, where the arm widens into the hand (palm and thumb)
        sm = np.convolve(th, np.ones(5) / 5, mode="same")
        w = next((i for i in range(int(0.6 * L), L) if sm[i] > 1.3 * fore), int(0.8 * L))
        sgn = -1 if side == "L" else 1
        x_at = lambda i: (tl if side == "L" else tr) + sgn * i
        y_line = float(np.median(cy[: max(3, int(0.6 * L))]))
        arms[side] = {"shoulder": (x_at(0), y_line), "elbow": (x_at(int(0.47 * w)), y_line), "wrist": (x_at(w), y_line),
                      "tip": (x_at(L - 1), y_line), "thick": float(np.median(th[: int(0.4 * L)])), "fore": float(fore), "dir": sgn}
    # neck: the head is everything above the arm band's top, less a little
    neck_y = a0 - 0.01 * H
    # crotch: first row below the torso where the figure splits into two runs near the middle
    crotch = None
    for y in range(a1 + int(0.1 * H), bot):
        r = [(s, e) for s, e in _runs(fig[y]) if e - s > 3]
        if len(r) >= 2:
            crotch = y; break
    skirt = crotch is None or crotch > top + 0.8 * H
    if skirt:   # a long skirt, dress or sari: the legs part only below its hem
        crotch = next((y for y in range(int(top + 0.8 * H), bot) if len([r for r in _runs(fig[y]) if r[1] - r[0] > 3]) >= 2), None)
        if crotch is None or crotch > top + 0.97 * H:
            raise ValueError("no gap between the legs or feet found: draw the legs (or at least the feet) apart")
    gaps = [(r1[1], r2[0]) for r1, r2 in zip(_runs(fig[crotch + 5])[:-1], _runs(fig[crotch + 5])[1:])]
    gx = min(gaps, key=lambda g: abs((g[0] + g[1]) / 2 - cx)) if gaps else (cx, cx)
    leg_mid = (gx[0] + gx[1]) / 2
    legs = {}
    for side in ("L", "R"):
        lo, hi = (0, int(leg_mid)) if side == "L" else (int(leg_mid), fig.shape[1])
        wid, cxs = [], []
        for y in range(crotch, bot + 1):
            c = np.where(fig[y, lo:hi])[0]
            wid.append((c.max() - c.min() + 1) if len(c) else 0); cxs.append(lo + (c.max() + c.min()) / 2 if len(c) else np.nan)
        wid = np.array(wid, float); n = len(wid)
        shin = np.median(wid[int(0.35 * n): int(0.6 * n)])
        sm = np.convolve(wid, np.ones(5) / 5, mode="same")
        a = next((i for i in range(int(0.55 * n), n) if sm[i] > 1.25 * shin), int(0.85 * n))   # the shoe is wider than the shin
        ankle_y = crotch + a
        hip_x = float(np.nanmedian(cxs[: max(3, int(0.3 * n))]))
        legs[side] = {"hip": (hip_x, crotch - 0.03 * H), "knee": (float(np.nanmedian(cxs[int(0.4 * n): int(0.6 * n)])), crotch + 0.5 * a),
                      "ankle": (float(np.nanmedian(cxs[max(0, a - 10): a + 1])), ankle_y), "thick": float(shin)}
    if skirt:   # the leg's joint at the hem: the feet shuffle under it
        for Lg in legs.values():
            Lg["hip"] = (Lg["hip"][0], crotch - 0.01 * H)
    return {"skirt": bool(skirt), "top": int(top), "bot": int(bot), "left": int(left), "right": int(right), "H": int(H), "torso": (tl, tr), "cx": cx,
            "band": (int(a0), int(a1)), "neck_y": float(neck_y), "crotch": int(crotch), "arms": arms, "legs": legs}


# ------------------------------------------------------------------ parts
def _disc(shape, c, r):
    yy, xx = np.ogrid[: shape[0], : shape[1]]
    return (xx - c[0]) ** 2 + (yy - c[1]) ** 2 <= r * r


def _halfplane(shape, p, q, keep_side):
    """pixels on one side of the line through p perpendicular to the direction p->q: keep_side +1 = towards q"""
    yy, xx = np.mgrid[: shape[0], : shape[1]]
    d = np.array(q, float) - np.array(p, float); d /= np.linalg.norm(d) + 1e-9
    s = (xx - p[0]) * d[0] + (yy - p[1]) * d[1]
    return s >= 0 if keep_side > 0 else s < 0


def part_masks(fig, lm, rgb=None):
    """{part: mask} on the image, each with a round cap over its joint; and {part: pivot}"""
    shp = fig.shape; masks, piv = {}, {}
    hair = np.zeros(shp, bool)
    if rgb is not None:   # the hair's colour (the top of the head): hair touching a sleeve stays with the head
        top_rows = fig & (np.arange(shp[0])[:, None] < lm["top"] + 0.06 * lm["H"])
        hc = _mode_colour(rgb[top_rows]); hair = (np.abs(rgb - hc).sum(-1) < 45) & fig
        # only hair-coloured areas joined to the hair on top of the head (grey edge pixels along an outline elsewhere
        # can be near a grey hair's colour)
        lab, _ = ND.label(hair); ids = np.unique(lab[top_rows & hair]); hair = np.isin(lab, ids[ids > 0])
    tl, tr = lm["torso"]; a0, a1 = lm["band"]
    yy, xx = np.mgrid[: shp[0], : shp[1]]
    arm_any = np.zeros(shp, bool); caps = {}
    for side, A in lm["arms"].items():
        s, e, w, t = A["shoulder"], A["elbow"], A["wrist"], A["tip"]
        out = (xx <= tl) if side == "L" else (xx >= tr)
        band = (yy >= a0 - 0.06 * lm["H"]) & (yy <= a1 + 0.06 * lm["H"])
        cand = fig & out & band & ~hair
        # shoulder to wrist: in each column only the run through the arm's line (hair tips and their outline above
        # the sleeve are other runs); past the wrist the hand's whole piece (a raised thumb is its own run)
        arm = np.zeros(shp, bool); yl = int(round(s[1]))
        x_w = int(round(w[0]))
        cols = range(int(min(s[0], x_w)), int(max(s[0], x_w)) + 1)
        for x in cols:
            for r0, r1 in _runs(cand[:, x]):
                if r0 <= yl < r1:
                    arm[r0:r1, x] = True
        beyond = cand & ((xx < x_w) if side == "L" else (xx > x_w))
        lab, _ = ND.label(beyond | arm)
        k = lab[yl, x_w] if (beyond | arm)[yl, x_w] else 0
        arm = arm | ((lab == k) & beyond) if k else arm | beyond
        arm_any |= arm
        # the shoulder: the sleeve's run at the torso side gives its thickness; the joint sits inside the torso by
        # 0.6 of its radius, and the upper arm gets a drawn round end there (fill and outline of the sleeve), so a
        # hanging or raised arm has a round shoulder instead of the straight edge it was cut along
        x0 = int(tl if side == "L" else tr); inward = 1 if side == "L" else -1
        xs_ = x0 - inward * 2
        run = next(((r0, r1) for r0, r1 in _runs(arm[:, xs_]) if r0 <= yl < r1), (yl - 10, yl + 10))
        T = run[1] - run[0]; rr = T / 2; yc = (run[0] + run[1]) / 2
        P = (x0 + inward * 0.6 * rr, yc)
        lw = 2
        if rgb is not None:
            col = rgb[run[0]:run[1], xs_].sum(-1)
            lw = int(np.clip(next((i for i, v in enumerate(col) if v > 330), 3), 2, 0.2 * T))
            near = arm & (np.abs(xx - x0) < 0.4 * T) & (rgb.sum(-1) > 330)
            fillc = _mode_colour(rgb[near])
        else:
            fillc = np.array([200, 200, 200])
        caps[side] = {"P": P, "r": rr, "lw": lw, "fill": fillc, "seam": (x0, run[0], run[1], inward)}
        r_fo = A["fore"] * 0.6
        up = arm & ~_halfplane(shp, e, t, +1)
        fo = arm & _halfplane(shp, e, t, +1) & ~_halfplane(shp, w, t, +1) | (arm & _disc(shp, e, r_fo))
        ha = arm & _halfplane(shp, w, t, +1) | (arm & _disc(shp, w, r_fo * 0.8))
        masks[f"upperarm_{side}"], masks[f"forearm_{side}"], masks[f"hand_{side}"] = up, fo, ha
        piv[f"upperarm_{side}"], piv[f"forearm_{side}"], piv[f"hand_{side}"] = P, e, w
    body = fig & ~arm_any
    # anything left beside the torso at arm height is stray (edge pixels of the arms), not body
    body &= ~(((yy >= a0 - 0.06 * lm["H"]) & (yy <= a1 + 0.06 * lm["H"])) & ((xx < tl - 3) | (xx > tr + 3)) & ~ND.binary_dilation(hair, iterations=5))
    neck_y, crotch = lm["neck_y"], lm["crotch"]
    head = body & (yy < neck_y + 0.03 * lm["H"])
    # all of the hair goes with the head, wherever its tips reach (with its outline): the hair touching the head
    lab, _ = ND.label(hair & body)
    ids = np.unique(lab[head & hair]); ids = ids[ids > 0]
    hair_all = ND.binary_dilation(np.isin(lab, ids), iterations=3) & body
    head = head | hair_all
    masks["head"] = head; piv["head"] = (lm["cx"], neck_y)
    # hips: the band above the crotch (the shorts' or skirt's top), torso above it
    # (with a long skirt the hips are the skirt: from halfway between the arms and the hem down to the hem)
    hip_top = (a1 + 0.45 * (crotch - a1)) if lm.get("skirt") else crotch - 0.12 * lm["H"]
    legs_any = np.zeros(shp, bool)
    for side, Lg in lm["legs"].items():
        lo = (xx < (lm["legs"]["L"]["hip"][0] + lm["legs"]["R"]["hip"][0]) / 2) if side == "L" else (xx >= (lm["legs"]["L"]["hip"][0] + lm["legs"]["R"]["hip"][0]) / 2)
        leg = body & lo & (yy >= crotch - 0.02 * lm["H"])
        legs_any |= leg
        h, k, a = Lg["hip"], Lg["knee"], Lg["ankle"]
        r = Lg["thick"] * 0.6
        th = leg & (yy < k[1]) | ((leg if lm.get("skirt") else body & lo) & _disc(shp, h, r) & (yy >= hip_top))   # under a skirt no cloth swings with the leg
        sh = leg & (yy >= k[1]) & (yy < a[1]) | (leg & _disc(shp, k, r))
        ft = leg & (yy >= a[1]) | (leg & _disc(shp, a, r * 0.8))
        masks[f"thigh_{side}"], masks[f"shin_{side}"], masks[f"foot_{side}"] = th, sh, ft
        piv[f"thigh_{side}"], piv[f"shin_{side}"], piv[f"foot_{side}"] = h, k, a
    trunk = body & ~legs_any & (yy >= neck_y - 0.01 * lm["H"]) & ~(hair_all & (yy >= neck_y + 0.03 * lm["H"]))
    masks["torso"] = trunk & (yy < hip_top + 0.02 * lm["H"])
    masks["hip"] = trunk & (yy >= hip_top - 0.02 * lm["H"])
    mid_hip = (lm["cx"], hip_top)
    piv["torso"], piv["hip"] = mid_hip, mid_hip
    return masks, piv, caps


# ------------------------------------------------------------------ face features
def face_features(rgb, head_mask):
    """eyes and mouth on the face: blobs enclosed by skin in the head's lower part -> (skin colour, eyes [boxes],
    mouth box, ink colour)"""
    ys, xs = np.where(head_mask)
    y0, y1 = ys.min(), ys.max()
    lower = head_mask & (np.arange(head_mask.shape[0])[:, None] > y0 + 0.45 * (y1 - y0))
    skin = _mode_colour(rgb[lower & ((rgb.sum(-1)) > 200)])
    near_skin = (np.abs(rgb - skin).sum(-1) < 60) & head_mask
    face = ND.binary_fill_holes(ND.binary_closing(near_skin, iterations=2))
    feat = face & ~near_skin
    lab, n = ND.label(ND.binary_dilation(feat, iterations=1))
    blobs = []
    for i in range(1, n + 1):
        m = lab == i; by, bx = np.where(m)
        if len(by) < 12:
            continue
        dark = (rgb[m].sum(-1) < 300).mean()
        blobs.append({"m": m, "box": (bx.min(), by.min(), bx.max(), by.max()), "c": (bx.mean(), by.mean()), "n": len(by), "dark": dark})
    fy0, fy1 = np.where(face)[0].min(), np.where(face)[0].max()
    fx = np.where(face)[1]; fcx = (fx.min() + fx.max()) / 2; fw = fx.max() - fx.min()
    # eyes: the two darkest sizeable blobs either side of the centre, in the face's upper-middle
    for b in blobs:   # how solid a mark is: an eye is a filled dot, a glasses rim a ring
        x0, y0, x1, y1 = b["box"]; b["solid"] = b["n"] / max(1, (x1 - x0 + 1) * (y1 - y0 + 1))
    cand = [b for b in blobs if fy0 + 0.2 * (fy1 - fy0) < b["c"][1] < fy0 + 0.7 * (fy1 - fy0) and b["dark"] > 0.3 and b["n"] > 40 and b["solid"] > 0.4]
    left = [b for b in cand if b["c"][0] < fcx - 0.08 * fw]; right = [b for b in cand if b["c"][0] > fcx + 0.08 * fw]
    eyes = [max(left, key=lambda b: b["n"] * b["dark"]), max(right, key=lambda b: b["n"] * b["dark"])] if left and right else []
    # mouth: the widest mark below the eyes and within about an eye spacing of them (the nose is narrower; the chin
    # and collar lines are further down)
    ey = max((e["c"][1] for e in eyes), default=fy0 + 0.5 * (fy1 - fy0))
    sp = abs(eyes[1]["c"][0] - eyes[0]["c"][0]) if len(eyes) == 2 else 0.35 * fw
    mx = (eyes[0]["c"][0] + eyes[1]["c"][0]) / 2 if len(eyes) == 2 else fcx
    mc = [b for b in blobs if ey + 0.15 * sp < b["c"][1] < ey + 1.3 * sp and abs(b["c"][0] - mx) < 0.4 * sp and all(b is not e for e in eyes)
          and b["box"][2] - b["box"][0] > 0.28 * sp]   # wider than a nose
    mouth = min(mc, key=lambda b: b["c"][1]) if mc else None   # the first such mark below the eyes (chin and collar lines are lower)
    ink = _mode_colour(rgb[head_mask & (rgb.sum(-1) < 260) & (rgb.sum(-1) > 40)])
    return {"skin": skin, "face": face, "eyes": eyes, "mouth": mouth, "ink": ink}


def mouth_sheet(path, white_tol=40):
    """the mouths on a sheet, in reading order (rows top to bottom, left to right): [RGBA crops]"""
    rgb = _load(path); fig = (255 - rgb).sum(-1) >= white_tol
    # marks of one mouth (a smile and its chin line) close together; mouths are far apart
    lab, n = ND.label(ND.binary_dilation(fig, iterations=max(4, int(0.02 * max(fig.shape)))))
    items = []
    for i in range(1, n + 1):
        by, bx = np.where(lab == i)
        if len(by) < 300:
            continue
        m = (lab == i) & fig; by, bx = np.where(m)
        items.append(((by.min() + by.max()) / 2, (bx.min() + bx.max()) / 2, (bx.min(), by.min(), bx.max() + 1, by.max() + 1), m))
    if not items:
        return []
    hs = sorted(it[0] for it in items); rowh = np.median([it[2][3] - it[2][1] for it in items])
    rows = []
    for it in sorted(items, key=lambda t: t[0]):
        if rows and abs(it[0] - rows[-1][0][0]) < rowh:
            rows[-1].append(it)
        else:
            rows.append([it])
    out = []
    for r in rows:
        for it in sorted(r, key=lambda t: t[1]):
            x0, y0, x1, y1 = it[2]; m = it[3][y0:y1, x0:x1]
            crop = np.dstack([rgb[y0:y1, x0:x1], (ND.binary_fill_holes(m) * 255)]).astype(np.uint8)
            out.append(Image.fromarray(crop, "RGBA"))
    return out


# ------------------------------------------------------------------ assembly
def _rot_point(p, c, deg):
    """PIL's rotate(deg) turns the picture counter-clockwise on screen; the same for a point (y down)"""
    a = math.radians(deg); dx, dy = p[0] - c[0], p[1] - c[1]
    return (c[0] + dx * math.cos(a) + dy * math.sin(a), c[1] - dx * math.sin(a) + dy * math.cos(a))


def _uri(im):
    b = io.BytesIO(); im.save(b, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


def build(sheet, name, mouths=None, mouths_extra=None, model="", license_id=""):
    """-> (puppet dict, report)"""
    rgb = _load(sheet)
    fig = figure_mask(rgb)
    lm = landmarks(fig)
    masks, piv, caps = part_masks(fig, lm, rgb)
    ff = face_features(rgb, masks["head"])
    rgba = np.dstack([rgb, np.full(rgb.shape[:2], 255)]).astype(np.uint8)
    # lift the eyes and the mouth off the face: paint them over with the skin colour (only inside the face)
    head_rgb = rgb.copy()
    lift = np.zeros(fig.shape, bool)
    for b in ff["eyes"] + ([ff["mouth"]] if ff["mouth"] else []):
        lift |= ND.binary_dilation(b["m"], iterations=2) & ff["face"]
    head_rgb[lift] = ff["skin"]
    # scale and placement on the artboard: soles on the ground, the body's centre at x = 300
    s = HEIGHT / max(1, lm["H"])
    ax = lambda x: (x - lm["cx"]) * s + ARTBOARD[0] / 2
    ay = lambda y: (y - lm["bot"]) * s + GROUND
    # the arms hang down: swing each arm's parts and pivots about its shoulder
    swing = {"L": 90.0, "R": -90.0}

    inkc = tuple(int(v) for v in ff["ink"])

    def layer(part):
        src = head_rgb if part == "head" else rgb
        a = np.dstack([src, masks[part] * 255]).astype(np.uint8)
        if part == "torso":   # close the torso's sides where the sleeves joined it, with the drawing's outline
            for c in caps.values():
                x0, y0_, y1_, inward = c["seam"]; xa, xb = sorted((x0, x0 + inward * c["lw"]))
                a[y0_:y1_, xa:xb + 1, :3] = inkc; a[y0_:y1_, xa:xb + 1, 3] = 255
        im = Image.fromarray(a, "RGBA"); p = piv[part]; side = part[-1]
        if part.startswith("upperarm"):   # the drawn round shoulder under the sleeve
            c = caps[side]; cap = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(cap)
            (px, py), r = c["P"], c["r"]
            fillc = tuple(int(v) for v in c["fill"]) + (255,)
            if side == "L":   # the back arm, behind the torso: only its outer edge shows, so it has the outline
                d.ellipse([px - r, py - r, px + r, py + r], fill=inkc + (255,)); r2 = r - c["lw"]
            else:             # the front arm lies over the torso: fill only, so no circle is drawn on the shirt
                r2 = r - c["lw"] * 0.5
            d.ellipse([px - r2, py - r2, px + r2, py + r2], fill=fillc)
            cap.alpha_composite(im); im = cap
        if part.split("_")[0] in ("upperarm", "forearm", "hand"):
            sh = piv[f"upperarm_{side}"]
            im = im.rotate(swing[side], resample=Image.BICUBIC, center=sh, expand=False)
            p = _rot_point(p, sh, swing[side])
        return im, p

    # room for the hanging arms: pad the page downwards before rotating
    pad = int(max(A["tip"][0] - A["shoulder"][0] if A["dir"] > 0 else A["shoulder"][0] - A["tip"][0] for A in lm["arms"].values()) + 20)
    if pad > 0:
        rgb = np.pad(rgb, ((0, pad), (0, 0), (0, 0)), constant_values=255); head_rgb = np.pad(head_rgb, ((0, pad), (0, 0), (0, 0)), constant_values=255)
        for k in masks:
            masks[k] = np.pad(masks[k], ((0, pad), (0, 0)))
        ff["face"] = np.pad(ff["face"], ((0, pad), (0, 0)))
    template_z = {"hip": 20, "torso": 22, "head": 40, "upperarm_L": 10, "forearm_L": 11, "hand_L": 12, "upperarm_R": 30, "forearm_R": 31,
                  "hand_R": 32, "thigh_L": 14, "shin_L": 15, "foot_L": 16, "thigh_R": 17, "shin_R": 18, "foot_R": 19}
    parent = {"hip": None, "torso": "hip", "head": "torso", "upperarm_L": "torso", "forearm_L": "upperarm_L", "hand_L": "forearm_L",
              "upperarm_R": "torso", "forearm_R": "upperarm_R", "hand_R": "forearm_R", "thigh_L": "hip", "shin_L": "thigh_L", "foot_L": "shin_L",
              "thigh_R": "hip", "shin_R": "thigh_R", "foot_R": "shin_R"}
    parts, report = {}, {}
    for part in template_z:
        im, p = layer(part)
        bb = im.getbbox()
        if not bb:
            raise ValueError(f"part {part} came out empty")
        crop = im.crop(bb)
        parts[part] = {"parent": parent[part], "pivot": [round(ax(p[0]), 1), round(ay(p[1]), 1)], "z": template_z[part],
                       "strokes": [{"image": _uri(crop), "x": round(ax(bb[0]), 1), "y": round(ay(bb[1]), 1),
                                    "w": round((bb[2] - bb[0]) * s, 1), "h": round((bb[3] - bb[1]) * s, 1)}]}
        report[part] = {"pixels": int(masks[part].sum()), "pivot": parts[part]["pivot"]}
    # eyes: open = the drawn eyes; closed = a curved lid line where each eye was; half = the eye's top half lifted
    swaps = {}
    ink = _hex(ff["ink"])
    if len(ff["eyes"]) == 2:
        op, cl = [], []
        for b in ff["eyes"]:
            x0, y0, x1, y1 = b["box"]; m = b["m"][y0:y1 + 1, x0:x1 + 1]
            crop = Image.fromarray(np.dstack([rgb[y0:y1 + 1, x0:x1 + 1], m * 255]).astype(np.uint8), "RGBA")
            op.append({"image": _uri(crop), "x": round(ax(x0), 1), "y": round(ay(y0), 1), "w": round((x1 - x0 + 1) * s, 1), "h": round((y1 - y0 + 1) * s, 1)})
            cxe, cye, wx = ax((x0 + x1) / 2), ay((y0 + y1) / 2), (x1 - x0) * s / 2
            cl.append({"d": f"M{cxe - wx:.1f} {cye:.1f} Q{cxe:.1f} {cye + wx * 0.55:.1f} {cxe + wx:.1f} {cye:.1f}", "fill": "none", "stroke": "ink", "width": round(max(2.5, 0.22 * wx), 1)})
        swaps["eyes"] = {"anchor": "head", "z": 42, "shapes": {"open": op, "closed": cl}}
    # mouth: the face's own mouth is the smile; a sheet of mouths fills the lip-sync shapes at its scale
    if ff["mouth"]:
        x0, y0, x1, y1 = ff["mouth"]["box"]; m = ff["mouth"]["m"][y0:y1 + 1, x0:x1 + 1]
        own = Image.fromarray(np.dstack([rgb[y0:y1 + 1, x0:x1 + 1], m * 255]).astype(np.uint8), "RGBA")
        mcx, mcy, mw = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0 + 1)

        def place(im, k=None, flip=False):
            k = k or 1.0
            w, h = im.size[0] * k * s, im.size[1] * k * s
            if flip:
                im = im.transpose(Image.FLIP_TOP_BOTTOM)
            return [{"image": _uri(im), "x": round(ax(mcx) - w / 2, 1), "y": round(ay(mcy) - h * 0.35, 1), "w": round(w, 1), "h": round(h, 1)}]
        # closed (m, b, p and at rest) is the face's own closed smile, as drawn
        shapes = {"closed": place(own, 1.0), "smile": place(own, 1.0)}
        shapes["frown"] = place(own, 1.0, flip=True)
        sheet_m = mouth_sheet(mouths) if mouths else []
        extra = mouth_sheet(mouths_extra) if mouths_extra else []
        report["mouth_sheet"] = len(sheet_m)
        if len(sheet_m) >= 6:
            k = mw / sheet_m[0].size[0]   # the sheet's closed smile is drawn the face's mouth's width
            if len(sheet_m) >= 8:   # smile, slightly open, ah, oh, oo, ee, m, l
                pick = {"small": sheet_m[1], "wide": sheet_m[2], "O": sheet_m[3], "FV": sheet_m[5],
                        "mid": (extra[1] if len(extra) >= 2 else sheet_m[5])}
            else:                   # smile, slightly open, ah, oh, ee, l
                pick = {"small": sheet_m[1], "wide": sheet_m[2], "O": sheet_m[3], "FV": sheet_m[4], "mid": sheet_m[5]}
            for sh, im in pick.items():
                shapes[sh] = place(im, k)
            report["mouth_scale"] = round(k, 3)
        swaps["mouth"] = {"anchor": "head", "z": 45, "shapes": shapes}
    palette = {"skin": _hex(ff["skin"]), "ink": ink, "eye": "#ffffff"}
    for slot, part in (("cloth1", "torso"), ("cloth2", "hip"), ("shoe", "foot_L")):
        px = rgb[masks[part] & (rgb.sum(-1) > 120)]
        palette[slot] = _hex(_mode_colour(px))
    head_px = rgb[masks["head"] & ~ff["face"] & (rgb.sum(-1) < 700)]
    palette["hair"] = _hex(_mode_colour(head_px))
    puppet = {"format": "doodleberry.puppet", "version": "0.14", "name": name, "template": "humanoid", "artboard": list(ARTBOARD), "ground": GROUND,
              "palette": palette, "parts": parts, "swaps": swaps, "acting": {"gestures": "humanoid"},
              "meta": {"author": "cast.from_sheet", "source": "generated character sheet", "model": model or "unrecorded",
                       "license": license_id or "unrecorded", "note": "drawn by an image model from a written description; check it resembles no existing character"}}
    report.update({"eyes": len(ff["eyes"]), "mouth": bool(ff["mouth"]), "scale": round(s, 4), "palette": palette,
                   "landmarks": {k: lm[k] for k in ("band", "torso", "crotch", "neck_y", "H", "skirt")}})
    return puppet, report
