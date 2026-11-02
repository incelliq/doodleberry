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


# ---------- phone-level (plan 2.1): the TTS model's own phoneme durations ----------
PAUSE_MARKS = set(".,!?;:—…")


def phone_visemes(phones, t0=0.0, rest_gap=0.12):
    """phones: [(phoneme, start, end)] from the voice model (seconds, line-relative) -> [[t, shape], ...] on the film
    clock (t0 = line start). Stress and length marks extend the phone before them; spaces join words; a pause mark
    longer than rest_gap closes the mouth. Exact by construction for synthesised lines (25 ms model frames)."""
    cues = []
    glued = []
    for ph, s, e in phones:
        if ph in STRIP and ph != " ":
            if glued:
                glued[-1][2] = e
            continue
        if ph == " ":
            continue
        if glued and glued[-1][0] + ph in WIDE:  # diphthongs like a+ɪ
            glued[-1][0] += ph; glued[-1][2] = e; continue
        glued.append([ph, s, e])
    prev_end = None
    for ph, s, e in glued:
        if prev_end is not None and s - prev_end > 0.07 and (not cues or cues[-1][1] != "closed"):
            cues.append([round(t0 + prev_end + 0.02, 3), "closed"])   # silence between phones (inserted pauses)
        if ph in PAUSE_MARKS:
            sh = "closed" if e - s >= rest_gap else None
        else:
            sh = shape_of(ph)
        if sh and (not cues or cues[-1][1] != sh):
            cues.append([round(t0 + s, 3), sh])
        if ph not in PAUSE_MARKS:
            prev_end = e
    if glued:
        cues.append([round(t0 + max(e for _, _, e in glued) + 0.03, 3), "closed"])
    return cues


def phone_words(phones, script_words, phonemize=None):
    """word timings from the phone timeline. Phones between spaces and pause marks form a spoken word, mapped onto
    the script's words in order. When the counts disagree (espeak runs "for a" together, reads "25" as two words),
    each script word gets its share of the phone stream by its own phoneme count (phonemize(word)), and each
    boundary moves to a space when one is within two phones. Returns None only without phones."""
    spans, cur = [], None
    for ph, s, e in phones:
        if ph == " " or ph in PAUSE_MARKS:
            if cur:
                spans.append(cur); cur = None
            continue
        if ph in STRIP:
            if cur:
                cur[1] = e
            continue
        cur = [s, e] if cur is None else [cur[0], e]
    if cur:
        spans.append(cur)
    if len(spans) == len(script_words):
        return [{"text": w, "start": round(a, 3), "end": round(b, 3)} for w, (a, b) in zip(script_words, spans)]
    if not spans:
        return None

    def count(w):
        try:
            if phonemize:
                return max(1, len([p for sent in phonemize(w) for p in sent if p not in STRIP and p not in PAUSE_MARKS]))
        except Exception:
            pass
        return max(1, len(re.sub(r"\W", "", w)))
    wc = [count(w) for w in script_words]
    # sounding phones per spoken span, with their times
    sp_ph, cur = [], None
    for ph, s, e in phones:
        if ph == " " or ph in PAUSE_MARKS:
            if cur:
                sp_ph.append(cur); cur = None
            continue
        if ph in STRIP:
            if cur:
                cur[-1][2] = e
            continue
        (cur := cur or []).append([ph, s, e])
    if cur:
        sp_ph.append(cur)
    # DP: group script words and spoken spans (1 span : 1-3 words, or 2-3 spans : 1 word), closest phone counts
    W, S_ = len(wc), len(sp_ph); INF = 1e9
    best = [[INF] * (S_ + 1) for _ in range(W + 1)]; back = [[None] * (S_ + 1) for _ in range(W + 1)]
    best[0][0] = 0
    for i in range(W + 1):
        for j in range(S_ + 1):
            if best[i][j] >= INF:
                continue
            for dw, ds in ((1, 1), (2, 1), (3, 1), (1, 2), (1, 3)):
                if i + dw <= W and j + ds <= S_:
                    c = best[i][j] + abs(sum(wc[i:i + dw]) - sum(len(x) for x in sp_ph[j:j + ds])) + 0.5 * (dw + ds - 2)
                    if c < best[i + dw][j + ds]:
                        best[i + dw][j + ds] = c; back[i + dw][j + ds] = (dw, ds)
    if best[W][S_] >= INF:
        return None
    groups, i, j = [], W, S_
    while i or j:
        dw, ds = back[i][j]; groups.append((i - dw, i, j - ds, j)); i -= dw; j -= ds
    out = []
    for w0, w1, s0, s1 in reversed(groups):
        seq = [p for x in sp_ph[s0:s1] for p in x]
        if w1 - w0 == 1:
            out.append({"text": script_words[w0], "start": round(seq[0][1], 3), "end": round(seq[-1][2], 3)}); continue
        tot, acc, k0 = sum(wc[w0:w1]), 0, 0
        for w in range(w0, w1):  # run-together words: split the span by each word's phoneme count
            acc += wc[w]; k1 = len(seq) if w == w1 - 1 else min(len(seq) - (w1 - 1 - w), max(k0 + 1, round(len(seq) * acc / tot)))
            out.append({"text": script_words[w], "start": round(seq[k0][1], 3), "end": round(seq[k1 - 1][2], 3)}); k0 = k1
    return out

