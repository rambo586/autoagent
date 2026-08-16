#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
TEST_ROOT=$(mktemp -d)
trap 'rm -r "$TEST_ROOT"' EXIT

mkdir -p "$TEST_ROOT/mock" "$TEST_ROOT/home" "$TEST_ROOT/server" "$TEST_ROOT/project"
ln -s /usr/bin/true "$TEST_ROOT/mock/cao"
ln -s /usr/bin/true "$TEST_ROOT/mock/cao-server"
touch "$TEST_ROOT/server/openapi.json"

git -C "$TEST_ROOT/project" init -q
git -C "$TEST_ROOT/project" config user.name AutoAgent-Test
git -C "$TEST_ROOT/project" config user.email test@example.invalid
git -C "$TEST_ROOT/project" commit --allow-empty -qm init

(
  cd "$TEST_ROOT/project"
  HOME="$TEST_ROOT/home" \
  AUTOAGENT_HOME="$TEST_ROOT/state" \
  AUTOAGENT_CAO_URL="file://$TEST_ROOT/server" \
  AUTOAGENT_MINIMAX=off \
  PATH="$TEST_ROOT/mock:/usr/bin:/bin" \
    "$ROOT_DIR/bin/autoagent" run \
      --preset fast \
      --set developer.model='Cursor Grok 4.6' \
      'dry run implementation' >/dev/null
)

run_id=$(tr -d '\n' < "$TEST_ROOT/state/latest-run")
python3 - \
  "$TEST_ROOT/state/runs/$run_id/meta.json" \
  "$TEST_ROOT/state/runs/$run_id/effective-config.json" \
  "$TEST_ROOT/state/runs/$run_id/profile-manifest.json" <<'PY'
import json, sys

meta, config, manifest = (
    json.load(open(path, encoding="utf-8")) for path in sys.argv[1:]
)
assert meta["schema_version"] == "autoagent.run/v2"
assert meta["preset"] == "fast" and meta["max_cycles"] == 1
assert config["roles"]["developer"]["model"] == "Cursor Grok 4.6"
assert manifest["roles"]["manager"]["name"].endswith("_manager")
PY

HOME="$TEST_ROOT/home" \
AUTOAGENT_HOME="$TEST_ROOT/state" \
PATH="$TEST_ROOT/mock:/usr/bin:/bin" \
  "$ROOT_DIR/bin/autoagent" status "$run_id" | grep -F 'state:     LAUNCHED' >/dev/null

printf 'run dry test passed\n'
