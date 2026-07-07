"""Policy evaluation helpers for permissions tasks."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

GateName = Literal["pull-request", "issue"]
PolicyDefault = Literal["allow", "deny"]


@dataclass(frozen=True)
class Verdict:
    """A repository event gate decision."""

    allowed: bool
    actor: str
    login: str
    reason: str
    gate: GateName
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
            "gate": self.gate,
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


def normalize_gate(raw: str) -> GateName:
    """Normalize a user-supplied gate name."""
    normalized = raw.strip().replace("_", "-")
    if normalized == "pull-request":
        return "pull-request"
    if normalized == "issue":
        return "issue"
    raise GateError(
        'gate must be "pull-request" or "issue"',
        field="gate",
    )


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


def evaluate_gate(gate: str, config: dict[str, Any], event: dict[str, Any]) -> Verdict:
    """Evaluate a supported event gate against the configured policy."""
    normalized = normalize_gate(gate)
    if normalized == "pull-request":
        return evaluate_pull_request(config, event)
    return evaluate_issue(config, event)


def evaluate_pull_request(config: dict[str, Any], event: dict[str, Any]) -> Verdict:
    """Evaluate a GitHub pull request event against the configured gate policy."""
    return _evaluate_author_gate(
        gate="pull-request",
        policy=_gate_policy(config, "pull_request"),
        login=_pull_request_login(event),
    )


def evaluate_issue(config: dict[str, Any], event: dict[str, Any]) -> Verdict:
    """Evaluate a GitHub issue event against the configured gate policy."""
    return _evaluate_author_gate(
        gate="issue",
        policy=_gate_policy(config, "issue"),
        login=_issue_login(event),
    )


def format_human_verdict(verdict: Verdict) -> str:
    """Format a verdict for terminal readers."""
    status = "allowed" if verdict.allowed else "denied"
    mark = "✓" if verdict.allowed else "✗"
    target = "pull request" if verdict.gate == "pull-request" else "issue"
    lines = [f"{mark} {status}: {target} author {verdict.actor} ({verdict.reason})"]
    if verdict.message:
        lines.append(verdict.message)
    return "\n".join(lines)


def format_json_payload(payload: dict[str, Any]) -> str:
    """Format a machine-readable payload."""
    return json.dumps(payload, sort_keys=True)


def _evaluate_author_gate(
    gate: GateName, policy: dict[str, Any], login: str
) -> Verdict:
    default = _default(policy, gate)
    allow = _principal_list(policy, "allow", gate)
    deny = _principal_list(policy, "deny", gate)
    message = _message(policy, gate)

    actor = f"user:{login}"
    policy_key = _policy_key(gate)

    if actor in deny:
        allowed = False
        reason = f"matched deny entry {actor}"
    elif actor in allow:
        allowed = True
        reason = f"matched allow entry {actor}"
    elif default == "allow":
        allowed = True
        reason = f"gate.{policy_key}.default is allow"
    else:
        allowed = False
        reason = f"{actor} is not in gate.{policy_key}.allow"

    return Verdict(
        allowed=allowed,
        actor=actor,
        login=login,
        reason=reason,
        gate=gate,
        message=message,
    )


def _gate_policy(config: dict[str, Any], policy_key: str) -> dict[str, Any]:
    field = f"gate.{policy_key}"
    gate_policy = config.get("gate")
    if not isinstance(gate_policy, dict):
        raise GateError(f"missing [{field}] policy", field=field)

    policy = gate_policy.get(policy_key)
    if not isinstance(policy, dict):
        raise GateError(f"missing [{field}] policy", field=field)

    return policy


def _default(policy: dict[str, Any], gate: GateName) -> PolicyDefault:
    field = f"gate.{_policy_key(gate)}.default"
    default = policy.get("default", "deny")
    if default == "deny" or default == "allow":
        return default
    raise GateError(f'{field} must be "deny" or "allow"', field=field)


def _principal_list(policy: dict[str, Any], key: str, gate: GateName) -> list[str]:
    field = f"gate.{_policy_key(gate)}.{key}"
    principals = policy.get(key, [])
    if not isinstance(principals, list) or not all(
        isinstance(item, str) for item in principals
    ):
        raise GateError(
            f"{field} must be a list of strings",
            field=field,
        )

    unsupported = [
        principal for principal in principals if not principal.startswith("user:")
    ]
    if unsupported:
        unsupported_list = ", ".join(sorted(unsupported))
        raise GateError(
            f"unsupported principals in {key} list: {unsupported_list}",
            field=field,
        )

    if "user:" in principals:
        raise GateError(
            "user principals must include a non-empty login",
            field=field,
        )

    return principals


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


def _issue_login(event: dict[str, Any]) -> str:
    issue = event.get("issue")
    if not isinstance(issue, dict):
        raise GateError("event is missing issue", field="issue")

    if "pull_request" in issue:
        raise GateError(
            "issue gate does not evaluate pull request conversation events",
            field="issue.pull_request",
        )

    user = issue.get("user")
    login = user.get("login") if isinstance(user, dict) else None

    if login is None:
        raise GateError("event is missing issue.user.login", field="issue.user.login")

    if not isinstance(login, str) or not login:
        raise GateError(
            "issue.user.login must be a non-empty string",
            field="issue.user.login",
        )

    return login


def _message(policy: dict[str, Any], gate: GateName) -> str | None:
    field = f"gate.{_policy_key(gate)}.message"
    message = policy.get("message")
    if message is not None and not isinstance(message, str):
        raise GateError(
            f"{field} must be a string when set",
            field=field,
        )
    return message


def _policy_key(gate: GateName) -> str:
    return "pull_request" if gate == "pull-request" else "issue"
