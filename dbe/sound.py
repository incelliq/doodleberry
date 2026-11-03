"""Sound editing (WP-40): a sound designer's edits to a film's cues and music, kept in films/<name>/sound.json and
applied every time the mix is made, so they survive re-renders (the cues themselves are derived again each time: a
whoosh on every cut, cues the shots declare, foley from the motion).

    {"edits": [
       {"op": "move",    "type": "thud", "t": 2.35, "to": 2.50},     // the cue of that type nearest t (within 0.15 s)
       {"op": "gain",    "type": "pop_small", "t": 1.9, "gain": 0.5},
       {"op": "replace", "type": "whoosh", "t": 4.11, "with": "pop_small"},
       {"op": "trim",    "type": "scratch", "t": 0.4, "dur": 0.8},
       {"op": "delete",  "type": "step", "t": 3.0},
       {"op": "add",     "t": 5.2, "type": "ding", "gain": 0.8}],
     "music": [
       {"start": 3.0, "end": 6.0, "kind": "reflect"}]}           // swap the music in a span: main | intro | finale | reflect | none

Music swaps cut the score's sections at the nearest beats and give the span the new kind (the chords carry on), so
the swap lands on the beat grid. Edits that find nothing are reported, not dropped silently.

Any time (t, to, start, end) may be line-relative, like shots.json: "got.end-0.36" is 0.36 s before line "got" ends.
The Studio page writes them that way, so the edits follow the words (and the foley that follows the acting) when a
film is re-voiced or translated.
"""
import copy
import json
import math
from pathlib import Path

import numpy as np

KINDS = ("main", "intro", "finale", "reflect", "none")


def resolve(edits_doc, timing):
    """line-relative times in a sound.json document -> seconds, for this voicing"""
    import re
    L = {l["id"]: l for l in (timing or {}).get("lines", [])}
    pat = re.compile(r"^\s*([\w-]+)\.(start|end)\s*([+-]\s*[\d.]+)?\s*$")

    def sec(v):
        if not isinstance(v, str):
            return v
        m = pat.match(v)
        if not m or m.group(1) not in L:
            raise ValueError(f"sound.json: unknown time {v!r}")
        return round(L[m.group(1)][m.group(2)] + float((m.group(3) or "0").replace(" ", "")), 3)
    out = {"edits": [{k: (sec(v) if k in ("t", "to") else v) for k, v in e.items()} for e in edits_doc.get("edits", [])],
           "music": [{k: (sec(v) if k in ("start", "end") else v) for k, v in m.items()} for m in edits_doc.get("music", [])]}
    return out


def line_relative(t, timing, fps=30):
    """a time in seconds written against the nearest line start or end (seconds again when there are no lines)"""
    best = None
    for l in (timing or {}).get("lines", []):
        for k in ("start", "end"):
            d = t - l[k]
            if best is None or abs(d) < abs(best[2]):
                best = (l["id"], k, d)
    if not best:
        return round(t, 3)
    lid, k, d = best
    return f"{lid}.{k}{'+' if d >= 0 else '-'}{abs(d):.3f}"


def apply_edits(cues, edits, tol=0.15):
    """-> (cues after the edits, [report per edit])"""
    out = [dict(c) for c in cues]
    for c in out:
        c.setdefault("origin", "derived")
    rep = []
    for e in edits or []:
        op = e.get("op")
        if op == "add":
            out.append({"t": round(float(e["t"]), 3), "type": e["type"], "gain": e.get("gain", 1), **({"dur": e["dur"]} if e.get("dur") else {}), "origin": "added"})
            rep.append({"op": op, "ok": True, "t": e["t"]}); continue
        cand = [(abs(c["t"] - float(e["t"])), i) for i, c in enumerate(out) if c["type"] == e.get("type") and c.get("origin") != "deleted"]
        cand = [x for x in cand if x[0] <= tol]
        if not cand:
            rep.append({"op": op, "ok": False, "why": f"no {e.get('type')} cue within {tol} s of {e.get('t')}"}); continue
        i = min(cand)[1]; c = out[i]
        if op == "move":
            c["t"] = round(float(e["to"]), 3)
        elif op == "gain":
            c["gain"] = float(e["gain"])
        elif op == "replace":
            c["type"] = e["with"]
        elif op == "trim":
            c["dur"] = float(e["dur"])
        elif op == "delete":
            c["origin"] = "deleted"
        else:
            rep.append({"op": op, "ok": False, "why": "unknown op"}); continue
        if op != "delete":
            c["origin"] = "edited"
        rep.append({"op": op, "ok": True, "t": c["t"], "type": c["type"]})
    kept = sorted((c for c in out if c.get("origin") != "deleted"), key=lambda c: c["t"])
    return kept, rep


def apply_music(score, swaps):
    """the score with each swap's span given its kind, sections cut at the nearest beats"""
    sc = copy.deepcopy(score)
    beat, off = 60 / sc["bpm"], sc.get("offset_s", 0)
    for sw in swaps or []:
        if sw.get("kind") not in KINDS:
            raise ValueError(f"music kind {sw.get('kind')!r}: one of {', '.join(KINDS)}")
        b0, b1 = round((float(sw["start"]) - off) / beat), round((float(sw["end"]) - off) / beat)
        if b1 <= b0:
            continue
        secs = []
        for s in sc["sections"]:
            a, z = s["from_beat"], s["to_beat"]
            for lo, hi, inside in ((a, min(z, b0), False), (max(a, b0), min(z, b1), True), (max(a, b1), z, False)):
                if hi <= lo:
                    continue
                piece = {**s, "from_beat": lo, "to_beat": hi}
                # chords keep their place in the bar cycle: rotate the progression to where this piece starts
                k = ((lo - a) // 4) % max(1, len(s["chords"]))
                piece["chords"] = s["chords"][k:] + s["chords"][:k]
                if hi != z:
                    piece.pop("end_chord", None)
                if inside:
                    piece["kind"] = sw["kind"]; piece["swapped"] = True
                secs.append(piece)
        sc["sections"] = secs
    return sc


def onset(stem_wav, t, window=0.25, frame_s=1 / 30):
    """the first onset in a stem within window of t: where the short-term energy jumps (in seconds), or None"""
    import soundfile as sf
    x, sr = sf.read(str(stem_wav), dtype="float64")
    if x.ndim > 1:
        x = x.mean(axis=1)
    hop = int(sr * 0.002); win = int(sr * 0.006)
    a = max(0, int((t - 1.5 * frame_s) * sr)); z = min(len(x), int((t + window) * sr))   # from just before t: an earlier hit is not this one
    seg = x[max(0, a - win):z]
    if len(seg) < win * 3:
        return None
    e = np.array([np.sqrt(np.mean(seg[i:i + win] ** 2)) for i in range(0, len(seg) - win, hop)])
    floor = np.percentile(e, 20) + 1e-6
    rise = np.flatnonzero((e[1:] > 4 * floor) & (e[1:] > 1.8 * e[:-1]) & (e[1:] > 0.02 * e.max() + 1e-6))
    if not len(rise):
        return None
    return round((max(0, a - win) + (rise[0] + 1) * hop) / sr, 4)


def energy(stem_wav, t0, t1, band=None):
    """RMS of a stem between two times (dBFS), optionally in a frequency band"""
    import soundfile as sf
    x, sr = sf.read(str(stem_wav), dtype="float64")
    if x.ndim > 1:
        x = x.mean(axis=1)
    seg = x[int(t0 * sr):int(t1 * sr)]
    if band:
        from scipy.signal import butter, sosfilt
        seg = sosfilt(butter(4, band, btype="bandpass", fs=sr, output="sos"), seg)
    return round(20 * math.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9), 2)


def audacity(out_dir, stems, cues, sections):
    """an Audacity project to open: a LOF (list of files, each at its offset) and label tracks of the cues and the
    music sections (File > Import > Labels)"""
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "project.lof").write_text("".join(f'file "{Path(p).resolve()}" offset 0\n' for p in stems))
    (out_dir / "cues.txt").write_text("".join(f"{c['t']:.3f}\t{c['t'] + c.get('dur', 0):.3f}\t{c['type']}\n" for c in cues))
    (out_dir / "music.txt").write_text("".join(f"{s['start']:.3f}\t{s['end']:.3f}\t{s['kind']}\n" for s in sections))
    return [str(out_dir / f) for f in ("project.lof", "cues.txt", "music.txt")]


def sections_in_time(score):
    beat, off = 60 / score["bpm"], score.get("offset_s", 0)
    return [{"i": i, "start": round(off + s["from_beat"] * beat, 3), "end": round(off + s["to_beat"] * beat, 3), "kind": s["kind"], "chords": s["chords"],
             "swapped": bool(s.get("swapped"))} for i, s in enumerate(score["sections"])]


def self_test():
    cues = [{"t": 1.0, "type": "thud", "gain": 1}, {"t": 2.0, "type": "pop_small", "gain": 0.9}, {"t": 3.0, "type": "whoosh", "gain": 0.7}]
    out, rep = apply_edits(cues, [{"op": "move", "type": "thud", "t": 1.05, "to": 1.4}, {"op": "replace", "type": "whoosh", "t": 3.0, "with": "ding"},
                                   {"op": "delete", "type": "pop_small", "t": 2.0}, {"op": "add", "t": 0.5, "type": "step"}, {"op": "gain", "type": "thud", "t": 9, "gain": 0.1}])
    bad = []
    if [(c["t"], c["type"]) for c in out] != [(0.5, "step"), (1.4, "thud"), (3.0, "ding")] or rep[-1]["ok"] or not all(r["ok"] for r in rep[:-1]):
        bad.append({"edits": [out, rep]})
    sc = {"bpm": 100, "offset_s": 0, "sections": [{"kind": "main", "from_beat": 0, "to_beat": 16, "chords": ["F", "Dm", "Bb", "C"], "end_chord": "F"}]}
    m = apply_music(sc, [{"start": 2.4, "end": 4.8, "kind": "reflect"}])   # beats 4 to 8
    got = [(s["from_beat"], s["to_beat"], s["kind"], s["chords"][0], s.get("end_chord")) for s in m["sections"]]
    if got != [(0, 4, "main", "F", None), (4, 8, "reflect", "Dm", None), (8, 16, "main", "Bb", "F")]:
        bad.append({"music": got})
    return bad, {"edits": len(rep), "sections": got}
