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


def is_kokoro(voice_id):
    return str(voice_id).startswith("kokoro:")


def whisper_lang(voice_id):
    return WHISPER.get(voice_id.split(":", 1)[1][:1], "en")


class KokoroVoice:
    def __init__(self, voice_id, voices_dir):
        from kokoro_onnx import Kokoro
        d = Path(voices_dir) / "kokoro"
        key = str(d)
        if key not in _MODEL:
            _MODEL[key] = Kokoro(str(d / "kokoro-v1.0.onnx"), str(d / "voices-v1.0.bin"))
        self.k = _MODEL[key]
        self.name = voice_id.split(":", 1)[1]
        self.lang = LANG.get(self.name[:1], "en-us")
        if self.name not in self.k.get_voices():
            raise ValueError(f"unknown Kokoro voice {self.name}")

    def synth(self, text, length_scale=1.0):
        audio, sr = self.k.create(text, voice=self.name, speed=1.0 / max(0.5, min(2.0, length_scale)), lang=self.lang)
        return np.asarray(audio, np.float32), sr

    def phonemize(self, word):
        """same shape as PiperVoice.phonemize: [[phoneme, ...]] per sentence"""
        ipa = self.k.tokenizer.phonemize(word, self.lang)
        return [[c for c in ipa if not c.isspace()]]
