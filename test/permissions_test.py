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
    evaluate_pull_request,
    format_human_verdict,
    format_json_payload,
    load_config,
    load_event,
    resolve_path,
)


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
            {"pull_request": {"user": {"login": "brownie-ricon"}}},
        )

        self.assertEqual(
            verdict,
            Verdict(
                allowed=True,
                actor="user:brownie-ricon",
                login="brownie-ricon",
                reason="matched allow entry user:brownie-ricon",
                message="configured principals only",
            ),
        )
        self.assertEqual(verdict.exit_code, 0)

    def test_denied_user_returns_denied_verdict(self) -> None:
        verdict = evaluate_pull_request(
            {"gate": {"pull_request": {"default": "deny", "allow": ["user:rikonor"]}}},
            {"pull_request": {"user": {"login": "stranger"}}},
        )

        self.assertFalse(verdict.allowed)
        self.assertEqual(verdict.actor, "user:stranger")
        self.assertEqual(verdict.exit_code, 1)

    def test_missing_policy_raises_gate_error(self) -> None:
        with self.assertRaises(GateError) as raised:
            evaluate_pull_request({}, {"pull_request": {"user": {"login": "rikonor"}}})

        self.assertEqual(raised.exception.field, "gate.pull_request")

    def test_non_deny_default_is_rejected_for_first_slice(self) -> None:
        with self.assertRaises(GateError) as raised:
            evaluate_pull_request(
                {
                    "gate": {
                        "pull_request": {"default": "allow", "allow": ["user:rikonor"]}
                    }
                },
                {"pull_request": {"user": {"login": "rikonor"}}},
            )

        self.assertEqual(raised.exception.field, "gate.pull_request.default")

    def test_unsupported_principal_types_are_rejected(self) -> None:
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
                {"pull_request": {"user": {"login": "brownie-ricon"}}},
            )

        self.assertEqual(raised.exception.field, "gate.pull_request.allow")
        self.assertIn("team:KnickKnackLabs/agents", raised.exception.message)

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


class FormattingTest(unittest.TestCase):
    def test_human_verdict_includes_status_actor_reason_and_message(self) -> None:
        verdict = Verdict(
            allowed=False,
            actor="user:stranger",
            login="stranger",
            reason="user:stranger is not in gate.pull_request.allow",
            message="configured principals only",
        )

        self.assertEqual(
            format_human_verdict(verdict),
            "✗ denied: pull request author user:stranger "
            "(user:stranger is not in gate.pull_request.allow)\n"
            "configured principals only",
        )

    def test_json_payload_is_stable_and_machine_readable(self) -> None:
        output = format_json_payload({"reason": "ok", "allowed": True})

        self.assertEqual(json.loads(output), {"allowed": True, "reason": "ok"})
        self.assertEqual(output, '{"allowed": true, "reason": "ok"}')


if __name__ == "__main__":
    unittest.main(verbosity=2)
