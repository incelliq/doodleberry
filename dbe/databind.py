"""Data-bound visuals (plan 2.17): every number on screen or in the narration comes from films/<name>/data.json.

Text anywhere in shots.json or in script lines may hold {{path}} or {{path|format}}: path walks data.json
("totals.nights", "monthly.0.1"); formats: an integer (decimals: {{share|1}}), "comma" (12,400), "pct" (0.42 -> 42%),
"pct1", "int", "word" (1-10 as words), "upper". Chart elements with "data_from" get their data inlined. Bound values
are substituted when the shots are resolved and when the script is voiced, so the shot hashes (and so incremental
re-renders) follow exactly the data each shot shows.
"""
import json
import re

_TPL = re.compile(r"\{\{\s*([\w.\-]+)\s*(?:\|\s*([\w]+))?\s*\}\}")
WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]


def lookup(data, path):
    cur = data
    for k in str(path).split("."):
        if isinstance(cur, list) and re.fullmatch(r"-?\d+", k):
            cur = cur[int(k)]
        elif isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            raise KeyError(f"data.json has no {path!r} (stopped at {k!r})")
    return cur


def fmt(v, f):
    if f is None:
        return f"{v:,}" if isinstance(v, int) and abs(v) >= 10000 else (f"{v:g}" if isinstance(v, float) else str(v))
    if f.isdigit():
        return f"{float(v):,.{int(f)}f}"
    if f == "comma":
        return f"{float(v):,.0f}"
    if f == "int":
        return str(int(round(float(v))))
    if f in ("pct", "pct1"):
        return f"{float(v) * 100:.{1 if f == 'pct1' else 0}f}%"
    if f == "word":
        n = int(round(float(v))); return WORDS[n] if 0 <= n < len(WORDS) else str(n)
    if f == "upper":
        return str(v).upper()
    raise ValueError(f"unknown format {f!r} in a {{{{...}}}} binding")


def bind_text(s, data):
    return _TPL.sub(lambda m: fmt(lookup(data, m.group(1)), m.group(2)), s)


def bind(obj, data, used=None):
    """substitute bindings in every string and inline data_from; `used` collects the paths read"""
    if isinstance(obj, dict):
        out = {k: bind(v, data, used) for k, v in obj.items()}
        if isinstance(obj.get("data_from"), str) and "data" not in obj:
            out["data"] = lookup(data, obj["data_from"])
            if used is not None:
                used.add(obj["data_from"])
        return out
    if isinstance(obj, list):
        return [bind(x, data, used) for x in obj]
    if isinstance(obj, str) and "{{" in obj:
        if used is not None:
            used.update(m.group(1) for m in _TPL.finditer(obj))
        return bind_text(obj, data)
    return obj
