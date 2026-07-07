#!/usr/bin/env python3
"""Unit tests for GitHub Action helpers."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_DIR / "lib"))

import action as permissions_action  # noqa: E402
from permissions import GateError  # noqa: E402


class ActionHelperTest(unittest.TestCase):
    def test_evaluate_from_paths_returns_verdict_and_event_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / "permissions.toml").write_text(
                '[gate.issue]\ndefault = "deny"\nallow = ["user:rikonor"]\n',
                encoding="utf-8",
            )
            (workspace / "event.json").write_text(
                json.dumps({"issue": {"number": 7, "user": {"login": "stranger"}}}),
                encoding="utf-8",
            )

            verdict, event = permissions_action.evaluate_from_paths(
                gate="issue",
                config="permissions.toml",
                event="event.json",
                workspace=workspace,
            )

        self.assertFalse(verdict.allowed)
        self.assertEqual(verdict.actor, "user:stranger")
        self.assertEqual(event["issue"]["number"], 7)

    def test_validate_on_deny_rejects_unknown_values(self) -> None:
        with self.assertRaises(GateError) as raised:
            permissions_action.validate_on_deny("delete")

        self.assertEqual(raised.exception.field, "on-deny")

    def test_parse_bool_input_accepts_true_and_false(self) -> None:
        self.assertTrue(permissions_action.parse_bool_input("true", name="flag"))
        self.assertFalse(permissions_action.parse_bool_input("FALSE", name="flag"))

    def test_parse_bool_input_rejects_other_values(self) -> None:
        with self.assertRaises(GateError) as raised:
            permissions_action.parse_bool_input("yes", name="deny-comment")

        self.assertEqual(raised.exception.field, "deny-comment")

    def test_outputs_for_verdict_formats_action_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / "permissions.toml").write_text(
                '[gate.issue]\ndefault = "deny"\nallow = ["user:rikonor"]\n',
                encoding="utf-8",
            )
            (workspace / "event.json").write_text(
                json.dumps({"issue": {"number": 7, "user": {"login": "rikonor"}}}),
                encoding="utf-8",
            )
            verdict, _ = permissions_action.evaluate_from_paths(
                gate="issue",
                config="permissions.toml",
                event="event.json",
                workspace=workspace,
            )

        outputs = permissions_action.outputs_for_verdict(verdict)

        self.assertEqual(outputs["allowed"], "true")
        self.assertEqual(outputs["actor"], "user:rikonor")
        self.assertEqual(outputs["gate"], "issue")

    def test_close_denied_closes_denied_issue_as_not_planned(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / "permissions.toml").write_text(
                '[gate.issue]\ndefault = "deny"\nallow = ["user:rikonor"]\n',
                encoding="utf-8",
            )
            event = {"issue": {"number": 7, "user": {"login": "stranger"}}}
            (workspace / "event.json").write_text(json.dumps(event), encoding="utf-8")
            verdict, event_payload = permissions_action.evaluate_from_paths(
                gate="issue",
                config="permissions.toml",
                event="event.json",
                workspace=workspace,
            )

            calls: list[tuple[str, str, str, dict[str, object]]] = []

            def fake_request_json(
                method: str, url: str, token: str, payload: dict[str, object]
            ) -> None:
                calls.append((method, url, token, payload))

            with mock.patch.object(
                permissions_action, "request_json", side_effect=fake_request_json
            ):
                permissions_action.close_denied(
                    verdict=verdict,
                    event=event_payload,
                    repository="KnickKnackLabs/permissions",
                    token="token",
                    api_url="https://api.github.test",
                )

        self.assertEqual(
            calls,
            [
                (
                    "PATCH",
                    "https://api.github.test/repos/KnickKnackLabs/permissions/issues/7",
                    "token",
                    {"state": "closed", "state_reason": "not_planned"},
                )
            ],
        )

    def test_close_denied_closes_denied_pull_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / "permissions.toml").write_text(
                '[gate.pull_request]\ndefault = "deny"\nallow = ["user:rikonor"]\n',
                encoding="utf-8",
            )
            event = {"pull_request": {"number": 3, "user": {"login": "stranger"}}}
            (workspace / "event.json").write_text(json.dumps(event), encoding="utf-8")
            verdict, event_payload = permissions_action.evaluate_from_paths(
                gate="pull-request",
                config="permissions.toml",
                event="event.json",
                workspace=workspace,
            )

            calls: list[tuple[str, str, str, dict[str, object]]] = []

            def fake_request_json(
                method: str, url: str, token: str, payload: dict[str, object]
            ) -> None:
                calls.append((method, url, token, payload))

            with mock.patch.object(
                permissions_action, "request_json", side_effect=fake_request_json
            ):
                permissions_action.close_denied(
                    verdict=verdict,
                    event=event_payload,
                    repository="KnickKnackLabs/permissions",
                    token="token",
                    api_url="https://api.github.test",
                )

        self.assertEqual(
            calls,
            [
                (
                    "PATCH",
                    "https://api.github.test/repos/KnickKnackLabs/permissions/pulls/3",
                    "token",
                    {"state": "closed"},
                )
            ],
        )

    def test_apply_denied_side_effects_labels_comments_and_closes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / "permissions.toml").write_text(
                '[gate.issue]\ndefault = "deny"\nallow = ["user:rikonor"]\n'
                'message = "configured principals only"\n',
                encoding="utf-8",
            )
            event = {"issue": {"number": 7, "user": {"login": "stranger"}}}
            (workspace / "event.json").write_text(json.dumps(event), encoding="utf-8")
            verdict, event_payload = permissions_action.evaluate_from_paths(
                gate="issue",
                config="permissions.toml",
                event="event.json",
                workspace=workspace,
            )

            calls: list[tuple[str, str, str, dict[str, object]]] = []

            def fake_request_json(
                method: str, url: str, token: str, payload: dict[str, object]
            ) -> None:
                calls.append((method, url, token, payload))

            with mock.patch.object(
                permissions_action, "request_json", side_effect=fake_request_json
            ):
                notes = permissions_action.apply_denied_side_effects(
                    verdict=verdict,
                    event=event_payload,
                    repository="KnickKnackLabs/permissions",
                    token="token",
                    api_url="https://api.github.test",
                    label="permissions-denied",
                    comment=True,
                )

        self.assertEqual(
            [call[1] for call in calls],
            [
                "https://api.github.test/repos/KnickKnackLabs/permissions/labels",
                "https://api.github.test/repos/KnickKnackLabs/permissions/issues/7/labels",
                "https://api.github.test/repos/KnickKnackLabs/permissions/issues/7/comments",
                "https://api.github.test/repos/KnickKnackLabs/permissions/issues/7",
            ],
        )
        self.assertEqual(calls[1][3], {"labels": ["permissions-denied"]})
        comment_body = str(calls[2][3]["body"])
        self.assertIn(
            "[permissions](https://github.com/KnickKnackLabs/permissions)",
            comment_body,
        )
        self.assertIn("@stranger is not currently allowed", comment_body)
        self.assertIn("`gate.issue` policy", comment_body)
        self.assertNotIn("user:stranger", comment_body)
        self.assertEqual(
            notes,
            [
                "Labeled denied issue with permissions-denied.",
                "Commented on denied issue.",
                "Closed denied issue from user:stranger.",
            ],
        )

    def test_apply_denied_side_effects_can_skip_label_and_comment(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / "permissions.toml").write_text(
                '[gate.issue]\ndefault = "deny"\nallow = ["user:rikonor"]\n',
                encoding="utf-8",
            )
            event = {"issue": {"number": 7, "user": {"login": "stranger"}}}
            (workspace / "event.json").write_text(json.dumps(event), encoding="utf-8")
            verdict, event_payload = permissions_action.evaluate_from_paths(
                gate="issue",
                config="permissions.toml",
                event="event.json",
                workspace=workspace,
            )

            calls: list[tuple[str, str, str, dict[str, object]]] = []

            def fake_request_json(
                method: str, url: str, token: str, payload: dict[str, object]
            ) -> None:
                calls.append((method, url, token, payload))

            with mock.patch.object(
                permissions_action, "request_json", side_effect=fake_request_json
            ):
                notes = permissions_action.apply_denied_side_effects(
                    verdict=verdict,
                    event=event_payload,
                    repository="KnickKnackLabs/permissions",
                    token="token",
                    api_url="https://api.github.test",
                    label="",
                    comment=False,
                )

        self.assertEqual(len(calls), 1)
        self.assertEqual(notes, ["Closed denied issue from user:stranger."])


if __name__ == "__main__":
    unittest.main(verbosity=2)
