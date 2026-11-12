"""Run Python in a running Unreal Editor via the PythonScriptPlugin remote execution.

Usage (with the engine's own Python):
    python -I ue_exec.py script.py
    python -I ue_exec.py -c "import unreal; print(unreal.SystemLibrary.get_engine_version())"
Prints the editor's output; exits 1 with COMMAND_FAILED and the traceback if the code raised,
2 if no editor answered (is Project Settings > Python > Enable Remote Execution on?).
Set UE_ROOT if the engine is not in C:\\Program Files\\Epic Games\\UE_5.8.
"""
import os
import sys
import time

UE_ROOT = os.environ.get("UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8")
sys.path.insert(0, os.path.join(UE_ROOT, r"Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python"))
import remote_execution as rx  # noqa: E402


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "-c":
        code = sys.argv[2]
    else:
        with open(sys.argv[1], encoding="utf-8") as f:
            code = f.read()

    remote = rx.RemoteExecution()
    remote.start()
    try:
        deadline = time.time() + 10
        while not remote.remote_nodes and time.time() < deadline:
            time.sleep(0.2)
        if not remote.remote_nodes:
            print("NO_UNREAL_NODE_FOUND")
            sys.exit(2)
        node = remote.remote_nodes[0]
        remote.open_command_connection(node["node_id"])
        res = remote.run_command(code, unattended=True, exec_mode=rx.MODE_EXEC_FILE)
        for entry in res.get("output", []):
            print(entry.get("output", "").rstrip())
        if not res.get("success", False):
            print("COMMAND_FAILED:", res.get("result"))
            sys.exit(1)
    finally:
        remote.stop()


if __name__ == "__main__":
    main()
