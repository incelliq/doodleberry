"""Pipeline film session (plan 3.7): rebuilds an existing film through every gate, in its own workspace and branch,
reporting to the production orchestrator at each checkpoint and doing what the answers say.

    python tools/film_agent.py FILM [--fail-at first_render]   (started by prod.launch, cwd = workspace)

Steps: research gate -> research checkpoint; voice (if the workspace has none) and the first shot -> first_render
checkpoint; the full render with QA -> final checkpoint (one round of film.heal if QA fails, then report again);
a builder entry in the ledger; commit on the film's branch. An answer with continue=false ends the session;
instructions (the owner narrowing the scope) are logged, and are already in the film's brief. --fail-at makes a
step fail on purpose, for tests of the orchestrator.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

PY = sys.executable


def dbe(cmd, args):
    r = subprocess.run([PY, "-m", "dbe", cmd, json.dumps(args)], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"{cmd} failed: {(r.stderr or r.stdout)[-800:]}")
    return json.loads(r.stdout)


def say(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def checkpoint(film, stage, report):
    ans = dbe("prod.checkpoint", {"film": film, "stage": stage, "report": report})
    say(f"checkpoint {stage}: {ans['verdict']}", "; ".join(ans.get("reasons") or []))
    for ins in ans.get("instructions") or []:
        say("owner instruction:", ins)
    if not ans.get("continue"):
        say("the orchestrator says stop here"); sys.exit(0)
    return ans


def main():
    film = sys.argv[1]
    fail_at = sys.argv[sys.argv.index("--fail-at") + 1] if "--fail-at" in sys.argv else None
    fd = Path("films") / film
    say("research gate"); rc = dbe("research.check", {"name": film})
    ans = checkpoint(film, "research", {"contradictions": [], "errors": len(rc.get("errors", []))})
    if ans["verdict"] == "blocked":
        say("the research gate fails, and this session cannot write research: stopping"); sys.exit(1)
    if fail_at == "first_render":
        raise SystemExit("seeded failure before the first render")
    if not (fd / "build" / "voice.wav").exists():
        say("voice"); dbe("voice.build", {"name": film})
    first = json.loads((fd / "shots.json").read_text())["shots"][0]["id"]
    say("first shot", first); dbe("shot.render", {"name": film, "shot": first})
    checkpoint(film, "first_render", {"shot": first})
    say("full render"); r = dbe("film.render", {"name": film})
    ans = checkpoint(film, "final", {"qa": r.get("qa")})
    if ans["verdict"] == "fail":
        say("QA fails: one round of film.heal"); dbe("film.heal", {"name": film, "rounds": 1})
        ans = checkpoint(film, "final", {"healed": True})
    dbe("ledger.add", {"name": film, "role": "builder", "verdict": "ready" if ans["verdict"] == "ready" else "needs work",
                       "notes": f"pipeline session (plan 3.7): {ans['verdict']}; " + "; ".join(ans.get("reasons") or [])})
    subprocess.run(["git", "add", str(fd)], check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode:
        subprocess.run(["git", "commit", "-q", "-m", f"film {film}: pipeline session checkpoints and ledger (plan 3.7)"], check=True)
    say("done:", ans["verdict"])


if __name__ == "__main__":
    main()
