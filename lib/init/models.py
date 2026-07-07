"""Models and validation for permissions init."""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from permissions import GateError

SUPPORTED_GATES = ("issue", "pull-request")
DEFAULT_ACTION_REF = "v0.5.0"
DEFAULT_MEMBERSHIP_SECRET = "PERMISSIONS_MEMBERSHIP_TOKEN"


@dataclass(frozen=True)
class InitOptions:
    """Options for initializing repository permissions."""

    gates: tuple[str, ...]
    allow: tuple[str, ...]
    on_deny: str = "close"
    action_ref: str = DEFAULT_ACTION_REF
    membership_token_secret: str = ""
    write: bool = False
    force: bool = False
    allow_default_membership_token: bool = False


@dataclass(frozen=True)
class PlannedFile:
    """A file that init may write."""

    path: Path
    content: str

    def status(self, root: Path) -> str:
        """Return the file's status relative to the current filesystem."""
        full_path = root / self.path
        if not full_path.exists():
            return "create"
        existing = full_path.read_text(encoding="utf-8")
        if existing == self.content:
            return "unchanged"
        return "update"


@dataclass(frozen=True)
class InitPlan:
    """Concrete permissions init plan."""

    options: InitOptions
    files: tuple[PlannedFile, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)
    guidance: tuple[str, ...] = field(default_factory=tuple)

    def to_json(self, root: Path) -> dict[str, Any]:
        """Return a JSON-serializable plan summary."""
        return {
            "write": self.options.write,
            "gates": list(self.options.gates),
            "allow": list(self.options.allow),
            "on_deny": self.options.on_deny,
            "action_ref": self.options.action_ref,
            "membership_token_secret": self.options.membership_token_secret,
            "files": [
                {"path": str(file.path), "status": file.status(root)}
                for file in self.files
            ],
            "warnings": list(self.warnings),
            "guidance": list(self.guidance),
        }


def parse_usage_list(value: str | None) -> tuple[str, ...]:
    """Parse a variadic #USAGE value into a tuple."""
    if not value:
        return ()
    return tuple(item for item in shlex.split(value) if item)


def bool_from_env(value: str | None) -> bool:
    """Return whether a #USAGE boolean env value is true."""
    return (value or "false").lower() == "true"


def options_from_env(env: dict[str, str]) -> InitOptions:
    """Build init options from mise #USAGE environment variables."""
    gates = tuple(
        normalize_gate(gate) for gate in parse_usage_list(env.get("usage_gate"))
    )
    allow = parse_usage_list(env.get("usage_allow"))
    return InitOptions(
        gates=gates,
        allow=allow,
        on_deny=env.get("usage_on_deny") or "",
        action_ref=env.get("usage_action_ref") or DEFAULT_ACTION_REF,
        membership_token_secret=env.get("usage_membership_token_secret") or "",
        write=bool_from_env(env.get("usage_write")),
        force=bool_from_env(env.get("usage_force")),
        allow_default_membership_token=bool_from_env(
            env.get("usage_allow_default_membership_token")
        ),
    )


def validate_options(options: InitOptions) -> InitOptions:
    """Validate and normalize init options."""
    gates = tuple(dict.fromkeys(normalize_gate(gate) for gate in options.gates))
    if not gates:
        raise GateError("at least one --gate is required")
    unsupported = [gate for gate in gates if gate not in SUPPORTED_GATES]
    if unsupported:
        raise GateError(f"unsupported gate(s): {', '.join(unsupported)}")

    allow = tuple(dict.fromkeys(options.allow))
    if not allow:
        raise GateError("at least one --allow principal is required")
    for principal in allow:
        validate_principal(principal)

    on_deny = options.on_deny or "close"
    if on_deny not in {"fail", "close"}:
        raise GateError('on-deny must be "fail" or "close"')

    return InitOptions(
        gates=gates,
        allow=allow,
        on_deny=on_deny,
        action_ref=options.action_ref or DEFAULT_ACTION_REF,
        membership_token_secret=options.membership_token_secret,
        write=options.write,
        force=options.force,
        allow_default_membership_token=options.allow_default_membership_token,
    )


def normalize_gate(gate: str) -> str:
    """Normalize a gate name."""
    normalized = gate.strip().replace("_", "-")
    if normalized == "pr":
        return "pull-request"
    return normalized


def validate_principal(principal: str) -> None:
    """Validate init-supported principal syntax."""
    if principal.startswith("user:") and principal.removeprefix("user:"):
        return
    if principal.startswith("team:"):
        rest = principal.removeprefix("team:")
        org, sep, slug = rest.partition("/")
        if org and sep and slug:
            return
    raise GateError(
        f"unsupported principal {principal!r}; use user:<login> or team:<org>/<slug>"
    )


def has_team_principals(principals: tuple[str, ...]) -> bool:
    """Return whether any configured principal is a team principal."""
    return any(principal.startswith("team:") for principal in principals)
