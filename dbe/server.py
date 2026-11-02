"""HTTP API + Studio UI, and an MCP server over stdio. Both expose exactly the command registry."""
import hashlib
import json
import mimetypes
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import ROOT, call, describe

STUDIO = Path(__file__).parent / "studio" / "index.html"
JOBS, LOCK = {}, threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, default=str).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def log_message(self, *a):
        pass

    def do_GET(self):
        p = self.path.split("?")[0]
        if p in ("/", "/studio"):
            return self._send(200, STUDIO.read_bytes(), "text/html; charset=utf-8")
        if p == "/timeline":   # plan 3.1: lanes, live scrub, drag to re-time
            return self._send(200, (STUDIO.parent / "timeline.html").read_bytes(), "text/html; charset=utf-8")
        if p == "/review":     # plan 3.4: notes pinned to frames, fixed and checked by the critic
            return self._send(200, (STUDIO.parent / "review.html").read_bytes(), "text/html; charset=utf-8")
        if p == "/doodle":     # plan 3.6: phone-first creator flow (snap, confirm cuts, see it talk) and drawing requests
            return self._send(200, (STUDIO.parent / "doodle.html").read_bytes(), "text/html; charset=utf-8")
        if p == "/actout":     # plan 3.5: a phone or webcam take becomes a character's clip
            return self._send(200, (STUDIO.parent / "actout.html").read_bytes(), "text/html; charset=utf-8")
        if p == "/api":
            return self._send(200, describe())
        if p.startswith("/api/jobs/"):
            return self._send(200, JOBS.get(p.rsplit("/", 1)[1], {"error": "no such job"}))
        f = (ROOT / p.lstrip("/")).resolve()  # static files: films, puppet canvas, renders
        if str(f).startswith(str(ROOT)) and f.is_file():
            return self._send(200, f.read_bytes(), mimetypes.guess_type(str(f))[0] or "application/octet-stream")
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.startswith("/upload"):   # raw body: Act it out takes and doodle photos, into out/ (git-ignored)
            n = int(self.headers.get("Content-Length", 0) or 0)
            if not 0 < n <= 300 * 1024 * 1024:
                return self._send(413, {"error": "uploads must be under 300 MB"})
            data = self.rfile.read(n)
            ext = (self.path.split("ext=", 1)[1].split("&")[0] if "ext=" in self.path else "mp4").lower()
            if ext in ("jpg", "jpeg", "png", "webp"):     # doodle photos (plan 3.6) and drawings for requests
                d = ROOT / "out" / "doodle" / "uploads"
            elif ext in ("mp4", "webm", "mov", "m4v", "mkv", "avi"):
                d = ROOT / "out" / "actout" / "takes"
            else:
                return self._send(400, {"error": f"not a photo or video type: {ext}"})
            d.mkdir(parents=True, exist_ok=True)
            f = d / f"{hashlib.sha256(data).hexdigest()[:16]}.{ext}"; f.write_bytes(data)
            return self._send(200, {"path": str(f.relative_to(ROOT))})
        if not self.path.startswith("/api/"):
            return self._send(404, {"error": "not found"})
        name = self.path[5:].split("?")[0]
        args = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0) or 0)) or b"{}")
        if "async=1" in self.path:  # long renders: run in a thread, poll /api/jobs/<id>
            jid = f"job{len(JOBS) + 1}"
            JOBS[jid] = {"status": "running", "command": name}

            def run():
                try:
                    JOBS[jid] = {"status": "done", "command": name, "result": call(name, args)}
                except Exception as e:
                    JOBS[jid] = {"status": "error", "command": name, "error": str(e)}
            threading.Thread(target=run, daemon=True).start()
            return self._send(202, {"job": jid})
        try:
            self._send(200, {"result": call(name, args)})
        except Exception as e:
            self._send(400, {"error": str(e), "trace": traceback.format_exc()[-1500:]})


def serve(port=8770):
    print(f"Doodleberry Studio on http://127.0.0.1:{port}  (API: POST /api/<command>)")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def mcp_stdio():
    """Minimal MCP server (JSON-RPC 2.0 over stdio): tools = every dbe command."""
    def reply(i, result=None, error=None):
        msg = {"jsonrpc": "2.0", "id": i}
        msg.update({"error": error} if error else {"result": result})
        sys.stdout.write(json.dumps(msg, default=str) + "\n"); sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        m, i, params = req.get("method"), req.get("id"), req.get("params") or {}
        if i is None:  # notification
            continue
        if m == "initialize":
            reply(i, {"protocolVersion": params.get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {}},
                      "serverInfo": {"name": "doodleberry", "version": "0.1"}})
        elif m == "tools/list":
            reply(i, {"tools": [{"name": t["name"].replace(".", "_"), "description": t["description"] or t["name"], "inputSchema": t["inputSchema"]} for t in describe()]})
        elif m == "tools/call":
            name = params.get("name", "").replace("_", ".", 1)
            try:
                res = call(name, params.get("arguments") or {})
                reply(i, {"content": [{"type": "text", "text": json.dumps(res, indent=1, default=str)}]})
            except Exception as e:
                reply(i, {"content": [{"type": "text", "text": f"error: {e}"}], "isError": True})
        elif m == "ping":
            reply(i, {})
        else:
            reply(i, error={"code": -32601, "message": f"method not found: {m}"})
