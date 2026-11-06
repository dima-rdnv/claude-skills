"""One MCP tool call into the running Cinema 4D (Maxon MCP server) through Maxon's stdio relay.
usage: python -I c4dmcp.py TOOL [JSON_ARGS | @args.json]
       python -I c4dmcp.py py script.py [timeout_s]   (exec_python with the file's code)
Prints the tool result's text content (or the raw JSON on error)."""
import glob, json, os, subprocess, sys

def _newest(paths):
    return max(paths, key=os.path.getmtime) if paths else None

# newest installed Cinema 4D on Windows, and the newest MCP token of that year
C4D = max(glob.glob(r"C:\Program Files\Maxon Cinema 4D 20*") or [""])     # highest year (by name)
RELAY = os.path.join(C4D, r"resource\mxn_plugins\mcp_adapter\scripts\stdio_relay.py")
YEAR = os.path.basename(C4D).split()[-1] if C4D else "*"
TOKEN = [_newest(glob.glob(os.path.join(os.environ.get("APPDATA", ""), "Maxon", "Maxon Cinema 4D %s_*" % YEAR,
                                        "prefs", "mcp", "token")))]


def call(tool, args, timeout=320):
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "claude-code-shell", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": tool, "arguments": args}},
    ]
    p = subprocess.Popen([sys.executable, RELAY, "http://127.0.0.1:5556/mcp", "--token-file", TOKEN[0]],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         encoding="utf-8")
    out, err = p.communicate("\n".join(json.dumps(m) for m in msgs) + "\n", timeout=timeout)
    for line in out.splitlines():
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if m.get("id") == 2:
            return m
    raise SystemExit("no reply to the tool call; relay stderr:\n" + err[-2000:])


if __name__ == "__main__":
    tool = sys.argv[1]
    if tool == "py":
        code = open(sys.argv[2], encoding="utf-8").read()
        args = {"code": code}
        if len(sys.argv) > 3:
            args["timeout_seconds"] = float(sys.argv[3])
        tool = "exec_python"
    elif len(sys.argv) > 2:
        a = sys.argv[2]
        args = json.load(open(a[1:], encoding="utf-8")) if a.startswith("@") else json.loads(a)
    else:
        args = {}
    m = call(tool, args)
    res = m.get("result")
    if res and "content" in res:
        for c in res["content"]:
            print(c.get("text", json.dumps(c)[:500]))
        if res.get("isError"):
            sys.exit(1)
    else:
        print(json.dumps(m, indent=1)[:5000])
        sys.exit(1)
