"""Measured layout and delivery checks (plan 0.11), learned from the bioinformatics.lk film playbook:

- frame fill: share of bare ground per scene, sampled every 3 s from the final encode (playbook definition: a pixel is
  bare when it matches a ground colour and sits in a flat area)
- safe zones and type sizes: every on-screen word inside the platform-safe area (at least three quarters of its box)
  and at least the minimum size
- reading time: static text blocks stay up for at least words / 3 + 1 s; caption flow speed
- seams: mean frame difference at each cut
- cold open: a character on screen in frame one, and the first words by 1.5 s
- mix: effects below music; effect onsets within one frame of their cues

- AI look: drop shadows, gradient blobs, blur glows, emoji and everything centred (gradients and filters of the house
  set library are ours and exempt)

Thresholds were calibrated per style (WP-04: explainer, doodle, cartoon) on reference films and live in
dbe/profiles.json "layout_styles", with the checks each style enforces. A film's style is inferred from its cast (or set
with shots.json "style"); shots.json "qa" may add thresholds and enforced checks of its own.
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


def safe_and_size(boxes, size, inside_min=0.75, zoom_max=1.25):
    """a word is outside when less than inside_min of its box lies in the safe area; a word the camera has pushed
    entirely out of frame is not on screen, and one magnified past zoom_max by a push-in is background detail cropped by
    the frame, so neither is counted (type size is still checked for every visible word)"""
    asp = aspect_of(*size); x0, y0, x1, y1 = SAFE[asp]; mn = MIN_PX[asp]; W, H = size
    out_of, small = [], []
    for b in boxes:
        if b["x1"] <= 0 or b["y1"] <= 0 or b["x0"] >= W or b["y0"] >= H:
            continue
        if b.get("zoom", 1) > zoom_max:   # set text magnified by a camera push-in: cropped background, not text to read
            continue
        area = max(1e-6, (b["x1"] - b["x0"]) * (b["y1"] - b["y0"]))
        inside = max(0, min(b["x1"], x1) - max(b["x0"], x0)) * max(0, min(b["y1"], y1) - max(b["y0"], y0)) / area
        if inside < inside_min:
            out_of.append({k: (round(v) if isinstance(v, float) and k != "t" else v) for k, v in b.items() if k in ("t", "text", "x0", "y0", "x1", "y1")})
        if b["px"] < mn - 0.5:
            small.append({"t": b["t"], "text": b["text"], "px": b["px"]})
    dedupe = lambda L: list({x["text"]: x for x in L}.values())
    return {"aspect": asp, "safe_area": [x0, y0, x1, y1], "min_px": mn, "outside_safe": dedupe(out_of)[:20], "too_small": dedupe(small)[:20]}


def reading_time(shots_resolved, timing, captions=True, warp=None, script=None):
    """static blocks (timed overlays, silent bubbles) need words / 3 + 1 s on screen; the caption pace counts only when
    the film shows captions. warp ([[cut, film], ...], a sound-off cut): every line shown as a bubble, a thought or a
    narration box needs the same, on the cut's own clock (WP-17)"""
    short = []
    if warp and len(warp) >= 2:
        def to_cut(t):   # film time -> cut time, piecewise linear through the knots
            if t <= warp[0][1]:
                return warp[0][0] + (t - warp[0][1])
            for a, b in zip(warp, warp[1:]):
                if t <= b[1]:
                    return a[0] + (b[0] - a[0]) * (t - a[1]) / ((b[1] - a[1]) or 1)
            return warp[-1][0] + (t - warp[-1][1])
        bubble_text = {l.get("id"): l.get("bubble") for l in (script or {}).get("lines", [])}
        for l in timing.get("lines", []):
            text = bubble_text.get(l.get("id")) or l.get("text", "")
            n = len(re.findall(r"[\w']+", text)); need = n / 3 + 1; on = to_cut(l["end"] + 0.5) - to_cut(l["start"] - 0.12)
            if n and on < need - 1e-6:
                short.append({"line": l.get("id"), "text": text[:50], "on_screen_s": round(on, 2), "needs_s": round(need, 2)})
    for s in shots_resolved:
        blocks = [(o.get("text", ""), o.get("start"), o.get("end")) for o in s.get("overlays", []) if o.get("start") is not None and o.get("end") is not None]
        blocks += [(b.get("text", ""), b.get("start"), b.get("end")) for b in s.get("extra_bubbles", [])]
        for text, a, b in blocks:
            text = " ".join(map(str, text)) if isinstance(text, list) else str(text or "")   # kit signs take a list of lines
            n = len(re.findall(r"[\w']+", text)); need = n / 3 + 1
            if n and b - a < need - 1e-6:
                short.append({"shot": s["id"], "text": text[:50], "on_screen_s": round(b - a, 2), "needs_s": round(need, 2)})
    words = [w for l in timing.get("lines", []) for w in (l.get("words") or [])]
    speech_s = sum(l["end"] - l["start"] for l in timing.get("lines", [])) or 1
    return {"too_short": short, "caption_words_per_s": round(len(words) / speech_s, 2) if captions else None}


# ---------------- seams, cold open, mix ----------------
def seams(video, cuts, fps, windows=None):
    """windows: {cut time: (frames before, frames after)} for cuts made as transitions (WP-15): the largest change
    from one frame to the next anywhere in the transition counts"""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", "scale=192:108,format=gray", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, 108, 192).astype(np.float32)
    d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))
    out = []
    for c in cuts:
        i = int(round(c * fps)) - 1
        w = (windows or {}).get(round(c, 3))
        if 0 <= i < len(d):
            if w:   # a transition (WP-15): its sustained speed, the mean change per frame over the window (the blend's own rate
                # plus the shots' motion; a wipe reveals unevenly, so single steps vary), with the largest step reported too
                win = d[max(0, i - w[0] - 1):i + w[1] + 1]
                out.append({"t": round(c, 3), "change": round(float(win.mean()), 2), "largest_step": round(float(win.max()), 2), "transition_frames": w[0] + w[1]})
            else:
                out.append({"t": round(c, 3), "change": round(float(d[max(0, i - 1):i + 2].max()), 2)})
    return {"seams": out, "median_change": round(float(np.median(d)), 2) if len(d) else 0}


def cold_open(shots_resolved, timing, size):
    W, H = size
    first = shots_resolved[0]
    on = []
    for c in first.get("cast", []):
        pl = c.get("place", {})
        x = pl[0][1]["x"] if isinstance(pl, list) else (pl["path"]["points"][0][0] if "path" in pl else pl.get("x", W / 2))
        on.append(-60 <= x <= W + 60 and abs(x - W / 2) < W * 0.62)
    for o in first.get("overlays", []):   # a kit character (a face) counts when it is up from the first frame
        if o.get("type") == "face" and (o.get("start") or 0) <= 1 / 30 and -60 <= o.get("x", W / 2) <= W + 60:
            on.append(True)
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
        times = sorted({round(c["t"], 4) for c in cues})
        for c in cues:
            if any(k in c.get("type", "") for k in ("whoosh", "swish", "swell", "riser", "pad")):
                continue  # these swell into their moment by design (a swish ramps in over ~25 ms); only percussive cues are timed by onset
            prev = max([t for t in times if t < c["t"] - 1e-4] or [-1])
            # the window opens halfway after an earlier cue (else 0.1 s before), so a close neighbour's sound is not
            # taken for this cue's onset; the onset is the rise above what is already sounding
            t0 = max(c["t"] - 0.1, (prev + c["t"]) / 2)
            a, b = int(t0 * sr), int((c["t"] + 0.15) * sr)
            seg = env[max(0, a):max(0, b)]
            if not len(seg):
                continue
            base = float(seg[:max(1, int(0.005 * sr))].mean())
            if seg.max() - base < 1e-4:
                continue
            onset = np.argmax(seg > base + 0.2 * (seg.max() - base)) + max(0, a)
            offs.append(round((onset / sr - c["t"]) * 1000, 1))
        res["cue_onset_offsets_ms"] = offs
    return res


# ---------------- report ----------------
def style_of(shots_all):
    """explainer (kit and paper, no cast), doodle (doodle-template characters) or cartoon (the humanoid cast in
    illustrated sets); a film may say so itself with shots.json "style": "<name>" """
    if isinstance(shots_all.get("style"), str):
        return shots_all["style"]
    tpls = set()
    for sh in shots_all.get("shots", []):
        for c in sh.get("cast", []):
            try:
                tpls.add(json.loads((ROOT / c["puppet"]).read_text()).get("template", "humanoid"))
            except Exception:
                pass
    return "doodle" if "doodle" in tpls else "cartoon" if tpls else "explainer"


def style_config(style):
    """thresholds and enforced checks calibrated for a style (dbe/profiles.json layout_styles, WP-04)"""
    prof = json.loads((ROOT / "dbe" / "profiles.json").read_text()).get("layout_styles", {})
    return prof.get(style, {})


def house_ids():
    """gradient and filter ids defined by the house set library: part of our sets, not AI-look habits"""
    ids = set()
    for f in (ROOT / "sets").glob("*.js"):
        ids |= set(re.findall(r"<(?:linearGradient|radialGradient|filter)[^>]*\sid=\"([A-Za-z0-9_-]+)\"", f.read_text()))
    return sorted(ids)


def ai_look(page, step=1.0):
    r = subprocess.run(["node", "tools/ailook.mjs", str(page), str(step), ",".join(house_ids())], cwd=ROOT, capture_output=True, text=True, timeout=900)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else {"error": r.stderr[-400:]}


def config_for(shots_all):
    """the style's calibrated thresholds, then the film's own shots.json "qa" overrides; enforced checks are the union"""
    style = style_of(shots_all); sc = style_config(style)
    film_qa = shots_all.get("qa") or {}
    cfg = {**DEFAULTS, **{k: v for k, v in sc.items() if k != "enforce"}, **{k: v for k, v in film_qa.items() if k != "enforce"}}
    cfg["enforce"] = sorted(set(sc.get("enforce", [])) | set(film_qa.get("enforce", [])))
    return style, cfg


def judge(rep, cfg):
    """checks from measurements (a pure function, so seeded reports can be judged without rendering)"""
    checks = {}
    ff = rep.get("frame_fill")
    if ff:
        checks["frame_fill"] = max(ff["per_shot_mean"].values() or [0]) <= cfg["fill_max"]
    if rep.get("seams") is not None:
        checks["seams"] = all(x["change"] <= cfg["seam_max"] for x in rep["seams"]["seams"])
    al = rep.get("ai_look")
    if al and "error" not in al:
        checks["ai_look"] = not any(al[k]["frames"] for k in ("shadow", "gradient", "glow", "emoji")) and al["centred_share"] <= cfg.get("centred_max", 0.5)
    if rep.get("text"):
        checks["text_in_safe_area"] = not rep["text"]["outside_safe"]
        checks["type_size"] = not rep["text"]["too_small"]
    if rep.get("reading"):
        wps = rep["reading"]["caption_words_per_s"]
        checks["reading_time"] = not rep["reading"]["too_short"] and (wps is None or wps <= cfg["caption_wps_max"])
    co = rep.get("cold_open")
    if co:
        checks["cold_open"] = co["character_in_frame_one"] and co["first_text_s"] is not None and co["first_text_s"] <= cfg["hook_by_s"]
    m = rep.get("mix") or {}
    if m.get("sfx_lufs") is not None and m.get("music_lufs") is not None:
        checks["effects_below_music"] = m["sfx_lufs"] < m["music_lufs"]
    if m.get("cue_onset_offsets_ms"):
        checks["cue_sync"] = max(abs(o) for o in m["cue_onset_offsets_ms"]) <= cfg["sync_ms"]
    checks = {k: bool(v) for k, v in checks.items()}
    enforce = set(cfg.get("enforce", []))
    return {"checks": checks, "enforced": sorted(enforce),
            "failed_enforced": sorted(k for k in enforce if checks.get(k) is False),
            "advisory_failures": sorted(k for k, v in checks.items() if v is False and k not in enforce)}


def run(film_dir, page=None):
    from .commands import _shots, _json  # resolved times
    d = Path(film_dir); name = d.name
    shots_all = _shots(name); shots = shots_all["shots"]
    style, cfg = config_for(shots_all)
    size = shots_all.get("size", [1080, 1920]); fps = shots_all.get("fps", 30)
    timing = _json(d / "timing.json", {})
    video = d / "build" / "final.mp4"
    rep = {"config": cfg, "style": style}
    if video.exists():
        rep["frame_fill"] = frame_fill(video, shots, cfg.get("ground"))
        rep["frame_fill"]["worst_bare"] = (rep["frame_fill"]["worst_frame"] or {}).get("bare", 0)
        tw = {round(x["at"], 3): (x["before"], x["after"]) for x in _json(d / "build" / "transitions.json", [])}
        rep["seams"] = seams(video, [s["start"] for s in shots[1:]], fps, tw)
    boxes = []
    if page:
        tb = text_boxes(page); boxes += tb.get("boxes", [])
        if tb.get("error"):
            rep["text_probe_error"] = tb["error"]
        al = ai_look(page)   # generic-AI-look lint (WP-04)
        if "error" not in al:
            n = max(1, al["frames"])
            rep["ai_look"] = {k: {"frames": len({x["t"] for x in al[k]}), "first": al[k][:3]} for k in ("shadow", "gradient", "glow", "emoji", "centred")}
            rep["ai_look"]["centred_share"] = round(len(al["centred"]) / n, 3)
        else:
            rep["ai_look"] = al
    if shots_all.get("captions", True):
        boxes += caption_boxes(timing, size, shots_all.get("caption_style") or {})
    rep["text"] = safe_and_size(boxes, size)
    rep["reading"] = reading_time(shots, timing, captions=shots_all.get("captions", True), warp=shots_all.get("timewarp"), script=_json(d / "script.json", {}))
    rep["cold_open"] = cold_open(shots, timing, size)
    cues = _json(d / "build" / "cues.json", [])
    try:
        rep["mix"] = mix_checks(d / "build", cues)
    except Exception as e:  # soundfile missing etc.
        rep["mix"] = {"error": str(e)[:200]}
    rep.update(judge(rep, cfg))
    return rep


def self_test(tmp):
    """the AI-look probe flags a seeded page (shadow, gradient blob, glow, emoji, all centred) and passes a house set
    gradient; style inference and style configs read right"""
    fails, got = [], {}
    tmp = Path(tmp); tmp.mkdir(parents=True, exist_ok=True)
    page = tmp / "ailook_case.html"
    frame = ('<defs><filter id="sh"><feDropShadow dx="4" dy="6" stdDeviation="8"/></filter><filter id="neon"><feGaussianBlur stdDeviation="9"/></filter>'
             '<linearGradient id="blob"><stop offset="0" stop-color="#7f5af0"/><stop offset="1" stop-color="#2cb67d"/></linearGradient>'
             '<linearGradient id="skyg"><stop offset="0" stop-color="#9cf"/><stop offset="1" stop-color="#fff"/></linearGradient></defs>'
             '<rect width="1080" height="600" fill="url(#skyg)"/><rect x="100" y="700" width="880" height="500" rx="40" fill="url(#blob)" filter="url(#sh)"/>'
             '<text x="540" y="400" text-anchor="middle" font-size="60" filter="url(#neon)">Big idea \u2728</text>'
             '<text x="540" y="900" text-anchor="middle" font-size="50">Centred</text><text x="540" y="1300" text-anchor="middle" font-size="50">Also centred</text>')
    page.write_text("<!doctype html><html><body style='margin:0'><svg id='stage' xmlns='http://www.w3.org/2000/svg' width='1080' height='1920'></svg><script>"
                    "window.FILM={width:1080,height:1920};window.FILMTIME={start:0,end:2};window.frameAtTime=t=>{document.getElementById('stage').innerHTML=%s};"
                    "window.ready=true;</script></body></html>" % json.dumps(frame))
    r = ai_look(page, step=1.0)
    got["seeded"] = {k: len(r.get(k, [])) for k in ("shadow", "gradient", "glow", "emoji", "centred")} if "error" not in r else r
    if "error" in r or not all(r[k] for k in ("shadow", "gradient", "glow", "emoji", "centred")):
        fails.append(f"seeded AI look not caught: {got['seeded']}")
    elif any(x.get("id") == "skyg" for x in r["gradient"]):
        fails.append("a house set gradient was flagged")
    st = {"shots": [{"cast": [{"puppet": "cast/generated/ravi.puppet.json"}]}]}
    if style_of(st) != "cartoon" or style_of({"shots": [{}]}) != "explainer" or style_of({"style": "doodle", "shots": []}) != "doodle":
        fails.append("style inference")
    got["styles"] = {}
    for sty in ("explainer", "doodle", "cartoon"):
        sc = style_config(sty)
        if not sc:
            fails.append(f"no calibrated config for {sty}"); continue
        _, cfg = config_for({"style": sty, "shots": []})
        clean = _seed_report(cfg)
        j = judge(clean, cfg)
        if j["failed_enforced"] or j["advisory_failures"]:
            fails.append(f"{sty}: a report just inside its thresholds fails {j['failed_enforced'] + j['advisory_failures']}")
        caught = {}
        for chk, spoil in SEEDS.items():   # one seeded failure at a time
            bad = json.loads(json.dumps(clean)); spoil(bad, cfg)
            caught[chk] = chk in judge(bad, cfg)["failed_enforced"]
        missed = [c for c in cfg["enforce"] if c in caught and not caught[c]]
        if missed:
            fails.append(f"{sty}: seeded {missed} not failed")
        if not set(MUST_ENFORCE) <= set(cfg["enforce"]):
            fails.append(f"{sty}: does not enforce {sorted(set(MUST_ENFORCE) - set(cfg['enforce']))}")
        got["styles"][sty] = {"enforce": cfg["enforce"], "seeded_failures_caught": sorted(c for c, v in caught.items() if v)}
    return fails, got


MUST_ENFORCE = ["frame_fill", "text_in_safe_area", "type_size", "ai_look", "cold_open", "reading_time"]


def _seed_report(cfg):
    """measurements just inside a style's thresholds"""
    return {"frame_fill": {"per_shot_mean": {"s1": round(cfg["fill_max"] - 0.02, 3)}, "worst_frame": None},
            "seams": {"seams": [{"t": 3.0, "change": round(cfg["seam_max"] * 0.9, 2)}]},
            "ai_look": {**{k: {"frames": 0, "first": []} for k in ("shadow", "gradient", "glow", "emoji", "centred")}, "centred_share": round(cfg.get("centred_max", 0.5) * 0.5, 3)},
            "text": {"outside_safe": [], "too_small": []},
            "reading": {"too_short": [], "caption_words_per_s": round(cfg["caption_wps_max"] - 0.1, 2)},
            "cold_open": {"character_in_frame_one": True, "first_text_s": round(cfg["hook_by_s"] - 0.2, 2)},
            "mix": {"sfx_lufs": -30.0, "music_lufs": -20.0, "cue_onset_offsets_ms": [cfg["sync_ms"] - 4]}}


def _spoil_ai(r, cfg):
    r["ai_look"]["shadow"]["frames"] = 3


SEEDS = {   # one failure per check, the kind each style's reference films never show
    "frame_fill": lambda r, c: r["frame_fill"]["per_shot_mean"].update(s2=round(c["fill_max"] + 0.08, 3)),
    "seams": lambda r, c: r["seams"]["seams"].append({"t": 6.0, "change": c["seam_max"] * 3}),
    "ai_look": _spoil_ai,
    "text_in_safe_area": lambda r, c: r["text"]["outside_safe"].append({"t": 5, "text": "TITLE", "x0": 137, "y0": 1603, "x1": 513, "y1": 1748}),
    "type_size": lambda r, c: r["text"]["too_small"].append({"t": 2, "text": "fine print", "px": 18}),
    "reading_time": lambda r, c: r["reading"]["too_short"].append({"shot": "s1", "text": "a long sign", "on_screen_s": 0.8, "needs_s": 2.3}),
    "cold_open": lambda r, c: r["cold_open"].update(first_text_s=c["hook_by_s"] + 1.0),
    "effects_below_music": lambda r, c: r["mix"].update(sfx_lufs=-12.0),
    "cue_sync": lambda r, c: r["mix"].update(cue_onset_offsets_ms=[c["sync_ms"] * 3]),
}
