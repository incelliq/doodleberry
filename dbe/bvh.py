"""BVH (Biovision hierarchy) for clips (WP-12): motion out to other tools, motion capture in.

Export: a puppet's part tree becomes the BVH skeleton (one joint per part, named by its id, offset from its parent's
pivot to its own, y up), and a clip is sampled per frame the way the player plays it (smoothstep between keys): each
joint's Z rotation is the part's local angle (negated: the artboard's y points down, BVH's up), the root's position
is the clip's offset track. Every renderer and Blender read it.

Import: a BVH's joints are matched to the puppet's parts, by the same names (a round trip), or by the usual motion
capture names (Hips, Spine, LeftArm, LeftForeArm, ...; MAP below). Our own files carry the angles directly. Other
skeletons are posed in 3D (forward kinematics with their own channel orders), each bone projected onto the picture
plane (x, y: the camera looks along -z), and its 2D direction compared with the same bone in the BVH's rest pose,
so a 3D take becomes 2D angles as it would be seen from the front; parts with no match keep their pose. Keys are
then reduced to the fewest that stay within `tol` degrees (actout.reduce_keys).
"""
import math
import re

import numpy as np

# motion-capture joint names (CMU, Mixamo without its prefix, Rokoko, Blender's own) -> humanoid parts
MAP = {"hips": "hip", "pelvis": "hip", "root": "hip", "spine": "torso", "spine1": "torso", "chest": "torso", "upperchest": "torso",
       "neck": "neck", "neck1": "neck", "head": "head",
       "leftarm": "upperarm_L", "leftupperarm": "upperarm_L", "lshoulder": "upperarm_L", "lhumerus": "upperarm_L", "upperarm.l": "upperarm_L",
       "leftforearm": "forearm_L", "leftlowerarm": "forearm_L", "lelbow": "forearm_L", "lradius": "forearm_L", "forearm.l": "forearm_L",
       "lefthand": "hand_L", "lwrist": "hand_L", "lhand": "hand_L", "hand.l": "hand_L",
       "rightarm": "upperarm_R", "rightupperarm": "upperarm_R", "rshoulder": "upperarm_R", "rhumerus": "upperarm_R", "upperarm.r": "upperarm_R",
       "rightforearm": "forearm_R", "rightlowerarm": "forearm_R", "relbow": "forearm_R", "rradius": "forearm_R", "forearm.r": "forearm_R",
       "righthand": "hand_R", "rwrist": "hand_R", "rhand": "hand_R", "hand.r": "hand_R",
       "leftupleg": "thigh_L", "leftupperleg": "thigh_L", "lfemur": "thigh_L", "lhip": "thigh_L", "thigh.l": "thigh_L",
       "leftleg": "shin_L", "leftlowerleg": "shin_L", "ltibia": "shin_L", "lknee": "shin_L", "shin.l": "shin_L",
       "leftfoot": "foot_L", "lfoot": "foot_L", "lankle": "foot_L", "foot.l": "foot_L",
       "rightupleg": "thigh_R", "rightupperleg": "thigh_R", "rfemur": "thigh_R", "rhip": "thigh_R", "thigh.r": "thigh_R",
       "rightleg": "shin_R", "rightlowerleg": "shin_R", "rtibia": "shin_R", "rknee": "shin_R", "shin.r": "shin_R",
       "rightfoot": "foot_R", "rfoot": "foot_R", "rankle": "foot_R", "foot.r": "foot_R"}


def _smooth(k):
    return k * k * (3 - 2 * k)


def sample(keys, t):
    """a track at time t, as acting.js sampleKeys plays it (smoothstep between keys)"""
    if not keys:
        return None
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            k = _smooth(min(1.0, max(0.0, (t - t0) / ((t1 - t0) or 1))))
            if isinstance(v0, (int, float)):
                return v0 + (v1 - v0) * k
            return [a + (b - a) * k for a, b in zip(v0, v1)]
    return keys[-1][1]


def _tree(puppet):
    parts = puppet["parts"]; kids = {}
    for pid, p in parts.items():
        kids.setdefault(p.get("parent"), []).append(pid)
    return parts, kids


def export(puppet, clip, fps=30, scale=1.0, name="clip"):
    """-> BVH text: the puppet's skeleton and the clip sampled at fps"""
    parts, kids = _tree(puppet)
    roots = kids.get(None, [])
    if len(roots) != 1:
        raise ValueError(f"BVH needs one root part; this puppet has {roots}")
    order, lines = [], ["HIERARCHY"]
    f = lambda v: f"{v:.4f}"

    def joint(pid, depth, parent):
        ind = "  " * depth; p = parts[pid]
        px, py = p["pivot"]; qx, qy = parts[parent]["pivot"] if parent else (px, py)
        off = (0.0, 0.0) if parent is None else ((px - qx) * scale, -(py - qy) * scale)
        lines.append(f"{ind}{'ROOT' if parent is None else 'JOINT'} {pid}")
        lines.append(f"{ind}{{")
        lines.append(f"{ind}  OFFSET {f(off[0])} {f(off[1])} 0.0000")
        lines.append(f"{ind}  CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation" if parent is None else f"{ind}  CHANNELS 3 Zrotation Xrotation Yrotation")
        order.append(pid)
        ch = sorted(kids.get(pid, []))
        for c in ch:
            joint(c, depth + 1, pid)
        if not ch:
            lines.append(f"{ind}  End Site"); lines.append(f"{ind}  {{"); lines.append(f"{ind}    OFFSET 0.0000 {f(-20 * scale)} 0.0000"); lines.append(f"{ind}  }}")
        lines.append(f"{ind}}}")
    joint(roots[0], 0, None)
    dur = clip.get("duration") or max([k[-1][0] for k in clip["tracks"].values() if k] + [0])
    n = int(round(dur * fps)) + 1
    lines += ["MOTION", f"Frames: {n}", f"Frame Time: {1 / fps:.6f}"]
    for i in range(n):
        t = i / fps; vals = []
        for pid in order:
            a = sample(clip["tracks"].get(pid), t) or 0.0
            if pid == roots[0]:
                o = sample(clip.get("offset"), t) or [0.0, 0.0]
                vals += [o[0] * scale, -o[1] * scale, 0.0]
            vals += [-a, 0.0, 0.0]
        lines.append(" ".join(f(v) for v in vals))
    return "\n".join(lines) + "\n"


def parse(text):
    """-> {joints: [{name, parent, offset, channels}], frames: (F, C) array, frame_time}"""
    toks = re.findall(r"[^\s{}]+|[{}]", text.split("MOTION")[0])
    joints, stack, i, pending, end_of = [], [], 0, None, None
    while i < len(toks):
        tk = toks[i]
        if tk in ("ROOT", "JOINT"):
            pending = {"name": toks[i + 1], "parent": stack[-1] if stack else None, "channels": [], "offset": [0, 0, 0]}; i += 2; continue
        if tk == "End":
            pending = {"end": True, "of": stack[-1]}; i += 2; continue
        if tk == "{":
            if pending is not None and pending.get("end"):
                end_of = pending["of"]
            stack.append(None if pending.get("end") else len(joints)) if pending is not None else None
            if pending is not None and not pending.get("end"):
                joints.append(pending)
            pending = None; i += 1; continue
        if tk == "}":
            stack.pop(); i += 1; continue
        if tk == "OFFSET":
            if stack and stack[-1] is not None:
                joints[stack[-1]]["offset"] = [float(x) for x in toks[i + 1:i + 4]]
            elif stack:   # an End Site: where the joint's bone ends
                joints[end_of]["end"] = [float(x) for x in toks[i + 1:i + 4]]
            i += 4; continue
        if tk == "CHANNELS":
            n = int(toks[i + 1]); joints[stack[-1]]["channels"] = toks[i + 2:i + 2 + n]; i += 2 + n; continue
        i += 1
    mot = text.split("MOTION", 1)[1].strip().splitlines()
    nf = int(mot[0].split(":")[1]); ft = float(mot[1].split(":")[1])
    rows = [[float(x) for x in ln.split()] for ln in mot[2:2 + nf] if ln.strip()]
    return {"joints": joints, "frames": np.array(rows), "frame_time": ft}


def _rot(axis, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    if axis == "X":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if axis == "Y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def _fk(b, row):
    """world positions and rotations of every joint for one frame"""
    J = b["joints"]; pos, rot, k = [], [], 0
    for j in J:
        R = np.eye(3); t = np.array(j["offset"], float)
        for ch in j["channels"]:
            v = row[k]; k += 1
            if ch.endswith("position"):
                t = t + {"X": np.array([v, 0, 0]), "Y": np.array([0, v, 0]), "Z": np.array([0, 0, v])}[ch[0]] * (1 if j["parent"] is None else 0)
            else:
                R = R @ _rot(ch[0], v)
        if j["parent"] is None:
            pos.append(t); rot.append(R)
        else:
            pp, pr = pos[j["parent"]], rot[j["parent"]]
            pos.append(pp + pr @ np.array(j["offset"], float)); rot.append(pr @ R)
    return pos, rot


def side_swap(part, facing):
    """our puppets face the viewer and name their parts by the side of the picture they are drawn on (upperarm_L on
    the left); an actor facing the camera has their left on the picture's right, so a motion-capture "left" drives
    the puppet's _R part (facing "camera"); "away" keeps the names"""
    if facing != "camera" or not part:
        return part
    return part[:-2] + ("_R" if part.endswith("_L") else "_L") if part.endswith(("_L", "_R")) else part


def to_clip(text, puppet, fps=30, tol=0.5, facing="camera"):
    """a BVH as a clip for this puppet: {clip, matched: {part: joint}, unmatched: [joints], method}. facing: how a
    motion-capture actor stands to the camera ("camera": their left is on the picture's right); our own skeleton
    (joints named as the puppet's parts) is read as it is."""
    from .actout import reduce_keys
    b = parse(text); J = b["joints"]; parts = puppet["parts"]
    norm = lambda s: re.sub(r"[_.]([lr])$", r".\1", re.sub(r"^(mixamorig[:_]?|bip01[ _]?|[a-z]+:)", "", s.strip().lower()).replace(" ", ""))   # upperarm_L, UpperArm.L
    match = {}
    for i, j in enumerate(J):
        p = j["name"] if j["name"] in parts else side_swap(MAP.get(norm(j["name"])), facing)
        if p in parts and p not in match:
            match[p] = i
    own = all(j["name"] in parts for j in J) and all(j["channels"][-3:] == ["Zrotation", "Xrotation", "Yrotation"] for j in J)
    F = len(b["frames"]); src_ft = b["frame_time"]; ts = np.arange(F) * src_ft
    tracks, ang = {}, {}
    if own:   # our own skeleton: the Z rotations are the angles
        k = 0
        for j in J:
            nch = len(j["channels"]); zi = k + j["channels"].index("Zrotation"); ang[j["name"]] = -b["frames"][:, zi]; k += nch
        root = J[0]; off = np.stack([b["frames"][:, 0], -b["frames"][:, 1]], 1)
        method = "own skeleton: Z rotations"
    else:     # a 3D skeleton: each matched bone's direction on the picture plane against its rest direction
        rest_rows = np.zeros(b["frames"].shape[1])
        rp, _ = _fk(b, rest_rows)
        world = {p: np.zeros(F) for p in match}
        kids = {}
        for i, j in enumerate(J):
            kids.setdefault(j["parent"], []).append(i)
        def tip(i, pos, rot):   # the bone's far end: its farthest child joint at rest, else its End Site
            c = max(kids.get(i, []), key=lambda k: np.linalg.norm(J[k]["offset"]), default=None)
            if c is not None and np.linalg.norm(J[c]["offset"]) > 1e-6:
                return pos[c]
            if J[i].get("end") and np.linalg.norm(J[i]["end"]) > 1e-6:
                return pos[i] + rot[i] @ np.array(J[i]["end"], float)
            return None
        _, rr = _fk(b, rest_rows)
        for fi in range(F):
            pos, rot = _fk(b, b["frames"][fi])
            for p, i in match.items():
                e, e0 = tip(i, pos, rot), tip(i, rp, rr)
                if e is None:   # no bone to aim along (a head whose children sit on its pivot): the joint's own x axis
                    d, d0 = rot[i] @ np.array([1.0, 0, 0]), rr[i] @ np.array([1.0, 0, 0])
                else:
                    d = e - pos[i]; d0 = e0 - rp[i]
                a = math.degrees(math.atan2(d[1], d[0]) - math.atan2(d0[1], d0[0]))
                world[p][fi] = -a
        for p in world:
            world[p] = np.degrees(np.unwrap(np.radians(world[p])))
        def wrot(p):
            q = parts[p].get("parent")
            while q is not None and q not in world:
                q = parts[q].get("parent")
            return world[q] if q is not None else np.zeros(F)
        for p in world:
            ang[p] = world[p] - wrot(p)
        r0 = J[0]["offset"]; first, _ = _fk(b, b["frames"][0])
        off = np.array([[(_fk(b, b["frames"][fi])[0][0] - first[0])[0], -(_fk(b, b["frames"][fi])[0][0] - first[0])[1]] for fi in range(F)])
        method = "3D skeleton projected on the picture plane"
    for p, a in ang.items():
        if p not in parts:
            continue
        a = a - 360.0 * round(float(np.median(a)) / 360.0)
        keys, _ = reduce_keys(ts, a, tol)
        tracks[p] = [[round(float(ts[i]), 3), round(float(a[i]), 2)] for i in keys]
    clip = {"duration": round(float(ts[-1]), 3), "loop": False, "tracks": tracks}
    if np.abs(off).max() > 1e-6:
        keys, _ = reduce_keys(ts, off, max(0.5, tol))
        clip["offset"] = [[round(float(ts[i]), 3), [round(float(off[i, 0]), 2), round(float(off[i, 1]), 2)]] for i in keys]
    return {"clip": clip, "matched": {p: J[i]["name"] for p, i in match.items()}, "unmatched": [j["name"] for i, j in enumerate(J) if i not in match.values()], "method": method}
