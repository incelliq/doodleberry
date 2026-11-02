"""Posting with a human approval per post (plan 4.15, WP-08).

Nothing is posted without a person's approval of that post. The queue is machine-local, next to the production
registry (productions/posting.json, or $DBE_PRODUCTION/posting.json):

    queued -> approved (by a named person) -> exported (files and a reminder; a person posts it) -> posted (link)
                                            -> posted (a connector posted it, where platform terms allow)
    any state -> held (approval revoked, or the package no longer passes)

- **post.queue** makes one post per platform from a film's posting package (`film.package`: caption, title, cover per
  platform from `cover.make`, subtitles, posting flags) and its calendar row (date, channel). A film still flagged by
  `film.provenance`, or whose package checks fail (title not true of the film, no subtitles), is queued as blocked.
- **post.approve** records who approved which post and when. It refuses a blocked post, and a post with posting flags
  unless the approver accepts them by name (`accept_flags`).
- **post.run** handles every approved post that is due: a platform with a connector configured (posting connectors in
  the registry folder, never in git: credentials stay on the machine) is posted through it; every other platform gets
  an export folder (video, cover, caption, title, subtitles, audio tracks) and a calendar reminder (`reminder.ics`) for
  the person who posts it. Unapproved posts that are due are listed as held and never leave.
- **post.done** records the link a person posted (or a connector returned); when a calendar row's posts are all out,
  the row is marked posted in the plan (`plan.posted`, with every link).

Connectors: only a `dryrun` connector ships (it writes to a local outbox, for tests). Platform APIs (YouTube Data API
uploads, TikTok Content Posting API, Instagram Graph API for Reels, LinkedIn) need the owner's own app credentials
and, for some, an app review before public posting; until one is set up, export with a reminder is the route.
Multi-language audio: a film localised with `film.localize` (`<film>-<lang>`) adds its audio as an extra track on
platforms that take several audio tracks (YouTube), and is its own post elsewhere.
"""
import contextlib
import datetime as dt
import fcntl
import json
import re
import shutil
import subprocess
from pathlib import Path

from . import ROOT

MULTI_AUDIO = {"youtube"}


def qdir():
    from .production import reg_dir
    return reg_dir()


@contextlib.contextmanager
def queue(write=True):
    d = qdir(); d.mkdir(parents=True, exist_ok=True)
    with open(d / "posting.lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        f = d / "posting.json"
        q = json.loads(f.read_text()) if f.exists() else {"note": "posting queue (WP-08): one entry per post; machine-local", "posts": {}}
        yield q
        if write:
            tmp = f.with_suffix(".tmp"); tmp.write_text(json.dumps(q, indent=1)); tmp.replace(f)


def connectors():
    f = qdir() / "connectors.json"   # {platform: {"connector": "dryrun"}}; credentials live with the connector, on this machine
    return json.loads(f.read_text()) if f.exists() else {}


def now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def event(p, what, **kw):
    p.setdefault("history", []).append({"at": now().isoformat(), "what": what, **kw})


def localised(film):
    """films made from this one by film.localize: <film>-<lang> with a script language"""
    out = []
    for d in sorted((ROOT / "films").glob(f"{film}-*")):
        sc = d / "script.json"
        if sc.exists() and "--" not in d.name:
            lang = json.loads(sc.read_text()).get("lang")
            if lang and d.name == f"{film}-{lang}" and (d / "build" / "final.mp4").exists():
                out.append({"lang": lang, "film": d.name, "video": f"films/{d.name}/build/final.mp4"})
    return out


def make_posts(film, pkg, covers, post_at, row, flags):
    """one post per platform from a film's package"""
    out = {}
    for plat, v in pkg["posts"].items():
        pid = f"{post_at[:10]}-{film}-{plat}"
        cov = covers.get(f"master--{plat}") or pkg.get("cover")
        blocked = [k for k, ok in pkg["checks"].items() if not ok and k in ("title_true", "subtitles", "has_sources")]
        tracks = [{"lang": x["lang"], "video": x["video"]} for x in localised(film)] if plat in MULTI_AUDIO else []
        out[pid] = {"id": pid, "film": film, "platform": plat, "post_at": post_at, "row": row,
                    "video": f"films/{film}/{pkg['video']}", "cover": f"films/{film}/{cov}" if cov and not cov.startswith("films/") else cov,
                    "caption": v["caption"], "title": v.get("title"), "description": v.get("description"),
                    "subtitles": [f"films/{film}/{s}" for s in pkg.get("subtitles", [])], "audio_tracks": tracks,
                    "flags": flags, "blocked": blocked, "state": "blocked" if blocked else "queued"}
    return out


def ics(p, path):
    """a calendar reminder for the person who posts it, at the posting time, with a 30-minute alarm"""
    t = dt.datetime.fromisoformat(p["post_at"]).astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path.write_text("\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//doodleberry//posting//EN", "BEGIN:VEVENT",
        f"UID:{p['id']}@doodleberry", f"DTSTAMP:{now().strftime('%Y%m%dT%H%M%SZ')}", f"DTSTART:{t}",
        f"SUMMARY:Post {p['film']} on {p['platform']} (approved by {p['approval']['by']})",
        f"DESCRIPTION:Files in {path.parent}. Then: python -m dbe post.done '{{\"id\": \"{p['id']}\"\\, \"url\": \"...\"}}'",
        "BEGIN:VALARM", "TRIGGER:-PT30M", "ACTION:DISPLAY", f"DESCRIPTION:Post {p['film']} on {p['platform']}", "END:VALARM",
        "END:VEVENT", "END:VCALENDAR", ""]))


def export(p, out_root):
    d = out_root / p["post_at"][:10] / p["platform"] / p["film"]; d.mkdir(parents=True, exist_ok=True)
    files = []
    for k in ("video", "cover"):
        if p.get(k) and (ROOT / p[k]).exists():
            shutil.copy(ROOT / p[k], d / f"{k}{Path(p[k]).suffix}"); files.append(f"{k}{Path(p[k]).suffix}")
    for s in p.get("subtitles", []):
        if (ROOT / s).exists():
            shutil.copy(ROOT / s, d / Path(s).name); files.append(Path(s).name)
    for tr in p.get("audio_tracks", []):   # extra language tracks, as audio files for platforms that take several
        a = d / f"audio_{tr['lang']}.m4a"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(ROOT / tr["video"]), "-vn", "-c:a", "copy", str(a)], check=True)
        files.append(a.name)
    (d / "post.txt").write_text("\n\n".join(x for x in [f"Title: {p['title']}" if p.get("title") else "", p["caption"],
                                                       p.get("description") or "", "Upload the cover file; do not use the platform default."] if x) + "\n")
    files.append("post.txt")
    ics(p, d / "reminder.ics"); files.append("reminder.ics")
    return d, files


def dryrun_post(p, out_root):
    """the test connector: 'posts' to a local outbox and returns a link to it"""
    d = out_root / "_dryrun_outbox" / p["platform"]; d.mkdir(parents=True, exist_ok=True)
    (d / f"{p['id']}.json").write_text(json.dumps({k: p[k] for k in ("film", "platform", "post_at", "caption", "title", "video", "cover")}, indent=1))
    return f"dryrun://{p['platform']}/{p['id']}"


CONNECTORS = {"dryrun": dryrun_post}


def row_posts(q, row):
    return [p for p in q["posts"].values() if p.get("row") and p["row"]["quarter"] == row["quarter"] and p["row"]["date"] == row["date"]
            and p["row"].get("channel") == row.get("channel")]


def self_test(tmp):
    """on a throwaway queue and plan: approvals need a name, a blocked post cannot be approved and a flagged one only
    with the flags accepted; nothing unapproved leaves; approved posts are exported with a reminder or posted through
    a connector at their time; links close the calendar row"""
    import os
    from . import commands as C
    fails, got = [], {}
    tmp = Path(tmp); shutil.rmtree(tmp, ignore_errors=True); (tmp / "plan" / "channels" / "t").mkdir(parents=True)
    media = ROOT / "out" / "postingtest"; shutil.rmtree(media, ignore_errors=True); media.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=270x480:rate=30:duration=1", "-pix_fmt", "yuv420p", str(media / "v.mp4")], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(media / "v.mp4"), "-frames:v", "1", str(media / "c.png")], check=True)
    (media / "c.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n")
    ch = {"name": "t", "audience": "a", "fields": ["f"], "locale": "x", "languages": ["en"], "post_time": "18:30", "timezone": "Asia/Colombo",
          "rules": {"post_days": ["mon"], "series": {"day": "mon", "name": "S", "sweeps": ["evergreen"], "format": "x"}}}
    (tmp / "plan" / "channels" / "t" / "channel.json").write_text(json.dumps(ch))
    (tmp / "plan" / "channels" / "t" / "ideas.json").write_text(json.dumps({"ideas": [{"id": "I1", "title": "T", "status": "planned"}]}))
    (tmp / "plan" / "channels" / "t" / "2027-Q1.json").write_text(json.dumps({"quarter": "2027-Q1", "rows": [{"date": "2027-01-04", "idea": "I1", "title": "T"}]}))
    (tmp / "plan" / "channels.json").write_text(json.dumps({"default": "t"}))
    (tmp / "prod").mkdir(); (tmp / "prod" / "connectors.json").write_text(json.dumps({"youtube": {"connector": "dryrun"}}))
    old = {k: os.environ.get(k) for k in ("DBE_PLAN", "DBE_PRODUCTION")}
    os.environ["DBE_PLAN"] = str(tmp / "plan"); os.environ["DBE_PRODUCTION"] = str(tmp / "prod")
    try:
        pkg = {"video": "x", "cover": "x", "subtitles": [], "checks": {"title_true": True, "subtitles": True, "has_sources": True},
               "posts": {"tiktok": {"caption": "c"}, "youtube": {"caption": "c", "title": "T", "description": "d"}}}
        row = {"quarter": "2027-Q1", "date": "2027-01-04", "channel": "t", "title": "T"}
        posts = make_posts("ok-film", pkg, {}, "2027-01-04T18:30:00+05:30", row, [])
        bad = make_posts("bad-film", {**pkg, "checks": {**pkg["checks"], "title_true": False}}, {}, "2027-01-04T18:30:00+05:30", None, [])
        flagged = make_posts("flag-film", pkg, {}, "2027-01-05T18:30:00+05:30", None, ["voice x is restricted, not clean"])
        late = make_posts("late-film", pkg, {}, "2027-01-04T18:30:00+05:30", None, [])
        for ps in (posts, bad, flagged, late):
            for p in ps.values():
                p.update(video="out/postingtest/v.mp4", cover="out/postingtest/c.png", subtitles=["out/postingtest/c.srt"])
        with queue() as q:
            for ps in (posts, bad, flagged, late):
                q["posts"].update(ps)

        def err(fn, **kw):
            try:
                fn(**kw); return None
            except Exception as e:
                return type(e).__name__
        got["no_name"] = err(C.post_approve, film="ok-film", date="2027-01-04", by=" ")
        got["blocked"] = err(C.post_approve, film="bad-film", date="2027-01-04", by="owner")
        got["flags_unaccepted"] = err(C.post_approve, film="flag-film", date="2027-01-05", by="owner")
        got["flags_accepted"] = err(C.post_approve, film="flag-film", date="2027-01-05", by="owner", accept_flags=True)
        if got["no_name"] != "ValueError" or got["blocked"] != "PermissionError" or got["flags_unaccepted"] != "PermissionError" or got["flags_accepted"]:
            fails.append(f"approval gate: {got}")
        C.post_approve(film="ok-film", date="2027-01-04", by="owner")
        early = C.post_run(at="2027-01-04T12:00:00+00:00")   # 17:30 in Colombo: not yet due
        if early["exported"] or early["posted"]:
            fails.append(f"posted before its time: {early}")
        r = C.post_run(at="2027-01-04T13:01:00+00:00")
        got["run"] = {"exported": [x["id"] for x in r["exported"]], "posted": r["posted"], "held": [x["id"] for x in r["held"]], "blocked": [x["id"] for x in r["blocked"]]}
        if got["run"]["posted"] != ["2027-01-04-ok-film-youtube"] or [x["id"] for x in r["exported"]] != ["2027-01-04-ok-film-tiktok"]:
            fails.append(f"due approved posts: {got['run']}")
        if sorted(got["run"]["held"]) != ["2027-01-04-late-film-tiktok", "2027-01-04-late-film-youtube"] or len(got["run"]["blocked"]) != 2:
            fails.append(f"unapproved or blocked posts left the queue: {got['run']}")
        ex = ROOT / r["exported"][0]["folder"] if r["exported"] else None
        ics_txt = (ex / "reminder.ics").read_text() if ex and (ex / "reminder.ics").exists() else ""
        if not ex or not (ex / "video.mp4").exists() or "DTSTART:20270104T130000Z" not in ics_txt or "approved by owner" not in ics_txt:
            fails.append("export folder or reminder")
        got["held_done"] = err(C.post_done, id="2027-01-04-late-film-tiktok", url="https://example.invalid/x")
        if got["held_done"] != "PermissionError":
            fails.append("an unapproved post was marked posted")
        d = C.post_done(id="2027-01-04-ok-film-tiktok", url="https://example.invalid/tiktok/1")
        cal = json.loads((tmp / "plan" / "channels" / "t" / "2027-Q1.json").read_text())
        got["row"] = cal["rows"][0].get("posted")
        if not d["rows_posted"] or sorted((got["row"] or {}).get("links", {})) != ["tiktok", "youtube"]:
            fails.append(f"the calendar row was not closed with both links: {got['row']}")
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(media, ignore_errors=True); shutil.rmtree(ROOT / "out" / "posting" / "2027-01-04", ignore_errors=True)
        shutil.rmtree(ROOT / "out" / "posting" / "_dryrun_outbox", ignore_errors=True)
    return fails, got
