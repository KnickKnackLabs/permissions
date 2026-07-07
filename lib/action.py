"""GitHub Action helper functions for permissions."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from textwrap import dedent
from typing import Any

from permissions import (
    GateError,
    Verdict,
    evaluate_gate,
    load_config,
    load_event,
    resolve_path,
)

DEFAULT_DENY_LABEL = "permissions-denied"


def evaluate_from_paths(
    *,
    gate: str,
    config: str,
    event: str,
    workspace: Path,
    team_resolver: Any = None,
) -> tuple[Verdict, dict[str, Any]]:
    """Evaluate a gate from Action input paths."""
    event_payload = load_event(resolve_path(workspace, event))
    verdict = evaluate_gate(
        gate,
        load_config(resolve_path(workspace, config)),
        event_payload,
        team_resolver=team_resolver,
    )
    return verdict, event_payload


def validate_on_deny(on_deny: str) -> None:
    """Validate the requested deny behavior."""
    if on_deny not in {"fail", "close"}:
        raise GateError('on-deny must be "fail" or "close"', field="on-deny")


def parse_bool_input(value: str, *, name: str) -> bool:
    """Parse a GitHub Action boolean-like string input."""
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise GateError(f'{name} must be "true" or "false"', field=name)


def outputs_for_verdict(verdict: Verdict) -> dict[str, str]:
    """Return GitHub Action outputs for a verdict."""
    return {
        "actor": verdict.actor,
        "allowed": json.dumps(verdict.allowed),
        "gate": verdict.gate,
        "login": verdict.login,
        "reason": verdict.reason,
    }


def apply_denied_side_effects(
    *,
    verdict: Verdict,
    event: dict[str, Any],
    repository: str,
    token: str,
    api_url: str = "https://api.github.com",
    label: str = DEFAULT_DENY_LABEL,
    comment: bool = True,
) -> list[str]:
    """Apply configured side effects for a denied event and return action notes."""
    if not repository or "/" not in repository:
        raise GateError("GITHUB_REPOSITORY is required for on-deny=close")
    if not token:
        raise GateError("github-token is required for on-deny=close")

    normalized_api_url = api_url.rstrip("/")
    number = event_number(verdict, event)
    notes: list[str] = []

    if label:
        ensure_label(
            repository=repository,
            token=token,
            api_url=normalized_api_url,
            label=label,
        )
        add_label(
            repository=repository,
            token=token,
            api_url=normalized_api_url,
            number=number,
            label=label,
        )
        notes.append(f"Labeled denied {verdict.gate} with {label}.")

    if comment:
        create_comment(
            repository=repository,
            token=token,
            api_url=normalized_api_url,
            number=number,
            body=deny_comment_body(verdict),
        )
        notes.append(f"Commented on denied {verdict.gate}.")

    close_denied(
        verdict=verdict,
        event=event,
        repository=repository,
        token=token,
        api_url=normalized_api_url,
    )
    notes.append(f"Closed denied {verdict.gate} from {verdict.actor}.")
    return notes


def close_denied(
    *,
    verdict: Verdict,
    event: dict[str, Any],
    repository: str,
    token: str,
    api_url: str = "https://api.github.com",
) -> None:
    """Close the denied GitHub issue or pull request."""
    if not repository or "/" not in repository:
        raise GateError("GITHUB_REPOSITORY is required for on-deny=close")
    if not token:
        raise GateError("github-token is required for on-deny=close")

    normalized_api_url = api_url.rstrip("/")
    if verdict.gate == "pull-request":
        number = _event_number(event, "pull_request", "pull request")
        path = f"/repos/{repository}/pulls/{number}"
        payload: dict[str, Any] = {"state": "closed"}
    else:
        number = _event_number(event, "issue", "issue")
        path = f"/repos/{repository}/issues/{number}"
        payload = {"state": "closed", "state_reason": "not_planned"}

    request_json(
        "PATCH",
        f"{normalized_api_url}{path}",
        token,
        payload,
    )


def ensure_label(*, repository: str, token: str, api_url: str, label: str) -> None:
    """Create the deny label if it does not already exist."""
    try:
        request_json(
            "POST",
            f"{api_url}/repos/{repository}/labels",
            token,
            {
                "name": label,
                "color": "b60205",
                "description": "Closed by permissions policy",
            },
        )
    except GateError as exc:
        if "HTTP 422" in exc.message:
            return
        raise


def add_label(
    *, repository: str, token: str, api_url: str, number: int, label: str
) -> None:
    """Apply a label to a denied issue or pull request conversation."""
    request_json(
        "POST",
        f"{api_url}/repos/{repository}/issues/{number}/labels",
        token,
        {"labels": [label]},
    )


def create_comment(
    *, repository: str, token: str, api_url: str, number: int, body: str
) -> None:
    """Create an explanatory comment on a denied issue or pull request."""
    request_json(
        "POST",
        f"{api_url}/repos/{repository}/issues/{number}/comments",
        token,
        {"body": body},
    )


def deny_comment_body(verdict: Verdict) -> str:
    """Return the default comment body for a denied event."""
    if verdict.gate == "pull-request":
        return pull_request_deny_comment(verdict.login)
    return issue_deny_comment(verdict.login)


def issue_deny_comment(login: str) -> str:
    """Return the default comment body for a denied issue."""
    return dedent(
        f"""
        Thanks for opening this. This repository uses [permissions](https://github.com/KnickKnackLabs/permissions)
        to limit who can open issues.

        @{login} is not currently allowed by this repository's `gate.issue` policy,
        so this issue was closed automatically.

        If you think this is a mistake, please contact a maintainer.
        """
    ).strip()


def pull_request_deny_comment(login: str) -> str:
    """Return the default comment body for a denied pull request."""
    return dedent(
        f"""
        Thanks for the contribution. This repository uses [permissions](https://github.com/KnickKnackLabs/permissions)
        to limit who can open pull requests.

        @{login} is not currently allowed by this repository's `gate.pull_request` policy,
        so this pull request was closed automatically.

        If you think this is a mistake, please contact a maintainer.
        """
    ).strip()


def event_number(verdict: Verdict, event: dict[str, Any]) -> int:
    """Return the GitHub issue/PR number for a verdict's event payload."""
    if verdict.gate == "pull-request":
        return _event_number(event, "pull_request", "pull request")
    return _event_number(event, "issue", "issue")


def request_json(method: str, url: str, token: str, payload: dict[str, Any]) -> None:
    """Send a JSON request to GitHub."""
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "KnickKnackLabs-permissions-action",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status < 200 or response.status >= 300:
                raise GateError(f"GitHub API returned HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise GateError(
            f"GitHub API returned HTTP {exc.code} while mutating denied event: {detail}"
        ) from exc
    except urllib.error.URLError as exc:
        raise GateError(
            f"GitHub API request failed while mutating denied event: {exc}"
        ) from exc


def write_outputs(output_path: str | None, outputs: dict[str, str]) -> None:
    """Write GitHub Action outputs when GITHUB_OUTPUT is available."""
    if not output_path:
        return

    with Path(output_path).open("a", encoding="utf-8") as fh:
        for key, value in outputs.items():
            fh.write(f"{key}={value}\n")


def _event_number(event: dict[str, Any], key: str, label: str) -> int:
    payload = event.get(key)
    number = payload.get("number") if isinstance(payload, dict) else None
    if not isinstance(number, int):
        raise GateError(f"event is missing {key}.number for closing denied {label}")
    return number
