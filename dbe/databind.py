"""Data-bound visuals (plan 2.17): every number on screen or in the narration comes from films/<name>/data.json.

Text anywhere in shots.json or in script lines may hold {{path}} or {{path|format}}: path walks data.json
("totals.nights", "monthly.0.1"); formats: an integer (decimals: {{share|1}}), "comma" (12,400), "pct" (0.42 -> 42%),
"pct1", "int", "word" (1-10 as words), "upper". In a film with a language (shots.json "lang", script.json "lang",
WP-25) numbers take that locale's separators (CLDR, through Babel; Latin digits) and "word" spells out only in English.
Chart elements with "data_from" get their data inlined. Bound values
are substituted when the shots are resolved and when the script is voiced, so the shot hashes (and so incremental
re-renders) follow exactly the data each shot shows.
"""
import json
import re

_TPL = re.compile(r"\{\{\s*([\w.\-]+)\s*(?:\|\s*([\w]+))?\s*\}\}")
DIGITS = {"arab": "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669", "arabext": "\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9",
          "deva": "\u0966\u0967\u0968\u0969\u096a\u096b\u096c\u096d\u096e\u096f", "beng": "\u09e6\u09e7\u09e8\u09e9\u09ea\u09eb\u09ec\u09ed\u09ee\u09ef",
          "thai": "\u0e50\u0e51\u0e52\u0e53\u0e54\u0e55\u0e56\u0e57\u0e58\u0e59", "tamldec": "\u0be6\u0be7\u0be8\u0be9\u0bea\u0beb\u0bec\u0bed\u0bee\u0bef",
          "mymr": "\u1040\u1041\u1042\u1043\u1044\u1045\u1046\u1047\u1048\u1049"}   # WP-25: native digits by numbering system (CLDR names)
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


def fmt(v, f, lang=None):
    if lang and lang.split("-")[0] != "en" and f != "upper":   # WP-25: the film's locale
        from babel.numbers import format_decimal as _fd, format_percent as _fp
        base, _, ns = lang.partition("-u-nu-")   # "ar-u-nu-arab": the locale's own digits; else Latin digits
        loc = base.replace("-", "_"); nsys = ns or "latn"
        dig = str.maketrans("0123456789", DIGITS.get(nsys, "0123456789"))   # Babel keeps Latin digits: write the system's own
        format_decimal = lambda v, *a, **k: _fd(v, *a, numbering_system=nsys, **k).translate(dig)
        format_percent = lambda v, *a, **k: _fp(v, *a, numbering_system=nsys, **k).translate(dig)
        if f in ("pct", "pct1"):
            return format_percent(float(v), "#,##0.0%" if f == "pct1" else "#,##0%", locale=loc)
        if f and f.isdigit():
            return format_decimal(float(v), "#,##0." + "0" * int(f) if int(f) else "#,##0", locale=loc)
        if f in ("int", "word"):
            return format_decimal(int(round(float(v))), locale=loc)
        if isinstance(v, (int, float)):
            return format_decimal(v, locale=loc)
        return str(v)
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


def bind_text(s, data, lang=None):
    return _TPL.sub(lambda m: fmt(lookup(data, m.group(1)), m.group(2), lang), s)


def bind(obj, data, used=None, lang=None):
    """substitute bindings in every string and inline data_from; `used` collects the paths read"""
    if isinstance(obj, dict):
        out = {k: bind(v, data, used, lang) for k, v in obj.items()}
        if isinstance(obj.get("data_from"), str) and "data" not in obj:
            out["data"] = lookup(data, obj["data_from"])
            if used is not None:
                used.add(obj["data_from"])
        return out
    if isinstance(obj, list):
        return [bind(x, data, used, lang) for x in obj]
    if isinstance(obj, str) and "{{" in obj:
        if used is not None:
            used.update(m.group(1) for m in _TPL.finditer(obj))
        return bind_text(obj, data, lang)
    return obj
