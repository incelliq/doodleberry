"""Audio description (WP-24): a describer's track written from the film's own data and voiced into its pauses.

What the picture shows that the words do not is already written down in shots.json: the set, who is in the shot and
how they come in, what they do (the clips of their timelines, held faces), and the text, numbers and charts drawn on
screen. Each shot gives a few **events** (the shot's start, each clip and on-screen element as it appears), each a
short sentence in plain present tense, as describers write ("Ravi and Priya are in a classroom." "Ravi points."). On-
screen text the narration already says is not read again. A shot can carry its own words, "describe": "..." in
shots.json, which replace the generated start of that shot ("describe": false leaves the shot undescribed).

Events are **placed in the pauses** first: never over a spoken line (0.15 s clear either side), as soon after the
moment as the pauses allow and before the shot ends; a sentence that does not fit loses its less important parts,
then may be read up to 20% faster. What still does not fit is **extended** (WCAG 1.2.7, extended audio
description): the picture holds on the frame at the end of the line being spoken (a hold never splits a line) while
the description is read, and the film then carries on; events that land in the same place share one hold. Only
what is worth stopping the film for is extended (the setting, who comes in, text, numbers and charts on screen);
gestures, faces and icons are read in pauses or left out. The described cut is therefore a little longer than the film; its
captions are retimed to match.

Each cue is voiced by a clean Kokoro voice different from the film's own speakers; the film's sound is lowered by
10 dB under cues placed in pauses (150 ms ramps) and silent during holds; the result is brought to -14 LUFS, true
peak limited below -1.6 dBTP.
"""
import re
import subprocess

import numpy as np

SETS = {"park": "in a park", "clinic": "in a clinic", "paper": "on a sheet of paper", "cutaway": "in a cutaway of the ground", "kitchen": "in a kitchen",
        "classroom": "in a classroom", "office": "in an office", "street": "on a street", "farm": "on a farm", "bedroom": "in a bedroom", "forest": "in a forest",
        "lab": "in a lab", "night": "under a night sky", "reservoir": "by a reservoir", "stage": "on a stage", "map": "in front of a map", "space": "in space"}
VERBS = {"celebrate": "cheers", "clap": "claps", "cross_arms": "folds their arms", "facepalm": "puts their face in their hand", "head_shake": "shakes their head",
         "jump": "jumps", "nod": "nods", "point_L": "points", "point_R": "points", "present_L": "gestures to the side", "present_R": "gestures to the side",
         "run": "runs", "sad": "droops", "scratch_head": "scratches their head", "shrug": "shrugs", "stomp": "stomps", "surprised": "starts in surprise",
         "think": "thinks", "wave_L": "waves", "wave_R": "waves", "hop": "hops", "lean_in": "leans in", "shake": "shakes", "tilt": "tilts their head",
         "tilt_R": "tilts their head", "wag": "wags"}
QUIET = {"idle", "talk", "talk_beat", "talk_open_palms", "blink", "breathe"}
EMOTIONS = {"happy": "smiles", "sad": "looks sad", "surprised": "looks surprised", "angry": "frowns", "worried": "looks worried", "thinking": "looks thoughtful",
            "excited": "beams", "confused": "looks puzzled", "proud": "looks proud"}
PAD = 0.15        # seconds kept clear around spoken lines
WPS = 2.9         # describer pace, words a second (about 175 wpm)
MAX_SPEED = 1.2   # a cue may be read up to this much faster to fit its pause
DUCK_DB = -10.0
HOLD_PAD = (0.3, 0.45)   # silence before and after a description read in a hold


def _words(t):
    return re.findall(r"[a-z0-9']+", t.lower())


def _and(names):
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _spoken_near(text, lines, t, span=6.0):
    """the share of an on-screen text's words that a line spoken around then also says"""
    w = set(_words(text))
    if not w:
        return 1.0
    said = set()
    for l in lines:
        if l["end"] >= t - span and l["start"] <= t + span:
            said |= set(_words(l.get("text", "")))
    return len(w & said) / len(w)


def _name(cast, puppets):
    p = puppets.get(cast["puppet"]) or {}
    return p.get("name") or cast.get("speaker", "").title() or "A character"


def _entrance(place, W):
    if isinstance(place, list) and len(place) > 1:
        x0, x1 = place[0][1].get("x", W / 2), place[-1][1].get("x", W / 2)
        if x0 < 0 <= x1 <= W:
            return "walks in from the left"
        if x0 > W >= x1 >= 0:
            return "walks in from the right"
        if 0 <= x0 <= W and (x1 < 0 or x1 > W):
            return "walks off"
    if isinstance(place, dict) and "path" in place:
        return "walks across"
    return None


def _overlay_text(o, data, lines, t):
    k = o.get("type")
    txt = o.get("text")
    txt = " ".join(txt) if isinstance(txt, list) else txt
    txt = re.sub(r"[\[\]]", "", txt or "")
    if k == "sign" and txt:
        return f'A sign reads "{txt}".', 2
    if k in ("title", "paper", "text", "section") and txt:
        return (None, 0) if _spoken_near(txt, lines, t) >= 0.6 else (f'On screen: "{txt}".', 2)
    if k == "card":
        body = ": ".join(x.rstrip(".") for x in (o.get("title"), o.get("body")) if x)
        return (None, 0) if _spoken_near(body, lines, t) >= 0.6 else (f'A card: "{body}".', 2)
    if k == "counter":
        v = o.get("to"); dec = o.get("decimals", 0)
        s = f"{v:.{dec}f}" if isinstance(v, (int, float)) else str(v)
        s = (o.get("prefix", "") + s + o.get("suffix", "")).replace("°", " degrees")
        return (None, 0) if _spoken_near(s, lines, t) >= 0.6 else (f"A number appears: {s}.", 1)
    if k == "bars":
        rows = o.get("data")
        if rows is None and o.get("data_from"):
            rows = data
            for part in o["data_from"].split("."):
                rows = rows.get(part) if isinstance(rows, dict) else None
        title = o.get("title") or "a bar chart"
        if isinstance(rows, list) and rows and all(isinstance(r, list) and len(r) >= 2 for r in rows):
            top = max(rows, key=lambda r: r[1])
            return f"A bar chart, {title}: {len(rows)} bars, highest for {top[0]} at {top[1]}.", 2
        return f"A bar chart: {title}.", 2
    if k == "icon" and o.get("name"):
        return f"An icon: {o['name'].replace('-', ' ')}.", 0
    if k == "citation" and txt:
        return f"{txt.rstrip(',')}.", 1
    if k == "console" and o.get("lines"):
        return "A terminal shows a command and its output.", 1
    if k == "face":
        return f"A face appears, looking {o.get('mood', 'calm')}.", 0
    return None, 0


def events(s, timing, puppets, data, W, rt):
    """[(t, priority, text, shot, parts)]: what each shot shows, in the order it appears (priority 2 most important)"""
    lines = timing.get("lines", []); ev = []; last_set = None; seen = set()
    for sh in s["shots"]:
        t0 = sh["start"]
        if sh.get("describe") is False:
            last_set = sh.get("set"); continue
        parts = []; new_names = []; entrances = []
        st = sh.get("set"); where = SETS.get(st) if st != last_set else None
        last_set = st
        for c in sh.get("cast", []):
            nm = _name(c, puppets); en = _entrance(c.get("place"), W)
            if en:
                entrances.append(f"{nm} {en}.")
            elif nm not in seen:
                new_names.append(nm)
            seen.add(nm)
            tl = c.get("timeline") or {}
            for cl in tl.get("clips", []):
                v = VERBS.get(cl.get("clip"))
                if not v or cl.get("clip") in QUIET or (en and cl.get("clip") == "walk"):
                    continue
                tc = max(t0, rt(cl.get("start"), t0))
                (parts.append((1, f"{nm} {v}.")) if tc - t0 < 0.8 else ev.append((tc, 1, f"{nm} {v}.", sh["id"], [(1, f"{nm} {v}.")])))
            for k in tl.get("emotion") or []:
                if isinstance(k, list) and len(k) == 2 and k[1] in EMOTIONS:
                    tc = max(t0, rt(k[0], t0)); txt = f"{nm} {EMOTIONS[k[1]]}."
                    ev.append((tc, 0, txt, sh["id"], [(0, txt)]))
        verb = "is" if len(new_names) == 1 else "are"
        lead = (f"{_and(new_names)} {verb} {where}." if where and new_names else f"{where[0].upper()}{where[1:]}." if where else
                f"{_and(new_names)} {'appears' if len(new_names) == 1 else 'appear'}." if new_names else None)
        if lead:
            parts.insert(0, (2, lead))
        parts[1:1] = [(2, e) for e in entrances]
        for o in (sh.get("overlays") or []) + (sh.get("underlays") or []):
            st_ = o.get("start")
            tc = t0 if st_ is None or (isinstance(st_, (int, float)) and st_ < 0) else max(t0, rt(st_, t0))
            txt, pr = _overlay_text(o, data, lines, tc)
            if txt:
                (parts.append((pr, txt)) if tc - t0 < 0.8 else ev.append((tc, pr, txt, sh["id"], [(pr, txt)])))
        if isinstance(sh.get("describe"), str):
            parts = [(3, sh["describe"])]
        if parts:
            ev.append((t0, max(p for p, _ in parts), " ".join(t for _, t in parts), sh["id"], parts))
    return sorted(ev, key=lambda e: e[0])


def pauses(timing, total):
    """[(start, end)] free of speech"""
    sp = sorted((l["start"] - PAD, l["end"] + PAD) for l in timing.get("lines", []))
    out, t = [], 0.0
    for a, b in sp:
        if a > t:
            out.append((t, a))
        t = max(t, b)
    if total > t:
        out.append((t, total))
    return out


def _hold_point(t, timing, total):
    """where a hold may go for an event at t: not inside a line (then at its end), and not past the film's end"""
    for l in timing.get("lines", []):
        if l["start"] - PAD < t < l["end"] + PAD:
            t = l["end"] + 0.05
    return round(min(t, max(0.0, total - 0.05)), 3)


def place(evs, gaps, shot_end, timing, total, extend=True):
    """-> (cues in pauses, holds, dropped). Each event goes in the first pause after it (before its shot ends) with
    room, losing minor parts and then reading faster if it must; else into a hold (extended description)."""
    cues, holds, dropped = [], {}, []; used = []
    for t, pr, text, sid, parts in evs:
        end_by = shot_end[sid]
        options = [text] + [" ".join(x for _, x in sorted(parts, key=lambda x: -x[0])[:n]) for n in range(len(parts) - 1, 0, -1)]
        done = False
        for txt in options:
            need = len(_words(txt)) / WPS + 0.2
            for a, b in gaps:
                a2 = max(a, t - 0.3)
                for u0, u1 in used:
                    if u0 < b and u1 > a2:
                        a2 = max(a2, u1 + 0.25)
                b2 = min(b, end_by + 0.5); room = b2 - a2
                if room <= 0.6 or a2 > t + 6:
                    continue
                if need / MAX_SPEED <= room:
                    dur = min(need, room)
                    cues.append({"start": round(a2, 3), "end": round(a2 + dur, 3), "text": txt, "shot": sid, "event_t": round(t, 3), "speed": round(max(1.0, need / room), 3),
                                 **({"shortened": True} if txt != text else {})})
                    used.append((a2, a2 + dur)); done = True; break
            if done:
                break
        if done:
            continue
        keep = " ".join(x for p_, x in parts if p_ >= 2)   # what is worth stopping the film for: setting, entrances, on-screen information
        if extend and keep:
            at = _hold_point(t, timing, total); holds.setdefault(at, []).append({"text": keep, "shot": sid, "event_t": round(t, 3)})
            if keep != text:
                dropped.append({"t": round(t, 3), "text": " ".join(x for p_, x in parts if p_ < 2), "shot": sid})
        else:
            dropped.append({"t": round(t, 3), "text": text, "shot": sid})
    hl = [{"at": at, "text": " ".join(x["text"] for x in xs), "shots": sorted({x["shot"] for x in xs}), "events": [x["event_t"] for x in xs]} for at, xs in sorted(holds.items())]
    return sorted(cues, key=lambda c: c["start"]), hl, dropped


def shift_of(holds):
    """film time -> described cut time"""
    pts = sorted((h["at"], h["dur"]) for h in holds)
    return lambda t: t + sum(d for a, d in pts if a <= t + 1e-9)


def vtt(cues):
    f = lambda t: f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{t % 60:06.3f}"
    return "WEBVTT\nKind: descriptions\n\n" + "\n".join(f"{i + 1}\n{f(c['start'])} --> {f(c['end'])}\n{c['text']}\n" for i, c in enumerate(cues))


def retime_vtt(text, shift):
    """a WebVTT file's cue times moved onto the described cut's clock"""
    def ts(m):
        h, mi, s = m.group(1), m.group(2), m.group(3); t = int(h) * 3600 + int(mi) * 60 + float(s); t = shift(t)
        return f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{t % 60:06.3f}"
    return re.sub(r"(\d{2}):(\d{2}):(\d{2}\.\d{3})", ts, text)


def voice_all(texts, voice_id, voices_dir, sr_out, slots=None):
    """each text voiced (a slot, if given, is the most time it may take: read faster up to MAX_SPEED)"""
    import sys
    from pathlib import Path
    from scipy.signal import resample_poly
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))
    import kokoro_voice as K
    v = K.KokoroVoice(voice_id, voices_dir); out = []
    for i, txt in enumerate(texts):
        a, sr = v.synth(txt, length_scale=1.0)
        slot = (slots or [None] * len(texts))[i]
        if slot and len(a) / sr > slot:
            a, sr = v.synth(txt, length_scale=max(1 / MAX_SPEED, slot / (len(a) / sr)))
        a = resample_poly(a, sr_out, sr) if sr != sr_out else a
        nz = np.nonzero(np.abs(a) > 0.01)[0]
        a = a[max(0, nz[0] - int(0.03 * sr_out)): nz[-1] + int(0.05 * sr_out)] if len(nz) else a
        out.append(a.astype(np.float32))
    return out


def _level(a, meter, target=-18.0):
    if len(a) > int(0.4 * meter.rate):
        l = meter.integrated_loudness(a)
        if np.isfinite(l):
            return a * 10 ** ((target - l) / 20)
    return a


def build_audio(main, sr, cues, cue_clips, holds, hold_clips):
    """the described mix on the described cut's clock: the main mix with silence at each hold (short fades either
    side), lowered under cues in pauses; every description added. -> stereo float"""
    import pyloudnorm as pyln
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))
    from audio import limit
    x = main if main.ndim == 2 else np.stack([main, main], 1); meter = pyln.Meter(sr); fade = int(0.03 * sr)
    segs, prev = [], 0
    for h in holds:
        i = int(round(h["at"] * sr)); seg = x[prev:i].copy()
        if len(seg) > fade:
            seg[-fade:] *= np.linspace(1, 0, fade)[:, None]
        segs += [seg, np.zeros((int(round(h["dur"] * sr)), 2), np.float32)]; prev = i
    tail = x[prev:].copy()
    if holds and len(tail) > fade:
        tail[:fade] *= np.linspace(0, 1, fade)[:, None]
    y = np.concatenate(segs + [tail]); n = len(y); g = np.ones(n, np.float32); ramp = int(0.15 * sr); low = 10 ** (DUCK_DB / 20)
    ad = np.zeros(n, np.float32); shift = shift_of(holds)
    for c, a in zip(cues, cue_clips):
        i0 = int(shift(c["start"]) * sr); a = _level(a, meter)[:max(0, n - i0)]; i1 = i0 + len(a)
        ad[i0:i1] += a
        a0, a1 = max(0, i0 - ramp), min(n, i1 + ramp); env = np.full(a1 - a0, low, np.float32)
        k = i0 - a0; env[:k] = np.linspace(1, low, k); k2 = a1 - i1
        if k2 > 0:
            env[-k2:] = np.linspace(low, 1, k2)
        g[a0:a1] = np.minimum(g[a0:a1], env)
    for h, a in zip(holds, hold_clips):
        i0 = int((shift(h["at"]) - h["dur"] + HOLD_PAD[0]) * sr); a = _level(a, meter)[:max(0, n - i0)]
        ad[i0:i0 + len(a)] += a
    y = y * g[:, None] + ad[:, None]
    for _ in range(3):   # to -14 LUFS, limited below -1.6 dBTP (as the main mix)
        y = y * 10 ** ((-14 - meter.integrated_loudness(y)) / 20); y = limit(y, -1.6)
    return y.astype(np.float32)


def build_video(final, holds, fps, out, crf=18):
    """the final's picture with each hold: the frame at that moment held for the hold's length"""
    if not holds:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(final), "-map", "0:v", "-c:v", "copy", str(out)], check=True); return
    parts, prev, k = [], 0.0, 0
    for h in holds:
        parts.append(f"[0:v]trim=start={prev:.4f}:end={h['at']:.4f},setpts=PTS-STARTPTS[v{k}]"); k += 1
        n = max(1, int(round(h["dur"] * fps)))
        parts.append(f"[0:v]trim=start={h['at']:.4f}:end={h['at'] + 1 / fps:.4f},setpts=PTS-STARTPTS,loop=loop={n - 1}:size=1:start=0,setpts=N/{fps}/TB[v{k}]"); k += 1
        prev = h["at"]
    parts.append(f"[0:v]trim=start={prev:.4f},setpts=PTS-STARTPTS[v{k}]"); k += 1
    fc = ";".join(parts) + ";" + "".join(f"[v{i}]" for i in range(k)) + f"concat=n={k}:v=1:a=0,fps={fps}[v]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(final), "-filter_complex", fc, "-map", "[v]", "-c:v", "libx264", "-crf", str(crf),
                    "-preset", "medium", "-pix_fmt", "yuv420p", str(out)], check=True)
