"""Act it out (plan 3.5): a phone or webcam take becomes an action clip for a character.

    video --ffmpeg--> frames at the film rate --MediaPipe Pose + Face Landmarker--> keypoints and blendshapes
          --retarget--> joint angles per part, root offset, foot contacts, mouth/eye/brow swaps, gaze
          --ease-aware key reduction--> a clip in the v0.7 format (puppet.clips[name])

Everything is measured in image space, so the character does what the video shows: the arm on the left of the
picture drives the part drawn on the left of the artboard (`_L`). `mirror` flips the take first (a selfie preview).

Retargeting is pure geometry against the puppet's own rest pose. For a part with a video segment (shoulder to elbow
for upperarm, elbow to wrist for forearm, ...) its world rotation is the segment's angle minus the angle of the same
bone in the drawn rest pose (pivot to child pivot); the clip track is that world rotation minus the parent's, which
is exactly how puppet.js composes angles. Tracks that the take cannot see (legs in a waist-up webcam take, a hand
pointing straight at the lens) are dropped or bridged, never guessed: an idle or another clip fills them.

Keys are reduced against what Acting.evaluate will actually play (smoothstep between keys), not against straight
lines, so the reported error is the error on screen.

Detection needs `mediapipe` (Apache-2.0, requirements-tools.txt) and two Apache-2.0 model files, fetched once into
DBE_MODELS (default ~/.cache/doodleberry/models) and checked by sha256. Retargeting needs only numpy.
"""
import hashlib
import io
import json
import math
import os
import subprocess
import time
import urllib.request
from pathlib import Path

import numpy as np

from . import geom as G

MODELS = Path(os.environ.get("DBE_MODELS", str(Path.home() / ".cache" / "doodleberry" / "models")))
MODEL_FILES = {   # Apache-2.0 (MediaPipe model cards); pinned by hash
    "pose": ("pose_landmarker_full.task", "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task",
             "4eaa5eb7a98365221087693fcc286334cf0858e2eb6e15b506aa4a7ecdcec4ad"),
    "face": ("face_landmarker.task", "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task",
             "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"),
}
# MediaPipe Pose landmark indices, per anatomical side (L = the person's left)
LM = {"nose": 0, "eye": {"L": 2, "R": 5}, "ear": {"L": 7, "R": 8}, "sh": {"L": 11, "R": 12}, "el": {"L": 13, "R": 14},
      "wr": {"L": 15, "R": 16}, "pinky": {"L": 17, "R": 18}, "index": {"L": 19, "R": 20}, "hp": {"L": 23, "R": 24},
      "kn": {"L": 25, "R": 26}, "an": {"L": 27, "R": 28}, "heel": {"L": 29, "R": 30}, "toe": {"L": 31, "R": 32}}


# ---------------------------------------------------------------- models and frames
def model_path(kind):
    fn, url, sha = MODEL_FILES[kind]
    p = MODELS / fn
    if not p.exists():
        MODELS.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".part")
        with urllib.request.urlopen(url, timeout=120) as r:
            tmp.write_bytes(r.read())
        tmp.rename(p)
    got = hashlib.sha256(p.read_bytes()).hexdigest()
    if got != sha:
        raise RuntimeError(f"{p} does not match the pinned sha256 (got {got[:12]}...); delete it to fetch again")
    return p


def frames(video, fps=30, start=0.0, duration=0.0, mirror=False, long_side=960):
    """-> (list of HxWx3 uint8 RGB frames at exactly `fps`, (W, H)). ffmpeg applies phone rotation metadata."""
    from PIL import Image
    vf = [f"fps={fps}"] + (["hflip"] if mirror else []) + [f"scale='if(gt(iw,ih),min({long_side},iw),-2)':'if(gt(iw,ih),-2,min({long_side},ih))'"]
    base = ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}"] + (["-t", f"{duration:.3f}"] if duration else []) + ["-i", str(video), "-an", "-vf", ",".join(vf)]
    probe = subprocess.run(base + ["-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    if probe.returncode or not probe.stdout:
        raise RuntimeError(f"cannot read video {video}: {probe.stderr.decode()[-400:]}")
    W, H = Image.open(io.BytesIO(probe.stdout)).size
    raw = subprocess.run(base + ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    n = len(raw) // (W * H * 3)
    arr = np.frombuffer(raw[: n * W * H * 3], np.uint8).reshape(n, H, W, 3)
    return arr, (W, H)


def detect(video, fps=30, start=0.0, duration=0.0, mirror=False, face=True):
    """Keypoints for a take: {fps, size, frames: [{pose: [[x, y, visibility, depth] x 33] (pixels; depth from the hips,
    negative is nearer the camera) | None,
    face: {blendshape: score} | None}], timing}. Deterministic for a given file and options."""
    try:
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision
    except ImportError as e:
        raise RuntimeError("Act it out needs MediaPipe: python -m pip install -r requirements-tools.txt") from e
    t0 = time.time()
    arr, (W, H) = frames(video, fps, start, duration, mirror)
    t_dec = time.time() - t0
    VRM = vision.RunningMode.VIDEO
    pose_lm = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path("pose"))), running_mode=VRM, num_poses=1,
        min_pose_detection_confidence=0.5, min_tracking_confidence=0.5))
    face_lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path("face"))), running_mode=VRM, num_faces=1,
        output_face_blendshapes=True)) if face else None
    out = []
    for i, img in enumerate(arr):
        ts = int(round(i * 1000 / fps))
        r = pose_lm.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(img)), ts)
        pose = None
        if r.pose_landmarks:
            pose = [[round(l.x * W, 2), round(l.y * H, 2), round(float(l.visibility if l.visibility is not None else 1.0), 3), round(l.z * W, 2)] for l in r.pose_landmarks[0]]
        fc = None
        if face_lm is not None:
            crop = img
            if pose:   # the face is small in a full-body take: run the face model on a square crop around the head
                pts = np.array([pose[j][:2] for j in (0, 2, 5, 7, 8)])
                c = pts.mean(0); s = max(2.8 * max(np.ptp(pts[:, 0]), np.ptp(pts[:, 1])), 64)
                x0, y0 = int(max(0, c[0] - s / 2)), int(max(0, c[1] - s / 2))
                crop = np.ascontiguousarray(img[y0:int(min(H, c[1] + s / 2)), x0:int(min(W, c[0] + s / 2))])
                if crop.shape[0] < 32 or crop.shape[1] < 32:
                    crop = img
            fr = face_lm.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(crop)), ts)
            if fr.face_blendshapes:
                fc = {b.category_name: round(float(b.score), 3) for b in fr.face_blendshapes[0]}
        out.append({"pose": pose, "face": fc})
    pose_lm.close()
    if face_lm:
        face_lm.close()
    return {"fps": fps, "size": [W, H], "mirror": bool(mirror), "start": start, "frames": out,
            "timing": {"decode_s": round(t_dec, 2), "detect_s": round(time.time() - t0 - t_dec, 2)}}


# ---------------------------------------------------------------- signal helpers
def _interp_gaps(v, ok):
    """fill False samples by linear interpolation between valid neighbours, holding the ends"""
    v = np.array(v, float); idx = np.arange(len(v))
    if ok.sum() == 0:
        return v
    v[~ok] = np.interp(idx[~ok], idx[ok], v[ok])
    return v


def _median(v, k=5):
    if len(v) < k:
        return v
    p = np.pad(v, (k // 2, k // 2), mode="edge")
    return np.median(np.lib.stride_tricks.sliding_window_view(p, k), axis=-1)


def _gauss(v, sigma):
    if sigma <= 0 or len(v) < 3:
        return v
    r = int(math.ceil(3 * sigma)); x = np.arange(-r, r + 1); k = np.exp(-x * x / (2 * sigma * sigma)); k /= k.sum()
    if v.ndim == 1:
        return np.convolve(np.pad(v, (r, r), mode="edge"), k, mode="valid")
    return np.stack([_gauss(v[:, j], sigma) for j in range(v.shape[1])], 1)


def _smoothstep(k):
    k = np.clip(k, 0, 1); return k * k * (3 - 2 * k)


def reduce_keys(ts, vs, tol):
    """Fewest keys such that the clip as Acting.evaluate plays it (smoothstep between keys) stays within `tol` of
    the measured curve. Seeded with the curve's clear turning points (an animator's extremes), then split where the
    played curve strays most. vs: (n,) or (n, d) -> (key indices, max error)."""
    ts = np.asarray(ts, float); V = np.asarray(vs, float); V2 = V if V.ndim == 2 else V[:, None]; n = len(ts)
    if n <= 2:
        return list(range(n)), 0.0
    keys = {0, n - 1}
    for j in range(V2.shape[1]):   # turning points with real amplitude on both sides
        d = np.sign(np.diff(V2[:, j])); last = 0
        for i in range(1, n - 1):
            if d[i - 1] != 0 and d[i] != 0 and d[i - 1] != d[i]:
                if abs(V2[i, j] - V2[last, j]) > 2 * tol:
                    keys.add(i); last = i

    def played(i, k):
        a, b = keys_sorted[k], keys_sorted[k + 1]
        w = _smoothstep((ts[a:b + 1] - ts[a]) / max(ts[b] - ts[a], 1e-9))[:, None]
        return V2[a] + (V2[b] - V2[a]) * w

    while True:
        keys_sorted = sorted(keys); worst, at = 0.0, None
        for k in range(len(keys_sorted) - 1):
            a, b = keys_sorted[k], keys_sorted[k + 1]
            if b - a < 2:
                continue
            e = np.linalg.norm(played(None, k) - V2[a:b + 1], axis=1)
            m = int(np.argmax(e))
            if e[m] > worst:
                worst, at = float(e[m]), a + m
        if worst <= tol or at is None:
            return keys_sorted, worst
        keys.add(at)


def _runs(labels, fps, hold):
    """discrete per-frame labels -> [[t, label]] with runs shorter than `hold` seconds folded into the previous one"""
    out = []
    n_hold = max(1, int(round(hold * fps)))
    i = 0
    while i < len(labels):
        j = i
        while j < len(labels) and labels[j] == labels[i]:
            j += 1
        if out and (j - i) < n_hold and j < len(labels):
            i = j; continue
        if not out or out[-1][1] != labels[i]:
            out.append([round(i / fps, 3), labels[i]])
        i = j
    return out


# ---------------------------------------------------------------- retargeting
def _wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def _ang(v):
    return math.degrees(math.atan2(v[1], v[0]))


def rest_directions(puppet):
    """rest angle (degrees, artboard space) of each bone the take can drive, from the drawn rest pose"""
    parts = puppet["parts"]; piv = lambda p: parts[p]["pivot"]
    rest = {}
    for s in ("L", "R"):
        for bone, child in ((f"upperarm_{s}", f"forearm_{s}"), (f"forearm_{s}", f"hand_{s}"), (f"thigh_{s}", f"shin_{s}"), (f"shin_{s}", f"foot_{s}")):
            if bone in parts and child in parts:
                rest[bone] = _ang((piv(child)[0] - piv(bone)[0], piv(child)[1] - piv(bone)[1]))
        if f"hand_{s}" in parts and f"forearm_{s}" in rest:
            rest[f"hand_{s}"] = rest[f"forearm_{s}"]        # a hand hangs in line with its forearm
        if f"arm_{s}" in parts:                               # one-bone arms (doodle template): the drawing's own axis
            rest[f"arm_{s}"] = _ang(G.part_axis(parts[f"arm_{s}"]))
    for spine in ("torso", "body"):
        if spine in parts:
            up = next((c for c in ("neck", "head") if c in parts and parts[c].get("parent") in (spine, "neck")), None)
            rest[spine] = _ang((piv(up)[0] - piv(spine)[0], piv(up)[1] - piv(spine)[1])) if up else -90.0
    return rest


def retarget(kp, puppet, tol=1.5, smooth=0.03, face="upper", root="move", arms="angles", min_seen=0.6):
    """keypoints (from detect) + puppet -> (clip, report). face: all | upper (eyes and brows; the mouth stays with
    lip-sync) | none. root: move (the take's hip travel, feet kept on the ground) | in_place. arms: angles (joint
    angles copied; natural on a flat character, whose forearm cannot foreshorten toward the lens) | reach (hands placed
    where the take's hands are, relative to the shoulders and scaled to this body: claps and hands on the body meet,
    but a hand held close to the chest makes a short-armed character wing its elbow out)."""
    fps = kp["fps"]; F = len(kp["frames"]); parts = puppet["parts"]
    if F < 3:
        raise ValueError("the take is shorter than three frames")
    ts = np.arange(F) / fps
    P = np.full((F, 33, 4), np.nan)
    for i, fr in enumerate(kp["frames"]):
        if fr.get("pose"):
            a = np.array(fr["pose"], float); P[i, :, :a.shape[1]] = a
    W, H = kp["size"]
    have = ~np.isnan(P[:, 0, 0])
    if have.mean() < 0.3:
        raise ValueError(f"no person found in most of the take (found in {have.sum()} of {F} frames)")

    # which anatomical side is on the left of the picture (facing the camera: the person's right)
    shx = np.nanmedian(P[:, LM["sh"]["L"], 0] - P[:, LM["sh"]["R"], 0])
    img = {"L": "R", "R": "L"} if shx > 0 else {"L": "L", "R": "R"}     # puppet side (image side) -> anatomical side

    def pt(name, s=None):
        j = LM[name] if s is None else LM[name][img[s]]
        return P[:, j, :2], (P[:, j, 2] > 0.5) & (P[:, j, 0] > -0.02 * W) & (P[:, j, 0] < 1.02 * W) & (P[:, j, 1] > -0.02 * H) & (P[:, j, 1] < 1.02 * H)

    def mid(a, b):
        (pa, oa), (pb, ob) = a, b
        return (pa + pb) / 2, oa & ob

    shm = mid(pt("sh", "L"), pt("sh", "R")); hpm = mid(pt("hp", "L"), pt("hp", "R"))
    hand = {s: ((pt("index", s)[0] + pt("pinky", s)[0]) / 2, pt("index", s)[1] & pt("pinky", s)[1]) for s in "LR"}
    segs = {}   # part -> (from, to) series
    for s in "LR":
        segs[f"upperarm_{s}"] = (pt("sh", s), pt("el", s)); segs[f"forearm_{s}"] = (pt("el", s), pt("wr", s))
        segs[f"hand_{s}"] = (pt("wr", s), hand[s]); segs[f"arm_{s}"] = (pt("sh", s), pt("wr", s))
        segs[f"thigh_{s}"] = (pt("hp", s), pt("kn", s)); segs[f"shin_{s}"] = (pt("kn", s), pt("an", s))
    spine_seen = (shm[1] & hpm[1]).mean() >= min_seen
    for sp in ("torso", "body"):
        segs[sp] = (hpm, shm)

    rest = rest_directions(puppet)
    world, dropped, coverage = {}, {}, {}
    for part, ((a, oa), (b, ob)) in segs.items():
        if part not in rest:
            continue
        if part in ("torso", "body") and not spine_seen:
            continue    # waist-up take: the spine comes from the shoulder line below
        d = b - a; L = np.hypot(d[:, 0], d[:, 1]); ok = oa & ob & ~np.isnan(L)
        if ok.any():   # foreshortened (pointing at the lens): direction unreliable, bridge it
            ok &= L > 0.3 * np.nanpercentile(L[ok], 95)
        coverage[part] = round(float(ok.mean()), 2)
        if ok.mean() < min_seen:
            dropped[part] = f"seen in {ok.mean():.0%} of the take"; continue
        raw = np.degrees(np.arctan2(d[:, 1], d[:, 0])) - rest[part]
        good = np.unwrap(np.radians(raw[ok]))
        u = np.full(F, np.nan); u[ok] = np.degrees(good)
        world[part] = _interp_gaps(u, ok)
    if not spine_seen and shm[1].mean() >= min_seen:   # waist-up: the torso leans with the shoulder line
        for sp in ("torso", "body"):
            if sp in parts:
                ls, rs = pt("sh", "L"), pt("sh", "R"); d = rs[0] - ls[0]; ok = ls[1] & rs[1]
                u = np.full(F, np.nan); u[ok] = np.degrees(np.unwrap(np.arctan2(d[ok, 1], d[ok, 0])))
                world[sp] = 0.7 * _interp_gaps(u, ok); coverage[sp] = round(float(ok.mean()), 2)
    if "head" in parts:   # head roll from the eye and ear lines
        rolls, oks = [], []
        for nm in ("ear", "eye"):
            l, r = pt(nm, "L"), pt(nm, "R"); d = r[0] - l[0]; rolls.append(np.degrees(np.arctan2(d[:, 1], d[:, 0]))); oks.append(l[1] & r[1])
        ok = oks[0] | oks[1]
        roll = np.where(oks[0] & oks[1], (rolls[0] + rolls[1]) / 2, np.where(oks[0], rolls[0], rolls[1]))
        coverage["head"] = round(float(ok.mean()), 2)
        if ok.mean() >= min_seen:
            u = np.full(F, np.nan); u[ok] = np.degrees(np.unwrap(np.radians(roll[ok]))); world["head"] = np.clip(_interp_gaps(u, ok), -40, 40)
        else:
            dropped["head"] = f"face seen in {ok.mean():.0%} of the take"

    # body scale (video pixels -> artboard units) from the same anatomical points MediaPipe reports
    piv = lambda p: parts[p]["pivot"]
    scale, root_pt = None, None
    arms_p, legs_p = ("upperarm_L", "upperarm_R"), ("thigh_L", "thigh_R")
    if spine_seen and all(p in parts for p in arms_p + legs_p):
        vid = np.hypot(*(shm[0] - hpm[0]).T); art = math.dist(np.mean([piv(p) for p in arms_p], 0), np.mean([piv(p) for p in legs_p], 0)); root_pt = hpm
    elif all(p in parts for p in arms_p):
        vid = np.hypot(*(pt("sh", "R")[0] - pt("sh", "L")[0]).T); art = math.dist(piv("upperarm_L"), piv("upperarm_R")); root_pt = shm
    else:
        vid, art = None, None
    if art:
        okv = root_pt[1] & ~np.isnan(vid)
        if okv.mean() >= min_seen:
            scale = art / float(np.median(vid[okv])); root_pt = (root_pt[0], okv)

    # reach: hands go where the take's hands are relative to the shoulders (scaled to this body), elbows bend to
    # the side the take's elbows are on; keeps hand-to-chest and hand-to-face contacts on a differently built body
    reached = []
    if arms == "reach" and scale:
        tw = world.get("torso", world.get("body", np.zeros(F))) if ("torso" in parts or "body" in parts) else np.zeros(F)
        spine = "torso" if "torso" in parts else "body" if "body" in parts else None
        for sd in "LR":
            up, lo, en = f"upperarm_{sd}", f"forearm_{sd}", f"hand_{sd}"
            if not all(p in parts for p in (up, lo, en)) or up not in world or lo not in world:
                continue
            (sh_, ok1), (el_, ok2), (wr_, ok3) = pt("sh", sd), pt("el", sd), pt("wr", sd)
            ok = ok1 & ok2 & ok3
            if ok.mean() < min_seen:
                continue
            L1, L2 = math.dist(piv(up), piv(lo)), math.dist(piv(lo), piv(en))
            sp = piv(spine) if spine else piv(up)
            uw, lw = np.array(world[up]), np.array(world[lo])
            for i in np.nonzero(ok)[0]:
                r = math.radians(tw[i]); c, si = math.cos(r), math.sin(r)
                dx, dy = piv(up)[0] - sp[0], piv(up)[1] - sp[1]
                S = (sp[0] + c * dx - si * dy, sp[1] + si * dx + c * dy)
                T = (S[0] + (wr_[i, 0] - sh_[i, 0]) * scale, S[1] + (wr_[i, 1] - sh_[i, 1]) * scale)
                d = min(max(math.dist(S, T), abs(L1 - L2) + 1e-3), L1 + L2 - 1e-3)
                a = math.acos(max(-1, min(1, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d))))
                base = math.atan2(T[1] - S[1], T[0] - S[0])
                side = np.sign((wr_[i, 0] - sh_[i, 0]) * (el_[i, 1] - sh_[i, 1]) - (wr_[i, 1] - sh_[i, 1]) * (el_[i, 0] - sh_[i, 0])) or 1.0
                upW = base + side * a     # the elbow on the same side of the shoulder-wrist line as in the take
                E = (S[0] + L1 * math.cos(upW), S[1] + L1 * math.sin(upW))
                loW = math.atan2(T[1] - E[1], T[0] - E[0])
                uw[i] = math.degrees(upW) - rest[up]; lw[i] = math.degrees(loW) - rest[lo]
            for arr_, orig in ((uw, world[up]), (lw, world[lo])):   # keep continuity with the measured unwrap
                arr_[:] = orig + _wrap(arr_ - orig)
            world[up], world[lo] = uw, lw; reached.append(sd)

    # local angles: world rotation minus the parent's (undriven parts inherit their parent's rotation)
    sig = smooth * fps
    W_all = {}

    def wrot(p):
        if p is None or p not in parts:
            return np.zeros(F)
        if p not in W_all:
            W_all[p] = world[p] if p in world else wrot(parts[p].get("parent"))
        return W_all[p]
    tracks, errs, nkeys = {}, {}, 0
    for part in [p for p in parts if p in world]:
        loc = world[part] - wrot(parts[part].get("parent"))
        loc = loc - 360.0 * round(float(np.median(loc)) / 360.0)
        loc = _gauss(_median(loc, 5), sig * (2 if part.startswith("hand") else 1))
        if part.startswith("hand"):
            loc = np.clip(loc, -45, 45)
        if parts[part].get("limits"):
            loc = np.clip(loc, *parts[part]["limits"])
        keys, err = reduce_keys(ts, loc, tol)
        tracks[part] = [[round(float(ts[i]), 3), round(float(loc[i]), 1)] for i in keys]
        errs[part] = round(err, 2); nkeys += len(keys)

    clip = {"duration": round(float(ts[-1]), 3), "loop": False, "tracks": tracks}

    # root: hips (or shoulders in a waist-up take)
    legs_seen = all(p in world for p in ("thigh_L", "thigh_R", "shin_L", "shin_R"))
    if root == "move" and "hip" in parts and scale:
        s, (rp, okv) = scale, root_pt
        x = _interp_gaps(rp[:, 0], okv); y = _interp_gaps(rp[:, 1], okv)
        ox = (x - x[0]) * s; oy = (y - y[0]) * s
        contacts = None
        if legs_seen and "foot_L" in parts and "foot_R" in parts:
            contacts, oy = _ground_lock(puppet, clip, P, pt, ts, oy, s, fps)
        elif not legs_seen:
            oy = np.zeros(F)     # waist-up: the camera bobbing is not the character jumping
        off = np.stack([_gauss(ox, sig), oy if contacts else _gauss(oy, sig)], 1)   # a locked root is already exact
        keys, err = reduce_keys(ts, off, 1.0 if contacts else max(2.0, tol * 2))
        clip["offset"] = [[round(float(ts[i]), 3), [round(float(off[i, 0]), 1), round(float(off[i, 1]), 1)]] for i in keys]
        errs["offset"] = round(err, 2)
        if contacts:
            clip["contacts"] = contacts
    # face: blendshapes -> the puppet's own mouth, eye and brow drawings, and gaze
    swaps, face_cov = _face(kp, puppet, face, fps) if face != "none" else ({}, 0.0)
    # layer order: a forearm drawn behind the body comes in front while the take's wrist is nearer the lens than
    # the shoulders (a thumbs-up across the chest), using the existing pose.z override
    spine_part = next((p for p in ("torso", "body") if p in parts), None)
    if spine_part and not np.isnan(P[:, :, 3]).all():
        tz = parts[spine_part].get("z", 0); front_z = {}
        shz = (P[:, LM["sh"]["L"], 3] + P[:, LM["sh"]["R"], 3]) / 2
        shw = float(np.nanmedian(np.hypot(*(pt("sh", "R")[0] - pt("sh", "L")[0]).T)))
        for s in "LR":
            arm = [p for p in (f"forearm_{s}", f"hand_{s}", f"arm_{s}") if p in tracks and parts[p].get("z", 0) < tz]
            if not arm:
                continue
            wz = P[:, LM["wr"][img[s]], 3]; ok = pt("wr", s)[1] & ~np.isnan(wz) & ~np.isnan(shz)
            front = np.zeros(F, bool); front[ok] = (wz[ok] - shz[ok]) < -0.35 * shw
            front_z[s] = (front, {p: round(tz + 0.5 + 0.1 * k, 1) for k, p in enumerate(arm)})
        if any(f.any() for f, _ in front_z.values()):
            lab = []
            for i in range(F):
                z = {}
                for f, zs in front_z.values():
                    if f[i]:
                        z.update(zs)
                lab.append(json.dumps(z, sort_keys=True))
            swaps["z"] = [[t, json.loads(v)] for t, v in _runs(lab, fps, 0.15)]
    if swaps:
        clip["swaps"] = swaps
    warnings = []
    if scale:   # the body's size on screen: a zoom or a walk toward the lens reads as travel
        size = np.hypot(*(pt("sh", "R")[0] - pt("sh", "L")[0]).T)
        okz = pt("sh", "R")[1] & pt("sh", "L")[1]
        if okz.sum() > 5:
            lo_, hi_ = np.percentile(size[okz], [10, 90])
            if hi_ / max(lo_, 1e-6) > 1.25:
                warnings.append(f"the performer's size on screen changed by {hi_ / lo_ - 1:.0%} (a zoom, a moving camera, or walking toward the lens): "
                                "the root travel may be camera motion; use root=in_place unless the camera was fixed")
    if face != "none" and 0 < face_cov < 0.8:
        warnings.append(f"the face was found in {face_cov:.0%} of the take: face drawings may flicker; face=upper or none, or light the face")
    report = {"frames": F, "seconds": round(F / fps, 2), "person_found": round(float(have.mean()), 2),
              "facing": "camera" if shx > 0 else "away", "tracks": sorted(tracks), "dropped": dropped, "coverage": coverage,
              "keys": nkeys, "max_error_deg": errs, "face_found": face_cov, "swaps": {k: len(v) for k, v in swaps.items()},
              "root": "move" if "offset" in clip else "in_place", "arms": {sd: "reach" for sd in reached}, "legs": legs_seen, "spine": "hips to shoulders" if spine_seen else "shoulder line", "warnings": warnings}
    return clip, report


def _ground_lock(puppet, clip, P, pt, ts, oy_video, s, fps):
    """Feet that are planted in the take stay on the puppet's ground line: during contacts the vertical offset is
    whatever puts the lowest planted sole on the ground (forward kinematics through the clip's own angles); between
    contacts (a jump) the take's hip motion carries it, corrected smoothly between the locked ends."""
    from .geom import apply, part_matrices
    F = len(ts); parts = puppet["parts"]; ground = puppet.get("ground", puppet["artboard"][1])
    # contacts in the take: an ankle near the floor and slow
    ank = {s_: pt("an", s_) for s_ in "LR"}
    ys = np.stack([ank[s_][0][:, 1] for s_ in "LR"], 1)
    floor = float(np.nanpercentile(np.nanmax(ys, 1), 90))
    body = float(np.nanmedian(np.abs(ys.mean(1) - pt("sh", "L")[0][:, 1]))) or 1.0
    con = {}
    for s_ in "LR":
        y = _interp_gaps(ank[s_][0][:, 1], ank[s_][1]); x = _interp_gaps(ank[s_][0][:, 0], ank[s_][1])
        sp = np.hypot(np.gradient(x), np.gradient(y)) * fps / body
        c = (y > floor - 0.04 * body) & (sp < 0.8)
        c = _median(c.astype(float), 5) > 0.5
        con[s_] = c
    # sample the clip's angles per frame (dense) for forward kinematics
    ang = _sample_tracks(clip["tracks"], ts)
    sole = {s_: (parts[f"foot_{s_}"]["pivot"][0], ground) for s_ in "LR"}
    lock = np.full(F, np.nan)
    for i in range(F):
        planted = [s_ for s_ in "LR" if con[s_][i]]
        if not planted:
            continue
        M = part_matrices(puppet, {k: v[i] for k, v in ang.items()})
        lock[i] = ground - max(apply(M[f"foot_{s_}"], sole[s_])[1] for s_ in planted)
    ok = ~np.isnan(lock)
    if ok.any():
        corr = _interp_gaps(np.where(ok, lock - oy_video, 0.0), ok)
        oy = oy_video + corr
    else:
        oy = oy_video
    contacts = {f"foot_{s_}": [[t, bool(v)] for t, v in _runs([bool(x) for x in con[s_]], fps, 0.1)] for s_ in "LR"}
    return contacts, oy


def _sample_tracks(tracks, ts):
    """the clip's angle at each time, as Acting.sampleKeys plays it (smoothstep between keys)"""
    out = {}
    for part, keys in tracks.items():
        kt = np.array([k[0] for k in keys]); kv = np.array([k[1] for k in keys]); v = np.empty(len(ts))
        for i, t in enumerate(ts):
            j = int(np.searchsorted(kt, t))
            if j <= 0:
                v[i] = kv[0]
            elif j >= len(kt):
                v[i] = kv[-1]
            else:
                w = _smoothstep((t - kt[j - 1]) / max(kt[j] - kt[j - 1], 1e-9)); v[i] = kv[j - 1] + (kv[j] - kv[j - 1]) * w
        out[part] = v
    return out


FALLBACK = {"mid": ["small", "wide"], "wide": ["mid", "small"], "O": ["small", "mid"], "small": ["mid", "closed"], "smile": ["closed"], "frown": ["closed"]}


def _face(kp, puppet, mode, fps):
    sw = puppet.get("swaps") or {}
    shapes = {k: set((v.get("shapes") or {}).keys()) for k, v in sw.items()}
    fr = kp["frames"]; F = len(fr)
    found = np.array([bool(f.get("face")) for f in fr])
    if found.mean() < 0.3:
        return {}, round(float(found.mean()), 2)
    names = sorted({k for f in fr if f.get("face") for k in f["face"]})
    B = {n: _gauss(_interp_gaps(np.array([(f.get("face") or {}).get(n, np.nan) for f in fr], float), found), 0.06 * fps) for n in names}
    g = lambda n: B.get(n, np.zeros(F))
    avg = lambda a, b: (g(a) + g(b)) / 2

    def pick(kind, want):
        have = shapes.get(kind, set())
        if want in have:
            return want
        for alt in FALLBACK.get(want, []):
            if alt in have:
                return alt
        return "closed" if kind == "mouth" and "closed" in have else None
    out = {}
    if mode == "all" and "mouth" in shapes:
        jaw, fun = g("jawOpen"), np.maximum(g("mouthFunnel"), g("mouthPucker"))
        smile, frown = avg("mouthSmileLeft", "mouthSmileRight"), avg("mouthFrownLeft", "mouthFrownRight")
        lab = []
        for i in range(F):
            w = ("O" if fun[i] > 0.3 else "wide") if jaw[i] > 0.45 else ("O" if fun[i] > 0.3 else "mid") if jaw[i] > 0.22 else \
                "O" if fun[i] > 0.45 else "smile" if smile[i] > 0.5 else "small" if jaw[i] > 0.1 else "frown" if frown[i] > 0.4 else "closed"
            lab.append(pick("mouth", w))
        out["mouth"] = _runs(lab, fps, 0.12)
    if "eyes" in shapes:
        bl = avg("eyeBlinkLeft", "eyeBlinkRight")
        out["eyes"] = _runs([pick("eyes", "closed" if b > 0.55 else "half" if b > 0.35 else "open") or "open" for b in bl], fps, 0.06)
        if all(v == "open" for _, v in out["eyes"]):
            out.pop("eyes")
    if "brows" in shapes:
        inner, outer, down = g("browInnerUp"), avg("browOuterUpLeft", "browOuterUpRight"), avg("browDownLeft", "browDownRight")
        lab = ["angry" if down[i] > 0.45 else "worried" if inner[i] > 0.5 and outer[i] < 0.25 else "raised" if max(inner[i], outer[i]) > 0.45 else "neutral" for i in range(F)]
        out["brows"] = _runs([pick("brows", x) or "neutral" for x in lab], fps, 0.3)
        if all(v == "neutral" for _, v in out["brows"]):
            out.pop("brows")
    if "pupils" in shapes:   # gaze in image space: + is the right of the picture and down
        gx = ((g("eyeLookOutLeft") + g("eyeLookInRight")) - (g("eyeLookInLeft") + g("eyeLookOutRight"))) / 2
        gy = (avg("eyeLookDownLeft", "eyeLookDownRight") - avg("eyeLookUpLeft", "eyeLookUpRight"))
        # relative to the take's own resting gaze (a performer mostly looks at the lens; smiling biases the scores),
        # with a small dead zone so the pupils settle
        look = np.stack([gx - np.median(gx[found]), gy - np.median(gy[found])], 1)
        look = np.clip(np.sign(look) * np.maximum(np.abs(look) - 0.08, 0) * 1.6, -1, 1)
        if np.abs(look).max() > 0.15:
            keys, _ = reduce_keys(np.arange(F) / fps, look, 0.12)
            out["look"] = [[round(i / fps, 3), [round(float(look[i, 0]), 2), round(float(look[i, 1]), 2)]] for i in keys]
    return out, round(float(found.mean()), 2)


# ---------------------------------------------------------------- synthetic takes (tests)
def synthetic_take(puppet, clip, fps=30, seconds=None, noise=1.5, seed=7, size=(720, 1280), scale=1.0, facing="camera", hide=()):
    """Pose landmarks for a person acting `clip`, made by forward kinematics through `puppet` (pixels, with seeded
    noise): retargeting this back onto the same puppet must recover the clip's angles. Pure."""
    from .geom import apply, part_matrices
    rng = np.random.default_rng(seed); parts = puppet["parts"]
    dur = seconds or clip["duration"]; ts = np.arange(int(round(dur * fps)) + 1) / fps
    ang = _sample_tracks(clip["tracks"], np.minimum(ts, clip["duration"]))
    offs = _sample_tracks({"x": [[k[0], k[1][0]] for k in clip["offset"]], "y": [[k[0], k[1][1]] for k in clip["offset"]]}, np.minimum(ts, clip["duration"])) if clip.get("offset") else None
    piv = lambda p: parts[p]["pivot"]
    W, H = size; ox, oy = W / 2 - piv("hip")[0] * scale, H * 0.92 - puppet.get("ground", 1000) * scale
    an = {"L": "R", "R": "L"} if facing == "camera" else {"L": "L", "R": "R"}   # image side -> anatomical side
    frames = []
    for i in range(len(ts)):
        M = part_matrices(puppet, {k: float(v[i]) for k, v in ang.items()})
        q = lambda part, p: apply(M[part], p)
        lm = [[W / 2, H * 0.2, 0.0] for _ in range(33)]

        def put(name, s, part, p):
            j = LM[name][an[s]] if s else LM[name]
            x, y = q(part, p)
            if offs:
                x, y = x + offs["x"][i], y + offs["y"][i]
            lm[j] = [x * scale + ox + rng.normal(0, noise), y * scale + oy + rng.normal(0, noise), 0.0 if name in hide else 0.99]
        for s in "LR":
            put("sh", s, f"upperarm_{s}", piv(f"upperarm_{s}")); put("el", s, f"forearm_{s}", piv(f"forearm_{s}"))
            put("wr", s, f"hand_{s}", piv(f"hand_{s}"))
            fa = np.subtract(piv(f"hand_{s}"), piv(f"forearm_{s}")); tip = np.add(piv(f"hand_{s}"), 0.35 * fa)
            put("index", s, f"hand_{s}", tip); put("pinky", s, f"hand_{s}", tip)
            put("hp", s, f"thigh_{s}", piv(f"thigh_{s}")); put("kn", s, f"shin_{s}", piv(f"shin_{s}")); put("an", s, f"foot_{s}", piv(f"foot_{s}"))
            hx = piv("head")
            put("ear", s, "head", (hx[0] + (-40 if s == "L" else 40), hx[1] - 30)); put("eye", s, "head", (hx[0] + (-22 if s == "L" else 22), hx[1] - 40))
        put("nose", None, "head", (piv("head")[0], piv("head")[1] - 20))
        frames.append({"pose": [[round(a, 2), round(b, 2), c] for a, b, c in lm], "face": None})
    return {"fps": fps, "size": list(size), "mirror": False, "start": 0, "frames": frames}


def angle_error(clip_a, clip_b, ts):
    """per-track mean and max absolute difference (degrees) between two clips sampled at ts"""
    a, b = _sample_tracks(clip_a["tracks"], ts), _sample_tracks(clip_b["tracks"], ts)
    return {k: (round(float(np.mean(np.abs(a[k] - b[k]))), 2), round(float(np.max(np.abs(a[k] - b[k]))), 2)) for k in a if k in b}


def cache_key(video, **opts):
    h = hashlib.sha256(Path(video).read_bytes()).hexdigest()[:16]
    return h + "_" + hashlib.sha256(json.dumps(opts, sort_keys=True).encode()).hexdigest()[:8]


def self_test(puppet, lib):
    """Regression checks that need neither MediaPipe nor a video (run by `python -m dbe test`): takes made by forward
    kinematics through a puppet must come back as the clips that made them. -> (failures, measurements)"""
    import copy
    from .geom import apply, part_matrices
    fails, got = [], {}
    for name, mean_ok, max_ok in (("wave_R", 1.5, 6.0), ("celebrate", 1.5, 6.0), ("shrug", 1.5, 7.0)):   # angles back
        c = lib[name]; ts = np.arange(int(c["duration"] * 30)) / 30
        clip, _ = retarget(synthetic_take(puppet, c, seconds=max(c["duration"], 1.0)), puppet, face="none")
        e = angle_error(c, clip, ts); m, mx = float(np.mean([v[0] for v in e.values()])), max(v[1] for v in e.values())
        got[name] = {"mean_deg": round(m, 2), "max_deg": mx}
        if m > mean_ok or mx > max_ok:
            fails.append(f"{name}: angles back {m:.2f} deg mean, {mx:.2f} max")
        played = _sample_tracks(clip["tracks"], np.arange(len(ts)) / 30)   # keys honour the tolerance as played
        if not clip["tracks"] or any(len(v) != len(ts) for v in played.values()):
            fails.append(f"{name}: tracks missing")
    c = lib["jump"]; kp = synthetic_take(puppet, c, seconds=1.6)   # contacts and planted feet
    clip, _ = retarget(kp, puppet, face="none")
    con = clip.get("contacts") or {}
    lift = [k[0] for k in con.get("foot_L", []) if k[1] is False][:1]; land = [k[0] for k in con.get("foot_L", []) if k[1] is True and k[0] > 0][:1]
    got["jump"] = {"lift_s": lift, "land_s": land}
    if not lift or not land or abs(lift[0] - 0.34) > 0.08 or abs(land[0] - 0.74) > 0.08:
        fails.append(f"jump: contacts {con.get('foot_L')} (want lift near 0.34 s, land near 0.74 s)")
    ts = np.arange(48) / 30; ang = _sample_tracks(clip["tracks"], ts)
    oy = _sample_tracks({"y": [[k[0], k[1][1]] for k in clip["offset"]]}, ts)["y"]; ground = puppet.get("ground", 1000); worst = 0.0
    for i, t in enumerate(ts):
        planted = [s_ for s_ in "LR" if _sample_tracks({"c": [[k[0], 1.0 if k[1] else 0.0] for k in con[f"foot_{s_}"]]}, np.array([t]))["c"][0] > 0.99]
        M = part_matrices(puppet, {k: v[i] for k, v in ang.items()})
        for s_ in planted:
            worst = max(worst, abs(apply(M[f"foot_{s_}"], (puppet["parts"][f"foot_{s_}"]["pivot"][0], ground))[1] + oy[i] - ground))
    got["jump"]["planted_sole_off_ground"] = round(worst, 1)
    if worst > 5:
        fails.append(f"jump: a planted sole is {worst:.1f} units off the ground")
    kp = synthetic_take(puppet, lib["wave_R"], seconds=1.2, hide=("kn", "an", "hp", "heel", "toe"))   # waist-up take
    clip, rep = retarget(kp, puppet, face="none")
    got["waist_up"] = {"dropped": sorted(rep["dropped"]), "spine": rep["spine"]}
    if any(p in clip["tracks"] for p in ("thigh_L", "thigh_R", "shin_L", "shin_R")) or any(k[1][1] for k in clip.get("offset", [])):
        fails.append("waist-up take: legs or vertical travel were guessed")
    hu = copy.deepcopy(puppet); P = hu["parts"]   # reach: a long-armed performer's clap still meets on this body
    for sd in "LR":
        sh, el, wr = (np.array(P[f"{q}_{sd}"]["pivot"]) for q in ("upperarm", "forearm", "hand"))
        el2 = sh + (el - sh) * 1.22; P[f"forearm_{sd}"]["pivot"] = el2.tolist(); P[f"hand_{sd}"]["pivot"] = (el2 + (wr - el) * 1.22).tolist()
    c = lib["clap"]; ts = np.arange(int(c["duration"] * 30)) / 30; kp = synthetic_take(hu, c, seconds=max(c["duration"], 1.0))

    def hands(pz, cl):
        a = _sample_tracks(cl["tracks"], ts); pp = pz["parts"]
        tor = math.dist(np.mean([pp["upperarm_L"]["pivot"], pp["upperarm_R"]["pivot"]], 0), np.mean([pp["thigh_L"]["pivot"], pp["thigh_R"]["pivot"]], 0))
        out = []
        for i in range(len(ts)):
            M = part_matrices(pz, {k: v[i] for k, v in a.items()})
            out.append([(np.array(apply(M[f"hand_{sd}"], pp[f"hand_{sd}"]["pivot"])) - np.array(apply(M[f"upperarm_{sd}"], pp[f"upperarm_{sd}"]["pivot"]))) / tor for sd in "LR"])
        return np.array(out)
    want = hands(hu, c)
    er = {m: float(np.linalg.norm(hands(puppet, retarget(kp, puppet, face="none", arms=m)[0]) - want, axis=-1).mean()) for m in ("angles", "reach")}
    got["clap_hand_error_torso"] = {k: round(v, 3) for k, v in er.items()}
    if not er["reach"] < 0.06 or not er["reach"] < er["angles"] / 2:
        fails.append(f"reach: clap hands {er['reach']:.3f} torso lengths off (angles {er['angles']:.3f})")
    base = {"jawOpen": 0.02, "eyeBlinkLeft": 0.05, "eyeBlinkRight": 0.05, "browInnerUp": 0.05}   # face drawings
    seq = [{}, {"jawOpen": 0.6}, {"eyeBlinkLeft": 0.9, "eyeBlinkRight": 0.9}, {"browInnerUp": 0.7, "browOuterUpLeft": 0.6, "browOuterUpRight": 0.6},
           {"mouthSmileLeft": 0.8, "mouthSmileRight": 0.8}]
    kp = synthetic_take(puppet, lib["idle"], seconds=len(seq) * 0.5 - 1 / 30)
    for i, f in enumerate(kp["frames"]):
        f["face"] = {**base, **seq[min(len(seq) - 1, i // 15)]}
    sw = retarget(kp, puppet, face="all")[0].get("swaps", {})
    vals = {k: [v for _, v in sw.get(k, [])] for k in ("mouth", "eyes", "brows")}
    got["face"] = vals
    if "wide" not in vals["mouth"] or "smile" not in vals["mouth"] or "closed" not in vals["eyes"] or "raised" not in vals["brows"]:
        fails.append(f"face: {vals}")
    if "mouth" in retarget(kp, puppet, face="upper")[0].get("swaps", {}):
        fails.append("face=upper must leave the mouth to lip-sync")
    return fails, got
