#!/bin/bash
# Installs the Claude Bridge CEP panel for After Effects on macOS, for the current user only.
#   1. Self-signs ../panel with ZXPSignCmd from $SIGNING_DIR (default ~/.claude/cep-signing). CEP 12
#      refuses unsigned panels. The certificate and its password are created there on first use and
#      stay there; never share them.
#   2. Copies the signed panel to ~/Library/Application Support/Adobe/CEP/extensions/com.claude.aebridge.
#   3. Moves the old ScriptUI panel (ClaudeBridge.jsx in any AE version's ScriptUI Panels folder) to
#      the Trash, so two bridges never serve the same inbox.
# Then restart After Effects (it finds new extensions only at start-up) and open
# Window > Extensions > Claude Bridge. Re-run after editing the panel: an edited file breaks the
# signature. A new host.jsx loads when the panel is closed and reopened.
set -euo pipefail

SIGNING_DIR="${SIGNING_DIR:-$HOME/.claude/cep-signing}"
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/../panel"
DST="$HOME/Library/Application Support/Adobe/CEP/extensions/com.claude.aebridge"
ZXP_SIGN="$SIGNING_DIR/ZXPSignCmd"
CERT="$SIGNING_DIR/claude-bridge.p12"
PW_FILE="$SIGNING_DIR/claude-bridge.p12.password"

if [ ! -x "$ZXP_SIGN" ]; then
  cat <<EOF
No ZXPSignCmd in $SIGNING_DIR; After Effects refuses unsigned CEP panels. Adobe's tool:
  mkdir -p "$SIGNING_DIR"
  curl -fL -o "$ZXP_SIGN" https://raw.githubusercontent.com/Adobe-CEP/CEP-Resources/master/ZXPSignCMD/4.1.3/macOS/ZXPSignCmd
  chmod +x "$ZXP_SIGN"
It is an Intel binary: Apple Silicon needs Rosetta (softwareupdate --install-rosetta).
EOF
  exit 1
fi

if [ ! -f "$CERT" ]; then
  (umask 077; openssl rand -hex 16 > "$PW_FILE")
  "$ZXP_SIGN" -selfSignedCert US NA "Claude Bridge" "Claude Bridge local signing" "$(cat "$PW_FILE")" "$CERT" -validityDays 3650
  chmod 600 "$CERT"
  echo "Created self-signed certificate $CERT"
fi

STAGE="$SIGNING_DIR/stage-ae"
rm -rf "$STAGE"; mkdir -p "$STAGE/panel"
# Finder's .DS_Store files would be signed along, or break the signature if they appear later
rsync -a --exclude .DS_Store --exclude __MACOSX "$SRC/" "$STAGE/panel/"
"$ZXP_SIGN" -sign "$STAGE/panel" "$STAGE/panel.zxp" "$CERT" "$(cat "$PW_FILE")"
unzip -q "$STAGE/panel.zxp" -d "$STAGE/signed"     # a .zxp is a zip
mkdir -p "$DST"
rsync -a --delete "$STAGE/signed/" "$DST/"
"$ZXP_SIGN" -verify "$DST"
echo "Signed panel installed to $DST"

shopt -s nullglob
for old in "$HOME/Library/Preferences/Adobe/After Effects/"*"/Scripts/ScriptUI Panels/ClaudeBridge.jsx"; do
  if command -v trash >/dev/null 2>&1; then trash "$old"; else mv "$old" "$HOME/.Trash/ClaudeBridge-$(date +%s).jsx"; fi
  echo "Moved old ScriptUI panel to the Trash: $old"
done
