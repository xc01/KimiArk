from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AUTHORIZATION_SCHEMA_VERSION = "KIMIARK_CODEX_CLI_AUTHORIZATION_V1"


def load_authorization(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != AUTHORIZATION_SCHEMA_VERSION:
        raise RuntimeError(f"unsupported authorization schema: {config.get('schema_version')!r}")
    required = {"provider", "model", "reasoning_effort", "extra_config_values"}
    missing = sorted(required - set(config))
    if missing:
        raise RuntimeError(f"authorization config missing fields: {missing}")
    if not isinstance(config["provider"], str) or not config["provider"]:
        raise RuntimeError("authorization provider must be a non-empty string")
    if not isinstance(config["model"], str) or not config["model"]:
        raise RuntimeError("authorization model must be a non-empty string")
    if config["reasoning_effort"] not in {"minimal", "low", "medium", "high", "xhigh"}:
        raise RuntimeError("authorization reasoning_effort is invalid")
    if not isinstance(config["extra_config_values"], list) or any(not isinstance(value, str) for value in config["extra_config_values"]):
        raise RuntimeError("authorization extra_config_values must be an array of strings")
    return config


def validate_cli_authorization(
    config_path: Path, command: list[str], *, prompt_sha256: str | None = None
) -> dict[str, Any]:
    config = load_authorization(config_path)
    errors: list[str] = []
    if command[:2] != ["codex", "exec"]:
        errors.append("command must begin with codex exec")
    if "--json" not in command:
        errors.append("command must enable --json")
    sandbox_index = command.index("--sandbox") if "--sandbox" in command else None
    if sandbox_index is None or sandbox_index + 1 >= len(command) or command[sandbox_index + 1] != "read-only":
        errors.append("command must run with --sandbox read-only")

    model_values = [command[index + 1] for index, value in enumerate(command) if value == "-m" and index + 1 < len(command)]
    if model_values != [config["model"]]:
        errors.append(f"model authorization mismatch: observed {model_values!r}, required {config['model']!r}")

    overrides = [command[index + 1] for index, value in enumerate(command) if value == "-c" and index + 1 < len(command)]
    required_overrides = [
        'model_provider="openai"',
        f'model_reasoning_effort="{config["reasoning_effort"]}"',
        *config["extra_config_values"],
    ]
    if overrides != required_overrides:
        errors.append(f"configuration override authorization mismatch: observed {overrides!r}, required {required_overrides!r}")
    if overrides and any(overrides.count(value) > 1 for value in overrides):
        errors.append("duplicate configuration override is forbidden")

    if config.get("prompt_sha256") is not None and config["prompt_sha256"] != prompt_sha256:
        errors.append("frozen prompt hash does not match authorization")
    if errors:
        raise RuntimeError("Codex CLI authorization rejected before STARTED: " + "; ".join(errors))
    return {
        "schema_version": AUTHORIZATION_SCHEMA_VERSION,
        "status": "AUTHORIZED",
        "authorization_path": str(config_path),
        "argv": command,
        "provider": config["provider"],
        "model": config["model"],
        "reasoning_effort": config["reasoning_effort"],
        "prompt_sha256": prompt_sha256,
    }
