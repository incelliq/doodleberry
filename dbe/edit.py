"""Beat grid and master-to-many cuts (plan 2.14).

One production is rendered once per aspect (the master); an edit list (films/<name>/edit.json) assembles any number
of cuts from it: the full film, an episode series, teasers and recaps. Every cut point lands on the music's grid
(a bar line when one falls in the pause, else a beat) and never inside a spoken line, so picture and music cut
together. The audio of a cut is assembled from the master's mixed stems (voice, music, effects), so each segment
sounds exactly as it does in the master, then the joins are crossfaded and the whole is levelled to -14 LUFS.

edit.json:
  {"cuts": {
     "full":   {"aspect": "16:9", "ranges": "all"},
     "ep":     {"aspect": "9:16", "split": 4},                       -> ep1 .. ep4, split at scene changes
     "teaser": {"aspect": "9:16", "ranges": [["m1.start", "m1.end"], ["bar:10", "m5.end"]]},
     "recap":  {"ranges": [{"film": "other-film", "from": 3.2, "to": "l2.end"}, ["p3.start", "p3.end"]]}}}
Range ends are seconds, "bar:N" (bar N of the score, from 0) or line-relative ("id.start+0.2"); each is snapped
outward to the grid. A range may come from another film (an insert), cut on that film's grid.
"""
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILMS = ROOT / "films"


def grid(film_dir):
    """beats and bars (seconds) of a film's score"""
    d = Path(film_dir)
    sc = json.loads((d / "score.json").read_text())
    tm = json.loads((d / "timing.json").read_text())
    bpm, off = sc["bpm"], sc.get("offset_s", 0)
    beat = 60.0 / bpm
    total = sc.get("length_s") or tm.get("duration", 0)
    n = int(math.ceil((total - off) / beat)) + 1
    beats = [round(off + i * beat, 4) for i in range(n) if off + i * beat <= total + 1e-6]
    bars = [b for i, b in enumerate(beats) if i % 4 == 0]
    return {"bpm": bpm, "beat": beat, "bar": 4 * beat, "offset": off, "beats": beats, "bars": bars, "total": total}


def _time(v, lines, g):
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    m = re.match(r"^bar:(\d+)$", s)
    if m:
        return g["offset"] + int(m.group(1)) * g["bar"]
    m = re.match(r"^([\w-]+)\.(start|end)\s*([+-]\s*[0-9.]+)?$", s)
    if not m or m.group(1) not in lines:
        raise ValueError(f"bad time {v!r}: seconds, 'bar:N' or 'line.start|end[+-s]'")
    return lines[m.group(1)][m.group(2)] + (float(m.group(3).replace(" ", "")) if m.group(3) else 0.0)


def snap(x, side, lines, g, total):
    """move a cut point out of any spoken line, then onto the grid inside the pause it falls in:
    the bar line nearest to x, else the nearest beat, else the middle of the pause"""
    ls = sorted(lines.values(), key=lambda l: l["start"])
    for l in ls:  # inside a line: start cuts go before it, end cuts after it
        if l["start"] - 0.05 < x < l["end"] + 0.05:
            x = l["start"] - 0.05 if side == "start" else l["end"] + 0.05
    lo = max([l["end"] + 0.12 for l in ls if l["end"] <= x + 0.06] + [0.0])
    hi = min([l["start"] - 0.08 for l in ls if l["start"] >= x - 0.06] + [total])
    if x <= 0.05:
        return 0.0, "start"
    if x >= total - 0.05:
        return total, "end"
    for kind, pts in (("bar", g["bars"]), ("beat", g["beats"])):
        inside = [p for p in pts if lo <= p <= hi]
        if inside:
            return min(inside, key=lambda p: abs(p - x)), kind
    return round((lo + hi) / 2, 4) if hi > lo else x, "pause"


def _split_points(n, sh, lines, total):
    """n-1 boundaries: scene (shot) changes when there are exactly enough, else the longest pauses nearest to equal parts"""
    starts = [s["start"] for s in sh["shots"][1:]]
    if len(starts) == n - 1:
        return starts
    ls = sorted(lines.values(), key=lambda l: l["start"])
    gaps = [((a["end"] + b["start"]) / 2, b["start"] - a["end"]) for a, b in zip(ls, ls[1:])]
    out = []
    for k in range(1, n):
        target = k * total / n
        best = max((g for g in gaps if g[0] not in out), key=lambda g: g[1] - 0.25 * abs(g[0] - target))
        out.append(best[0])
    return sorted(out)


def plan(name, shots_resolved, edit=None):
    """resolve edit.json into concrete cuts: {cut: {aspect, segments: [{film, t0, t1, snapped}], length}}"""
    d = FILMS / name
    edit = edit or json.loads((d / "edit.json").read_text())
    tm = json.loads((d / "timing.json").read_text()); lines = {l["id"]: l for l in tm.get("lines", [])}
    g = grid(d); total = shots_resolved["shots"][-1]["end"]
    cache = {name: (lines, g, total)}

    def ctx(film):
        if film not in cache:
            fd = FILMS / film
            t2 = json.loads((fd / "timing.json").read_text()); g2 = grid(fd)
            cache[film] = ({l["id"]: l for l in t2.get("lines", [])}, g2, g2["total"])
        return cache[film]

    def seg(film, a, b):
        L, G, T = ctx(film)
        t0, k0 = snap(_time(a, L, G), "start", L, G, T)
        t1, k1 = snap(_time(b, L, G), "end", L, G, T)
        if t1 <= t0:
            raise ValueError(f"empty range {a}..{b} in {film}")
        return {"film": film, "t0": round(t0, 4), "t1": round(t1, 4), "snapped": [k0, k1],
                "lines": [l["id"] for l in L.values() if l["start"] >= t0 - 0.01 and l["end"] <= t1 + 0.01]}

    out = {}
    for cid, c in (edit.get("cuts") or {}).items():
        aspect = c.get("aspect", "")
        if c.get("split"):
            pts = [0.0] + _split_points(int(c["split"]), shots_resolved, lines, total) + [total]
            for i in range(len(pts) - 1):
                s = seg(name, pts[i], pts[i + 1])
                out[f"{cid}{i + 1}"] = {"aspect": aspect, "segments": [s], "length": round(s["t1"] - s["t0"], 3), "part": [i + 1, len(pts) - 1]}
            continue
        rs = c.get("ranges", "all")
        segs = [seg(name, 0.0, total)] if rs == "all" else [
            seg(r["film"], r["from"], r["to"]) if isinstance(r, dict) else seg(name, r[0], r[1]) for r in rs]
        out[cid] = {"aspect": aspect, "segments": segs, "length": round(sum(s["t1"] - s["t0"] for s in segs), 3)}
    return out


def otio(cut_id, cut, fps, media):
    """OpenTimelineIO JSON (Timeline.1) for a cut: one video and one audio track of clips from the master renders"""
    def rt(v):
        return {"OTIO_SCHEMA": "RationalTime.1", "rate": fps, "value": round(v * fps)}

    def clip(s, kind):
        return {"OTIO_SCHEMA": "Clip.2", "name": f"{s['film']} {s['t0']:.2f}-{s['t1']:.2f}", "metadata": {"doodleberry": {"lines": s["lines"], "snapped": s["snapped"]}},
                "source_range": {"OTIO_SCHEMA": "TimeRange.1", "start_time": rt(s["t0"]), "duration": rt(s["t1"] - s["t0"])},
                "media_references": {"DEFAULT_MEDIA": {"OTIO_SCHEMA": "ExternalReference.1", "target_url": media[s["film"]]}},
                "active_media_reference_key": "DEFAULT_MEDIA", "effects": [], "markers": [], "enabled": True}
    tracks = [{"OTIO_SCHEMA": "Track.1", "name": k, "kind": k, "children": [clip(s, k) for s in cut["segments"]], "effects": [], "markers": [], "enabled": True, "metadata": {}}
              for k in ("Video", "Audio")]
    return {"OTIO_SCHEMA": "Timeline.1", "name": cut_id, "metadata": {"doodleberry": {"aspect": cut["aspect"]}}, "global_start_time": None,
            "tracks": {"OTIO_SCHEMA": "Stack.1", "name": "tracks", "children": tracks, "effects": [], "markers": [], "enabled": True, "metadata": {}}}


def srt(cut, timings):
    """sidecar captions on the cut's clock, one cue per line"""
    def ts(t):
        ms = int(round(t * 1000)); return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    out, off, n = [], 0.0, 0
    for s in cut["segments"]:
        for l in timings[s["film"]]:
            if l["start"] >= s["t0"] - 0.01 and l["end"] <= s["t1"] + 0.01:
                n += 1; out.append(f"{n}\n{ts(l['start'] - s['t0'] + off)} --> {ts(l['end'] - s['t0'] + off)}\n{l['text']}\n")
        off += s["t1"] - s["t0"]
    return "\n".join(out)
