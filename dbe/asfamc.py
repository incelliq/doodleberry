"""CMU motion capture (ASF skeleton + AMC motion) as 2D clips (WP-12).

The ASF gives each bone a direction and length in the rest pose (world axes, y up) and a local frame ("axis",
Euler angles in the order given); the AMC gives, per frame, the root's position and orientation and each bone's
rotations in that local frame (dof order). Forward kinematics as the ASF/AMC format defines it: a bone's rotation is
C M C^-1 (C its axis frame, M its frame's rotations) after its parent's; its end is its start plus that rotation of
direction x length. The 3D take is then seen from the front (the picture plane x, y; the camera looks along -z), and
each puppet part takes its bone's 2D direction against the puppet's own rest direction for that part (the next joint
of its chain on the artboard: CMU's rest pose is a T-pose, the puppet's is not): world angles, then local angles
(minus the parent part's). The actor faces the camera, so their left is drawn on the picture's right (bvh.side_swap).
Keys are reduced to the fewest that stay within `tol` degrees (actout.reduce_keys).
"""
import math
import re

import numpy as np

# CMU bones -> humanoid parts (by the actor's side; side_swap turns them to the picture's side)
BONES = {"lhumerus": "upperarm_L", "lradius": "forearm_L", "lhand": "hand_L", "rhumerus": "upperarm_R", "rradius": "forearm_R", "rhand": "hand_R",
         "lfemur": "thigh_L", "ltibia": "shin_L", "lfoot": "foot_L", "rfemur": "thigh_R", "rtibia": "shin_R", "rfoot": "foot_R",
         "upperneck": "neck", "head": "head"}
SPINE = ("lowerback", "thorax")   # the torso: from the base of the lower back to the end of the thorax


def _rot(axis, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return {"X": np.array([[1, 0, 0], [0, c, -s], [0, s, c]]), "Y": np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]]),
            "Z": np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])}[axis]


def _euler(vals, order):
    """rotations applied in `order` (first letter first): R = R_last ... R_first"""
    R = np.eye(3)
    for a, v in zip(order, vals):
        R = _rot(a, v) @ R
    return R


def parse_asf(text):
    bones, root = {}, {}
    units_deg = "angle rad" not in text.lower()
    sec = re.split(r"^:(\w+)", text, flags=re.M)
    parts = dict(zip(sec[1::2], sec[2::2]))
    for ln in parts.get("root", "").splitlines():
        w = ln.split()
        if w and w[0] == "order":
            root["order"] = [x.upper() for x in w[1:]]
        elif w and w[0] == "axis":
            root["axis"] = w[1].upper()
        elif w and w[0] in ("position", "orientation"):
            root[w[0]] = [float(x) for x in w[1:4]]
    for blk in re.findall(r"begin(.*?)end", parts.get("bonedata", ""), flags=re.S):
        b = {"dof": []}
        for ln in blk.splitlines():
            w = ln.split()
            if not w:
                continue
            if w[0] == "name":
                b["name"] = w[1]
            elif w[0] == "direction":
                b["dir"] = np.array([float(x) for x in w[1:4]])
            elif w[0] == "length":
                b["len"] = float(w[1])
            elif w[0] == "axis":
                b["axis"] = [float(x) for x in w[1:4]]; b["axis_order"] = w[4].upper()
            elif w[0] == "dof":
                b["dof"] = [x.lower() for x in w[1:]]
        bones[b["name"]] = b
    parent = {}
    for ln in parts.get("hierarchy", "").splitlines():
        w = ln.split()
        if not w or w[0] in ("begin", "end"):
            continue
        for ch in w[1:]:
            parent[ch] = w[0]
    for b in bones.values():
        b["C"] = _euler(b["axis"], b["axis_order"]); b["parent"] = parent.get(b["name"], "root")
    root.setdefault("axis", "XYZ"); root.setdefault("orientation", [0, 0, 0]); root.setdefault("position", [0, 0, 0])
    root["C"] = _euler(root["orientation"], root["axis"])
    return {"bones": bones, "root": root, "deg": units_deg}


def parse_amc(text):
    frames, cur = [], None
    for ln in text.splitlines():
        w = ln.split()
        if not w or w[0].startswith(("#", ":")):
            continue
        if len(w) == 1 and w[0].isdigit():
            cur = {}; frames.append(cur); continue
        if cur is not None:
            cur[w[0]] = [float(x) for x in w[1:]]
    return frames


def fk(asf, frame):
    """-> {bone: (start, end)} world positions, plus root position"""
    R0 = asf["root"]; order = R0.get("order", ["TX", "TY", "TZ", "RX", "RY", "RZ"]); v = frame.get("root", [0] * 6)
    vals = dict(zip(order, v)); pos = np.array([vals.get("TX", 0), vals.get("TY", 0), vals.get("TZ", 0)])
    rot_order = "".join(o[1] for o in order if o.startswith("R"))
    M = _euler([vals.get("R" + a, 0) for a in rot_order], rot_order)
    rootR = R0["C"] @ M @ R0["C"].T
    out = {"root": (pos, pos)}; RW = {"root": rootR}; END = {"root": pos}
    pending = list(asf["bones"])
    while pending:
        for name in list(pending):
            b = asf["bones"][name]
            if b["parent"] not in RW:
                continue
            dv = frame.get(name, []); dd = dict(zip(b["dof"], dv))
            order_ = "".join(d[1].upper() for d in b["dof"])
            Mb = _euler([dd.get("r" + a.lower(), 0) for a in order_], order_) if order_ else np.eye(3)
            R = RW[b["parent"]] @ b["C"] @ Mb @ b["C"].T
            start = END[b["parent"]]; end = start + R @ (b["dir"] * b["len"])
            RW[name], END[name] = R, end; out[name] = (start, end); pending.remove(name)
    return out


def to_clip(asf_text, amc_text, puppet, fps_in=120, fps=30, tol=0.6, facing="camera", root_scale=None, plane="front"):
    """plane "front": the picture plane x, y (the actor facing the camera); "side": seen from the side (z, y), the
    actor's way of travel to the right of the picture, for side-view puppets (walks, runs, jumps)"""
    from .actout import reduce_keys
    from .bvh import side_swap
    asf = parse_asf(asf_text); frames = parse_amc(amc_text)[:: max(1, round(fps_in / fps))]
    parts = puppet["parts"]; ts = np.arange(len(frames)) / fps
    rest = fk(asf, {})
    seg = lambda P, name: P[name][1] - P[name][0]
    if plane == "side":   # the horizontal axis is the actor's travel (z by default), signed so travel goes right
        r0, r1 = fk(asf, frames[0])["root"][0], fk(asf, frames[-1])["root"][0]
        hz = np.array([r1[0] - r0[0], 0.0, r1[2] - r0[2]]); hz = hz / (np.linalg.norm(hz) or 1) if np.linalg.norm(hz) > 1e-6 else np.array([0.0, 0.0, 1.0])
        facing = "away"   # from the side, left and right are near and far, not mirrored
    else:
        hz = np.array([1.0, 0.0, 0.0])
    proj = lambda v: (float(v @ hz), float(v[1]))
    def ang2d(v):
        x, y = proj(v); return math.degrees(math.atan2(y, x))
    match = {side_swap(p, facing): b for b, p in BONES.items() if b in asf["bones"] and side_swap(p, facing) in parts}
    # each part's rest direction on the puppet's own artboard (y down): towards the next joint of its chain, or for an
    # end part the way it is drawn (a foot points forward, a head and neck up, a hand on along its forearm); a part's
    # world angle is the angle between that and its bone in the take as the camera sees it (screen y down)
    NEXT = {"upperarm_L": "forearm_L", "forearm_L": "hand_L", "upperarm_R": "forearm_R", "forearm_R": "hand_R", "thigh_L": "shin_L",
            "shin_L": "foot_L", "thigh_R": "shin_R", "shin_R": "foot_R", "torso": "neck", "neck": "head"}
    def rest_dir(p):
        q = NEXT.get(p)
        if q in parts:
            a, b = parts[p]["pivot"], parts[q]["pivot"]
            if math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-6:
                return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        if p.startswith("hand"):
            return rest_dir("forearm" + p[4:])
        if p.startswith("foot"):
            return 0.0                 # toes forward (+x on the artboard)
        return -90.0                   # head, neck, torso: up
    scr = lambda v: (lambda x, y: math.degrees(math.atan2(-y, x)))(*proj(v))   # take vector -> screen angle (y down)
    world = {p: [] for p in match}; torso, hipline, rootpos = [], [], []
    for fr in frames:
        P = fk(asf, fr)
        for p, b in match.items():
            v = seg(P, b); x, y = proj(v)
            if math.hypot(x, y) < 0.15 * np.linalg.norm(v) and world[p]:   # pointing at the camera: its angle is noise, hold it
                world[p].append(world[p][-1]); continue
            world[p].append(scr(v) - rest_dir(p))
        if all(x in P for x in SPINE):
            torso.append(scr(P[SPINE[1]][1] - P[SPINE[0]][0]) - rest_dir("torso"))
        if plane != "side" and "lhipjoint" in P and "rhipjoint" in P:   # the pelvis line points at the camera from the side
            d, d0 = P["lhipjoint"][1] - P["rhipjoint"][1], rest["lhipjoint"][1] - rest["rhipjoint"][1]
            hipline.append(scr(d) - scr(d0))
        rootpos.append(np.array([*proj(P["root"][0]), 0.0]))
    if torso and "torso" in parts:
        world["torso"] = torso
    if hipline and "hip" in parts:
        world["hip"] = hipline
    W = {p: np.degrees(np.unwrap(np.radians(np.array(v)))) for p, v in world.items()}
    def wrot(p):
        q = parts[p].get("parent")
        while q is not None and q not in W:
            q = parts[q].get("parent")
        return W[q] if q is not None else np.zeros(len(frames))
    tracks = {}
    for p in W:
        a = W[p] - wrot(p); a = a - 360.0 * round(float(np.median(a)) / 360.0)
        keys, _ = reduce_keys(ts, a, tol)
        tracks[p] = [[round(float(ts[i]), 3), round(float(a[i]), 2)] for i in keys]
    clip = {"duration": round(float(ts[-1]), 3), "loop": False, "tracks": tracks}
    rp = np.array(rootpos); leg = sum(asf["bones"][b]["len"] for b in ("lfemur", "ltibia") if b in asf["bones"])
    if root_scale is None and leg and "thigh_L" in parts and "foot_L" in parts:
        root_scale = (parts["foot_L"]["pivot"][1] - parts["thigh_L"]["pivot"][1]) / leg   # artboard px per take unit, by leg length
    if root_scale:
        off = np.stack([(rp[:, 0] - rp[0, 0]) * root_scale, -(rp[:, 1] - rp[0, 1]) * root_scale], 1)
        keys, _ = reduce_keys(ts, off, 1.0)
        clip["offset"] = [[round(float(ts[i]), 3), [round(float(off[i, 0]), 1), round(float(off[i, 1]), 1)]] for i in keys]
    return {"clip": clip, "matched": match, "frames": len(frames), "fps": fps, "facing": facing}
