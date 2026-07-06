"""Policy evaluation helpers for permissions tasks."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Verdict:
    """A pull request gate decision."""

    allowed: bool
    actor: str
    login: str
    reason: str
    message: str | None = None

    @property
    def exit_code(self) -> int:
        """Return the process exit code for this verdict."""
        return 0 if self.allowed else 1

    def to_json(self) -> dict[str, Any]:
        """Return a machine-readable verdict payload."""
        payload: dict[str, Any] = {
            "allowed": self.allowed,
            "actor": self.actor,
            "login": self.login,
            "reason": self.reason,
        }
        if self.message:
            payload["message"] = self.message
        return payload


@dataclass(frozen=True)
class GateError(Exception):
    """A policy or event error that should fail the gate as malformed input."""

    message: str
    field: str | None = None

    @property
    def exit_code(self) -> int:
        """Return the process exit code for malformed input."""
        return 2

    def to_json(self) -> dict[str, Any]:
        """Return a machine-readable error payload."""
        payload: dict[str, Any] = {
            "allowed": False,
            "error": self.message,
            "reason": "malformed input",
        }
        if self.field is not None:
            payload["field"] = self.field
        return payload


def resolve_path(base_dir: Path, raw: str) -> Path:
    """Resolve a user-supplied path relative to the caller's working directory."""
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return base_dir / path


def load_config(path: Path) -> dict[str, Any]:
    """Load a TOML policy config."""
    try:
        with path.open("rb") as fh:
            config = tomllib.load(fh)
    except FileNotFoundError as exc:
        raise GateError(f"config file not found: {path}", field="config") from exc
    except tomllib.TOMLDecodeError as exc:
        raise GateError(f"invalid TOML in {path}: {exc}", field="config") from exc

    if not isinstance(config, dict):
        raise GateError("config must be a TOML table", field="config")
    return config


def load_event(path: Path) -> dict[str, Any]:
    """Load a GitHub event JSON file."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            event = json.load(fh)
    except FileNotFoundError as exc:
        raise GateError(f"event file not found: {path}", field="event") from exc
    except json.JSONDecodeError as exc:
        raise GateError(f"invalid JSON in {path}: {exc}", field="event") from exc

    if not isinstance(event, dict):
        raise GateError("event must be a JSON object", field="event")
    return event


def evaluate_pull_request(config: dict[str, Any], event: dict[str, Any]) -> Verdict:
    """Evaluate a GitHub pull request event against the configured gate policy."""
    pull_request_policy = _pull_request_policy(config)
    allow = _allowlist(pull_request_policy)
    login = _pull_request_login(event)
    message = _message(pull_request_policy)

    actor = f"user:{login}"
    allowed = actor in allow
    reason = (
        f"matched allow entry {actor}"
        if allowed
        else f"{actor} is not in gate.pull_request.allow"
    )

    return Verdict(
        allowed=allowed,
        actor=actor,
        login=login,
        reason=reason,
        message=message,
    )


def format_human_verdict(verdict: Verdict) -> str:
    """Format a verdict for terminal readers."""
    status = "allowed" if verdict.allowed else "denied"
    mark = "✓" if verdict.allowed else "✗"
    lines = [f"{mark} {status}: pull request author {verdict.actor} ({verdict.reason})"]
    if verdict.message:
        lines.append(verdict.message)
    return "\n".join(lines)


def format_json_payload(payload: dict[str, Any]) -> str:
    """Format a machine-readable payload."""
    return json.dumps(payload, sort_keys=True)


def _pull_request_policy(config: dict[str, Any]) -> dict[str, Any]:
    gate_policy = config.get("gate")
    if not isinstance(gate_policy, dict):
        raise GateError("missing [gate.pull_request] policy", field="gate.pull_request")

    policy = gate_policy.get("pull_request")
    if not isinstance(policy, dict):
        raise GateError("missing [gate.pull_request] policy", field="gate.pull_request")

    default = policy.get("default", "deny")
    if default != "deny":
        raise GateError(
            'gate.pull_request.default must be "deny" in this first slice',
            field="gate.pull_request.default",
        )

    return policy


def _allowlist(policy: dict[str, Any]) -> list[str]:
    allow = policy.get("allow", [])
    if not isinstance(allow, list) or not all(isinstance(item, str) for item in allow):
        raise GateError(
            "gate.pull_request.allow must be a list of strings",
            field="gate.pull_request.allow",
        )

    unsupported = [
        principal for principal in allow if not principal.startswith("user:")
    ]
    if unsupported:
        unsupported_list = ", ".join(sorted(unsupported))
        raise GateError(
            f"unsupported principals in allow list: {unsupported_list}",
            field="gate.pull_request.allow",
        )

    if "user:" in allow:
        raise GateError(
            "user principals must include a non-empty login",
            field="gate.pull_request.allow",
        )

    return allow


def _pull_request_login(event: dict[str, Any]) -> str:
    pull_request = event.get("pull_request")
    user = pull_request.get("user") if isinstance(pull_request, dict) else None
    login = user.get("login") if isinstance(user, dict) else None

    if login is None:
        raise GateError(
            "event is missing pull_request.user.login", field="pull_request.user.login"
        )

    if not isinstance(login, str) or not login:
        raise GateError(
            "pull_request.user.login must be a non-empty string",
            field="pull_request.user.login",
        )

    return login


def _message(policy: dict[str, Any]) -> str | None:
    message = policy.get("message")
    if message is not None and not isinstance(message, str):
        raise GateError(
            "gate.pull_request.message must be a string when set",
            field="gate.pull_request.message",
        )
    return message
