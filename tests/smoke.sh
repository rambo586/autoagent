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

gate = json.loads((root / "schemas/gate-result.schema.json").read_text())
assert gate["properties"]["verdict"]["enum"] == ["pass", "fail", "partial", "timeout"]

launcher = (root / "bin/autoagent").read_text(encoding="utf-8")
assert '"$cursor_command" --trust --print' in launcher
assert 'codex --ask-for-approval never exec' in launcher
assert 'mmx text chat' in launcher
assert 'mmx auth status' in launcher
for forbidden in ("git push", "git merge", "rm -rf", "security find-generic-password"):
    assert forbidden not in launcher, forbidden
PY

"$ROOT_DIR/bin/autoagent" --version | grep -Fx '0.1.1' >/dev/null
"$ROOT_DIR/bin/autoagent" --help | grep -F 'autoagent run' >/dev/null

printf 'smoke tests passed\n'
