"""GitHub API helpers for permissions."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from permissions import GateError


@dataclass(frozen=True)
class GitHubAPIError(Exception):
    """A sanitized GitHub API failure."""

    status: int | None
    message: str


def team_resolver_from_env(env: Mapping[str, str]) -> GitHubTeamResolver | None:
    """Build a team resolver from Action or CLI environment variables."""
    token = (
        env.get("PERMISSIONS_MEMBERSHIP_TOKEN")
        or env.get("GITHUB_MEMBERSHIP_TOKEN")
        or env.get("GITHUB_TOKEN")
        or env.get("GH_TOKEN")
    )
    if not token:
        return None
    return GitHubTeamResolver(
        token,
        api_url=env.get("GITHUB_API_URL", "https://api.github.com"),
    )


class GitHubTeamResolver:
    """Resolve GitHub team membership through the REST API."""

    def __init__(self, token: str, api_url: str = "https://api.github.com") -> None:
        if not token:
            raise GateError("a GitHub token is required to resolve team principals")
        self.token = token
        self.api_url = api_url.rstrip("/")
        self._team_exists: dict[tuple[str, str], bool] = {}
        self._memberships: dict[tuple[str, str, str], bool] = {}

    def is_team_member(self, *, org: str, slug: str, login: str) -> bool:
        """Return whether login is an active member of org/team slug."""
        membership_key = (org, slug, login)
        if membership_key in self._memberships:
            return self._memberships[membership_key]

        self._ensure_team_exists(org, slug)
        try:
            payload = self._get_json(
                f"/orgs/{quote_path(org)}/teams/{quote_path(slug)}"
                f"/memberships/{quote_path(login)}"
            )
        except GitHubAPIError as exc:
            if exc.status == 404:
                self._memberships[membership_key] = False
                return False
            raise team_resolution_error(org, slug, exc) from exc

        is_member = payload.get("state") == "active"
        self._memberships[membership_key] = is_member
        return is_member

    def _ensure_team_exists(self, org: str, slug: str) -> None:
        team_key = (org, slug)
        if team_key in self._team_exists:
            return

        try:
            self._get_json(f"/orgs/{quote_path(org)}/teams/{quote_path(slug)}")
        except GitHubAPIError as exc:
            raise team_resolution_error(org, slug, exc) from exc
        self._team_exists[team_key] = True

    def _get_json(self, path: str) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.api_url}{path}",
            method="GET",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "KnickKnackLabs-permissions",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise GitHubAPIError(exc.code, github_error_message(exc)) from exc
        except urllib.error.URLError as exc:
            raise GitHubAPIError(None, str(exc)) from exc

        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise GitHubAPIError(None, "GitHub API returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise GitHubAPIError(None, "GitHub API returned a non-object payload")
        return payload


def quote_path(value: str) -> str:
    """Quote one URL path segment."""
    return urllib.parse.quote(value, safe="")


def github_error_message(exc: urllib.error.HTTPError) -> str:
    """Return a sanitized GitHub API error message."""
    detail = exc.read().decode("utf-8", errors="replace")
    if not detail:
        return f"HTTP {exc.code}"
    try:
        payload = json.loads(detail)
    except json.JSONDecodeError:
        return f"HTTP {exc.code}"
    message = payload.get("message") if isinstance(payload, dict) else None
    if isinstance(message, str) and message:
        return f"HTTP {exc.code}: {message}"
    return f"HTTP {exc.code}"


def team_resolution_error(org: str, slug: str, exc: GitHubAPIError) -> GateError:
    """Build a fail-closed team resolution error."""
    if exc.status == 404:
        message = (
            f"team not found or token cannot read team membership: team:{org}/{slug}"
        )
    else:
        detail = f": {exc.message}" if exc.message else ""
        message = f"could not resolve team principal team:{org}/{slug}{detail}"
    return GateError(message, field="team")
