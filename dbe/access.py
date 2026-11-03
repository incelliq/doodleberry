"""Accessibility checks (WP-24): flashes, colour vision, motion.

**Flash check** (WCAG 2.2 success criterion 2.3.1, "Three Flashes or Below Threshold", and its definitions of
*general flash and red flash thresholds*). A *transition* is a change in relative luminance of at least 0.1 (of the
maximum) where the darker image is below 0.80; a *flash* is a pair of opposing transitions. A frame counts when the
areas making that transition cover at least 25% of some 10-degree field of view. WCAG approximates that field as
341 x 256 px of a 1024 x 768 screen, a third of a desktop screen's width; how much of a frame it covers depends on
how wide the frame looks, so the field is worked out from the frame's width in degrees: 13 for portrait and square
video (a phone held at about 30 cm, where 10 degrees is three quarters of the width) and 30 for landscape (a desktop
or TV, a third of the width), or `view_deg`. The film fails if any one second
holds more than three flashes, counted per area: luminance is averaged over blocks a 30th of the frame's short side (as broadcast flash analysers,
ITU-R BT.1702, average areas rather than pixels: a thin ink line shifting by a pixel is not a flash), and a block
must itself go light and dark again (a pan sweeping an edge across the frame changes each block once). *Red flash*: the same, for transitions of saturated red (R / (R + G + B) >= 0.8, the
change in (R - G - B) x 320 above 20, values in 0 to 1 sRGB). Transitions are tracked per pixel from its last
extreme, so a change spread over several frames counts once and slow fades are caught.

**Colour vision.** Machado, Oliveira and Fernandes (2009) simulation matrices at full severity for protanopia,
deuteranopia and tritanopia, applied in linear RGB. A frame's main colours (median-cut, each at least 0.5% of the
frame) are compared in CIELAB: a pair a viewer with normal colour vision tells apart (Delta E 76 >= 15) that
touches in the picture and falls below 7 under a simulation is a confusable pair. Data colours (chart series) must
stay apart under every simulation.

**Motion.** The camera's movement between frames by phase correlation of the frames' grey images (pixels per
second at the frame's own size), and how much of the picture changes from frame to frame.
"""
import json
import subprocess

import numpy as np

# Machado et al. 2009, severity 1.0, linear RGB
CVD = {
    "protanopia": np.array([[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]]),
    "deuteranopia": np.array([[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]]),
    "tritanopia": np.array([[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]]),
}


def _probe(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,avg_frame_rate", "-of", "json", str(video)],
                       capture_output=True, text=True)
    st = json.loads(r.stdout)["streams"][0]; n, d = map(int, st["avg_frame_rate"].split("/"))
    return st["width"], st["height"], n / d


def frames(video, short=270, every_s=None):
    """decoded RGB frames (uint8), the short side scaled to `short` px; yields (index, frame) (every_s: one frame
    every so many seconds, indexed in those steps)"""
    W, H, fps = _probe(video)
    w, h = (short, round(H * short / W / 2) * 2) if W <= H else (round(W * short / H / 2) * 2, short)
    vf = (f"fps=1/{every_s}," if every_s else "") + f"scale={w}:{h}:flags=area"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(video), "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    i = 0
    while True:
        b = p.stdout.read(w * h * 3)
        if len(b) < w * h * 3:
            break
        yield i, np.frombuffer(b, np.uint8).reshape(h, w, 3); i += 1
    p.wait()


def _lin(rgb8):
    c = rgb8.astype(np.float32) / 255
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def luminance(rgb8):
    l = _lin(rgb8)
    return l[..., 0] * 0.2126 + l[..., 1] * 0.7152 + l[..., 2] * 0.0722


def red_quantity(rgb8):
    c = rgb8.astype(np.float32) / 255; s = c.sum(axis=2) + 1e-6
    q = np.maximum(0, c[..., 0] - c[..., 1] - c[..., 2]) * 320
    return np.where(c[..., 0] / s >= 0.8, q, 0.0)


class _Tracker:
    """per pixel: the extremes since its last transition, and that transition's direction"""

    def __init__(self, x, step, dark=None):
        self.lo = x.copy(); self.hi = x.copy(); self.dir = np.zeros(x.shape, np.int8); self.step = step; self.dark = dark

    def update(self, x):
        self.hi = np.maximum(self.hi, x); self.lo = np.minimum(self.lo, x)
        rise, fall = x - self.lo, self.hi - x
        up = (self.dir <= 0) & (rise >= self.step); dn = (self.dir >= 0) & (fall >= self.step)
        if self.dark is not None:   # the darker image of the pair must be below `dark`
            up &= self.lo < self.dark; dn &= x < self.dark
        both = up & dn   # from rest, a pixel that both rose and fell since: the larger move wins
        up &= ~both | (rise >= fall); dn &= ~up
        self.dir[up] = 1; self.dir[dn] = -1
        moved = up | dn   # a transition starts new extremes at the level it reached
        self.hi[moved] = x[moved]; self.lo[moved] = x[moved]
        return up, dn


def _window_share(mask, win):
    """the largest share of any win x win window that the mask covers (integral image)"""
    h, w = mask.shape; win = min(win, h, w)
    ii = np.pad(mask.astype(np.int32).cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    s = ii[win:, win:] - ii[:-win, win:] - ii[win:, :-win] + ii[:-win, :-win]
    return float(s.max()) / (win * win)


BLOCK = 30   # luminance is averaged over blocks a 30th of the frame's short side (as broadcast analysers average areas)


def _blocks(x, n):
    """the image averaged over square blocks, n of them across its short side"""
    b = max(1, min(x.shape) // n); h, w = x.shape[0] // b * b, x.shape[1] // b * b
    return x[:h, :w].reshape(h // b, b, w // b, b).mean(axis=(1, 3))


VIEW_DEG = {"portrait": 13.0, "square": 13.0, "landscape": 30.0}   # how wide the frame looks: a phone at ~30 cm; a desktop or TV


def flash_check(video, area=0.25, max_flashes=3, view_deg=None):
    """-> {ok, general: {...}, red: {...}}. Each pixel keeps the frames of its recent transitions; at every frame, the
    flashes a pixel made in the last second are half its transitions there, and the frame's flash rate is the largest k
    for which the pixels with at least k flashes cover `area` of some 10-degree window. A pan that sweeps a dark edge
    across the frame moves each pixel once and is not a flash; a region that goes light and dark again is."""
    W, H, fps = _probe(video); n_sec = int(round(fps)); K = 4 * (max_flashes + 2)
    tr = {}; win = None; ring = {}; out = {"fps": round(fps, 3), "area": area}
    worst = {"general": (0, None), "red": (0, None)}; ntr = {"general": 0, "red": 0}
    for i, f in frames(video):
        L, R = _blocks(luminance(f), BLOCK), _blocks(red_quantity(f), BLOCK)
        if not tr:
            vd = view_deg or VIEW_DEG["landscape" if W > H else "square" if W == H else "portrait"]
            win = max(3, min(min(L.shape), round(L.shape[1] * 10 / vd)))   # the 10-degree field, in blocks, from the frame's width
            tr = {"general": _Tracker(L, 0.1, dark=0.8), "red": _Tracker(R, 20.0)}; out["view_deg"] = vd
            ring = {k: np.full((K,) + L.shape, -10 ** 6, np.int32) for k in tr}; slot = {k: np.zeros(L.shape, np.int32) for k in tr}; out["window_blocks"] = win; out["block_px"] = max(1, min(f.shape[:2]) // BLOCK)
            continue
        for k, x in (("general", L), ("red", R)):
            up, dn = tr[k].update(x); moved = up | dn
            if not moved.any():
                continue
            ntr[k] += int(_window_share(moved, win) >= area)
            yy, xx = np.nonzero(moved); ring[k][slot[k][yy, xx], yy, xx] = i; slot[k][yy, xx] = (slot[k][yy, xx] + 1) % K
            cnt = (ring[k] > i - n_sec).sum(0) // 2   # flashes in the last second, per pixel
            for fl in range(int(cnt.max()), worst[k][0], -1):
                if _window_share(cnt >= fl, win) >= area:
                    worst[k] = (fl, round(i / fps, 2)); break
    for k in tr or ("general", "red"):
        out[k] = {"worst_flashes_per_second": worst[k][0], "at_s": worst[k][1], "large_transition_frames": ntr[k], "ok": worst[k][0] <= max_flashes}
    out["ok"] = out["general"]["ok"] and out["red"]["ok"]
    return out


# ---------------- colour vision ----------------
def _lab(rgb8):
    l = _lin(np.asarray(rgb8, np.uint8))
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = l @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def simulate(rgb8, kind):
    l = _lin(np.asarray(rgb8, np.uint8)) @ CVD[kind].T; l = np.clip(l, 0, 1)
    s = np.where(l <= 0.0031308, l * 12.92, 1.055 * l ** (1 / 2.4) - 0.055)
    return np.round(s * 255).astype(np.uint8)


def delta_e(a, b):
    return float(np.linalg.norm(_lab(a) - _lab(b)))


def colours_apart(colours, min_de=15.0):
    """data colours (#hex): the closest pair under normal vision and each simulation"""
    rgb = [[int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)] for c in colours]
    out = {}
    for kind in ("normal", *CVD):
        cs = rgb if kind == "normal" else [simulate(np.array([c]), kind)[0].tolist() for c in rgb]
        pairs = [(delta_e(cs[i], cs[j]), colours[i], colours[j]) for i in range(len(cs)) for j in range(i + 1, len(cs))]
        if pairs:
            d, a, b = min(pairs); out[kind] = {"min_delta_e": round(d, 1), "pair": [a, b], "ok": d >= min_de}
    return out


def frame_confusions(rgb8, n=12, min_share=0.005, normal_de=15.0, sim_de=7.0, min_border=0.002):
    """colour pairs in one frame that touch and that a colour-blind viewer cannot tell apart"""
    from PIL import Image
    im = Image.fromarray(rgb8).quantize(n, method=Image.Quantize.MEDIANCUT)
    idx = np.asarray(im); pal = np.array(im.getpalette()[:n * 3], np.uint8).reshape(-1, 3)
    share = np.bincount(idx.ravel(), minlength=n) / idx.size
    keep = [i for i in range(n) if share[i] >= min_share]
    # how often two colours sit side by side (right and down neighbours)
    a = np.concatenate([idx[:, :-1].ravel(), idx[:-1, :].ravel()]); b = np.concatenate([idx[:, 1:].ravel(), idx[1:, :].ravel()])
    diff = a != b; adj = np.zeros((n, n)); np.add.at(adj, (a[diff], b[diff]), 1); adj = (adj + adj.T) / max(1, a.size)
    rows = []
    for x in range(len(keep)):
        for y in range(x + 1, len(keep)):
            i, j = keep[x], keep[y]
            if adj[i, j] < min_border or delta_e(pal[i], pal[j]) < normal_de:
                continue
            for kind in CVD:
                d = delta_e(simulate(pal[[i]], kind)[0], simulate(pal[[j]], kind)[0])
                if d < sim_de:
                    rows.append({"kind": kind, "colours": ["#%02x%02x%02x" % tuple(pal[i]), "#%02x%02x%02x" % tuple(pal[j])],
                                 "normal_de": round(delta_e(pal[i], pal[j]), 1), "simulated_de": round(d, 1), "border": round(float(adj[i, j]), 4)})
    return rows


def colour_check(video, every_s=2.0, data_colours=None):
    found = []; n = 0
    for i, f in frames(video, short=200, every_s=every_s):
        n += 1
        for r in frame_confusions(f):
            found.append({"t": round(i * every_s, 2), **r})
    data = colours_apart(data_colours) if data_colours and len(data_colours) > 1 else {}
    return {"frames_checked": n, "confusable_pairs": found, "frames_with_confusions": len({x["t"] for x in found}),
            "data_colours": data, "data_ok": all(v["ok"] for v in data.values()) if data else True}


# ---------------- motion ----------------
def _phase_shift(a, b, win):
    """the shift between two grey images by phase correlation (numpy), with the peak's strength"""
    A, B = np.fft.rfft2(a * win), np.fft.rfft2(b * win)
    R = A.conj() * B; R /= np.abs(R) + 1e-9
    r = np.fft.irfft2(R, s=a.shape); k = np.unravel_index(np.argmax(r), r.shape)
    dy, dx = [(v if v <= n // 2 else v - n) for v, n in zip(k, r.shape)]
    return float(dx), float(dy), float(r.max())


def motion(video, short=180):
    """camera movement (phase correlation of consecutive grey frames, px/s at the frame's own size) and picture change"""
    W, H, fps = _probe(video); prev = None; shifts, change = [], []; scale = min(W, H) / short; win = None
    for i, f in frames(video, short=short):
        g = f.astype(np.float32).mean(axis=2)
        if win is None:
            win = np.outer(np.hanning(g.shape[0]), np.hanning(g.shape[1])).astype(np.float32)
        if prev is not None:
            dx, dy, resp = _phase_shift(prev, g, win)
            shifts.append(float(np.hypot(dx, dy)) * scale * fps if resp > 0.1 else 0.0)
            change.append(float((np.abs(g - prev) > 6).mean()))
        prev = g
    s = np.array(shifts or [0.0]); c = np.array(change or [0.0])
    return {"camera_px_s": {"mean": round(float(s.mean()), 1), "p95": round(float(np.percentile(s, 95)), 1), "max": round(float(s.max()), 1)},
            "moving_frames_share": round(float((s > 15).mean()), 3), "changed_pixels": {"mean": round(float(c.mean()), 4), "p95": round(float(np.percentile(c, 95)), 4)}}


# ---------------- reduced motion ----------------
CALM_DROP_FX = ("speed_lines", "impacts")


def reduce_motion(s):
    """a shots.json with the motion that can trouble viewers taken out: no handheld drift, punch-ins or auto reframing
    (camera_auto off), camera moves held at their widest framing, line boil off, slides, wipes and irises made into
    dissolves, speed lines and impact bursts dropped. The acting, the timing and the words are unchanged.
    -> (shots, changes)"""
    import copy
    out = copy.deepcopy(s); changes = []
    for sh in out["shots"]:
        sid = sh["id"]
        if sh.get("camera_auto"):
            sh.pop("camera_auto"); changes.append(f"{sid}: automatic camera (reframing, punch-ins, handheld) off")
        cam = sh.get("camera")
        if isinstance(cam, list) and len(cam) > 1:
            widest = min(cam, key=lambda k: k[1][2])
            sh["camera"] = [[cam[0][0], widest[1]]]; changes.append(f"{sid}: camera move held at its widest framing (zoom {widest[1][2]})")
        st = sh.get("style") or {}
        if st.get("boil"):
            st.pop("boil"); changes.append(f"{sid}: line boil off")
        if st.get("handheld"):
            st.pop("handheld"); changes.append(f"{sid}: handheld off")
        tr = sh.get("transition")
        if isinstance(tr, dict) and tr.get("kind") not in (None, "dissolve", "dip"):
            changes.append(f"{sid}: {tr['kind']} transition made a dissolve"); sh["transition"] = {**tr, "kind": "dissolve"}; sh["transition"].pop("dir", None)
        fx = sh.get("fx")
        if isinstance(fx, dict):
            for k in CALM_DROP_FX:
                if fx.pop(k, None) is not None:
                    changes.append(f"{sid}: {k.replace('_', ' ')} dropped")
            if not fx:
                sh.pop("fx")
        comp = sh.get("comp")
        if isinstance(comp, dict) and comp.get("dof"):
            pass   # depth of field stays: it does not move
    return out, changes
