"""Helper for install-windows.ps1 (run with the bridge venv's python).

  python _claude_setup.py check          -> imports the MCP server (mcp 1.x + deps present?)
  python _claude_setup.py config <path>  -> backs up claude_desktop_config.json and adds
                                            mcpServers.cinema4d (this python + main.py)
"""
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.py")
NAME = "cinema4d"


def check():
    import importlib.metadata as md
    from mcp.server.fastmcp import FastMCP  # noqa: F401  (removed in mcp 2.x)

    sys.path.insert(0, os.path.join(HERE, "src"))
    import cinema4d_mcp.server  # noqa: F401

    print("server import OK - mcp", md.version("mcp"), "- python", sys.version.split()[0])


def config(cfg):
    data = {}
    if os.path.exists(cfg):
        with open(cfg, encoding="utf-8-sig") as f:
            txt = f.read()
        if txt.strip():
            data = json.loads(txt)
        bak = cfg + ".bak-" + time.strftime("%y%m%d-%H%M%S")
        shutil.copy2(cfg, bak)
        print("backup:", bak)
    else:
        os.makedirs(os.path.dirname(cfg), exist_ok=True)
    servers = data.setdefault("mcpServers", {})
    print("servers before:", ", ".join(servers) or "(none)")
    servers[NAME] = {"command": sys.executable, "args": [MAIN]}
    tmp = cfg + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    with open(tmp, encoding="utf-8") as f:
        json.load(f)  # validate before replacing
    os.replace(tmp, cfg)
    print("servers after:", ", ".join(servers))
    print(NAME, "->", servers[NAME]["command"], servers[NAME]["args"][0])


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "check":
        check()
    elif len(sys.argv) >= 3 and sys.argv[1] == "config":
        config(sys.argv[2])
    else:
        sys.exit(__doc__)
