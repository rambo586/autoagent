#!/usr/bin/env bash
set -euo pipefail

PREFIX="${AUTOAGENT_PREFIX:-$HOME/.local}"
BIN="$PREFIX/bin/autoagent"
SHARE="$PREFIX/share/autoagent"

if [[ -f "$BIN" ]]; then
  rm "$BIN"
  printf '已删除 %s\n' "$BIN"
fi

if [[ -d "$SHARE" ]]; then
  timestamp=$(date '+%Y%m%d-%H%M%S')
  backup="$PREFIX/share/autoagent.uninstalled-$timestamp"
  mv "$SHARE" "$backup"
  printf '配置副本已移至 %s（可恢复）\n' "$backup"
fi

cat <<'EOF'
CAO、各模型 CLI、运行 worktree、运行记录和 ~/.codex/config.toml 未被删除。
这是有意的安全行为；请确认不再需要后再手动清理。
EOF
