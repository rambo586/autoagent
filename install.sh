#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PREFIX="${AUTOAGENT_PREFIX:-$HOME/.local}"
BIN_DIR="$PREFIX/bin"
SHARE_DIR="$PREFIX/share/autoagent"
CODEX_CONFIG="$HOME/.codex/config.toml"

say() { printf '%s\n' "$*"; }
die() { printf 'install: %s\n' "$*" >&2; exit 1; }
has() { command -v "$1" >/dev/null 2>&1; }

[[ "$(uname -s)" == "Darwin" ]] || say "提示：v0.1 主要在 macOS 设计；将继续安装。"
has python3 || die "缺少 python3（需要 3.10+）"
has git || die "缺少 git"
has uv || die "缺少 uv。macOS 执行：brew install uv"
has tmux || die "缺少 tmux。macOS 执行：brew install tmux"

python3 - <<'PY' || die "需要 Python 3.10+"
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY

say "安装/更新 CLI Agent Orchestrator..."
uv tool install git+https://github.com/awslabs/cli-agent-orchestrator.git@main --upgrade

if ! has mmx; then
  has node || die "安装 MiniMax CLI 需要 Node.js 18+"
  has npm || die "安装 MiniMax CLI 需要 npm"
  say "安装官方 MiniMax CLI..."
  npm install -g mmx-cli
fi

mkdir -p "$BIN_DIR" "$SHARE_DIR/profiles" "$SHARE_DIR/schemas" "$HOME/.codex"
install -m 0755 "$ROOT_DIR/bin/autoagent" "$BIN_DIR/autoagent"
install -m 0644 "$ROOT_DIR/VERSION" "$SHARE_DIR/VERSION"
install -m 0644 "$ROOT_DIR"/profiles/*.md "$SHARE_DIR/profiles/"
install -m 0644 "$ROOT_DIR"/schemas/*.json "$SHARE_DIR/schemas/"

say "安装 CAO profiles..."
for profile in "$ROOT_DIR"/profiles/*.md; do
  cao profile validate "$profile"
  cao install "$profile"
done

touch "$CODEX_CONFIG"
if [[ ! -f "$CODEX_CONFIG.autoagent-backup" ]]; then
  cp "$CODEX_CONFIG" "$CODEX_CONFIG.autoagent-backup"
fi

if ! grep -q '^\[profiles\.autoagent_readonly\]' "$CODEX_CONFIG"; then
  cat >> "$CODEX_CONFIG" <<'EOF'

# Added by AutoAgent: non-interactive, hard read-only planning/review profile.
[profiles.autoagent_readonly]
approval_policy = "never"
sandbox_mode = "read-only"
EOF
fi

if ! grep -q '^\[profiles\.autoagent_tester\]' "$CODEX_CONFIG"; then
  cat >> "$CODEX_CONFIG" <<'EOF'

# Added by AutoAgent: tests may write build/cache output in the task worktree.
[profiles.autoagent_tester]
approval_policy = "never"
sandbox_mode = "workspace-write"
EOF
fi

say
say "AutoAgent 已安装：$BIN_DIR/autoagent"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *)
    say "请把下面这行加入 ~/.zshrc，然后重新打开终端："
    say "export PATH=\"$BIN_DIR:\$PATH\""
    ;;
esac
say "下一步：autoagent doctor"
say "真实模型连通检查：autoagent doctor --live（会消耗少量额度）"
if ! mmx auth status >/dev/null 2>&1; then
  say "MiniMax 尚未登录：请在本机交互执行 mmx auth login"
  say "不要把 API Key 或登录凭据粘贴到聊天或仓库。"
fi
