#!/usr/bin/env bash
# Links every skill in this repo into ~/.claude/skills, where Claude Code looks for skills.
# Run it again after a pull that adds, moves or renames a skill.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
target="${1:-$HOME/.claude/skills}"
mkdir -p "$target"
if [ "$(cd "$target" && pwd -P)" = "$repo" ]; then
  echo "This clone is the skills folder itself. Move it elsewhere (for example ~/.claude/claude-skills) and run this again." >&2
  exit 1
fi

# Remove links into this repo whose skill has moved or gone.
for l in "$target"/*; do
  [ -L "$l" ] || continue
  case "$(readlink "$l")" in
    "$repo"/*) [ -f "$l/SKILL.md" ] || { rm "$l"; echo "removed stale link $(basename "$l")"; } ;;
  esac
done

count=0
for skill in "$repo"/*/*/SKILL.md; do
  dir="$(dirname "$skill")"
  name="$(basename "$dir")"
  link="$target/$name"
  if [ -e "$link" ] && [ ! -L "$link" ]; then
    echo "skipped $name: $link is a real folder" >&2
    continue
  fi
  ln -sfn "$dir" "$link"
  count=$((count + 1))
done
echo "linked $count skills into $target"
