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
local quota, the analysis cadence (any week of its span), a repair pass (a week short of its local story or a span
short of its analysis, or a week without its series episode, takes the slot of one of its dated hooks), then the rest. Among candidates it prefers a field that has had nothing yet
(an empty field gets the next slot), then the least-used field, then the idea's score. Every row gets a start-by date
(the post date minus the lead time for its sweep) and a fact-lock date: the day facts.json must be cleared by the fact
gate (ledger fact_gate cleared), after which the script may change but its claims may not.

plan.check verifies every rule independently of the scheduler, so a calendar edited by hand is checked the same way.
plan.track reads the films and the production registry, so the calendar shows where each post really is.
Channels (WP-32): the studio can run several series side by side, each a channel with its own audience, fields,
locale, rules, brand kit, default cast and voices. Files, per channel: plan/channels/<id>/channel.json, ideas.json and
<quarter>.json (all in git: they are the studio's plan); plan/channels.json names the default channel. Every plan
command takes `channel` (default: the default channel). plan.cross lines the channels' quarters up week by week.
"""
import datetime as dt
import json
import os
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
        "expert_review": {"fields": ["life & health"], "keywords": ["disease", "medicine", "medical", "drug", "dose", "treatment",
                          "vaccine", "cancer", "diagnos", "symptom", "antivenom", "law", "legal", "court", "invest", "loan", "tax"]},
    },
}


def needs_expert(idea, ch):
    """WP-05: health, legal and finance claims get an expert reviewer -> the reason, or None"""
    rule = (ch.get("rules") or {}).get("expert_review") or DEFAULT_CHANNEL["rules"]["expert_review"]
    if idea.get("field") in rule["fields"]:
        return f"health: {idea['field']}"
    text = " ".join(str(idea.get(k, "")) for k in ("title", "angle", "hook")).lower()
    hit = next((k for k in rule["keywords"] if re.search(rf"\b{k}", text)), None)
    return f"keyword: {hit}" if hit else None


def plan_root():
    """plan/ (DBE_PLAN points elsewhere, for tests)"""
    return Path(os.environ.get("DBE_PLAN") or PLAN)


def channel_ids():
    d = plan_root() / "channels"
    return sorted(p.name for p in d.iterdir() if (p / "channel.json").exists()) if d.is_dir() else []


def default_channel():
    f = plan_root() / "channels.json"
    if f.exists():
        return json.loads(f.read_text())["default"]
    ids = channel_ids()
    return ids[0] if ids else "main"


def chan_dir(cid=None):
    cid = cid or default_channel()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", cid):
        raise ValueError("channel ids are lower-case letters, digits and -")
    return plan_root() / "channels" / cid


def channel(cid=None):
    """a channel's settings, with its id (the defaults when it has none yet)"""
    cid = cid or default_channel()
    f = chan_dir(cid) / "channel.json"
    ch = json.loads(f.read_text()) if f.exists() else json.loads(json.dumps(DEFAULT_CHANNEL))
    ch["id"] = cid
    return ch


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
    ratio = lambda A, B: len(A & B) / max(1, min(len(A), len(B)))
    A, B = topic_words(a), topic_words(b)
    return max(ratio(A, B), ratio(_stem(A), _stem(B))) >= threshold   # stripping plurals can lower the score as well as raise it


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
                   "review": "expert" if needs_expert(idea, ch) else "standard", "status": "planned"}
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
    def untake(d):
        v = rows[d]; used.discard(v["idea"]); by_field_dates[v["field"]].remove(d); rows[d] = None; return v

    def retake(d, v):
        rows[d] = v; used.add(v["idea"]); by_field_dates[v["field"]].append(d)

    for wk in weeks:   # the series day, or (when a dated hook has it) the next free day that week
        sday = wk + dt.timedelta(days=DAYS.index(r["series"]["day"]))
        if not start <= sday <= end:
            continue
        if rows.get(sday, 1) is None and not pick(sday, series_pool, r["series"]["name"]):
            # nothing fits the series day: a dated hook within the field gap may be blocking it; set it aside, place the
            # episode, and put the hook back if its field still fits
            near = [x for x in rows if rows[x] and rows[x]["role"] == "dated hook" and abs((x - sday).days) < max(7, r["min_field_gap_days"])]
            for hd in near:
                v = untake(hd)
                if pick(sday, series_pool, r["series"]["name"]):
                    if field_ok(v["field"], hd):
                        retake(hd, v)
                    break
                retake(hd, v)
        if any(v and v["role"] == r["series"]["name"] for x, v in rows.items() if week_of(x) == wk):
            continue
        # the series day is taken (a dated hook): the next free day that week, else an earlier one (a Sunday series)
        free = [x for x in rows if week_of(x) == wk and rows[x] is None and start <= x <= end]
        for d in sorted(x for x in free if x >= sday) + sorted((x for x in free if x < sday), reverse=True):
            if pick(d, series_pool, r["series"]["name"]):
                break
    for wk in weeks:   # the weekly local quota before the analysis cadence, which can use any week of its span
        have = sum(1 for d, v in rows.items() if week_of(d) == wk and v and v["local"])
        for d in [d for d in rows if week_of(d) == wk and rows[d] is None]:
            if have >= r["local_per_week"]:
                break
            if pick(d, [i for i in ideas if i.get("local")], "local"):
                have += 1
    for k, wk in enumerate(weeks):
        if k % r["analysis_every_weeks"] == 0:
            span = [x for x in weeks[k:k + r["analysis_every_weeks"]]]
            if not any(v and v["sweep"] == "analysis" for d, v in rows.items() if week_of(d) in span):
                for d in [d for d in rows if week_of(d) in span and rows[d] is None]:
                    if pick(d, [i for i in ideas if i["sweep"] == "analysis"], "analysis"):
                        break
    # repair: a week short of its local story, or a span short of its analysis, takes the slot of one of its dated
    # hooks (hooks are welcome extras; the quotas are rules)
    def swap_in(days, pool, role):
        # never a hook on the series day: it is what lets that week's episode sit on another day
        for d in sorted((x for x in days if rows[x] and rows[x]["role"] == "dated hook" and DAYS[x.weekday()] != r["series"]["day"]),
                        key=lambda x: byid[rows[x]["idea"]].get("score", 3)):
            v = untake(d)
            if pick(d, pool, role):
                return True
            retake(d, v)
        return False
    for wk in weeks:
        sday = wk + dt.timedelta(days=DAYS.index(r["series"]["day"]))
        if start <= sday <= end and not any(v and v["role"] == r["series"]["name"] for d, v in rows.items() if week_of(d) == wk):
            swap_in([d for d in rows if week_of(d) == wk], series_pool, r["series"]["name"])
        if sum(1 for d, v in rows.items() if week_of(d) == wk and v and v["local"]) < r["local_per_week"]:
            swap_in([d for d in rows if week_of(d) == wk], [i for i in ideas if i.get("local")], "local")
    for k, wk in enumerate(weeks):
        if k % r["analysis_every_weeks"] == 0:
            span = weeks[k:k + r["analysis_every_weeks"]]
            if not any(v and v["sweep"] == "analysis" for d, v in rows.items() if week_of(d) in span):
                swap_in([d for d in rows if week_of(d) in span], [i for i in ideas if i["sweep"] == "analysis"], "analysis")
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
    rule("expert_review_marked", None, [x["date"] for x in filled if x["idea"] in ideas and (x.get("review") == "expert") != bool(needs_expert(ideas[x["idea"]], ch))])
    rule("starting_points", None, [x["date"] for x in filled if not ideas.get(x["idea"], {}).get("sources")])
    return {"ok": all(v["ok"] for v in res.values()), "rules": res,
            "summary": {"posts": len(filled), "slots": len(rows), "fields": dict(Counter(x["field"] for x in filled)),
                        "sweeps": dict(Counter(x["sweep"] for x in filled)), "local": sum(x["local"] for x in filled)}}


# ---------------------------------------------------------------- the brief and the live tracker
def slug(title, n=48):
    """a film folder name from a title: at most n characters, cut at a word boundary"""
    s = re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", _fold(title).lower())).strip("-")
    return s if len(s) <= n else (s[:n].rsplit("-", 1)[0] if "-" in s[:n] else s[:n])


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
| review    | {('expert (' + needs_expert(idea, ch) + ')') if needs_expert(idea, ch) else 'standard'} |

## Sources (starting points only: research may overturn the premise; if it does, escalate)
{src}
{data}
## Research leads
{chr(10).join('- ' + x for x in idea['research_leads'])}

## Cautions
{chr(10).join('- ' + x for x in idea['cautions'])}
{_expert_note(idea, ch)}"""


def _sentences(t):
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+", str(t or "")) if x.strip()]


def short_source(src):
    """a citation short enough to read on screen: the site and the year"""
    host = re.sub(r"^www\.", "", re.sub(r"^https?://([^/]+).*$", r"\1", src.get("url", "")))
    year = (re.search(r"(19|20)\d\d", str(src.get("date", ""))) or [None])[0]
    return f"Source: {host}" + (f", {year}" if year else "")


def draft_storyboard(idea, row):
    """the template brief for a calendar row, drafted from the idea's own fields: the hook, the angle's first two
    sentences, the first source. Every line is a draft and every fact is unsourced: the session rewrites them after
    research (the research gate holds the film until each fact has a source). -> (format, brief fields)"""
    fmt = row.get("format") or idea.get("format") or "explainer"
    sents = _sentences(idea.get("angle")); hook = _sentences(idea.get("hook")) or [idea["title"]]
    first = sents[0] if sents else idea["title"]
    second = sents[1] if len(sents) > 1 else "(To write after research: the second step.)"
    src = short_source(idea["sources"][0]) if idea.get("sources") else "Source: to come"
    title = idea["title"]
    if fmt == "myth_vs_data":
        f = {"myth": " ".join(hook), "question": title if title.endswith("?") else "So, is that true?", "finding": first, "why": second, "source": src}
        fact_beats = {"finding": first, "why": second}
    elif fmt == "dialogue":
        f = {"topic": title.rstrip("?"), "exchanges": [{"q": title if title.endswith("?") else "What's going on here?", "a": first, "fact": "a1"},
                                                     {"q": "Why, though?", "a": second, "fact": "a2"}]}
        fact_beats = {"a1": first, "a2": second}
    else:
        fmt = "explainer"
        f = {"hook": " ".join(hook), "point": first, "detail": second, "source": src}
        fact_beats = {"point": first, "detail": second}
    f["title"] = title
    f["facts"] = {k: {"claim": v, "source": None, "status": "draft"} for k, v in fact_beats.items()}
    f["draft"] = (f"Drafted from plan row {row['date']} (idea {idea['id']}) on the planner's own words: rewrite every line "
                  f"after research, and lock the facts by {row['fact_lock']['by']}.")
    return fmt, f


def _expert_note(idea, ch):
    why = needs_expert(idea, ch)
    if not why:
        return ""
    return f"""
## Expert review ({why})
Every fact in facts.json records what its source leaves out (`omits`, e.g. first-line treatments, or "nothing
material"). Before approval, a qualified reviewer reads the script and facts and records
`ledger.add role=expert_review verdict=cleared` with their name and qualification in the notes. The production board
will not approve the film without it.
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
def synthetic_bank(ch, q, seed=5, offset=0):
    """a bank of made-up ideas (for tests only: example.invalid sources) with every sweep and field represented;
    offset gives another channel other titles"""
    import random
    rng = random.Random(seed); start, end = quarter_dates(q); ideas = []
    for k in range(90):
        sw = SWEEPS[k % 6]; f = ch["fields"][(k * 5 + k // 6) % len(ch["fields"])]
        tag = "".join(chr(97 + ((k + offset) // 26 ** j) % 26) for j in range(3))   # distinct words per idea (the topic guard compares words)
        x = {"title": f"{tag}ology {tag}ness {tag}ward", "sweep": sw, "field": f, "hook": "h", "angle": "a", "why_now": "w",
             "sources": [{"url": f"https://example.invalid/{k}", "title": "t", "date": "2026-10-01"}], "research_leads": ["l"], "cautions": ["c"],
             "score": rng.randint(1, 5), "format": ch["rules"]["series"]["format"] if sw in ch["rules"]["series"]["sweeps"] else "explainer"}
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


KIDS_SAMPLE = {   # a second channel for tests (WP-32): other audience, fields, locale, rules, brand, cast and voices
    "name": "Story sprouts (sample)", "audience": "children 6 to 10 watching with a parent; short words, one idea per film",
    "fields": ["animals", "space", "how things work", "the body"], "locale": "anywhere", "languages": ["en"],
    "brand": "sample-kids", "cast": {"expert": "priya", "learner": "momo", "narrator": "priya"}, "voices": {"priya": "kokoro:af_bella", "momo": "kokoro:af_heart"},
    "rules": {"post_days": ["tue", "sun"], "series": {"day": "sun", "name": "Story Sunday", "sweeps": ["evergreen"], "format": "wonder_story"},
              "max_field_per_week": 1, "min_field_gap_days": 3, "local_per_week": 0, "analysis_every_weeks": 6, "dated_hook_tolerance_days": 2,
              "lead_days": {"dated_hook": 10, "recent": 7, "evergreen": 7, "tool": 7, "analysis": 14, "local": 10},
              "fact_lock_days": {"default": 3, "analysis": 5},
              "expert_review": {"fields": ["the body"], "keywords": ["disease", "medicine", "vaccine"]}},
}


def channels_self_test(tmp):
    """two channels side by side (WP-32): each plans a quarter that passes its own rules, the cross-channel view finds
    no clash between distinct banks and finds one when both carry the same subject, briefs carry each channel's brand
    kit and cast, and a film resolves its own brand kit"""
    import shutil
    import subprocess
    import sys
    fails, got = [], {}
    root = Path(tmp) / "plan"; shutil.rmtree(root, ignore_errors=True)
    q = "2027-Q2"; planned_on = "2027-02-20"
    sci = json.loads((PLAN / "channels" / default_channel() / "channel.json").read_text()) if (PLAN / "channels").is_dir() else DEFAULT_CHANNEL
    for cid, ch, off in (("science", sci, 0), ("kids", KIDS_SAMPLE, 300)):
        d = root / "channels" / cid; d.mkdir(parents=True)
        (d / "channel.json").write_text(json.dumps(ch, indent=1))
        (d / "ideas.json").write_text(json.dumps(synthetic_bank({**ch, "id": cid}, q, seed=5 + off, offset=off), indent=1))
    (root / "channels.json").write_text(json.dumps({"default": "science"}))
    env = {**os.environ, "DBE_PLAN": str(root)}

    def run(cmd, args):
        r = subprocess.run([sys.executable, "-m", "dbe", cmd, json.dumps(args)], cwd=ROOT, capture_output=True, text=True, env=env, timeout=300)
        return json.loads(r.stdout) if r.returncode == 0 else {"error": (r.stderr or r.stdout).strip().splitlines()[-1]}
    got["channels"] = [c["id"] for c in run("plan.channels", {})] if isinstance(run("plan.channels", {}), list) else run("plan.channels", {})
    if got["channels"] != ["science", "kids"]:
        fails.append(f"channels: {got['channels']}")
    for cid in ("science", "kids"):
        r = run("plan.schedule", {"quarter": q, "planned_on": planned_on, "channel": cid})
        got[cid] = {"ok": r.get("ok"), "posts": (r.get("summary") or {}).get("posts"), "failing": [k for k, v in (r.get("rules") or {}).items() if not v["ok"]]}
        if not r.get("ok"):
            fails.append(f"{cid}: its quarter breaks its own rules: {got[cid]['failing'] or r}")
    sk = json.loads((root / "channels" / "kids" / f"{q}.json").read_text())
    per_week = Counter(week_of(dt.date.fromisoformat(r["date"])) for r in sk["rows"] if r.get("idea"))
    if max(per_week.values()) > len(KIDS_SAMPLE["rules"]["post_days"]):
        fails.append(f"kids posts more than its {len(KIDS_SAMPLE['rules']['post_days'])} a week: {max(per_week.values())}")
    x = run("plan.cross", {"quarter": q}); got["cross"] = {"weeks": len(x.get("weeks", [])), "clashes": len(x.get("clashes", []))}
    if x.get("clashes") or x.get("channels") != ["kids", "science"]:
        fails.append(f"cross view with distinct banks: {x.get('clashes') or x}")
    kb = json.loads((root / "channels" / "kids" / "ideas.json").read_text()); sb = json.loads((root / "channels" / "science" / "ideas.json").read_text())
    srow = next(r for r in json.loads((root / "channels" / "science" / f"{q}.json").read_text())["rows"] if r.get("idea"))
    krow = next(r for r in sk["rows"] if r.get("idea") and abs((dt.date.fromisoformat(r["date"]) - dt.date.fromisoformat(srow["date"])).days) < 7
                and week_of(dt.date.fromisoformat(r["date"])) == week_of(dt.date.fromisoformat(srow["date"])))
    same = next(i for i in sb["ideas"] if i["id"] == srow["idea"])
    for i in kb["ideas"]:
        if i["id"] == krow["idea"]:
            i["title"] = same["title"]   # the same subject on both channels in one week
    (root / "channels" / "kids" / "ideas.json").write_text(json.dumps(kb))
    x2 = run("plan.cross", {"quarter": q}); got["cross_seeded_clash"] = len(x2.get("clashes", []))
    if not x2.get("clashes"):
        fails.append("cross view missed two channels posting one subject in a week")
    sys.path.insert(0, str(ROOT))
    from . import commands as C
    for cid, kit in (("science", sci.get("brand", "brand")), ("kids", "sample-kids")):
        ch = {**(sci if cid == "science" else KIDS_SAMPLE), "id": cid}
        idea = next(i for i in json.loads((root / "channels" / cid / "ideas.json").read_text())["ideas"] if i["status"] == "planned")
        row = {"date": "2027-04-06", "format": "explainer", "fact_lock": {"by": "2027-04-01"}}
        fmt, fields = draft_storyboard(idea, row)
        fields.update({k: ch[k] for k in ("cast", "voices") if ch.get(k)}); fields["brand"] = ch.get("brand", "brand")
        name = f"zz-channeltest-{cid}"; fd = ROOT / "films" / name
        try:
            C.film_from_template(name, fmt, fields)
            sh = json.loads((fd / "shots.json").read_text()); sc = json.loads((fd / "script.json").read_text())
            k = C._brand_kit(sh); want = json.loads((ROOT / "brand" / f"{kit}.json").read_text())
            spk = sorted(sc["speakers"])
            got[f"{cid}_film"] = {"brand": sh.get("brand"), "primary": (k or {}).get("palette", {}).get("primary"), "speakers": spk}
            if sh.get("brand") != kit or k != want or not set(spk) <= set(ch["cast"].values()):
                fails.append(f"{cid}: the film does not carry the channel's brand kit and cast: {got[f'{cid}_film']}")
        finally:
            shutil.rmtree(fd, ignore_errors=True)
    if got.get("science_film", {}).get("primary") == got.get("kids_film", {}).get("primary"):
        fails.append("the two channels' films share one palette")
    # robustness: the scheduler on many made-up banks for both channels (a quarter can still miss a rule when the bank
    # runs short of fitting ideas; the check then says so)
    ok = n = 0
    for cid, ch0 in (("science", sci), ("kids", KIDS_SAMPLE)):
        for q2, po in (("2027-Q1", "2026-11-02"), ("2027-Q2", "2027-02-20"), ("2027-Q3", "2027-05-20"), ("2027-Q4", "2027-08-20")):
            for seed in range(5, 11):
                off = 300 if cid == "kids" else 0; chx = {**ch0, "id": cid}
                b = synthetic_bank(chx, q2, seed=seed + off, offset=off)
                rs = schedule(q2, b, chx, dt.date.fromisoformat(po)); n += 1
                ok += check({"quarter": q2, "planned_on": po, "rules": chx["rules"], "rows": rs}, b, chx)["ok"]
    got["robustness"] = f"{ok} of {n} made-up quarters pass every rule"
    if ok < n * 0.9:
        fails.append(f"scheduler robustness: {got['robustness']}")
    shutil.rmtree(root, ignore_errors=True)
    return fails, got
