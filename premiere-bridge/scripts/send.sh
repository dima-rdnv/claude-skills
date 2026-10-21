#!/bin/bash
# send.sh NAME [TIMEOUT_S]
# Stages $STAGE/NAME.jsx into the Premiere bridge inbox atomically and waits for outbox/NAME.json.
#   STAGE  folder where scripts are written (default: current dir)
#   BRIDGE bridge root (default: /d/WORK/Claude/premiere-bridge)
STAGE="${STAGE:-.}"; BRIDGE="${BRIDGE:-/d/WORK/Claude/premiere-bridge}"; n="$1"
rm -f "$BRIDGE/outbox/$n.json"
# write under a non-.jsx name first, then rename: the bridge globs *.jsx every second and
# would otherwise run a half-written (often empty) file
cp "$STAGE/$n.jsx" "$BRIDGE/inbox/$n.tmp" && mv "$BRIDGE/inbox/$n.tmp" "$BRIDGE/inbox/$n.jsx"
for i in $(seq 1 "${2:-120}"); do [ -f "$BRIDGE/outbox/$n.json" ] && break; sleep 1; done
if [ ! -f "$BRIDGE/outbox/$n.json" ]; then
  echo "TIMEOUT - $n.jsx is still in the inbox."
  # status.json is rewritten every ~5 s while the panel is open, and says which script is running
  python -c "import json,sys,time;d=json.load(open(sys.argv[1],encoding='utf-8'));age=time.time()-d['time']/1000.0;print('Premiere is still running %s (started %d s ago)' % (d['file'], age) if d['state']=='running' else 'Panel state: %s, last heartbeat %d s ago (stale = panel closed or Premiere busy)' % (d['state'], age))" "$BRIDGE/status.json" 2>/dev/null \
    || echo "No status.json - the Claude Bridge panel has never run."
  exit 1
fi
python -c "import json,sys;d=json.load(open(sys.argv[1],encoding='utf-8'));print('OK' if d['ok'] else 'FAIL', d.get('error',''), d.get('line',''), d.get('ms'))" "$BRIDGE/outbox/$n.json"
