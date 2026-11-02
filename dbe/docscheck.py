"""Docs consistency check (WP-01): the build plan, the feature map, the work packages and the command registry
must agree, so status can be trusted.

    commands_exist       every command named in backticks in the docs (`film.render`) is registered
    open_rows_point_on   every feature-map row marked ⬜ or 🟡 names a work package (WP-nn) or says "not planned"
    wp_refs_exist        every WP-nn mentioned in the docs is a work package in docs/work-packages.md
    plan_items_covered   every item in the build plan's phase tables has a status row or a work package that covers it
    wps_listed           every work package is in the at-a-glance table and in the order of work
"""
import re

from . import COMMANDS, ROOT

DOCS = ["docs/feature-map.md", "docs/build-plan.md", "docs/work-packages.md", "docs/dbe.md"]
FILE_EXT = {"js", "mjs", "json", "md", "py", "html", "png", "jpg", "svg", "mp4", "wav", "txt", "onnx", "bin", "task", "sh", "css",
            "srt", "vtt", "ass", "pdf", "otio", "sif", "blend", "glb", "kra", "psd", "ora", "puppet", "jsonl", "lottie", "toml", "yaml", "cfg"}


def check():
    text = {d: (ROOT / d).read_text() for d in DOCS}
    ns = {c.split(".")[0] for c in COMMANDS}
    probs = {}
    named = set()
    for d, t in text.items():
        for tok in re.findall(r"`([a-z]+\.[a-z_]+)`", t):
            a, b = tok.split(".")
            if a in ns and b not in FILE_EXT:
                named.add(tok)
    probs["commands_exist"] = sorted(c for c in named if c not in COMMANDS)
    open_rows = []
    for n, line in enumerate(text["docs/feature-map.md"].split("\n"), 1):
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        status = next((c for c in cells if c[:1] in ("⬜", "🟡")), None)
        if status is None or len(cells) < 3:
            continue
        if not re.search(r"WP-\d\d|not planned", line):
            open_rows.append(f"line {n}: {cells[0][:60]}")
    probs["open_rows_point_on"] = open_rows
    wps = set(re.findall(r"^\*\*WP-(\d\d) ", text["docs/work-packages.md"], re.M))
    refs = {r for t in text.values() for r in re.findall(r"WP-(\d\d)", t)}
    probs["wp_refs_exist"] = sorted(f"WP-{r}" for r in refs - wps)
    plan = text["docs/build-plan.md"]
    items = re.findall(r"^\| (\d\.\d+) \| \*\*", plan, re.M)
    status_rows = plan[plan.index("## Status"):] if "## Status" in plan else ""
    have = set(re.findall(r"^\| ([\d.]+(?: [+/] [\d.]+)?) ", status_rows, re.M))
    done = {x for h in have for x in re.findall(r"\d\.\d+", h)}
    wptext = text["docs/work-packages.md"]
    probs["plan_items_covered"] = [i for i in items if i not in done and not re.search(rf"(?<![\d.]){re.escape(i)}(?![\d])", wptext)]
    glance = wptext[wptext.index("## At a glance"):wptext.index("## Definition of done")] if "## At a glance" in wptext else ""
    order = wptext[wptext.index("## Order of work"):wptext.index("## M1")] if "## Order of work" in wptext else ""
    scheduled = {int(x) for x in re.findall(r"(?<![\d.])(\d{1,2})(?![\d.])", order)}
    for a_, b_ in re.findall(r"(\d{1,2}) to (\d{1,2})", order):   # "26 to 30"
        scheduled |= set(range(int(a_), int(b_) + 1))
    probs["wps_listed"] = sorted(f"WP-{w}" for w in wps if not re.search(rf"^\| {w} \|", glance, re.M) or int(w) not in scheduled)
    return {"ok": not any(probs.values()), "problems": probs,
            "counts": {"commands_named": len(named), "work_packages": len(wps), "plan_items": len(items), "open_feature_rows": sum(
                1 for l in text["docs/feature-map.md"].split("\n") if l.startswith("| ") and re.search(r"\| (⬜|🟡)", l))}}
