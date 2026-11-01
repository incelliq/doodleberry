"""Measured layout and delivery checks (plan 0.11), learned from the bioinformatics.lk film playbook:

- frame fill: share of bare ground per scene, sampled every 3 s from the final encode (playbook definition: a pixel is
  bare when it matches a ground colour and sits in a flat area)
- safe zones and type sizes: every on-screen word inside the platform-safe area and at least the minimum size
- reading time: static text blocks stay up for at least words / 3 + 1 s; caption flow speed
- seams: mean frame difference at each cut
- cold open: a character on screen in frame one, and the first words by 1.5 s
- mix: effects below music; effect onsets within one frame of their cues

Thresholds come from flat-paper explainer films. Every film gets the measurements; a check fails the film only if the
film opts in (shots.json "qa": {"enforce": [...]}) because cartoon styles need their own calibration first.
"""
import json
import re
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SAFE = {  # (x0, y0, x1, y1) text-safe areas, from the playbook's platform UI measurements
    "9:16": (64, 200, 960, 1560),    # TikTok / Reels / Shorts: right rail, caption block, top bar
    "16:9": (96, 54, 1824, 1026),    # 5% title-safe
}
MIN_PX = {"9:16": 26, "16:9": 24}
DEFAULTS = {"fill_max": 0.40, "seam_max": 3.5, "hook_by_s": 1.5, "caption_wps_max": 3.2, "sync_ms": 34}


def aspect_of(w, h):
    return "9:16" if h > w else "16:9"


# ---------------- frame fill ----------------
def _box(x, w):
    r = w // 2
    p = np.pad(x, ((r + 1, r), (r + 1, r)), mode="edge"); c = p.cumsum(0).cumsum(1)
    return (c[w:, w:] - c[:-w, w:] - c[w:, :-w] + c[:-w, :-w]) / (w * w)


def bare_share(rgb, ground=None, win=31, tol=14):
    """rgb: H x W x 3 float. Bare = matches a ground colour and is flat (grey std < 5 over a win-pixel window).
    ground: list of RGB triples; default = flat colours covering more than 12% of the frame."""
    g = rgb.mean(-1); m = _box(g, win); sd = np.sqrt(np.maximum(_box(g * g, win) - m * m, 0))
    flat = sd < 5
    if ground is None:
        q = (rgb[flat] // 8).astype(np.int32)
        if not len(q):
            return 0.0, []
        keys, counts = np.unique(q[:, 0] * 1024 + q[:, 1] * 32 + q[:, 2], return_counts=True)
        big = keys[counts > 0.12 * g.size]
        ground = [[(k // 1024) * 8 + 4, (k // 32 % 32) * 8 + 4, (k % 32) * 8 + 4] for k in big]
    if not ground:
        return 0.0, []
    near = np.zeros(g.shape, bool)
    for c in ground:
        near |= np.abs(rgb - np.array(c, np.float32)).max(-1) < tol
    return float((near & flat).mean()), ground


def frames_every(video, step, width):
    """-> list of (t, rgb float array) sampled every `step` seconds, scaled to `width`"""
    pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", str(video)],
                                   capture_output=True, text=True).stdout)["streams"][0]
    W, H = pr["width"], pr["height"]; h = round(width * H / W) // 2 * 2
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps=1/{step},scale={width}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, h, width, 3).astype(np.float32)
    return [(round(i * step, 2), f) for i, f in enumerate(fr)]


def frame_fill(video, shots, ground=None, step=3.0):
    rows = []
    for t, f in frames_every(video, step, 360):
        share, _ = bare_share(f, ground, win=11)  # 31 px at 1080 wide = about 11 px at 360
        sid = next((s["id"] for s in shots if s["start"] <= t < s["end"]), shots[-1]["id"])
        rows.append({"t": t, "shot": sid, "bare": round(share, 3)})
    per = {}
    for r in rows:
        per.setdefault(r["shot"], []).append(r["bare"])
    worst = max(rows, key=lambda r: r["bare"]) if rows else None
    return {"per_shot_mean": {k: round(sum(v) / len(v), 3) for k, v in per.items()}, "worst_frame": worst, "samples": rows}


# ---------------- text: safe zones, sizes, reading time ----------------
def text_boxes(page, step=0.5):
    r = subprocess.run(["node", "tools/textboxes.mjs", str(page), str(step)], cwd=ROOT, capture_output=True, text=True, timeout=900)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else {"size": None, "boxes": [], "error": r.stderr[-400:]}


def caption_boxes(timing, size, style):
    """boxes of the film-level burned-in captions (dbe/captions.py layout), one per caption chunk"""
    W, H = size
    fs = style.get("font_size", 88); bottom = H - style.get("y_from_bottom", 380); chunk = style.get("chunk", 3)
    out = []
    for line in timing.get("lines", []):
        ws = line.get("words") or []
        for c0 in range(0, len(ws), chunk):
            g = ws[c0:c0 + chunk]; text = " ".join(w["text"] for w in g)
            from .captions import fit_size, safe_width, safe_margins, CHAR_W
            f = fit_size(text, fs, safe_width(W, H)); tw = len(text) * f * CHAR_W
            ml, mr = safe_margins(W, H); cx = (ml + W - mr) / 2
            out.append({"t": g[0]["start"], "t1": g[-1]["end"], "text": text, "x0": cx - tw / 2, "x1": cx + tw / 2,
                        "y0": bottom - f * 1.15, "y1": bottom, "px": f, "words": len(g)})
    return out


def safe_and_size(boxes, size):
    asp = aspect_of(*size); x0, y0, x1, y1 = SAFE[asp]; mn = MIN_PX[asp]
    out_of, small = [], []
    for b in boxes:
        if b["x0"] < x0 - 1 or b["x1"] > x1 + 1 or b["y0"] < y0 - 1 or b["y1"] > y1 + 1:
            out_of.append({k: (round(v) if isinstance(v, float) else v) for k, v in b.items() if k in ("t", "text", "x0", "y0", "x1", "y1")})
        if b["px"] < mn - 0.5:
            small.append({"t": b["t"], "text": b["text"], "px": b["px"]})
    dedupe = lambda L: list({x["text"]: x for x in L}.values())
    return {"aspect": asp, "safe_area": [x0, y0, x1, y1], "min_px": mn, "outside_safe": dedupe(out_of)[:20], "too_small": dedupe(small)[:20]}


def reading_time(shots_resolved, timing):
    """static blocks (timed overlays, silent bubbles) need words / 3 + 1 s on screen"""
    short = []
    for s in shots_resolved:
        blocks = [(o.get("text", ""), o.get("start"), o.get("end")) for o in s.get("overlays", []) if o.get("start") is not None and o.get("end") is not None]
        blocks += [(b.get("text", ""), b.get("start"), b.get("end")) for b in s.get("extra_bubbles", [])]
        for text, a, b in blocks:
            n = len(re.findall(r"[\w']+", text)); need = n / 3 + 1
            if n and b - a < need - 1e-6:
                short.append({"shot": s["id"], "text": text[:50], "on_screen_s": round(b - a, 2), "needs_s": round(need, 2)})
    words = [w for l in timing.get("lines", []) for w in (l.get("words") or [])]
    speech_s = sum(l["end"] - l["start"] for l in timing.get("lines", [])) or 1
    return {"too_short": short, "caption_words_per_s": round(len(words) / speech_s, 2)}


# ---------------- seams, cold open, mix ----------------
def seams(video, cuts, fps):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", "scale=192:108,format=gray", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, 108, 192).astype(np.float32)
    d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))
    out = []
    for c in cuts:
        i = int(round(c * fps)) - 1
        if 0 <= i < len(d):
            out.append({"t": round(c, 3), "change": round(float(d[max(0, i - 1):i + 2].max()), 2)})
    return {"seams": out, "median_change": round(float(np.median(d)), 2) if len(d) else 0}


def cold_open(shots_resolved, timing, size):
    W, H = size
    first = shots_resolved[0]
    on = []
    for c in first.get("cast", []):
        pl = c.get("place", {})
        x = pl[0][1]["x"] if isinstance(pl, list) else pl.get("x", W / 2)
        on.append(-60 <= x <= W + 60 and abs(x - W / 2) < W * 0.62)
    words = [w["start"] for l in timing.get("lines", []) for w in (l.get("words") or [])]
    overlay0 = [o.get("start", 0) for o in first.get("overlays", []) if o.get("text")]
    hook_t = min(words[:1] + overlay0) if (words or overlay0) else None
    return {"character_in_frame_one": any(on), "first_text_s": hook_t}


def _lufs(wav):
    o = subprocess.run(["ffmpeg", "-nostats", "-i", str(wav), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", o)
    return float(m[-1]) if m else None


def mix_checks(build, cues):
    res = {}
    if (build / "sfx.wav").exists() and (build / "music.wav").exists():
        res["sfx_lufs"], res["music_lufs"] = _lufs(build / "sfx.wav"), _lufs(build / "music.wav")
    if (build / "sfx.wav").exists() and cues:
        sr = 48000
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(build / "sfx.wav"), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True, check=True).stdout
        x = np.abs(np.frombuffer(raw, np.float32))
        k = max(1, int(sr * 0.002)); env = np.convolve(x, np.ones(k) / k, mode="same")
        offs = []
        for c in cues:
            if any(k in c.get("type", "") for k in ("whoosh", "swell", "riser", "pad")):
                continue  # these swell into their moment by design; only percussive cues are timed by onset
            a, b = int((c["t"] - 0.1) * sr), int((c["t"] + 0.15) * sr)
            seg = env[max(0, a):max(0, b)]
            if not len(seg) or seg.max() < 1e-4:
                continue
            onset = np.argmax(seg > 0.2 * seg.max()) + max(0, a)
            offs.append(round((onset / sr - c["t"]) * 1000, 1))
        res["cue_onset_offsets_ms"] = offs
    return res


# ---------------- report ----------------
def run(film_dir, page=None):
    from .commands import _shots, _json  # resolved times
    d = Path(film_dir); name = d.name
    shots_all = _shots(name); shots = shots_all["shots"]
    cfg = {**DEFAULTS, **(shots_all.get("qa") or {})}
    size = shots_all.get("size", [1080, 1920]); fps = shots_all.get("fps", 30)
    timing = _json(d / "timing.json", {})
    video = d / "build" / "final.mp4"
    rep, checks = {"config": cfg}, {}
    if video.exists():
        rep["frame_fill"] = frame_fill(video, shots, cfg.get("ground"))
        worst = (rep["frame_fill"]["worst_frame"] or {}).get("bare", 0)
        checks["frame_fill"] = max(rep["frame_fill"]["per_shot_mean"].values() or [0]) <= cfg["fill_max"]
        rep["frame_fill"]["worst_bare"] = worst
        cuts = [s["start"] for s in shots[1:]]
        rep["seams"] = seams(video, cuts, fps)
        checks["seams"] = all(x["change"] <= cfg["seam_max"] for x in rep["seams"]["seams"])
    boxes = []
    if page:
        tb = text_boxes(page); boxes += tb.get("boxes", [])
        if tb.get("error"):
            rep["text_probe_error"] = tb["error"]
    if shots_all.get("captions", True):
        boxes += caption_boxes(timing, size, shots_all.get("caption_style") or {})
    rep["text"] = safe_and_size(boxes, size)
    checks["text_in_safe_area"] = not rep["text"]["outside_safe"]
    checks["type_size"] = not rep["text"]["too_small"]
    rep["reading"] = reading_time(shots, timing)
    checks["reading_time"] = not rep["reading"]["too_short"] and rep["reading"]["caption_words_per_s"] <= cfg["caption_wps_max"]
    rep["cold_open"] = cold_open(shots, timing, size)
    checks["cold_open"] = rep["cold_open"]["character_in_frame_one"] and rep["cold_open"]["first_text_s"] is not None and rep["cold_open"]["first_text_s"] <= cfg["hook_by_s"]
    cues = _json(d / "build" / "cues.json", [])
    try:
        rep["mix"] = mix_checks(d / "build", cues)
    except Exception as e:  # soundfile missing etc.
        rep["mix"] = {"error": str(e)[:200]}
    m = rep["mix"]
    if m.get("sfx_lufs") is not None and m.get("music_lufs") is not None:
        checks["effects_below_music"] = m["sfx_lufs"] < m["music_lufs"]
    if m.get("cue_onset_offsets_ms"):
        checks["cue_sync"] = max(abs(o) for o in m["cue_onset_offsets_ms"]) <= cfg["sync_ms"]
    enforce = set(cfg.get("enforce", []))
    checks = {k: bool(v) for k, v in checks.items()}
    rep["checks"] = checks
    rep["enforced"] = sorted(enforce)
    rep["failed_enforced"] = sorted(k for k in enforce if checks.get(k) is False)
    rep["advisory_failures"] = sorted(k for k, v in checks.items() if v is False and k not in enforce)
    return rep
