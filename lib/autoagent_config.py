#!/usr/bin/env python3
"""Dependency-free configuration and runtime-profile support for AutoAgent."""

from __future__ import annotations

import argparse
import copy
import json
import os
import pathlib
import re
import shutil
import sys
from typing import Any


CORE_ROLES = ("manager", "planner", "developer", "tester", "reviewer")
ADVISOR_ROLES = ("challenger", "researcher")
ALL_ROLES = CORE_ROLES + ADVISOR_ROLES
MODES = {"required", "optional", "disabled", "manual"}
PROVIDER_ALIASES = {
    "claude": "claude_code",
    "claude_code": "claude_code",
    "cursor": "cursor_cli",
    "cursor_cli": "cursor_cli",
    "codex": "codex",
    "minimax": "minimax",
    "antigravity": "antigravity",
    "custom": "custom",
}
PROVIDER_COMMANDS = {
    "claude": "claude",
    "claude_code": "claude",
    "cursor": "cursor-agent",
    "cursor_cli": "cursor-agent",
    "codex": "codex",
    "minimax": "mmx",
    "antigravity": "agy",
}
SENSITIVE_KEY = re.compile(r"(?:token|secret|password|credential|api[_-]?key|cookie)", re.I)


class ConfigError(ValueError):
    pass


def read_json(path: str | None, *, required: bool = False) -> dict[str, Any]:
    if not path:
        return {}
    file_path = pathlib.Path(path)
    if not file_path.exists():
        if required:
            raise ConfigError(f"配置文件不存在：{file_path}")
        return {}
    try:
        value = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"配置文件不是有效 JSON：{file_path}:{exc.lineno}:{exc.colno}") from exc
    if not isinstance(value, dict):
        raise ConfigError(f"配置文件顶层必须是对象：{file_path}")
    reject_secrets(value, str(file_path))
    return value


def write_json(path: str, value: dict[str, Any], *, overwrite: bool = True) -> None:
    file_path = pathlib.Path(path)
    if file_path.exists() and not overwrite:
        raise ConfigError(f"配置已存在：{file_path}；使用 --force 才能覆盖")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = file_path.with_name(file_path.name + ".tmp")
    temp_path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_path, file_path)


def reject_secrets(value: Any, source: str, prefix: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            location = f"{prefix}.{key}" if prefix else key
            if SENSITIVE_KEY.search(str(key)):
                raise ConfigError(f"配置禁止保存凭据字段：{source}:{location}")
            reject_secrets(child, source, location)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_secrets(child, source, f"{prefix}[{index}]")


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = copy.deepcopy(value)
    return base


def deep_diff(value: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """Return only values that differ, preserving nested mapping structure."""
    result: dict[str, Any] = {}
    for key, child in value.items():
        if key not in baseline:
            result[key] = copy.deepcopy(child)
        elif isinstance(child, dict) and isinstance(baseline[key], dict):
            nested = deep_diff(child, baseline[key])
            if nested:
                result[key] = nested
        elif child != baseline[key]:
            result[key] = copy.deepcopy(child)
    return result


def parse_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def normalize_set_key(key: str) -> str:
    if key.startswith("role."):
        return "roles." + key[len("role.") :]
    if key.startswith(tuple(role + "." for role in ALL_ROLES)):
        return "roles." + key
    return key


def set_path(root: dict[str, Any], expression: str) -> None:
    if "=" not in expression:
        raise ConfigError(f"--set 必须是 key=value：{expression}")
    raw_key, raw_value = expression.split("=", 1)
    key = normalize_set_key(raw_key.strip())
    if not key or any(not part for part in key.split(".")):
        raise ConfigError(f"无效配置键：{raw_key}")
    if SENSITIVE_KEY.search(key):
        raise ConfigError(f"配置禁止保存凭据字段：{key}")
    cursor: dict[str, Any] = root
    parts = key.split(".")
    for part in parts[:-1]:
        existing = cursor.get(part)
        if existing is None:
            cursor[part] = {}
        elif not isinstance(existing, dict):
            raise ConfigError(f"无法覆盖非对象配置：{part}")
        cursor = cursor[part]
    cursor[parts[-1]] = parse_value(raw_value.strip())


def resolve_config(
    default_path: str,
    global_path: str | None,
    project_path: str | None,
    preset_override: str | None = None,
    set_overrides: list[str] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    defaults = read_json(default_path, required=True)
    presets = defaults.get("presets")
    if not isinstance(presets, dict) or not presets:
        raise ConfigError("默认配置缺少 presets")

    layers: list[tuple[str, dict[str, Any]]] = []
    if global_path and pathlib.Path(global_path).exists():
        layers.append(("global", read_json(global_path)))
    if project_path and pathlib.Path(project_path).exists():
        layers.append(("project", read_json(project_path)))

    preset = str(defaults.get("preset", "balanced"))
    for _, layer in layers:
        if "preset" in layer:
            preset = str(layer["preset"])
    if preset_override:
        preset = preset_override
    if preset not in presets:
        raise ConfigError(f"未知 preset：{preset}；可用值：{', '.join(sorted(presets))}")

    effective: dict[str, Any] = {"version": 1, "preset": preset}
    deep_merge(effective, copy.deepcopy(presets[preset]))
    sources = [f"preset:{preset}"]
    for label, layer in layers:
        override = {k: v for k, v in layer.items() if k not in {"version", "preset"}}
        deep_merge(effective, override)
        sources.append(f"{label}:{global_path if label == 'global' else project_path}")
    for expression in set_overrides or []:
        set_path(effective, expression)
        sources.append(f"cli:{expression}")

    validate_effective(effective)
    return effective, sources


def validate_effective(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    warnings: list[str] = []
    allowed_top_level = {"version", "preset", "max_cycles", "fallback_policy", "roles", "specialists"}
    for key in config:
        if key not in allowed_top_level:
            errors.append(f"未知配置字段：{key}")
    if config.get("version") != 1:
        errors.append("version 必须为 1")
    max_cycles = config.get("max_cycles")
    if not isinstance(max_cycles, int) or isinstance(max_cycles, bool) or not 1 <= max_cycles <= 20:
        errors.append("max_cycles 必须是 1..20 的整数")
    if config.get("fallback_policy") not in {"never", "notify", "ask"}:
        errors.append("fallback_policy 必须是 never、notify 或 ask")

    roles = config.get("roles")
    if not isinstance(roles, dict):
        errors.append("roles 必须是对象")
        roles = {}
    for role in roles:
        if role not in ALL_ROLES:
            errors.append(f"未知角色：roles.{role}")
    for role in ALL_ROLES:
        value = roles.get(role)
        if not isinstance(value, dict):
            errors.append(f"缺少角色配置：roles.{role}")
            continue
        provider = str(value.get("provider", ""))
        mode = str(value.get("mode", ""))
        model = value.get("model")
        for key in value:
            if key not in {"provider", "model", "mode", "template", "profile", "codex_profile"}:
                errors.append(f"未知角色字段：roles.{role}.{key}")
        if provider not in PROVIDER_ALIASES:
            errors.append(f"roles.{role}.provider 不支持：{provider}")
        if mode not in MODES:
            errors.append(f"roles.{role}.mode 不支持：{mode}")
        if model is not None and (not isinstance(model, str) or not model.strip()):
            errors.append(f"roles.{role}.model 必须是非空字符串")
        if provider == "custom" and not value.get("profile"):
            errors.append(f"roles.{role} 使用 custom 时必须提供 profile")
        if role in CORE_ROLES and mode in {"manual", "disabled"} and role in {"manager", "planner"}:
            errors.append(f"核心角色 {role} 不能设为 {mode}")
        if provider in {"minimax", "antigravity"} and role in CORE_ROLES:
            errors.append(f"{provider} 当前没有 CAO provider，不能直接承担核心角色 {role}")
        if provider == "antigravity" and mode not in {"manual", "disabled"}:
            errors.append("Antigravity 消费者登录只能设为 manual 或 disabled，不能由 AutoAgent 自动调用")
        if provider == "codex" and role == "manager":
            errors.append("Manager 不能直接使用 Codex provider；RUN_DIR 在 worktree 外。如有合适的 CAO profile，请使用 custom")

    specialists = config.get("specialists", [])
    if not isinstance(specialists, list):
        errors.append("specialists 必须是数组")
    else:
        names: set[str] = set()
        for index, specialist in enumerate(specialists):
            if not isinstance(specialist, dict):
                errors.append(f"specialists[{index}] 必须是对象")
                continue
            for field in ("name", "profile", "purpose", "when"):
                if not isinstance(specialist.get(field), str) or not specialist[field].strip():
                    errors.append(f"specialists[{index}].{field} 必须是非空字符串")
            name = str(specialist.get("name", ""))
            for key in specialist:
                if key not in {"name", "profile", "purpose", "when", "mode"}:
                    errors.append(f"未知 specialist 字段：specialists[{index}].{key}")
            if name in names:
                errors.append(f"specialist 名称重复：{name}")
            names.add(name)
            if specialist.get("mode", "optional") not in {"optional", "required", "disabled"}:
                errors.append(f"specialists[{index}].mode 不支持")

    reject_secrets(config, "effective-config")
    if errors:
        raise ConfigError("；".join(errors))
    return warnings


def config_target_skeleton(preset: str) -> dict[str, Any]:
    return {"version": 1, "preset": preset, "roles": {}, "specialists": []}


def choose(label: str, options: list[str], current: str) -> str:
    ordered = [current] + [option for option in options if option != current]
    print(f"\n{label}")
    for index, option in enumerate(ordered, 1):
        suffix = "（当前）" if option == current else ""
        print(f"  {index}. {option}{suffix}")
    raw = input(f"选择 [1-{len(ordered)}，默认 1]：").strip()
    if not raw:
        return ordered[0]
    if not raw.isdigit() or not 1 <= int(raw) <= len(ordered):
        raise ConfigError(f"无效选择：{raw}")
    return ordered[int(raw) - 1]


def configure(args: argparse.Namespace) -> None:
    if not sys.stdin.isatty():
        raise ConfigError("autoagent configure 需要交互终端")
    effective, _ = resolve_config(args.default, args.global_path, args.project_path)
    defaults = read_json(args.default, required=True)
    preset = choose("运行预设", sorted(defaults["presets"]), str(effective["preset"]))
    effective, _ = resolve_config(args.default, args.global_path, args.project_path, preset_override=preset)

    max_cycles_raw = input(f"\n最大修复循环 [{effective['max_cycles']}]：").strip()
    max_cycles = int(max_cycles_raw) if max_cycles_raw else int(effective["max_cycles"])
    provider_options = {
        "manager": ["claude", "custom"],
        "planner": ["codex", "claude", "custom"],
        "developer": ["cursor", "codex", "claude", "custom"],
        "tester": ["codex", "cursor", "custom"],
        "reviewer": ["codex", "claude", "custom"],
    }
    roles = copy.deepcopy(effective["roles"])
    for role in CORE_ROLES:
        current = str(roles[role]["provider"])
        provider = choose(f"{role} provider", provider_options[role], current)
        roles[role]["provider"] = provider
        if provider == "custom":
            profile = input(f"{role} 已安装 CAO profile 名称：").strip()
            if not profile:
                raise ConfigError(f"{role} custom provider 必须填写 profile")
            roles[role]["profile"] = profile
        current_model = str(roles[role].get("model", "inherit"))
        model = input(f"{role} model [当前 {current_model}；inherit=沿用客户端]：").strip()
        roles[role]["model"] = model or current_model

    challenger_enabled = choose(
        "MiniMax Challenger",
        ["optional", "disabled", "required"],
        str(roles["challenger"]["mode"]),
    )
    roles["challenger"]["mode"] = challenger_enabled
    researcher_mode = choose(
        "Antigravity Researcher（消费者账号仅允许手动）",
        ["manual", "disabled"],
        str(roles["researcher"]["mode"]),
    )
    roles["researcher"]["mode"] = researcher_mode

    desired = {
        "version": 1,
        "preset": preset,
        "max_cycles": max_cycles,
        "fallback_policy": str(effective["fallback_policy"]),
        "roles": roles,
        "specialists": copy.deepcopy(effective.get("specialists", [])),
    }
    validate_effective(desired)
    target_is_project = pathlib.Path(args.target) == pathlib.Path(args.project_path)
    inherited, _ = resolve_config(
        args.default,
        args.global_path if target_is_project else None,
        None,
        preset_override=preset,
    )
    output = {"version": 1, "preset": preset}
    deep_merge(output, deep_diff(desired, inherited))
    write_json(args.target, output)
    print(f"\n配置已写入：{args.target}")


def split_frontmatter(text: str) -> tuple[list[str], str]:
    if not text.startswith("---\n"):
        raise ConfigError("profile 缺少 YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ConfigError("profile frontmatter 未闭合")
    lines = text[4:end].splitlines()
    return lines, text[end + 5 :]


def update_scalar(lines: list[str], key: str, value: str | None, after: str = "role") -> list[str]:
    pattern = re.compile(rf"^{re.escape(key)}:")
    found = False
    result: list[str] = []
    for line in lines:
        if pattern.match(line):
            found = True
            if value is not None:
                result.append(f"{key}: {yaml_scalar(value)}")
        else:
            result.append(line)
    if value is not None and not found:
        insert_at = next((i + 1 for i, line in enumerate(result) if line.startswith(after + ":")), 0)
        result.insert(insert_at, f"{key}: {yaml_scalar(value)}")
    return result


def yaml_scalar(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./-]+", value) and value.lower() not in {
        "null", "true", "false", "yes", "no", "on", "off",
    }:
        return value
    return json.dumps(value, ensure_ascii=False)


def render_profiles(args: argparse.Namespace) -> None:
    config = read_json(args.config, required=True)
    validate_effective(config)
    templates_dir = pathlib.Path(args.templates)
    output_dir = pathlib.Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_run_id = re.sub(r"[^a-zA-Z0-9_]", "_", args.run_id)
    manifest: dict[str, Any] = {"run_id": args.run_id, "roles": {}, "specialists": []}

    for role in CORE_ROLES:
        role_config = config["roles"][role]
        mode = role_config["mode"]
        if mode in {"disabled", "manual"}:
            manifest["roles"][role] = {"mode": mode, "name": None, "generated": False}
            continue
        provider = role_config["provider"]
        if provider == "custom":
            manifest["roles"][role] = {
                "mode": mode,
                "name": role_config["profile"],
                "generated": False,
                "provider": "custom",
                "model": role_config.get("model", "inherit"),
            }
            continue

        template_name = role_config.get("template", f"autoagent_{role}")
        template_path = templates_dir / f"{template_name}.md"
        if not template_path.exists():
            raise ConfigError(f"找不到 {role} template：{template_path}")
        lines, body = split_frontmatter(template_path.read_text(encoding="utf-8"))
        profile_name = f"autoagent_{safe_run_id}_{role}"
        lines = update_scalar(lines, "name", profile_name, after="name")
        lines = update_scalar(lines, "provider", PROVIDER_ALIASES[provider], after="description")
        model = str(role_config.get("model", "inherit"))
        lines = update_scalar(lines, "model", None if model in {"inherit", "default"} else model)
        codex_profile = role_config.get("codex_profile")
        if PROVIDER_ALIASES[provider] == "codex":
            if not codex_profile:
                codex_profile = "autoagent_readonly" if role in {"planner", "reviewer"} else "autoagent_tester"
            lines = update_scalar(lines, "codexProfile", str(codex_profile), after="model")
        else:
            lines = update_scalar(lines, "codexProfile", None)
        rendered = "---\n" + "\n".join(lines) + "\n---\n" + body
        output_path = output_dir / f"{profile_name}.md"
        output_path.write_text(rendered, encoding="utf-8")
        manifest["roles"][role] = {
            "mode": mode,
            "name": profile_name,
            "generated": True,
            "path": str(output_path),
            "provider": provider,
            "model": model,
        }

    for specialist in config.get("specialists", []):
        if specialist.get("mode", "optional") != "disabled":
            manifest["specialists"].append(copy.deepcopy(specialist))
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False))


def print_models(config: dict[str, Any]) -> None:
    print(f"{'ROLE':<12} {'PROVIDER':<14} {'MODEL':<22} {'MODE':<10} STATUS")
    for role in ALL_ROLES:
        value = config["roles"][role]
        provider = str(value["provider"])
        model = str(value.get("model", "inherit"))
        mode = str(value["mode"])
        if provider == "custom":
            status = f"profile:{value.get('profile', '?')}"
        else:
            command = PROVIDER_COMMANDS.get(provider)
            resolved = shutil.which(command) if command else None
            if provider in {"cursor", "cursor_cli"} and not resolved:
                resolved = shutil.which("agent")
            status = resolved or "not-installed"
        print(f"{role:<12} {provider:<14} {model:<22} {mode:<10} {status}")


def specialist_add(args: argparse.Namespace) -> None:
    value = read_json(args.target) if pathlib.Path(args.target).exists() else config_target_skeleton("balanced")
    specialists = value.setdefault("specialists", [])
    if not isinstance(specialists, list):
        raise ConfigError("specialists 必须是数组")
    if any(isinstance(item, dict) and item.get("name") == args.name for item in specialists):
        raise ConfigError(f"specialist 已存在：{args.name}")
    specialists.append({
        "name": args.name,
        "profile": args.profile,
        "purpose": args.purpose,
        "when": args.when,
        "mode": args.mode,
    })
    reject_secrets(value, args.target)
    write_json(args.target, value)
    print(f"specialist 已添加：{args.name} -> {args.profile}")


def specialist_remove(args: argparse.Namespace) -> None:
    value = read_json(args.target) if pathlib.Path(args.target).exists() else config_target_skeleton("balanced")
    specialists = value.setdefault("specialists", [])
    remaining = [
        item for item in specialists
        if not (isinstance(item, dict) and item.get("name") == args.name)
    ]
    if len(remaining) == len(specialists):
        raise ConfigError(f"specialist 不存在：{args.name}")
    value["specialists"] = remaining
    write_json(args.target, value)
    print(f"specialist 已移除：{args.name}")


def print_specialists(config: dict[str, Any]) -> None:
    specialists = config.get("specialists", [])
    if not specialists:
        print("未配置额外 specialist。")
        return
    print(f"{'NAME':<18} {'PROFILE':<28} {'MODE':<10} WHEN")
    for item in specialists:
        print(f"{item['name']:<18} {item['profile']:<28} {item.get('mode', 'optional'):<10} {item['when']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--default", required=True)
    common.add_argument("--global-path")
    common.add_argument("--project-path")

    effective = sub.add_parser("effective", parents=[common])
    effective.add_argument("--preset")
    effective.add_argument("--set", action="append", default=[])
    effective.add_argument("--with-sources", action="store_true")

    validate = sub.add_parser("validate", parents=[common])
    validate.add_argument("--preset")
    validate.add_argument("--set", action="append", default=[])

    init = sub.add_parser("init")
    init.add_argument("--target", required=True)
    init.add_argument("--preset", default="balanced")
    init.add_argument("--force", action="store_true")

    configure_parser = sub.add_parser("configure", parents=[common])
    configure_parser.add_argument("--target", required=True)

    set_parser = sub.add_parser("set")
    set_parser.add_argument("--target", required=True)
    set_parser.add_argument("--expression", action="append", required=True)

    presets = sub.add_parser("presets")
    presets.add_argument("--default", required=True)

    models = sub.add_parser("models", parents=[common])
    models.add_argument("--preset")

    render = sub.add_parser("render-profiles")
    render.add_argument("--config", required=True)
    render.add_argument("--templates", required=True)
    render.add_argument("--output", required=True)
    render.add_argument("--manifest", required=True)
    render.add_argument("--run-id", required=True)

    manifest_lines = sub.add_parser("manifest-lines")
    manifest_lines.add_argument("--manifest", required=True)

    specialist_add_parser = sub.add_parser("specialist-add")
    specialist_add_parser.add_argument("--target", required=True)
    specialist_add_parser.add_argument("--name", required=True)
    specialist_add_parser.add_argument("--profile", required=True)
    specialist_add_parser.add_argument("--purpose", required=True)
    specialist_add_parser.add_argument("--when", required=True)
    specialist_add_parser.add_argument("--mode", choices=("optional", "required", "disabled"), default="optional")

    specialist_remove_parser = sub.add_parser("specialist-remove")
    specialist_remove_parser.add_argument("--target", required=True)
    specialist_remove_parser.add_argument("--name", required=True)

    specialist_list_parser = sub.add_parser("specialist-list", parents=[common])

    args = parser.parse_args()
    try:
        if args.command in {"effective", "validate", "models"}:
            config, sources = resolve_config(
                args.default,
                args.global_path,
                args.project_path,
                getattr(args, "preset", None),
                getattr(args, "set", []),
            )
            warnings = validate_effective(config)
            for warning in warnings:
                print(f"warning: {warning}", file=sys.stderr)
            if args.command == "effective":
                output: dict[str, Any] = config
                if args.with_sources:
                    output = {"config": config, "sources": sources}
                print(json.dumps(output, ensure_ascii=False, indent=2))
            elif args.command == "validate":
                print("配置有效")
            else:
                print_models(config)
        elif args.command == "init":
            write_json(args.target, config_target_skeleton(args.preset), overwrite=args.force)
            print(f"配置已创建：{args.target}")
        elif args.command == "configure":
            configure(args)
        elif args.command == "set":
            value = read_json(args.target) if pathlib.Path(args.target).exists() else config_target_skeleton("balanced")
            for expression in args.expression:
                set_path(value, expression)
            reject_secrets(value, args.target)
            write_json(args.target, value)
            print(f"配置已更新：{args.target}")
        elif args.command == "presets":
            defaults = read_json(args.default, required=True)
            for name, value in sorted(defaults["presets"].items()):
                print(f"{name:<14} max_cycles={value['max_cycles']}")
        elif args.command == "render-profiles":
            render_profiles(args)
        elif args.command == "manifest-lines":
            manifest = read_json(args.manifest, required=True)
            for role, value in manifest["roles"].items():
                if value.get("generated"):
                    print(f"{role}\t{value['name']}\t{value['path']}")
        elif args.command == "specialist-add":
            specialist_add(args)
        elif args.command == "specialist-remove":
            specialist_remove(args)
        elif args.command == "specialist-list":
            config, _ = resolve_config(args.default, args.global_path, args.project_path)
            print_specialists(config)
        return 0
    except (ConfigError, OSError, ValueError) as exc:
        print(f"autoagent config: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
