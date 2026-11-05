"""Sound sketches (WP-43): a sound effect drawn from a few words, for a cue no synthesised or recorded sound covers.

AudioLDM (cvssp/audioldm-s-full-v2, CC BY-NC-SA 4.0: in-house, flagged at the posting gate) on the CPU makes a
2-3 s clip from a text prompt in about ten seconds (25 denoising steps, seeded: the same prompt and seed give the
same sound); it comes out at 16 kHz and is resampled to the film's 48 kHz, faded at both ends. CLAP
(laion/clap-htsat-unfused, Apache-2.0), an audio-text model trained apart from it, checks a sketch: how near it sits
to its own prompt against other prompts. Models live in the model cache (DBE_MODELS, ~/.cache/doodleberry/models).
"""
import os
from pathlib import Path

import numpy as np

MODELS = Path(os.environ.get("DBE_MODELS", str(Path.home() / ".cache" / "doodleberry" / "models")))
AUDIOLDM = {"repo": "cvssp/audioldm-s-full-v2", "dir": "audioldm-s-full-v2", "license": "CC-BY-NC-SA-4.0", "class": "non-commercial"}
CLAP = {"repo": "laion/clap-htsat-unfused", "dir": "clap-htsat-unfused", "license": "Apache-2.0", "class": "permissive"}
AST = {"repo": "MIT/ast-finetuned-audioset-10-10-0.4593", "dir": "ast-audioset", "license": "BSD-3-Clause", "class": "permissive"}
_P = {}


def _fetch(m, patterns):
    d = MODELS / m["dir"]
    if not (d / "model_index.json").exists() and not (d / "config.json").exists():
        from huggingface_hub import snapshot_download
        snapshot_download(m["repo"], local_dir=str(d), allow_patterns=patterns)
    return d


def pipe():
    if "ldm" not in _P:
        import torch
        from diffusers import AudioLDMPipeline
        _P["ldm"] = AudioLDMPipeline.from_pretrained(str(_fetch(AUDIOLDM, ["*.json", "*.txt", "*.safetensors", "tokenizer/*"])), torch_dtype=torch.float32)
        _P["ldm"].set_progress_bar_config(disable=True)
    return _P["ldm"]


def sketch(prompt, seconds=2.5, seed=0, steps=25, sr=48000, candidates=1):
    """-> float32 mono at sr: the prompt's sound, seeded, faded in 5 ms and out 40 ms. candidates > 1: that many seeds
    (seed, seed+1, ...), the one CLAP finds nearest the prompt kept"""
    if candidates > 1:
        outs = [sketch(prompt, seconds, seed + k, steps, sr) for k in range(candidates)]
        sims = clap_similarity(outs, [prompt])[:, 0]
        return outs[int(np.argmax(sims))]
    import torch
    from scipy.signal import resample_poly
    g = torch.Generator().manual_seed(int(seed))
    a = pipe()(prompt, num_inference_steps=steps, audio_length_in_s=float(seconds), generator=g).audios[0]
    y = resample_poly(np.asarray(a, np.float64), sr // 16000, 1) if sr % 16000 == 0 else resample_poly(a, sr, 16000)
    fi, fo = int(0.005 * sr), int(0.04 * sr)
    y[:fi] *= np.linspace(0, 1, fi); y[-fo:] *= np.linspace(1, 0, fo)
    return y.astype(np.float32)


def clap_similarity(audios, prompts, sr=48000):
    """cosine similarities [audio][prompt] by CLAP (audio at 48 kHz, as CLAP takes it)"""
    import torch
    from transformers import ClapModel, ClapProcessor
    if "clap" not in _P:
        d = _fetch(CLAP, ["*.json", "*.txt", "*.bin"])
        _P["clap"] = (ClapModel.from_pretrained(str(d)).eval(), ClapProcessor.from_pretrained(str(d)))
    model, proc = _P["clap"]
    with torch.no_grad():
        ti = proc(text=list(prompts), return_tensors="pt", padding=True)
        te = model.get_text_features(**ti)
        ai = proc(audio=[np.asarray(a, np.float32) for a in audios], sampling_rate=sr, return_tensors="pt")
        ae = model.get_audio_features(**ai)
    te = getattr(te, "pooler_output", te); ae = getattr(ae, "pooler_output", ae)
    te = te / te.norm(dim=-1, keepdim=True); ae = ae / ae.norm(dim=-1, keepdim=True)
    return (ae @ te.T).numpy()


def tags(audios, sr=48000, top=5):
    """AudioSet labels by AST (an audio tagger trained apart from both): [[(label, p), ...] per audio]"""
    import torch
    from scipy.signal import resample_poly
    from transformers import ASTFeatureExtractor, ASTForAudioClassification
    if "ast" not in _P:
        d = _fetch(AST, ["*.json", "*.safetensors"])
        _P["ast"] = (ASTForAudioClassification.from_pretrained(str(d)).eval(), ASTFeatureExtractor.from_pretrained(str(d)))
    model, fe = _P["ast"]; out = []
    for a in audios:
        x = resample_poly(np.asarray(a, np.float64), 1, sr // 16000).astype(np.float32)
        with torch.no_grad():
            pr = torch.sigmoid(model(**fe(x, sampling_rate=16000, return_tensors="pt")).logits[0]).numpy()
        idx = np.argsort(-pr)[:top]
        out.append([(model.config.id2label[int(i)], round(float(pr[i]), 3)) for i in idx])
    return out
