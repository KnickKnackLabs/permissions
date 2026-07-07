#!/usr/bin/env python3
"""Unit tests for GitHub API helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_DIR / "lib"))

from github import (  # noqa: E402
    GitHubAPIError,
    GitHubTeamResolver,
    quote_path,
    team_resolver_from_env,
)
from permissions import GateError  # noqa: E402


class GitHubTeamResolverTest(unittest.TestCase):
    def test_quote_path_escapes_one_segment(self) -> None:
        self.assertEqual(quote_path("team/name"), "team%2Fname")

    def test_team_resolver_from_env_uses_membership_token_first(self) -> None:
        resolver = team_resolver_from_env(
            {
                "PERMISSIONS_MEMBERSHIP_TOKEN": "membership-token",
                "GITHUB_TOKEN": "github-token",
                "GITHUB_API_URL": "https://api.github.test",
            }
        )

        self.assertIsInstance(resolver, GitHubTeamResolver)
        assert isinstance(resolver, GitHubTeamResolver)
        self.assertEqual(resolver.token, "membership-token")
        self.assertEqual(resolver.api_url, "https://api.github.test")

    def test_team_resolver_from_env_falls_back_to_github_token(self) -> None:
        resolver = team_resolver_from_env({"GITHUB_TOKEN": "github-token"})

        self.assertIsInstance(resolver, GitHubTeamResolver)
        assert isinstance(resolver, GitHubTeamResolver)
        self.assertEqual(resolver.token, "github-token")

    def test_team_resolver_from_env_returns_none_without_token(self) -> None:
        self.assertIsNone(team_resolver_from_env({}))

    def test_active_membership_matches(self) -> None:
        resolver = GitHubTeamResolver("token")

        with mock.patch.object(
            resolver,
            "_get_json",
            side_effect=[{"id": 1}, {"state": "active"}],
        ) as get_json:
            self.assertTrue(
                resolver.is_team_member(
                    org="KnickKnackLabs", slug="agents", login="brownie-ricon"
                )
            )

        self.assertEqual(
            [call.args[0] for call in get_json.call_args_list],
            [
                "/orgs/KnickKnackLabs/teams/agents",
                "/orgs/KnickKnackLabs/teams/agents/memberships/brownie-ricon",
            ],
        )

    def test_pending_membership_does_not_match(self) -> None:
        resolver = GitHubTeamResolver("token")

        with mock.patch.object(
            resolver,
            "_get_json",
            side_effect=[{"id": 1}, {"state": "pending"}],
        ):
            self.assertFalse(
                resolver.is_team_member(
                    org="KnickKnackLabs", slug="agents", login="brownie-ricon"
                )
            )

    def test_missing_membership_does_not_match_existing_team(self) -> None:
        resolver = GitHubTeamResolver("token")

        with mock.patch.object(
            resolver,
            "_get_json",
            side_effect=[{"id": 1}, GitHubAPIError(404, "HTTP 404: Not Found")],
        ):
            self.assertFalse(
                resolver.is_team_member(
                    org="KnickKnackLabs", slug="agents", login="stranger"
                )
            )

    def test_missing_team_fails_closed(self) -> None:
        resolver = GitHubTeamResolver("token")

        with mock.patch.object(
            resolver,
            "_get_json",
            side_effect=GitHubAPIError(404, "HTTP 404: Not Found"),
        ):
            with self.assertRaises(GateError) as raised:
                resolver.is_team_member(
                    org="KnickKnackLabs", slug="missing", login="brownie-ricon"
                )

        self.assertIn("team not found", raised.exception.message)
        self.assertEqual(raised.exception.field, "team")

    def test_forbidden_membership_check_fails_closed(self) -> None:
        resolver = GitHubTeamResolver("token")

        with mock.patch.object(
            resolver,
            "_get_json",
            side_effect=[{"id": 1}, GitHubAPIError(403, "HTTP 403: Forbidden")],
        ):
            with self.assertRaises(GateError) as raised:
                resolver.is_team_member(
                    org="KnickKnackLabs", slug="agents", login="brownie-ricon"
                )

        self.assertIn("could not resolve team principal", raised.exception.message)
        self.assertEqual(raised.exception.field, "team")

    def test_membership_results_are_cached(self) -> None:
        resolver = GitHubTeamResolver("token")

        with mock.patch.object(
            resolver,
            "_get_json",
            side_effect=[{"id": 1}, {"state": "active"}],
        ) as get_json:
            self.assertTrue(
                resolver.is_team_member(
                    org="KnickKnackLabs", slug="agents", login="brownie-ricon"
                )
            )
            self.assertTrue(
                resolver.is_team_member(
                    org="KnickKnackLabs", slug="agents", login="brownie-ricon"
                )
            )

        self.assertEqual(get_json.call_count, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
