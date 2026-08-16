#!/usr/bin/env python3
"""Focused configuration/runtime profile regression tests."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import autoagent_config as config  # noqa: E402


def write(path: pathlib.Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    default = str(ROOT / "config/default.json")
    effective, sources = config.resolve_config(default, None, None)
    assert effective["preset"] == "balanced"
    assert effective["roles"]["developer"]["provider"] == "cursor"
    assert sources == ["preset:balanced"]

    with tempfile.TemporaryDirectory() as raw_temp:
        temp = pathlib.Path(raw_temp)
        global_path = temp / "global.json"
        project_path = temp / "project.json"
        write(global_path, {"version": 1, "preset": "quality", "max_cycles": 6})
        write(project_path, {
            "version": 1,
            "max_cycles": 2,
            "roles": {"developer": {"model": "Composer 2.5"}},
        })
        effective, _ = config.resolve_config(
            default,
            str(global_path),
            str(project_path),
            set_overrides=["role.developer.model=Cursor Grok 4.6", "max_cycles=3"],
        )
        assert effective["preset"] == "quality"
        assert effective["max_cycles"] == 3
        assert effective["roles"]["developer"]["model"] == "Cursor Grok 4.6"

        secret_path = temp / "secret.json"
        write(secret_path, {"version": 1, "api_key": "must-not-be-stored"})
        try:
            config.resolve_config(default, str(secret_path), None)
        except config.ConfigError as exc:
            assert "禁止保存凭据" in str(exc)
        else:
            raise AssertionError("secret-bearing config was accepted")

        try:
            config.resolve_config(default, None, None, set_overrides=["roles.developr.model=typo"])
        except config.ConfigError as exc:
            assert "未知角色" in str(exc)
        else:
            raise AssertionError("unknown role was accepted")

        runtime_config = temp / "effective.json"
        profile_dir = temp / "profiles"
        manifest_path = temp / "manifest.json"
        write(runtime_config, effective)
        config.render_profiles(argparse.Namespace(
            config=str(runtime_config),
            templates=str(ROOT / "profiles"),
            output=str(profile_dir),
            manifest=str(manifest_path),
            run_id="test-run",
        ))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["roles"]["manager"]["name"] == "autoagent_test_run_manager"
        developer_path = pathlib.Path(manifest["roles"]["developer"]["path"])
        developer = developer_path.read_text(encoding="utf-8")
        assert 'model: "Cursor Grok 4.6"' in developer
        assert "provider: cursor_cli" in developer

        target = temp / "specialists.json"
        config.specialist_add(argparse.Namespace(
            target=str(target),
            name="security",
            profile="my_security_profile",
            purpose="security review",
            when="authentication or permissions change",
            mode="optional",
        ))
        stored = json.loads(target.read_text(encoding="utf-8"))
        assert stored["specialists"][0]["profile"] == "my_security_profile"
        config.specialist_remove(argparse.Namespace(target=str(target), name="security"))
        assert json.loads(target.read_text(encoding="utf-8"))["specialists"] == []

    print("config tests passed")


if __name__ == "__main__":
    main()
