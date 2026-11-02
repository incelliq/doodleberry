"""Production orchestrator (plan 3.7): many films in flight at once, each in its own session, workspace and branch,
reporting at checkpoints, with the owner approving at the end.

    prod.plan      a film, its posting date and runner          -> registry entry (state planned)
    prod.launch    start planned films (at most max_parallel at once; the rest queue)
                   each gets a git worktree on branch film/<name> and a session:
                     pipeline  tools/film_agent.py: research gate, voice, first shot, full render, ledger, commit
                     claude    Claude Code headless (`claude -p`) with the director prompt and the protocol below
                     manual    nothing started: the protocol is written for any agent (e.g. a cloud session)
    prod.checkpoint  sessions report research | first_render | final; the orchestrator measures for itself in the
                   film's workspace (research.check, the shot file, qa.json, the ledger) and answers with a verdict,
                   any owner instructions, and whether to continue
    prod.status    the board: states, verdicts, measurements, schedule against posting dates (and starts queued films)
    prod.stop / narrow / relaunch / decide / approve / merge   the owner's controls

Escalation: when the research contradicts the brief (a counter-evidence ledger entry that contradicts or blocks, or
contradictions in the session's own report) the film stops at the research checkpoint until the owner decides:
proceed, narrow (a written change of scope, added to the film's brief) or stop.
Merging needs the owner's approval of a final render that passed QA, and refuses a branch that touches anything
outside the film's own folder (and new characters under cast/drawn/).

The registry lives in DBE_PRODUCTION (default productions/, git-ignored: it holds machine-local paths, process ids
and copies of the renders for the board). Writes are serialised with a file lock, since sessions report concurrently.
"""
import contextlib
import datetime as dt
import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

from . import ROOT

STAGES = ["research", "first_render", "final"]
DEFAULTS = {"lead_days": {"research": 10, "first_render": 6, "final": 3, "approved": 1}, "max_parallel": 3,
            "runners": {"claude": ["claude", "-p", "{prompt}", "--permission-mode", "acceptEdits",
                                   "--allowedTools", "Bash(python -m dbe:*),Bash(git add:*),Bash(git commit:*),Read,Edit,Write,Glob,Grep"]}}
PY = os.environ.get("DBE_PY", sys.executable)


def reg_dir():
    return Path(os.environ.get("DBE_PRODUCTION") or ROOT / "productions")


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


@contextlib.contextmanager
def registry(write=True):
    d = reg_dir(); d.mkdir(parents=True, exist_ok=True)
    with open(d / "registry.lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        f = d / "registry.json"
        reg = json.loads(f.read_text()) if f.exists() else {"note": "production registry (plan 3.7); machine-local", "films": {}}
        for k, v in DEFAULTS.items():
            reg.setdefault(k, json.loads(json.dumps(v)))
        yield reg
        if write:
            tmp = f.with_suffix(".tmp"); tmp.write_text(json.dumps(reg, indent=1)); tmp.replace(f)


def event(e, what, **kw):
    e.setdefault("events", []).append({"at": now(), "what": what, **kw})


# ---------------------------------------------------------------- schedule
def schedule(e, lead, today):
    """next milestone and whether the film is on track for its posting date"""
    if e["state"] == "merged":
        return {"status": "done", "next": None}
    if e["state"] == "stopped":
        return {"status": "stopped", "next": None}
    post = dt.date.fromisoformat(e["post_on"])
    passed = {c["stage"] for c in e.get("checkpoints", []) if c["verdict"] in ("ok", "ready")}
    nxt = next((s for s in STAGES if s not in passed), None) or ("approved" if e["state"] != "approved" else None)
    if nxt is None:
        return {"status": "on_track" if today <= post else "late", "next": "merge", "due": post.isoformat()}
    due = post - dt.timedelta(days=lead.get(nxt, 0))
    status = "late" if today > due else "due_soon" if today >= due - dt.timedelta(days=1) else "on_track"
    if e["state"] == "escalated":
        status = "needs_owner"
    return {"status": status, "next": nxt, "due": due.isoformat(), "days_left": (due - today).days}


# ---------------------------------------------------------------- workspaces and sessions
def _git(*a, cwd=ROOT, check=True):
    r = subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(a[:3])}: {(r.stderr or r.stdout).strip()[-400:]}")
    return r.stdout.strip()


def workspace(film):
    """a git worktree on branch film/<name>, next to the repository"""
    ws = ROOT.parent / f"{ROOT.name}-films" / film
    if not (ws / ".git").exists():
        ws.parent.mkdir(parents=True, exist_ok=True)
        if _git("branch", "--list", f"film/{film}"):
            _git("worktree", "add", str(ws), f"film/{film}")
        else:
            _git("worktree", "add", "-b", f"film/{film}", str(ws), "HEAD")
    return ws


def protocol(e):
    """what any session is told: the brief, the checkpoints and how to report"""
    f = e["film"]
    return f"""# Production protocol for {f} (plan 3.7)

You produce the film in films/{f}/ in this workspace (branch film/{f}). Follow docs/director-prompt.md and the brief
in films/{f}/brief.md. It posts on {e['post_on']}.

Report at each checkpoint, then do what the answer says:

    python -m dbe prod.checkpoint '{{"film": "{f}", "stage": "research", "report": {{"contradictions": []}}}}'
    python -m dbe prod.checkpoint '{{"film": "{f}", "stage": "first_render", "report": {{"shot": "<first shot id>"}}}}'
    python -m dbe prod.checkpoint '{{"film": "{f}", "stage": "final", "report": {{}}}}'

- research: after the research gate (python -m dbe research.check). List anything in the sources that contradicts
  the brief under "contradictions"; the owner decides before you go on.
- first_render: after the first shot renders (python -m dbe shot.render).
- final: after python -m dbe film.render passes QA.
The answer has "verdict", "reasons", "instructions" (owner changes of scope: apply them) and "continue". If continue
is false, stop work and end the session. Commit your work on this branch (git add films/{f} && git commit); never
push, never merge, never edit outside films/{f}/ (new characters may go in cast/drawn/).
"""


def start(e, reg):
    """create the workspace and start the session for one film"""
    ws = workspace(e["film"]); e["workspace"] = str(ws); e["branch"] = f"film/{e['film']}"
    pd = ws / ".production"; pd.mkdir(exist_ok=True)
    (pd / "PRODUCTION.md").write_text(protocol(e))
    log = reg_dir() / e["film"] / "session.log"; log.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "DBE_PRODUCTION": str(reg_dir())}
    env.pop("DBE_FILM_AGENT_FAIL", None)
    if e["runner"] == "pipeline":
        cmd = [PY, "tools/film_agent.py", e["film"]] + (["--fail-at", e["seed_fail"]] if e.get("seed_fail") else [])
    elif e["runner"] == "claude":
        prompt = (pd / "PRODUCTION.md").read_text() + "\n\n" + (ROOT / "docs" / "director-prompt.md").read_text()
        cmd = [prompt if a == "{prompt}" else a for a in reg["runners"]["claude"]]
    else:
        e.update(state="running", session={"runner": "manual", "started": now(), "pid": None, "protocol": str(pd / "PRODUCTION.md")})
        event(e, "waiting for a session", protocol=str(pd / "PRODUCTION.md")); return
    with open(log, "ab") as lf:
        p = subprocess.Popen(cmd, cwd=ws, env=env, stdout=lf, stderr=subprocess.STDOUT, start_new_session=True)
    e.update(state="running", session={"runner": e["runner"], "started": now(), "pid": p.pid, "log": str(log)})
    event(e, "launched", runner=e["runner"], pid=p.pid)


def alive(pid):
    if not pid:
        return False
    try:
        st = Path(f"/proc/{pid}/stat").read_text().split(") ")[-1].split()[0]
    except OSError:
        return False
    if st == "Z":
        with contextlib.suppress(ChildProcessError, OSError):
            os.waitpid(pid, os.WNOHANG)
        return False
    return True


def kill(e):
    pid = (e.get("session") or {}).get("pid")
    if pid and alive(pid):
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(pid, signal.SIGTERM)


def tick(reg):
    """reap ended sessions and start queued films while there is room"""
    for e in reg["films"].values():
        s = e.get("session") or {}
        if e["state"] == "running" and s.get("pid") and not alive(s["pid"]):
            passed = {c["stage"] for c in e.get("checkpoints", []) if c["verdict"] in ("ok", "ready")}
            finals = [c for c in e.get("checkpoints", []) if c["stage"] == "final"]
            if "final" not in passed and finals:   # it rendered, but QA still fails after the session's own repairs
                e["state"] = "needs_work"; event(e, "session ended with a failing final render", reasons=finals[-1]["reasons"])
            elif "final" not in passed:
                tail = ""
                with contextlib.suppress(OSError):
                    tail = Path(s.get("log", "")).read_text(errors="replace")[-600:]
                e["state"] = "failed"; event(e, "session ended before the final checkpoint", log_tail=tail)
    running = sum(e["state"] == "running" for e in reg["films"].values())
    for e in sorted(reg["films"].values(), key=lambda e: (e["post_on"], e.get("priority", 1))):
        if e["state"] == "queued" and running < reg["max_parallel"]:
            start(e, reg); running += 1
    return reg


# ---------------------------------------------------------------- checkpoints
def _dbe(ws, cmd, args):
    env = {k: v for k, v in os.environ.items() if k != "DBE_PRODUCTION"}
    r = subprocess.run([PY, "-m", "dbe", cmd, json.dumps(args)], cwd=ws, capture_output=True, text=True, env=env, timeout=1800)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"error": (r.stderr or r.stdout)[-500:]}


def _keep(e, src, name):
    """copy a deliverable from the film's workspace to the registry, for the board"""
    dst = reg_dir() / e["film"] / name
    if Path(src).exists():
        shutil.copy(src, dst); return str(dst)
    return None


def measure(e, stage, report):
    """the orchestrator's own reading of a checkpoint -> (verdict, reasons, measured, escalate)"""
    ws, f = Path(e["workspace"]), e["film"]; fd = ws / "films" / f
    if stage == "research":
        rc = _dbe(ws, "research.check", {"name": f})
        ledger = json.loads((fd / "ledger.json").read_text()) if (fd / "ledger.json").exists() else []
        decided = max((d["at"] for d in e.get("decisions", []) if d["decision"] in ("proceed", "narrow")), default="")
        counter = [x for x in ledger if x.get("role") == "counter_evidence" and str(x.get("verdict", "")).lower() in ("contradicts", "blocked") and x.get("at", "") > decided]
        said = [] if decided else list(report.get("contradictions") or [])
        measured = {"errors": len(rc.get("errors", [])), "warnings": len(rc.get("warnings", [])), "facts": rc.get("facts")}
        if counter or said:
            return "escalate", [f"research contradicts the brief: {x.get('notes') or x}" for x in counter] + [f"session reports: {c}" for c in said], measured, True
        if rc.get("error") or rc.get("errors"):
            return "blocked", rc.get("errors") or [rc.get("error")], measured, False
        return "ok", [], measured, False
    if stage == "first_render":
        shot = report.get("shot") or "s1"; mp4 = fd / "build" / "shots" / f"{shot}.mp4"
        if not mp4.exists():
            return "fail", [f"no render at films/{f}/build/shots/{shot}.mp4"], {}, False
        pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate", "-of", "json", str(mp4)], capture_output=True, text=True)
        st = (json.loads(pr.stdout or "{}").get("streams") or [{}])[0]
        size = json.loads((fd / "shots.json").read_text()).get("size", [1080, 1920]) if (fd / "shots.json").exists() else [1080, 1920]
        measured = {"shot": shot, "width": st.get("width"), "height": st.get("height"), "fps": st.get("r_frame_rate")}
        still = reg_dir() / f / "first.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "0.5", "-i", str(mp4), "-frames:v", "1", "-vf", "scale=270:-2", str(still)], capture_output=True)
        if [st.get("width"), st.get("height")] != list(size):
            return "fail", [f"first shot is {st.get('width')}x{st.get('height')}, the film is {size[0]}x{size[1]}"], measured, False
        return "ok", [], measured, False
    if stage == "final":
        qf = fd / "build" / "qa.json"
        if not qf.exists():
            return "fail", ["no QA report: run film.render"], {}, False
        q = json.loads(qf.read_text()); checks = q.get("checks") or {}
        failing = sorted(k for k, v in checks.items() if v is False)
        ledger = json.loads((fd / "ledger.json").read_text()) if (fd / "ledger.json").exists() else []
        director = next((x for x in reversed(ledger) if x.get("role") == "director"), None)
        measured = {"duration_s": q.get("duration"), "loudness_lufs": q.get("loudness_lufs"), "true_peak_dbtp": q.get("true_peak_dbtp"),
                    "checks_passed": sum(v is True for v in checks.values()), "checks": len(checks), "failing": failing,
                    "layout_advisory": (q.get("layout") or {}).get("advisory_failures", []), "director": director and director.get("verdict")}
        _keep(e, fd / "build" / "final.mp4", "final.mp4"); _keep(e, qf, "qa.json")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1", "-i", str(fd / "build" / "final.mp4"), "-frames:v", "1", "-vf", "scale=270:-2", str(reg_dir() / f / "poster.jpg")], capture_output=True)
        if failing:
            return "fail", [f"QA fails: {', '.join(failing)}"], measured, False
        return "ready", [], measured, False
    raise ValueError(f"stage is one of {STAGES}")


def checkpoint(film, stage, report):
    with registry() as reg:
        e = reg["films"].get(film)
        if not e:
            raise KeyError(f"{film} is not in the production registry")
        if e["state"] in ("stopped", "merged"):
            return {"verdict": "stopped", "continue": False, "reasons": [f"the film is {e['state']}"], "instructions": []}
        snapshot = dict(e)
    verdict, reasons, measured, esc = measure(snapshot, stage, report or {})   # outside the lock: it can take a while
    with registry() as reg:
        e = reg["films"][film]
        e.setdefault("checkpoints", []).append({"stage": stage, "at": now(), "report": report or {}, "measured": measured, "verdict": verdict, "reasons": reasons})
        event(e, f"checkpoint {stage}: {verdict}")
        if esc:
            e["state"] = "escalated"; e["escalation"] = {"at": now(), "reasons": reasons}
        elif stage == "final" and verdict == "ready" and e["state"] == "running":
            e["state"] = "waiting_owner"
        inbox = [m for m in e.get("inbox", []) if not m.get("delivered")]
        for m in inbox:
            m["delivered"] = now()
        go = e["state"] in ("running", "waiting_owner") and verdict != "escalate"
        return {"verdict": verdict, "reasons": reasons, "measured": measured, "instructions": [m["text"] for m in inbox], "continue": go,
                "state": e["state"]}


# ---------------------------------------------------------------- owner controls
def narrow_brief(e, text):
    """the owner's change of scope goes into the film's brief in its workspace (the session commits it)"""
    b = Path(e["workspace"]) / "films" / e["film"] / "brief.md"
    if b.parent.exists():
        with open(b, "a") as fh:
            fh.write(f"\n\n## Narrowed by the owner ({now()[:10]})\n{text}\n")


def merge(e):
    """merge an approved film branch into the current branch, if it only touches the film (and new characters)"""
    br = f"film/{e['film']}"
    if alive((e.get("session") or {}).get("pid")):
        raise PermissionError(f"{e['film']}'s session is still running; merge once it has committed and ended")
    ws = e.get("workspace")
    if ws and Path(ws).exists():
        dirty = _git("status", "--porcelain", "--", f"films/{e['film']}", cwd=ws)
        if dirty:
            raise PermissionError(f"{e['film']}'s workspace has work that is not committed on {br}: {dirty.splitlines()[:4]}")
    changed = [p for p in _git("diff", "--name-only", f"HEAD...{br}").splitlines() if p]
    outside = [p for p in changed if not (p.startswith(f"films/{e['film']}/") or p.startswith("cast/drawn/"))]
    if outside:
        raise PermissionError(f"film/{e['film']} touches files outside the film: {outside[:6]}")
    if changed:
        _git("merge", "--no-ff", "-m", f"Merge film {e['film']} (approved by {e['approvals'][-1]['by']}, plan 3.7)", br)
    out = ROOT / "films" / e["film"] / "build"; out.mkdir(parents=True, exist_ok=True)
    for name in ("final.mp4", "qa.json"):   # the approved deliverables, next to the merged film data
        src = reg_dir() / e["film"] / name
        if src.exists():
            shutil.copy(src, out / name)
    return changed


# ---------------------------------------------------------------- self-test (python -m dbe test)
def self_test(scratch):
    """Run the orchestrator for real (git worktree, branch, checkpoints, owner controls, merge) on a throwaway clone
    of this repository with the working tree's files, using a manual session whose reports this test makes. Pure
    logic and git; renders are stand-ins (ffmpeg test patterns). -> (failures, measurements)"""
    import tempfile
    fails, got = [], {}
    base = Path(tempfile.mkdtemp(prefix="prodtest_", dir=scratch)); repo = base / "repo"
    _git("clone", "-q", str(ROOT), str(repo))
    files = _git("ls-files", "-co", "--exclude-standard").splitlines()
    for f in files:   # the working tree as it is now (uncommitted code included)
        src, dst = ROOT / f, repo / f
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dst)
    for a in (("add", "-A"), ("-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-q", "-m", "snapshot", "--allow-empty")):
        subprocess.run(["git", *a], cwd=repo, capture_output=True)
    env = {**os.environ, "DBE_PRODUCTION": str(repo / "productions"), "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
           "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}

    def run(cmd, args, cwd=repo):
        r = subprocess.run([PY, "-m", "dbe", cmd, json.dumps(args)], cwd=cwd, capture_output=True, text=True, env=env, timeout=600)
        if r.returncode:
            return {"error": (r.stderr or r.stdout).strip().splitlines()[-1]}
        return json.loads(r.stdout)

    def git(*a, cwd):
        return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, env=env)
    film = "direct-demo"; today = dt.date.today()
    try:
        run("prod.plan", {"film": film, "post_on": (today + dt.timedelta(days=12)).isoformat(), "runner": "manual"})
        run("prod.launch", {"film": film})
        ws = base / "repo-films" / film; fd = ws / "films" / film
        base_sha = git("rev-parse", "HEAD", cwd=ws).stdout.strip()
        if not (ws / ".production" / "PRODUCTION.md").exists() or git("rev-parse", "--abbrev-ref", "HEAD", cwd=ws).stdout.strip() != f"film/{film}":
            fails.append("launch: no workspace on its own branch with the protocol")
        a = run("prod.checkpoint", {"film": film, "stage": "research", "report": {}}); got["research"] = a.get("verdict")
        if a.get("verdict") != "ok":
            fails.append(f"research: {a}")
        led = json.loads((fd / "ledger.json").read_text()) if (fd / "ledger.json").exists() else []
        led.append({"at": now(), "round": 1, "role": "counter_evidence", "verdict": "contradicts", "notes": "the source says the opposite of the brief's hook"})
        (fd / "ledger.json").write_text(json.dumps(led))
        a = run("prod.checkpoint", {"film": film, "stage": "research", "report": {}})
        st = run("prod.status", {})
        got["escalation"] = {"verdict": a.get("verdict"), "continue": a.get("continue"), "board": st["films"][0]["schedule"]["status"]}
        if a.get("verdict") != "escalate" or a.get("continue") or st["films"][0]["state"] != "escalated":
            fails.append(f"escalation: {a}")
        run("prod.decide", {"film": film, "decision": "narrow", "note": "Drop the contested hook; open on the demo instead."})
        a = run("prod.checkpoint", {"film": film, "stage": "research", "report": {}})
        if a.get("verdict") != "ok" or not a.get("instructions") or "Narrowed by the owner" not in (fd / "brief.md").read_text():
            fails.append(f"narrow: {a}")
        (fd / "build" / "shots").mkdir(parents=True, exist_ok=True)
        tp = lambda out, size, secs=1: subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=size={size}:rate=30:duration={secs}",
                                                       "-f", "lavfi", "-i", "sine=duration=%d" % secs, "-shortest", "-pix_fmt", "yuv420p", str(out)], capture_output=True)
        tp(fd / "build" / "shots" / "s1.mp4", "540x960")
        a = run("prod.checkpoint", {"film": film, "stage": "first_render", "report": {"shot": "s1"}}); got["first_wrong_size"] = a.get("verdict")
        tp(fd / "build" / "shots" / "s1.mp4", "1080x1920")
        b = run("prod.checkpoint", {"film": film, "stage": "first_render", "report": {"shot": "s1"}}); got["first"] = b.get("verdict")
        if a.get("verdict") != "fail" or b.get("verdict") != "ok":
            fails.append(f"first render: {a.get('verdict')}, {b.get('verdict')}")
        tp(fd / "build" / "final.mp4", "1080x1920", 3)
        (fd / "build" / "qa.json").write_text(json.dumps({"duration": 3.0, "loudness_lufs": -14.2, "true_peak_dbtp": -1.3, "checks": {"size": True, "loudness": False}}))
        a = run("prod.checkpoint", {"film": film, "stage": "final", "report": {}})
        no = run("prod.approve", {"film": film, "by": "owner"})
        (fd / "build" / "qa.json").write_text(json.dumps({"duration": 3.0, "loudness_lufs": -14.0, "true_peak_dbtp": -1.3, "checks": {"size": True, "loudness": True}}))
        b = run("prod.checkpoint", {"film": film, "stage": "final", "report": {}})
        got["final"] = [a.get("verdict"), b.get("verdict")]
        if a.get("verdict") != "fail" or "error" not in no or b.get("verdict") != "ready":
            fails.append(f"final and approval gate: {a.get('verdict')}, approve-before-pass {no}, {b.get('verdict')}")
        run("prod.approve", {"film": film, "by": "owner"})
        un = run("prod.merge", {"film": film})   # the narrowed brief is not committed yet
        if "error" not in un or "not committed" not in un["error"]:
            fails.append(f"merge with uncommitted work: {un}")
        (ws / "README.md").write_text((ws / "README.md").read_text() + "\nstray edit\n")
        git("add", "-A", "films", "README.md", cwd=ws); git("commit", "-q", "-m", "film work plus a stray edit", cwd=ws)
        bad = run("prod.merge", {"film": film})
        if "error" not in bad or "outside the film" not in bad["error"]:
            fails.append(f"merge scope: {bad}")
        git("reset", "-q", "--soft", base_sha, cwd=ws); git("reset", "-q", "--", "README.md", cwd=ws); git("checkout", "--", "README.md", cwd=ws)
        git("commit", "-q", "-m", "film work only", cwd=ws)
        ok = run("prod.merge", {"film": film})
        got["merge"] = ok.get("files") or ok
        merged_brief = (repo / "films" / film / "brief.md").read_text()
        if ok.get("state") != "merged" or "Narrowed by the owner" not in merged_brief or not (repo / "films" / film / "build" / "final.mp4").exists():
            fails.append(f"merge: {ok}")
        sch = {}
        for days, want in ((12, "on_track"), (7, "due_soon"), (3, "late")):   # first shot due 6 days before posting   # a fresh plan against different posting dates
            e = {"state": "running", "post_on": (today + dt.timedelta(days=days)).isoformat(), "checkpoints": [{"stage": "research", "verdict": "ok"}]}
            sch[days] = schedule(e, DEFAULTS["lead_days"], today)["status"]
            if sch[days] != want:
                fails.append(f"schedule {days} days out: {sch[days]}, want {want}")
        got["schedule"] = sch
    finally:
        subprocess.run(["git", "worktree", "prune"], cwd=repo, capture_output=True)
        shutil.rmtree(base, ignore_errors=True)
    return fails, got
