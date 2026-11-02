"""Parity matrix (WP-41): what the professional 2D+ tools can do, chapter by chapter, and where Doodleberry stands.

parity/<tool>.json holds one tool's inventory, written by research agents from the tool's manual and release notes:
every chapter of the manual, each capability in our own words with how professionals use it, and our match:

    command          an existing command does it (ref: command names)
    data             a field of the film or puppet data does it (ref: the field)
    metric           a QA measure covers it
    partial          partly there (ref: the commands and the WP that finishes it)
    gap              missing (ref: the WP that closes it)
    not_applicable   not relevant to an agent-run studio (the note says why)

parity.check validates every file (commands named exist, every gap and partial names a work package that exists,
every chapter has capabilities, ids are unique) and measures coverage per tool and overall; parity.matrix writes
docs/parity-matrix.md from the files. It is re-run at the end of each parity phase to measure progress.
"""
import json
import re
from collections import Counter

from . import ROOT

KINDS = ("command", "data", "metric", "partial", "gap", "not_applicable")
DIR = ROOT / "parity"


def load():
    return {f.stem: json.loads(f.read_text()) for f in sorted(DIR.glob("*.json"))}


def wp_ids():
    return set(re.findall(r"^\*\*(WP-\d\d) ", (ROOT / "docs" / "work-packages.md").read_text(), re.M))


def caps(t):
    for ch in t.get("chapters", []):
        for c in ch.get("capabilities", []):
            yield ch, c


def check(tools=None):
    from . import COMMANDS
    wps = wp_ids(); probs = []; cov = {}; seen = set()
    tools = tools if tools is not None else load()
    for key, t in tools.items():
        if not t.get("chapters"):
            probs.append(f"{key}: no chapters"); continue
        kinds = Counter()
        for ch, c in caps(t):
            cid = c.get("id", "?")
            if cid in seen:
                probs.append(f"{key}: duplicate id {cid}")
            seen.add(cid)
            m = c.get("match") or {}; k = m.get("kind"); refs = m.get("ref") or []
            refs = [refs] if isinstance(refs, str) else refs
            if k not in KINDS:
                probs.append(f"{cid}: unknown match kind {k!r}"); continue
            kinds[k] += 1
            if not c.get("capability") or not c.get("pro_use"):
                probs.append(f"{cid}: capability or professional use missing")
            if k in ("command", "partial"):
                cmds = [r for r in refs if re.fullmatch(r"[a-z_]+\.[a-z_.]+", r)]
                bad = [r for r in cmds if r not in COMMANDS]
                if bad:
                    probs.append(f"{cid}: no such command {bad}")
                if k == "command" and not cmds:
                    probs.append(f"{cid}: a command match names no command")
            if k in ("gap", "partial"):
                named = [r for r in refs if re.fullmatch(r"WP-\d\d", r)]
                if not named:
                    probs.append(f"{cid}: a {k} names no work package")
                elif any(r not in wps for r in named):
                    probs.append(f"{cid}: no such work package {[r for r in named if r not in wps]}")
            if k == "not_applicable" and not m.get("note"):
                probs.append(f"{cid}: not applicable without a reason")
        for ch in t["chapters"]:
            if not ch.get("capabilities"):
                probs.append(f"{key}: chapter {ch.get('chapter')!r} has no capabilities")
        n = sum(kinds.values()); rel = n - kinds["not_applicable"]
        cov[key] = {"tool": t.get("tool", key), "chapters": len(t["chapters"]), "capabilities": n, **{k: kinds[k] for k in KINDS},
                    "covered": round((kinds["command"] + kinds["data"] + kinds["metric"]) / rel, 3) if rel else None,
                    "covered_or_partial": round((kinds["command"] + kinds["data"] + kinds["metric"] + kinds["partial"]) / rel, 3) if rel else None}
    tot = Counter()
    for v in cov.values():
        for k in KINDS:
            tot[k] += v[k]
    rel = sum(tot.values()) - tot["not_applicable"]
    overall = {**{k: tot[k] for k in KINDS}, "capabilities": sum(tot.values()),
               "covered": round((tot["command"] + tot["data"] + tot["metric"]) / rel, 3) if rel else None,
               "covered_or_partial": round((tot["command"] + tot["data"] + tot["metric"] + tot["partial"]) / rel, 3) if rel else None}
    gaps = Counter()
    for t in tools.values():
        for _, c in caps(t):
            if (c.get("match") or {}).get("kind") in ("gap", "partial"):
                for r in (c["match"].get("ref") or []):
                    if re.fullmatch(r"WP-\d\d", str(r)):
                        gaps[r] += 1
    return {"ok": not probs, "problems": probs[:60], "tools": cov, "overall": overall, "gaps_by_wp": dict(gaps.most_common())}


def matrix_md(tools=None):
    tools = tools if tools is not None else load()
    rep = check(tools); o = rep["overall"]
    L = ["# Parity matrix", "",
         "What the professional 2D+ tools can do, chapter by chapter, and where Doodleberry stands (WP-41). Each capability",
         "is described in our own words from the tool's manual and release notes; the data is in `parity/<tool>.json`, and",
         "`python -m dbe parity.check` validates it and measures coverage. Generated by `python -m dbe parity.matrix`; re-run",
         "at the end of each parity phase.", "",
         "Match: **command** (an existing command does it), **data** (a field of the film or puppet data), **metric** (a QA",
         "measure), **partial** (partly there; the WP that finishes it), **gap** (missing; the WP that closes it), **n/a**",
         "(not relevant to an agent-run studio).", "",
         f"Overall: {o['capabilities']} capabilities; covered {round(100 * (o['covered'] or 0))}%, covered or partial "
         f"{round(100 * (o['covered_or_partial'] or 0))}% (of those that apply).", "",
         "| Tool | Chapters | Capabilities | Command | Data | Metric | Partial | Gap | n/a | Covered | Covered or partial |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for v in rep["tools"].values():
        L.append(f"| {v['tool']} | {v['chapters']} | {v['capabilities']} | {v['command']} | {v['data']} | {v['metric']} | {v['partial']} | {v['gap']} | "
                 f"{v['not_applicable']} | {round(100 * (v['covered'] or 0))}% | {round(100 * (v['covered_or_partial'] or 0))}% |")
    L += ["", "Gaps and partial matches by the work package that closes them:", "",
          ", ".join(f"{k} {n}" for k, n in rep["gaps_by_wp"].items()) or "none", ""]
    for key, t in tools.items():
        L += [f"## {t.get('tool', key)} ({t.get('version', '')})", "",
              "Sources: " + "; ".join(f"[{s.get('title', s['url'])}]({s['url']})" for s in t.get("sources", [])[:8]), ""]
        for ch in t["chapters"]:
            L += [f"### {ch['chapter']}", "", "| Capability | How professionals use it | Doodleberry |", "|---|---|---|"]
            for c in ch["capabilities"]:
                m = c.get("match") or {}; refs = m.get("ref") or []
                refs = [refs] if isinstance(refs, str) else refs
                k = {"not_applicable": "n/a"}.get(m.get("kind"), m.get("kind"))
                ours = f"**{k}**" + (": " + ", ".join(f"`{r}`" if "." in str(r) else str(r) for r in refs) if refs else "") + (f" ({m['note']})" if m.get("note") else "")
                cell = lambda s: str(s).replace("|", "/").replace("\n", " ")
                L.append(f"| {cell(c['capability'])} | {cell(c['pro_use'])} | {cell(ours)} |")
            L.append("")
    return "\n".join(L) + "\n", rep
