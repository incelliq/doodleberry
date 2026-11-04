"""Render farm (WP-38): shots rendered by several workers from a shared queue, with a shared cache by content hash.

**The cache** (out/farm/cache/): a shot's render is stored under its content hash (`_shot_hash`: the resolved shot,
the film's size and fps, its puppets, clip libraries, lip-sync cues and the renderer code), with its frame keys. A
shot whose hash is in the cache is not rendered again by any worker, film or machine that shares the folder; the
render is copied in and marked fresh, so film.render skips it.

**The queue** (out/farm/runs/<run>/): one task per shot still to render, ordered by its estimated cost (render.estimate),
the dearest first so no worker is left with a long shot at the end. A worker claims a task by renaming its file into
its own folder (atomic on one filesystem: two workers never take the same shot), renders it, puts it in the cache and
records how long it took. Workers are processes (`python -m dbe farm.worker`), here each pinned to its own CPU core
to stand for one machine; on several machines they share the repository and out/farm over a network filesystem.
Pinned workers run with tools/farm/keep_affinity.c preloaded: SwiftShader (Chromium's software WebGL) pins its own
threads to core 0 upwards whatever cores the process may use, so without it every worker drew its 3D on core 0
(measured: each shot 1.8 times slower with three workers than with one).

**Assembly**: when the queue is empty, film.render runs as usual: every shot is fresh, so it only joins, mixes and
checks. Frames are identical to a single-machine render because a shot is rendered whole by the same code from the
same inputs (and the test compares them frame by frame).
"""
import json
import os
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FARM = ROOT / "out" / "farm"
CACHE = FARM / "cache"


def cache_get(key, mp4):
    c = CACHE / f"{key}.mp4"
    if not c.exists():
        return False
    shutil.copy(c, mp4)
    k = CACHE / f"{key}.keys.json"
    if k.exists():
        shutil.copy(k, Path(str(mp4) + ".keys.json"))
    return True


def cache_put(key, mp4):
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = CACHE / f".{key}.{os.getpid()}.mp4"; shutil.copy(mp4, tmp); os.replace(tmp, CACHE / f"{key}.mp4")
    k = Path(str(mp4) + ".keys.json")
    if k.exists():
        shutil.copy(k, CACHE / f"{key}.keys.json")


def make_queue(run, tasks):
    """tasks: [{film, shot, key, cost}] -> the run folder, tasks written dearest first"""
    q = FARM / "runs" / run
    shutil.rmtree(q, ignore_errors=True)
    for sub in ("todo", "doing", "done", "failed"):
        (q / sub).mkdir(parents=True)
    for i, t in enumerate(sorted(tasks, key=lambda t: -t["cost"])):
        (q / "todo" / f"{i:05d}_{t['film']}_{t['shot']}.json").write_text(json.dumps(t))
    return q


def claim(q, worker):
    """take the next task (lowest number = dearest) by renaming it into doing/: atomic, so never taken twice"""
    for f in sorted((q / "todo").glob("*.json")):
        dst = q / "doing" / f"{worker}__{f.name}"
        try:
            os.rename(f, dst)
        except FileNotFoundError:
            continue   # another worker took it first
        return dst
    return None


def finish(q, task_file, ok, rec):
    dst = q / ("done" if ok else "failed") / task_file.name
    dst.write_text(json.dumps({**json.loads(task_file.read_text()), **rec}))
    task_file.unlink()


def results(q):
    return [json.loads(f.read_text()) for f in sorted((q / "done").glob("*.json"))], [json.loads(f.read_text()) for f in sorted((q / "failed").glob("*.json"))]


def wait(procs, q, poll=2.0, timeout=7 * 3600):
    t0 = time.time()
    while any(p.poll() is None for p in procs):
        if time.time() - t0 > timeout:
            for p in procs:
                p.kill()
            raise TimeoutError("farm run timed out")
        time.sleep(poll)
    return [p.returncode for p in procs]
