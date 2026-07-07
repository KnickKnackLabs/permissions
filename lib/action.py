"""GitHub Action helper functions for permissions."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from permissions import (
    GateError,
    Verdict,
    evaluate_gate,
    load_config,
    load_event,
    resolve_path,
)


def evaluate_from_paths(
    *, gate: str, config: str, event: str, workspace: Path
) -> tuple[Verdict, dict[str, Any]]:
    """Evaluate a gate from Action input paths."""
    event_payload = load_event(resolve_path(workspace, event))
    verdict = evaluate_gate(
        gate,
        load_config(resolve_path(workspace, config)),
        event_payload,
    )
    return verdict, event_payload


def validate_on_deny(on_deny: str) -> None:
    """Validate the requested deny behavior."""
    if on_deny not in {"fail", "close"}:
        raise GateError('on-deny must be "fail" or "close"', field="on-deny")


def outputs_for_verdict(verdict: Verdict) -> dict[str, str]:
    """Return GitHub Action outputs for a verdict."""
    return {
        "actor": verdict.actor,
        "allowed": json.dumps(verdict.allowed),
        "gate": verdict.gate,
        "login": verdict.login,
        "reason": verdict.reason,
    }


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
    else:
        number = _event_number(event, "issue", "issue")
        path = f"/repos/{repository}/issues/{number}"

    request_json(
        "PATCH",
        f"{normalized_api_url}{path}",
        token,
        {"state": "closed"},
    )


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
            f"GitHub API returned HTTP {exc.code} while closing denied event: {detail}"
        ) from exc
    except urllib.error.URLError as exc:
        raise GateError(
            f"GitHub API request failed while closing denied event: {exc}"
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
