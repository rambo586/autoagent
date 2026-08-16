#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

bash -n "$ROOT_DIR/bin/autoagent"
bash -n "$ROOT_DIR/install.sh"
bash -n "$ROOT_DIR/uninstall.sh"

python3 - "$ROOT_DIR" <<'PY'
import json, pathlib, re, sys

root = pathlib.Path(sys.argv[1])
for path in (root / "schemas").glob("*.json"):
    json.loads(path.read_text(encoding="utf-8"))

expected = {
    "autoagent_manager.md": "claude_code",
    "autoagent_planner.md": "codex",
    "autoagent_developer.md": "cursor_cli",
    "autoagent_tester.md": "codex",
    "autoagent_reviewer.md": "codex",
}
for name, provider in expected.items():
    text = (root / "profiles" / name).read_text(encoding="utf-8")
    assert text.startswith("---\n"), name
    assert re.search(rf"^provider: {re.escape(provider)}$", text, re.M), name
    assert "@cao-mcp-server" in text, name

developer = (root / "profiles/autoagent_developer.md").read_text(encoding="utf-8")
assert re.search(r"^model: auto$", developer, re.M)

gate = json.loads((root / "schemas/gate-result.schema.json").read_text())
assert gate["properties"]["verdict"]["enum"] == ["pass", "fail", "partial", "timeout"]

launcher = (root / "bin/autoagent").read_text(encoding="utf-8")
assert '"$cursor_command" --trust --print --model "$cursor_model"' in launcher
assert 'codex_probe=(codex --ask-for-approval never)' in launcher
assert 'mmx text chat' in launcher
assert 'mmx auth status' in launcher
assert 'render-profiles' in launcher
assert 'PROFILE_MAP_JSON' in launcher
assert 'autoagent watch' in launcher
assert 'agy --' not in launcher
assert 'AUTOAGENT_ANTIGRAVITY' not in launcher

installer = (root / "install.sh").read_text(encoding="utf-8")
assert 'lib/autoagent_config.py' in installer
assert 'config/default.json' in installer
assert 'antigravity.google/cli/install.sh' not in installer

manager = (root / "profiles/autoagent_manager.md").read_text(encoding="utf-8")
assert 'PROFILE_MAP_JSON' in manager
assert 'autoagent.status/v2' in manager
assert 'manual-only' in manager
for forbidden in ("git push", "git merge", "rm -rf", "security find-generic-password"):
    assert forbidden not in launcher, forbidden
PY

python3 "$ROOT_DIR/tests/config_test.py"
bash "$ROOT_DIR/tests/run_dry.sh"

"$ROOT_DIR/bin/autoagent" --version | grep -Fx '0.2.0' >/dev/null
"$ROOT_DIR/bin/autoagent" --help | grep -F 'autoagent run' >/dev/null
"$ROOT_DIR/bin/autoagent" --help | grep -F 'autoagent configure' >/dev/null
"$ROOT_DIR/bin/autoagent" --help | grep -F 'autoagent watch' >/dev/null

printf 'smoke tests passed\n'
