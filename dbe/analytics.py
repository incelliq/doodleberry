"""Analytics (WP-31): what each post did, what it says about the next films, and a plan that re-ranks itself.

**Store.** plan/channels/<id>/analytics.json (in git, with the plan): one record per post (a calendar row on one
platform: its date, idea, film, link) with dated **snapshots** of its numbers (views, watch time, average view
duration and percentage viewed, likes, comments, shares, saves, subscribers gained, impressions and click-through,
revenue, the share who stayed to watch rather than swiped), its **retention curve** ([[seconds, percent]]) and its
**geography** (views and revenue by country). Snapshots are kept, never overwritten: the 1-, 24- and 48-hour reads
and later ones all count. A record made from simulated numbers is marked "synthetic" and never feeds a real plan.

**Ingestion.** Platform exports, imported by `analytics.import`: the CSV a creator downloads from YouTube Studio,
TikTok Studio or Instagram's insights (headers are matched by name, case and punctuation ignored; unknown headers are
reported and can be mapped with `columns`), or the canonical JSON. Rows are matched to posts by link, by video id
inside the link, or by title. Where a platform's terms allow an API and the owner has set up credentials, a connector
reads the same numbers (YouTube Analytics API: `youtube_api`); otherwise the export is the route.

**The 48-hour checklist** (`checklist`): at 1, 24 and 48 hours, what to read and what it means for this channel: views
against the channel's median at the same age, the share that stayed to watch, retention at 3 seconds (the hook),
average percentage viewed, shares and saves per thousand views, comments, subscribers gained, and for long videos
impressions and click-through; each with the action it points to.

**Retention onto the film** (`retention_map`): the curve laid over the film's shots and lines: where viewers leave,
per second, against the curve's own smooth decay, so a line or shot that loses people stands out by name.

**Effects and re-ranking** (`effects`, `score_idea`): a post's performance is log2 of its 48-hour views over the
channel's median on that platform (a doubling is +1), averaged over its platforms. The effects of the feature values
(a field, a sweep, a format, local or not, the calendar role) are estimated together by ridge regression, so features
that travel together are told apart, each pulled toward zero as if by k = 3 pseudo-posts so that one lucky post moves
little. An idea's score is its own score plus half the sum of its features' effects, and every point is explained.
"""
import csv
import datetime as dt
import io
import json
import math
import re
from collections import defaultdict
from pathlib import Path

PLATFORM_HOSTS = {"youtube": ("youtube.com", "youtu.be"), "tiktok": ("tiktok.com",), "instagram": ("instagram.com",), "facebook": ("facebook.com", "fb.watch"),
                  "x": ("x.com", "twitter.com"), "linkedin": ("linkedin.com",)}
# export headers by platform, as the studios name them (matched case- and punctuation-insensitively)
ALIASES = {
    "common": {"views": "views", "video views": "views", "plays": "views", "total views": "views", "likes": "likes", "total likes": "likes",
               "comments": "comments", "comments added": "comments", "total comments": "comments", "shares": "shares", "total shares": "shares",
               "saves": "saves", "add to favorites": "saves", "subscribers": "subs", "subscribers gained": "subs", "followers gained": "subs", "new followers": "subs",
               "average view duration": "avg_view_s", "average watch time": "avg_view_s", "avg watch time": "avg_view_s",
               "average percentage viewed": "avg_pct", "average percentage viewed (%)": "avg_pct", "watched full video": "full_pct", "watched full video (%)": "full_pct",
               "watch time (hours)": "watch_time_h", "impressions": "impressions", "impressions click-through rate (%)": "ctr", "impressions click-through rate": "ctr",
               "estimated revenue (usd)": "revenue", "estimated revenue": "revenue", "revenue": "revenue", "rpm (usd)": "rpm", "rpm": "rpm",
               "stayed to watch (%)": "stayed_pct", "stayed to watch": "stayed_pct", "viewed vs swiped away (%)": "stayed_pct",
               "content": "video_id", "video": "video_id", "video id": "video_id", "video title": "title", "title": "title", "description": "title",
               "video link": "url", "permalink": "url", "link": "url", "url": "url", "video publish time": "published", "post time": "published", "publish time": "published",
               "geography": "country", "country": "country", "territory": "country",
               "video position (%)": "pos_pct", "video position": "pos_pct", "absolute audience retention (%)": "ret_pct", "audience retention (%)": "ret_pct",
               "seconds": "pos_s", "time (s)": "pos_s", "retention (%)": "ret_pct"},
}
NUMERIC = {"views", "likes", "comments", "shares", "saves", "subs", "avg_view_s", "avg_pct", "full_pct", "watch_time_h", "impressions", "ctr", "revenue", "rpm",
           "stayed_pct", "pos_pct", "ret_pct", "pos_s"}
K_SHRINK = 3.0
FEATURES = ("field", "sweep", "format", "local", "role")


def _key(h):
    return re.sub(r"\s+", " ", re.sub(r"[^\w%()]+", " ", (h or "").strip().lower())).strip()


def _num(v):
    """numbers as exports write them: 1,234 / 12.5% / 0:00:31 / 31s / $1.20"""
    if v is None:
        return None
    s = str(v).strip().replace(",", "").replace("$", "").replace("%", "").replace("USD", "").strip()
    if not s or s in ("-", "--"):
        return None
    if re.fullmatch(r"\d+:\d{1,2}(:\d{1,2})?(\.\d+)?", s):
        parts = [float(x) for x in s.split(":")]
        return parts[0] * 3600 + parts[1] * 60 + parts[2] if len(parts) == 3 else parts[0] * 60 + parts[1]
    s = re.sub(r"(?i)\s*s(ec(onds)?)?$", "", s)
    try:
        return float(s)
    except ValueError:
        return None


def platform_of(url):
    host = re.sub(r"^https?://(www\.|m\.)?", "", url or "").split("/")[0].lower()
    return next((p for p, hs in PLATFORM_HOSTS.items() if any(host == h or host.endswith("." + h) for h in hs)), None)


# ---------------- store ----------------
def store_path(chan_dir):
    return Path(chan_dir) / "analytics.json"


def load(chan_dir):
    f = store_path(chan_dir)
    return json.loads(f.read_text()) if f.exists() else {"note": "WP-31: what each post did (dbe/analytics.py)", "posts": {}}


def save(chan_dir, st):
    store_path(chan_dir).write_text(json.dumps(st, indent=1, ensure_ascii=False) + "\n")


def posts_from_calendars(chan_dir, extra_links=None):
    """posts the plan knows: calendar rows marked posted, one per platform link -> {post_id: record}"""
    out = {}
    for f in sorted(Path(chan_dir).glob("20??-Q?.json")):
        cal = json.loads(f.read_text())
        for r in cal.get("rows", []):
            p = r.get("posted") or {}
            links = dict(p.get("links") or {})
            if p.get("url"):
                links.setdefault(platform_of(p["url"]) or "other", p["url"])
            for plat, url in links.items():
                out[f"{r['date']}-{plat}"] = {"date": r["date"], "quarter": cal["quarter"], "idea": r.get("idea"), "film": r.get("film"), "title": r.get("title"),
                                             "platform": plat, "url": url, "posted_at": p.get("at") or r["date"],
                                             **{k: r.get(k) for k in FEATURES}}
    for pid, rec in (extra_links or {}).items():
        out.setdefault(pid, rec)
    return out


def _hours(posted_at, as_of):
    a = dt.datetime.fromisoformat(posted_at if "T" in posted_at else posted_at + "T00:00:00")
    b = dt.datetime.fromisoformat(as_of if "T" in as_of else as_of + "T00:00:00")
    return round((b - a).total_seconds() / 3600, 1)


def read_export(text, columns=None):
    """CSV text -> (rows of canonical keys, unknown headers)"""
    rd = csv.reader(io.StringIO(text.lstrip("﻿")))
    rows = [r for r in rd if any(c.strip() for c in r)]
    if not rows:
        return [], []
    head = rows[0]; amap = {**ALIASES["common"], **{_key(k): v for k, v in (columns or {}).items()}}
    keys = [amap.get(_key(h)) for h in head]; unknown = [h for h, k in zip(head, keys) if not k]
    out = []
    for r in rows[1:]:
        if r and r[0].strip().lower() in ("total", "totals"):
            continue
        rec = {}
        for k, v in zip(keys, r):
            if k:
                rec[k] = _num(v) if k in NUMERIC else v.strip()
        out.append(rec)
    return out, unknown


def match_post(rec, posts, platform):
    """the post an export row is about: its link, its video id inside a link, else its title"""
    cands = {pid: p for pid, p in posts.items() if p["platform"] == platform}
    url = (rec.get("url") or "").strip(); vid = (rec.get("video_id") or "").strip()
    for pid, p in cands.items():
        if url and p.get("url") and url.rstrip("/") == p["url"].rstrip("/"):
            return pid
        if vid and len(vid) >= 6 and vid in (p.get("url") or ""):
            return pid
    t = _key(rec.get("title"))
    if t:
        for pid, p in cands.items():
            if t and t in (_key(p.get("title")), _key(p.get("film"))):
                return pid
    return None


def ingest(st, posts, rows, platform, as_of, kind="totals", source="export"):
    """add a snapshot (or a retention curve, or geography) to each matched post -> (matched, unmatched)"""
    matched, unmatched = [], []
    for rec in rows:
        pid = match_post(rec, posts, platform)
        if not pid:
            unmatched.append(rec.get("title") or rec.get("url") or rec.get("video_id")); continue
        p = st["posts"].setdefault(pid, {**posts[pid], "snapshots": []})
        if kind == "geography" or rec.get("country"):
            g = p.setdefault("geo", {}).setdefault(rec.get("country") or "unknown", {})
            for k in ("views", "revenue", "watch_time_h"):
                if rec.get(k) is not None:
                    g[k] = rec[k]
            matched.append(pid); continue
        snap = {"at": as_of, "hours": _hours(p["posted_at"], as_of), "source": source, **{k: v for k, v in rec.items() if k in NUMERIC and v is not None}}
        p["snapshots"] = [s for s in p["snapshots"] if s["at"] != as_of] + [snap]
        p["snapshots"].sort(key=lambda s: s["hours"])
        matched.append(pid)
    return matched, unmatched


def add_retention(st, posts, pid, rows, duration_s=None):
    """a retention export: position in % (YouTube) or seconds -> [[seconds, percent]]"""
    p = st["posts"].setdefault(pid, {**posts[pid], "snapshots": []})
    pts = []
    for r in rows:
        if r.get("ret_pct") is None:
            continue
        if r.get("pos_s") is not None:
            pts.append([round(r["pos_s"], 2), r["ret_pct"]])
        elif r.get("pos_pct") is not None and duration_s:
            pts.append([round(r["pos_pct"] / 100 * duration_s, 2), r["ret_pct"]])
    p["retention"] = sorted(pts)
    return len(pts)


# ---------------- reading ----------------
def snapshot_at(p, hours=48):
    """the snapshot nearest the given age, at or after it if any (else the latest)"""
    ss = p.get("snapshots") or []
    after = [s for s in ss if s["hours"] >= hours]
    return min(after, key=lambda s: s["hours"]) if after else (ss[-1] if ss else None)


def medians(st, hours=48, synthetic=False):
    by = defaultdict(list)
    for p in st["posts"].values():
        if bool(p.get("synthetic")) != synthetic:
            continue
        s = snapshot_at(p, hours)
        if s and s.get("views"):
            by[p["platform"]].append(s["views"])
    return {k: sorted(v)[len(v) // 2] for k, v in by.items()}


def hold_at(p, sec=3.0):
    r = p.get("retention") or []
    for (t0, a), (t1, b) in zip(r, r[1:]):
        if t0 <= sec <= t1:
            return a + (b - a) * (sec - t0) / ((t1 - t0) or 1)
    return None


CHECKS = [   # (id, label, metric fn, good-if, the action when it is not)
    ("views_vs_median", "views against the channel's median at the same age", None, None, "packaging: try the other true title or thumbnail, and post the cut to the platform it did best on"),
    ("stayed", "share that stayed to watch rather than swiped (Shorts)", "stayed_pct", 60, "the first frame and first words: the cold open (variants.hooks) is the place to test"),
    ("hold_3s", "retention at 3 seconds (the hook)", None, 70, "hook: a hook variant for the next film of this kind; retention_map shows which line lost them"),
    ("avg_pct", "average percentage viewed", "avg_pct", 70, "pacing: lines and shots where retention falls fastest (retention_map)"),
    ("shares_per_k", "shares per thousand views", None, 5, "the payoff: is there a line worth sending to someone?"),
    ("saves_per_k", "saves per thousand views", None, 5, "usefulness: a tool or number viewers would come back to"),
    ("comments_per_k", "comments per thousand views", None, 2, "a question at the end; answer the first comments within the first hours"),
    ("subs_per_k", "subscribers gained per thousand views", None, 1, "the end card and series promise"),
    ("ctr", "impressions click-through rate (long form)", "ctr", 4, "title and thumbnail"),
]


def checklist(st, pid, now_hours=48):
    """the 48-hour checklist for one post: each metric at 1, 24 and 48 hours, judged, with the action it points to"""
    p = st["posts"][pid]; med = medians(st, synthetic=bool(p.get("synthetic")))
    out = {"post": pid, "film": p.get("film"), "platform": p["platform"], "reads": {}}
    for h in (1, 24, 48):
        s = next((x for x in p.get("snapshots") or [] if abs(x["hours"] - h) <= max(1, h * 0.25)), None)
        out["reads"][f"{h}h"] = {k: s.get(k) for k in ("views", "likes", "shares", "saves", "comments", "subs")} if s else "not read yet"
    s = snapshot_at(p, 48) or {}
    v = s.get("views") or 0; per_k = lambda k: round(1000 * (s.get(k) or 0) / v, 2) if v else None
    vals = {"views_vs_median": round(v / med[p["platform"]], 2) if v and med.get(p["platform"]) else None, "stayed": s.get("stayed_pct"),
            "hold_3s": round(hold_at(p), 1) if hold_at(p) is not None else None, "avg_pct": s.get("avg_pct"),
            "shares_per_k": per_k("shares"), "saves_per_k": per_k("saves"), "comments_per_k": per_k("comments"), "subs_per_k": per_k("subs"), "ctr": s.get("ctr")}
    items = []
    for cid, label, _, good, action in CHECKS:
        val = vals.get(cid)
        if val is None:
            items.append({"check": cid, "what": label, "value": None, "state": "no data"}); continue
        ok = val >= (1.0 if cid == "views_vs_median" else good)
        items.append({"check": cid, "what": label, "value": val, "state": "ok" if ok else "attention", **({} if ok else {"action": action})})
    out["checks"] = items; out["attention"] = [i["check"] for i in items if i["state"] == "attention"]
    return out


def retention_map(p, shots, lines, duration_s=None):
    """the curve laid over shots and lines: percent lost and lost per second in each, against the curve's own smooth
    decay (a straight line through log retention after the hook) -> {shots, lines, worst}"""
    r = p.get("retention") or []
    if len(r) < 4:
        return {"error": "no retention curve for this post"}
    ts = [a for a, _ in r]; ys = [max(0.5, b) for _, b in r]

    def at(t):
        if t <= ts[0]:
            return ys[0]
        for (t0, a), (t1, b) in zip(zip(ts, ys), zip(ts[1:], ys[1:])):
            if t0 <= t <= t1:
                return a + (b - a) * (t - t0) / ((t1 - t0) or 1)
        return ys[-1]
    after = [(t, math.log(y)) for t, y in zip(ts, ys) if t >= 3]
    if len(after) >= 2:
        n = len(after); mt = sum(t for t, _ in after) / n; my = sum(y for _, y in after) / n
        slope = sum((t - mt) * (y - my) for t, y in after) / (sum((t - mt) ** 2 for t, _ in after) or 1)
    else:
        slope = 0.0
    def seg(a, b, label, kind):
        a, b = max(a, ts[0]), min(b, ts[-1])
        if b <= a:
            return None
        ya, yb = at(a), at(b); lost = ya - yb; exp_lost = ya * (1 - math.exp(slope * (b - a)))
        return {"kind": kind, "what": label, "from_s": round(a, 2), "to_s": round(b, 2), "start_pct": round(ya, 1), "lost_pct": round(lost, 1),
                "lost_per_s": round(lost / (b - a), 2), "vs_expected": round(lost - exp_lost, 1)}
    S = [x for x in (seg(sh["start"], sh["end"], sh["id"], "shot") for sh in shots) if x]
    L = [x for x in (seg(l["start"], l["end"], f"{l['id']}: {l.get('text', '')[:60]}", "line") for l in lines) if x]
    worst = sorted(S + L, key=lambda x: -x["vs_expected"])[:3]
    return {"hold_3s": round(at(3.0), 1), "decay_per_s": round(-slope * 100, 2), "shots": S, "lines": L, "worst": worst}


def perf(st, synthetic=False, quarters=None):
    """per calendar row (date): mean over its platforms of log2(48-hour views / the platform's median), with features"""
    med = medians(st, synthetic=synthetic); rows = defaultdict(list); feat = {}
    for p in st["posts"].values():
        if bool(p.get("synthetic")) != synthetic or (quarters and p.get("quarter") not in quarters):
            continue
        s = snapshot_at(p, 48)
        if not s or not s.get("views") or not med.get(p["platform"]):
            continue
        rows[p["date"]].append(math.log2(s["views"] / med[p["platform"]]))
        feat[p["date"]] = {**{k: p.get(k) for k in ("idea", "title", *FEATURES)}, "local": str(bool(p.get("local")))}
    return {d: {**feat[d], "perf": round(sum(v) / len(v), 3), "platforms": len(v)} for d, v in rows.items()}


def effects(rows, lam=K_SHRINK):
    """each feature value's effect on performance, all estimated together (ridge regression on one-hot features with
    an intercept: lam acts like that many pseudo-posts pulling each effect toward zero), so features that travel
    together (most local stories in one field, say) are told apart; with the raw mean of its posts for reference"""
    import numpy as np
    keys = sorted({(f, str(r[f])) for r in rows.values() for f in FEATURES if r.get(f) is not None})
    if not rows or not keys:
        return {}
    idx = {k: n for n, k in enumerate(keys)}; R = list(rows.values())
    X = np.zeros((len(R), len(keys) + 1)); y = np.array([r["perf"] for r in R]); X[:, -1] = 1.0
    for a, r in enumerate(R):
        for f in FEATURES:
            if r.get(f) is not None:
                X[a, idx[(f, str(r[f]))]] = 1.0
    P = np.eye(len(keys) + 1) * lam; P[-1, -1] = 1e-6   # the intercept is not shrunk
    beta = np.linalg.solve(X.T @ X + P, X.T @ y)
    out = {}
    for (f, v), n in idx.items():
        xs = [r["perf"] for r in R if str(r.get(f)) == v]
        out[f"{f}={v}"] = {"feature": f, "value": v, "n": len(xs), "mean": round(sum(xs) / len(xs), 3), "effect": round(float(beta[n]), 3)}
    return out


def idea_features(idea):
    """the features an idea has before it is placed (its row's role, the series slot, comes with the calendar)"""
    return {"field": idea.get("field"), "sweep": idea.get("sweep"), "format": idea.get("format", "explainer"), "local": str(bool(idea.get("local")))}


def score_idea(idea, eff, base=3.0):
    """-> (score, [contributions]) from the measured effects of the idea's features"""
    parts = []
    for f, v in idea_features(idea).items():
        e = eff.get(f"{f}={v}")
        if e and round(0.5 * e["effect"], 2):
            parts.append({"feature": f, "value": v, "points": round(0.5 * e["effect"], 2), "posts": e["n"], "mean_vs_median": round(2 ** e["mean"], 2)})
    s = max(0.0, min(8.0, base + sum(p["points"] for p in parts)))   # wide bounds: a clamp would make different ideas look alike
    return round(s, 2), parts


def explain(parts):
    if not parts:
        return "no measured posts share its features: base score"
    return "; ".join(f"{'+' if p['points'] >= 0 else ''}{p['points']} {p['feature']} {p['value']} ({p['posts']} post{'s' if p['posts'] != 1 else ''}, {p['mean_vs_median']}x median views)"
                     for p in sorted(parts, key=lambda p: -abs(p["points"])))


def lessons(maps, min_lines=12):
    """what retention says for the next films (E11), from retention_map results with each line's words per second:
    hook hold by format, and how losing viewers in a line goes with its pace (a least-squares line through lost per
    second against words per second, with its correlation); a pacing note only when the correlation is clear (r >= 0.4)
    and there are enough lines"""
    hold = defaultdict(list); pts = []
    for m in maps:
        if m.get("hold_3s") is not None:
            hold[m.get("format") or "?"].append(m["hold_3s"])
        for l in m.get("lines", []):
            if l.get("wps"):
                pts.append((l["wps"], l["lost_per_s"]))
    out = {"hook_hold_by_format": {k: {"posts": len(v), "mean_hold_3s": round(sum(v) / len(v), 1)} for k, v in hold.items()}, "lines": len(pts)}
    if len(pts) >= min_lines:
        n = len(pts); mx = sum(x for x, _ in pts) / n; my = sum(y for _, y in pts) / n
        sxx = sum((x - mx) ** 2 for x, _ in pts); syy = sum((y - my) ** 2 for _, y in pts); sxy = sum((x - mx) * (y - my) for x, y in pts)
        slope = sxy / sxx if sxx else 0.0; r = sxy / math.sqrt(sxx * syy) if sxx and syy else 0.0
        out["pace"] = {"slope_pct_per_s_per_wps": round(slope, 3), "r": round(r, 2), "mean_wps": round(mx, 2)}
        if r >= 0.4:
            fast = sorted(x for x, _ in pts)[int(0.75 * n)]
            out["advice"] = f"lines faster than about {fast:.1f} words a second lose viewers faster here ({slope:+.2f} percent a second per extra word a second, r = {r:.2f}): slow them or split them"
        elif r <= -0.4:
            out["advice"] = f"slower lines lose more viewers here (r = {r:.2f}): tighten the slow ones"
    best = max(out["hook_hold_by_format"].items(), key=lambda kv: kv[1]["mean_hold_3s"], default=None)
    if best and len(out["hook_hold_by_format"]) > 1:
        out["hook_advice"] = f"openings of the {best[0]} format hold best at 3 s ({best[1]['mean_hold_3s']}%)"
    return out


# ---------------- experiments and polls ----------------
def _beta_p_better(a_succ, a_n, b_succ, b_n, draws=20000, seed=7):
    """P(B's rate > A's) under Beta(1+s, 1+n-s) posteriors (Monte Carlo, seeded)"""
    import random
    rnd = random.Random(seed); w = 0
    for _ in range(draws):
        if rnd.betavariate(1 + b_succ, 1 + b_n - b_succ) > rnd.betavariate(1 + a_succ, 1 + a_n - a_succ):
            w += 1
    return w / draws


def compare_hooks(st, variants, metric="hold_3s"):
    """variants: {name: post_id}. Hook hold (retention at 3 s) as a share of each post's viewers -> P(each beats the
    first) and a winner when that is at least 0.95"""
    names = list(variants); res = {}
    for n in names:
        p = st["posts"][variants[n]]; s = snapshot_at(p, 48) or {}; v = int(s.get("views") or 0)
        rate = (hold_at(p) if metric == "hold_3s" else s.get("stayed_pct")) or 0
        res[n] = {"post": variants[n], "viewers": v, "rate_pct": round(rate, 1), "successes": int(round(v * rate / 100))}
    a = res[names[0]]; best, bp = names[0], 0.0
    for n in names[1:]:
        p_ = _beta_p_better(a["successes"], a["viewers"], res[n]["successes"], res[n]["viewers"]); res[n]["p_beats_" + names[0]] = round(p_, 3)
        if p_ >= 0.95 and p_ > bp:
            best, bp = n, p_
        if p_ <= 0.05:
            res[n]["worse"] = True
    decided = best != names[0] or all(r.get("worse") for k, r in res.items() if k != names[0])
    return {"metric": metric, "variants": res, "winner": best if decided else None, "decided": decided}


POLL_LIMITS = {"youtube": (2, 5, 65), "x": (2, 4, 25), "instagram": (2, 2, 24), "linkedin": (2, 4, 30), "facebook": (2, 4, 100)}   # min, max options, characters


def make_poll(titles, platform):
    """a poll between a film's true titles (titles.json entries whose checks passed), within the platform's limits"""
    lo, hi, n = POLL_LIMITS[platform]
    opts = [t["text"] for t in titles.get("titles", []) if (t.get("checks") or {}).get("ok", True) and len(t["text"]) <= n][:hi]
    if len(opts) < lo:
        return {"error": f"{len(opts)} true title(s) fit {platform}'s {n}-character options; it needs {lo}"}
    return {"platform": platform, "question": "Which title would make you watch?", "options": opts}


def poll_result(options, counts, draws=20000, seed=11):
    """P(each option is the most preferred) under a Dirichlet(1 + counts) posterior; decided at 0.9"""
    import random
    rnd = random.Random(seed); wins = [0] * len(options)
    for _ in range(draws):
        g = [rnd.gammavariate(1 + c, 1) for c in counts]; wins[g.index(max(g))] += 1
    pb = [round(w / draws, 3) for w in wins]; i = pb.index(max(pb))
    return {"options": options, "counts": counts, "p_best": pb, "winner": options[i] if pb[i] >= 0.9 else None, "total": sum(counts)}


# ---------------- business ----------------
def business(st, synthetic=False, months_ahead=24, half_life_months=6.0):
    """revenue by platform and country, RPM, and catalogue value: the last complete month's revenue carried forward
    with a decay (its half-life from the last two complete months when revenue fell between them, else
    `half_life_months`): a rough value, since new posts keep adding to later months"""
    plat, geo, films = defaultdict(lambda: {"views": 0, "revenue": 0.0}), defaultdict(lambda: {"views": 0, "revenue": 0.0}), defaultdict(float)
    monthly = defaultdict(float)
    for p in st["posts"].values():
        if bool(p.get("synthetic")) != synthetic:
            continue
        s = (p.get("snapshots") or [None])[-1]
        if not s:
            continue
        plat[p["platform"]]["views"] += s.get("views") or 0; plat[p["platform"]]["revenue"] += s.get("revenue") or 0
        films[p.get("film") or p.get("title") or p["date"]] += s.get("revenue") or 0
        for c, g in (p.get("geo") or {}).items():
            geo[c]["views"] += g.get("views") or 0; geo[c]["revenue"] += g.get("revenue") or 0
        prev = 0.0   # revenue by calendar month, from consecutive snapshots
        for x in p.get("snapshots") or []:
            r = x.get("revenue") or 0; monthly[x["at"][:7]] += r - prev; prev = r
    rpm = {k: round(1000 * v["revenue"] / v["views"], 2) if v["views"] else None for k, v in plat.items()}
    ms = sorted(monthly)
    full = ms[:-1]   # the month of the latest read is not over: only complete months set the base and the decay
    hl = half_life_months
    if len(full) >= 2 and monthly[full[-2]] > monthly[full[-1]] > 0:
        hl = round(math.log(2) / math.log(monthly[full[-2]] / monthly[full[-1]]), 1)
    last = monthly[full[-1]] if full else (monthly[ms[-1]] if ms else 0.0)
    k = 0.5 ** (1 / hl); value = sum(last * k ** m for m in range(1, months_ahead + 1))
    return {"by_platform": {k: {**v, "revenue": round(v["revenue"], 2), "rpm": rpm[k]} for k, v in plat.items()},
            "by_country": dict(sorted(((c, {**v, "revenue": round(v["revenue"], 2)}) for c, v in geo.items()), key=lambda x: -x[1]["revenue"])),
            "by_month": {m: round(monthly[m], 2) for m in ms}, "top_films": sorted(((f, round(r, 2)) for f, r in films.items()), key=lambda x: -x[1])[:10],
            "total_revenue": round(sum(v["revenue"] for v in plat.values()), 2), "catalogue_value": {"next_months": months_ahead, "half_life_months": hl, "value": round(value, 2)}}


# ---------------- a simulator for tests and rehearsals (numbers marked synthetic) ----------------
def simulate(posts, effects_true, seed=3, base_views=2000, noise=0.35):
    """synthetic exports for posts: 48-hour views = base x 2^(sum of true effects + noise); for tests and rehearsals
    of the pipeline only (every record is marked synthetic)"""
    import random
    rnd = random.Random(seed); csvs = defaultdict(list)
    for pid, p in sorted(posts.items()):
        e = sum(effects_true.get(f"{f}={p.get(f) if f != 'local' else str(bool(p.get('local')))}", 0.0) for f in FEATURES)
        v48 = int(base_views * 2 ** (e + rnd.gauss(0, noise)) * {"youtube": 1.0, "tiktok": 1.4, "instagram": 0.7}.get(p["platform"], 1.0))
        for h, frac in ((1, 0.12), (24, 0.7), (48, 1.0)):
            v = int(v48 * frac)
            csvs[(p["platform"], h)].append({"Video link": p["url"], "Video title": p.get("title") or "", "Views": f"{v:,}", "Likes": str(int(v * 0.05)),
                                             "Comments": str(int(v * 0.004)), "Shares": str(int(v * 0.006)), "Saves": str(int(v * 0.005)),
                                             "Subscribers": str(int(v * 0.0012)), "Average percentage viewed (%)": f"{68 + 6 * e:.1f}",
                                             "Stayed to watch (%)": f"{62 + 5 * e:.1f}", "Estimated revenue (USD)": f"{v / 1000 * 0.06:.2f}"})
    out = {}
    for (plat, h), rows in csvs.items():
        b = io.StringIO(); w = csv.DictWriter(b, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows); out[(plat, h)] = b.getvalue()
    return out
