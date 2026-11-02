"""Kokoro-82M as a second TTS backend (Apache-2.0 weights and code; https://huggingface.co/hexgrad/Kokoro-82M).

Voice ids look like "kokoro:af_heart". The first letter of the voice name is its language (a: US English,
b: UK English, e: Spanish, f: French, h: Hindi, i: Italian, j: Japanese, p: Brazilian Portuguese, z: Mandarin).
Model files live in <voices_dir>/kokoro/ (kokoro-v1.0.onnx, voices-v1.0.bin from the kokoro-onnx releases).
Phonemes come from the same espeak-based tokenizer that voices the line, so visemes match the audio.
"""
from pathlib import Path

import numpy as np

LANG = {"a": "en-us", "b": "en-gb", "e": "es", "f": "fr-fr", "h": "hi", "i": "it", "j": "ja", "p": "pt-br", "z": "cmn"}
WHISPER = {"a": "en", "b": "en", "e": "es", "f": "fr", "h": "hi", "i": "it", "j": "ja", "p": "pt", "z": "zh"}
_MODEL = {}
PHONE_LEAD = 0.08   # seconds; see KokoroVoice.synth


def is_kokoro(voice_id):
    return str(voice_id).startswith("kokoro:")


def whisper_lang(voice_id):
    return WHISPER.get(voice_id.split(":", 1)[1][:1], "en")


def timed_model(d):
    """kokoro-v1.0-timed.onnx: the same model with its duration predictor's output (frames per phoneme token, after
    rounding and clipping) exposed as a second output named "duration", which kokoro-onnx turns into phoneme timings
    (plan 2.1). Made once from kokoro-v1.0.onnx with the onnx package; returns None if that is not installed."""
    src, dst = d / "kokoro-v1.0.onnx", d / "kokoro-v1.0-timed.onnx"
    if dst.exists():
        return dst
    try:
        import onnx
        from onnx import helper, TensorProto
    except ImportError:
        return None
    m = onnx.load(str(src))
    if not any("/encoder/Cast_output_0" in n.output for n in m.graph.node):
        return None
    m.graph.node.append(helper.make_node("Identity", ["/encoder/Cast_output_0"], ["duration"], name="expose_duration"))
    m.graph.output.append(helper.make_tensor_value_info("duration", TensorProto.INT64, None))
    onnx.save(m, str(dst))
    return dst


class KokoroVoice:
    def __init__(self, voice_id, voices_dir):
        from kokoro_onnx import Kokoro
        d = Path(voices_dir) / "kokoro"
        key = str(d)
        if key not in _MODEL:
            tm = timed_model(d)
            _MODEL[key] = Kokoro(str(tm or d / "kokoro-v1.0.onnx"), str(d / "voices-v1.0.bin"))
        self.k = _MODEL[key]
        self.name = voice_id.split(":", 1)[1]
        self.lang = LANG.get(self.name[:1], "en-us")
        if self.name not in self.k.get_voices():
            raise ValueError(f"unknown Kokoro voice {self.name}")

    def synth(self, text, length_scale=1.0):
        """audio and sample rate; self.last_phones holds [(phoneme, start_s, end_s)] for it when the model is timed"""
        speed = 1.0 / max(0.5, min(2.0, length_scale))
        if getattr(self.k, "has_timings", False):
            audio, sr, spoken = self.k.create_timed(text, voice=self.name, speed=speed, lang=self.lang)
            # kokoro-onnx places phones about 80 ms after they sound (measured over 5 voices x 21 lines against the
            # first-formant energy of the audio: median lag 75-100 ms; first phone 25-50 ms after the onset), so
            # shift them back by that calibration (plan 2.1)
            self.last_phones = [(t.phoneme, max(0.0, float(t.start) - PHONE_LEAD), max(0.0, float(t.end) - PHONE_LEAD)) for t in spoken]
        else:
            audio, sr = self.k.create(text, voice=self.name, speed=speed, lang=self.lang)
            self.last_phones = None
        return np.asarray(audio, np.float32), sr

    def phonemize(self, word):
        """same shape as PiperVoice.phonemize: [[phoneme, ...]] per sentence"""
        ipa = self.k.tokenizer.phonemize(word, self.lang)
        return [[c for c in ipa if not c.isspace()]]
