"""Geometry shared by the exporters: SVG path parsing to cubic Béziers, 2D affine matrices, the puppet skeleton
(same maths as puppet/loader/puppet.js) and the swap-selection rules for a baked frame."""
import math
import re

# ---------- SVG path -> subpaths of cubic segments [(p0, c1, c2, p1), ...] ----------
_TOK = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def _arc_to_cubics(p0, rx, ry, phi, fa, fs, p1):
    x1, y1 = p0; x2, y2 = p1
    if rx == 0 or ry == 0:
        return [(p0, p0, p1, p1)]
    cp, sp = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p, y1p = cp * dx + sp * dy, -sp * dx + cp * dy
    rx, ry = abs(rx), abs(ry)
    lam = x1p ** 2 / rx ** 2 + y1p ** 2 / ry ** 2
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx ** 2 * ry ** 2 - rx ** 2 * y1p ** 2 - ry ** 2 * x1p ** 2
    den = rx ** 2 * y1p ** 2 + ry ** 2 * x1p ** 2
    co = math.sqrt(max(0, num / den)) if den else 0
    if fa == fs:
        co = -co
    cxp, cyp = co * rx * y1p / ry, -co * ry * x1p / rx
    cx, cy = cp * cxp - sp * cyp + (x1 + x2) / 2, sp * cxp + cp * cyp + (y1 + y2) / 2
    ang = lambda ux, uy, vx, vy: math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
    t1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dt = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not fs and dt > 0:
        dt -= 2 * math.pi
    elif fs and dt < 0:
        dt += 2 * math.pi
    n = max(1, int(math.ceil(abs(dt) / (math.pi / 2))))
    out, d = [], dt / n
    k = 4 / 3 * math.tan(d / 4)
    pt = lambda a: (cx + rx * math.cos(a) * cp - ry * math.sin(a) * sp, cy + rx * math.cos(a) * sp + ry * math.sin(a) * cp)
    der = lambda a: (-rx * math.sin(a) * cp - ry * math.cos(a) * sp, -rx * math.sin(a) * sp + ry * math.cos(a) * cp)
    a = t1
    for _ in range(n):
        b = a + d
        pa, pb, da, db = pt(a), pt(b), der(a), der(b)
        out.append((pa, (pa[0] + k * da[0], pa[1] + k * da[1]), (pb[0] - k * db[0], pb[1] - k * db[1]), pb))
        a = b
    return out


def parse_path(d):
    """-> list of (segments, closed) where segments are cubic tuples."""
    toks = _TOK.findall(d)
    i, cmd = 0, None
    cur = start = (0.0, 0.0)
    subs, segs = [], []
    last_c = None

    def num():
        nonlocal i
        v = float(toks[i]); i += 1
        return v

    def close_sub(closed):
        nonlocal segs
        if segs:
            subs.append((segs, closed))
        segs = []

    while i < len(toks):
        if re.match(r"[A-Za-z]", toks[i]):
            cmd = toks[i]; i += 1
        rel = cmd.islower(); C = cmd.upper()
        if C == "Z":
            if cur != start:
                segs.append((cur, cur, start, start))
            cur = start
            close_sub(True); last_c = None
            continue
        ox, oy = cur if rel else (0, 0)
        if C == "M":
            close_sub(False)
            cur = start = (num() + ox, num() + oy); cmd = "l" if rel else "L"; last_c = None
        elif C == "L":
            p = (num() + ox, num() + oy); segs.append((cur, cur, p, p)); cur = p; last_c = None
        elif C == "H":
            p = (num() + (ox if rel else 0), cur[1]); segs.append((cur, cur, p, p)); cur = p; last_c = None
        elif C == "V":
            p = (cur[0], num() + (oy if rel else 0)); segs.append((cur, cur, p, p)); cur = p; last_c = None
        elif C == "C":
            c1 = (num() + ox, num() + oy); c2 = (num() + ox, num() + oy); p = (num() + ox, num() + oy)
            segs.append((cur, c1, c2, p)); cur = p; last_c = c2
        elif C == "S":
            c1 = (2 * cur[0] - last_c[0], 2 * cur[1] - last_c[1]) if last_c else cur
            c2 = (num() + ox, num() + oy); p = (num() + ox, num() + oy)
            segs.append((cur, c1, c2, p)); cur = p; last_c = c2
        elif C == "Q":
            q = (num() + ox, num() + oy); p = (num() + ox, num() + oy)
            c1 = (cur[0] + 2 / 3 * (q[0] - cur[0]), cur[1] + 2 / 3 * (q[1] - cur[1]))
            c2 = (p[0] + 2 / 3 * (q[0] - p[0]), p[1] + 2 / 3 * (q[1] - p[1]))
            segs.append((cur, c1, c2, p)); cur = p; last_c = None
        elif C == "A":
            rx, ry, phi, fa, fs = num(), num(), num(), num(), num()
            p = (num() + ox, num() + oy)
            segs.extend(_arc_to_cubics(cur, rx, ry, phi, int(fa), int(fs), p)); cur = p; last_c = None
        else:
            raise ValueError(f"unsupported path command {cmd}")
    close_sub(False)
    return subs


def sample(segs, per=8):
    pts = []
    for (p0, c1, c2, p1) in segs:
        for k in range(per):
            t = k / per; u = 1 - t
            pts.append((u ** 3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * p1[0],
                        u ** 3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * p1[1]))
    if segs:
        pts.append(segs[-1][3])
    return pts


# ---------- affine [a, b, c, d, e, f] ----------
I = [1, 0, 0, 1, 0, 0]


def mul(m, n):
    return [m[0] * n[0] + m[2] * n[1], m[1] * n[0] + m[3] * n[1], m[0] * n[2] + m[2] * n[3], m[1] * n[2] + m[3] * n[3],
            m[0] * n[4] + m[2] * n[5] + m[4], m[1] * n[4] + m[3] * n[5] + m[5]]


def rot_about(deg, p):
    r = math.radians(deg); c, s = math.cos(r), math.sin(r)
    return [c, s, -s, c, p[0] - c * p[0] + s * p[1], p[1] - s * p[0] - c * p[1]]


def apply(m, p):
    return (m[0] * p[0] + m[2] * p[1] + m[4], m[1] * p[0] + m[3] * p[1] + m[5])


def _scale_of(scales, pid):
    v = (scales or {}).get(pid)
    return None if v is None else (list(v) if isinstance(v, (list, tuple)) else [v, v])


def part_matrices(puppet, angles, shifts=None, scales=None):
    """world matrices per part; shifts[part] = [dx, dy] moves a part in its parent's space before it rotates (v0.4);
    scales[part] = [sx, sy] stretches the part's own drawing about its pivot and carries its children's pivots, without
    shearing them (v0.9, same maths as puppet.js)"""
    parts, M, B = puppet["parts"], {}, {}
    shifts = shifts or {}

    def visit(pid):
        if pid in B:
            return
        par = parts[pid].get("parent")
        par = par if par in parts else None
        if par:
            visit(par)
        dx, dy = (shifts.get(pid) or [0, 0])
        ps = _scale_of(scales, par) if par else None
        if ps:
            pp, cp = parts[par]["pivot"], parts[pid]["pivot"]
            dx += (ps[0] - 1) * (cp[0] - pp[0]); dy += (ps[1] - 1) * (cp[1] - pp[1])
        local = rot_about(angles.get(pid, 0) or 0, parts[pid]["pivot"])
        if dx or dy:
            local = mul([1, 0, 0, 1, dx, dy], local)
        B[pid] = mul(B[par] if par else I, local)
        own = _scale_of(scales, pid)
        if own:
            px, py = parts[pid]["pivot"]
            M[pid] = mul(B[pid], [own[0], 0, 0, own[1], px - own[0] * px, py - own[1] * py])
        else:
            M[pid] = B[pid]
    for pid in parts:
        visit(pid)
    return M


def root_matrix(puppet, fr):
    hip = puppet["parts"].get("hip", {}).get("pivot", [puppet["artboard"][0] / 2, puppet["ground"]])
    s, flip = fr.get("s", 1), fr.get("flip", 1) * (fr.get("squash") or 1)
    ox, oy = fr.get("offset") or [0, 0]
    # translate(x,y) scale(s*flip, s) translate(-hip.x + ox, -ground + oy)
    return [s * flip, 0, 0, s, fr["x"] + s * flip * (-hip[0] + ox), fr["y"] + s * (-puppet["ground"] + oy)]


# ---------- swap choice (mirrors puppet.js) ----------
def chosen_swaps(puppet, fr):
    out = {}
    for sid, sw in (puppet.get("swaps") or {}).items():
        shapes = sw["shapes"]
        if sid == "mouth":
            shape = fr.get("mouth") or "closed"
        elif sid == "eyes":
            b = fr.get("blink") or 0
            shape = fr.get("eyes") or ("closed" if b > 0.6 else "half" if b > 0.25 else "open")
        elif sid == "brows":
            shape = fr.get("brows") or "neutral"
        elif sid == "pupils":
            if (fr.get("blink") or 0) > 0.25 or fr.get("eyes") == "closed":
                continue
            shape = "default"
        else:
            shape = fr.get(sid)
            if not shape:
                continue
        strokes = shapes.get(shape) or []
        if not strokes and sid == "eyes" and shape == "half":
            shape, strokes = "open", shapes.get("open") or []
        if not strokes and sid == "mouth":
            shape, strokes = "closed", shapes.get("closed") or []
        if strokes:
            out[sid] = shape
    return out


def colour(v, pal):
    if not v or v == "none":
        return None
    return v if v.startswith("#") else pal.get(v, "#ff00ff")


def hex_rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def in_view(puppet, view):
    """apply a v0.2 view's overrides (parts and swap shapes) to a puppet"""
    v = (puppet.get("views") or {}).get(view) if view else None
    if not v:
        return puppet
    parts = {k: {**p, **(v.get("parts") or {}).get(k, {})} for k, p in puppet["parts"].items()}
    swaps = {}
    for k, sw in (puppet.get("swaps") or {}).items():
        o = (v.get("swaps") or {}).get(k, {})
        swaps[k] = {**sw, **o, "shapes": {**sw["shapes"], **o.get("shapes", {})}}
    return {**puppet, "parts": parts, "swaps": swaps}


# ---------- v0.4 bendy joints (mirrors puppet.js bentD: arc bend with an attachment correction) ----------
def part_axis(part):
    pts = [q for st in part.get("strokes", []) if st.get("d") for segs, _ in parse_path(st["d"]) for q in sample(segs, 2)]
    if not pts:
        return (0.0, 1.0)
    cx = sum(q[0] for q in pts) / len(pts); cy = sum(q[1] for q in pts) / len(pts)
    dx, dy = cx - part["pivot"][0], cy - part["pivot"][1]; L = math.hypot(dx, dy) or 1
    return (dx / L, dy / L)


def bend_point(q, pivot, axis, width, theta_deg):
    """artboard point of a bendy child part -> its position in the parent's space (apply the parent matrix after)"""
    ax = axis; nx = (-ax[1], ax[0]); dx, dy = q[0] - pivot[0], q[1] - pivot[1]
    s = dx * ax[0] + dy * ax[1]; n = dx * nx[0] + dy * nx[1]; L = width; h = L / 2
    if s <= -h:
        return q
    th = math.radians(theta_deg); c, si = math.cos(th), math.sin(th)
    rigid = lambda px, py: (pivot[0] + c * (px - pivot[0]) - si * (py - pivot[1]), pivot[1] + si * (px - pivot[0]) + c * (py - pivot[1]))
    if s >= h:
        return rigid(*q)
    k = th / L; u = s + h; phi = k * u

    def arc(uu):
        f = k * uu
        A = uu if abs(k) < 1e-6 else math.sin(f) / k
        B = 0 if abs(k) < 1e-6 else (1 - math.cos(f)) / k
        return (pivot[0] - h * ax[0] + A * ax[0] + B * nx[0], pivot[1] - h * ax[1] + A * ax[1] + B * nx[1])
    cu = arc(u); cp, sp = math.cos(phi), math.sin(phi)
    nr = (cp * nx[0] - sp * ax[0], cp * nx[1] - sp * ax[1])
    lx, ly = cu[0] + n * nr[0], cu[1] + n * nr[1]
    end = arc(L); want = rigid(pivot[0] + h * ax[0], pivot[1] + h * ax[1])
    w = max(0.0, min(1.0, u / L)); w = w * w * (3 - 2 * w)
    return (lx - (end[0] - want[0]) * w, ly - (end[1] - want[1]) * w)


# ---------- palette variants per scene (WP-16; mirrors Puppet.recolour in puppet.js) ----------
def recolour_hex(h, v):
    """one colour through a variant {desat, tint, tint_amt, mult}: the same arithmetic and rounding as puppet.js"""
    import math
    if not isinstance(h, str) or not h.startswith("#") or len(h) not in (4, 7):
        return h
    if len(h) == 4:
        h = "#" + "".join(c * 2 for c in h[1:])
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    g = 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]; d = v.get("desat", 0)
    c = [x + (g - x) * d for x in c]
    if v.get("tint"):
        t = [int(v["tint"][i:i + 2], 16) / 255 for i in (1, 3, 5)]; a = v.get("tint_amt", 0)
        c = [x + (y - x) * a for x, y in zip(c, t)]
    m = v.get("mult", [1, 1, 1])
    c = [min(1.0, max(0.0, x * k)) for x, k in zip(c, m)]
    return "#" + "".join(f"{int(math.floor(x * 255 + 0.5)):02x}" for x in c)


def recolour(puppet, v):
    """a copy of a puppet with every palette colour and every literal colour in its drawings put through a variant"""
    import copy
    p = copy.deepcopy(puppet)
    p["palette"] = {k: recolour_hex(x, v) for k, x in (p.get("palette") or {}).items()}

    def strokes(lst):
        for st in lst or []:
            for k in ("fill", "stroke"):
                if isinstance(st.get(k), str) and st[k].startswith("#"):
                    st[k] = recolour_hex(st[k], v)
    for part in p.get("parts", {}).values():
        strokes(part.get("strokes"))
    for sw in (p.get("swaps") or {}).values():
        for sh in (sw.get("shapes") or {}).values():
            strokes(sh)
    for view in (p.get("views") or {}).values():
        for part in (view.get("parts") or {}).values():
            strokes(part.get("strokes") if isinstance(part, dict) else None)
        for sw in (view.get("swaps") or {}).values():
            for sh in ((sw or {}).get("shapes") or {}).values():
                strokes(sh)
    return p

