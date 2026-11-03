"""Corrections, companions and living films (WP-27).

**Corrections log** (films/<name>/corrections.json): every change made to a published film after the fact, dated,
with what it said, what it says now, why, what kind (an error, an update when a source changed, a clarification) and
who reported it (credited, if they agree). A correction is made by key (the keys film.strings lists: a line, an
overlay's text, a title, a thumbnail line, a fact's claim) and carried to every surface: the voice and captions
(a line is re-voiced and the film re-rendered), the title and covers, the credits (a dated corrections section and
thanks to who reported it), the film's page (a dated log, "what we got wrong" apart from updates) and the posting
package. Each surface is then read back for the new words.

**The film's page** (build/page/index.html): its title, the film, what it says, its sources (facts.json), its
credits and its corrections log, self-contained.

**Companion guide** (build/companion/): a runnable script (guide.py, and the same as guide.md) that recomputes every
number the film shows or says from the film's own analysis: it copies analysis/ (scripts, sources.json, the cached
source files, each checked against its recorded sha256) to a scratch folder, runs the scripts in order, and prints
every number the film uses beside the number it gets, as JSON; film.companion runs it and checks they agree.
"""
import datetime as dt
import html
import json
import re
from pathlib import Path

KINDS = ("error", "update", "clarification")


def log_path(d):
    return Path(d) / "corrections.json"


def load_log(d):
    f = log_path(d)
    return json.loads(f.read_text()) if f.exists() else {"note": "WP-27: dated corrections to this film (film.correct)", "corrections": []}


def add(d, entry):
    lg = load_log(d); entry = {"id": f"c{len(lg['corrections']) + 1}", **entry}
    lg["corrections"].append(entry); log_path(d).write_text(json.dumps(lg, indent=1, ensure_ascii=False) + "\n")
    return entry


def credits_section(lg):
    """lines for credits.txt: the corrections, and thanks to who reported them"""
    cs = lg.get("corrections") or []
    if not cs:
        return []
    out = ["", "Corrections"]
    for c in cs:
        out.append(f"  {c['date']} ({c['kind']}): {c['why']}" + (f" Thanks to {c['credit']}." if c.get("credit") else ""))
    return out


def page(title, video, lines, facts, credits, lg, lang="en"):
    """a film's page: self-contained HTML"""
    e = html.escape
    errs = [c for c in lg.get("corrections", []) if c["kind"] == "error"]; ups = [c for c in lg.get("corrections", []) if c["kind"] != "error"]
    row = lambda c: (f"<li><time>{e(c['date'])}</time> <b>{e(c['why'])}</b><br><span class=was>It said: “{e(str(c.get('from')))}”</span> "
                     f"<span class=now>It now says: “{e(str(c.get('to')))}”</span>" + (f" <span class=thanks>Thanks to {e(c['credit'])}.</span>" if c.get("credit") else "") + "</li>")
    src = "".join(f"<li>{e(f.get('claim', ''))}" + "".join(f" <a href=\"{e(s.get('url'))}\">{e(s.get('title') or s.get('url'))}</a>" for s in (f.get("sources") or []) if s.get("url")) + "</li>" for f in facts)
    return f"""<!doctype html><html lang="{e(lang)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{e(title)}</title>
<style>:root{{--bg:#f4f1ea;--ink:#24160e;--muted:#7a6a5c;--line:#e2dccf;--accent:#e8743a}}@media (prefers-color-scheme:dark){{:root{{--bg:#1c1916;--ink:#f2ebe2;--muted:#a8998a;--line:#3a342e}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,sans-serif}}main{{max-width:720px;margin:0 auto;padding:16px}}video{{width:100%;max-height:70vh;background:#000;border-radius:12px}}
h1{{font-size:22px}}h2{{font-size:17px;margin-top:28px;border-top:1px solid var(--line);padding-top:12px}}time,.was{{color:var(--muted)}}.now{{display:block}}li{{margin-bottom:10px}}a{{color:var(--accent)}}pre{{white-space:pre-wrap;font:13px ui-monospace,monospace}}</style></head>
<body><main><h1>{e(title)}</h1><video controls src="{e(video)}"></video>
<h2>What it says</h2><ol>{''.join(f'<li>{e(l)}</li>' for l in lines)}</ol>
<h2>Sources</h2><ul>{src or '<li>none listed</li>'}</ul>
<h2 id="corrections">Corrections</h2>{('<h3>What we got wrong</h3><ul>' + ''.join(row(c) for c in errs) + '</ul>') if errs else ''}{('<h3>Updates and clarifications</h3><ul>' + ''.join(row(c) for c in ups) + '</ul>') if ups else ''}{'' if (errs or ups) else '<p>None so far.</p>'}
<h2>Credits</h2><pre>{e(credits)}</pre></main></body></html>"""


GUIDE = '''"""Companion guide: {title}

Every number in the film, recomputed from its own analysis. Run: python guide.py (Python 3, standard library only,
plus what the analysis scripts import). It copies the analysis (scripts, sources.json and the cached source files,
each checked against the sha256 recorded when the film was made) to a scratch folder, runs the scripts in order,
and prints each number the film uses beside the number it gets now.
"""
import hashlib, json, re, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANALYSIS = HERE / "analysis"
NUMBERS = json.loads((HERE / "numbers.json").read_text())   # what the film shows and says, and where


def lookup(data, path):
    cur = data
    for k in path.split("."):
        cur = cur[int(k)] if isinstance(cur, list) else cur[k]
    return cur


def main():
    out = {{"sources": [], "numbers": []}}
    work = Path(tempfile.mkdtemp()); shutil.copytree(ANALYSIS, work / "analysis")
    for s in json.loads((ANALYSIS / "sources.json").read_text()).get("sources", []):
        f = work / "analysis" / "cache" / s["file"]; got = hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None
        out["sources"].append({{"id": s.get("id"), "file": s["file"], "terms": s.get("terms"), "sha256_ok": got == s.get("sha256")}})
    for py in sorted((work / "analysis").glob("*.py")):
        subprocess.run([sys.executable, py.name], cwd=work / "analysis", check=True)
    data = json.loads((work / "data.json").read_text())
    for n in NUMBERS:
        try:
            v = lookup(data, n["path"])
        except (KeyError, IndexError, ValueError):
            v = None
        out["numbers"].append({{**n, "reproduced": v, "same": v == n["value"]}})
    shutil.rmtree(work, ignore_errors=True)
    out["all_reproduced"] = all(x["same"] for x in out["numbers"]) and all(s["sha256_ok"] for s in out["sources"])
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
'''


def numbers_in(film_data, script, shots):
    """every number the film uses: each binding in its lines and on screen, and every value of each chart -> [{where, path, value}]"""
    tpl = re.compile(r"\{\{\s*([\w.\-]+)\s*(?:\|\s*(\w+))?\s*\}\}")
    from .databind import lookup
    out, seen = [], set()

    def add(where, path):
        try:
            v = lookup(film_data, path)
        except KeyError:
            return
        if isinstance(v, (int, float)) and not isinstance(v, bool) and (where, path) not in seen:
            seen.add((where, path)); out.append({"where": where, "path": path, "value": v})
    for ln in script.get("lines", []):
        for m in tpl.finditer(ln.get("text", "")):
            add(f"line {ln['id']}", m.group(1))
    for sh in shots.get("shots", []):
        for kind in ("overlays", "underlays"):
            for n, o in enumerate(sh.get(kind) or []):
                for f, v in o.items():
                    if isinstance(v, str):
                        for m in tpl.finditer(v):
                            add(f"shot {sh['id']} {o.get('type')} {f}", m.group(1))
                if o.get("data_from"):
                    rows = lookup(film_data, o["data_from"])
                    for i, r in enumerate(rows if isinstance(rows, list) else []):
                        if isinstance(r, list):
                            for j, x in enumerate(r):
                                if isinstance(x, (int, float)):
                                    add(f"shot {sh['id']} {o.get('type')} ({r[0]})", f"{o['data_from']}.{i}.{j}")
    return out


def write_companion(d, title, nums):
    import shutil
    cd = Path(d) / "build" / "companion"; shutil.rmtree(cd, ignore_errors=True); cd.mkdir(parents=True)
    shutil.copytree(Path(d) / "analysis", cd / "analysis", ignore=shutil.ignore_patterns("__pycache__"))
    (cd / "numbers.json").write_text(json.dumps(nums, indent=1, ensure_ascii=False))
    code = GUIDE.format(title=title.replace('"', "'"))
    (cd / "guide.py").write_text(code)
    md = [f"# Companion guide: {title}", "", "Every number in the film, recomputed from its own analysis.", "", "## The numbers", "",
          "| where in the film | data | value |", "|---|---|---|", *[f"| {n['where']} | `{n['path']}` | {n['value']} |" for n in nums], "",
          "## Reproduce them", "", "```bash", "python guide.py", "```", "", "It prints each number beside the one it computes; `all_reproduced` is true when every one matches and every",
          "cached source file still has the sha256 it had when the film was made.", "", "## The code", "", "```python", code, "```"]
    (cd / "guide.md").write_text("\n".join(md) + "\n")
    return cd
