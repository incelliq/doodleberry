"""Research and safety gates (plan 0.10) and the critic ledger (plan 0.12).

The engine cannot judge truth, but it can enforce the process from the film playbook:
- every fact has a source and a trace excerpt; numbers have two independent sources (or a recorded reason);
- research_log.md records searches, sources read with verdicts, what was rejected, open questions and the
  counter-evidence search;
- a fresh fact-check agent's verdict ("cleared") is recorded in the ledger before anything renders;
- a brief marked sensitive (shots.json brief.sensitive = true) needs a recorded safety clearance;
- critic rounds (sound-off reader, fact checker, director) are logged with before/after QA numbers.

facts.json: {"sources": {key: {"url"|"title"...}}, "facts": [{"id", "claim", "src", "srcs": [more keys],
"source_sentence" | "excerpt", "label": "re-analysis"|"illustration"|"preliminary", "single_source_reason"}]}
"""
import datetime
import json
import re
from pathlib import Path
from urllib.parse import urlparse

LOG_SECTIONS = ["Searches", "Sources", "Rejected", "Open questions", "Counter-evidence"]


def _j(p, default=None):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else default


def _domain(src):
    if isinstance(src, dict):
        src = src.get("url") or src.get("doi") or src.get("title") or ""
    s = str(src)
    host = urlparse(s).netloc if "://" in s else s.split("/")[0]
    return host.lower().removeprefix("www.") or s[:40]


def check(film_dir):
    """-> {"errors", "warnings", "gate": {...}} for a film's research records"""
    d = Path(film_dir)
    facts_doc = _j(d / "facts.json", {"facts": []})
    facts = facts_doc.get("facts", [])
    sources = facts_doc.get("sources", {})
    errs, warns = [], []
    for f in facts:
        fid = f.get("id", "?")
        keys = [k for k in [f.get("src"), *(f.get("srcs") or [])] if k]
        if not keys and not f.get("source"):
            errs.append(f"fact {fid}: no source")
        if not (f.get("source_sentence") or f.get("excerpt")):
            warns.append(f"fact {fid}: no trace excerpt (source_sentence)")
        if re.search(r"\d", f.get("claim", "")) and f.get("kind") != "date":
            doms = {_domain(sources.get(k, k)) for k in keys} | ({_domain(f["source"])} if f.get("source") else set())
            if len(doms) < 2 and not f.get("single_source_reason"):
                warns.append(f"fact {fid}: a number with one independent source; add a second (srcs) or a single_source_reason")
    log = (d / "research_log.md").read_text() if (d / "research_log.md").exists() else ""
    missing = [s for s in LOG_SECTIONS if not re.search(rf"^#+\s*{re.escape(s)}", log, re.M | re.I)]
    if facts and not log:
        errs.append("research_log.md is missing")
    elif facts and missing:
        warns.append(f"research_log.md lacks sections: {', '.join(missing)}")
    led = ledger(d)
    gate = next((e for e in reversed(led) if e["role"] == "fact_gate"), None)
    cleared = bool(gate and gate["verdict"] == "cleared")
    if facts and not cleared:
        errs.append("no fact-check clearance: a fresh fact_gate reviewer must record verdict 'cleared' (ledger.add)")
    shots = _j(d / "shots.json", {}) or {}
    review = review_level(d, shots)
    expert = None
    if review["level"] == "expert":   # WP-05: health, legal and finance claims get an expert reviewer
        for f in facts:
            if not f.get("omits"):
                errs.append(f"fact {f.get('id', '?')}: an expert-review film records what the source leaves out (omits), e.g. first-line treatments, or 'nothing material'")
        ex = next((e for e in reversed(led) if e["role"] == "expert_review"), None)
        expert = "cleared" if ex and ex["verdict"] == "cleared" else "pending"
        if expert == "pending":
            warns.append(f"expert review pending ({review['why']}): a qualified reviewer records ledger.add role expert_review verdict cleared before the film is approved")
    cited = {fid for ln in (_j(d / "script.json", {}) or {}).get("lines", []) for fid in ([ln.get("fact")] if isinstance(ln.get("fact"), str) else (ln.get("fact") or []))}
    for f in facts:
        if f.get("label") and f.get("label") not in LABELS:
            errs.append(f"fact {f.get('id', '?')}: label must be one of {', '.join(LABELS)}")
        elif f.get("label") and f.get("id") not in cited:
            warns.append(f"fact {f.get('id', '?')} is labelled {f['label']!r} but no line cites it, so the label never shows")
    if (shots.get("brief") or {}).get("sensitive"):
        safe = next((e for e in reversed(led) if e["role"] == "safety"), None)
        if not (safe and safe["verdict"] == "cleared"):
            errs.append("the brief is marked sensitive: a reviewer must record a safety clearance (ledger.add role safety) before production")
    return {"errors": errs, "warnings": warns, "facts": len(facts),
            "gate": {"fact_gate": gate["verdict"] if gate else None, "log_sections_missing": missing if facts else [],
                     "review": review["level"], **({"expert_review": expert, "review_why": review["why"]} if expert else {})}}


LABELS = ("re-analysis", "illustration", "preliminary")


def review_level(d, shots=None):
    """standard or expert: shots.json brief.review, or the brief.md table row "| review | expert (...) |" """
    shots = shots if shots is not None else (_j(Path(d) / "shots.json", {}) or {})
    lvl = (shots.get("brief") or {}).get("review")
    why = (shots.get("brief") or {}).get("review_why", "")
    if not lvl and (Path(d) / "brief.md").exists():
        m = re.search(r"^\|\s*review\s*\|\s*(standard|expert)\b\s*(?:\(([^)]*)\))?", (Path(d) / "brief.md").read_text(), re.M | re.I)
        if m:
            lvl, why = m.group(1).lower(), m.group(2) or ""
    return {"level": lvl or "standard", "why": why}


def labels_for(d, timing_lines):
    """[(start, end, label)] for every timed line that cites a labelled fact (honest on-screen labels)"""
    facts = {f.get("id"): f for f in (_j(Path(d) / "facts.json", {"facts": []}) or {}).get("facts", [])}
    script = {ln.get("id"): ln for ln in (_j(Path(d) / "script.json", {}) or {}).get("lines", [])}
    out = []
    for tl in timing_lines:
        ln = script.get(tl.get("id"), {})
        ids = [ln.get("fact")] if isinstance(ln.get("fact"), str) else (ln.get("fact") or [])
        labs = sorted({facts[i]["label"] for i in ids if i in facts and facts[i].get("label") in LABELS})
        if labs:
            out.append((tl["start"], tl["end"], " · ".join(labs)))
    return out


def self_test(tmp):
    """expert-review films: omits required, review pending until cleared; labels must be valid and cited"""
    import shutil
    fails, got = [], {}
    d = Path(tmp) / "expert_case"; shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
    (d / "brief.md").write_text("| field | value |\n|---|---|\n| review    | expert (health: life & health) |\n")
    (d / "facts.json").write_text(json.dumps({"sources": {"a": {"url": "https://example.invalid/a"}, "b": {"url": "https://example.org/b"}},
        "facts": [{"id": "F1", "claim": "TB is curable", "src": "a", "srcs": ["b"], "source_sentence": "x", "label": "preliminary"},
                  {"id": "F2", "claim": "a claim", "src": "a", "source_sentence": "y", "omits": "nothing material", "label": "guess"}]}))
    (d / "script.json").write_text(json.dumps({"lines": [{"id": "l1", "text": "t", "fact": "F1"}]}))
    (d / "research_log.md").write_text("\n".join(f"## {s}" for s in LOG_SECTIONS))
    add(d, "fact_gate", "cleared")
    r = check(d); got["before"] = {"review": r["gate"]["review"], "expert": r["gate"].get("expert_review"), "errors": len(r["errors"])}
    if r["gate"]["review"] != "expert" or r["gate"].get("expert_review") != "pending":
        fails.append(f"expert review not detected: {r['gate']}")
    if not any("F1" in e and "omits" in e for e in r["errors"]) or not any("F2" in e and "label" in e for e in r["errors"]):
        fails.append(f"omits and label checks: {r['errors']}")
    add(d, "expert_review", "cleared", "reviewed by a physician (test)")
    if check(d)["gate"].get("expert_review") != "cleared":
        fails.append("expert review not cleared after the ledger entry")
    lab = labels_for(d, [{"id": "l1", "start": 1.0, "end": 2.5}]); got["labels"] = lab
    if lab != [(1.0, 2.5, "preliminary")]:
        fails.append(f"labels: {lab}")
    from .captions import make_ass
    ass = make_ass({"lines": [{"id": "l1", "start": 1.0, "end": 2.5, "words": [{"text": "TB", "start": 1.0, "end": 1.4}]}]}, [1080, 1920], labels=lab)
    if "Label,,0,0,0,,PRELIMINARY" not in ass or "Style: Label," not in ass:
        fails.append("the label is not in the captions")
    shutil.rmtree(d, ignore_errors=True)
    return fails, got


# ---------------- ledger ----------------
def ledger(d):
    return _j(Path(d) / "ledger.json", [])


def add(d, role, verdict, notes="", metrics=None, round_no=None):
    d = Path(d)
    led = ledger(d)
    rn = round_no if round_no is not None else max([e["round"] for e in led], default=1)  # pass round_no to open a new round
    entry = {"at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "round": rn, "role": role,
             "verdict": verdict, "notes": notes, "metrics": metrics or {}}
    led.append(entry)
    (d / "ledger.json").write_text(json.dumps(led, indent=1))
    _write_md(d, led)
    return entry


def _write_md(d, led):
    out = ["# Ledger", "", "Generated from ledger.json: critic rounds, gates and measured numbers.", ""]
    rounds = sorted({e.get("round", 1) for e in led})   # entries written by hand may lack round, notes or metrics
    prev = {}
    for r in rounds:
        out += [f"## Round {r}", ""]
        for e in [x for x in led if x.get("round", 1) == r]:
            out += [f"- **{e['role']}** ({e.get('at', '')}): {e['verdict']}" + (f". {e['notes']}" if e.get("notes") else "")]
            if e.get("metrics"):
                out += ["", "| metric | before | now |", "|---|---|---|"]
                for k, v in e["metrics"].items():
                    out.append(f"| {k} | {prev.get(k, '–')} | {v} |")
                prev.update(e["metrics"])
                out.append("")
        out.append("")
    (Path(d) / "ledger.md").write_text("\n".join(out))
