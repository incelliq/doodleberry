"""One line in a clean Kokoro voice -> a WAV and its lip-sync cues, for quick previews (plan 3.6: a new doodle says
its first line). Runs as its own process, like the voice build, because the phonemizer pulls in espeak-ng (GPL).

    python engine/say_line.py "Hi, I'm Nib!" kokoro:af_heart OUT.wav VOICES_DIR
    -> prints {"duration": s, "visemes": [[t, shape], ...], "timed": true}

Cues come from the model's own phoneme timings (plan 2.1), so the mouth matches the audio exactly; leading and
trailing silence is trimmed and the cues moved with it.
"""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import kokoro_voice as K  # noqa: E402
import visemes as V  # noqa: E402


def say(text, voice, out, voices_dir):
    kv = K.KokoroVoice(voice, voices_dir)
    a, sr = kv.synth(text)
    loud = np.nonzero(np.abs(a) > 0.01)[0]
    cut0 = max(0, int(loud[0]) - int(0.03 * sr)) if len(loud) else 0
    cut1 = min(len(a), int(loud[-1]) + int(0.08 * sr)) if len(loud) else len(a)
    a = a[cut0:cut1]
    phones = [(p, s - cut0 / sr, e - cut0 / sr) for p, s, e in (kv.last_phones or [])]
    cues = [[max(0.0, round(t, 3)), sh] for t, sh in V.phone_visemes(phones)] if phones else []
    peak = float(np.max(np.abs(a))) or 1.0
    sf.write(out, (a * (0.89 / peak)).astype(np.float32), sr)
    return {"duration": round(len(a) / sr, 3), "visemes": cues, "timed": bool(phones), "sample_rate": sr}


if __name__ == "__main__":
    text, voice, out, vdir = sys.argv[1:5]
    print(json.dumps(say(text, voice, out, vdir)))
