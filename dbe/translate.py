"""Machine-translation drafts (WP-25): a film's strings drafted in another language by NLLB-200 (Meta's distilled
600M model, run by CTranslate2 on the CPU), for a person to review before the version is made.

The model is Meta's own checkpoint (facebook/nllb-200-distilled-600M), converted here with CTranslate2's converter
to int8 (`model()` does it once into the models folder). Its licence is CC BY-NC 4.0: fine in-house; a version made
from machine strings records the model in its provenance.json, so the posting gate flags it for the owner.

Data bindings survive: each {{...}} is replaced by a distinct number before translation (NLLB carries numbers
through) and put back after; a string whose numbers do not all come back is left empty and listed, never guessed.
The i18n file records which strings are machine drafts (`machine.keys`); a person marks them checked by listing
them in `reviewed` (or by editing them: an edited string is no longer the draft).
"""
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

MODELS = Path(os.environ.get("DBE_MODELS", str(Path.home() / ".cache" / "doodleberry" / "models")))
SRC = MODELS / "nllb-200-distilled-600M"
CT2 = MODELS / "nllb-200-distilled-600M-ct2-int8"
NAME = "NLLB-200 distilled 600M (Meta), CTranslate2 int8"
LICENSE = "CC-BY-NC-4.0"
FILES = ["config.json", "generation_config.json", "pytorch_model.bin", "sentencepiece.bpe.model", "special_tokens_map.json", "tokenizer.json", "tokenizer_config.json"]

# language tags -> NLLB's codes (FLORES-200)
CODES = {"en": "eng_Latn", "es": "spa_Latn", "fr": "fra_Latn", "de": "deu_Latn", "pt": "por_Latn", "it": "ita_Latn", "nl": "nld_Latn",
         "ar": "arb_Arab", "he": "heb_Hebr", "fa": "pes_Arab", "ur": "urd_Arab", "hi": "hin_Deva", "bn": "ben_Beng", "mr": "mar_Deva",
         "ta": "tam_Taml", "te": "tel_Telu", "kn": "kan_Knda", "ml": "mal_Mlym", "gu": "guj_Gujr", "pa": "pan_Guru", "si": "sin_Sinh",
         "ne": "npi_Deva", "zh": "zho_Hans", "ja": "jpn_Jpan", "ko": "kor_Hang", "th": "tha_Thai", "vi": "vie_Latn", "id": "ind_Latn",
         "ms": "zsm_Latn", "fil": "tgl_Latn", "my": "mya_Mymr", "ru": "rus_Cyrl", "uk": "ukr_Cyrl", "pl": "pol_Latn", "tr": "tur_Latn",
         "el": "ell_Grek", "sw": "swh_Latn", "ha": "hau_Latn", "yo": "yor_Latn", "am": "amh_Ethi"}
_TPL = re.compile(r"\{\{[^}]+\}\}")


def model():
    """the converted model's folder (downloads and converts once)"""
    if (CT2 / "model.bin").exists():
        return CT2
    SRC.mkdir(parents=True, exist_ok=True)
    import urllib.request
    for f in FILES:
        if not (SRC / f).exists():
            urllib.request.urlretrieve(f"https://huggingface.co/facebook/nllb-200-distilled-600M/resolve/main/{f}", SRC / f)
    subprocess.run([sys.executable, "-m", "ctranslate2.converters.transformers", "--model", str(SRC), "--output_dir", str(CT2), "--quantization", "int8",
                    "--copy_files", "sentencepiece.bpe.model", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"], check=True, capture_output=True)
    return CT2


def code(lang):
    base = lang.split("-")[0]
    if base not in CODES:
        raise ValueError(f"no NLLB code for {lang!r} here (have {', '.join(sorted(CODES))})")
    return CODES[base]


def translate(texts, lang, src="en", beam=4):
    """[text] -> [(translation or None, why)]"""
    import ctranslate2
    import sentencepiece as spm
    m = model(); sp = spm.SentencePieceProcessor(model_file=str(m / "sentencepiece.bpe.model"))
    tr = ctranslate2.Translator(str(m), device="cpu", compute_type="int8", inter_threads=1, intra_threads=max(1, (os.cpu_count() or 2) - 1))
    s_code, t_code = code(src), code(lang)
    masked, maps = [], []
    for i, t in enumerate(texts):
        mp = {}
        def sub(mo):
            tok = str(9101 + 7 * len(mp))   # distinct, unlikely numbers
            mp[tok] = mo.group(0); return tok
        masked.append(_TPL.sub(sub, t)); maps.append(mp)
    toks = [[s_code] + sp.encode(t, out_type=str) + ["</s>"] for t in masked]
    res = tr.translate_batch(toks, target_prefix=[[t_code]] * len(toks), beam_size=beam, max_decoding_length=256)
    out = []
    for r, mp, orig in zip(res, maps, texts):
        hyp = r.hypotheses[0]
        hyp = hyp[1:] if hyp and hyp[0] == t_code else hyp
        text = sp.decode(hyp).strip()
        lost = [tok for tok in mp if tok not in text]
        if lost:
            out.append((None, f"the model dropped a data binding ({', '.join(mp[t] for t in lost)}): translate this one by hand")); continue
        for tok, ph in mp.items():
            text = text.replace(tok, ph)
        if t_code == "sin_Sinh" and re.search(r"\u0DCA (?=[\u0DBB\u0DBA])", text):
            # NLLB learnt Sinhala with the zero-width joiner stripped: a rakaransaya or yansaya comes out as a hal kirima, a
            # space and ra or ya ("රාත් රී" for "රාත්‍රී"), which looks exactly like a word ending before a word starting with
            # ra or ya ("කින් රාත්‍රී"); it cannot be told apart from the text, so the reviewer is told where to look
            out.append((text, "machine draft; check the conjuncts: a hal kirima before a space and ra or ya may need to be joined (ZWJ)")); continue
        out.append((text, "machine draft"))
    return out


def draft(i18n_path, source, lang, refresh=False):
    """fill the empty strings of an i18n file with machine drafts; -> report"""
    p = Path(i18n_path)
    spec = json.loads(p.read_text()) if p.exists() else {"lang": lang, "source": {}, "strings": {}, "voices": {}, "swaps": {}}
    spec.setdefault("source", {}).update(source); strings = spec.setdefault("strings", {})
    mach = spec.setdefault("machine", {"model": NAME, "license": LICENSE, "keys": []})
    prev = set(mach.get("keys") or [])
    todo = [k for k in source if not strings.get(k) or (refresh and k in prev and k not in (spec.get("reviewed") or []))]
    res = translate([source[k] for k in todo], lang) if todo else []
    filled, failed = [], []
    notes = {}
    for k, (t, why) in zip(todo, res):
        if t is None:
            strings[k] = ""; failed.append({"key": k, "why": why})
        else:
            strings[k] = t; filled.append(k)
            if why != "machine draft":
                notes[k] = why
    mach.update({"model": NAME, "license": LICENSE, "at": datetime.date.today().isoformat(), "keys": sorted((prev | set(filled)) - {f["key"] for f in failed}),
                 "drafts": {k: strings[k] for k in filled} | {k: v for k, v in (mach.get("drafts") or {}).items() if k not in filled},
                 "notes": notes | {k: v for k, v in (mach.get("notes") or {}).items() if k not in filled}})
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(spec, indent=1, ensure_ascii=False))
    return {"file": str(p), "drafted": len(filled), "failed": failed, "notes": notes, "kept": len([k for k in source if k not in todo])}


def unreviewed(spec):
    """machine strings still as drafted and not marked reviewed"""
    m = spec.get("machine") or {}; rev = set(spec.get("reviewed") or []); dr = m.get("drafts") or {}
    return [k for k in m.get("keys") or [] if k not in rev and (spec.get("strings") or {}).get(k) == dr.get(k)]
