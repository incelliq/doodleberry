"""CLI:  python -m dbe <command> ['{"json": "args"}']   |   python -m dbe serve [port] [host]   |   python -m dbe mcp"""
import json
import sys

from . import call, describe


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help", "help"):
        print(__doc__)
        for c in describe():
            print(f"  {c['name']:<18} {c['description'].splitlines()[0] if c['description'] else ''}")
        return
    if a[0] == "serve":
        from .server import serve
        return serve(int(a[1]) if len(a) > 1 else 8770, a[2] if len(a) > 2 else None)
    if a[0] == "mcp":
        from .server import mcp_stdio
        return mcp_stdio()
    args = json.loads(a[1]) if len(a) > 1 else {}
    print(json.dumps(call(a[0], args), indent=1, default=str))


if __name__ == "__main__":
    main()
