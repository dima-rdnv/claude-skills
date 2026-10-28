#!/bin/bash
# send.sh NAME [TIMEOUT_S]
# Stages $STAGE/NAME.jsx into the bridge inbox atomically and waits for outbox/NAME.json.
#   STAGE  folder where scripts are written (default: current dir)
#   BRIDGE bridge root = the folder with inbox/ outbox/ done/ (required)
STAGE="${STAGE:-.}"; n="$1"
if [ ! -d "$BRIDGE/inbox" ]; then echo "Set BRIDGE to the bridge folder (the one holding inbox/ - shown in the panel's status line)"; exit 1; fi
rm -f "$BRIDGE/outbox/$n.json"
# write under a non-.jsx name first, then rename: the bridge globs *.jsx every second and
# would otherwise run a half-written (often empty) file
cp "$STAGE/$n.jsx" "$BRIDGE/inbox/$n.tmp" && mv "$BRIDGE/inbox/$n.tmp" "$BRIDGE/inbox/$n.jsx"
for i in $(seq 1 "${2:-120}"); do [ -f "$BRIDGE/outbox/$n.json" ] && break; sleep 1; done
if [ ! -f "$BRIDGE/outbox/$n.json" ]; then echo "TIMEOUT - is the Claude Bridge panel stopped or closed?"; exit 1; fi
# summary line via Python if a real one runs (Windows may only have the Microsoft Store stub),
# otherwise the start of the raw JSON
for py in python3 python; do
  if "$py" -c "" >/dev/null 2>&1; then
    "$py" -c "import json,sys;d=json.load(open(sys.argv[1],encoding='utf-8'));print('OK' if d['ok'] else 'FAIL', d.get('error',''), d.get('line',''), d.get('ms'))" "$BRIDGE/outbox/$n.json"
    exit
  fi
done
head -c 400 "$BRIDGE/outbox/$n.json"; echo
