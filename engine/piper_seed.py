"""Piper voices made deterministic.

Piper's model draws its noise (prosody and duration variation) from two RandomNormalLike nodes with no seed, so the
same line came out a different length each time (24,832 to 26,368 samples over three runs of one Sinhala line), and
with it a film's line times, Whisper's words, caption chunks and the frames checks read. Here the model's random nodes
get a fixed seed and the voice a session built from that model: a fresh voice then reads the same lines, in the same
order, identically (a session continues its random sequence from call to call, so it is the order that repeats).
"""
from pathlib import Path


def seeded(voice, model_path, include_alignments=False, seed=1234):
    """replace a loaded PiperVoice's session with one whose noise is seeded; the voice is returned unchanged if onnx
    is not installed"""
    try:
        import onnx
        import onnxruntime as ort
    except ImportError:
        return voice
    m = onnx.load(str(Path(model_path)))
    if include_alignments:
        try:
            from piper.patch_voice_with_alignment import add_alignment_output
            add_alignment_output(m)
        except (ImportError, ValueError):
            pass
    for n in m.graph.node:
        if n.op_type in ("RandomNormalLike", "RandomNormal", "RandomUniformLike", "RandomUniform"):
            keep = [a for a in n.attribute if a.name != "seed"]
            del n.attribute[:]; n.attribute.extend(keep + [onnx.helper.make_attribute("seed", float(seed))])
    voice.session = ort.InferenceSession(m.SerializeToString(), sess_options=ort.SessionOptions(), providers=["CPUExecutionProvider"])
    return voice
