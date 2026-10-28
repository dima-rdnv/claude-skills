#!/bin/bash
# send.sh NAME [TIMEOUT_S]
# Signs $STAGE/NAME.jsx, stages it into the bridge inbox atomically and waits for outbox/NAME.json.
#   STAGE  folder where scripts are written (default: current dir)
#   BRIDGE bridge root = the folder with inbox/ outbox/ done/ (required)
# The panel only runs scripts signed with ~/.claude/ae-bridge.key (created here on first use):
# first line "// claude-bridge-sig <unix time> <HMAC-SHA256 of "<time>\n<NAME>\n<script bytes>">".
STAGE="${STAGE:-.}"; n="$1"
if [ ! -d "$BRIDGE/inbox" ]; then echo "Set BRIDGE to the bridge folder (the one holding inbox/ - shown in the panel's status line)"; exit 1; fi
if [ ! -f "$STAGE/$n.jsx" ]; then echo "No script $STAGE/$n.jsx"; exit 1; fi
command -v openssl >/dev/null 2>&1 || { echo "openssl not found - it is needed to sign scripts for the bridge"; exit 1; }
KEY_FILE="$HOME/.claude/ae-bridge.key"
if [ ! -s "$KEY_FILE" ]; then mkdir -p "$HOME/.claude" && (umask 077; openssl rand -hex 32 > "$KEY_FILE") || exit 1; fi
key=$(tr -d ' \r\n' < "$KEY_FILE"); ts=$(date +%s)
sig=$({ printf '%s\n%s\n' "$ts" "$n"; cat "$STAGE/$n.jsx"; } | openssl dgst -sha256 -hmac "$key" | sed 's/^.*= //')
rm -f "$BRIDGE/outbox/$n.json"
# write under a non-.jsx name first, then rename: the bridge globs *.jsx every second and
# would otherwise pick up a half-written file
{ printf '// claude-bridge-sig %s %s\n' "$ts" "$sig"; cat "$STAGE/$n.jsx"; } > "$BRIDGE/inbox/$n.tmp" && mv "$BRIDGE/inbox/$n.tmp" "$BRIDGE/inbox/$n.jsx"
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
