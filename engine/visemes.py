"""Sound-based lip-sync: turn word timings into mouth shapes (visemes).

Each word is phonemised with Piper's espeak-ng phonemiser (the same one that voiced it), its phonemes are spread
across the word's measured duration (vowels weighted double), and each phoneme maps to a mouth shape in the puppet
mouth chart: closed (M B P), FV, O (rounded), wide (open vowels), mid, smile (EE), small (other consonants).

    from visemes import line_visemes
    cues = line_visemes(voice, words)   # words: [{text, start, end}] -> [[t, shape], ...]
"""
import re

CLOSED = set("mbp") | {"β"}  # β: Spanish soft b, lips nearly closed
FV = set("fv") | {"ɸ"}
ROUND = {"o", "ɔ", "u", "ʊ", "w", "ɒ"}
WIDE = {"a", "ɑ", "æ", "ʌ", "ɐ", "aɪ", "aʊ"}
MID = {"e", "ɛ", "ə", "ɚ", "ɜ", "ɝ", "œ"}
SMILE = {"i", "ɪ", "j", "y"}
VOWELS = ROUND | WIDE | MID | SMILE
STRIP = {"ˈ", "ˌ", "ː", "ˑ", " ", "-", "'"}


def shape_of(ph):
    if ph in CLOSED:
        return "closed"
    if ph in FV:
        return "FV"
    if ph in ROUND:
        return "O"
    if ph in WIDE:
        return "wide"
    if ph in MID:
        return "mid"
    if ph in SMILE:
        return "smile"
    return "small"


def phonemes(voice, word):
    w = re.sub(r"[^\w'\-]", "", word).replace("_", "")
    if not w:
        return []
    try:
        raw = [p for sent in voice.phonemize(w) for p in sent]
    except Exception:
        return []
    out = []
    for p in raw:
        if p in STRIP:
            continue
        if out and out[-1] + p in WIDE:  # glue diphthongs like a+ɪ
            out[-1] = out[-1] + p
            continue
        out.append(p)
    return out


def line_visemes(voice, words, rest_gap=0.12):
    """words: [{text, start, end}] in seconds -> [[t, shape], ...] including closed rests in gaps."""
    cues = []
    prev_end = None
    for w in words:
        s, e = float(w["start"]), float(w["end"])
        if prev_end is not None and s - prev_end > rest_gap:
            cues.append([round(prev_end + 0.03, 3), "closed"])
        phs = phonemes(voice, w["text"]) or ["ə"]
        weights = [2.0 if p in VOWELS or p[:1] in "aeiouɑɔəɛɪʊ" else 1.0 for p in phs]
        tot = sum(weights)
        t = s
        for p, wt in zip(phs, weights):
            sh = shape_of(p)
            if not cues or cues[-1][1] != sh:
                cues.append([round(t, 3), sh])
            t += (e - s) * wt / tot
        prev_end = e
    if prev_end is not None:
        cues.append([round(prev_end + 0.03, 3), "closed"])
    return cues


def shape_at(cues, t):
    """mouth shape at time t from a sorted cue list (closed before the first cue)."""
    sh = "closed"
    for ct, s in cues:
        if ct > t:
            break
        sh = s
    return sh
