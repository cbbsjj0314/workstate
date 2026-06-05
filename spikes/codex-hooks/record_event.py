#!/usr/bin/env python3
"""Record sanitized Codex hook events for the WorkState M0 spike."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


SCHEMA_VERSION = 1
SOURCE = "codex"
STOP_STDOUT = '{"continue":true}'
HANDOFF_RE = re.compile(r"(?mi)^WorkState-Handoff-ID:\s*(ws_[0-9A-HJKMNP-TV-Z]{10,64})\s*$")
SUPPORTED_EVENTS = {"SessionStart", "UserPromptSubmit", "PostToolUse", "Stop"}
APPLY_PATCH_ALIASES = {"apply_patch", "Edit", "Write"}


def main() -> int:
    configured_event = sys.argv[1] if len(sys.argv) > 1 else ""
    emit_stop_stdout = configured_event == "Stop"

    try:
        if configured_event not in SUPPORTED_EVENTS:
            warn("unsupported or missing configured hook event")
            return finish(emit_stop_stdout)

        raw_stdin = sys.stdin.read()
        try:
            payload = json.loads(raw_stdin or "{}")
        except json.JSONDecodeError:
            warn("malformed hook input JSON")
            return finish(emit_stop_stdout)

        if not isinstance(payload, dict):
            warn("hook input JSON was not an object")
            return finish(emit_stop_stdout)

        stdin_event = payload.get("hook_event_name")
        if stdin_event != configured_event:
            warn("hook input event name was missing or mismatched")
            return finish(emit_stop_stdout)

        validation_error = validate_required_fields(configured_event, payload)
        if validation_error is not None:
            warn(validation_error)
            return finish(emit_stop_stdout)

        record = normalize_record(configured_event, payload)
        append_record(record)
    except Exception as exc:  # Fail open for all hook paths.
        warn(f"recorder failure: {exc.__class__.__name__}")

    return finish(emit_stop_stdout)


def finish(emit_stop_stdout: bool) -> int:
    if emit_stop_stdout:
        sys.stdout.write(STOP_STDOUT)
    return 0


def warn(message: str) -> None:
    print(f"workstate codex hook recorder: {message}", file=sys.stderr)


def validate_required_fields(hook_event_name: str, payload: dict[str, Any]) -> str | None:
    requirements = {
        "SessionStart": {"source": str},
        "UserPromptSubmit": {"prompt": str, "turn_id": str},
        "PostToolUse": {"tool_name": str, "tool_use_id": str, "turn_id": str},
        "Stop": {"stop_hook_active": bool, "turn_id": str},
    }
    required_fields = requirements.get(hook_event_name, {})
    for field, expected_type in required_fields.items():
        value = payload.get(field)
        if not isinstance(value, expected_type):
            return f"required hook input field was missing or invalid: {field}"

    if hook_event_name == "PostToolUse" and "tool_input" not in payload:
        return "required hook input field was missing or invalid: tool_input"

    return None


def normalize_record(hook_event_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    cwd = string_or_none(payload.get("cwd")) or os.getcwd()
    return {
        "schema_version": SCHEMA_VERSION,
        "recorded_at": utc_now(),
        "source": SOURCE,
        "hook_event_name": hook_event_name,
        "session_id": string_or_none(payload.get("session_id")),
        "turn_id": string_or_none(payload.get("turn_id")),
        "cwd": cwd,
        "repo_root": repo_root_for(cwd),
        "model": string_or_none(payload.get("model")),
        "permission_mode": string_or_none(payload.get("permission_mode")),
        "event_data": event_data_for(hook_event_name, payload),
    }


def event_data_for(hook_event_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if hook_event_name == "SessionStart":
        return {
            "session_start_source": string_or_none(payload.get("source")),
        }
    if hook_event_name == "UserPromptSubmit":
        prompt = string_or_none(payload.get("prompt")) or ""
        handoff_match = HANDOFF_RE.search(prompt)
        return {
            "prompt_length": len(prompt),
            "prompt_sha256": sha256_text(prompt),
            "workstate_handoff_id_detected": handoff_match is not None,
            "workstate_handoff_id": handoff_match.group(1) if handoff_match else None,
        }
    if hook_event_name == "PostToolUse":
        raw_tool_name = string_or_none(payload.get("tool_name"))
        tool_name = normalize_tool_name(raw_tool_name)
        tool_input = payload.get("tool_input")
        return {
            "tool_name": tool_name,
            "tool_use_id": string_or_none(payload.get("tool_use_id")),
            "tool_input_sha256": sha256_json(tool_input),
            "tool_response_present": "tool_response" in payload and payload.get("tool_response") is not None,
            "file_edit_candidate": tool_name == "apply_patch",
        }
    if hook_event_name == "Stop":
        message = string_or_none(payload.get("last_assistant_message"))
        return {
            "stop_hook_active": bool_or_none(payload.get("stop_hook_active")),
            "last_assistant_message_present": message is not None,
            "last_assistant_message_length": len(message) if message is not None else 0,
            "last_assistant_message_sha256": sha256_text(message) if message is not None else None,
        }
    return {}


def normalize_tool_name(tool_name: str | None) -> str | None:
    if tool_name in APPLY_PATCH_ALIASES:
        return "apply_patch"
    return tool_name


def append_record(record: dict[str, Any]) -> None:
    log_path = event_log_path()
    repo_root = record.get("repo_root")
    if repo_root is not None and is_relative_to(log_path.resolve(), Path(repo_root).resolve()):
        raise RuntimeError("event log path is inside the repository")

    log_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(log_path.parent, 0o700)
    except OSError:
        pass

    line = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)
    try:
        os.chmod(log_path, 0o600)
    except OSError:
        pass


def event_log_path() -> Path:
    override = os.environ.get("WORKSTATE_CODEX_EVENT_LOG")
    if override:
        return Path(override).expanduser()

    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        base = Path(xdg_data_home).expanduser()
    else:
        base = Path.home() / ".local" / "share"
    return base / "workstate" / "events" / "codex.jsonl"


def repo_root_for(cwd: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_json(value: Any) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def bool_or_none(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
