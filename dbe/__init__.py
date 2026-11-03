"""Doodleberry engine (dbe): one backend for agents and people.

Every capability is a registered command with a JSON-in/JSON-out signature. The same registry is served as a CLI
(`python -m dbe CMD '{json}'`), an HTTP API with the Studio UI (`python -m dbe serve`), and an MCP server over stdio
(`python -m dbe mcp`), so an agent and a person always drive exactly the same operations.
"""
import inspect
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMMANDS = {}


def command(_cmd, /, **schema):
    """Register fn as command `name`. schema: param -> (json type, description[, default])."""
    def wrap(fn):
        COMMANDS[_cmd] = {"fn": fn, "doc": (inspect.getdoc(fn) or "").strip(), "schema": schema}
        return fn
    return wrap


# ---------- progress events (WP-20) ----------
# A long command reports how far it has got with progress(stage=..., ...). The HTTP server's async jobs collect the
# events (GET /api/jobs/<id>) and post each to a webhook when one was given; DBE_PROGRESS=stderr prints them for the CLI.
import contextvars
import os
import sys
import time

PROGRESS = contextvars.ContextVar("dbe_progress", default=None)


def progress(**ev):
    ev.setdefault("at", round(time.time(), 2))
    sink = PROGRESS.get()
    if sink:
        sink(ev)
    elif os.environ.get("DBE_PROGRESS") == "stderr":
        print(json.dumps(ev), file=sys.stderr, flush=True)


def call(name, args=None):
    if name not in COMMANDS:
        raise KeyError(f"unknown command {name}; try engine.commands")
    return COMMANDS[name]["fn"](**(args or {}))


def describe():
    out = []
    for name, c in sorted(COMMANDS.items()):
        props, req = {}, []
        for p, spec in c["schema"].items():
            typ, desc = spec[0], spec[1]
            props[p] = {"type": typ, "description": desc}
            if len(spec) < 3:
                req.append(p)
        out.append({"name": name, "description": c["doc"], "inputSchema": {"type": "object", "properties": props, "required": req}})
    return out


from . import commands  # noqa: E402,F401  (registers everything)
