"""Content planner (plan 3.8): research sweeps -> idea bank -> a dated calendar under spread rules -> a live tracker.

Six sweeps feed the bank (each is a research task for an agent; plan.sweep_prompt gives the prompt and the schema):
    dated_hook  anniversaries, awareness days, sky events and scheduled launches that fall in the quarter
    recent      new papers, discoveries and decisions from the last few months that stay newsworthy
    evergreen   myths, "how does it work" and "why" questions that are always in season
    tool        free tools and public data a viewer can use themselves
    analysis    an original analysis of public data we can run and re-run (data, terms, a sanity check)
    local       stories from the channel's locale (people, places, species, problems)

An idea is a brief in waiting (the brief template of feature map row 144): a draft hook, the angle, why now,
starting-point sources (leads, not facts), research leads and cautions, its field, its sweep, a format, and dates
(the event date of a dated hook, the fresh_until of a recent story).

The scheduler fills the quarter's posting days, in order: dated hooks on their day, the weekly series slot, the
analysis cadence, the local quota, then the rest. Among candidates it prefers a field that has had nothing yet
(an empty field gets the next slot), then the least-used field, then the idea's score. Every row gets a start-by date
(the post date minus the lead time for its sweep) and a fact-lock date: the day facts.json must be cleared by the fact
gate (ledger fact_gate cleared), after which the script may change but its claims may not.

plan.check verifies every rule independently of the scheduler, so a calendar edited by hand is checked the same way.
plan.track reads the films and the production registry, so the calendar shows where each post really is.
Files: plan/channel.json, plan/ideas.json, plan/<quarter>.json (all in git: they are the studio's plan).
"""
import datetime as dt
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from . import ROOT

PLAN = ROOT / "plan"
SWEEPS = ("dated_hook", "recent", "evergreen", "tool", "analysis", "local")
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DEFAULT_CHANNEL = {
    "name": "Doodleberry science shorts",
    "audience": "curious general viewers on phones (9:16), ages 13 and up; no prior science assumed",
    "fields": ["life & health", "plants & farming", "animals & ecology", "space & physics", "earth & climate", "tech & computing"],
    "locale": "Sri Lanka",
    "languages": ["en"],
    "rules": {
        "post_days": ["mon", "wed", "fri", "sat"],
        "series": {"day": "mon", "name": "Myth Monday", "sweeps": ["evergreen"], "format": "myth_vs_data"},
        "max_field_per_week": 1,
        "min_field_gap_days": 4,
        "local_per_week": 1,
        "analysis_every_weeks": 2,
        "dated_hook_tolerance_days": 1,
        "lead_days": {"dated_hook": 14, "recent": 10, "evergreen": 10, "tool": 10, "analysis": 21, "local": 14},
        "fact_lock_days": {"default": 4, "analysis": 6},
    },
}


def channel():
    f = PLAN / "channel.json"
    return json.loads(f.read_text()) if f.exists() else json.loads(json.dumps(DEFAULT_CHANNEL))


def quarter_dates(q):
    m = re.fullmatch(r"(\d{4})-Q([1-4])", q)
    if not m:
        raise ValueError("quarter looks like 2027-Q1")
    y, n = int(m.group(1)), int(m.group(2))
    start = dt.date(y, 3 * n - 2, 1)
    end = (dt.date(y + (n == 4), 1 if n == 4 else 3 * n + 1, 1)) - dt.timedelta(days=1)
    return start, end


def week_of(d):
    return d - dt.timedelta(days=d.weekday())


# ---------------------------------------------------------------- the idea bank
IDEA_FIELDS = {"title": str, "sweep": str, "field": str, "hook": str, "angle": str, "why_now": str, "sources": list,
               "research_leads": list, "cautions": list}


def _norm(t):
    return re.sub(r"[^a-z0-9 ]", "", _fold(t)).split()


def similar(a, b):
    """word-overlap similarity of two titles (to keep the bank free of near-duplicates)"""
    A, B = set(_norm(a)) - {"the", "a", "of", "and", "is", "how", "why", "what", "to", "in", "your"}, set(_norm(b)) - {"the", "a", "of", "and", "is", "how", "why", "what", "to", "in", "your"}
    return len(A & B) / max(1, min(len(A), len(B)))


TOPIC_STOP = set("the a an of and or is are was how why what to in on for with your you it its this that from by at as be can do does not no "
                 "more than into our we they their his her have has about just only who when where which sri lanka lankan".split())


def _fold(t):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c)).lower()   # El Niño = El Nino


def topic_words(i):
    return {w for w in re.findall(r"[a-z]{4,}", _fold(" ".join(str(i.get(k, "")) for k in ("title", "angle", "hook")))) if w not in TOPIC_STOP}


def _stem(ws):
    return {w[:-1] if w.endswith("s") and not w.endswith("ss") else w for w in ws}


def same_topic(a, b, threshold=0.4):
    """two ideas about the same subject, e.g. a dated hook and a local story about the same disease; a quarter should
    not carry both: their titles share two or more words and most of the shorter title, or title, angle and hook
    share most of their content words"""
    ta, tb = _stem(topic_words({"title": a.get("title", "")})), _stem(topic_words({"title": b.get("title", "")}))
    shared = ta & tb
    if len(shared) >= 2 and len(shared) / max(1, min(len(ta), len(tb))) >= 0.6:
        return True
    A, B = _stem(topic_words(a)), _stem(topic_words(b))
    return len(A & B) / max(1, min(len(A), len(B))) >= threshold


def validate_idea(x, ch):
    errs = []
    for k, t in IDEA_FIELDS.items():
        if not isinstance(x.get(k), t) or (t is str and not x[k].strip()):
            errs.append(f"{k} missing")
    if x.get("sweep") not in SWEEPS:
        errs.append(f"sweep must be one of {SWEEPS}")
    if x.get("field") not in ch["fields"]:
        errs.append(f"field must be one of {ch['fields']}")
    srcs = x.get("sources") or []
    if not srcs or not all(isinstance(s, dict) and str(s.get("url", "")).startswith("http") for s in srcs):
        errs.append("sources: at least one {url, title, date} starting point")
    if x.get("sweep") == "dated_hook":
        try:
            dt.date.fromisoformat(x.get("date", ""))
        except ValueError:
            errs.append("a dated hook needs its date (YYYY-MM-DD)")
    if x.get("sweep") == "recent":
        try:
            dt.date.fromisoformat(x.get("fresh_until", ""))
        except ValueError:
            errs.append("a recent story needs fresh_until (YYYY-MM-DD)")
    if x.get("sweep") == "analysis" and not x.get("data"):
        errs.append("an analysis needs data: {source, url, terms}")
    return errs


def add_ideas(bank, ideas, ch, by):
    added, rejected = [], []
    n = max([int(i["id"][1:]) for i in bank["ideas"]] + [0])
    for x in ideas:
        errs = validate_idea(x, ch)
        dup = next((i["id"] for i in bank["ideas"] if similar(i["title"], x.get("title", "")) >= 0.75), None)
        if errs or dup:
            rejected.append({"title": x.get("title"), "why": errs or [f"near-duplicate of {dup}"]}); continue
        n += 1
        idea = {"id": f"I{n:03d}", **{k: x[k] for k in x if k != "id"}, "status": "idea", "added": dt.date.today().isoformat(), "by": by}
        idea.setdefault("score", 3); idea.setdefault("local", x["sweep"] == "local"); idea.setdefault("format", "explainer")
        bank["ideas"].append(idea); added.append(idea["id"])
    return added, rejected


# ---------------------------------------------------------------- scheduling
def lead(r, sweep):
    return r["lead_days"].get(sweep, 10)


def fact_lock_days(r, sweep):
    return r["fact_lock_days"].get(sweep, r["fact_lock_days"]["default"])


def post_days(r, start, end):
    days = [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]
    return [d for d in days if DAYS[d.weekday()] in r["post_days"]]


def eligible(idea, day, r, planned_on):
    if idea["status"] not in ("idea", "planned"):
        return False
    if day - dt.timedelta(days=lead(r, idea["sweep"])) < planned_on:
        return False   # too late to start it
    if idea["sweep"] == "recent" and day > dt.date.fromisoformat(idea["fresh_until"]):
        return False
    if idea["sweep"] == "dated_hook":
        return False   # dated hooks are placed on their own day
    return True


def schedule(q, bank, ch, planned_on):
    """-> calendar rows for quarter q"""
    r = ch["rules"]; start, end = quarter_dates(q)
    days = post_days(r, start, end)
    rows = {d: None for d in days}
    used, by_field_dates = set(), defaultdict(list)
    tol = r["dated_hook_tolerance_days"]

    def take(d, idea, role):
        rows[d] = {"date": d.isoformat(), "idea": idea["id"], "title": idea["title"], "sweep": idea["sweep"], "field": idea["field"],
                   "local": bool(idea.get("local")), "role": role, "format": idea.get("format", "explainer"),
                   "start_by": (d - dt.timedelta(days=lead(r, idea["sweep"]))).isoformat(),
                   "fact_lock": {"by": (d - dt.timedelta(days=fact_lock_days(r, idea["sweep"]))).isoformat(), "status": "open"},
                   "status": "planned"}
        used.add(idea["id"]); by_field_dates[idea["field"]].append(d)

    def field_ok(field, d):
        wk = week_of(d)
        same_week = sum(1 for x in by_field_dates[field] if week_of(x) == wk)
        gap = min([abs((d - x).days) for x in by_field_dates[field]] + [999])
        return same_week < r["max_field_per_week"] and gap >= r["min_field_gap_days"]

    # 1. dated hooks: on their day (a posting day within the tolerance, or the day itself added as a slot)
    hooks = sorted([i for i in bank["ideas"] if i["sweep"] == "dated_hook" and i["status"] in ("idea", "planned") and start <= dt.date.fromisoformat(i["date"]) <= end],
                   key=lambda i: -i.get("score", 3))
    for h in hooks:
        hd = dt.date.fromisoformat(h["date"])
        if hd - dt.timedelta(days=lead(r, "dated_hook")) < planned_on:
            continue
        cands = sorted([d for d in rows if abs((d - hd).days) <= tol and d <= hd], key=lambda d: abs((d - hd).days)) or [hd]
        wk_days = sum(1 for x in rows if week_of(x) == week_of(hd))
        series_in = start <= week_of(hd) + dt.timedelta(days=DAYS.index(r["series"]["day"])) <= end
        cap = wk_days - (1 if series_in else 0) - r["local_per_week"]   # leave room for the week's series episode and local story
        if sum(1 for x, v in rows.items() if v and week_of(x) == week_of(hd)) >= cap:
            continue
        for d in cands:
            if d not in rows:   # the event day is not a posting day: it takes the place of that week's nearest free slot
                wk = [x for x in rows if week_of(x) == week_of(hd) and rows[x] is None and DAYS[x.weekday()] != r["series"]["day"]]
                if not wk:
                    continue
                del rows[min(wk, key=lambda x: abs((x - hd).days))]; rows[d] = None
            if rows.get(d) is None and field_ok(h["field"], d) and not any(same_topic(h, i) for i in bank["ideas"] if i["id"] in used):
                take(d, h, "dated hook"); break
    rows = dict(sorted(rows.items()))
    # 2. the series slot, 3. analysis cadence, 4. local quota, 5. everything else
    weeks = sorted({week_of(d) for d in rows})

    byid = {i["id"]: i for i in bank["ideas"]}

    def fresh_topic(i):
        return not any(same_topic(i, byid[u]) for u in used)

    def pick(d, pool, role):
        cands = [i for i in pool if i["id"] not in used and eligible(i, d, r, planned_on) and field_ok(i["field"], d) and fresh_topic(i)]
        if not cands:
            return False
        counts = Counter({f: sum(1 for x in v if x < d) for f, v in by_field_dates.items()})   # posts before this day
        best = min(cands, key=lambda i: (counts[i["field"]] > 0, counts[i["field"]], -i.get("score", 3),
                                          i.get("fresh_until", "9999") if i["sweep"] == "recent" else "9999", i["id"]))
        take(d, best, role); return True
    ideas = bank["ideas"]
    series_pool = [i for i in ideas if i["sweep"] in r["series"]["sweeps"] and i.get("format") == r["series"]["format"]]
    for wk in weeks:   # the series day, or (when a dated hook has it) the next free day that week
        sday = wk + dt.timedelta(days=DAYS.index(r["series"]["day"]))
        if not start <= sday <= end:
            continue
        for d in sorted(x for x in rows if week_of(x) == wk and x >= sday and rows[x] is None):
            if pick(d, series_pool, r["series"]["name"]):
                break
    for k, wk in enumerate(weeks):
        if k % r["analysis_every_weeks"] == 0:
            span = [x for x in weeks[k:k + r["analysis_every_weeks"]]]
            if not any(v and v["sweep"] == "analysis" for d, v in rows.items() if week_of(d) in span):
                for d in [d for d in rows if week_of(d) == wk and rows[d] is None]:
                    if pick(d, [i for i in ideas if i["sweep"] == "analysis"], "analysis"):
                        break
    for wk in weeks:
        have = sum(1 for d, v in rows.items() if week_of(d) == wk and v and v["local"])
        for d in [d for d in rows if week_of(d) == wk and rows[d] is None]:
            if have >= r["local_per_week"]:
                break
            if pick(d, [i for i in ideas if i.get("local")], "local"):
                have += 1
    for d in rows:
        if rows[d] is None:
            pick(d, [i for i in ideas if i["sweep"] != "dated_hook"], "open slot")
    return [v if v else {"date": d.isoformat(), "idea": None, "status": "empty", "role": "unfilled"} for d, v in rows.items()]


# ---------------------------------------------------------------- the rule check (independent of the scheduler)
def check(cal, bank, ch):
    r = ch["rules"]; ideas = {i["id"]: i for i in bank["ideas"]}
    planned_on = dt.date.fromisoformat(cal["planned_on"]); start, end = quarter_dates(cal["quarter"])
    rows = [x for x in cal["rows"]]
    res = {}

    def rule(name, ok, detail):
        res[name] = {"ok": not detail if ok is None else ok, "detail": detail[:12] if isinstance(detail, list) else detail}
    filled = [x for x in rows if x.get("idea")]
    rule("every_slot_filled", None, [x["date"] for x in rows if not x.get("idea")])
    D = lambda s: dt.date.fromisoformat(s)
    weeks = defaultdict(list)
    for x in filled:
        weeks[week_of(D(x["date"]))].append(x)
    all_weeks = sorted({week_of(d) for d in post_days(r, start, end)})
    expect = Counter(week_of(d) for d in post_days(r, start, end))   # the quarter's first and last weeks may be short
    rule("posts_per_week", None, [f"week of {w}: {len(weeks[w])} posts, {expect[w]} posting days" for w in all_weeks if not expect[w] <= len(weeks[w]) <= expect[w] + 1])
    rule("topic_diversity", None, [f"week of {w}: {f} x{n}" for w, xs in weeks.items() for f, n in Counter(x["field"] for x in xs).items() if n > r["max_field_per_week"]])
    gaps = []
    byf = defaultdict(list)
    for x in sorted(filled, key=lambda x: x["date"]):
        byf[x["field"]].append(D(x["date"]))
    for f, ds in byf.items():
        gaps += [f"{f}: {a} and {b}" for a, b in zip(ds, ds[1:]) if (b - a).days < r["min_field_gap_days"]]
    rule("field_gap", None, gaps)
    rule("local_quota", None, [f"week of {w}: {sum(x['local'] for x in weeks[w])} local" for w in all_weeks if sum(x["local"] for x in weeks[w]) < r["local_per_week"]])
    miss = []
    for k in range(0, len(all_weeks), r["analysis_every_weeks"]):
        span = all_weeks[k:k + r["analysis_every_weeks"]]
        if not any(x["sweep"] == "analysis" for w in span for x in weeks[w]):
            miss.append(f"weeks of {span[0]} to {span[-1]}")
    rule("analysis_cadence", None, miss)
    sd = DAYS.index(r["series"]["day"])   # every week whose series day is in the quarter has an episode (on that day unless a dated hook has it)
    rule("series_cadence", None, [f"week of {w}" for w in all_weeks if start <= w + dt.timedelta(days=sd) <= end and not any(
        ideas.get(x["idea"], {}).get("format") == r["series"]["format"] and ideas.get(x["idea"], {}).get("sweep") in r["series"]["sweeps"]
        and (D(x["date"]).weekday() == sd or any(y["sweep"] == "dated_hook" and D(y["date"]).weekday() == sd for y in weeks[w])) for x in weeks[w])])
    bad = []
    for x in filled:
        i = ideas.get(x["idea"])
        if not i:
            bad.append(f"{x['date']}: unknown idea {x['idea']}"); continue
        if i["sweep"] == "dated_hook" and not (0 <= (D(i["date"]) - D(x["date"])).days <= r["dated_hook_tolerance_days"]):
            bad.append(f"{x['date']}: {i['title']} is dated {i['date']}")
        if i["sweep"] == "recent" and D(x["date"]) > D(i["fresh_until"]):
            bad.append(f"{x['date']}: {i['title']} was fresh until {i['fresh_until']}")
    rule("timeliness", None, bad)
    rule("lead_times", None, [f"{x['date']}: start by {x['start_by']}, planned on {cal['planned_on']}" for x in filled
                               if D(x["start_by"]) < planned_on or D(x["start_by"]) != D(x["date"]) - dt.timedelta(days=lead(r, x["sweep"]))])
    rule("fact_lock_marked", None, [x["date"] for x in filled if not (x.get("fact_lock", {}).get("by") and D(x["start_by"]) < D(x["fact_lock"]["by"]) < D(x["date"]))])
    # an empty field gets the next slot: among open slots, no field repeats while another field with an eligible,
    # unused idea has not had a post yet
    seen, late = set(), []
    for x in sorted(filled, key=lambda x: x["date"]):
        if x["role"] == "open slot" and x["field"] in seen:
            d0 = D(x["date"])
            fits = lambda f: all(not (week_of(D(y["date"])) == week_of(d0) and y["field"] == f) and abs((D(y["date"]) - d0).days) >= r["min_field_gap_days"]
                                 for y in filled if y["field"] == f and y is not x)
            waiting = [f for f in ch["fields"] if f not in seen and fits(f) and any(i["field"] == f and i["sweep"] != "dated_hook" and i["id"] not in {y["idea"] for y in filled}
                                                                                    and eligible(i, d0, r, planned_on) for i in bank["ideas"])]
            if waiting:
                late.append(f"{x['date']}: {x['field']} again while {', '.join(waiting)} had nothing")
        seen.add(x["field"])
    rule("empty_field_next", None, late)
    rule("no_repeats", None, [k for k, n in Counter(x["idea"] for x in filled).items() if n > 1])
    ids = [x["idea"] for x in filled if x["idea"] in ideas]
    rule("distinct_topics", None, [f"{a} and {b}" for k, a in enumerate(ids) for b in ids[k + 1:] if same_topic(ideas[a], ideas[b])])
    rule("starting_points", None, [x["date"] for x in filled if not ideas.get(x["idea"], {}).get("sources")])
    return {"ok": all(v["ok"] for v in res.values()), "rules": res,
            "summary": {"posts": len(filled), "slots": len(rows), "fields": dict(Counter(x["field"] for x in filled)),
                        "sweeps": dict(Counter(x["sweep"] for x in filled)), "local": sum(x["local"] for x in filled)}}


# ---------------------------------------------------------------- the brief and the live tracker
def slug(title):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", title.lower())).strip("-")[:48]


def brief_md(idea, row, ch):
    src = "\n".join(f"- {s.get('title', s['url'])} ({s.get('date', 'n.d.')}): {s['url']}" for s in idea["sources"])
    data = f"\n## Data\n{idea['data'].get('source')}: {idea['data'].get('url')} (terms: {idea['data'].get('terms', 'check')})\n" if idea.get("data") else ""
    return f"""# Brief: {idea['title']}

Planned by the content planner (plan 3.8) for {row['date']} ({row.get('role')}). Start by {row['start_by']}; facts locked
by {row['fact_lock']['by']} (fact gate cleared in the ledger).

| field     | value |
|-----------|-------|
| channel   | {ch['name']} |
| audience  | {ch['audience']} |
| field     | {idea['field']}{' (local: ' + ch['locale'] + ')' if idea.get('local') else ''} |
| format    | {idea.get('format', 'explainer')} |
| hook      | {idea['hook']} (draft) |
| angle     | {idea['angle']} |
| why now   | {idea['why_now']} |

## Sources (starting points only: research may overturn the premise; if it does, escalate)
{src}
{data}
## Research leads
{chr(10).join('- ' + x for x in idea['research_leads'])}

## Cautions
{chr(10).join('- ' + x for x in idea['cautions'])}
"""


def track(cal, bank, reg_films, today):
    """where each row really is: planned, briefed, in production (with the registry state), fact-locked, merged,
    posted; and what is overdue"""
    out = []
    for x in cal["rows"]:
        if not x.get("idea"):
            out.append({**x, "stage": "empty", "overdue": []}); continue
        film = x.get("film"); fd = ROOT / "films" / film if film else None
        stage = "planned"
        if fd and (fd / "brief.md").exists():
            stage = "briefed"
        e = reg_films.get(film) if film else None
        if e:
            stage = {"merged": "merged", "approved": "approved", "waiting_owner": "final ready"}.get(e["state"], "in production")
        led = json.loads((fd / "ledger.json").read_text()) if fd and (fd / "ledger.json").exists() else []
        locked = any(l.get("role") == "fact_gate" and str(l.get("verdict")).lower() == "cleared" for l in led)
        if e and e.get("workspace"):   # in production: the gate is recorded in the film's workspace
            wl = Path(e["workspace"]) / "films" / film / "ledger.json"
            if wl.exists():
                locked = locked or any(l.get("role") == "fact_gate" and str(l.get("verdict")).lower() == "cleared" for l in json.loads(wl.read_text()))
        if x.get("posted"):
            stage = "posted"
        D = dt.date.fromisoformat
        over = []
        if stage == "planned" and today > D(x["start_by"]):
            over.append(f"not started (start by {x['start_by']})")
        if not locked and stage != "posted" and today > D(x["fact_lock"]["by"]):
            over.append(f"facts not locked (by {x['fact_lock']['by']})")
        if stage not in ("posted",) and today > D(x["date"]):
            over.append("posting date passed")
        out.append({**x, "stage": stage, "fact_lock": {**x["fact_lock"], "status": "locked" if locked else "open"}, "overdue": over})
    return out


# ---------------------------------------------------------------- self-test
def synthetic_bank(ch, q, seed=5):
    """a bank of made-up ideas (for tests only: example.invalid sources) with every sweep and field represented"""
    import random
    rng = random.Random(seed); start, end = quarter_dates(q); ideas = []
    for k in range(90):
        sw = SWEEPS[k % 6]; f = ch["fields"][(k * 5 + k // 6) % len(ch["fields"])]
        tag = "".join(chr(97 + (k // 26 ** j) % 26) for j in range(3))   # distinct words per idea (the topic guard compares words)
        x = {"title": f"{tag}ology {tag}ness {tag}ward", "sweep": sw, "field": f, "hook": "h", "angle": "a", "why_now": "w",
             "sources": [{"url": f"https://example.invalid/{k}", "title": "t", "date": "2026-10-01"}], "research_leads": ["l"], "cautions": ["c"],
             "score": rng.randint(1, 5), "format": "myth_vs_data" if sw == "evergreen" else "explainer"}
        if sw == "dated_hook":
            x["date"] = (start + dt.timedelta(days=rng.randint(15, (end - start).days))).isoformat()
        if sw == "recent":
            x["fresh_until"] = (start + dt.timedelta(days=rng.randint(30, 90))).isoformat()
        if sw == "analysis":
            x["data"] = {"source": "test", "url": "https://example.invalid/data", "terms": "test"}
        ideas.append(x)
    bank = {"ideas": []}
    add_ideas(bank, ideas, ch, "self-test")
    return bank


def self_test():
    """the scheduler's calendar must pass the independent check; broken calendars must fail the right rules"""
    import copy
    fails, got = [], {}
    ch = json.loads(json.dumps(DEFAULT_CHANNEL)); q = "2027-Q1"; planned_on = dt.date(2026, 11, 2)
    bank = synthetic_bank(ch, q)
    rows = schedule(q, bank, ch, planned_on)
    cal = {"quarter": q, "planned_on": planned_on.isoformat(), "rows": rows}
    c = check(cal, bank, ch); got["synthetic"] = {k: v["ok"] for k, v in c["rules"].items()}; got["summary"] = c["summary"]
    if not c["ok"]:
        fails.append(f"the scheduler's own calendar fails: {[k for k, v in c['rules'].items() if not v['ok']]}")
    filled = [x for x in rows if x.get("idea")]
    breaks = {
        "topic_diversity": lambda C: [x.update(field=filled[1]["field"]) for x in C["rows"] if x["date"] == filled[0]["date"]],
        "local_quota": lambda C: [x.update(local=False) for x in C["rows"]],
        "fact_lock_marked": lambda C: C["rows"][3].pop("fact_lock", None) if C["rows"][3].get("idea") else None,
        "lead_times": lambda C: C.update(planned_on="2027-01-20"),
        "series_cadence": lambda C: [x.update(idea=next(y["idea"] for y in filled if y["sweep"] == "tool")) for x in C["rows"] if x["role"] == ch["rules"]["series"]["name"]][:1],
    }
    for rule_, brk in breaks.items():
        C = copy.deepcopy(cal); brk(C)
        cc = check(C, bank, ch)
        if cc["rules"][rule_]["ok"]:
            fails.append(f"breaking {rule_} was not caught")
    got["breaks_caught"] = sorted(breaks)
    return fails, got


# ---------------------------------------------------------------- sweep prompts (for research agents)
SWEEP_ASK = {
    "dated_hook": "Dated hooks: events whose date falls inside the quarter and that a 30-60 s science short can hang on: "
                  "round-number anniversaries of discoveries, inventions, missions and births of scientists (25, 50, 100, 150... years); "
                  "official awareness days and international days (UN, WHO, FAO, UNESCO); sky events visible somewhere on Earth "
                  "(eclipses, meteor showers, close approaches, planet alignments) and scheduled launches or missions. "
                  "Verify every date against an official or primary page; give the event date as \"date\".",
    "recent": "Recent developments: peer-reviewed papers, discoveries, approvals, missions and decisions from the last four months "
              "that will still be worth explaining during the quarter. Give \"fresh_until\" (the last day it still feels new, "
              "at most 120 days after the news) and the news date in the sources.",
    "evergreen": "Evergreen stories for the weekly series \"{series}\" (format myth_vs_data: a common belief, a prediction prompt, "
                 "the data, why): widely held myths or misconceptions that good evidence answers clearly. Set \"format\": \"myth_vs_data\". "
                 "Also a few \"how does it work / why\" questions (format \"explainer\").",
    "tool": "Tools: free, legal tools and public data viewers a curious viewer can use themselves today (citizen science apps, "
            "public databases, sky and weather tools, open-source software), each with one thing to show in the film.",
    "analysis": "Original analyses: questions we can answer ourselves from public data with a short script, e.g. a trend, "
                "a comparison or a re-check of a common claim. Give \"data\": {{\"source\", \"url\", \"terms\" (licence or "
                "terms of use), \"check\" (a published figure to sanity-check against)}}. Only data whose terms allow reuse.",
    "local": "Local stories from {locale}: researchers and institutions, native species and ecosystems, farming, health and "
             "environmental questions, inventions and history with a science angle. Set \"local\": true.",
}


def sweep_prompt(sweep, q, ch, count=20):
    start, end = quarter_dates(q)
    ask = SWEEP_ASK[sweep].format(series=ch["rules"]["series"]["name"], locale=ch["locale"])
    return f"""You are a research scout for {ch['name']}: {ch['audience']}. Topic fields: {', '.join(ch['fields'])}.
Local angle: {ch['locale']}. The quarter being planned runs {start} to {end}; today is {dt.date.today()}.

Find {count} ideas for this sweep. {ask}

Rules:
- Search the web and open the pages you cite. Every idea needs at least one real source URL you have seen, with its
  title and date. Never invent a URL, a date, a number or a quotation. If you cannot confirm something, leave it out.
- Sources are starting points, not facts: the film's own research will verify them. Put what to verify in
  "research_leads" and what could go wrong (contested evidence, sensitive health or safety content, people's privacy,
  copyrighted characters or footage) in "cautions".
- Spread the ideas across the fields, and skip anything that needs real footage of people or copyrighted characters.
- Each idea fits a 30-60 s vertical explainer with original drawn characters.

Output: a JSON array, each item exactly:
{{"title": "...", "sweep": "{sweep}", "field": one of {json.dumps(ch['fields'])},
 "hook": "a draft first line that makes a viewer stop", "angle": "the one thing the film explains",
 "why_now": "why this quarter", "sources": [{{"url": "...", "title": "...", "date": "YYYY-MM-DD or YYYY"}}],
 "research_leads": ["..."], "cautions": ["..."], "score": 1-5 (how strong for this audience),
 "format": "explainer" | "myth_vs_data" | "dialogue",
 "local": true|false{', "date": "YYYY-MM-DD (the event day, inside the quarter)"' if sweep == 'dated_hook' else ''}{', "fresh_until": "YYYY-MM-DD"' if sweep == 'recent' else ''}{', "data": {"source": "...", "url": "...", "terms": "...", "check": "..."}' if sweep == 'analysis' else ''}}}
"""


# ---------------------------------------------------------------- source spot-check
def check_url(url, timeout=12):
    """'ok' (it answers), 'missing' (404/410, or the host does not exist), 'blocked' (refuses robots: 401/403/429,
    or times out); only 'missing' disqualifies a source"""
    import socket
    import urllib.error
    import urllib.request
    from urllib.parse import urlparse
    try:   # a host that does not exist is missing, whatever a proxy answers
        socket.getaddrinfo(urlparse(url).hostname or "", 443)
    except socket.gaierror:
        return "missing"
    except Exception:
        pass
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (doodleberry source check)", "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return "ok" if r.status < 400 else "missing"
    except urllib.error.HTTPError as e:
        return "missing" if e.code in (404, 410) else "blocked"
    except urllib.error.URLError as e:
        return "missing" if isinstance(e.reason, socket.gaierror) else "blocked"
    except Exception:
        return "blocked"


def check_sources(ideas, workers=12):
    """{url: status} for every source URL in the ideas, fetched in parallel"""
    from concurrent.futures import ThreadPoolExecutor
    urls = sorted({s["url"] for i in ideas for s in i.get("sources", []) if isinstance(s, dict) and s.get("url")}
                  | {i["data"]["url"] for i in ideas if isinstance(i.get("data"), dict) and i["data"].get("url")})
    with ThreadPoolExecutor(workers) as ex:
        return dict(zip(urls, ex.map(check_url, urls)))
