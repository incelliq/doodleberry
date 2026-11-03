"""Team roles and permissions (WP-39): people and agent sessions with roles, assignments and locks on films and
characters, and an audit log of who changed what.

**Who is acting.** A person or an agent session is named by `DBE_AS` (the CLI and the MCP server read it from the
environment; the HTTP API from the `X-DBE-As` header): `"<id>"` acts in that person's first role, `"<id>:<role>"` in
one of their roles. team/people.json lists them: `{"people": {id: {"name", "roles": [...], "kind": "person" | "agent"}}}`.
With no people file and nobody named, the local user is the owner (one person working alone loses nothing), and
every change is still audited.

**Roles** (team/roles.json): each role is a set of command patterns (`puppet.*`, `film.render`), plus the read
commands everyone has (lists, checks, reports). `approve` names the commands that sign something off (a post, a
production checkpoint, a film's content credentials): only roles that list them may run them.

**Assignments and locks** (team/state.json, machine-local): a film (`film:<name>`) or a character
(`character:<puppet path>`) may be assigned to people, after which only they (and the owner and directors) may change
it; and it may be locked by one person while they work, after which nobody else may change it until it is unlocked
(the owner may break a lock). A command's target is read from its arguments: `name` for a film, `path`/`puppet` for a
character, a cast `id` through the cast library.

**Audit** (team/audit.jsonl, machine-local): every command that changes something is logged with when, who, which
role, how (cli, http, mcp), the command, its target, a digest of its arguments, and whether it ran, failed or was
refused. Read commands are not logged.
"""
import datetime as dt
import fnmatch
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

READ = ["*.list", "*.get", "*.check", "*.status", "*.info", "*.doctor", "*.commands", "*.validate", "*.verify", "*.report",
        "*.estimate", "*.bench_estimate", "*.lessons", "*.matrix", "*.disclosure", "*.strings", "*.text_check", "*.provenance",
        "*.diff", "*.whoami", "*.roles", "*.people", "*.audit", "*.continuity", "*.abilities", "*.channels", "*.business"]


def team_dir():
    return Path(os.environ.get("DBE_TEAM") or ROOT / "team")


def _j(p, default):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else default


def roles():
    return _j(team_dir() / "roles.json", None) or _j(ROOT / "team" / "roles.json", {"roles": {"owner": {"commands": ["*"]}}})


def people():
    return _j(team_dir() / "people.json", {"people": {}})["people"]


def state():
    return _j(team_dir() / "state.json", {"assignments": {}, "locks": {}})


def save_state(st):
    team_dir().mkdir(parents=True, exist_ok=True); (team_dir() / "state.json").write_text(json.dumps(st, indent=1) + "\n")


def is_read(cmd):
    return any(fnmatch.fnmatch(cmd, p) for p in READ)


def actor(named=None, via="cli"):
    """-> {id, name, role, via}; named: "<id>" or "<id>:<role>" (else DBE_AS); refuses an unknown person or a role they lack"""
    named = named if named is not None else os.environ.get("DBE_AS", "")
    ppl = people()
    if not named:
        if ppl and os.environ.get("DBE_TEAM_STRICT"):
            raise PermissionError("say who is acting (DBE_AS or X-DBE-As): this project lists its people")
        return {"id": "local", "name": "local user", "role": "owner", "via": via}
    pid, _, role = named.partition(":")
    p = ppl.get(pid)
    if not p:
        raise PermissionError(f"{pid!r} is not in team/people.json")
    role = role or p["roles"][0]
    if role not in p["roles"]:
        raise PermissionError(f"{pid} does not have the {role} role (has {', '.join(p['roles'])})")
    return {"id": pid, "name": p.get("name", pid), "role": role, "via": via, "kind": p.get("kind", "person")}


def allowed(role, cmd):
    r = roles()["roles"].get(role)
    if r is None:
        return False, f"no role {role!r} in team/roles.json"
    pats = r.get("commands", [])
    if any(fnmatch.fnmatch(cmd, p) for p in r.get("never", [])):
        return False, f"the {role} role may not run {cmd}"
    if cmd in roles().get("approve", []) and cmd not in r.get("approve", []) and "*" not in pats:
        return False, f"{cmd} signs something off; the {role} role cannot"
    if is_read(cmd) or any(fnmatch.fnmatch(cmd, p) for p in pats):
        return True, ""
    return False, f"the {role} role does not include {cmd}"


def target(cmd, args):
    """film:<name> or character:<puppet path> a command changes, from its arguments (None if neither)"""
    a = args or {}
    if cmd.startswith(("cast.", "puppet.", "doodle.", "level.", "pack.")) or a.get("puppet"):
        p = next((v for v in (a.get("path"), a.get("puppet"), a.get("source")) if isinstance(v, str) and v), None)
        if not p and a.get("id"):
            cast = {e["id"]: e["path"] for e in _j(ROOT / "cast" / "index.json", {"puppets": []})["puppets"]}
            p = cast.get(a["id"])
        if p:
            return f"character:{p}"
    n = a.get("name") or a.get("film")
    if isinstance(n, str) and (ROOT / "films" / n).is_dir():
        return f"film:{n}"
    return None


def check_target(who, cmd, tgt):
    if not tgt or is_read(cmd):
        return
    st = state(); lk = st["locks"].get(tgt)
    if lk and lk["by"] != who["id"] and not (who["role"] == "owner" and cmd == "team.unlock"):
        raise PermissionError(f"{tgt} is locked by {lk['by']} since {lk['at']} ({lk.get('why', '')}); ask them, or the owner, to unlock it")
    asg = st["assignments"].get(tgt)
    if asg and who["id"] not in asg and who["role"] not in ("owner", "director"):
        raise PermissionError(f"{tgt} is assigned to {', '.join(asg)}")


def audit(entry):
    team_dir().mkdir(parents=True, exist_ok=True)
    with open(team_dir() / "audit.jsonl", "a") as f:
        f.write(json.dumps({"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), **entry}, default=str) + "\n")


def _digest(args):
    out = {}
    for k, v in (args or {}).items():
        s = v if isinstance(v, (int, float, bool)) or v is None else json.dumps(v, default=str, ensure_ascii=False)
        out[k] = s if not isinstance(s, str) or len(s) <= 120 else s[:117] + "..."
    return out


def guarded(cmd, args, run, named=None, via="cli"):
    """run a command as the acting person: the role, the target's lock and assignment, then the audit"""
    tgt = target(cmd, args)
    try:
        who = actor(named, via)
    except PermissionError as e:   # an unknown person, or a role they lack: refused, and logged
        audit({"who": (named if named is not None else os.environ.get("DBE_AS", "")) or "?", "role": None, "via": via, "command": cmd,
               **({"target": tgt} if tgt else {}), "args": _digest(args), "result": "refused", "why": str(e)})
        raise
    base = {"who": who["id"], "role": who["role"], "via": via, "command": cmd, **({"target": tgt} if tgt else {})}
    ok, why = allowed(who["role"], cmd)
    try:
        if not ok:
            raise PermissionError(why)
        check_target(who, cmd, tgt)
    except PermissionError as e:
        audit({**base, "args": _digest(args), "result": "refused", "why": str(e)})
        raise
    if is_read(cmd):
        return run()
    try:
        from . import ACTOR
        tok = ACTOR.set(who)
        try:
            res = run()
        finally:
            ACTOR.reset(tok)
    except Exception as e:
        audit({**base, "args": _digest(args), "result": "failed", "why": str(e)[:300]})
        raise
    audit({**base, "args": _digest(args), "result": "ok"})
    return res
