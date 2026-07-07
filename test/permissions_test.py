#!/usr/bin/env python3
"""Unit tests for permissions policy helpers."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_DIR / "lib"))

from permissions import (  # noqa: E402
    GateError,
    Verdict,
    evaluate_gate,
    evaluate_issue,
    evaluate_pull_request,
    format_human_verdict,
    format_json_payload,
    load_config,
    load_event,
    normalize_gate,
    resolve_path,
)


class FakeTeamResolver:
    def __init__(self, memberships: set[tuple[str, str, str]]) -> None:
        self.memberships = memberships
        self.calls: list[tuple[str, str, str]] = []

    def is_team_member(self, *, org: str, slug: str, login: str) -> bool:
        self.calls.append((org, slug, login))
        return (org, slug, login) in self.memberships


class PathResolutionTest(unittest.TestCase):
    def test_resolve_path_uses_base_dir_for_relative_paths(self) -> None:
        base_dir = Path("/tmp/example-caller")

        self.assertEqual(
            resolve_path(base_dir, "permissions.toml"), base_dir / "permissions.toml"
        )

    def test_resolve_path_preserves_absolute_paths(self) -> None:
        absolute = Path("/tmp/event.json")

        self.assertEqual(
            resolve_path(Path("/tmp/example-caller"), str(absolute)), absolute
        )


class LoadingTest(unittest.TestCase):
    def test_load_config_reads_toml(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "permissions.toml"
            config_path.write_text(
                '[gate.pull_request]\ndefault = "deny"\n', encoding="utf-8"
            )

            self.assertEqual(
                load_config(config_path)["gate"]["pull_request"]["default"], "deny"
            )

    def test_load_event_requires_json_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            event_path = Path(tmpdir) / "event.json"
            event_path.write_text("[]", encoding="utf-8")

            with self.assertRaises(GateError) as raised:
                load_event(event_path)

        self.assertEqual(raised.exception.field, "event")
        self.assertEqual(raised.exception.exit_code, 2)


class GateSelectionTest(unittest.TestCase):
    def test_normalize_gate_accepts_supported_gate_names(self) -> None:
        self.assertEqual(normalize_gate("pull_request"), "pull-request")
        self.assertEqual(normalize_gate("pull-request"), "pull-request")
        self.assertEqual(normalize_gate("issue"), "issue")

    def test_normalize_gate_rejects_unknown_gate_names(self) -> None:
        with self.assertRaises(GateError) as raised:
            normalize_gate("issue-comment")

        self.assertEqual(raised.exception.field, "gate")

    def test_evaluate_gate_dispatches_to_issue_gate(self) -> None:
        verdict = evaluate_gate(
            "issue",
            {"gate": {"issue": {"default": "deny", "allow": ["user:rikonor"]}}},
            {"issue": {"number": 1, "user": {"login": "rikonor"}}},
        )

        self.assertTrue(verdict.allowed)
        self.assertEqual(verdict.gate, "issue")


class PullRequestEvaluationTest(unittest.TestCase):
    def test_allowed_user_returns_allowed_verdict(self) -> None:
        verdict = evaluate_pull_request(
            {
                "gate": {
                    "pull_request": {
                        "default": "deny",
                        "allow": ["user:brownie-ricon"],
                        "message": "configured principals only",
                    }
                }
            },
            {"pull_request": {"number": 2, "user": {"login": "brownie-ricon"}}},
        )

        self.assertEqual(
            verdict,
            Verdict(
                allowed=True,
                actor="user:brownie-ricon",
                login="brownie-ricon",
                reason="matched allow entry user:brownie-ricon",
                gate="pull-request",
                message="configured principals only",
            ),
        )
        self.assertEqual(verdict.exit_code, 0)

    def test_denied_user_returns_denied_verdict(self) -> None:
        verdict = evaluate_pull_request(
            {"gate": {"pull_request": {"default": "deny", "allow": ["user:rikonor"]}}},
            {"pull_request": {"number": 3, "user": {"login": "stranger"}}},
        )

        self.assertFalse(verdict.allowed)
        self.assertEqual(verdict.actor, "user:stranger")
        self.assertEqual(verdict.gate, "pull-request")
        self.assertEqual(verdict.exit_code, 1)

    def test_missing_policy_raises_gate_error(self) -> None:
        with self.assertRaises(GateError) as raised:
            evaluate_pull_request({}, {"pull_request": {"user": {"login": "rikonor"}}})

        self.assertEqual(raised.exception.field, "gate.pull_request")

    def test_default_allow_permits_unlisted_users(self) -> None:
        verdict = evaluate_pull_request(
            {"gate": {"pull_request": {"default": "allow", "deny": []}}},
            {"pull_request": {"number": 3, "user": {"login": "stranger"}}},
        )

        self.assertTrue(verdict.allowed)
        self.assertEqual(verdict.reason, "gate.pull_request.default is allow")

    def test_explicit_deny_overrides_default_allow(self) -> None:
        verdict = evaluate_pull_request(
            {
                "gate": {
                    "pull_request": {
                        "default": "allow",
                        "deny": ["user:stranger"],
                    }
                }
            },
            {"pull_request": {"number": 3, "user": {"login": "stranger"}}},
        )

        self.assertFalse(verdict.allowed)
        self.assertEqual(verdict.reason, "matched deny entry user:stranger")

    def test_invalid_default_is_rejected(self) -> None:
        with self.assertRaises(GateError) as raised:
            evaluate_pull_request(
                {
                    "gate": {
                        "pull_request": {"default": "maybe", "allow": ["user:rikonor"]}
                    }
                },
                {"pull_request": {"user": {"login": "rikonor"}}},
            )

        self.assertEqual(raised.exception.field, "gate.pull_request.default")

    def test_team_allow_permits_members(self) -> None:
        resolver = FakeTeamResolver({("KnickKnackLabs", "agents", "brownie-ricon")})

        verdict = evaluate_pull_request(
            {
                "gate": {
                    "pull_request": {
                        "default": "deny",
                        "allow": ["team:KnickKnackLabs/agents"],
                    }
                }
            },
            {"pull_request": {"number": 3, "user": {"login": "brownie-ricon"}}},
            team_resolver=resolver,
        )

        self.assertTrue(verdict.allowed)
        self.assertEqual(
            verdict.reason, "matched allow entry team:KnickKnackLabs/agents"
        )
        self.assertEqual(
            resolver.calls, [("KnickKnackLabs", "agents", "brownie-ricon")]
        )

    def test_team_deny_overrides_user_allow(self) -> None:
        resolver = FakeTeamResolver({("KnickKnackLabs", "blocked", "brownie-ricon")})

        verdict = evaluate_pull_request(
            {
                "gate": {
                    "pull_request": {
                        "default": "deny",
                        "allow": ["user:brownie-ricon"],
                        "deny": ["team:KnickKnackLabs/blocked"],
                    }
                }
            },
            {"pull_request": {"number": 3, "user": {"login": "brownie-ricon"}}},
            team_resolver=resolver,
        )

        self.assertFalse(verdict.allowed)
        self.assertEqual(
            verdict.reason, "matched deny entry team:KnickKnackLabs/blocked"
        )

    def test_team_principal_requires_resolver(self) -> None:
        with self.assertRaises(GateError) as raised:
            evaluate_pull_request(
                {
                    "gate": {
                        "pull_request": {
                            "default": "deny",
                            "allow": ["team:KnickKnackLabs/agents"],
                        }
                    }
                },
                {"pull_request": {"number": 3, "user": {"login": "brownie-ricon"}}},
            )

        self.assertEqual(raised.exception.field, "gate.pull_request.allow")
        self.assertIn("team principals require", raised.exception.message)

    def test_invalid_team_principal_shape_is_rejected(self) -> None:
        with self.assertRaises(GateError) as raised:
            evaluate_pull_request(
                {
                    "gate": {
                        "pull_request": {
                            "default": "deny",
                            "allow": ["team:KnickKnackLabs"],
                        }
                    }
                },
                {"pull_request": {"number": 3, "user": {"login": "brownie-ricon"}}},
            )

        self.assertEqual(raised.exception.field, "gate.pull_request.allow")
        self.assertIn("team:<org>/<team-slug>", raised.exception.message)

    def test_unsupported_principal_types_are_rejected(self) -> None:
        with self.assertRaises(GateError) as raised:
            evaluate_pull_request(
                {
                    "gate": {
                        "pull_request": {
                            "default": "deny",
                            "allow": ["org:KnickKnackLabs"],
                        }
                    }
                },
                {"pull_request": {"number": 3, "user": {"login": "brownie-ricon"}}},
            )

        self.assertEqual(raised.exception.field, "gate.pull_request.allow")
        self.assertIn(
            "unsupported principal: org:KnickKnackLabs", raised.exception.message
        )

    def test_missing_login_is_rejected(self) -> None:
        with self.assertRaises(GateError) as raised:
            evaluate_pull_request(
                {
                    "gate": {
                        "pull_request": {"default": "deny", "allow": ["user:rikonor"]}
                    }
                },
                {"pull_request": {"user": {}}},
            )

        self.assertEqual(raised.exception.field, "pull_request.user.login")


class IssueEvaluationTest(unittest.TestCase):
    def test_allowed_issue_author_returns_allowed_verdict(self) -> None:
        verdict = evaluate_issue(
            {
                "gate": {
                    "issue": {
                        "default": "deny",
                        "allow": ["user:rikonor"],
                        "message": "configured issue authors only",
                    }
                }
            },
            {"issue": {"number": 7, "user": {"login": "rikonor"}}},
        )

        self.assertEqual(
            verdict,
            Verdict(
                allowed=True,
                actor="user:rikonor",
                login="rikonor",
                reason="matched allow entry user:rikonor",
                gate="issue",
                message="configured issue authors only",
            ),
        )

    def test_denied_issue_author_returns_denied_verdict(self) -> None:
        verdict = evaluate_issue(
            {"gate": {"issue": {"default": "deny", "allow": ["user:rikonor"]}}},
            {"issue": {"number": 8, "user": {"login": "stranger"}}},
        )

        self.assertFalse(verdict.allowed)
        self.assertEqual(verdict.actor, "user:stranger")
        self.assertEqual(verdict.reason, "user:stranger did not match gate.issue.allow")
        self.assertEqual(verdict.exit_code, 1)

    def test_issue_gate_rejects_pull_request_conversation_events(self) -> None:
        with self.assertRaises(GateError) as raised:
            evaluate_issue(
                {"gate": {"issue": {"default": "deny", "allow": ["user:rikonor"]}}},
                {
                    "issue": {
                        "number": 9,
                        "pull_request": {
                            "url": "https://api.github.com/repos/o/r/pulls/9"
                        },
                        "user": {"login": "rikonor"},
                    }
                },
            )

        self.assertEqual(raised.exception.field, "issue.pull_request")

    def test_missing_issue_policy_raises_gate_error(self) -> None:
        with self.assertRaises(GateError) as raised:
            evaluate_issue({}, {"issue": {"user": {"login": "rikonor"}}})

        self.assertEqual(raised.exception.field, "gate.issue")

    def test_missing_issue_login_is_rejected(self) -> None:
        with self.assertRaises(GateError) as raised:
            evaluate_issue(
                {"gate": {"issue": {"default": "deny", "allow": ["user:rikonor"]}}},
                {"issue": {"user": {}}},
            )

        self.assertEqual(raised.exception.field, "issue.user.login")


class FormattingTest(unittest.TestCase):
    def test_human_verdict_includes_status_actor_reason_and_message(self) -> None:
        verdict = Verdict(
            allowed=False,
            actor="user:stranger",
            login="stranger",
            reason="user:stranger did not match gate.pull_request.allow",
            gate="pull-request",
            message="configured principals only",
        )

        self.assertEqual(
            format_human_verdict(verdict),
            "✗ denied: pull request author user:stranger "
            "(user:stranger did not match gate.pull_request.allow)\n"
            "configured principals only",
        )

    def test_issue_human_verdict_names_issue_author(self) -> None:
        verdict = Verdict(
            allowed=False,
            actor="user:stranger",
            login="stranger",
            reason="user:stranger did not match gate.issue.allow",
            gate="issue",
        )

        self.assertEqual(
            format_human_verdict(verdict),
            "✗ denied: issue author user:stranger "
            "(user:stranger did not match gate.issue.allow)",
        )

    def test_json_payload_is_stable_and_machine_readable(self) -> None:
        output = format_json_payload({"reason": "ok", "allowed": True})

        self.assertEqual(json.loads(output), {"allowed": True, "reason": "ok"})
        self.assertEqual(output, '{"allowed": true, "reason": "ok"}')


if __name__ == "__main__":
    unittest.main(verbosity=2)
