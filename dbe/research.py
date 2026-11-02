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
    if (shots.get("brief") or {}).get("sensitive"):
        safe = next((e for e in reversed(led) if e["role"] == "safety"), None)
        if not (safe and safe["verdict"] == "cleared"):
            errs.append("the brief is marked sensitive: a reviewer must record a safety clearance (ledger.add role safety) before production")
    return {"errors": errs, "warnings": warns, "facts": len(facts),
            "gate": {"fact_gate": gate["verdict"] if gate else None, "log_sections_missing": missing if facts else []}}


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
